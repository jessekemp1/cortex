# VortexV2 Ensemble Forecasting Implementation Guide

## Executive Summary

This comprehensive analysis provides implementation guidance for three missing ensemble models in VortexV2: `ensemble_raw`, `ensemble_bias_corrected`, and `ensemble_enhanced`. The document covers ensemble strategies, GRIB data processing optimization, LSTM caching mechanisms, and a detailed implementation roadmap.

---

## 1. Ensemble Model Architecture Analysis

### 1.1 Model Hierarchy and Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        VortexV2 Ensemble Architecture                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────────┐    ┌────────────────────┐          │
│  │ RAW INPUTS  │───▶│  ENSEMBLE_RAW   │───▶│ ENSEMBLE_BIAS_     │          │
│  │ (NWP Models)│    │  (Aggregation)  │    │ CORRECTED          │          │
│  └─────────────┘    └─────────────────┘    └────────────────────┘          │
│         │                   │                        │                      │
│         │                   │                        ▼                      │
│         │                   │              ┌────────────────────┐          │
│         │                   └─────────────▶│ ENSEMBLE_ENHANCED  │          │
│         │                                  │ (ML Integration)   │          │
│         │                                  └────────────────────┘          │
│         │                                           │                      │
│         ▼                                           ▼                      │
│  ┌─────────────────────────────────────────────────────────────┐          │
│  │                    GRIB Processing Pipeline                  │          │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │          │
│  │  │ GFS      │  │ ECMWF    │  │ NAM      │  │ HRRR     │    │          │
│  │  │ 0.25°    │  │ 0.1°     │  │ 12km     │  │ 3km      │    │          │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │          │
│  └─────────────────────────────────────────────────────────────┘          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Missing Model Specifications

| Model | Purpose | Input Sources | Output Format | Priority |
|-------|---------|---------------|---------------|----------|
| `ensemble_raw` | Base aggregation of NWP outputs | GFS, ECMWF, NAM, HRRR | NetCDF/Zarr | P0 - Critical |
| `ensemble_bias_corrected` | Statistical correction layer | ensemble_raw + historical obs | NetCDF/Zarr | P0 - Critical |
| `ensemble_enhanced` | ML-augmented predictions | bias_corrected + LSTM features | NetCDF/Zarr | P1 - High |

---

## 2. Ensemble Strategies

### 2.1 Ensemble_Raw Implementation

