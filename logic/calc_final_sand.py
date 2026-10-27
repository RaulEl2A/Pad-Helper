import math
from typing import Any, Dict, List, Optional


def safe_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0

        text = str(value).replace(",", "").strip()

        if text == "":
            return 0.0

        number = float(text)

        if math.isnan(number) or math.isinf(number):
            return 0.0

        return number

    except Exception:
        return 0.0


def safe_int(value: Any) -> int:
    try:
        number = safe_float(value)
        return int(number)
    except Exception:
        return 0


def is_blank(value: Any) -> bool:
    if value is None:
        return True

    if str(value).strip() == "":
        return True

    return False


def calculate_average_design_from_total(total_sand: Any, stages_left: Any) -> Dict[str, Any]:
    total = safe_float(total_sand)
    stages = safe_float(stages_left)

    if stages <= 0:
        return {
            "average_design": 0,
            "error": "Stages left must be greater than 0.",
        }

    average = total / stages

    return {
        "average_design": round(average),
        "error": "",
    }


def calculate_final_sand(
    wells: List[Dict[str, Any]],
    sand_on_location: Any,
    average_box_weight: Any,
    spread_stage_count: Any,
    pipeline_counts: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    warnings: List[str] = []

    if pipeline_counts is None:
        pipeline_counts = {}

    well_results: List[Dict[str, Any]] = []
    total_remaining_design = 0.0

    if not wells:
        warnings.append("No wells have been added.")

    for well in wells:
        well_name = str(well.get("well_name", "")).strip()
        stages_left_raw = well.get("stages_left")
        design_prop_raw = well.get("design_prop_per_stage")

        stages_left = safe_float(stages_left_raw)
        design_prop_per_stage = safe_float(design_prop_raw)

        display_name = well_name if well_name else "Unnamed well"

        if not well_name:
            warnings.append("A well is missing a well name.")

        if is_blank(stages_left_raw):
            warnings.append(f"{display_name} is missing stages left.")
        elif stages_left <= 0:
            warnings.append(f"{display_name} has 0 or invalid stages left.")

        if is_blank(design_prop_raw):
            warnings.append(f"{display_name} is missing design prop per stage.")
        elif design_prop_per_stage <= 0:
            warnings.append(f"{display_name} has 0 or invalid design prop per stage.")

        well_total = stages_left * design_prop_per_stage
        total_remaining_design += well_total

        well_results.append(
            {
                "well_name": display_name,
                "stages_left": stages_left,
                "design_prop_per_stage": round(design_prop_per_stage),
                "total_prop_needed": round(well_total),
            }
        )

    sand_location_raw = sand_on_location
    avg_box_weight_raw = average_box_weight
    spread_count_raw = spread_stage_count

    sand_location = safe_float(sand_location_raw)
    avg_box_weight = safe_float(avg_box_weight_raw)
    avg_load_weight = avg_box_weight * 2

    if is_blank(sand_location_raw):
        warnings.append("Sand on Location is missing.")
    elif sand_location < 0:
        warnings.append("Sand on Location cannot be negative.")

    if is_blank(avg_box_weight_raw):
        warnings.append("Average Box Weight is missing.")
    elif avg_box_weight <= 0:
        warnings.append("Average Box Weight must be greater than 0.")

    prop_needed_before_rounding = total_remaining_design - sand_location

    surplus = 0.0

    if prop_needed_before_rounding < 0:
        surplus = abs(prop_needed_before_rounding)
        prop_needed_before_rounding = 0.0
        warnings.append("Sand on Location is greater than remaining design. Result shows surplus.")

    raw_loads_needed = 0.0
    total_loads_needed = 0
    total_boxes_needed = 0

    if avg_load_weight > 0 and prop_needed_before_rounding > 0:
        raw_loads_needed = prop_needed_before_rounding / avg_load_weight
        total_loads_needed = math.ceil(raw_loads_needed)
        total_boxes_needed = total_loads_needed * 2

    extra_sand = 0.0

    if total_loads_needed > 0:
        extra_sand = (total_loads_needed * avg_load_weight) - prop_needed_before_rounding

    spread_count = safe_int(spread_count_raw)

    if is_blank(spread_count_raw):
        warnings.append("Spread stage count is missing.")
        extra_per_stage = 0.0
    elif spread_count <= 0:
        warnings.append("Spread stage count must be greater than 0.")
        extra_per_stage = 0.0
    else:
        extra_per_stage = extra_sand / spread_count

    ordered = safe_int(pipeline_counts.get("ordered"))
    at_terminal = safe_int(pipeline_counts.get("at_terminal"))
    in_transit = safe_int(pipeline_counts.get("in_transit"))
    at_destination = safe_int(pipeline_counts.get("at_destination"))

    if ordered < 0:
        warnings.append("Ordered count cannot be negative.")

    if at_terminal < 0:
        warnings.append("At Terminal count cannot be negative.")

    if in_transit < 0:
        warnings.append("In Transit count cannot be negative.")

    if at_destination < 0:
        warnings.append("At Destination count cannot be negative.")

    pipeline_load_credit = ordered + at_terminal + in_transit + at_destination
    pipeline_box_credit = pipeline_load_credit * 2

    loads_still_needed = max(0, total_loads_needed - pipeline_load_credit)
    boxes_still_needed = loads_still_needed * 2

    excess_pipeline_loads = max(0, pipeline_load_credit - total_loads_needed)
    excess_pipeline_boxes = excess_pipeline_loads * 2

    if pipeline_load_credit > total_loads_needed and total_loads_needed > 0:
        warnings.append("Pipeline loads are greater than total loads needed.")

    summary = {
        "total_remaining_design": round(total_remaining_design),
        "sand_on_location": round(sand_location),
        "prop_needed_before_rounding": round(prop_needed_before_rounding),
        "average_box_weight": round(avg_box_weight),
        "average_load_weight": round(avg_load_weight),
        "raw_loads_needed": round(raw_loads_needed, 2),
        "total_loads_needed": total_loads_needed,
        "total_boxes_needed": total_boxes_needed,
        "pipeline_load_credit": pipeline_load_credit,
        "pipeline_box_credit": pipeline_box_credit,
        "loads_still_needed": loads_still_needed,
        "boxes_still_needed": boxes_still_needed,
        "excess_pipeline_loads": excess_pipeline_loads,
        "excess_pipeline_boxes": excess_pipeline_boxes,
        "extra_sand": round(extra_sand),
        "spread_stage_count": spread_count,
        "extra_per_stage": round(extra_per_stage),
        "surplus": round(surplus),

        # Compatibility aliases for the UI.
        # These prevent N/A if the UI is looking for slightly different names.
        "excess_pipeline": excess_pipeline_loads,
        "excess_pipeline_load_count": excess_pipeline_loads,
        "excess_pipeline_box_count": excess_pipeline_boxes,
        "extra_sand_from_rounding": round(extra_sand),
        "extra_per_final_stage": round(extra_per_stage),
        "surplus_sand": round(surplus),
    }

    return {
        "wells": well_results,
        "summary": summary,
        "pipeline": {
            "ordered": ordered,
            "at_terminal": at_terminal,
            "in_transit": in_transit,
            "at_destination": at_destination,
        },
        "warnings": warnings,
    }