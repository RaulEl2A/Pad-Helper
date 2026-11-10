from __future__ import annotations

import copy
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from logic.calc_chemical import calculate_chemical_forecast
from logic.calc_final_sand import calculate_final_sand
from logic.calc_time import calculate_time_summary
from logic.calc_wellbore import calculate_capacity_to_depth
from logic.excel_loader import ExcelLoader
from logic.pad_data_json import (
    adapt_pad_data_document,
    build_pad_data_document,
    load_pad_data_file,
    save_pad_data_file,
)
from logic.parser_ts import TSParser
from logic.parser_ttmt import TTMTParser
from ui.main_window import PadHelperApp


def build_tmt_data():
    return {
        "list_tab": {
            "customer": "Operator",
            "pad_name": "Pad A",
            "wells": ["Well 1", "Well 2"],
            "well_details": [
                {
                    "field_ticket": "FT-1",
                    "well_name": "Well 1",
                    "well_api": "API-1",
                    "stage_count": 10,
                },
                {
                    "field_ticket": "FT-2",
                    "well_name": "Well 2",
                    "well_api": "API-2",
                    "stage_count": 12,
                },
            ],
            "well_count": 2,
            "stages_per_well": {"Well 1": 10, "Well 2": 12},
            "total_stages": 22,
        },
        "chemdispatch_tab": {
            "chemical_count": 1,
            "chemicals": [
                {"name": "XLB", "current_gallons": 1200, "code": "XL-1"}
            ],
        },
        "sandbol_tab": {
            "sand_on_location": 50000,
            "raw_loads": ["LOAD-1", "LOAD-1"],
        },
        "sandinfo_completed": {
            "completed_by_well": {"Well 1": 2, "Well 2": 3},
            "total_completed_stages": 5,
        },
        "sandinfo_stage_data": {
            "total_design": 220000,
            "stage_rows": [
                {
                    "well_name": "Well 1",
                    "stage_number": 1,
                    "design_mass": 10000,
                    "actual_mass": 9500,
                }
            ],
        },
        "timelog_data": {
            "rows": [
                {
                    "well_name": "Well 1",
                    "stage_number": 1,
                    "attempt": 1,
                    "party": "Frac",
                    "main_event": "Frac",
                    "time_type": "PUMP",
                    "complete": "Yes",
                    "date_time": datetime(2026, 11, 8, 12, 30),
                    "duration": 45,
                }
            ]
        },
        "warnings": [],
    }


def build_ts_data():
    return {
        "Well 1": {
            "source_file": "Well 1.xlsx",
            "pipe_sections": [
                {
                    "pipe_type": "Casing",
                    "top_depth": 0,
                    "bottom_depth": 10000,
                    "capacity_factor": 0.01,
                }
            ],
            "survey_rows": [
                {
                    "measured_depth": 10000,
                    "inclination": 80,
                    "azimuth": 120,
                }
            ],
            "chem_tab": {
                "chemical_names": ["XLB"],
                "stage_strap_rows": [
                    {
                        "stage_number": 1,
                        "excel_row": 7,
                        "usage": {"XLB": 12.5},
                    }
                ],
                "skipped_future_stage_rows": 2,
                "warnings": [],
            },
        },
        "Well 2": {
            "source_file": "Well 2.xlsx",
            "pipe_sections": [],
            "survey_rows": [],
            "chem_tab": {
                "chemical_names": ["XLB"],
                "stage_strap_rows": [],
                "skipped_future_stage_rows": 0,
                "warnings": [],
            },
        },
    }


