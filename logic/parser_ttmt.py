from typing import Any, Dict, List

import pandas as pd


class TTMTParser:
    REQUIRED_SHEETS = [
        "List", "ChemDispatch", "SetUp", "SandBOL",
        "SandInfo", "strapCharts", "TimeLog",
    ]

    def __init__(self, workbook_sheets: Dict[str, pd.DataFrame]) -> None:
        self.sheets = workbook_sheets

    def validate_required_sheets(self):
        missing = []
        for sheet_name in self.REQUIRED_SHEETS:
            if sheet_name not in self.sheets:
                missing.append(sheet_name)
        return missing

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
            stage_count_value = self._safe_float(stage_count)
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
                "current_gallons": self._cell(df, 3, col),
                "code": self._cell(df, 10, col),
                "column_index": col,
            })

        return {"chemical_count": chemical_count, "chemicals": chemicals}

    def parse_sandbol_tab(self) -> Dict[str, Any]:
        df = self.sheets["SandBOL"]
        sand_on_location = self._cell(df, 10, 10)
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
        list_wells = self.parse_list_tab().get("wells", [])
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
                completed_by_well[well_name_text] = self._safe_float(completed_stage)
            row += 1

        return {
            "completed_by_well": completed_by_well,
            "total_completed_stages": self._safe_sum(list(completed_by_well.values())),
        }

    def parse_sandinfo_stage_data(self) -> Dict[str, Any]:
        df = self.sheets["SandInfo"]
        total_design = self._cell(df, 4, 6)
        stage_rows = []
        actual_pumped_total = 0.0
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

            actual_mass_value = self._safe_float(actual_mass)
            stage_rows.append({
                "well_name": well_name_text,
                "stage_number": stage_number,
                "design_mass": self._safe_float(design_mass),
                "actual_mass": actual_mass_value,
            })
            actual_pumped_total += actual_mass_value
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
            stage_number = self._cell(df, row, 11)
            attempt = self._cell(df, row, 12)
            party = self._cell(df, row, 13)
            main_event = self._cell(df, row, 14)
            time_type = self._cell(df, row, 15)
            complete = self._cell(df, row, 16)
            date_time = self._cell(df, row, 17)
            duration = self._cell(df, row, 18)

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
        return {
            "list_tab": self.parse_list_tab(),
            "chemdispatch_tab": self.parse_chemdispatch_tab(),
            "sandbol_tab": self.parse_sandbol_tab(),
            "sandinfo_completed": self.parse_sandinfo_completed_stages(),
            "sandinfo_stage_data": self.parse_sandinfo_stage_data(),
            "timelog_data": self.parse_timelog_data(),
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

    def _safe_text(self, value: Any) -> str:
        if self._is_blank(value):
            return ""
        return str(value).strip()

    def _safe_sum(self, values: List[Any]) -> float:
        return sum(self._safe_float(value) for value in values)

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
