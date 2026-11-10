"""Versioned JSON storage for parsed Pad Helper operational data."""

from __future__ import annotations

import json
import math
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


SCHEMA_VERSION = 1


def build_pad_data_document(
    ttmt_data: Dict[str, Any],
    ts_data: Dict[str, Any],
    sources: Optional[Dict[str, Any]] = None,
    diagnostics: Optional[List[str]] = None,
) -> Dict[str, Any]:
    sources = sources or {}
    list_tab = (ttmt_data or {}).get("list_tab", {})
    well_details = {
        str(row.get("well_name", "")).strip(): row
        for row in list_tab.get("well_details", [])
    }
    completed = (ttmt_data or {}).get("sandinfo_completed", {}).get(
        "completed_by_well", {}
    )
    wells = []
    for well_name in list_tab.get("wells", []):
        name = str(well_name).strip()
        detail = well_details.get(name, {})
        wells.append(
            {
                "name": name,
                "field_ticket": detail.get("field_ticket") or None,
                "api": detail.get("well_api") or None,
                "planned_stages": _number(
                    list_tab.get("stages_per_well", {}).get(name)
                ),
                "completed_stages": _number(completed.get(name)),
            }
        )

    chemicals = []
    for chemical in (ttmt_data or {}).get("chemdispatch_tab", {}).get(
        "chemicals", []
    ):
        chemicals.append(
            {
                "name": _text(chemical.get("name")),
                "code": _text(chemical.get("code")),
                "quantity": {
                    "value": _number(chemical.get("current_gallons")),
                    "unit": None,
                },
            }
        )

    sandbol = (ttmt_data or {}).get("sandbol_tab", {})
    sandinfo = (ttmt_data or {}).get("sandinfo_stage_data", {})
    sand_stages = [
        {
            "well_name": _text(row.get("well_name")),
            "stage_number": _number(row.get("stage_number")),
            "design": {
                "value": _number(row.get("design_mass")),
                "unit": "lb",
            },
            "actual": {
                "value": _number(row.get("actual_mass")),
                "unit": "lb",
            },
        }
        for row in sandinfo.get("stage_rows", [])
    ]
    time_log = [
        {
            "well_name": _text(row.get("well_name")),
            "stage_number": _number(row.get("stage_number")),
            "attempt": _json_value(row.get("attempt")),
            "party": _text(row.get("party")),
            "event": _text(row.get("main_event")),
            "time_type": _text(row.get("time_type")),
            "complete": _text(row.get("complete")),
            "timestamp": _json_value(row.get("date_time")),
            "duration": {"value": _number(row.get("duration")), "unit": "min"},
        }
        for row in (ttmt_data or {}).get("timelog_data", {}).get("rows", [])
    ]

    tech_sheets = []
    source_rows = []
    for well_name, well_data in (ts_data or {}).items():
        chem_tab = (well_data or {}).get("chem_tab", {})
        chemical_names = [
            _text(name) for name in chem_tab.get("chemical_names", [])
        ]
        chemical_stages = []
        for row in chem_tab.get("stage_strap_rows", []) or []:
            usage = row.get("usage", {}) or {}
            chemical_stages.append(
                {
                    "stage_number": _number(row.get("stage_number")),
                    "source_row": _number(row.get("excel_row")),
                    "usage": [_number(usage.get(name)) for name in chemical_names],
                }
            )

        tech_sheets.append(
            {
                "well_name": str(well_name).strip(),
                "source_file": _text(well_data.get("source_file")),
                "chemical_names": chemical_names,
                "chemical_usage_units": {name: None for name in chemical_names},
                "chemical_stages": chemical_stages,
                "skipped_future_stage_rows": _number(
                    chem_tab.get("skipped_future_stage_rows")
                ),
                "pipe_sections": [
                    {
                        "pipe_type": _text(row.get("pipe_type")),
                        "top_depth_ft": _number(row.get("top_depth")),
                        "bottom_depth_ft": _number(row.get("bottom_depth")),
                        "capacity_factor_bbl_per_ft": _number(
                            row.get("capacity_factor")
                        ),
                    }
                    for row in well_data.get("pipe_sections", [])
                ],
                "survey": [
                    {
                        "measured_depth_ft": _number(
                            row.get("measured_depth")
                        ),
                        "inclination_deg": _number(row.get("inclination")),
                        "azimuth_deg": _number(row.get("azimuth")),
                    }
                    for row in well_data.get("survey_rows", [])
                ],
                "warnings": list(
                    well_data.get("warnings", chem_tab.get("warnings", [])) or []
                ),
            }
        )
        source_rows.append(
            {
                "well_name": str(well_name).strip(),
                "file": _text(well_data.get("source_file")),
            }
        )

    supplied_sources = sources.get("tech_sheets")
    if supplied_sources:
        source_rows = [
            {
                "well_name": _text(row.get("well_name")),
                "file": _text(row.get("file")),
            }
            for row in supplied_sources
        ]

    document = {
        "schema_version": SCHEMA_VERSION,
        "sources": {
            "tmt_file": _text(sources.get("tmt_file")),
            "tech_sheets": source_rows,
        },
        "pad": {
            "customer": _json_value(list_tab.get("customer")),
            "name": _json_value(list_tab.get("pad_name")),
            "total_planned_stages": _number(list_tab.get("total_stages")),
            "wells": wells,
            "chemicals": chemicals,
            "sand": {
                "on_location": {
                    "value": _number(sandbol.get("sand_on_location")),
                    "unit": "lb",
                },
                "load_ids": [
                    _text(value)
                    for value in sandbol.get("raw_loads", []) or []
                ],
                "stages": sand_stages,
                "total_design_lb": _number(sandinfo.get("total_design")),
            },
            "time_log": time_log,
        },
        "tech_sheets": tech_sheets,
        "diagnostics": {
            "tmt": list((ttmt_data or {}).get("warnings", []) or []),
            "application": list(diagnostics or []),
        },
    }
    return _json_value(document)


