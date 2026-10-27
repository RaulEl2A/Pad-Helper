import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk

from logic.calc_time import calculate_time_summary


class TimeTab:
    def __init__(self, parent) -> None:
        self.frame = ttk.Frame(parent)
        self.state = None
        self._build()

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
        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)

        title = ttk.Label(
            self.scrollable_frame,
            text="Pad Status / Time Sticker",
            font=("Segoe UI", 14, "bold"),
        )
        title.pack(anchor="w", pady=(0, 10))

        main = ttk.Frame(self.scrollable_frame)
        main.pack(fill="both", expand=True)

        left = ttk.Frame(main)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))

        right = ttk.Frame(main)
        right.pack(side="right", fill="both", expand=True, padx=(10, 0))

        self._build_well_status_section(left)
        self._build_time_inputs_section(left)
        self._build_results_section(right)

    def _build_well_status_section(self, parent) -> None:
        section = ttk.LabelFrame(parent, text="Well Status", padding=10)
        section.pack(fill="both", expand=True, pady=(0, 10))

        columns = ("well", "completed", "total", "left")
        self.tree_wells = ttk.Treeview(
            section,
            columns=columns,
            show="headings",
            height=8,
        )
        self.tree_wells.heading("well", text="Well")
        self.tree_wells.heading("completed", text="Completed")
        self.tree_wells.heading("total", text="Total")
        self.tree_wells.heading("left", text="Left")
        self.tree_wells.column("well", width=260)
        self.tree_wells.column("completed", width=90, anchor="center")
        self.tree_wells.column("total", width=80, anchor="center")
        self.tree_wells.column("left", width=80, anchor="center")
        self.tree_wells.pack(fill="both", expand=True)

    def _build_time_inputs_section(self, parent) -> None:
        section = ttk.LabelFrame(parent, text="Time Estimate Inputs", padding=10)
        section.pack(fill="x", pady=(0, 10))

        ttk.Label(section, text="Current Well").grid(
            row=0, column=0, padx=5, pady=5, sticky="w"
        )
        self.cmb_well = ttk.Combobox(section, state="readonly", width=30)
        self.cmb_well.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(section, text="Operation Mode").grid(
            row=1, column=0, padx=5, pady=5, sticky="w"
        )
        self.cmb_operation_mode = ttk.Combobox(
            section,
            state="readonly",
            width=30,
            values=["Zipper / Multi-well", "Single Well"],
        )
        self.cmb_operation_mode.grid(
            row=1, column=1, padx=5, pady=5, sticky="w"
        )
        self.cmb_operation_mode.set("Zipper / Multi-well")

        ttk.Label(section, text="Average Mode").grid(
            row=2, column=0, padx=5, pady=5, sticky="w"
        )
        self.cmb_average_mode = ttk.Combobox(
            section,
            state="readonly",
            width=30,
            values=["Last X Stages", "From Stage Number"],
        )
        self.cmb_average_mode.grid(
            row=2, column=1, padx=5, pady=5, sticky="w"
        )
        self.cmb_average_mode.set("Last X Stages")

        ttk.Label(section, text="Average Stage Count").grid(
            row=3, column=0, padx=5, pady=5, sticky="w"
        )
        self.entry_average_count = ttk.Entry(section, width=12)
        self.entry_average_count.grid(
            row=3, column=1, padx=5, pady=5, sticky="w"
        )
        self.entry_average_count.insert(0, "5")

        ttk.Label(section, text="Start Average From Stage").grid(
            row=4, column=0, padx=5, pady=5, sticky="w"
        )
        self.entry_start_stage = ttk.Entry(section, width=12)
        self.entry_start_stage.grid(
            row=4, column=1, padx=5, pady=5, sticky="w"
        )

        ttk.Label(section, text="NPT Allowance / Stage (min)").grid(
            row=5, column=0, padx=5, pady=5, sticky="w"
        )
        self.entry_npt_allowance = ttk.Entry(section, width=12)
        self.entry_npt_allowance.grid(
            row=5, column=1, padx=5, pady=5, sticky="w"
        )
        self.entry_npt_allowance.insert(0, "0")

        ttk.Label(
            section,
            text="Wireline / Transition Allowance (min)",
        ).grid(row=6, column=0, padx=5, pady=5, sticky="w")
        self.entry_wireline_allowance = ttk.Entry(section, width=12)
        self.entry_wireline_allowance.grid(
            row=6, column=1, padx=5, pady=5, sticky="w"
        )
        self.entry_wireline_allowance.insert(0, "0")

        self.var_use_phase_estimate = tk.BooleanVar(value=True)
        self.chk_phase_estimate = ttk.Checkbutton(
            section,
            text="Use Phase Estimate: zipper phase + single-well phase",
            variable=self.var_use_phase_estimate,
        )
        self.chk_phase_estimate.grid(
            row=7,
            column=0,
            columnspan=2,
            padx=5,
            pady=(8, 5),
            sticky="w",
        )

        note = ttk.Label(
            section,
            text=(
                "The forecast uses the elapsed time between completed Frac "
                "events. Phase mode estimates the zipper and later "
                "single-well portions separately."
            ),
            wraplength=520,
        )
        note.grid(
            row=8,
            column=0,
            columnspan=2,
            padx=5,
            pady=(2, 5),
            sticky="w",
        )

        self.btn_calculate = ttk.Button(
            section,
            text="Calculate Time",
            command=self.recalculate,
        )
        self.btn_calculate.grid(
            row=9,
            column=0,
            columnspan=2,
            padx=5,
            pady=(10, 5),
            sticky="w",
        )

    def _build_results_section(self, parent) -> None:
        section = ttk.LabelFrame(parent, text="Time Results", padding=10)
        section.pack(fill="both", expand=True)

        self.lbl_answer = ttk.Label(
            section,
            text="Load TMT data, choose settings, then press Calculate Time.",
            font=("Segoe UI", 13, "bold"),
            wraplength=560,
        )
        self.lbl_answer.pack(anchor="w", pady=(0, 15))

        self.lbl_estimate_method = ttk.Label(section, text="Estimate Method: N/A")
        self.lbl_total_stages = ttk.Label(section, text="Total Pad Stages: N/A")
        self.lbl_completed_stages = ttk.Label(section, text="Completed Stages: N/A")
        self.lbl_stages_left = ttk.Label(section, text="Stages Left: N/A")

        self.lbl_cycle_header = ttk.Label(
            section,
            text="Completion-Cycle Details",
            font=("Segoe UI", 10, "bold"),
        )
        self.lbl_zipper_cycle = ttk.Label(
            section, text="Zipper Completion Cycle: N/A"
        )
        self.lbl_zipper_sample = ttk.Label(
            section, text="Zipper Cycle Sample Size: N/A"
        )
        self.lbl_zipper_average = ttk.Label(
            section, text="Zipper Cycle Average / Median: N/A"
        )
        self.lbl_single_cycle = ttk.Label(
            section, text="Single-Well Completion Cycle: N/A"
        )
        self.lbl_single_sample = ttk.Label(
            section, text="Single-Well Cycle Sample Size: N/A"
        )
        self.lbl_single_average = ttk.Label(
            section, text="Single-Well Cycle Average / Median: N/A"
        )

        self.lbl_stage_detail_header = ttk.Label(
            section,
            text="Stage Event Averages",
            font=("Segoe UI", 10, "bold"),
        )
        self.lbl_pad_avg_pump = ttk.Label(section, text="Pad Avg Pump Time: N/A")
        self.lbl_pad_avg_np = ttk.Label(section, text="Pad Avg NP Time: N/A")
        self.lbl_pad_avg_npt = ttk.Label(section, text="Pad Avg NPT: N/A")
        self.lbl_pad_avg_total = ttk.Label(section, text="Pad Avg Total Event Time: N/A")
        self.lbl_pad_sample = ttk.Label(section, text="Event Average Sample Size: N/A")

        self.lbl_phase_header = ttk.Label(
            section,
            text="Phase Estimate Details",
            font=("Segoe UI", 10, "bold"),
        )
        self.lbl_active_wells = ttk.Label(section, text="Active Wells: N/A")
        self.lbl_zipper_reference = ttk.Label(
            section, text="Zipper Reference Stages: N/A"
        )
        self.lbl_zipper_pumped = ttk.Label(
            section, text="Zipper Pumped Stages: N/A"
        )
        self.lbl_single_well_name = ttk.Label(
            section, text="Single-Well Name: N/A"
        )
        self.lbl_single_well_stages = ttk.Label(
            section, text="Single-Well Stages: N/A"
        )
        self.lbl_phase_hours = ttk.Label(
            section, text="Phase-Cycle Estimate Hours Left: N/A"
        )
        self.lbl_standard_hours = ttk.Label(
            section, text="One-Cycle Estimate Hours Left: N/A"
        )

        self.lbl_hours_left = ttk.Label(section, text="Estimated Hours Left: N/A")
        self.lbl_days_left = ttk.Label(section, text="Estimated Days Left: N/A")
        self.lbl_finish_time = ttk.Label(section, text="Estimated Finish Time: N/A")

        labels = [
            self.lbl_estimate_method,
            self.lbl_total_stages,
            self.lbl_completed_stages,
            self.lbl_stages_left,
            self.lbl_cycle_header,
            self.lbl_zipper_cycle,
            self.lbl_zipper_sample,
            self.lbl_zipper_average,
            self.lbl_single_cycle,
            self.lbl_single_sample,
            self.lbl_single_average,
            self.lbl_stage_detail_header,
            self.lbl_pad_avg_pump,
            self.lbl_pad_avg_np,
            self.lbl_pad_avg_npt,
            self.lbl_pad_avg_total,
            self.lbl_pad_sample,
            self.lbl_phase_header,
            self.lbl_active_wells,
            self.lbl_zipper_reference,
            self.lbl_zipper_pumped,
            self.lbl_single_well_name,
            self.lbl_single_well_stages,
            self.lbl_phase_hours,
            self.lbl_standard_hours,
            self.lbl_hours_left,
            self.lbl_days_left,
            self.lbl_finish_time,
        ]

        for label in labels:
            label.pack(anchor="w", pady=3)

    def update_from_state(self, state) -> None:
        self.state = state
        self.refresh_from_state()

    def refresh_from_state(self) -> None:
        if not self.state:
            return

        list_tab = self.state.ttmt_data.get("list_tab", {})
        wells = list_tab.get("wells", [])
        self.cmb_well["values"] = wells

        if wells and not self.cmb_well.get():
            self.cmb_well.set(wells[0])

        self.refresh_well_status_table()

    def refresh_well_status_table(self) -> None:
        for item in self.tree_wells.get_children():
            self.tree_wells.delete(item)

        if not self.state:
            return

        list_tab = self.state.ttmt_data.get("list_tab", {})
        completed = self.state.ttmt_data.get("sandinfo_completed", {})
        wells = list_tab.get("wells", [])
        stages_per_well = list_tab.get("stages_per_well", {})
        completed_by_well = completed.get("completed_by_well", {})

        for well in wells:
            total_stages = self._safe_float(stages_per_well.get(well, 0))
            completed_stages = self._safe_float(
                completed_by_well.get(well, 0)
            )
            stages_left = max(0, total_stages - completed_stages)

            self.tree_wells.insert(
                "",
                "end",
                values=(
                    well,
                    self._format_number(completed_stages),
                    self._format_number(total_stages),
                    self._format_number(stages_left),
                ),
            )

    def recalculate(self) -> None:
        if not self.state:
            return

        current_well = self.cmb_well.get().strip()
        list_tab = self.state.ttmt_data.get("list_tab", {})
        completed = self.state.ttmt_data.get("sandinfo_completed", {})

        wells = list_tab.get("wells", [])
        stages_per_well = list_tab.get("stages_per_well", {})
        completed_by_well = completed.get("completed_by_well", {})
        total_stages = list_tab.get("total_stages", 0)
        completed_stages = completed.get("total_completed_stages", 0)
        time_rows = self.state.ttmt_data.get("timelog_data", {}).get(
            "rows", []
        )

        result = calculate_time_summary(
            time_rows=time_rows,
            current_well=current_well,
            total_stages=total_stages,
            completed_stages=completed_stages,
            average_mode=self._get_average_mode_value(),
            average_stage_count=self.entry_average_count.get(),
            start_stage_number=self.entry_start_stage.get(),
            operation_mode=self._get_operation_mode_value(),
            npt_allowance_per_stage=self.entry_npt_allowance.get(),
            wireline_allowance_per_stage=self.entry_wireline_allowance.get(),
            use_phase_estimate=self.var_use_phase_estimate.get(),
            wells=wells,
            stages_per_well=stages_per_well,
            completed_by_well=completed_by_well,
        )

        hours_left = result.get("hours_left_on_pad", 0)
        days_left = result.get("days_left_on_pad", 0)
        estimate_method = result.get("estimate_method", "completion_cycle")

        if hours_left > 0:
            finish_time = datetime.now() + timedelta(hours=hours_left)
            finish_text = finish_time.strftime("%m/%d/%Y %I:%M %p")

            if estimate_method == "phase_cycle":
                answer_text = (
                    f"Phase-cycle estimate time left: {hours_left} hours "
                    f"({days_left} days)."
                )
            else:
                answer_text = (
                    f"Completion-cycle estimate time left: {hours_left} hours "
                    f"({days_left} days)."
                )
        else:
            finish_text = "N/A"
            answer_text = "Not enough completed Frac events to estimate time left."

        method_display = estimate_method.replace("_", " ").title()
        self.lbl_answer.config(text=answer_text)
        self.lbl_estimate_method.config(
            text=f"Estimate Method: {method_display}"
        )
        self.lbl_total_stages.config(
            text=f"Total Pad Stages: {self._format_number(total_stages)}"
        )
        self.lbl_completed_stages.config(
            text=(
                "Completed Stages: "
                f"{self._format_number(completed_stages)}"
            )
        )
        self.lbl_stages_left.config(
            text=(
                "Stages Left: "
                f"{self._format_number(result.get('stages_left', 0))}"
            )
        )

        self.lbl_zipper_cycle.config(
            text=(
                "Zipper Completion Cycle: "
                f"{result.get('zipper_cycle_minutes', 0)} min/stage"
            )
        )
        self.lbl_zipper_sample.config(
            text=(
                "Zipper Cycle Sample Size: "
                f"{result.get('zipper_cycle_sample_count', 0)} cycles"
            )
        )
        self.lbl_zipper_average.config(
            text=(
                "Zipper Cycle Average / Median: "
                f"{result.get('zipper_cycle_average_minutes', 0)} / "
                f"{result.get('zipper_cycle_median_minutes', 0)} min"
            )
        )
        self.lbl_single_cycle.config(
            text=(
                "Single-Well Completion Cycle: "
                f"{result.get('single_well_cycle_minutes', 0)} min/stage"
            )
        )
        self.lbl_single_sample.config(
            text=(
                "Single-Well Cycle Sample Size: "
                f"{result.get('single_well_cycle_sample_count', 0)} cycles"
            )
        )
        self.lbl_single_average.config(
            text=(
                "Historical Same-Well Average / Median: "
                f"{result.get('single_well_cycle_average_minutes', 0)} / "
                f"{result.get('single_well_cycle_median_minutes', 0)} min"
            )
        )

        self.lbl_pad_avg_pump.config(
            text=f"Pad Avg Pump Time: {result.get('pad_avg_pump', 0)} min"
        )
        self.lbl_pad_avg_np.config(
            text=f"Pad Avg NP Time: {result.get('pad_avg_np', 0)} min"
        )
        self.lbl_pad_avg_npt.config(
            text=f"Pad Avg NPT: {result.get('pad_avg_npt', 0)} min"
        )
        self.lbl_pad_avg_total.config(
            text=(
                "Pad Avg Total Event Time: "
                f"{result.get('pad_avg_total', 0)} min"
            )
        )
        self.lbl_pad_sample.config(
            text=(
                "Event Average Sample Size: "
                f"{result.get('pad_average_sample_count', 0)} stages"
            )
        )

        self.lbl_active_wells.config(
            text=f"Active Wells: {result.get('active_well_count', 0)}"
        )
        self.lbl_zipper_reference.config(
            text=(
                "Zipper Reference Stages: "
                f"{self._format_number(result.get('zipper_reference_stages', 0))}"
            )
        )
        self.lbl_zipper_pumped.config(
            text=(
                "Zipper Pumped Stages: "
                f"{self._format_number(result.get('zipper_pumped_stages', 0))}"
            )
        )
        self.lbl_single_well_name.config(
            text=(
                "Single-Well Name: "
                f"{result.get('single_well_name', '') or 'N/A'}"
            )
        )
        self.lbl_single_well_stages.config(
            text=(
                "Single-Well Stages: "
                f"{self._format_number(result.get('single_well_stages', 0))}"
            )
        )
        self.lbl_phase_hours.config(
            text=(
                "Phase-Cycle Estimate Hours Left: "
                f"{result.get('phase_hours_left', 0)}"
            )
        )
        self.lbl_standard_hours.config(
            text=(
                "One-Cycle Estimate Hours Left: "
                f"{result.get('standard_hours_left', 0)}"
            )
        )
        self.lbl_hours_left.config(
            text=f"Estimated Hours Left: {hours_left}"
        )
        self.lbl_days_left.config(
            text=f"Estimated Days Left: {days_left}"
        )
        self.lbl_finish_time.config(
            text=f"Estimated Finish Time: {finish_text}"
        )

    def _get_average_mode_value(self) -> str:
        if self.cmb_average_mode.get().strip() == "From Stage Number":
            return "from_stage"
        return "last_n"

    def _get_operation_mode_value(self) -> str:
        if self.cmb_operation_mode.get().strip() == "Single Well":
            return "single_well"
        return "zipper"

    def _safe_float(self, value) -> float:
        try:
            if value is None:
                return 0.0
            text = str(value).replace(",", "").strip()
            if text == "":
                return 0.0
            return float(text)
        except (TypeError, ValueError):
            return 0.0

    def _format_number(self, value) -> str:
        number = self._safe_float(value)
        if number == int(number):
            return f"{int(number):,}"
        return f"{number:,.1f}"

    def _bind_mousewheel(self, event) -> None:
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel_linux)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel_linux)

    def _unbind_mousewheel(self, event) -> None:
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event) -> None:
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_mousewheel_linux(self, event) -> None:
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")
