from pathlib import Path
from typing import Any, Dict, List

import pandas as pd


class TSParser:
    def __init__(
        self,
        workbook_sheets: Dict[str, pd.DataFrame],
        file_path: str = "",
    ) -> None:
        self.sheets = workbook_sheets
        self.file_path = file_path

    def parse_wellbore_tab(self) -> Dict[str, Any]:
        if "Wellbore" not in self.sheets:
            return {"pipe_sections": [], "survey_rows": []}

        df = self.sheets["Wellbore"]
        pipe_sections: List[Dict[str, Any]] = []
        row = 13

        while row < len(df):
            pipe_type = self._cell(df, row, 2)
            top_depth = self._cell(df, row, 3)
            bottom_depth = self._cell(df, row, 4)
            capacity_factor = self._cell(df, row, 5)

            if self._is_blank(pipe_type):
                break

            pipe_sections.append({
                "pipe_type": str(pipe_type).strip(),
                "top_depth": self._safe_float(top_depth),
                "bottom_depth": self._safe_float(bottom_depth),
                "capacity_factor": self._safe_float(capacity_factor),
            })
            row += 1

        survey_rows: List[Dict[str, Any]] = []
        row = 32

        while row < len(df):
            md = self._cell(df, row, 1)
            inc = self._cell(df, row, 2)
            azm = self._cell(df, row, 3)

            if self._is_blank(md):
                break

            survey_rows.append({
                "measured_depth": self._safe_float(md),
                "inclination": self._safe_float(inc),
                "azimuth": self._safe_float(azm),
            })
            row += 1

        return {"pipe_sections": pipe_sections, "survey_rows": survey_rows}

    def parse_chem_tab(self) -> Dict[str, Any]:
        if "Chem" not in self.sheets:
            return {
                "chemical_names": [],
                "chemical_columns": {},
                "stage_strap_rows": [],
                "usage_by_stage": {},
                "stage_count": 0,
                "chemical_count": 0,
                "warnings": ["Chem sheet was not loaded."],
            }

        df = self.sheets["Chem"]
        header_row = 4
        stage_col = 1
        category_col = 3
        first_chemical_col = 4

        chemical_columns: Dict[int, str] = {}
        for col in range(first_chemical_col, len(df.columns)):
            header = self._cell(df, header_row, col)
            if self._is_blank(header):
                continue
            header_text = str(header).strip()
            if self._is_nonchemical_header(header_text):
                continue
            chemical_columns[col] = header_text

        chemical_names = list(chemical_columns.values())
        stage_strap_rows: List[Dict[str, Any]] = []
        usage_by_stage: Dict[str, Dict[str, float]] = {}
        warnings: List[str] = []
        current_stage: Any = None
        skipped_future_rows = 0

        for row in range(header_row + 1, len(df)):
            stage_value = self._cell(df, row, stage_col)
            category_value = self._cell(df, row, category_col)

            if not self._is_blank(stage_value):
                parsed_stage = self._parse_stage_number(stage_value)
                if parsed_stage is not None:
                    current_stage = parsed_stage

            if self._normalize_text(category_value) != "stagestrap":
                continue

            if current_stage is None:
                warnings.append(
                    f"StageStrap found on Excel row {row + 1} without a stage number."
                )
                continue

            usage: Dict[str, float] = {}
            for col, chemical_name in chemical_columns.items():
                usage[chemical_name] = self._safe_float(self._cell(df, row, col))

            # Future/unpumped stage templates have an all-zero StageStrap row.
            # Keep a completed stage when one chemical is zero but another is
            # positive. Skip only when every chemical value is zero.
            if not any(value > 0 for value in usage.values()):
                skipped_future_rows += 1
                continue

            stage_key = self._stage_key(current_stage)
            stage_record = {
                "stage_number": current_stage,
                "excel_row": row + 1,
                "usage": usage,
                "has_stage_activity": True,
            }
            stage_strap_rows.append(stage_record)

            if stage_key in usage_by_stage:
                warnings.append(
                    f"Stage {stage_key} has more than one active StageStrap row. "
                    "The last row was retained in usage_by_stage."
                )
            usage_by_stage[stage_key] = usage

        return {
            "chemical_names": chemical_names,
            "chemical_columns": {
                chemical_name: col + 1
                for col, chemical_name in chemical_columns.items()
            },
            "stage_strap_rows": stage_strap_rows,
            "usage_by_stage": usage_by_stage,
            "stage_count": len(stage_strap_rows),
            "chemical_count": len(chemical_names),
            "skipped_future_stage_rows": skipped_future_rows,
            "warnings": warnings,
        }

    def parse_all(self) -> Dict[str, Any]:
        return {
            "wellbore_tab": self.parse_wellbore_tab(),
            "chem_tab": self.parse_chem_tab(),
            "source_file": str(Path(self.file_path).name) if self.file_path else "",
        }

    def _cell(self, df: pd.DataFrame, row: int, col: int) -> Any:
        try:
            return df.iat[row, col]
        except (IndexError, KeyError):
            return None

    def _is_blank(self, value: Any) -> bool:
        if value is None:
            return True
        try:
            if pd.isna(value):
                return True
        except (TypeError, ValueError):
            pass
        return str(value).strip() == ""

    def _safe_float(self, value: Any) -> float:
        try:
            if value is None or pd.isna(value):
                return 0.0
            text = str(value).replace(",", "").strip()
            if text == "":
                return 0.0
            return float(text)
        except (TypeError, ValueError):
            return 0.0

    def _parse_stage_number(self, value: Any) -> Any:
        if self._is_blank(value):
            return None
        try:
            number = float(str(value).replace(",", "").strip())
            return int(number) if number.is_integer() else number
        except (TypeError, ValueError):
            return None

    def _stage_key(self, value: Any) -> str:
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value).strip()

    def _normalize_text(self, value: Any) -> str:
        if self._is_blank(value):
            return ""
        return "".join(str(value).strip().lower().split())

    def _is_nonchemical_header(self, header: str) -> bool:
        return self._normalize_text(header) in {
            "stage#", "stage", "category", "well", "wellname"
        }
