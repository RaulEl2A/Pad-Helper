from datetime import datetime
from statistics import mean, median
from typing import Any, Dict, List, Optional, Tuple
import math


def safe_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        text = str(value).replace(",", "").strip().lower()
        if text in ("", "nan", "none"):
            return 0.0
        number = float(text)
        if math.isnan(number) or math.isinf(number):
            return 0.0
        return number
    except (TypeError, ValueError):
        return 0.0


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(safe_float(value))
    except (TypeError, ValueError):
        return default


def normalize_name(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().split())


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().replace("-", " ").split())


def parse_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%m/%d/%Y %I:%M %p",
        "%m/%d/%Y %H:%M",
        "%m/%d/%y %H:%M",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def classify_time_type(value: Any) -> str:
    text = normalize_text(value).upper()
    if text in ("PUMP", "PUMPING", "PUMP TIME"):
        return "PUMP"
    if text in ("NP", "NON PUMP", "NON PUMP TIME"):
        return "NP"
    if text in ("NPT", "NPT/DT", "NON PRODUCTIVE", "NON PRODUCTIVE TIME"):
        return "NPT"
    return text


def is_completed_frac(row: Dict[str, Any]) -> bool:
    event = normalize_text(row.get("main_event", row.get("event", "")))
    complete = normalize_text(row.get("complete", row.get("completed", "")))
    return event == "frac" and complete in (
        "yes", "y", "true", "1", "complete", "completed"
    )


def get_event_datetime(row: Dict[str, Any]) -> Optional[datetime]:
    for key in ("date_time", "event_datetime", "timestamp", "start_time"):
        result = parse_datetime(row.get(key))
        if result is not None:
            return result
    return None


