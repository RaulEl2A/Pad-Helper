import json
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox

from logic.calc_final_sand import (
    calculate_average_design_from_total,
    calculate_final_sand,
)


class FinalSandTab:
    def __init__(self, parent) -> None:
        self.frame = ttk.Frame(parent)
        self.state = None
        self.wells = []

        self.save_dir = Path.home() / ".frac_calculator"
        self.save_file = self.save_dir / "final_sand_last_inputs.json"

        self._build()
        self.load_last_inputs(show_message=False)

    def _build(self) -> None:
        self.canvas = tk.Canvas(self.frame, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(
            self.frame,
            orient="vertical",
            command=self.canvas.yview,
        )

        self.scrollable_frame = ttk.Frame(self.canvas, padding=10)

        self.canvas_window = self.canvas.create_window(
            (0, 0),
            window=self.scrollable_frame,
            anchor="nw",
        )

        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.scrollable_frame.bind(
            "<Configure>",
            lambda event: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            ),
        )

        self.canvas.bind(
            "<Configure>",
            lambda event: self.canvas.itemconfig(
                self.canvas_window,
                width=event.width,
            ),
        )

        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        title = ttk.Label(
            self.scrollable_frame,
            text="Final Sand Calculator",
            font=("Segoe UI", 14, "bold"),
        )
        title.pack(anchor="w", pady=(0, 10))

        main = ttk.Frame(self.scrollable_frame)
        main.pack(fill="both", expand=True)

        self.left_frame = ttk.Frame(main)
        self.left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self.right_frame = ttk.Frame(main)
        self.right_frame.pack(side="right", fill="both", expand=True, padx=(10, 0))

        self.wells_section = self._create_collapsible_section(
            self.left_frame,
            "Wells",
            expanded=True,
        )

        self.pad_section = self._create_collapsible_section(
            self.left_frame,
            "Pad Inputs",
            expanded=True,
        )

        self.pipeline_section = self._create_collapsible_section(
            self.left_frame,
            "Pipeline Counts",
            expanded=False,
        )

        self.results_section = self._create_collapsible_section(
            self.right_frame,
            "Results",
            expanded=True,
        )

        self._build_well_section()
        self._build_pad_inputs()
        self._build_pipeline_section()
        self._build_results_section()

    def _create_collapsible_section(self, parent, title: str, expanded: bool = True):
        container = ttk.Frame(parent)
        container.pack(fill="x", pady=(0, 10))

        header = ttk.Frame(container)
        header.pack(fill="x")

        content = ttk.LabelFrame(container, padding=10)

        is_open = tk.BooleanVar(value=expanded)

        def toggle():
            if is_open.get():
                content.pack_forget()
                button.config(text="▶")
                is_open.set(False)
            else:
                content.pack(fill="x", pady=(3, 0))
                button.config(text="▼")
                is_open.set(True)

        button = ttk.Button(
            header,
            text="▼" if expanded else "▶",
            width=3,
            command=toggle,
        )
        button.pack(side="left", padx=(0, 5))

        label = ttk.Label(
            header,
            text=title,
            font=("Segoe UI", 11, "bold"),
        )
        label.pack(side="left")

        if expanded:
            content.pack(fill="x", pady=(3, 0))

        return content

    def _build_well_section(self) -> None:
        section = self.wells_section

        ttk.Label(section, text="Well Name").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Label(section, text="Stages Left").grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(section, text="Design Prop / Stage").grid(row=0, column=2, padx=5, pady=5, sticky="w")

        self.entry_well_name = ttk.Entry(section, width=22)
        self.entry_stages_left = ttk.Entry(section, width=12)
        self.entry_design_prop = ttk.Entry(section, width=18)

        self.entry_well_name.grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.entry_stages_left.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        self.entry_design_prop.grid(row=1, column=2, padx=5, pady=5, sticky="w")

        self.btn_avg_from_total = ttk.Button(
            section,
            text="Avg From Total",
            command=self.open_avg_from_total_popup,
        )
        self.btn_avg_from_total.grid(row=1, column=3, padx=5, pady=5, sticky="w")

        self.btn_add_well = ttk.Button(
            section,
            text="Add Well",
            command=self.add_well,
        )
        self.btn_add_well.grid(row=1, column=4, padx=5, pady=5, sticky="w")

        columns = ("well", "stages_left", "design_prop", "total_prop")

        self.tree_wells = ttk.Treeview(
            section,
            columns=columns,
            show="headings",
            height=8,
        )

        self.tree_wells.heading("well", text="Well")
        self.tree_wells.heading("stages_left", text="Stages Left")
        self.tree_wells.heading("design_prop", text="Design / Stage")
        self.tree_wells.heading("total_prop", text="Total Needed")

        self.tree_wells.column("well", width=180)
        self.tree_wells.column("stages_left", width=100, anchor="center")
        self.tree_wells.column("design_prop", width=130, anchor="center")
        self.tree_wells.column("total_prop", width=130, anchor="center")

        self.tree_wells.grid(
            row=2,
            column=0,
            columnspan=5,
            padx=5,
            pady=(10, 5),
            sticky="nsew",
        )

        button_frame = ttk.Frame(section)
        button_frame.grid(row=3, column=0, columnspan=5, sticky="w", padx=5, pady=5)

        self.btn_edit_well = ttk.Button(
            button_frame,
            text="Edit Selected",
            command=self.edit_selected_well,
        )
        self.btn_edit_well.pack(side="left", padx=(0, 5))

        self.btn_remove_well = ttk.Button(
            button_frame,
            text="Remove Selected",
            command=self.remove_selected_well,
        )
        self.btn_remove_well.pack(side="left")

    def _build_pad_inputs(self) -> None:
        section = self.pad_section

        ttk.Label(section, text="Sand on Location").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Label(section, text="Average Box Weight").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ttk.Label(section, text="Spread Extra Over Last ___ Stages").grid(row=2, column=0, padx=5, pady=5, sticky="w")

        self.entry_sand_on_location = ttk.Entry(section, width=18)
        self.entry_average_box_weight = ttk.Entry(section, width=18)
        self.entry_spread_stage_count = ttk.Entry(section, width=18)

        self.entry_sand_on_location.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.entry_average_box_weight.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        self.entry_spread_stage_count.grid(row=2, column=1, padx=5, pady=5, sticky="w")

        self.entry_spread_stage_count.insert(0, "4")

        note = ttk.Label(
            section,
            text="Note: 1 load = 2 boxes. Average load weight is calculated automatically.",
        )
        note.grid(row=3, column=0, columnspan=2, padx=5, pady=(8, 0), sticky="w")

    def _build_pipeline_section(self) -> None:
        section = self.pipeline_section

        ttk.Label(section, text="Ordered").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Label(section, text="At Terminal").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ttk.Label(section, text="In Transit").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        ttk.Label(section, text="At Destination").grid(row=3, column=0, padx=5, pady=5, sticky="w")

        self.entry_ordered = ttk.Entry(section, width=12)
        self.entry_at_terminal = ttk.Entry(section, width=12)
        self.entry_in_transit = ttk.Entry(section, width=12)
        self.entry_at_destination = ttk.Entry(section, width=12)

        self.entry_ordered.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.entry_at_terminal.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        self.entry_in_transit.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        self.entry_at_destination.grid(row=3, column=1, padx=5, pady=5, sticky="w")

        note = ttk.Label(
            section,
            text="Delivered is not entered here. It will be handled later during reconciliation.",
            wraplength=500,
        )
        note.grid(row=4, column=0, columnspan=2, padx=5, pady=(8, 0), sticky="w")

    def _build_results_section(self) -> None:
        section = self.results_section

        self.lbl_answer = ttk.Label(
            section,
            text="Add wells, enter pad inputs, then press Calculate.",
            font=("Segoe UI", 13, "bold"),
            wraplength=500,
        )
        self.lbl_answer.pack(anchor="w", pady=(0, 15))

        self.warning_frame = ttk.LabelFrame(section, text="Warnings", padding=10)
        self.warning_frame.pack(fill="x", pady=(0, 15))

        self.lbl_warnings = ttk.Label(
            self.warning_frame,
            text="No warnings.",
            foreground="green",
            wraplength=500,
            justify="left",
        )
        self.lbl_warnings.pack(anchor="w")

        self.lbl_total_design = ttk.Label(section, text="Total Remaining Design: N/A")
        self.lbl_sand_location = ttk.Label(section, text="Sand on Location: N/A")
        self.lbl_prop_needed = ttk.Label(section, text="Prop Needed Before Rounding: N/A")
        self.lbl_box_weight = ttk.Label(section, text="Average Box Weight: N/A")
        self.lbl_load_weight = ttk.Label(section, text="Average Load Weight: N/A")
        self.lbl_total_loads = ttk.Label(section, text="Total Loads Needed: N/A")
        self.lbl_total_boxes = ttk.Label(section, text="Total Boxes Needed: N/A")
        self.lbl_pipeline_credit = ttk.Label(section, text="Pipeline Credit: N/A")
        self.lbl_still_needed = ttk.Label(section, text="Still Need To Order: N/A")
        self.lbl_excess_pipeline = ttk.Label(section, text="Excess Pipeline: N/A")
        self.lbl_extra_sand = ttk.Label(section, text="Extra Sand From Rounding: N/A")
        self.lbl_extra_stage = ttk.Label(section, text="Extra Per Final Stage: N/A")
        self.lbl_surplus = ttk.Label(section, text="Surplus: N/A")

        labels = [
            self.lbl_total_design,
            self.lbl_sand_location,
            self.lbl_prop_needed,
            self.lbl_box_weight,
            self.lbl_load_weight,
            self.lbl_total_loads,
            self.lbl_total_boxes,
            self.lbl_pipeline_credit,
            self.lbl_still_needed,
            self.lbl_excess_pipeline,
            self.lbl_extra_sand,
            self.lbl_extra_stage,
            self.lbl_surplus,
        ]

        for label in labels:
            label.pack(anchor="w", pady=3)

        button_frame = ttk.Frame(section)
        button_frame.pack(anchor="w", pady=(15, 0))

        self.btn_calculate_results = ttk.Button(
            button_frame,
            text="Calculate",
            command=self.recalculate,
        )
        self.btn_calculate_results.pack(side="left", padx=(0, 8))

        self.btn_save_inputs = ttk.Button(
            button_frame,
            text="Save Inputs",
            command=self.save_inputs,
        )
        self.btn_save_inputs.pack(side="left", padx=(0, 8))

        self.btn_load_inputs = ttk.Button(
            button_frame,
            text="Load Last Inputs",
            command=lambda: self.load_last_inputs(show_message=True),
        )
        self.btn_load_inputs.pack(side="left")

    def update_from_state(self, state) -> None:
        self.state = state
        self.autofill_from_tmt()

    def autofill_from_tmt(self) -> None:
        if not self.state:
            return

        ttmt_data = self.state.ttmt_data

        if not ttmt_data:
            return

        sandbol = ttmt_data.get("sandbol_tab", {})
        sand_on_location = sandbol.get("sand_on_location", "")

        if sand_on_location not in ("", None):
            self._set_entry(self.entry_sand_on_location, sand_on_location)

        stage_data = ttmt_data.get("sandinfo_stage_data", {})
        completed = ttmt_data.get("sandinfo_completed", {})
        list_tab = ttmt_data.get("list_tab", {})

        stage_rows = stage_data.get("stage_rows", [])
        completed_by_well = completed.get("completed_by_well", {})
        stages_per_well = list_tab.get("stages_per_well", {})

        if not stage_rows:
            return

        grouped = {}

        for row in stage_rows:
            well_name = str(row.get("well_name", "")).strip()

            if not well_name:
                continue

            design = self._safe_float(row.get("design_mass"))

            if well_name not in grouped:
                grouped[well_name] = {
                    "design_values": [],
                }

            if design > 0:
                grouped[well_name]["design_values"].append(design)

        self.wells = []

        for well_name, info in grouped.items():
            total_stages = self._safe_float(stages_per_well.get(well_name, 0))
            completed_stages = self._safe_float(completed_by_well.get(well_name, 0))
            stages_left = max(0, total_stages - completed_stages)

            designs = info["design_values"]
            average_design = 0

            if designs:
                average_design = sum(designs) / len(designs)

            self.wells.append(
                {
                    "well_name": well_name,
                    "stages_left": stages_left,
                    "design_prop_per_stage": average_design,
                }
            )

        self.refresh_well_table()

    def add_well(self) -> None:
        well_name = self.entry_well_name.get().strip()
        stages_left = self.entry_stages_left.get().strip()
        design_prop = self.entry_design_prop.get().strip()

        if not well_name:
            messagebox.showwarning("Missing Well Name", "Please enter a well name.")
            return

        self.wells.append(
            {
                "well_name": well_name,
                "stages_left": stages_left,
                "design_prop_per_stage": design_prop,
            }
        )

        self.entry_well_name.delete(0, tk.END)
        self.entry_stages_left.delete(0, tk.END)
        self.entry_design_prop.delete(0, tk.END)

        self.refresh_well_table()

    def edit_selected_well(self) -> None:
        selected = self.tree_wells.selection()

        if not selected:
            messagebox.showwarning("No Selection", "Please select a well to edit.")
            return

        item_id = selected[0]
        index = int(self.tree_wells.item(item_id, "tags")[0])
        well = self.wells[index]

        self.open_edit_well_popup(index, well)

    def remove_selected_well(self) -> None:
        selected = self.tree_wells.selection()

        if not selected:
            messagebox.showwarning("No Selection", "Please select a well to remove.")
            return

        item_id = selected[0]
        index = int(self.tree_wells.item(item_id, "tags")[0])

        del self.wells[index]

        self.refresh_well_table()

    def open_edit_well_popup(self, index, well) -> None:
        popup = tk.Toplevel(self.frame)
        popup.title("Edit Well")
        popup.geometry("420x220")
        popup.transient(self.frame)
        popup.grab_set()

        ttk.Label(popup, text="Well Name").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        ttk.Label(popup, text="Stages Left").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        ttk.Label(popup, text="Design Prop / Stage").grid(row=2, column=0, padx=10, pady=10, sticky="w")

        entry_name = ttk.Entry(popup, width=25)
        entry_stages = ttk.Entry(popup, width=25)
        entry_design = ttk.Entry(popup, width=25)

        entry_name.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        entry_stages.grid(row=1, column=1, padx=10, pady=10, sticky="w")
        entry_design.grid(row=2, column=1, padx=10, pady=10, sticky="w")

        entry_name.insert(0, well.get("well_name", ""))
        entry_stages.insert(0, well.get("stages_left", ""))
        entry_design.insert(0, well.get("design_prop_per_stage", ""))

        def save_changes():
            self.wells[index] = {
                "well_name": entry_name.get().strip(),
                "stages_left": entry_stages.get().strip(),
                "design_prop_per_stage": entry_design.get().strip(),
            }

            self.refresh_well_table()
            popup.destroy()

        def avg_from_total():
            self.open_avg_from_total_popup(
                target_entry=entry_design,
                stages_entry=entry_stages,
            )

        ttk.Button(
            popup,
            text="Avg From Total",
            command=avg_from_total,
        ).grid(row=3, column=0, padx=10, pady=15, sticky="w")

        ttk.Button(
            popup,
            text="Save",
            command=save_changes,
        ).grid(row=3, column=1, padx=10, pady=15, sticky="e")

    def open_avg_from_total_popup(self, target_entry=None, stages_entry=None) -> None:
        popup = tk.Toplevel(self.frame)
        popup.title("Average From Total")
        popup.geometry("420x220")
        popup.transient(self.frame)
        popup.grab_set()

        ttk.Label(popup, text="Total Remaining Sand").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        ttk.Label(popup, text="Stages Left").grid(row=1, column=0, padx=10, pady=10, sticky="w")

        entry_total = ttk.Entry(popup, width=25)
        entry_stages = ttk.Entry(popup, width=25)

        entry_total.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        entry_stages.grid(row=1, column=1, padx=10, pady=10, sticky="w")

        if stages_entry is not None:
            entry_stages.insert(0, stages_entry.get())
        else:
            entry_stages.insert(0, self.entry_stages_left.get())

        lbl_result = ttk.Label(popup, text="Average Design: N/A")
        lbl_result.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="w")

        def calculate_and_apply():
            result = calculate_average_design_from_total(
                total_sand=entry_total.get(),
                stages_left=entry_stages.get(),
            )

            if result["error"]:
                messagebox.showwarning("Invalid Input", result["error"])
                return

            average = result["average_design"]
            lbl_result.config(text=f"Average Design: {average}")

            if target_entry is not None:
                target_entry.delete(0, tk.END)
                target_entry.insert(0, str(average))
            else:
                self.entry_design_prop.delete(0, tk.END)
                self.entry_design_prop.insert(0, str(average))

        ttk.Button(
            popup,
            text="Calculate",
            command=calculate_and_apply,
        ).grid(row=3, column=0, padx=10, pady=15, sticky="w")

        ttk.Button(
            popup,
            text="Close",
            command=popup.destroy,
        ).grid(row=3, column=1, padx=10, pady=15, sticky="e")

    def refresh_well_table(self) -> None:
        for item in self.tree_wells.get_children():
            self.tree_wells.delete(item)

        for index, well in enumerate(self.wells):
            stages_left = self._safe_float(well.get("stages_left"))
            design_prop = self._safe_float(well.get("design_prop_per_stage"))
            total_prop = stages_left * design_prop

            self.tree_wells.insert(
                "",
                "end",
                values=(
                    well.get("well_name", ""),
                    self._format_number(stages_left),
                    self._format_number(design_prop),
                    self._format_number(total_prop),
                ),
                tags=(str(index),),
            )

    def recalculate(self) -> None:
        pipeline_counts = {
            "ordered": self.entry_ordered.get(),
            "at_terminal": self.entry_at_terminal.get(),
            "in_transit": self.entry_in_transit.get(),
            "at_destination": self.entry_at_destination.get(),
        }

        result = calculate_final_sand(
            wells=self.wells,
            sand_on_location=self.entry_sand_on_location.get(),
            average_box_weight=self.entry_average_box_weight.get(),
            spread_stage_count=self.entry_spread_stage_count.get(),
            pipeline_counts=pipeline_counts,
        )

        summary = result["summary"]
        warnings = result.get("warnings", [])

        loads_still_needed = summary.get("loads_still_needed", 0)
        boxes_still_needed = summary.get("boxes_still_needed", 0)
        excess_pipeline_loads = summary.get("excess_pipeline_loads", 0)
        excess_pipeline_boxes = summary.get("excess_pipeline_boxes", 0)
        surplus = summary.get("surplus", 0)
        total_loads_needed = summary.get("total_loads_needed", 0)

        required_issue_found = self._has_required_input_warning(warnings)

        if required_issue_found:
            answer_text = "Complete required inputs before using this result."
        elif surplus > 0:
            answer_text = "Sand on location is greater than remaining design. No additional loads needed."
        elif loads_still_needed > 0:
            answer_text = (
                f"You still need {loads_still_needed} loads / "
                f"{boxes_still_needed} boxes delivered."
            )
        elif excess_pipeline_loads > 0:
            answer_text = (
                f"Pipeline covers the current need. Excess pipeline: "
                f"{excess_pipeline_loads} loads / {excess_pipeline_boxes} boxes."
            )
        elif total_loads_needed > 0:
            answer_text = "Current pipeline exactly covers the calculated need. No additional loads needed."
        else:
            answer_text = "No additional loads needed based on the current inputs."

        self.lbl_answer.config(text=answer_text)

        self.lbl_total_design.config(
            text=f"Total Remaining Design: {self._format_number(summary.get('total_remaining_design', 0))} lb"
        )

        self.lbl_sand_location.config(
            text=f"Sand on Location: {self._format_number(summary.get('sand_on_location', 0))} lb"
        )

        self.lbl_prop_needed.config(
            text=f"Prop Needed Before Rounding: {self._format_number(summary.get('prop_needed_before_rounding', 0))} lb"
        )

        self.lbl_box_weight.config(
            text=f"Average Box Weight: {self._format_number(summary.get('average_box_weight', 0))} lb"
        )

        self.lbl_load_weight.config(
            text=f"Average Load Weight: {self._format_number(summary.get('average_load_weight', 0))} lb"
        )

        self.lbl_total_loads.config(
            text=f"Total Loads Needed: {summary.get('total_loads_needed', 0)}"
        )

        self.lbl_total_boxes.config(
            text=f"Total Boxes Needed: {summary.get('total_boxes_needed', 0)}"
        )

        self.lbl_pipeline_credit.config(
            text=(
                f"Pipeline Credit: {summary.get('pipeline_load_credit', 0)} loads / "
                f"{summary.get('pipeline_box_credit', 0)} boxes"
            )
        )

        self.lbl_still_needed.config(
            text=(
                f"Still Need To Order: {summary.get('loads_still_needed', 0)} loads / "
                f"{summary.get('boxes_still_needed', 0)} boxes"
            )
        )

        self.lbl_excess_pipeline.config(
            text=(
                f"Excess Pipeline: {summary.get('excess_pipeline_loads', 0)} loads / "
                f"{summary.get('excess_pipeline_boxes', 0)} boxes"
            )
        )

        self.lbl_extra_sand.config(
            text=f"Extra Sand From Rounding: {self._format_number(summary.get('extra_sand', 0))} lb"
        )

        self.lbl_extra_stage.config(
            text=(
                f"Extra Per Final Stage: {self._format_number(summary.get('extra_per_stage', 0))} lb "
                f"over {summary.get('spread_stage_count', 0)} stages"
            )
        )

        self.lbl_surplus.config(
            text=f"Surplus: {self._format_number(summary.get('surplus', 0))} lb"
        )

        if warnings:
            warning_text = "Review before using result:\n\n"
            warning_text += "\n".join(f"- {warning}" for warning in warnings)
            self.lbl_warnings.config(text=warning_text, foreground="red")
        else:
            self.lbl_warnings.config(text="No warnings.", foreground="green")

    def _has_required_input_warning(self, warnings) -> bool:
        required_warning_phrases = [
            "missing",
            "invalid",
            "must be greater than 0",
            "cannot be negative",
            "No wells have been added",
        ]

        for warning in warnings:
            warning_text = str(warning)

            for phrase in required_warning_phrases:
                if phrase.lower() in warning_text.lower():
                    return True

        return False

    def save_inputs(self) -> None:
        try:
            self.save_dir.mkdir(parents=True, exist_ok=True)

            data = {
                "wells": self.wells,
                "pad_inputs": {
                    "sand_on_location": self.entry_sand_on_location.get(),
                    "average_box_weight": self.entry_average_box_weight.get(),
                    "spread_stage_count": self.entry_spread_stage_count.get(),
                },
                "pipeline_counts": {
                    "ordered": self.entry_ordered.get(),
                    "at_terminal": self.entry_at_terminal.get(),
                    "in_transit": self.entry_in_transit.get(),
                    "at_destination": self.entry_at_destination.get(),
                },
            }

            with open(self.save_file, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=4)

            messagebox.showinfo("Saved", "Final Sand inputs saved successfully.")

        except Exception as exc:
            messagebox.showerror("Save Error", f"Could not save Final Sand inputs:\n{exc}")

    def load_last_inputs(self, show_message: bool = True) -> None:
        try:
            if not self.save_file.exists():
                if show_message:
                    messagebox.showinfo("No Saved Inputs", "No saved Final Sand inputs found.")
                return

            with open(self.save_file, "r", encoding="utf-8") as file:
                data = json.load(file)

            self.wells = data.get("wells", [])
            self.refresh_well_table()

            pad_inputs = data.get("pad_inputs", {})
            self._set_entry(self.entry_sand_on_location, pad_inputs.get("sand_on_location", ""))
            self._set_entry(self.entry_average_box_weight, pad_inputs.get("average_box_weight", ""))
            self._set_entry(self.entry_spread_stage_count, pad_inputs.get("spread_stage_count", "4"))

            pipeline_counts = data.get("pipeline_counts", {})
            self._set_entry(self.entry_ordered, pipeline_counts.get("ordered", ""))
            self._set_entry(self.entry_at_terminal, pipeline_counts.get("at_terminal", ""))
            self._set_entry(self.entry_in_transit, pipeline_counts.get("in_transit", ""))
            self._set_entry(self.entry_at_destination, pipeline_counts.get("at_destination", ""))

            if show_message:
                messagebox.showinfo("Loaded", "Last Final Sand inputs loaded successfully.")

        except Exception as exc:
            if show_message:
                messagebox.showerror("Load Error", f"Could not load Final Sand inputs:\n{exc}")

    def _set_entry(self, entry, value) -> None:
        entry.delete(0, tk.END)
        entry.insert(0, str(value))

    def _safe_float(self, value) -> float:
        try:
            if value is None:
                return 0.0

            text = str(value).replace(",", "").strip()

            if text == "":
                return 0.0

            return float(text)

        except Exception:
            return 0.0

    def _format_number(self, value) -> str:
        number = self._safe_float(value)

        if number == int(number):
            return f"{int(number):,}"

        return f"{number:,.2f}"

    def _on_mousewheel(self, event) -> None:
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")