def adapt_pad_data_document(
    document: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    _validate_document(document)
    pad = document["pad"]

    wells = pad.get("wells", [])
    well_names = [row["name"] for row in wells]
    stages_per_well = {
        row["name"]: row.get("planned_stages") for row in wells
    }
    completed_by_well = {
        row["name"]: row.get("completed_stages") for row in wells
    }
    list_tab = {
        "customer": pad.get("customer"),
        "pad_name": pad.get("name"),
        "wells": well_names,
        "well_details": [
            {
                "field_ticket": row.get("field_ticket") or "",
                "well_name": row["name"],
                "well_api": row.get("api") or "",
                "stage_count": row.get("planned_stages"),
            }
            for row in wells
        ],
        "well_count": len(well_names),
        "stages_per_well": stages_per_well,
        "total_stages": pad.get("total_planned_stages") or 0.0,
    }

    chemicals = [
        {
            "name": row.get("name") or "",
            "current_gallons": (row.get("quantity") or {}).get("value"),
            "code": row.get("code") or "",
        }
        for row in pad.get("chemicals", [])
    ]

    sand = pad.get("sand", {})
    load_ids = [str(value) for value in sand.get("load_ids", [])]
    load_counts: Dict[str, int] = {}
    for load_id in load_ids:
        load_counts[load_id] = load_counts.get(load_id, 0) + 1
    sand_warnings = [
        f"Load {load_id} appears {count} times"
        for load_id, count in load_counts.items()
        if count != 2
    ]
    sand_stage_rows = [
        {
            "well_name": row.get("well_name") or "",
            "stage_number": row.get("stage_number"),
            "design_mass": (row.get("design") or {}).get("value"),
            "actual_mass": (row.get("actual") or {}).get("value"),
        }
        for row in sand.get("stages", [])
    ]

    ttmt_data = {
        "list_tab": list_tab,
        "chemdispatch_tab": {
            "chemical_count": len(chemicals),
            "chemicals": chemicals,
        },
        "sandbol_tab": {
            "sand_on_location": (sand.get("on_location") or {}).get("value"),
            "raw_loads": load_ids,
            "cleaned_loads": sorted(load_counts),
            "cleaned_load_count": len(load_counts),
            "warnings": sand_warnings,
        },
        "sandinfo_completed": {
            "completed_by_well": completed_by_well,
            "total_completed_stages": _sum(completed_by_well.values()),
        },
        "sandinfo_stage_data": {
            "total_design": sand.get("total_design_lb"),
            "actual_pumped_total": _sum(
                row.get("actual_mass") for row in sand_stage_rows
            ),
            "stage_rows": sand_stage_rows,
        },
        "timelog_data": {
            "rows": [
                {
                    "well_name": row.get("well_name") or "",
                    "stage_number": row.get("stage_number"),
                    "attempt": row.get("attempt"),
                    "party": row.get("party") or "",
                    "main_event": row.get("event") or "",
                    "time_type": row.get("time_type") or "",
                    "complete": row.get("complete") or "",
                    "date_time": row.get("timestamp"),
                    "start_time": row.get("timestamp"),
                    "duration": (row.get("duration") or {}).get("value"),
                }
                for row in pad.get("time_log", [])
            ]
        },
        "warnings": list(document.get("diagnostics", {}).get("tmt", []) or []),
    }

    ts_data: Dict[str, Any] = {}
    for sheet in document.get("tech_sheets", []):
        chemical_names = list(sheet.get("chemical_names", []) or [])
        chemical_columns = {
            name: index for index, name in enumerate(chemical_names, start=5)
        }
        stage_rows = []
        usage_by_stage: Dict[str, Dict[str, Any]] = {}
        for row in sheet.get("chemical_stages", []):
            usage = dict(zip(chemical_names, row.get("usage", [])))
            stage_number = row.get("stage_number")
            stage_rows.append(
                {
                    "stage_number": stage_number,
                    "excel_row": row.get("source_row"),
                    "usage": usage,
                    "has_stage_activity": any(
                        _number(value) is not None and _number(value) > 0
                        for value in usage.values()
                    ),
                }
            )
            usage_by_stage[_stage_key(stage_number)] = usage

        ts_data[sheet["well_name"]] = {
            "pipe_sections": [
                {
                    "pipe_type": row.get("pipe_type") or "",
                    "top_depth": row.get("top_depth_ft"),
                    "bottom_depth": row.get("bottom_depth_ft"),
                    "capacity_factor": row.get("capacity_factor_bbl_per_ft"),
                }
                for row in sheet.get("pipe_sections", [])
            ],
            "survey_rows": [
                {
                    "measured_depth": row.get("measured_depth_ft"),
                    "inclination": row.get("inclination_deg"),
                    "azimuth": row.get("azimuth_deg"),
                }
                for row in sheet.get("survey", [])
            ],
            "chem_tab": {
                "chemical_names": chemical_names,
                "chemical_columns": chemical_columns,
                "stage_strap_rows": stage_rows,
                "usage_by_stage": usage_by_stage,
                "stage_count": len(stage_rows),
                "chemical_count": len(chemical_names),
                "skipped_future_stage_rows": sheet.get(
                    "skipped_future_stage_rows", 0
                ),
                "warnings": list(sheet.get("warnings", []) or []),
            },
            "source_file": sheet.get("source_file") or "",
        }

    return ttmt_data, ts_data


def save_pad_data_file(path: str | Path, document: Dict[str, Any]) -> None:
    _validate_document(document)
    Path(path).write_text(
        json.dumps(_json_value(document), indent=2, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def load_pad_data_file(path: str | Path) -> Dict[str, Any]:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read Pad Helper JSON: {exc}") from exc
    _validate_document(document)
    return document


def _validate_document(document: Any) -> None:
    if not isinstance(document, dict):
        raise ValueError("Pad Helper JSON must contain a JSON object.")
    if document.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported Pad Helper JSON schema version: "
            f"{document.get('schema_version')!r}"
        )
    pad = document.get("pad")
    if not isinstance(pad, dict) or not isinstance(pad.get("wells"), list):
        raise ValueError("Pad Helper JSON is missing the pad.wells array.")
    _validate_numeric_value(
        pad.get("total_planned_stages"), "total planned stages"
    )

    well_names = []
    for well in pad["wells"]:
        if not isinstance(well, dict) or not isinstance(well.get("name"), str):
            raise ValueError("Each pad well must have a string name.")
        name = well["name"].strip()
        if not name:
            raise ValueError("Pad well names cannot be blank.")
        if name in well_names:
            raise ValueError(f"Duplicate TMT well association: {name}")
        well_names.append(name)
        _validate_numeric_value(well.get("planned_stages"), "planned stages")
        _validate_numeric_value(well.get("completed_stages"), "completed stages")

    well_name_set = set(well_names)
    for collection_name in ("chemicals", "time_log"):
        if not isinstance(pad.get(collection_name, []), list):
            raise ValueError(f"pad.{collection_name} must be an array.")

    for chemical in pad.get("chemicals", []):
        if not isinstance(chemical, dict):
            raise ValueError("Each pad chemical must be an object.")
        _validate_measurement(
            chemical.get("quantity"),
            "chemical quantity",
            allowed_units=(None, "gal", "lb"),
        )

    sand = pad.get("sand")
    if not isinstance(sand, dict):
        raise ValueError("Pad Helper JSON is missing the pad.sand object.")
    _validate_measurement(
        sand.get("on_location"),
        "sand on location",
        allowed_units=("lb",),
    )
    if not isinstance(sand.get("stages", []), list):
        raise ValueError("pad.sand.stages must be an array.")
    for stage in sand.get("stages", []):
        if not isinstance(stage, dict):
            raise ValueError("Each sand stage must be an object.")
        _validate_well_reference(stage.get("well_name"), well_name_set, "sand stage")
        _validate_numeric_value(stage.get("stage_number"), "sand stage number")
        _validate_measurement(stage.get("design"), "sand design", ("lb",))
        _validate_measurement(stage.get("actual"), "actual sand", ("lb",))

    for row in pad.get("time_log", []):
        if not isinstance(row, dict):
            raise ValueError("Each time-log row must be an object.")
        _validate_well_reference(row.get("well_name"), well_name_set, "time log")
        _validate_numeric_value(row.get("stage_number"), "time-log stage number")
        if row.get("timestamp") is not None and not isinstance(
            row.get("timestamp"), str
        ):
            raise ValueError("time-log timestamp must be a string or null.")
        _validate_measurement(row.get("duration"), "time-log duration", ("min",))

    tech_sheets = document.get("tech_sheets", [])
    if not isinstance(tech_sheets, list):
        raise ValueError("tech_sheets must be an array.")
    matched_wells = set()
    for sheet in tech_sheets:
        if not isinstance(sheet, dict):
            raise ValueError("Each Tech Sheet entry must be an object.")
        well_name = sheet.get("well_name")
        if well_name not in well_names:
            raise ValueError(
                f"Tech Sheet well {well_name!r} is not present in the TMT well list."
            )
        if well_name in matched_wells:
            raise ValueError(f"More than one Tech Sheet is associated with {well_name}.")
        matched_wells.add(well_name)
        if not isinstance(sheet.get("chemical_stages", []), list):
            raise ValueError("tech_sheets.chemical_stages must be an array.")
        if not isinstance(sheet.get("pipe_sections", []), list):
            raise ValueError("tech_sheets.pipe_sections must be an array.")
        if not isinstance(sheet.get("survey", []), list):
            raise ValueError("tech_sheets.survey must be an array.")
        for stage in sheet.get("chemical_stages", []):
            if not isinstance(stage, dict):
                raise ValueError("Each Tech Sheet chemical stage must be an object.")
            _validate_numeric_value(stage.get("stage_number"), "Tech Sheet stage number")
            if not isinstance(stage.get("chemicals", []), list):
                raise ValueError("Tech Sheet stage chemicals must be an array.")
            for chemical in stage.get("chemicals", []):
                if not isinstance(chemical, dict):
                    raise ValueError("Each Tech Sheet chemical usage must be an object.")
                unit = chemical.get("unit")
                if unit not in (None, "gal", "lb"):
                    raise ValueError(
                        f"Unsupported Tech Sheet chemical unit: {unit!r}."
                    )
                _validate_numeric_value(chemical.get("value"), "chemical usage")
        for section in sheet.get("pipe_sections", []):
            if not isinstance(section, dict):
                raise ValueError("Each Tech Sheet pipe section must be an object.")
            _validate_numeric_value(section.get("top_depth_ft"), "pipe top depth")
            _validate_numeric_value(section.get("bottom_depth_ft"), "pipe bottom depth")
            _validate_numeric_value(
                section.get("capacity_factor_bbl_per_ft"), "pipe capacity factor"
            )
        for survey_row in sheet.get("survey", []):
            if not isinstance(survey_row, dict):
                raise ValueError("Each Tech Sheet survey row must be an object.")
            _validate_numeric_value(
                survey_row.get("measured_depth_ft"), "survey measured depth"
            )
            _validate_numeric_value(
                survey_row.get("inclination_deg"), "survey inclination"
            )
            _validate_numeric_value(survey_row.get("azimuth_deg"), "survey azimuth")


def _validate_measurement(
    measurement: Any,
    label: str,
    allowed_units: Tuple[Optional[str], ...],
) -> None:
    if not isinstance(measurement, dict):
        raise ValueError(f"{label} must contain a value and unit.")
    if measurement.get("unit") not in allowed_units:
        raise ValueError(
            f"Unsupported unit for {label}: {measurement.get('unit')!r}."
        )
    _validate_numeric_value(measurement.get("value"), label)


def _validate_numeric_value(value: Any, label: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number or null.")
    if not math.isfinite(value):
        raise ValueError(f"{label} must be finite.")


def _validate_well_reference(value: Any, well_names: set[str], label: str) -> None:
    if value and value not in well_names:
        raise ValueError(f"{label} references unknown well {value!r}.")


def _number(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return int(number) if number.is_integer() else number


def _sum(values: Any) -> float:
    return sum(_number(value) or 0 for value in values)


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _stage_key(value: Any) -> str:
    number = _number(value)
    if isinstance(number, int):
        return str(number)
    return "" if value is None else str(value).strip()


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    try:
        import pandas as pd

        if pd.isna(value):
            return None
    except (ImportError, TypeError, ValueError):
        pass
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "item"):
        return _json_value(value.item())
    raise TypeError(f"Value of type {type(value).__name__} is not JSON serializable.")