def build_completed_frac_events(time_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    seen = set()

    for row in time_rows:
        if not is_completed_frac(row):
            continue
        completed_at = get_event_datetime(row)
        well_name = str(row.get("well_name", "")).strip()
        stage_number = safe_float(row.get("stage_number"))
        if completed_at is None or not well_name or stage_number <= 0:
            continue
        key = (normalize_name(well_name), stage_number, completed_at)
        if key in seen:
            continue
        seen.add(key)
        events.append({
            "well_name": well_name,
            "well_key": normalize_name(well_name),
            "stage_number": stage_number,
            "completed_at": completed_at,
        })

    events.sort(key=lambda item: item["completed_at"])
    return events


def build_completion_cycles(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cycles: List[Dict[str, Any]] = []
    ordered = sorted(events, key=lambda item: item["completed_at"])
    for previous, current in zip(ordered, ordered[1:]):
        minutes = (current["completed_at"] - previous["completed_at"]).total_seconds() / 60.0
        if minutes <= 0:
            continue
        cycles.append({
            "well_name": current["well_name"],
            "stage_number": current["stage_number"],
            "started_at": previous["completed_at"],
            "completed_at": current["completed_at"],
            "cycle_minutes": minutes,
        })
    return cycles


def filter_for_average(
    rows: List[Dict[str, Any]],
    average_mode: str,
    average_stage_count: Any,
    start_stage_number: Any,
) -> List[Dict[str, Any]]:
    if str(average_mode).strip().lower() == "from_stage":
        start_stage = safe_float(start_stage_number)
        if start_stage <= 0:
            return rows
        return [row for row in rows if safe_float(row.get("stage_number")) >= start_stage]

    count = safe_int(average_stage_count, 5)
    if count <= 0:
        count = 5
    return rows[-count:]


def summarize_cycles(cycles: List[Dict[str, Any]]) -> Dict[str, Any]:
    values = [safe_float(row.get("cycle_minutes")) for row in cycles]
    values = [value for value in values if value > 0]
    if not values:
        return {"average": 0.0, "median": 0.0, "forecast": 0.0, "count": 0}
    return {
        "average": round(mean(values), 1),
        "median": round(median(values), 1),
        "forecast": round(median(values), 1),
        "count": len(values),
    }


def build_stage_time_rows(time_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for index, row in enumerate(time_rows):
        well_raw = row.get("well_name", "")
        stage_raw = row.get("stage_number", "")
        well_key = normalize_name(well_raw)
        stage = str(stage_raw).strip()
        if not well_key or not stage:
            continue
        key = (well_key, stage)
        if key not in grouped:
            grouped[key] = {
                "well_name": str(well_raw).strip(),
                "stage_number": stage,
                "stage_number_value": safe_float(stage_raw),
                "pump": 0.0,
                "np": 0.0,
                "npt": 0.0,
                "sort_index": index,
            }
        duration = safe_float(row.get("duration"))
        time_type = classify_time_type(row.get("time_type", ""))
        if time_type == "PUMP":
            grouped[key]["pump"] += duration
        elif time_type == "NP":
            grouped[key]["np"] += duration
        elif time_type == "NPT":
            grouped[key]["npt"] += duration

    result = []
    for item in grouped.values():
        item["planned"] = item["pump"] + item["np"]
        item["total"] = item["pump"] + item["np"] + item["npt"]
        result.append(item)
    result.sort(key=lambda item: item["sort_index"])
    return result


def average_stage_rows(rows: List[Dict[str, Any]]) -> Dict[str, float]:
    if not rows:
        return {"pump": 0.0, "np": 0.0, "npt": 0.0, "planned": 0.0, "total": 0.0, "count": 0}
    count = len(rows)
    return {
        "pump": round(sum(safe_float(row.get("pump")) for row in rows) / count, 1),
        "np": round(sum(safe_float(row.get("np")) for row in rows) / count, 1),
        "npt": round(sum(safe_float(row.get("npt")) for row in rows) / count, 1),
        "planned": round(sum(safe_float(row.get("planned")) for row in rows) / count, 1),
        "total": round(sum(safe_float(row.get("total")) for row in rows) / count, 1),
        "count": count,
    }


def build_well_status_rows(
    wells: List[str],
    stages_per_well: Dict[str, Any],
    completed_by_well: Dict[str, Any],
) -> List[Dict[str, Any]]:
    result = []
    for well in wells:
        total = safe_float(stages_per_well.get(well, 0))
        completed = safe_float(completed_by_well.get(well, 0))
        result.append({
            "well_name": well,
            "total_stages": total,
            "completed_stages": completed,
            "stages_left": max(0.0, total - completed),
        })
    return result


def calculate_phase_counts(well_status_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    active = [row for row in well_status_rows if safe_float(row.get("stages_left")) > 0]
    if not active:
        return {"active_well_count": 0, "zipper_reference_stages": 0.0,
                "zipper_pumped_stages": 0.0, "single_well_stages": 0.0,
                "single_well_name": ""}
    if len(active) == 1:
        return {"active_well_count": 1, "zipper_reference_stages": 0.0,
                "zipper_pumped_stages": 0.0,
                "single_well_stages": safe_float(active[0].get("stages_left")),
                "single_well_name": str(active[0].get("well_name", ""))}

    minimum_left = min(safe_float(row.get("stages_left")) for row in active)
    single_well_name = ""
    single_well_stages = 0.0
    for row in active:
        remainder = safe_float(row.get("stages_left")) - minimum_left
        if remainder > single_well_stages:
            single_well_stages = remainder
            single_well_name = str(row.get("well_name", ""))
    return {
        "active_well_count": len(active),
        "zipper_reference_stages": round(minimum_left, 1),
        "zipper_pumped_stages": round(minimum_left * len(active), 1),
        "single_well_stages": round(single_well_stages, 1),
        "single_well_name": single_well_name,
    }


def calculate_time_summary(
    time_rows: List[Dict[str, Any]],
    current_well: str,
    total_stages: Any,
    completed_stages: Any,
    average_mode: str = "last_n",
    average_stage_count: Any = 5,
    start_stage_number: Any = "",
    operation_mode: str = "zipper",
    npt_allowance_per_stage: Any = 0,
    wireline_allowance_per_stage: Any = 0,
    use_phase_estimate: bool = False,
    wells: Optional[List[str]] = None,
    stages_per_well: Optional[Dict[str, Any]] = None,
    completed_by_well: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    wells = wells or []
    stages_per_well = stages_per_well or {}
    completed_by_well = completed_by_well or {}

    stage_rows = build_stage_time_rows(time_rows)
    selected_stage_rows = filter_for_average(
        stage_rows, average_mode, average_stage_count, start_stage_number
    )
    pad_avg = average_stage_rows(selected_stage_rows)

    current_rows = [
        row for row in stage_rows
        if normalize_name(row.get("well_name")) == normalize_name(current_well)
    ]
    current_selected = filter_for_average(
        current_rows, average_mode, average_stage_count, start_stage_number
    )
    current_avg = average_stage_rows(current_selected)

    events = build_completed_frac_events(time_rows)
    pad_cycles = build_completion_cycles(events)
    selected_pad_cycles = filter_for_average(
        pad_cycles, average_mode, average_stage_count, start_stage_number
    )
    zipper_summary = summarize_cycles(selected_pad_cycles)

    well_status_rows = build_well_status_rows(wells, stages_per_well, completed_by_well)
    phase = calculate_phase_counts(well_status_rows)
    single_name = phase.get("single_well_name", "")

    same_well_events = [
        event for event in events
        if normalize_name(event.get("well_name")) == normalize_name(single_name)
    ]
    same_well_cycles = build_completion_cycles(same_well_events)
    selected_single_cycles = filter_for_average(
        same_well_cycles, average_mode, average_stage_count, start_stage_number
    )
    single_summary = summarize_cycles(selected_single_cycles)

    npt_allowance = max(0.0, safe_float(npt_allowance_per_stage))
    wireline_allowance = max(0.0, safe_float(wireline_allowance_per_stage))

    zipper_cycle_minutes = zipper_summary["forecast"] + npt_allowance
    if single_summary["forecast"] > 0:
        single_cycle_minutes = (
            single_summary["forecast"] / 2.0
            + wireline_allowance
            + npt_allowance
        )
    else:
        single_cycle_minutes = zipper_cycle_minutes + wireline_allowance

    stages_left = max(0.0, safe_float(total_stages) - safe_float(completed_stages))
    zipper_stages = safe_float(phase.get("zipper_pumped_stages"))
    single_stages = safe_float(phase.get("single_well_stages"))

    standard_hours = (
        stages_left * zipper_cycle_minutes / 60.0
        if zipper_cycle_minutes > 0 else 0.0
    )
    phase_hours = (
        zipper_stages * zipper_cycle_minutes
        + single_stages * single_cycle_minutes
    ) / 60.0 if zipper_cycle_minutes > 0 else 0.0

    if use_phase_estimate and phase_hours > 0:
        final_hours = phase_hours
        method = "phase_cycle"
    else:
        final_hours = standard_hours
        method = "completion_cycle"

    return {
        "operation_mode": operation_mode,
        "average_mode": average_mode,
        "average_stage_count": safe_int(average_stage_count, 5),
        "start_stage_number": start_stage_number,
        "estimate_method": method,
        "stages_left": round(stages_left, 1),

        "pad_avg_pump": pad_avg["pump"],
        "pad_avg_np": pad_avg["np"],
        "pad_avg_npt": pad_avg["npt"],
        "pad_avg_planned": pad_avg["planned"],
        "pad_avg_total": pad_avg["total"],
        "pad_average_sample_count": pad_avg["count"],

        "current_well_avg_pump": current_avg["pump"],
        "current_well_avg_np": current_avg["np"],
        "current_well_avg_npt": current_avg["npt"],
        "current_well_avg_planned": current_avg["planned"],
        "current_well_avg_total": current_avg["total"],
        "current_well_average_sample_count": current_avg["count"],

        "active_well_count": phase.get("active_well_count", 0),
        "zipper_reference_stages": phase.get("zipper_reference_stages", 0),
        "zipper_pumped_stages": phase.get("zipper_pumped_stages", 0),
        "single_well_name": single_name,
        "single_well_stages": phase.get("single_well_stages", 0),

        "zipper_cycle_minutes": round(zipper_cycle_minutes, 1),
        "zipper_cycle_average_minutes": zipper_summary["average"],
        "zipper_cycle_median_minutes": zipper_summary["median"],
        "zipper_cycle_sample_count": zipper_summary["count"],
        "single_well_cycle_minutes": round(single_cycle_minutes, 1),
        "single_well_cycle_average_minutes": single_summary["average"],
        "single_well_cycle_median_minutes": single_summary["median"],
        "single_well_cycle_sample_count": single_summary["count"],

        "zipper_stage_minutes": round(zipper_cycle_minutes, 1),
        "single_well_stage_minutes": round(single_cycle_minutes, 1),
        "estimated_stage_minutes": round(zipper_cycle_minutes, 1),
        "standard_hours_left": round(standard_hours, 1),
        "standard_days_left": round(standard_hours / 24.0, 2) if standard_hours > 0 else 0.0,
        "phase_hours_left": round(phase_hours, 1),
        "phase_days_left": round(phase_hours / 24.0, 2) if phase_hours > 0 else 0.0,
        "hours_left_on_pad": round(final_hours, 1),
        "days_left_on_pad": round(final_hours / 24.0, 2) if final_hours > 0 else 0.0,

        "completed_frac_events": events,
        "pad_completion_cycles": pad_cycles,
        "selected_pad_cycles": selected_pad_cycles,
        "selected_single_well_cycles": selected_single_cycles,
        "stage_rows": stage_rows,
        "well_status_rows": well_status_rows,
    }
