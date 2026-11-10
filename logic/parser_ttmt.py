from typing import Any, Dict, List

import pandas as pd


class TTMTParser:
    REQUIRED_SHEETS = [
        "List", "ChemDispatch", "SetUp", "SandBOL",
        "SandInfo", "strapCharts", "TimeLog",
    ]

    def __init__(self, workbook_sheets: Dict[str, pd.DataFrame]) -> None:
        self.sheets = workbook_sheets
        self.warnings: List[str] = []

    def validate_required_sheets(self):
        missing = []
        for sheet_name in self.REQUIRED_SHEETS:
            if sheet_name not in self.sheets:
                missing.append(sheet_name)
        return missing

    def validate_required_columns(self) -> List[str]:
        minimum_columns = {
            "List": 10,
            "ChemDispatch": 9,
            "SandBOL": 11,
            "SandInfo": 9,
            "TimeLog": 19,
        }
        warnings = []
        for sheet_name, minimum in minimum_columns.items():
            df = self.sheets.get(sheet_name)
            if df is not None and len(df.columns) < minimum:
                warnings.append(
                    f"{sheet_name} has {len(df.columns)} columns; "
                    f"the parser reads through column {minimum}."
                )
        return warnings

    def parse_list_tab(self) -> Dict[str, Any]:
        df = self.sheets["List"]
        customer = self._cell(df, 22, 1)
        pad_name = self._cell(df, 2, 1)
        wells = []
        well_details = []
        stages_per_well = {}
        row = 2

        while row < len(df):
            field_ticket = self._cell(df, row, 2)
            well_name = self._cell(df, row, 3)
            well_api = self._cell(df, row, 4)
            stage_count = self._cell(df, row, 9)
            if self._is_blank(well_name):
                break

            well_name_text = str(well_name).strip()
            stage_count_value = self._safe_float(
                stage_count,
                f"List row {row + 1}, column 10 (stage count)",
            )
            if well_name_text in stages_per_well:
                self.warnings.append(
                    f"Duplicate well record in List: {well_name_text} "
                    f"at row {row + 1}."
                )
            wells.append(well_name_text)
            stages_per_well[well_name_text] = stage_count_value
            well_details.append({
                "field_ticket": self._safe_text(field_ticket),
                "well_name": well_name_text,
                "well_api": self._safe_text(well_api),
                "stage_count": stage_count_value,
            })
            row += 1

        return {
            "customer": customer,
            "pad_name": pad_name,
            "wells": wells,
            "well_details": well_details,
            "well_count": len(wells),
            "stages_per_well": stages_per_well,
            "total_stages": self._safe_sum(list(stages_per_well.values())),
        }

    def parse_chemdispatch_tab(self) -> Dict[str, Any]:
        df = self.sheets["ChemDispatch"]
        chemical_count = 0
        row = 9

        while row < len(df):
            value = self._cell(df, row, 5)
            if self._is_blank(value):
                break
            chemical_count += 1
            row += 1

        chemicals = []
        start_col = 8
        for index in range(chemical_count):
            col = start_col + index
            chemicals.append({
                "name": self._cell(df, 1, col),
                "current_gallons": self._safe_float(
                    self._cell(df, 3, col),
                    f"ChemDispatch row 4, column {col + 1} (current quantity)",
                ),
                "code": self._cell(df, 10, col),
                "column_index": col,
            })

        return {"chemical_count": chemical_count, "chemicals": chemicals}

    def parse_sandbol_tab(self) -> Dict[str, Any]:
        df = self.sheets["SandBOL"]
        sand_on_location = self._safe_float(
            self._cell(df, 10, 10),
            "SandBOL row 11, column 11 (sand on location)",
        )
        raw_loads = []
        row = 12

        while row < len(df):
            value = self._cell(df, row, 5)
            if self._is_blank(value):
                break
            raw_loads.append(str(value).strip())
            row += 1

        counts = {}
        for load in raw_loads:
            counts[load] = counts.get(load, 0) + 1

        cleaned_loads = sorted(counts.keys())
        warnings = []
        for load, count in counts.items():
            if count != 2:
                warnings.append(f"Load {load} appears {count} times")

        return {
            "sand_on_location": sand_on_location,
            "raw_loads": raw_loads,
            "cleaned_loads": cleaned_loads,
            "cleaned_load_count": len(cleaned_loads),
            "warnings": warnings,
        }

    def parse_sandinfo_completed_stages(self) -> Dict[str, Any]:
        df = self.sheets["SandInfo"]
        list_wells = self._list_wells()
        completed_by_well = {}
        row = 2

        while row < len(df):
            well_name = self._cell(df, row, 1)
            completed_stage = self._cell(df, row, 2)
            if self._is_blank(well_name):
                break

            well_name_text = str(well_name).strip()
            if well_name_text.lower() == "totals":
                break
            if well_name_text in list_wells:
                completed_by_well[well_name_text] = self._safe_float(
                    completed_stage,
                    f"SandInfo row {row + 1}, column 3 (completed stages)",
                )
            row += 1

        return {
            "completed_by_well": completed_by_well,
            "total_completed_stages": self._safe_sum(list(completed_by_well.values())),
        }

    def parse_sandinfo_stage_data(self) -> Dict[str, Any]:
        df = self.sheets["SandInfo"]
        total_design = self._safe_float(
            self._cell(df, 4, 6),
            "SandInfo row 5, column 7 (total design)",
        )
        stage_rows = []
        actual_pumped_total = 0.0
        list_wells = set(self._list_wells())
        row = 13

        while row < len(df):
            well_name = self._cell(df, row, 1)
            stage_number = self._cell(df, row, 2)
            design_mass = self._cell(df, row, 6)
            actual_mass = self._cell(df, row, 8)

            if self._is_blank(well_name):
                row += 1
                continue

            well_name_text = str(well_name).strip()
            if well_name_text.lower() == "totals":
                break

            stage_number_value = self._safe_float(
                stage_number,
                f"SandInfo row {row + 1}, column 3 (stage number)",
            )
            design_mass_value = self._safe_float(
                design_mass,
                f"SandInfo row {row + 1}, column 7 (design mass)",
            )
            actual_mass_value = self._safe_float(
                actual_mass,
                f"SandInfo row {row + 1}, column 9 (actual mass)",
            )
            if list_wells and well_name_text not in list_wells:
                self.warnings.append(
                    f"SandInfo row {row + 1} references well "
                    f"{well_name_text!r}, which is not listed on List."
                )
            stage_rows.append({
                "well_name": well_name_text,
                "stage_number": stage_number_value,
                "design_mass": design_mass_value,
                "actual_mass": actual_mass_value,
            })
            actual_pumped_total += actual_mass_value or 0.0
            row += 1

        return {
            "total_design": self._safe_float(total_design),
            "actual_pumped_total": actual_pumped_total,
            "stage_rows": stage_rows,
        }

    def parse_timelog_data(self) -> Dict[str, Any]:
        df = self.sheets["TimeLog"]
        rows = []
        row = 4

        while row < len(df):
            well_name = self._cell(df, row, 10)
            stage_number = self._safe_float(
                self._cell(df, row, 11),
                f"TimeLog row {row + 1}, column 12 (stage number)",
            )
            attempt = self._cell(df, row, 12)
            party = self._cell(df, row, 13)
            main_event = self._cell(df, row, 14)
            time_type = self._cell(df, row, 15)
            complete = self._cell(df, row, 16)
            date_time = self._cell(df, row, 17)
            duration = self._safe_float(
                self._cell(df, row, 18),
                f"TimeLog row {row + 1}, column 19 (duration)",
            )

            if (
                self._is_blank(well_name)
                and self._is_blank(stage_number)
                and self._is_blank(main_event)
                and self._is_blank(time_type)
                and self._is_blank(date_time)
            ):
                row += 1
                continue

            rows.append({
                "well_name": self._safe_text(well_name),
                "stage_number": stage_number,
                "attempt": attempt,
                "party": self._safe_text(party),
                "main_event": self._safe_text(main_event),
                "time_type": self._safe_text(time_type),
                "complete": self._safe_text(complete),
                "date_time": date_time,
                "start_time": date_time,
                "duration": duration,
            })
            row += 1

        return {"rows": rows}

    def parse_all(self) -> Dict[str, Any]:
        missing_sheets = self.validate_required_sheets()
        empty_list = {
            "customer": None,
            "pad_name": None,
            "wells": [],
            "well_details": [],
            "well_count": 0,
            "stages_per_well": {},
            "total_stages": 0.0,
        }
        empty_chemicals = {"chemical_count": 0, "chemicals": []}
        empty_sandbol = {
            "sand_on_location": None,
            "raw_loads": [],
            "cleaned_loads": [],
            "cleaned_load_count": 0,
            "warnings": [],
        }
        empty_completed = {
            "completed_by_well": {},
            "total_completed_stages": 0.0,
        }
        empty_sand_data = {
            "total_design": None,
            "actual_pumped_total": 0.0,
            "stage_rows": [],
        }

        return {
            "list_tab": self.parse_list_tab() if "List" in self.sheets else empty_list,
            "chemdispatch_tab": (
                self.parse_chemdispatch_tab()
                if "ChemDispatch" in self.sheets
                else empty_chemicals
            ),
            "sandbol_tab": (
                self.parse_sandbol_tab() if "SandBOL" in self.sheets else empty_sandbol
            ),
            "sandinfo_completed": (
                self.parse_sandinfo_completed_stages()
                if "SandInfo" in self.sheets
                else empty_completed
            ),
            "sandinfo_stage_data": (
                self.parse_sandinfo_stage_data()
                if "SandInfo" in self.sheets
                else empty_sand_data
            ),
            "timelog_data": (
                self.parse_timelog_data()
                if "TimeLog" in self.sheets
                else {"rows": []}
            ),
            "warnings": (
                [
                    f"Missing required worksheet: {sheet_name}"
                    for sheet_name in missing_sheets
                ]
                + self.validate_required_columns()
                + self.warnings
            ),
        }

    def _cell(self, df: pd.DataFrame, row: int, col: int) -> Any:
        try:
            return df.iat[row, col]
        except (IndexError, KeyError):
            return None

    def _list_wells(self) -> List[str]:
        df = self.sheets.get("List")
        if df is None:
            return []

        wells = []
        row = 2
        while row < len(df):
            value = self._cell(df, row, 3)
            if self._is_blank(value):
                break
            wells.append(str(value).strip())
            row += 1
        return wells

    def _is_blank(self, value: Any) -> bool:
        if value is None:
            return True
        try:
            if pd.isna(value):
                return True
        except (TypeError, ValueError):
            pass
        return str(value).strip() == ""

    def _safe_text(self, value: Any) -> str:
        if self._is_blank(value):
            return ""
        return str(value).strip()

    def _safe_sum(self, values: List[Any]) -> float:
        return sum(self._safe_float(value) or 0.0 for value in values)

    def _safe_float(self, value: Any, context: str = "") -> Any:
        try:
            if value is None or pd.isna(value):
                return None
            text = str(value).replace(",", "").strip()
            if text == "":
                return None
            number = float(text)
            if pd.isna(number) or number in (float("inf"), float("-inf")):
                raise ValueError
            return number
        except (TypeError, ValueError):
            if context:
                self.warnings.append(
                    f"Invalid numeric value at {context}: {value!r}."
                )
            return None