class WorkbookLoadingTests(unittest.TestCase):
    def test_sheet_names_are_trimmed_and_case_insensitive(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "layout.xlsx"
            with pd.ExcelWriter(path) as writer:
                pd.DataFrame([["value"]]).to_excel(
                    writer,
                    sheet_name=" list ",
                    index=False,
                    header=False,
                )

            sheets = ExcelLoader().read_multiple_sheets(
                path,
                ["List", "SandBOL"],
            )

        self.assertEqual(list(sheets), ["List"])

    def test_ttmt_missing_tabs_and_columns_are_reported(self):
        parsed = TTMTParser({"List": pd.DataFrame([["x"]])}).parse_all()

        self.assertEqual(parsed["list_tab"]["wells"], [])
        self.assertTrue(
            any("Missing required worksheet: TimeLog" in item for item in parsed["warnings"])
        )
        self.assertTrue(
            any("List has 1 columns" in item for item in parsed["warnings"])
        )

    def test_invalid_tmt_numbers_remain_missing_and_warn(self):
        list_sheet = pd.DataFrame([[""] * 10 for _ in range(3)])
        list_sheet.iat[2, 3] = "Well 1"
        list_sheet.iat[2, 9] = "invalid"
        sand_sheet = pd.DataFrame([[""] * 9 for _ in range(14)])
        sand_sheet.iat[13, 0] = "Well 1"
        sand_sheet.iat[13, 1] = 1
        sand_sheet.iat[13, 5] = "invalid mass"

        parsed = TTMTParser(
            {"List": list_sheet, "SandInfo": sand_sheet}
        ).parse_all()

        self.assertIsNone(parsed["list_tab"]["stages_per_well"]["Well 1"])
        self.assertIsNone(parsed["sandinfo_stage_data"]["stage_rows"][0]["design_mass"])
        self.assertIsNone(parsed["sandinfo_stage_data"]["stage_rows"][0]["actual_mass"])
        self.assertTrue(
            any("Invalid numeric value" in item for item in parsed["warnings"])
        )

    def test_duplicate_tmt_wells_are_reported(self):
        list_sheet = pd.DataFrame([[""] * 10 for _ in range(4)])
        list_sheet.iat[2, 3] = "Well 1"
        list_sheet.iat[2, 9] = 10
        list_sheet.iat[3, 3] = "Well 1"
        list_sheet.iat[3, 9] = 10

        parsed = TTMTParser({"List": list_sheet}).parse_all()

        self.assertTrue(
            any("Duplicate well record" in item for item in parsed["warnings"])
        )

    def test_ambiguous_tech_sheet_filename_match_is_not_guessed(self):
        app = PadHelperApp.__new__(PadHelperApp)

        self.assertEqual(
            app._matching_ts_wells("well a well b.xlsx", ["Well A", "Well B"]),
            ["Well A", "Well B"],
        )
        self.assertEqual(
            app._matching_ts_wells("well a.xlsx", ["Well A", "Well B"]),
            ["Well A"],
        )

    def test_ts_invalid_values_and_duplicate_stages_are_reported(self):
        chem = pd.DataFrame([[""] * 6 for _ in range(8)])
        chem.iat[4, 4] = "Chemical A"
        chem.iat[4, 5] = "Chemical B"
        chem.iat[5, 1] = 1
        chem.iat[5, 3] = "StageStrap"
        chem.iat[5, 4] = "invalid"
        chem.iat[5, 5] = 2.5
        chem.iat[6, 1] = 1
        chem.iat[6, 3] = "StageStrap"
        chem.iat[6, 4] = 3
        chem.iat[6, 5] = 4
        chem.iat[7, 1] = "bad stage"
        chem.iat[7, 3] = "StageStrap"
        chem.iat[7, 5] = 5

        parsed = TSParser({"Chem": chem}).parse_all()
        stage_rows = parsed["chem_tab"]["stage_strap_rows"]

        self.assertEqual(len(stage_rows), 2)
        self.assertIsNone(stage_rows[0]["usage"]["Chemical A"])
        self.assertEqual(parsed["chem_tab"]["usage_by_stage"]["1"]["Chemical A"], 3.0)
        self.assertTrue(any("Invalid numeric value" in item for item in parsed["warnings"]))
        self.assertTrue(any("Invalid stage number" in item for item in parsed["warnings"]))
        self.assertTrue(any("more than one active StageStrap row" in item for item in parsed["warnings"]))


class PadDataJsonTests(unittest.TestCase):
    def setUp(self):
        self.document = build_pad_data_document(
            build_tmt_data(),
            build_ts_data(),
            {
                "tmt_file": "Pad.xlsx",
                "tech_sheets": [
                    {"well_name": "Well 1", "file": "Well 1.xlsx"},
                    {"well_name": "Well 2", "file": "Well 2.xlsx"},
                ],
            },
            ["duplicate source warning"],
        )

    def test_multiple_tech_sheets_round_trip_for_existing_calculations(self):
        ttmt_data, ts_data = adapt_pad_data_document(self.document)

        self.assertEqual(set(ts_data), {"Well 1", "Well 2"})
        self.assertEqual(ttmt_data["chemdispatch_tab"]["chemicals"][0]["current_gallons"], 1200)
        self.assertEqual(ttmt_data["sandinfo_stage_data"]["stage_rows"][0]["design_mass"], 10000)
        self.assertEqual(
            ttmt_data["timelog_data"]["rows"][0]["date_time"],
            "2026-11-08T12:30:00",
        )
        self.assertEqual(
            ts_data["Well 1"]["chem_tab"]["stage_strap_rows"][0]["usage"]["XLB"],
            12.5,
        )
        self.assertEqual(ttmt_data["warnings"], [])
        self.assertEqual(
            self.document["diagnostics"]["application"],
            ["duplicate source warning"],
        )

    def test_reexport_does_not_duplicate_application_diagnostics(self):
        ttmt_data, ts_data = adapt_pad_data_document(self.document)
        exported_again = build_pad_data_document(
            ttmt_data,
            ts_data,
            self.document["sources"],
            self.document["diagnostics"]["application"],
        )

        self.assertEqual(
            exported_again["diagnostics"]["tmt"],
            self.document["diagnostics"]["tmt"],
        )
        self.assertEqual(
            exported_again["diagnostics"]["application"],
            self.document["diagnostics"]["application"],
        )

    def test_units_are_explicit_or_unknown(self):
        self.assertEqual(
            self.document["pad"]["sand"]["on_location"]["unit"], "lb"
        )
        self.assertIsNone(
            self.document["pad"]["chemicals"][0]["quantity"]["unit"]
        )
        self.assertIsNone(
            self.document["tech_sheets"][0]["chemical_usage_units"]["XLB"]
        )
        self.assertEqual(
            self.document["tech_sheets"][0]["chemical_stages"][0]["usage"],
            [12.5],
        )

    def test_round_trip_data_is_accepted_by_existing_calculators(self):
        ttmt_data, ts_data = adapt_pad_data_document(self.document)
        chemical_result = calculate_chemical_forecast(
            ttmt_data["chemdispatch_tab"]["chemicals"],
            ts_data=ts_data,
            stages_left_on_pad=17,
            estimated_hours_left=170,
        )
        time_result = calculate_time_summary(
            ttmt_data["timelog_data"]["rows"],
            "Well 1",
            ttmt_data["list_tab"]["total_stages"],
            ttmt_data["sandinfo_completed"]["total_completed_stages"],
            wells=ttmt_data["list_tab"]["wells"],
            stages_per_well=ttmt_data["list_tab"]["stages_per_well"],
            completed_by_well=ttmt_data["sandinfo_completed"]["completed_by_well"],
        )
        sand_result = calculate_final_sand(
            wells=[
                {
                    "well_name": row["well_name"],
                    "stages_left": row["planned_stages"] - row["completed_stages"],
                    "design_prop_per_stage": 10000,
                }
                for well_name in ttmt_data["list_tab"]["wells"]
                for row in [
                    {
                        "well_name": well_name,
                        "planned_stages": ttmt_data["list_tab"]["stages_per_well"][well_name],
                        "completed_stages": ttmt_data["sandinfo_completed"]["completed_by_well"][well_name],
                    }
                ]
            ],
            sand_on_location=ttmt_data["sandbol_tab"]["sand_on_location"],
            average_box_weight=2500,
            spread_stage_count=4,
        )
        wellbore_result = calculate_capacity_to_depth(
            ts_data["Well 1"]["pipe_sections"],
            5000,
        )

        self.assertEqual(chemical_result["chemicals"][0]["usage_source"], "TS StageStrap")
        self.assertEqual(time_result["pad_average_sample_count"], 1)
        self.assertGreater(sand_result["summary"]["total_remaining_design"], 0)
        self.assertEqual(wellbore_result["total_bbl"], 50.0)

    def test_json_file_round_trip(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "pad.json"
            save_pad_data_file(path, self.document)
            loaded = load_pad_data_file(path)

        self.assertEqual(loaded, self.document)

    def test_missing_excel_timestamp_serializes_as_null(self):
        tmt_data = copy.deepcopy(build_tmt_data())
        tmt_data["timelog_data"]["rows"][0]["date_time"] = pd.NaT
        document = build_pad_data_document(tmt_data, {})

        self.assertIsNone(document["pad"]["time_log"][0]["timestamp"])

    def test_invalid_stage_association_is_rejected(self):
        document = copy.deepcopy(self.document)
        document["tech_sheets"][0]["well_name"] = "Unknown Well"

        with self.assertRaisesRegex(ValueError, "not present in the TMT well list"):
            adapt_pad_data_document(document)

    def test_duplicate_tech_sheet_association_is_rejected(self):
        document = copy.deepcopy(self.document)
        document["tech_sheets"].append(copy.deepcopy(document["tech_sheets"][0]))

        with self.assertRaisesRegex(ValueError, "More than one Tech Sheet"):
            adapt_pad_data_document(document)

    def test_inconsistent_units_and_schema_versions_are_rejected(self):
        document = copy.deepcopy(self.document)
        document["pad"]["sand"]["on_location"]["unit"] = "kg"
        with self.assertRaisesRegex(ValueError, "Unsupported unit"):
            adapt_pad_data_document(document)

        document = copy.deepcopy(self.document)
        document["schema_version"] = 2
        with self.assertRaisesRegex(ValueError, "Unsupported Pad Helper JSON schema"):
            adapt_pad_data_document(document)


if __name__ == "__main__":
    unittest.main()