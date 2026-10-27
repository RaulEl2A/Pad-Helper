from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class AppState:
    ttmt_file_path: str = ""
    ts_file_paths: List[str] = field(default_factory=list)
    matched_ts_files: List[str] = field(default_factory=list)
    unmatched_ts_files: List[str] = field(default_factory=list)

    ttmt_data: Dict[str, Any] = field(default_factory=dict)
    ts_data: Dict[str, Any] = field(default_factory=dict)