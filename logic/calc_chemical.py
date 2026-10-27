from __future__ import annotations

from datetime import datetime, timedelta
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Tuple


DEFAULT_STAGE_COUNT = 5
DEFAULT_ZERO_STAGE_CHECK = 2
DEFAULT_LEAD_TIME_HOURS = 24.0


def safe_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        text = str(value).replace(",", "").strip()
        if text == "":
            return 0.0
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def normalize_chemical_name(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    return "".join(character for character in text if character.isalnum())


def stage_sort_value(value: Any) -> Tuple[int, float, str]:
    try:
        return (0, float(value), "")
    except (TypeError, ValueError):
        return (1, 0.0, str(value).strip().lower())


def get_default_profile(chemical_name: str) -> Dict[str, Any]:
    """Return editable first-version defaults for a chemical."""
    key = normalize_chemical_name(chemical_name)

    if "dfr" in key or "pga4045" in key:
        return {
            "profile_type": "dry_bulk",
            "unit": "lb",
            "working_capacity": None,
            "unusable_heel": 0.0,
            "arrival_target": 0.0,
            "delivery_quantity": 35000.0,
            "transport_maximum": None,
            "lead_time_hours": DEFAULT_LEAD_TIME_HOURS,
        }

    if "xlb" in key:
        return {
            "profile_type": "liquid_iso",
            "unit": "gal",
            "working_capacity": 6200.0,
            "unusable_heel": 700.0,
            "arrival_target": 1000.0,
            "delivery_quantity": 3000.0,
            "transport_maximum": 4500.0,
            "lead_time_hours": DEFAULT_LEAD_TIME_HOURS,
        }

    return {
        "profile_type": "liquid_iso",
        "unit": "gal",
        "working_capacity": 6200.0,
        "unusable_heel": 700.0,
        "arrival_target": 1000.0,
        "delivery_quantity": 4000.0,
        "transport_maximum": None,
        "lead_time_hours": DEFAULT_LEAD_TIME_HOURS,
    }


def merge_profile(
    chemical_name: str,
    override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    profile = get_default_profile(chemical_name)
    if override:
        for key, value in override.items():
            if value is not None:
                profile[key] = value
    return profile


def build_ts_chemical_index(ts_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}

    for well_name, well_data in (ts_data or {}).items():
        chem_tab = (well_data or {}).get("chem_tab", {})
        stage_rows = chem_tab.get("stage_strap_rows", []) or []

        for stage_row in stage_rows:
            stage_number = stage_row.get("stage_number")
            usage = stage_row.get("usage", {}) or {}

            for ts_name, raw_value in usage.items():
                key = normalize_chemical_name(ts_name)
                if not key:
                    continue

                item = index.setdefault(
                    key,
                    {"ts_names": set(), "records_by_well": {}},
                )
                item["ts_names"].add(str(ts_name).strip())
                item["records_by_well"].setdefault(str(well_name), []).append(
                    {
                        "well_name": str(well_name),
                        "stage_number": stage_number,
                        "usage": safe_float(raw_value),
                    }
                )

    for item in index.values():
        item["ts_names"] = sorted(item["ts_names"])
        for records in item["records_by_well"].values():
            records.sort(key=lambda row: stage_sort_value(row.get("stage_number")))

    return index


def select_recent_records(
    records_by_well: Dict[str, List[Dict[str, Any]]],
    stage_count: Any = DEFAULT_STAGE_COUNT,
    start_stage_number: Any = None,
) -> List[Dict[str, Any]]:
    count = int(safe_float(stage_count))
    if count <= 0:
        count = DEFAULT_STAGE_COUNT

    use_start_stage = str(start_stage_number).strip() not in ("", "None")
    start_stage = safe_float(start_stage_number)
    selected: List[Dict[str, Any]] = []

    for records in records_by_well.values():
        ordered = sorted(
            records,
            key=lambda row: stage_sort_value(row.get("stage_number")),
        )

        if use_start_stage and start_stage > 0:
            selected.extend(
                row
                for row in ordered
                if safe_float(row.get("stage_number")) >= start_stage
            )
        else:
            selected.extend(ordered[-count:])

    return selected


def classify_zero_usage(
    records_by_well: Dict[str, List[Dict[str, Any]]],
    selected_records: List[Dict[str, Any]],
    consecutive_zero_stages: int = DEFAULT_ZERO_STAGE_CHECK,
) -> Dict[str, Any]:
    """Differentiate recently cut from inactive in the selected design."""
    if consecutive_zero_stages <= 0:
        consecutive_zero_stages = DEFAULT_ZERO_STAGE_CHECK

    selected_has_usage = any(safe_float(row.get("usage")) > 0 for row in selected_records)
    historical_has_usage = any(
        safe_float(row.get("usage")) > 0
        for records in records_by_well.values()
        for row in records
    )

    well_zero_results: Dict[str, bool] = {}
    for well_name, records in records_by_well.items():
        ordered = sorted(
            records,
            key=lambda row: stage_sort_value(row.get("stage_number")),
        )
        recent = ordered[-consecutive_zero_stages:]
        well_zero_results[well_name] = (
            len(recent) >= consecutive_zero_stages
            and all(safe_float(row.get("usage")) == 0 for row in recent)
        )

    latest_all_zero = bool(well_zero_results) and all(well_zero_results.values())

    if latest_all_zero and historical_has_usage:
        status = "Confirmation required: recently zero"
        zero_classification = "possible_cut"
    elif not selected_has_usage:
        status = "Inactive in selected stages"
        zero_classification = "inactive"
    else:
        status = "Active"
        zero_classification = "active"

    return {
        "latest_all_zero": latest_all_zero,
        "historical_has_usage": historical_has_usage,
        "selected_has_usage": selected_has_usage,
        "zero_classification": zero_classification,
        "status": status,
        "well_zero_results": well_zero_results,
    }


def calculate_ts_usage(
    tmt_chemical_name: str,
    ts_index: Dict[str, Dict[str, Any]],
    stage_count: Any = DEFAULT_STAGE_COUNT,
    start_stage_number: Any = None,
    consecutive_zero_stages: int = DEFAULT_ZERO_STAGE_CHECK,
    confirmed_cut: Optional[bool] = None,
) -> Dict[str, Any]:
    key = normalize_chemical_name(tmt_chemical_name)
    match = ts_index.get(key)

    if not match:
        return {
            "matched": False,
            "matched_ts_names": [],
            "average_usage": 0.0,
            "forecast_usage": 0.0,
            "sample_count": 0,
            "selected_records": [],
            "requires_confirmation": False,
            "status": "No TS match",
        }

    records_by_well = match.get("records_by_well", {})
    selected = select_recent_records(
        records_by_well,
        stage_count,
        start_stage_number,
    )
    values = [safe_float(row.get("usage")) for row in selected]
    average_usage = mean(values) if values else 0.0

    zero_result = classify_zero_usage(
        records_by_well,
        selected,
        consecutive_zero_stages,
    )
    requires_confirmation = zero_result["zero_classification"] == "possible_cut"

    if confirmed_cut is True:
        forecast_usage = 0.0
        status = "Confirmed cut"
        requires_confirmation = False
    elif confirmed_cut is False:
        forecast_usage = average_usage
        status = "Kept active by user"
        requires_confirmation = False
    elif requires_confirmation:
        # Do not silently convert the forecast to zero. Display the recent
        # average until the user confirms whether the chemical was cut.
        forecast_usage = average_usage
        status = zero_result["status"]
    elif zero_result["zero_classification"] == "inactive":
        forecast_usage = 0.0
        status = zero_result["status"]
    else:
        forecast_usage = average_usage
        status = "Active"

    return {
        "matched": True,
        "matched_ts_names": match.get("ts_names", []),
        "average_usage": round(average_usage, 2),
        "forecast_usage": round(forecast_usage, 2),
        "sample_count": len(selected),
        "selected_records": selected,
        "requires_confirmation": requires_confirmation,
        "zero_classification": zero_result["zero_classification"],
        "well_zero_results": zero_result["well_zero_results"],
        "status": status,
    }


def normalize_iso_containers(
    current_quantity: Any,
    profile: Dict[str, Any],
    containers: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    capacity = safe_float(profile.get("working_capacity"))

    if containers:
        result = []
        for index, container in enumerate(containers, start=1):
            result.append(
                {
                    "container_id": str(
                        container.get("container_id", f"ISO {index}")
                    ),
                    "status": str(container.get("status", "Reserve")).title(),
                    "current_quantity": max(
                        0.0,
                        safe_float(container.get("current_quantity")),
                    ),
                    "working_capacity": max(
                        0.0,
                        safe_float(
                            container.get("working_capacity", capacity)
                        ),
                    ),
                    "can_receive": bool(container.get("can_receive", True)),
                }
            )
        return result

    return [
        {
            "container_id": "ISO 1",
            "status": "Active",
            "current_quantity": max(0.0, safe_float(current_quantity)),
            "working_capacity": capacity,
            "can_receive": True,
        }
    ]


def calculate_liquid_iso_refill(
    current_quantity: Any,
    usage_per_stage: Any,
    cycle_hours_per_stage: Any,
    stages_left_on_pad: Any,
    profile: Dict[str, Any],
    containers: Optional[List[Dict[str, Any]]] = None,
    receiving_container_id: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    now = now or datetime.now()
    usage = max(0.0, safe_float(usage_per_stage))
    cycle_hours = max(0.0, safe_float(cycle_hours_per_stage))
    stages_left = max(0.0, safe_float(stages_left_on_pad))
    heel = max(0.0, safe_float(profile.get("unusable_heel")))
    target = max(heel, safe_float(profile.get("arrival_target")))
    delivery = max(0.0, safe_float(profile.get("delivery_quantity")))
    transport_maximum = profile.get("transport_maximum")
    lead_time = max(0.0, safe_float(profile.get("lead_time_hours")))

    normalized = normalize_iso_containers(current_quantity, profile, containers)
    active = [row for row in normalized if row["status"] == "Active"]
    reserve = [row for row in normalized if row["status"] == "Reserve"]
    warnings: List[str] = []

    if len(active) == 0:
        warnings.append("No Active ISO is selected.")
    elif len(active) > 1:
        warnings.append("More than one ISO is marked Active.")

    receiving = None
    if receiving_container_id:
        receiving = next(
            (
                row
                for row in normalized
                if row["container_id"] == receiving_container_id
            ),
            None,
        )
    if receiving is None and active:
        receiving = active[0]
    if receiving is None:
        receiving = next(
            (row for row in normalized if row["can_receive"]),
            normalized[0] if normalized else None,
        )

    total_inventory = sum(row["current_quantity"] for row in normalized)
    usable_inventory = sum(
        max(0.0, row["current_quantity"] - heel)
        for row in normalized
        if row["status"] in ("Active", "Reserve")
    )
    pad_requirement = usage * stages_left
    shortage_to_finish = max(0.0, pad_requirement - usable_inventory)

    if usage <= 0 or cycle_hours <= 0 or receiving is None:
        return {
            "containers": normalized,
            "receiving_container_id": (
                receiving["container_id"] if receiving else None
            ),
            "total_inventory": round(total_inventory, 2),
            "usable_inventory": round(usable_inventory, 2),
            "pad_requirement": round(pad_requirement, 2),
            "shortage_to_finish": round(shortage_to_finish, 2),
            "hours_until_arrival_target": None,
            "hours_until_heel": None,
            "order_in_hours": None,
            "order_deadline": None,
            "target_delivery_time": None,
            "load_fits": None,
            "projected_receiving_inventory": None,
            "inventory_after_delivery": None,
            "safety_margin_hours": None,
            "order_status": "Not consuming" if usage <= 0 else "Missing cycle time",
            "warnings": warnings,
        }

    receiving_current = receiving["current_quantity"]
    stages_until_target = max(0.0, receiving_current - target) / usage
    hours_until_target = stages_until_target * cycle_hours
    stages_until_heel = max(0.0, receiving_current - heel) / usage
    hours_until_heel = stages_until_heel * cycle_hours
    order_in_hours = hours_until_target - lead_time

    target_delivery_time = now + timedelta(hours=hours_until_target)
    order_deadline = now + timedelta(hours=max(0.0, order_in_hours))
    order_status = "ORDER NOW" if order_in_hours <= 0 else "Schedule order"

    projected_receiving_inventory = max(
        heel,
        receiving_current - stages_until_target * usage,
    )
    inventory_after_delivery = projected_receiving_inventory + delivery
    load_fits = (
        receiving["can_receive"]
        and inventory_after_delivery <= receiving["working_capacity"]
    )
    safety_margin_hours = hours_until_heel - hours_until_target

    if not load_fits:
        warnings.append(
            "The planned load will not fit in the selected receiving ISO "
            "at the target delivery time."
        )
    if safety_margin_hours < 0:
        warnings.append("Inventory reaches the unusable heel before delivery.")
    if transport_maximum is not None and delivery > safe_float(transport_maximum):
        warnings.append(
            "Planned delivery exceeds the configured transport maximum."
        )
    if not receiving["can_receive"]:
        warnings.append("The selected receiving ISO is not available for delivery.")

    return {
        "containers": normalized,
        "receiving_container_id": receiving["container_id"],
        "total_inventory": round(total_inventory, 2),
        "usable_inventory": round(usable_inventory, 2),
        "pad_requirement": round(pad_requirement, 2),
        "shortage_to_finish": round(shortage_to_finish, 2),
        "stages_until_arrival_target": round(stages_until_target, 2),
        "hours_until_arrival_target": round(hours_until_target, 2),
        "hours_until_heel": round(hours_until_heel, 2),
        "order_in_hours": round(max(0.0, order_in_hours), 2),
        "order_deadline": order_deadline,
        "target_delivery_time": target_delivery_time,
        "projected_receiving_inventory": round(
            projected_receiving_inventory,
            2,
        ),
        "inventory_after_delivery": round(inventory_after_delivery, 2),
        "load_fits": load_fits,
        "safety_margin_hours": round(safety_margin_hours, 2),
        "order_status": order_status,
        "warnings": warnings,
    }


def calculate_dry_refill(
    current_quantity: Any,
    usage_per_stage: Any,
    cycle_hours_per_stage: Any,
    stages_left_on_pad: Any,
    profile: Dict[str, Any],
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    now = now or datetime.now()
    current = max(0.0, safe_float(current_quantity))
    usage = max(0.0, safe_float(usage_per_stage))
    cycle_hours = max(0.0, safe_float(cycle_hours_per_stage))
    stages_left = max(0.0, safe_float(stages_left_on_pad))
    lead_time = max(0.0, safe_float(profile.get("lead_time_hours")))
    delivery = max(0.0, safe_float(profile.get("delivery_quantity")))

    pad_requirement = usage * stages_left
    shortage = max(0.0, pad_requirement - current)

    if usage <= 0:
        return {
            "total_inventory": round(current, 2),
            "usable_inventory": round(current, 2),
            "pad_requirement": round(pad_requirement, 2),
            "shortage_to_finish": round(shortage, 2),
            "hours_until_empty": None,
            "order_in_hours": None,
            "order_deadline": None,
            "target_delivery_time": None,
            "load_fits": None,
            "order_status": "Not consuming",
            "warnings": [],
        }

    stages_until_empty = current / usage
    hours_until_empty = stages_until_empty * cycle_hours if cycle_hours > 0 else None

    if hours_until_empty is None:
        order_in_hours = None
        order_deadline = None
        target_delivery_time = None
        order_status = "Missing cycle time"
    else:
        order_in_hours = max(0.0, hours_until_empty - lead_time)
        order_deadline = now + timedelta(hours=order_in_hours)
        target_delivery_time = now + timedelta(hours=hours_until_empty)
        order_status = "ORDER NOW" if hours_until_empty <= lead_time else "Schedule order"

    capacity = profile.get("working_capacity")
    load_fits = None
    warnings: List[str] = []
    if capacity is not None:
        load_fits = delivery <= safe_float(capacity)
        if not load_fits:
            warnings.append("The planned dry load exceeds configured storage capacity.")

    return {
        "total_inventory": round(current, 2),
        "usable_inventory": round(current, 2),
        "pad_requirement": round(pad_requirement, 2),
        "shortage_to_finish": round(shortage, 2),
        "stages_until_empty": round(stages_until_empty, 2),
        "hours_until_empty": (
            round(hours_until_empty, 2) if hours_until_empty is not None else None
        ),
        "order_in_hours": (
            round(order_in_hours, 2) if order_in_hours is not None else None
        ),
        "order_deadline": order_deadline,
        "target_delivery_time": target_delivery_time,
        "load_fits": load_fits,
        "order_status": order_status,
        "warnings": warnings,
    }


def calculate_chemical_forecast(
    tmt_chemicals: Iterable[Dict[str, Any]],
    ts_data: Optional[Dict[str, Any]] = None,
    tmt_average_usage: Optional[Dict[str, Any]] = None,
    manual_usage: Optional[Dict[str, Any]] = None,
    stage_count: Any = DEFAULT_STAGE_COUNT,
    start_stage_number: Any = None,
    consecutive_zero_stages: int = DEFAULT_ZERO_STAGE_CHECK,
    stages_left_on_pad: Any = 0,
    estimated_hours_left: Any = 0,
    chemical_profiles: Optional[Dict[str, Dict[str, Any]]] = None,
    container_assignments: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    receiving_containers: Optional[Dict[str, str]] = None,
    cut_confirmations: Optional[Dict[str, bool]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Calculate TS usage, inventory life, refill timing, and fit warnings."""
    ts_index = build_ts_chemical_index(ts_data or {})
    tmt_average_usage = tmt_average_usage or {}
    manual_usage = manual_usage or {}
    chemical_profiles = chemical_profiles or {}
    container_assignments = container_assignments or {}
    receiving_containers = receiving_containers or {}
    cut_confirmations = cut_confirmations or {}

    normalized_manual = {
        normalize_chemical_name(name): value
        for name, value in manual_usage.items()
    }
    normalized_tmt_average = {
        normalize_chemical_name(name): value
        for name, value in tmt_average_usage.items()
    }
    normalized_profiles = {
        normalize_chemical_name(name): value
        for name, value in chemical_profiles.items()
    }
    normalized_containers = {
        normalize_chemical_name(name): value
        for name, value in container_assignments.items()
    }
    normalized_receiving = {
        normalize_chemical_name(name): value
        for name, value in receiving_containers.items()
    }
    normalized_confirmations = {
        normalize_chemical_name(name): value
        for name, value in cut_confirmations.items()
    }

    stages_left = max(0.0, safe_float(stages_left_on_pad))
    hours_left = max(0.0, safe_float(estimated_hours_left))
    cycle_hours = hours_left / stages_left if stages_left > 0 and hours_left > 0 else 0.0

    results: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for chemical in tmt_chemicals or []:
        name = str(chemical.get("name", "")).strip()
        if not name:
            continue

        key = normalize_chemical_name(name)
        current_quantity = safe_float(chemical.get("current_gallons"))
        profile = merge_profile(name, normalized_profiles.get(key))

        ts_usage = calculate_ts_usage(
            name,
            ts_index,
            stage_count,
            start_stage_number,
            consecutive_zero_stages,
            normalized_confirmations.get(key),
        )

        if key in normalized_manual:
            usage_per_stage = max(0.0, safe_float(normalized_manual[key]))
            usage_source = "Manual override"
            usage_status = "Manual"
            requires_confirmation = False
        elif ts_usage["matched"]:
            usage_per_stage = ts_usage["forecast_usage"]
            usage_source = "TS StageStrap"
            usage_status = ts_usage["status"]
            requires_confirmation = ts_usage["requires_confirmation"]
        elif key in normalized_tmt_average:
            usage_per_stage = max(0.0, safe_float(normalized_tmt_average[key]))
            usage_source = "TMT average"
            usage_status = "Fallback"
            requires_confirmation = False
        else:
            usage_per_stage = 0.0
            usage_source = "No source"
            usage_status = "Missing usage"
            requires_confirmation = False
            warnings.append(f"No usage source found for {name}.")

        if profile["profile_type"] == "dry_bulk":
            refill = calculate_dry_refill(
                current_quantity,
                usage_per_stage,
                cycle_hours,
                stages_left,
                profile,
                now,
            )
        else:
            refill = calculate_liquid_iso_refill(
                current_quantity,
                usage_per_stage,
                cycle_hours,
                stages_left,
                profile,
                normalized_containers.get(key),
                normalized_receiving.get(key),
                now,
            )

        for warning in refill.get("warnings", []):
            warnings.append(f"{name}: {warning}")

        results.append(
            {
                "chemical_name": name,
                "current_quantity": round(current_quantity, 2),
                "unit": profile["unit"],
                "usage_per_stage": round(usage_per_stage, 2),
                "usage_source": usage_source,
                "usage_status": usage_status,
                "ts_sample_count": ts_usage.get("sample_count", 0),
                "matched_ts_names": ts_usage.get("matched_ts_names", []),
                "requires_cut_confirmation": requires_confirmation,
                "profile": profile,
                "cycle_hours_per_stage": round(cycle_hours, 3),
                **refill,
            }
        )

    return {
        "chemicals": results,
        "warnings": warnings,
        "cycle_hours_per_stage": round(cycle_hours, 3),
        "ts_chemical_match_count": sum(
            1 for row in results if row["usage_source"] == "TS StageStrap"
        ),
        "confirmation_required_count": sum(
            1 for row in results if row["requires_cut_confirmation"]
        ),
    }
