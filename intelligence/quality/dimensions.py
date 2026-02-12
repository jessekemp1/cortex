#!/usr/bin/env python3
"""
Data Quality Dimension Checkers

Individual checkers for each quality dimension:
- Completeness: Required fields present
- Consistency: No contradictions
- Accuracy: Factually correct (may flag for AI review)
- Timeliness: Data freshness
- Uniqueness: No duplicates
- Validity: Format/schema valid
"""

import hashlib
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set


class DimensionCheckers:
    """Collection of dimension-specific quality checkers."""

    @staticmethod
    def check_completeness(data: Dict[str, Any], required_fields: List[str]) -> float:
        """
        Check completeness: Are required fields present and non-empty?

        Args:
            data: Data dictionary to check
            required_fields: List of required field names

        Returns:
            Completeness score 0.0-1.0 (1.0 = all fields present and valid)
        """
        if not required_fields:
            return 1.0

        complete_count = 0
        for field in required_fields:
            value = data.get(field)

            # Check field exists and is not empty
            if value is not None:
                if isinstance(value, str) and value.strip():
                    complete_count += 1
                elif isinstance(value, (list, dict)) and len(value) > 0:
                    complete_count += 1
                elif isinstance(value, (int, float, bool)):
                    complete_count += 1

        return complete_count / len(required_fields)

    @staticmethod
    def check_consistency(data: Dict[str, Any], rules: Optional[List[Dict]] = None) -> float:
        """
        Check consistency: No contradictions in the data.

        Args:
            data: Data dictionary to check
            rules: List of consistency rules to check
                   Each rule: {"type": "timestamp_order", "fields": ["created", "updated"]}
                            {"type": "value_range", "field": "confidence", "min": 0.0, "max": 1.0}

        Returns:
            Consistency score 0.0-1.0 (1.0 = all rules pass)
        """
        if not rules:
            # Default consistency checks
            rules = []

            # Check timestamp ordering if both created and updated exist
            if "timestamp" in data and "created_at" in data:
                rules.append({"type": "timestamp_order", "fields": ["created_at", "timestamp"]})

            # Check confidence ranges if present
            if "confidence" in data:
                rules.append({"type": "value_range", "field": "confidence", "min": 0.0, "max": 1.0})

        if not rules:
            return 1.0  # No rules to check, assume consistent

        passed = 0
        for rule in rules:
            rule_type = rule.get("type")

            if rule_type == "timestamp_order":
                fields = rule.get("fields", [])
                if len(fields) == 2:
                    ts1 = data.get(fields[0])
                    ts2 = data.get(fields[1])

                    if ts1 and ts2:
                        try:
                            dt1 = datetime.fromisoformat(ts1) if isinstance(ts1, str) else ts1
                            dt2 = datetime.fromisoformat(ts2) if isinstance(ts2, str) else ts2
                            if dt1 <= dt2:
                                passed += 1
                        except (ValueError, TypeError):
                            pass  # Invalid timestamp format = fail
                    else:
                        passed += 1  # Fields don't exist, skip

            elif rule_type == "value_range":
                field = rule.get("field")
                min_val = rule.get("min")
                max_val = rule.get("max")

                value = data.get(field)
                if value is not None:
                    try:
                        if min_val <= float(value) <= max_val:
                            passed += 1
                    except (ValueError, TypeError):
                        pass
                else:
                    passed += 1  # Field doesn't exist, skip

        return passed / len(rules) if rules else 1.0

    @staticmethod
    def check_accuracy(data: Dict[str, Any], known_facts: Optional[Dict[str, Any]] = None) -> float:
        """
        Check accuracy: Is the information factually correct?

        Note: This is a basic implementation. Full accuracy checking may require
        AI-based validation or external fact-checking.

        Args:
            data: Data dictionary to check
            known_facts: Dictionary of known facts to validate against

        Returns:
            Accuracy score 0.0-1.0 (1.0 = all facts match)
        """
        if not known_facts:
            # Without known facts, we can only do basic sanity checks
            sanity_checks = 0
            total_checks = 0

            # Check: If has outcome, should have followed field
            if "outcome" in data:
                total_checks += 1
                if "followed" in data:
                    sanity_checks += 1

            # Check: If has confidence, it should be numeric
            if "confidence" in data:
                total_checks += 1
                try:
                    float(data["confidence"])
                    sanity_checks += 1
                except (ValueError, TypeError):
                    pass

            # Check: If has files_changed, should be a list
            if "files_changed" in data:
                total_checks += 1
                if isinstance(data.get("files_changed"), list):
                    sanity_checks += 1

            return sanity_checks / total_checks if total_checks > 0 else 1.0

        # Validate against known facts
        matches = 0
        for key, expected_value in known_facts.items():
            if key in data and data[key] == expected_value:
                matches += 1

        return matches / len(known_facts)

    @staticmethod
    def check_timeliness(
        data: Dict[str, Any], timestamp_field: str = "timestamp", max_age_days: int = 30
    ) -> float:
        """
        Check timeliness: Is the data fresh enough for its use case?

        Args:
            data: Data dictionary to check
            timestamp_field: Name of timestamp field
            max_age_days: Maximum acceptable age in days

        Returns:
            Timeliness score 0.0-1.0 (1.0 = very recent, decays with age)
        """
        timestamp_value = data.get(timestamp_field)
        if not timestamp_value:
            return 0.5  # No timestamp = neutral score

        try:
            # Parse timestamp
            if isinstance(timestamp_value, str):
                timestamp = datetime.fromisoformat(timestamp_value)
            elif isinstance(timestamp_value, datetime):
                timestamp = timestamp_value
            else:
                return 0.5  # Unknown format

            # Calculate age
            age = datetime.now() - timestamp
            age_days = age.total_seconds() / 86400

            # Decay score: 1.0 at age 0, 0.5 at max_age, 0.0 at 2*max_age
            if age_days <= 0:
                return 1.0
            elif age_days <= max_age_days:
                return 1.0 - (age_days / max_age_days) * 0.5
            elif age_days <= 2 * max_age_days:
                return 0.5 - ((age_days - max_age_days) / max_age_days) * 0.5
            else:
                return 0.0

        except (ValueError, TypeError):
            return 0.5  # Invalid timestamp = neutral score

    @staticmethod
    def check_uniqueness(
        data: Dict[str, Any], existing_hashes: Set[str], hash_fields: Optional[List[str]] = None
    ) -> float:
        """
        Check uniqueness: Is this a duplicate entry?

        Args:
            data: Data dictionary to check
            existing_hashes: Set of existing content hashes
            hash_fields: Fields to include in hash (None = all fields)

        Returns:
            Uniqueness score 0.0-1.0 (1.0 = unique, 0.0 = duplicate)
        """
        # Create content hash
        if hash_fields:
            content = {k: data.get(k) for k in hash_fields if k in data}
        else:
            content = data

        # Sort keys for consistent hashing
        content_str = str(sorted(content.items()))
        content_hash = hashlib.md5(content_str.encode()).hexdigest()

        # Check if hash exists
        if content_hash in existing_hashes:
            return 0.0  # Duplicate
        else:
            existing_hashes.add(content_hash)
            return 1.0  # Unique

    @staticmethod
    def check_validity(data: Dict[str, Any], schema: Optional[Dict] = None) -> float:
        """
        Check validity: Does data conform to expected format/schema?

        Args:
            data: Data dictionary to check
            schema: Schema definition (simplified Pydantic-like schema)
                   {"field_name": {"type": "str", "pattern": r"^[a-z]+$"}}

        Returns:
            Validity score 0.0-1.0 (1.0 = all validations pass)
        """
        if not schema:
            # Basic type checking without schema
            valid_count = 0
            total_checks = 0

            # Check common fields have expected types
            type_expectations = {
                "timestamp": str,
                "confidence": (int, float),
                "followed": bool,
                "title": str,
                "description": str,
                "files_changed": list,
                "keywords": (list, set),
            }

            for field, expected_type in type_expectations.items():
                if field in data:
                    total_checks += 1
                    if isinstance(data[field], expected_type):
                        valid_count += 1

            return valid_count / total_checks if total_checks > 0 else 1.0

        # Validate against schema
        valid = 0
        for field, rules in schema.items():
            if field not in data:
                continue  # Optional field

            value = data[field]
            field_valid = True

            # Check type
            if "type" in rules:
                expected_type = rules["type"]
                type_map = {
                    "str": str,
                    "int": int,
                    "float": (int, float),
                    "bool": bool,
                    "list": list,
                    "dict": dict,
                }
                if not isinstance(value, type_map.get(expected_type, object)):
                    field_valid = False

            # Check pattern (for strings)
            if field_valid and "pattern" in rules and isinstance(value, str):
                pattern = rules["pattern"]
                if not re.match(pattern, value):
                    field_valid = False

            # Check range (for numbers)
            if field_valid and "min" in rules and isinstance(value, (int, float)):
                if value < rules["min"]:
                    field_valid = False

            if field_valid and "max" in rules and isinstance(value, (int, float)):
                if value > rules["max"]:
                    field_valid = False

            if field_valid:
                valid += 1

        return valid / len(schema) if schema else 1.0
