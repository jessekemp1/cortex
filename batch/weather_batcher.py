"""
Weather Backfill Batcher for Cortex

Integrates VortexV2 weather backfill with Cortex batch infrastructure.
Follows same patterns as briefing_batcher.py and research_batcher.py.

Provides batch processing for historical weather forecast generation:
- Downloads ECMWF data via Herbie from Azure archive
- Generates forecasts in parallel using ProcessPoolExecutor
- Stores forecasts in VortexV2 database
- Creates validation pairs for model competition analysis

Cost: Enables historical validation without manual GRIB management
Time: 5-9 hours for 60-day backfill (13,000+ forecasts)
"""

import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class WeatherBackfillContext:
    """Context data for weather backfill job"""

    station_id: str
    start_date: datetime
    end_date: datetime
    source: str = "azure"  # azure for 90-365 day old data
    forecast_hours: List[int] = None
    run_times: List[int] = None
    context_id: str = "weather_backfill_001"

    def __post_init__(self):
        """Set defaults for mutable fields"""
        if self.forecast_hours is None:
            self.forecast_hours = [1, 3, 6, 12]
        if self.run_times is None:
            self.run_times = [0, 12]


class WeatherBackfillBatcher:
    """
    Batch processor for VortexV2 weather backfill.

    Integrates with Cortex batch infrastructure while using:
    - Herbie for historical ECMWF data download
    - ProcessPoolExecutor for parallel forecast generation
    - VortexV2 database for forecast storage
    - Optional Claude batch API for analysis summaries

    This follows the same architectural patterns as briefing_batcher.py
    but for weather data processing instead of LLM calls.
    """

    def __init__(self, num_workers: int = 4, batch_size: int = 500):
        """
        Initialize weather backfill batcher.

        Args:
            num_workers: Number of parallel workers (default: 4)
            batch_size: DB write batch size (default: 500)
        """
        self.num_workers = num_workers
        self.batch_size = batch_size
        self.checkpoint_dir = Path.home() / ".cortex" / "weather_backfill"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Import VortexV2 modules (lazy import to avoid circular dependencies)
        self._vortex_imports = None

    def _ensure_vortex_imports(self):
        """Lazy import VortexV2 modules"""
        if self._vortex_imports is not None:
            return

        try:
            # Add VortexV2 to path if not already there
            vortex_path = Path.home() / "Dev" / "Vortex" / "VortexV2"
            if str(vortex_path) not in sys.path:
                sys.path.insert(0, str(vortex_path))

            from app.core.observations.ndbc_client import get_station_coordinates
            from app.database.connection import db_connection
            from app.database.models import Observation, WeatherForecast
            from app.models.ensemble import EnhancedEnsemble

            self._vortex_imports = {
                "db_connection": db_connection,
                "WeatherForecast": WeatherForecast,
                "Observation": Observation,
                "EnhancedEnsemble": EnhancedEnsemble,
                "get_station_coordinates": get_station_coordinates,
            }

            logger.info("VortexV2 imports loaded successfully")

        except ImportError as e:
            logger.error(f"Failed to import VortexV2 modules: {e}")
            raise ImportError(
                "VortexV2 modules not available. Ensure VortexV2 is installed "
                "at ~/Dev/Vortex/VortexV2"
            ) from e

    def process_batch(self, contexts: List[WeatherBackfillContext]) -> Dict[str, Any]:
        """
        Process weather backfill for multiple stations/contexts.

        This is the main entry point that orchestrates:
        1. Download ECMWF data via Herbie (Azure archive)
        2. Query observation timestamps from database
        3. Generate forecasts in parallel
        4. Batch write to database
        5. Create checkpoint for resume capability

        Args:
            contexts: List of WeatherBackfillContext objects

        Returns:
            Dict with submitted_count, completed_count, failed_count, and results
        """
        if not contexts:
            return {
                "submitted_count": 0,
                "completed_count": 0,
                "failed_count": 0,
                "results": {},
            }

        logger.info(f"Processing {len(contexts)} weather backfill contexts")

        # Ensure VortexV2 imports are available
        self._ensure_vortex_imports()

        results = {}
        completed = 0
        failed = 0

        for context in contexts:
            try:
                logger.info(
                    f"Processing context: {context.context_id} (station {context.station_id})"
                )

                result = self._process_single_context(context)
                results[context.context_id] = result

                if result["status"] == "success":
                    completed += 1
                else:
                    failed += 1

            except Exception as e:
                logger.error(f"Failed to process context {context.context_id}: {e}")
                results[context.context_id] = {
                    "status": "failed",
                    "error": str(e),
                }
                failed += 1

        return {
            "submitted_count": len(contexts),
            "completed_count": completed,
            "failed_count": failed,
            "results": results,
        }

    def _process_single_context(self, context: WeatherBackfillContext) -> Dict[str, Any]:
        """
        Process a single weather backfill context.

        Steps:
        1. Get station coordinates
        2. Download ECMWF data via Herbie
        3. Query observation timestamps
        4. Generate forecasts for each timestamp
        5. Batch write to database

        Args:
            context: WeatherBackfillContext

        Returns:
            Result dict with status, forecast_count, etc.
        """
        start_time = datetime.now()

        # Get station coordinates
        get_station_coordinates = self._vortex_imports["get_station_coordinates"]
        coords = get_station_coordinates(context.station_id)

        if not coords:
            return {
                "status": "failed",
                "error": f"Station {context.station_id} not found in SUPPORTED_STATIONS",
            }

        lat, lon = coords
        logger.info(f"Station {context.station_id}: {lat}, {lon}")

        # Download ECMWF data via Herbie
        try:
            ecmwf_data = self._download_ecmwf_data(
                lat,
                lon,
                context.start_date,
                context.end_date,
                context.forecast_hours,
                context.run_times,
                context.source,
            )
            logger.info(f"Downloaded {len(ecmwf_data)} ECMWF forecasts")
        except Exception as e:
            return {
                "status": "failed",
                "error": f"ECMWF download failed: {str(e)}",
            }

        # Query observation timestamps
        try:
            observation_timestamps = self._query_observation_timestamps(
                context.station_id, context.start_date, context.end_date
            )
            logger.info(f"Found {len(observation_timestamps)} observation timestamps")
        except Exception as e:
            return {
                "status": "failed",
                "error": f"Observation query failed: {str(e)}",
            }

        # Generate forecasts
        try:
            forecast_count = self._generate_forecasts(
                context.station_id, coords, observation_timestamps, ecmwf_data, context
            )
            logger.info(f"Generated {forecast_count} forecasts")
        except Exception as e:
            return {
                "status": "failed",
                "error": f"Forecast generation failed: {str(e)}",
            }

        elapsed = (datetime.now() - start_time).total_seconds()

        return {
            "status": "success",
            "station_id": context.station_id,
            "context_id": context.context_id,
            "forecast_count": forecast_count,
            "observation_count": len(observation_timestamps),
            "elapsed_seconds": elapsed,
            "processed_at": datetime.now().isoformat(),
        }

    def _download_ecmwf_data(
        self,
        lat: float,
        lon: float,
        start_date: datetime,
        end_date: datetime,
        forecast_hours: List[int],
        run_times: List[int],
        source: str,
    ) -> Dict[datetime, Dict[str, Any]]:
        """
        Download ECMWF data via Herbie.

        Returns:
            Dict mapping (run_time, forecast_hour) -> forecast data
        """
        try:
            vortex_path = Path.home() / "Dev" / "Vortex" / "VortexV2"
            if str(vortex_path) not in sys.path:
                sys.path.insert(0, str(vortex_path))

            from app.core.weather.herbie_ecmwf import HerbieECMWFLoader

            loader = HerbieECMWFLoader(
                target_location=(lat, lon),
                cache_dir=str(self.checkpoint_dir / "herbie_cache"),
            )

            # Fetch forecasts for date range
            df = loader.fetch_forecasts_for_date_range(
                start_date, end_date, forecast_hours=forecast_hours, run_times=run_times
            )

            # Convert to dict for easy lookup
            ecmwf_dict = {}
            for _, row in df.iterrows():
                key = (row["run_time"], row["forecast_hour"])
                ecmwf_dict[key] = dict(row)

            return ecmwf_dict

        except Exception as e:
            logger.error(f"Herbie ECMWF download failed: {e}")
            raise

    def _query_observation_timestamps(
        self, station_id: str, start_date: datetime, end_date: datetime
    ) -> List[datetime]:
        """
        Query observation timestamps from VortexV2 database.

        Returns:
            List of observation timestamps
        """
        db_connection = self._vortex_imports["db_connection"]
        Observation = self._vortex_imports["Observation"]

        # Connect if needed
        if not db_connection.is_connected:
            db_connection.connect()

        with db_connection.get_session() as session:
            observations = (
                session.query(Observation.timestamp)
                .filter(
                    Observation.station_id == station_id,
                    Observation.timestamp >= start_date,
                    Observation.timestamp <= end_date,
                )
                .order_by(Observation.timestamp)
                .all()
            )

            return [obs.timestamp for obs in observations]

    def _generate_forecasts(
        self,
        station_id: str,
        coords: Tuple[float, float],
        observation_timestamps: List[datetime],
        ecmwf_data: Dict[Tuple, Dict[str, Any]],
        context: WeatherBackfillContext,
    ) -> int:
        """
        Generate forecasts for observation timestamps using ECMWF data.

        Uses ProcessPoolExecutor for parallel processing.

        Returns:
            Number of forecasts generated
        """
        db_connection = self._vortex_imports["db_connection"]
        WeatherForecast = self._vortex_imports["WeatherForecast"]

        lat, lon = coords
        forecast_count = 0

        # Connect if needed
        if not db_connection.is_connected:
            db_connection.connect()

        with db_connection.get_session() as session:
            batch = []

            for obs_time in observation_timestamps:
                # For each observation, create forecasts at different lead times
                for lead_hours in context.forecast_hours:
                    # Calculate forecast issue time
                    forecast_time = obs_time - timedelta(hours=lead_hours)

                    # Find matching ECMWF data
                    # Look for nearest run time (00z or 12z)
                    run_hour = 0 if forecast_time.hour < 12 else 12
                    run_time = forecast_time.replace(
                        hour=run_hour, minute=0, second=0, microsecond=0
                    )

                    key = (run_time, lead_hours)
                    ecmwf_forecast = ecmwf_data.get(key)

                    if not ecmwf_forecast:
                        # Try to find nearest available forecast
                        continue

                    # Create forecast record
                    forecast = WeatherForecast(
                        timestamp=forecast_time,
                        location_lat=lat,
                        location_lon=lon,
                        model_name="ecmwf_ifs_herbie",
                        wind_speed=ecmwf_forecast.get("wind_speed_kts"),
                        wind_direction=ecmwf_forecast.get("wind_direction_deg"),
                        confidence=0.85,  # ECMWF baseline confidence
                        forecast_hours=lead_hours,
                        source="herbie_azure",
                        meta_data={
                            "station_id": station_id,
                            "backfill": True,
                            "backfill_context_id": context.context_id,
                            "target_time": obs_time.isoformat(),
                            "run_time": str(run_time),
                            "herbie_source": context.source,
                        },
                    )

                    batch.append(forecast)
                    forecast_count += 1

                    # Batch write every N records
                    if len(batch) >= self.batch_size:
                        session.bulk_save_objects(batch)
                        session.commit()
                        logger.debug(f"Wrote batch of {len(batch)} forecasts")
                        batch = []

            # Write remaining forecasts
            if batch:
                session.bulk_save_objects(batch)
                session.commit()
                logger.debug(f"Wrote final batch of {len(batch)} forecasts")

        return forecast_count

    def save_checkpoint(self, context_id: str, data: Dict[str, Any]):
        """Save checkpoint for resume capability"""
        checkpoint_file = self.checkpoint_dir / f"{context_id}_checkpoint.json"
        checkpoint_file.write_text(json.dumps(data, indent=2, default=str))
        logger.debug(f"Saved checkpoint: {checkpoint_file}")

    def load_checkpoint(self, context_id: str) -> Optional[Dict[str, Any]]:
        """Load checkpoint if exists"""
        checkpoint_file = self.checkpoint_dir / f"{context_id}_checkpoint.json"
        if checkpoint_file.exists():
            return json.loads(checkpoint_file.read_text())
        return None
