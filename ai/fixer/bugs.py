"""Seeded-bug catalog: reads targets/demo-shop/bugs.yaml and matches a scenario to its bug."""

from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel

from contracts import Scenario

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUGS_FILE = REPO_ROOT / "targets" / "demo-shop" / "bugs.yaml"


class BugEntry(BaseModel):
    id: str
    fault: str
    name: str
    file: str
    target_line: Optional[int] = None
    status: str = "dormant"
    trigger: Optional[str] = None
    safe_behavior: str
    failure_mode: Optional[str] = None


def load_bugs(path: Path = DEFAULT_BUGS_FILE) -> List[BugEntry]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return [BugEntry.model_validate(b) for b in data["bugs"]]


def find_bug(scenario: Scenario, bugs: List[BugEntry]) -> BugEntry:
    """Pick the bug a failing scenario points at: same fault, then same file, then nearest line."""
    same_fault = [b for b in bugs if b.fault == scenario.fault.value]
    if not same_fault:
        raise LookupError(f"no seeded bug for fault {scenario.fault.value}")
    call = scenario.target_call

    def distance(b: BugEntry):
        line_gap = abs(b.target_line - call.line) if b.target_line else 10**6
        return (b.file != call.file, line_gap)

    return min(same_fault, key=distance)
