import tkinter as tk
from tkinter import messagebox, ttk

from logic.calc_chemical import (
    calculate_chemical_forecast,
    get_default_profile,
    normalize_chemical_name,
)


class ChemicalTab:
    def __init__(self, parent) -> None:
        self.frame = ttk.Frame(parent)
        self.state = None
        self.last_result = None

        self.manual_usage = {}
        self.chemical_profiles = {}
        self.container_assignments = {}
        self.receiving_containers = {}
        self.cut_confirmations = {}

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

        ttk.Label(
            self.scrollable_frame,
            text="Chemical Forecast",
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w", pady=(0, 10))

        self._build_usage_settings()
        self._build_summary()
        self._build_results_table()
        self._build_selected_chemical_editor()

    def _build_usage_settings(self) -> None:
        section = ttk.LabelFrame(
            self.scrollable_frame,
            text="Forecast Settings",
            padding=10,
        )
        section.pack(fill="x", pady=(0, 10))

        ttk.Label(section, text="Average Mode").grid(
            row=0, column=0, padx=5, pady=5, sticky="w"
        )
        self.cmb_average_mode = ttk.Combobox(
            section,
            state="readonly",
            width=21,
            values=["Last X Stages", "From Stage Number"],
        )
        self.cmb_average_mode.grid(
            row=0, column=1, padx=5, pady=5, sticky="w"
        )
        self.cmb_average_mode.set("Last X Stages")

        ttk.Label(section, text="Stages Per Well").grid(
            row=0, column=2, padx=(20, 5), pady=5, sticky="w"
        )
        self.entry_stage_count = ttk.Entry(section, width=9)
        self.entry_stage_count.grid(
            row=0, column=3, padx=5, pady=5, sticky="w"
        )
        self.entry_stage_count.insert(0, "5")

        ttk.Label(section, text="Start From Stage").grid(
            row=0, column=4, padx=(20, 5), pady=5, sticky="w"
        )
        self.entry_start_stage = ttk.Entry(section, width=9)
        self.entry_start_stage.grid(
            row=0, column=5, padx=5, pady=5, sticky="w"
        )

        ttk.Label(section, text="Latest Zero Stages").grid(
            row=1, column=0, padx=5, pady=5, sticky="w"
        )
        self.entry_zero_stages = ttk.Entry(section, width=9)
        self.entry_zero_stages.grid(
            row=1, column=1, padx=5, pady=5, sticky="w"
        )
        self.entry_zero_stages.insert(0, "2")

        ttk.Label(section, text="Estimated Pad Hours Left").grid(
            row=1, column=2, padx=(20, 5), pady=5, sticky="w"
        )
        self.entry_hours_left = ttk.Entry(section, width=12)
        self.entry_hours_left.grid(
            row=1, column=3, padx=5, pady=5, sticky="w"
        )

        ttk.Label(
            section,
            text="Enter the current Time-tab forecast here.",
        ).grid(row=1, column=4, columnspan=2, padx=5, pady=5, sticky="w")

        ttk.Button(
            section,
            text="Calculate Chemical Forecast",
            command=self.recalculate,
        ).grid(
            row=2,
            column=0,
            columnspan=2,
            padx=5,
            pady=(8, 5),
            sticky="w",
        )

        ttk.Label(
            section,
            text=(
                "Select a chemical in the results table to configure delivery "
                "quantity, ISO status, receiving ISO, or cut confirmation."
            ),
            wraplength=1000,
        ).grid(
            row=2,
            column=2,
            columnspan=4,
            padx=5,
            pady=(8, 5),
            sticky="w",
        )

    def _build_summary(self) -> None:
        section = ttk.LabelFrame(
            self.scrollable_frame,
            text="Forecast Summary",
            padding=10,
        )
        section.pack(fill="x", pady=(0, 10))

        self.lbl_summary = ttk.Label(
            section,
            text="Load TMT and TS files, then calculate the forecast.",
            font=("Segoe UI", 11, "bold"),
            wraplength=1250,
        )
        self.lbl_summary.pack(anchor="w")

        self.lbl_details = ttk.Label(section, text="", wraplength=1250)
        self.lbl_details.pack(anchor="w", pady=(5, 0))

    def _build_results_table(self) -> None:
        section = ttk.LabelFrame(
            self.scrollable_frame,
            text="Chemical Results",
            padding=5,
        )
        section.pack(fill="both", expand=True, pady=(0, 10))

        columns = (
            "chemical",
            "inventory",
            "usage",
            "usage_status",
            "samples",
            "hours_target",
            "order_in",
            "delivery",
            "load_fits",
            "shortage",
            "order_status",
        )

        table_frame = ttk.Frame(section)
        table_frame.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            height=13,
        )
        scroll_y = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.tree.yview,
        )
        scroll_x = ttk.Scrollbar(
            table_frame,
            orient="horizontal",
            command=self.tree.xview,
        )
        self.tree.configure(
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set,
        )

        headings = {
            "chemical": "Chemical",
            "inventory": "Inventory",
            "usage": "Usage / Stage",
            "usage_status": "Usage Status",
            "samples": "TS Samples",
            "hours_target": "Hours to Target",
            "order_in": "Order In",
            "delivery": "Target Delivery",
            "load_fits": "Load Fits",
            "shortage": "Short to Finish",
            "order_status": "Order Status",
        }
        widths = {
            "chemical": 180,
            "inventory": 110,
            "usage": 115,
            "usage_status": 205,
            "samples": 80,
            "hours_target": 105,
            "order_in": 90,
            "delivery": 150,
            "load_fits": 85,
            "shortage": 115,
            "order_status": 115,
        }

        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(
                column,
                width=widths[column],
                minwidth=70,
                anchor="w" if column in (
                    "chemical", "usage_status", "order_status"
                ) else "center",
            )

        self.tree.tag_configure("order_now", background="#f4cccc")
        self.tree.tag_configure("warning", background="#fff2cc")
        self.tree.tag_configure("good", background="#d9ead3")
        self.tree.tag_configure("inactive", background="#eeeeee")

        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

    def _build_selected_chemical_editor(self) -> None:
        section = ttk.LabelFrame(
            self.scrollable_frame,
            text="Selected Chemical Setup",
            padding=10,
        )
        section.pack(fill="x", pady=(0, 10))

        self.lbl_selected_chemical = ttk.Label(
            section,
            text="Select a chemical above.",
            font=("Segoe UI", 11, "bold"),
        )
        self.lbl_selected_chemical.grid(
            row=0, column=0, columnspan=8, padx=5, pady=(0, 8), sticky="w"
        )

        labels = [
            ("Delivery Qty", 0),
            ("Lead Time (hr)", 2),
            ("Working Capacity", 4),
            ("Arrival Target", 6),
        ]
        for text, column in labels:
            ttk.Label(section, text=text).grid(
                row=1, column=column, padx=5, pady=4, sticky="w"
            )

        self.entry_delivery_qty = ttk.Entry(section, width=12)
        self.entry_lead_time = ttk.Entry(section, width=12)
        self.entry_capacity = ttk.Entry(section, width=12)
        self.entry_arrival_target = ttk.Entry(section, width=12)
        self.entry_delivery_qty.grid(row=1, column=1, padx=5, pady=4)
        self.entry_lead_time.grid(row=1, column=3, padx=5, pady=4)
        self.entry_capacity.grid(row=1, column=5, padx=5, pady=4)
        self.entry_arrival_target.grid(row=1, column=7, padx=5, pady=4)

        ttk.Label(section, text="Unusable Heel").grid(
            row=2, column=0, padx=5, pady=4, sticky="w"
        )
        ttk.Label(section, text="Manual Usage / Stage").grid(
            row=2, column=2, padx=5, pady=4, sticky="w"
        )
        ttk.Label(section, text="Receiving ISO").grid(
            row=2, column=4, padx=5, pady=4, sticky="w"
        )

        self.entry_heel = ttk.Entry(section, width=12)
        self.entry_manual_usage = ttk.Entry(section, width=12)
        self.cmb_receiving_iso = ttk.Combobox(
            section,
            state="readonly",
            width=15,
            values=["ISO 1", "ISO 2"],
        )
        self.entry_heel.grid(row=2, column=1, padx=5, pady=4)
        self.entry_manual_usage.grid(row=2, column=3, padx=5, pady=4)
        self.cmb_receiving_iso.grid(row=2, column=5, padx=5, pady=4)

        self._build_iso_row(section, 3, "ISO 1")
        self._build_iso_row(section, 4, "ISO 2")

        button_frame = ttk.Frame(section)
        button_frame.grid(
            row=5, column=0, columnspan=8, padx=5, pady=(10, 0), sticky="w"
        )

        ttk.Button(
            button_frame,
            text="Save Setup and Recalculate",
            command=self._save_selected_setup,
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            button_frame,
            text="Confirm Cut",
            command=lambda: self._set_cut_confirmation(True),
        ).pack(side="left", padx=4)
        ttk.Button(
            button_frame,
            text="Keep Active",
            command=lambda: self._set_cut_confirmation(False),
        ).pack(side="left", padx=4)
        ttk.Button(
            button_frame,
            text="Reset Chemical Setup",
            command=self._reset_selected_setup,
        ).pack(side="left", padx=4)

    def _build_iso_row(self, parent, row: int, iso_name: str) -> None:
        ttk.Label(parent, text=iso_name).grid(
            row=row, column=0, padx=5, pady=4, sticky="w"
        )
        ttk.Label(parent, text="Status").grid(
            row=row, column=1, padx=5, pady=4, sticky="e"
        )
        status = ttk.Combobox(
            parent,
            state="readonly",
            width=12,
            values=["Active", "Reserve", "Empty"],
        )
        status.grid(row=row, column=2, padx=5, pady=4, sticky="w")
        status.set("Active" if iso_name == "ISO 1" else "Empty")

        ttk.Label(parent, text="Quantity").grid(
            row=row, column=3, padx=5, pady=4, sticky="e"
        )
        quantity = ttk.Entry(parent, width=12)
        quantity.grid(row=row, column=4, padx=5, pady=4, sticky="w")
        quantity.insert(0, "0")

        can_receive = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            parent,
            text="Can Receive",
            variable=can_receive,
        ).grid(row=row, column=5, padx=5, pady=4, sticky="w")

        if iso_name == "ISO 1":
            self.cmb_iso1_status = status
            self.entry_iso1_quantity = quantity
            self.var_iso1_receive = can_receive
        else:
            self.cmb_iso2_status = status
            self.entry_iso2_quantity = quantity
            self.var_iso2_receive = can_receive

    def update_from_state(self, state) -> None:
        self.state = state
        self.recalculate(show_errors=False)

    def recalculate(self, show_errors: bool = True) -> None:
        self._clear_table()

        if not self.state:
            return

        chemicals = self.state.ttmt_data.get(
            "chemdispatch_tab", {}
        ).get("chemicals", [])
        if not chemicals:
            self.lbl_summary.config(text="No TMT chemical data is loaded.")
            return

        try:
            stage_count = self._positive_int(
                self.entry_stage_count.get(), "Stages Per Well"
            )
            zero_count = self._positive_int(
                self.entry_zero_stages.get(), "Latest Zero Stages"
            )
            hours_left = self._nonnegative_float(
                self.entry_hours_left.get(), "Estimated Pad Hours Left"
            )
        except ValueError as exc:
            if show_errors:
                messagebox.showwarning("Invalid Input", str(exc))
            return

        completed = self.state.ttmt_data.get(
            "sandinfo_completed", {}
        ).get("total_completed_stages", 0)
        total_stages = self.state.ttmt_data.get(
            "list_tab", {}
        ).get("total_stages", 0)
        stages_left = max(0.0, self._safe_float(total_stages) - self._safe_float(completed))

        start_stage = ""
        if self.cmb_average_mode.get() == "From Stage Number":
            start_stage = self.entry_start_stage.get().strip()
            if not start_stage:
                if show_errors:
                    messagebox.showwarning(
                        "Missing Stage",
                        "Enter a stage number for From Stage Number mode.",
                    )
                return

        self.last_result = calculate_chemical_forecast(
            tmt_chemicals=chemicals,
            ts_data=self.state.ts_data,
            manual_usage=self.manual_usage,
            stage_count=stage_count,
            start_stage_number=start_stage,
            consecutive_zero_stages=zero_count,
            stages_left_on_pad=stages_left,
            estimated_hours_left=hours_left,
            chemical_profiles=self.chemical_profiles,
            container_assignments=self.container_assignments,
            receiving_containers=self.receiving_containers,
            cut_confirmations=self.cut_confirmations,
        )

        order_now_count = 0
        warning_count = 0
        confirmation_count = self.last_result.get(
            "confirmation_required_count", 0
        )

        for chemical in self.last_result.get("chemicals", []):
            name = chemical.get("chemical_name", "")
            key = normalize_chemical_name(name)
            order_status = chemical.get("order_status", "")
            warnings = chemical.get("warnings", [])
            requires_confirmation = chemical.get(
                "requires_cut_confirmation", False
            )

            if order_status == "ORDER NOW":
                tag = "order_now"
                order_now_count += 1
            elif warnings or requires_confirmation:
                tag = "warning"
                warning_count += 1
            elif chemical.get("usage_per_stage", 0) <= 0:
                tag = "inactive"
            else:
                tag = "good"

            item_id = self.tree.insert(
                "",
                "end",
                iid=key,
                values=(
                    name,
                    self._qty(chemical.get("total_inventory", 0), chemical.get("unit", "gal")),
                    self._qty(chemical.get("usage_per_stage", 0), chemical.get("unit", "gal"), "/stage"),
                    chemical.get("usage_status", ""),
                    chemical.get("ts_sample_count", 0),
                    self._optional_number(chemical.get("hours_until_arrival_target", chemical.get("hours_until_empty"))),
                    self._hours_text(chemical.get("order_in_hours")),
                    self._date_text(chemical.get("target_delivery_time")),
                    self._yes_no(chemical.get("load_fits")),
                    self._qty(chemical.get("shortage_to_finish", 0), chemical.get("unit", "gal")),
                    order_status,
                ),
                tags=(tag,),
            )
            self.tree.set(item_id, "chemical", name)

        cycle_hours = self.last_result.get("cycle_hours_per_stage", 0)
        self.lbl_summary.config(
            text=(
                f"TS matched {self.last_result.get('ts_chemical_match_count', 0)} "
                f"of {len(chemicals)} chemicals. Stages left: "
                f"{self._format_number(stages_left)}. Completion cycle: "
                f"{self._format_number(cycle_hours)} hr/stage."
            )
        )
        self.lbl_details.config(
            text=(
                f"ORDER NOW: {order_now_count} | Warnings: {warning_count} | "
                f"Cut confirmations needed: {confirmation_count}. "
                f"Configuration warnings: {len(self.last_result.get('warnings', []))}."
            )
        )

    def _on_tree_select(self, event=None) -> None:
        selection = self.tree.selection()
        if not selection or not self.last_result:
            return

        key = selection[0]
        chemical = next(
            (
                row for row in self.last_result.get("chemicals", [])
                if normalize_chemical_name(row.get("chemical_name")) == key
            ),
            None,
        )
        if chemical:
            self._load_editor(chemical)

    def _load_editor(self, chemical) -> None:
        name = chemical.get("chemical_name", "")
        key = normalize_chemical_name(name)
        profile = self.chemical_profiles.get(key, chemical.get("profile", get_default_profile(name)))

        self.lbl_selected_chemical.config(
            text=f"Selected: {name} ({profile.get('unit', 'gal')})"
        )
        self._set_entry(self.entry_delivery_qty, profile.get("delivery_quantity"))
        self._set_entry(self.entry_lead_time, profile.get("lead_time_hours"))
        self._set_entry(self.entry_capacity, profile.get("working_capacity"))
        self._set_entry(self.entry_arrival_target, profile.get("arrival_target"))
        self._set_entry(self.entry_heel, profile.get("unusable_heel"))
        self._set_entry(self.entry_manual_usage, self.manual_usage.get(key, ""))

        containers = self.container_assignments.get(key)
        if not containers:
            total = chemical.get("current_quantity", 0)
            containers = [
                {
                    "container_id": "ISO 1",
                    "status": "Active",
                    "current_quantity": total,
                    "can_receive": True,
                },
                {
                    "container_id": "ISO 2",
                    "status": "Empty",
                    "current_quantity": 0,
                    "can_receive": True,
                },
            ]

        by_id = {row.get("container_id"): row for row in containers}
        iso1 = by_id.get("ISO 1", {})
        iso2 = by_id.get("ISO 2", {})

        self.cmb_iso1_status.set(iso1.get("status", "Active"))
        self.cmb_iso2_status.set(iso2.get("status", "Empty"))
        self._set_entry(self.entry_iso1_quantity, iso1.get("current_quantity", 0))
        self._set_entry(self.entry_iso2_quantity, iso2.get("current_quantity", 0))
        self.var_iso1_receive.set(bool(iso1.get("can_receive", True)))
        self.var_iso2_receive.set(bool(iso2.get("can_receive", True)))
        self.cmb_receiving_iso.set(
            self.receiving_containers.get(key, "ISO 1")
        )

    def _save_selected_setup(self) -> None:
        name = self._selected_chemical_name()
        if not name:
            return
        key = normalize_chemical_name(name)
        default = get_default_profile(name)

        try:
            profile = {
                **default,
                "delivery_quantity": self._nonnegative_float(
                    self.entry_delivery_qty.get(), "Delivery Quantity"
                ),
                "lead_time_hours": self._nonnegative_float(
                    self.entry_lead_time.get(), "Lead Time"
                ),
                "working_capacity": self._optional_nonnegative_float(
                    self.entry_capacity.get(), "Working Capacity"
                ),
                "arrival_target": self._nonnegative_float(
                    self.entry_arrival_target.get(), "Arrival Target"
                ),
                "unusable_heel": self._nonnegative_float(
                    self.entry_heel.get(), "Unusable Heel"
                ),
            }
            iso1_qty = self._nonnegative_float(
                self.entry_iso1_quantity.get(), "ISO 1 Quantity"
            )
            iso2_qty = self._nonnegative_float(
                self.entry_iso2_quantity.get(), "ISO 2 Quantity"
            )
        except ValueError as exc:
            messagebox.showwarning("Invalid Setup", str(exc))
            return

        manual_text = self.entry_manual_usage.get().strip()
        if manual_text:
            try:
                self.manual_usage[key] = self._nonnegative_float(
                    manual_text, "Manual Usage"
                )
            except ValueError as exc:
                messagebox.showwarning("Invalid Setup", str(exc))
                return
        else:
            self.manual_usage.pop(key, None)

        self.chemical_profiles[key] = profile
        self.container_assignments[key] = [
            {
                "container_id": "ISO 1",
                "status": self.cmb_iso1_status.get(),
                "current_quantity": iso1_qty,
                "working_capacity": profile.get("working_capacity"),
                "can_receive": self.var_iso1_receive.get(),
            },
            {
                "container_id": "ISO 2",
                "status": self.cmb_iso2_status.get(),
                "current_quantity": iso2_qty,
                "working_capacity": profile.get("working_capacity"),
                "can_receive": self.var_iso2_receive.get(),
            },
        ]
        self.receiving_containers[key] = (
            self.cmb_receiving_iso.get() or "ISO 1"
        )

        self.recalculate()
        if key in self.tree.get_children():
            self.tree.selection_set(key)
            self.tree.see(key)

    def _set_cut_confirmation(self, confirmed_cut: bool) -> None:
        name = self._selected_chemical_name()
        if not name:
            return
        key = normalize_chemical_name(name)
        self.cut_confirmations[key] = confirmed_cut
        self.recalculate()
        if key in self.tree.get_children():
            self.tree.selection_set(key)
            self.tree.see(key)

    def _reset_selected_setup(self) -> None:
        name = self._selected_chemical_name()
        if not name:
            return
        key = normalize_chemical_name(name)
        self.manual_usage.pop(key, None)
        self.chemical_profiles.pop(key, None)
        self.container_assignments.pop(key, None)
        self.receiving_containers.pop(key, None)
        self.cut_confirmations.pop(key, None)
        self.recalculate()
        if key in self.tree.get_children():
            self.tree.selection_set(key)
            self.tree.see(key)

    def _selected_chemical_name(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo(
                "Select Chemical",
                "Select a chemical in the results table first.",
            )
            return ""
        return self.tree.set(selection[0], "chemical")

    def _clear_table(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

    def _set_entry(self, entry, value) -> None:
        entry.delete(0, "end")
        if value is not None:
            entry.insert(0, self._format_number(value))

    def _positive_int(self, value, label):
        number = self._nonnegative_float(value, label)
        if number <= 0 or not number.is_integer():
            raise ValueError(f"{label} must be a positive whole number.")
        return int(number)

    def _nonnegative_float(self, value, label):
        try:
            number = float(str(value).replace(",", "").strip())
        except (TypeError, ValueError):
            raise ValueError(f"{label} must be a number.")
        if number < 0:
            raise ValueError(f"{label} cannot be negative.")
        return number

    def _optional_nonnegative_float(self, value, label):
        if str(value).strip() == "":
            return None
        return self._nonnegative_float(value, label)

    def _safe_float(self, value):
        try:
            return float(str(value).replace(",", "").strip())
        except (TypeError, ValueError):
            return 0.0

    def _format_number(self, value):
        if value is None:
            return ""
        number = self._safe_float(value)
        if number == int(number):
            return f"{int(number):,}"
        return f"{number:,.2f}"

    def _qty(self, value, unit, suffix=""):
        return f"{self._format_number(value)} {unit}{suffix}"

    def _optional_number(self, value):
        return "N/A" if value is None else self._format_number(value)

    def _hours_text(self, value):
        return "N/A" if value is None else f"{self._format_number(value)} hr"

    def _date_text(self, value):
        if value is None:
            return "N/A"
        return value.strftime("%m/%d/%Y %I:%M %p")

    def _yes_no(self, value):
        if value is None:
            return "N/A"
        return "Yes" if value else "No"

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
