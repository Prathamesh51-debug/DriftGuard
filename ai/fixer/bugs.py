"""Seeded-bug catalog: reads targets/demo-shop/bugs.yaml and matches a scenario to its bug."""

from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel

from contracts import Scenario

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUGS_FILE = REPO_ROOT / "targets" / "demo-shop" / "bugs.yaml"
# Curated fixes, tried in this order unless a fault has a verified Role C fallback.
BUNDLED_FIX_DIR = Path(__file__).resolve().parent / "known_fixes"
ROLE_C_PATCH_FIRST = {"BUG-01", "BUG-02", "BUG-09"}
KNOWN_FIX_DIRS = [REPO_ROOT / "targets" / "known-fixes", BUNDLED_FIX_DIR]


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


def known_fix_candidates(bug_id: str) -> List[Path]:
    """Curated fixes on disk for a bug, in the order the Fixer should try them."""
    dirs = list(KNOWN_FIX_DIRS)
    if bug_id in ROLE_C_PATCH_FIRST and BUNDLED_FIX_DIR in dirs:
        # The Role C integration patch supersedes the older target-side patch for these faults.
        dirs = [BUNDLED_FIX_DIR] + [directory for directory in dirs if directory != BUNDLED_FIX_DIR]
    return [d / f"{bug_id}{ext}" for d in dirs for ext in (".patch", ".diff") if (d / f"{bug_id}{ext}").is_file()]


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
