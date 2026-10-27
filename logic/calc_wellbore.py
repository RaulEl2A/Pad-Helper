import math
from typing import Any, Dict, List


def safe_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        text = str(value).replace(",", "").strip()
        if text == "":
            return 0.0
        return float(text)
    except Exception:
        return 0.0


def calculate_capacity_to_depth(
    pipe_sections: List[Dict[str, Any]],
    selected_depth: Any,
) -> Dict[str, Any]:
    target_depth = safe_float(selected_depth)

    total_bbl = 0.0
    included_sections = []

    for section in pipe_sections:
        pipe_type = section.get("pipe_type", "")
        top = safe_float(section.get("top_depth"))
        bottom = safe_float(section.get("bottom_depth"))
        factor = safe_float(section.get("capacity_factor"))

        if target_depth <= top:
            continue

        used_bottom = min(bottom, target_depth)
        used_length = max(0.0, used_bottom - top)

        if used_length <= 0:
            continue

        section_bbl = used_length * factor
        total_bbl += section_bbl

        included_sections.append(f"{pipe_type}: {top:.0f}-{used_bottom:.0f} ft")

        if target_depth <= bottom:
            break

    return {
        "total_bbl": round(total_bbl, 2),
        "included_sections": included_sections,
    }


def calculate_sand_in_wellbore(ppa: Any, barrels_after_sand_started: Any) -> float:
    ppa_value = safe_float(ppa)
    bbl_value = safe_float(barrels_after_sand_started)
    pounds = ppa_value * bbl_value * 42.0
    return round(pounds)


def minimum_curvature_step(
    md1: float,
    inc1_deg: float,
    az1_deg: float,
    md2: float,
    inc2_deg: float,
    az2_deg: float,
) -> Dict[str, float]:
    dmd = md2 - md1
    if dmd <= 0:
        return {"north": 0.0, "east": 0.0, "tvd": 0.0}

    inc1 = math.radians(inc1_deg)
    inc2 = math.radians(inc2_deg)
    az1 = math.radians(az1_deg)
    az2 = math.radians(az2_deg)

    cos_dl = (
        math.cos(inc1) * math.cos(inc2)
        + math.sin(inc1) * math.sin(inc2) * math.cos(az2 - az1)
    )
    cos_dl = max(-1.0, min(1.0, cos_dl))
    dogleg = math.acos(cos_dl)

    if abs(dogleg) < 1e-12:
        rf = 1.0
    else:
        rf = (2.0 / dogleg) * math.tan(dogleg / 2.0)

    north = (
        dmd / 2.0
        * (
            math.sin(inc1) * math.cos(az1)
            + math.sin(inc2) * math.cos(az2)
        )
        * rf
    )
    east = (
        dmd / 2.0
        * (
            math.sin(inc1) * math.sin(az1)
            + math.sin(inc2) * math.sin(az2)
        )
        * rf
    )
    tvd = (
        dmd / 2.0
        * (
            math.cos(inc1)
            + math.cos(inc2)
        )
        * rf
    )

    return {"north": north, "east": east, "tvd": tvd}


def build_survey_profile_points(
    survey_rows: List[Dict[str, Any]],
    canvas_width: int,
    canvas_height: int,
) -> List[tuple]:
    if len(survey_rows) < 2:
        return []

    cleaned = []
    for row in survey_rows:
        cleaned.append(
            {
                "md": safe_float(row.get("measured_depth")),
                "inc": safe_float(row.get("inclination")),
                "azm": safe_float(row.get("azimuth")),
            }
        )

    cleaned.sort(key=lambda r: r["md"])

    coords = [{"x": 0.0, "tvd": 0.0}]
    north = 0.0
    east = 0.0
    tvd = 0.0

    for i in range(1, len(cleaned)):
        prev = cleaned[i - 1]
        curr = cleaned[i]

        step = minimum_curvature_step(
            prev["md"], prev["inc"], prev["azm"],
            curr["md"], curr["inc"], curr["azm"],
        )

        north += step["north"]
        east += step["east"]
        tvd += step["tvd"]

        horizontal = math.sqrt(north ** 2 + east ** 2)

        coords.append({"x": horizontal, "tvd": tvd})

    max_x = max(point["x"] for point in coords) or 1.0
    max_tvd = max(point["tvd"] for point in coords) or 1.0

    left_margin = 60
    right_margin = 30
    top_margin = 30
    bottom_margin = 30

    usable_width = max(100, canvas_width - left_margin - right_margin)
    usable_height = max(100, canvas_height - top_margin - bottom_margin)

    points = []
    for point in coords:
        draw_x = left_margin + (point["x"] / max_x) * usable_width
        draw_y = top_margin + (point["tvd"] / max_tvd) * usable_height
        points.append((draw_x, draw_y))

    return points