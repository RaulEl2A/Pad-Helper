import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from logic.excel_loader import ExcelLoader
from logic.parser_ttmt import TTMTParser
from logic.parser_ts import TSParser
from models.app_state import AppState
from ui.tab_chemical import ChemicalTab
from ui.tab_final_sand import FinalSandTab
from ui.tab_time import TimeTab
from ui.tab_wellbore import WellboreTab


class PadHelperApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Frac Calculator")
        self.root.geometry("1400x850")
        self.root.minsize(1100, 700)
        self._maximize_window()

        self.state = AppState()
        self.loader = ExcelLoader()

        self._build_top_bar()
        self._build_notebook()

    def _maximize_window(self) -> None:
        try:
            self.root.state("zoomed")
        except Exception:
            try:
                self.root.attributes("-zoomed", True)
            except Exception:
                pass

    def _build_top_bar(self) -> None:
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(side="top", fill="x")

        self.btn_load_ttmt = ttk.Button(
            top_frame,
            text="Load TT and MT",
            command=self.load_ttmt_file,
        )
        self.btn_load_ttmt.grid(
            row=0,
            column=0,
            padx=5,
            pady=5,
            sticky="w",
        )

        self.btn_load_ts = ttk.Button(
            top_frame,
            text="Load TS Files",
            command=self.load_ts_files,
        )
        self.btn_load_ts.grid(
            row=0,
            column=1,
            padx=5,
            pady=5,
            sticky="w",
        )

        ttk.Label(top_frame, text="TT and MT File:").grid(
            row=0,
            column=2,
            padx=(20, 5),
            pady=5,
            sticky="e",
        )
        self.lbl_ttmt_file = ttk.Label(
            top_frame,
            text="None loaded",
            width=60,
        )
        self.lbl_ttmt_file.grid(
            row=0,
            column=3,
            padx=5,
            pady=5,
            sticky="w",
        )

        ttk.Label(top_frame, text="Matched TS Files:").grid(
            row=1,
            column=0,
            padx=5,
            pady=5,
            sticky="e",
        )
        self.lbl_matched_ts = ttk.Label(
            top_frame,
            text="0",
            width=20,
        )
        self.lbl_matched_ts.grid(
            row=1,
            column=1,
            padx=5,
            pady=5,
            sticky="w",
        )

        ttk.Label(top_frame, text="Unmatched TS Files:").grid(
            row=1,
            column=2,
            padx=5,
            pady=5,
            sticky="e",
        )
        self.lbl_unmatched_ts = ttk.Label(
            top_frame,
            text="0",
            width=20,
        )
        self.lbl_unmatched_ts.grid(
            row=1,
            column=3,
            padx=5,
            pady=5,
            sticky="w",
        )

        ttk.Label(top_frame, text="Status:").grid(
            row=2,
            column=0,
            padx=5,
            pady=5,
            sticky="e",
        )
        self.lbl_status = ttk.Label(
            top_frame,
            text="Ready",
            width=100,
        )
        self.lbl_status.grid(
            row=2,
            column=1,
            columnspan=3,
            padx=5,
            pady=5,
            sticky="w",
        )

    def _build_notebook(self) -> None:
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=(0, 10),
        )

        self.chemical_tab = ChemicalTab(self.notebook)
        self.time_tab = TimeTab(self.notebook)
        self.final_sand_tab = FinalSandTab(self.notebook)
        self.wellbore_tab = WellboreTab(self.notebook)

        self.notebook.add(self.chemical_tab.frame, text="Chemical")
        self.notebook.add(self.time_tab.frame, text="Time")
        self.notebook.add(self.final_sand_tab.frame, text="Final Sand")
        self.notebook.add(self.wellbore_tab.frame, text="Wellbore")

    def load_ttmt_file(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Select TT and MT File",
            filetypes=[("Excel Files", "*.xlsx *.xlsm *.xls")],
        )

        if not file_path:
            return

        try:
            self.loader.set_ttmt_file(file_path)

            required_sheets = [
                "List",
                "ChemDispatch",
                "SetUp",
                "SandBOL",
                "SandInfo",
                "strapCharts",
                "TimeLog",
            ]

            workbook_sheets = self.loader.read_multiple_sheets(
                file_path,
                required_sheets,
            )

            parser = TTMTParser(workbook_sheets)
            missing_sheets = parser.validate_required_sheets()

            if missing_sheets:
                messagebox.showwarning(
                    "Missing Sheets",
                    "Missing TT and MT sheets:\n"
                    + "\n".join(missing_sheets),
                )

            parsed_data = parser.parse_all()

            self.state.ttmt_file_path = file_path
            self.state.ttmt_data = parsed_data
            self.state.ts_file_paths = []
            self.state.matched_ts_files = []
            self.state.unmatched_ts_files = []
            self.state.ts_data = {}

            self.lbl_ttmt_file.config(
                text=os.path.basename(file_path)
            )
            self.lbl_matched_ts.config(text="0")
            self.lbl_unmatched_ts.config(text="0")
            self.lbl_status.config(
                text="TT and MT loaded successfully."
            )

            self.refresh_tabs()

            messagebox.showinfo(
                "Success",
                "TT and MT file loaded and parsed successfully.",
            )

        except Exception as exc:
            messagebox.showerror("Load Error", str(exc))
            self.lbl_status.config(
                text="Failed to load TT and MT file."
            )

    def load_ts_files(self) -> None:
        file_paths = filedialog.askopenfilenames(
            title="Select TS Files",
            filetypes=[("Excel Files", "*.xlsx *.xlsm *.xls")],
        )

        if not file_paths:
            return

        if not self.state.ttmt_file_path:
            messagebox.showwarning(
                "No TT and MT File",
                "Please load the TT and MT file first.",
            )
            return

        try:
            self.loader.set_ts_files(list(file_paths))

            ttmt_wells = self.state.ttmt_data.get(
                "list_tab",
                {},
            ).get("wells", [])

            matched = []
            unmatched = []
            ts_data = {}
            chem_stage_count = 0
            chem_name_count = 0
            chem_warnings = []

            for file_path in file_paths:
                base_name = os.path.basename(file_path).lower()
                matched_well = self._match_ts_to_well(
                    base_name,
                    ttmt_wells,
                )

                if not matched_well:
                    unmatched.append(file_path)
                    continue

                matched.append(file_path)

                workbook_sheets = self.loader.read_multiple_sheets(
                    file_path,
                    ["Wellbore", "Chem"],
                )

                parser = TSParser(workbook_sheets, file_path)
                wellbore_data = parser.parse_wellbore_tab()
                chem_data = parser.parse_chem_tab()

                # Preserve the prior top-level Wellbore structure so the
                # existing Wellbore tab continues to work. Add Chem data
                # alongside those existing fields.
                combined_data = dict(wellbore_data)
                combined_data["chem_tab"] = chem_data
                combined_data["source_file"] = os.path.basename(file_path)

                ts_data[matched_well] = combined_data

                chem_stage_count += chem_data.get("stage_count", 0)
                chem_name_count = max(
                    chem_name_count,
                    chem_data.get("chemical_count", 0),
                )

                for warning in chem_data.get("warnings", []):
                    chem_warnings.append(
                        f"{os.path.basename(file_path)}: {warning}"
                    )

            self.state.ts_file_paths = list(file_paths)
            self.state.matched_ts_files = matched
            self.state.unmatched_ts_files = unmatched
            self.state.ts_data = ts_data

            self.lbl_matched_ts.config(text=str(len(matched)))
            self.lbl_unmatched_ts.config(text=str(len(unmatched)))
            self.lbl_status.config(
                text=(
                    f"Loaded {len(file_paths)} TS file(s). "
                    f"Matched: {len(matched)} | "
                    f"Unmatched: {len(unmatched)} | "
                    f"Chemicals found: {chem_name_count} | "
                    f"StageStrap rows: {chem_stage_count}"
                )
            )

            if unmatched:
                unmatched_names = [
                    os.path.basename(path)
                    for path in unmatched
                ]
                messagebox.showwarning(
                    "Unmatched TS Files",
                    "These TS files did not match TT and MT wells:\n\n"
                    + "\n".join(unmatched_names),
                )

            if chem_warnings:
                messagebox.showwarning(
                    "TS Chemical Warnings",
                    "\n\n".join(chem_warnings[:20]),
                )

            self.refresh_tabs()

        except Exception as exc:
            messagebox.showerror("Load Error", str(exc))
            self.lbl_status.config(text="Failed to load TS files.")

    def _match_ts_to_well(
        self,
        base_name: str,
        ttmt_wells,
    ):
        for well in ttmt_wells:
            well_lower = well.lower().strip()
            parts = well_lower.split()

            if all(part in base_name for part in parts[:2]):
                return well

            if well_lower in base_name:
                return well

        return None

    def refresh_tabs(self) -> None:
        self.chemical_tab.update_from_state(self.state)
        self.time_tab.update_from_state(self.state)
        self.final_sand_tab.update_from_state(self.state)
        self.wellbore_tab.update_from_state(self.state)

    def run(self) -> None:
        self.root.mainloop()
