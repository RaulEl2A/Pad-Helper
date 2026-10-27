import tkinter as tk
from tkinter import ttk

from logic.calc_wellbore import (
    calculate_capacity_to_depth,
    calculate_sand_in_wellbore,
    build_survey_profile_points,
)


class WellboreTab:
    def __init__(self, parent) -> None:
        self.frame = ttk.Frame(parent, padding=10)
        self.state = None
        self._build()

    def _build(self) -> None:
        title = ttk.Label(self.frame, text="Wellbore", font=("Segoe UI", 14, "bold"))
        title.pack(anchor="w", pady=(0, 10))

        top = ttk.Frame(self.frame)
        top.pack(anchor="nw", fill="x", pady=(0, 10))

        ttk.Label(top, text="Selected Well:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.cmb_well = ttk.Combobox(top, state="readonly", width=30)
        self.cmb_well.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.cmb_well.bind("<<ComboboxSelected>>", self._on_well_changed)

        ttk.Label(top, text="Selected Depth:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.entry_depth = ttk.Entry(top, width=20)
        self.entry_depth.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(top, text="Sand Concentration (ppa):").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.entry_ppa = ttk.Entry(top, width=20)
        self.entry_ppa.grid(row=2, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(top, text="Barrels Pumped After Sand Started:").grid(
            row=3, column=0, padx=5, pady=5, sticky="w"
        )
        self.entry_bbl = ttk.Entry(top, width=20)
        self.entry_bbl.grid(row=3, column=1, padx=5, pady=5, sticky="w")

        self.btn_calculate = ttk.Button(top, text="Calculate", command=self.recalculate)
        self.btn_calculate.grid(row=4, column=0, columnspan=2, padx=5, pady=10, sticky="w")

        results = ttk.Frame(self.frame)
        results.pack(anchor="nw", fill="x", pady=(0, 10))

        self.lbl_total_bbl = ttk.Label(results, text="Total BBL to Selected Depth: N/A")
        self.lbl_sections = ttk.Label(results, text="Pipe Sections Included: N/A", wraplength=1200)
        self.lbl_sand_in_wellbore = ttk.Label(results, text="Sand in Wellbore (lb): N/A")

        self.lbl_total_bbl.pack(anchor="w", pady=3)
        self.lbl_sections.pack(anchor="w", pady=3)
        self.lbl_sand_in_wellbore.pack(anchor="w", pady=3)

        schematic_frame = ttk.LabelFrame(self.frame, text="Survey-Aware Schematic")
        schematic_frame.pack(fill="both", expand=True, pady=(10, 0))

        self.canvas = tk.Canvas(schematic_frame, bg="white", height=400)
        self.canvas.pack(fill="both", expand=True, padx=10, pady=10)

    def update_from_state(self, state) -> None:
        self.state = state

        wells = list(state.ts_data.keys())
        self.cmb_well["values"] = wells

        if wells:
            if not self.cmb_well.get() or self.cmb_well.get() not in wells:
                self.cmb_well.set(wells[0])
        else:
            self.cmb_well.set("")

        self.recalculate()

    def _on_well_changed(self, event=None) -> None:
        self.recalculate()

    def recalculate(self) -> None:
        self.canvas.delete("all")

        if not self.state:
            return

        selected_well = self.cmb_well.get().strip()
        if not selected_well or selected_well not in self.state.ts_data:
            self.lbl_total_bbl.config(text="Total BBL to Selected Depth: N/A")
            self.lbl_sections.config(text="Pipe Sections Included: No matched TS for this well")
            self.lbl_sand_in_wellbore.config(text="Sand in Wellbore (lb): N/A")
            self.canvas.create_text(250, 30, text="No matched TS for selected well", fill="black")
            return

        well_data = self.state.ts_data[selected_well]
        pipe_sections = well_data.get("pipe_sections", [])
        survey_rows = well_data.get("survey_rows", [])

        capacity_result = calculate_capacity_to_depth(
            pipe_sections=pipe_sections,
            selected_depth=self.entry_depth.get(),
        )

        sand_lb = calculate_sand_in_wellbore(
            ppa=self.entry_ppa.get(),
            barrels_after_sand_started=self.entry_bbl.get(),
        )

        self.lbl_total_bbl.config(
            text=f"Total BBL to Selected Depth: {capacity_result['total_bbl']}"
        )

        sections_text = " | ".join(capacity_result["included_sections"]) if capacity_result["included_sections"] else "None"
        self.lbl_sections.config(text=f"Pipe Sections Included: {sections_text}")

        self.lbl_sand_in_wellbore.config(text=f"Sand in Wellbore (lb): {sand_lb}")

        self._draw_schematic(survey_rows)

    def _draw_schematic(self, survey_rows) -> None:
        self.canvas.update_idletasks()

        width = max(300, self.canvas.winfo_width())
        height = max(200, self.canvas.winfo_height())

        self.canvas.create_text(70, 20, text="Surface", fill="black", anchor="w")

        points = build_survey_profile_points(survey_rows, width, height)

        if len(points) < 2:
            self.canvas.create_text(
                220,
                40,
                text="Not enough survey data to draw schematic",
                fill="black"
            )
            return

        flat_points = []
        for x, y in points:
            flat_points.extend([x, y])

        self.canvas.create_line(*flat_points, fill="blue", width=2)

        last_x, last_y = points[-1]
        self.canvas.create_text(last_x + 10, last_y, text="TD", anchor="w", fill="black")