```python
# ensemble_raw.py - Core Implementation

import numpy as np
import xarray as xr
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import dask.array as da
from scipy import stats

class WeightingStrategy(Enum):
    EQUAL = "equal"
    PERFORMANCE_BASED = "performance_based"
    BAYESIAN_MODEL_AVERAGING = "bma"
    RELIABILITY_WEIGHTED = "reliability_weighted"
    DYNAMIC_SUPERENSEMBLE = "dynamic_superensemble"

@dataclass
class EnsembleMember:
    """Represents a single ensemble member from an NWP model."""
    model_id: str
    member_id: int
    data: xr.DataArray
    weight: float = 1.0
    reliability_score: float = 1.0
    metadata: Dict = field(default_factory=dict)

@dataclass
class EnsembleConfig:
    """Configuration for ensemble generation."""
    weighting_strategy: WeightingStrategy = WeightingStrategy.EQUAL
    min_members: int = 10
    max_members: int = 100
    outlier_threshold: float = 3.0  # Standard deviations
    interpolation_method: str = "bilinear"
    target_resolution: Tuple[float, float] = (0.25, 0.25)
    temporal_window: int = 6  # hours
    variables: List[str] = field(default_factory=lambda: [
        "temperature_2m", "wind_speed_10m", "wind_direction_10m",
        "pressure_msl", "precipitation", "humidity_2m"
    ])

class EnsembleRaw:
    """
    Raw ensemble aggregation system for VortexV2.
    
    Implements multiple weighting strategies and statistical aggregation
    methods for combining NWP model outputs into coherent ensemble products.
    """
    
    def __init__(self, config: EnsembleConfig):
        self.config = config
        self.members: List[EnsembleMember] = []
        self.weight_history: Dict[str, List[float]] = {}
        self._initialized = False
        
    def add_member(self, member: EnsembleMember) -> None:
        """Add an ensemble member with validation."""
        if len(self.members) >= self.config.max_members:
            raise ValueError(f"Maximum ensemble size ({self.config.max_members}) exceeded")
        
        # Validate data dimensions
        if self.members:
            self._validate_compatibility(member)
        
        self.members.append(member)
        self._update_weights()
    
    def _validate_compatibility(self, new_member: EnsembleMember) -> None:
        """Ensure new member is compatible with existing ensemble."""
        reference = self.members[0].data
        
        # Check variable compatibility
        if set(new_member.data.data_vars) != set(reference.data_vars):
            raise ValueError("Variable mismatch in ensemble member")
        
        # Check temporal alignment (allow slight differences)
        time_diff = abs(
            (new_member.data.time[0] - reference.time[0]).values.astype('timedelta64[h]')
        )
        if time_diff > np.timedelta64(self.config.temporal_window, 'h'):
            raise ValueError(f"Temporal misalignment: {time_diff} hours")
    
    def _update_weights(self) -> None:
        """Update member weights based on selected strategy."""
        strategy = self.config.weighting_strategy
        
        if strategy == WeightingStrategy.EQUAL:
            self._apply_equal_weights()
        elif strategy == WeightingStrategy.PERFORMANCE_BASED:
            self._apply_performance_weights()
        elif strategy == WeightingStrategy.BAYESIAN_MODEL_AVERAGING:
            self._apply_bma_weights()
        elif strategy == WeightingStrategy.RELIABILITY_WEIGHTED:
            self._apply_reliability_weights()
        elif strategy == WeightingStrategy.DYNAMIC_SUPERENSEMBLE:
            self._apply_superensemble_weights()
    
    def _apply_equal_weights(self) -> None:
        """Apply equal weights to all members."""
        weight = 1.0 / len(self.members)
        for member in self.members:
            member.weight = weight
    
    def _apply_performance_weights(self) -> None:
        """
        Weight members based on recent forecast performance.
        Uses exponentially weighted RMSE from verification data.
        """
        if not hasattr(self, 'verification_data'):
            self._apply_equal_weights()
            return
        
        errors = []
        for member in self.members:
            rmse = self._calculate_rmse(member, self.verification_data)
            errors.append(rmse)
        
        # Convert errors to weights (inverse relationship)
        errors = np.array(errors)
        # Avoid division by zero
        errors = np.maximum(errors, 1e-6)
        
        # Exponential weighting
        raw_weights = np.exp(-errors / errors.mean())
        normalized_weights = raw_weights / raw_weights.sum()
        
        for member, weight in zip(self.members, normalized_weights):
            member.weight = weight
    
    def _apply_bma_weights(self) -> None:
        """
        Bayesian Model Averaging weights.
        Implements the Raftery et al. (2005) BMA approach.
        """
        if len(self.members) < 2:
            self._apply_equal_weights()
            return
        
        # Initialize with equal weights
        n_members = len(self.members)
        weights = np.ones(n_members) / n_members
        
        # EM algorithm for BMA
        max_iterations = 100
        tolerance = 1e-6
        
        for iteration in range(max_iterations):
            old_weights = weights.copy()
            
            # E-step: Calculate responsibilities
            responsibilities = self._calculate_bma_responsibilities(weights)
            
            # M-step: Update weights
            weights = responsibilities.mean(axis=1)
            weights = weights / weights.sum()
            
            # Check convergence
            if np.abs(weights - old_weights).max() < tolerance:
                break
        
        for member, weight in zip(self.members, weights):
            member.weight = weight
    
    def _calculate_bma_responsibilities(
        self, 
        weights: np.ndarray
    ) -> np.ndarray:
        """Calculate BMA responsibilities for E-step."""
        n_members = len(self.members)
        
        # Get ensemble data as numpy arrays
        data_arrays = [m.data.values.flatten() for m in self.members]
        n_points = len(data_arrays[0])
        
        # Calculate likelihoods (assuming Gaussian)
        likelihoods = np.zeros((n_members, n_points))
        
        for i, data in enumerate(data_arrays):
            ensemble_mean = np.mean([d for d in data_arrays], axis=0)
            ensemble_std = np.std([d for d in data_arrays], axis=0)
            ensemble_std = np.maximum(ensemble_std, 1e-6)
            
            likelihoods[i] = stats.norm.pdf(
                data, 
                loc=ensemble_mean, 
                scale=ensemble_std
            )
        
        # Calculate responsibilities
        weighted_likelihoods = likelihoods * weights[:, np.newaxis]
        total = weighted_likelihoods.sum(axis=0, keepdims=True)
        total = np.maximum(total, 1e-10)
        
        responsibilities = weighted_likelihoods / total
        
        return responsibilities
    
    def _apply_reliability_weights(self) -> None:
        """
        Weight based on reliability diagram analysis.
        Penalizes over/under-confident forecasts.
        """
        for member in self.members:
            # Calculate reliability score from metadata or default
            reliability = member.metadata.get('reliability_score', 1.0)
            member.reliability_score = reliability
        
        total_reliability = sum(m.reliability_score for m in self.members)
        
        for member in self.members:
            member.weight = member.reliability_score / total_reliability
    
    def _apply_superensemble_weights(self) -> None:
        """
        Dynamic superensemble weighting using regression.
        Implements the Krishnamurti et al. approach.
        """
        if not hasattr(self, 'training_data') or self.training_data is None:
            self._apply_equal_weights()
            return
        
        # Prepare training data
        X = np.column_stack([m.data.values.flatten() for m in self.members])
        y = self.training_data.values.flatten()
        
        # Ridge regression for stability
        from sklearn.linear_model import Ridge
        
        model = Ridge(alpha=1.0, fit_intercept=True)
        model.fit(X, y)
        
        # Normalize coefficients to get weights
        coefficients = np.abs(model.coef_)
        weights = coefficients / coefficients.sum()
        
        for member, weight in zip(self.members, weights):
            member.weight = weight
    
    def aggregate(
        self, 
        output_type: str = "mean"
    ) -> xr.Dataset:
        """
        Aggregate ensemble members into final product.
        
        Args:
            output_type: Type of aggregation
                - "mean": Weighted ensemble mean
                - "median": Ensemble median
                - "full": Full probabilistic output with percentiles
                
        Returns:
            xr.Dataset with aggregated ensemble data
        """
        if len(self.members) < self.config.min_members:
            raise ValueError(
                f"Insufficient ensemble members: {len(self.members)} < {self.config.min_members}"
            )
        
        # Remove outliers
        clean_members = self._remove_outliers()
        
        if output_type == "mean":
            return self._weighted_mean(clean_members)
        elif output_type == "median":
            return self._ensemble_median(clean_members)
        elif output_type == "full":
            return self._full_probabilistic(clean_members)
        else:
            raise ValueError(f"Unknown output_type: {output_type}")
    
    def _remove_outliers(self) -> List[EnsembleMember]:
        """Remove statistical outliers from ensemble."""
        threshold = self.config.outlier_threshold
        
        # Calculate ensemble statistics
        all_data = np.stack([m.data.values for m in self.members])
        mean = np.mean(all_data, axis=0)
        std = np.std(all_data, axis=0)
        std = np.maximum(std, 1e-6)
        
        clean_members = []
        for member in self.members:
            z_scores = np.abs((member.data.values - mean) / std)
            max_z = np.max(z_scores)
            
            if max_z <= threshold:
                clean_members.append(member)
        
        return clean_members
    
    def _weighted_mean(
        self, 
        members: List[EnsembleMember]
    ) -> xr.Dataset:
        """Calculate weighted ensemble mean."""
        weights = np.array([m.weight for m in members])
        weights = weights / weights.sum()
        
        result_data = {}
        reference = members[0].data
        
        for var in reference.data_vars:
            var_data = np.stack([m.data[var].values for m in members])
            weighted_mean = np.average(var_data, weights=weights, axis=0)
            
            result_data[var] = xr.DataArray(
                weighted_mean,
                dims=reference[var].dims,
                coords=reference[var].coords,
                attrs={
                    **reference[var].attrs,
                    'ensemble_type': 'weighted_mean',
                    'n_members': len(members)
                }
            )
        
        # Add spread/uncertainty metrics
        for var in reference.data_vars:
            var_data = np.stack([m.data[var].values