from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional


class StrapDatabase:
    """Read-only access to chemical container charts and defaults."""

    def __init__(self, database_path: Optional[str] = None) -> None:
        if database_path:
            self.database_path = Path(database_path)
        else:
            project_root = Path(__file__).resolve().parent.parent
            self.database_path = project_root / "data" / "chemical_inventory.db"

        if not self.database_path.exists():
            raise FileNotFoundError(
                f"Chemical inventory database not found: {self.database_path}"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def list_container_types(self, active_only: bool = True) -> List[Dict[str, Any]]:
        sql = """
            SELECT name, category, unit, default_capacity,
                   has_strap_chart, active, notes
            FROM container_types
        """
        parameters: tuple = ()

        if active_only:
            sql += " WHERE active = ?"
            parameters = (1,)

        sql += " ORDER BY category, name"

        with self._connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()

        return [dict(row) for row in rows]

    def get_container(self, container_name: str) -> Optional[Dict[str, Any]]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT name, category, unit, default_capacity,
                       has_strap_chart, active, notes
                FROM container_types
                WHERE name = ?
                """,
                (container_name,),
            ).fetchone()

        return dict(row) if row else None

    def get_chart_limits(self, container_name: str) -> Optional[Dict[str, float]]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT MIN(s.inch) AS minimum_inch,
                       MAX(s.inch) AS maximum_inch,
                       MIN(s.quantity) AS minimum_quantity,
                       MAX(s.quantity) AS maximum_quantity
                FROM strap_readings s
                JOIN container_types c ON c.id = s.container_type_id
                WHERE c.name = ?
                """,
                (container_name,),
            ).fetchone()

        if not row or row["minimum_inch"] is None:
            return None

        return dict(row)

    def lookup_quantity(
        self,
        container_name: str,
        inch_reading: Any,
        interpolate: bool = True,
    ) -> Dict[str, Any]:
        inch = self._to_nonnegative_float(inch_reading, "Inch reading")
        container = self.get_container(container_name)

        if container is None:
            raise ValueError(f"Unknown container type: {container_name}")

        if not container["has_strap_chart"]:
            raise ValueError(f"{container_name} does not use a strap chart.")

        limits = self.get_chart_limits(container_name)
        if limits is None:
            raise ValueError(f"No strap readings found for {container_name}.")

        if inch < limits["minimum_inch"] or inch > limits["maximum_inch"]:
            raise ValueError(
                f"Reading must be between {limits['minimum_inch']} and "
                f"{limits['maximum_inch']} inches for {container_name}."
            )

        with self._connect() as connection:
            exact = connection.execute(
                """
                SELECT s.inch, s.quantity
                FROM strap_readings s
                JOIN container_types c ON c.id = s.container_type_id
                WHERE c.name = ? AND s.inch = ?
                """,
                (container_name, inch),
            ).fetchone()

            if exact:
                return {
                    "container_name": container_name,
                    "input_inch": inch,
                    "matched_inch": exact["inch"],
                    "quantity": exact["quantity"],
                    "unit": container["unit"],
                    "match_type": "exact",
                }

            lower = connection.execute(
                """
                SELECT s.inch, s.quantity
                FROM strap_readings s
                JOIN container_types c ON c.id = s.container_type_id
                WHERE c.name = ? AND s.inch < ?
                ORDER BY s.inch DESC
                LIMIT 1
                """,
                (container_name, inch),
            ).fetchone()

            upper = connection.execute(
                """
                SELECT s.inch, s.quantity
                FROM strap_readings s
                JOIN container_types c ON c.id = s.container_type_id
                WHERE c.name = ? AND s.inch > ?
                ORDER BY s.inch ASC
                LIMIT 1
                """,
                (container_name, inch),
            ).fetchone()

        if lower is None or upper is None:
            nearest = lower or upper
            return {
                "container_name": container_name,
                "input_inch": inch,
                "matched_inch": nearest["inch"],
                "quantity": nearest["quantity"],
                "unit": container["unit"],
                "match_type": "nearest",
            }

        if not interpolate:
            lower_distance = abs(inch - lower["inch"])
            upper_distance = abs(upper["inch"] - inch)
            nearest = lower if lower_distance <= upper_distance else upper
            return {
                "container_name": container_name,
                "input_inch": inch,
                "matched_inch": nearest["inch"],
                "quantity": nearest["quantity"],
                "unit": container["unit"],
                "match_type": "nearest",
            }

        span = upper["inch"] - lower["inch"]
        fraction = (inch - lower["inch"]) / span
        quantity = lower["quantity"] + fraction * (
            upper["quantity"] - lower["quantity"]
        )

        return {
            "container_name": container_name,
            "input_inch": inch,
            "matched_inch": inch,
            "quantity": round(quantity, 2),
            "unit": container["unit"],
            "match_type": "interpolated",
            "lower_inch": lower["inch"],
            "upper_inch": upper["inch"],
        }

    def calculate_tote_inventory(
        self,
        full_totes: Any,
        active_tote_remaining: Any = 0,
        tote_size: Any = 330,
    ) -> Dict[str, Any]:
        tote_count = self._to_nonnegative_int(full_totes, "Full totes")
        size = self._to_positive_float(tote_size, "Tote size")
        partial = self._to_nonnegative_float(
            active_tote_remaining,
            "Active tote remaining",
        )

        if partial > size:
            raise ValueError("Active tote remaining cannot exceed the tote size.")

        total = tote_count * size + partial

        return {
            "full_totes": tote_count,
            "tote_size": size,
            "active_tote_remaining": partial,
            "total_quantity": round(total, 2),
            "unit": "gal",
        }

    def calculate_bucket_inventory(
        self,
        full_buckets: Any,
        active_bucket_remaining: Any = 0,
        bucket_weight: Any = 55,
    ) -> Dict[str, Any]:
        bucket_count = self._to_nonnegative_int(full_buckets, "Full buckets")
        weight = self._to_positive_float(bucket_weight, "Bucket weight")
        partial = self._to_nonnegative_float(
            active_bucket_remaining,
            "Active bucket remaining",
        )

        if partial > weight:
            raise ValueError(
                "Active bucket remaining cannot exceed the bucket weight."
            )

        total = bucket_count * weight + partial

        return {
            "full_buckets": bucket_count,
            "bucket_weight": weight,
            "active_bucket_remaining": partial,
            "total_quantity": round(total, 2),
            "unit": "lb",
        }

    def calculate_manual_inventory(
        self,
        quantity: Any,
        unit: str,
    ) -> Dict[str, Any]:
        amount = self._to_nonnegative_float(quantity, "Manual quantity")
        normalized_unit = str(unit).strip().lower()

        if normalized_unit not in ("gal", "lb"):
            raise ValueError("Manual unit must be 'gal' or 'lb'.")

        return {
            "total_quantity": round(amount, 2),
            "unit": normalized_unit,
        }

    @staticmethod
    def _to_nonnegative_float(value: Any, label: str) -> float:
        try:
            number = float(str(value).replace(",", "").strip())
        except (TypeError, ValueError):
            raise ValueError(f"{label} must be a number.")

        if number < 0:
            raise ValueError(f"{label} cannot be negative.")

        return number

    @classmethod
    def _to_positive_float(cls, value: Any, label: str) -> float:
        number = cls._to_nonnegative_float(value, label)

        if number <= 0:
            raise ValueError(f"{label} must be greater than zero.")

        return number

    @staticmethod
    def _to_nonnegative_int(value: Any, label: str) -> int:
        try:
            number = float(str(value).replace(",", "").strip())
        except (TypeError, ValueError):
            raise ValueError(f"{label} must be a whole number.")

        if number < 0 or not number.is_integer():
            raise ValueError(f"{label} must be a nonnegative whole number.")

        return int(number)
