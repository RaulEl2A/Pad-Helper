from pathlib import Path
from typing import Dict, List, Union

import pandas as pd


class ExcelLoader:
    def __init__(self) -> None:
        self.ttmt_path: Path | None = None
        self.ts_paths: List[Path] = []

    def set_ttmt_file(self, file_path: Union[str, Path]) -> None:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"TT and MT file not found: {path}")
        self.ttmt_path = path

    def set_ts_files(self, file_paths: List[Union[str, Path]]) -> None:
        paths: List[Path] = []
        for file_path in file_paths:
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"TS file not found: {path}")
            paths.append(path)
        self.ts_paths = paths

    def get_sheet_names(self, file_path: Union[str, Path]) -> List[str]:
        path = Path(file_path)
        with pd.ExcelFile(path) as excel_file:
            return excel_file.sheet_names

    def read_sheet(self, file_path: Union[str, Path], sheet_name: str) -> pd.DataFrame:
        path = Path(file_path)
        return pd.read_excel(path, sheet_name=sheet_name, header=None)

    def read_multiple_sheets(
        self,
        file_path: Union[str, Path],
        sheet_names: List[str]
    ) -> Dict[str, pd.DataFrame]:
        result: Dict[str, pd.DataFrame] = {}
        available_sheets = {
            name.strip().casefold(): name
            for name in self.get_sheet_names(file_path)
        }
        for sheet_name in sheet_names:
            actual_name = available_sheets.get(sheet_name.strip().casefold())
            if actual_name is None:
                continue
            result[sheet_name] = self.read_sheet(file_path, actual_name)
        return result