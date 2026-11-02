"""Checks and applies a model-written diff to a COPY of the target app. The original is never touched."""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

from pydantic import BaseModel

SHOP_PREFIX = "targets/demo-shop/"
COPY_IGNORE = shutil.ignore_patterns("node_modules", "dist", ".git")
HEADER = re.compile(r"^(--- |\+\+\+ |diff --git )")


class PatchCheck(BaseModel):
    ok: bool
    files: List[str] = []
    lines_changed: int = 0
    error: Optional[str] = None


def normalize_diff(diff: str) -> str:
    """Strip code fences and the repo-root prefix so paths are relative to the shop root."""
    text = diff.strip("\n")
    text = re.sub(r"^```[a-z]*\n", "", text)
    text = re.sub(r"\n```$", "", text)
    lines = [line.replace(SHOP_PREFIX, "") if HEADER.match(line) else line for line in text.split("\n")]
    return "\n".join(lines) + "\n"


def _scan(diff: str) -> Tuple[List[str], int]:
    files, changed = [], 0
    for line in diff.split("\n"):
        if line.startswith("+++ "):
            files.append(re.sub(r"^b/", "", line[4:].strip()))
        elif line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
            changed += 1
    return files, changed


def _git_apply(args: List[str], diff: str, cwd: Path) -> Optional[str]:
    proc = subprocess.run(
        ["git", "apply", "--recount", "--ignore-whitespace", *args, "-"],
        input=diff, text=True, capture_output=True, cwd=cwd,
    )
    return None if proc.returncode == 0 else (proc.stderr.strip() or "git apply failed")


def check_diff(diff: str, shop_dir: Path, allowed_file: str, max_changed_lines: int = 40) -> PatchCheck:
    """Guard the diff (one allowed file, small) and prove it applies cleanly to a scratch copy."""
    files, changed = _scan(diff)
    if not files:
        return PatchCheck(ok=False, error="diff has no '+++' file header")
    if set(files) != {allowed_file}:
        return PatchCheck(ok=False, files=files, lines_changed=changed,
                          error=f"diff may only change {allowed_file}, but touches {files}")
    if changed > max_changed_lines:
        return PatchCheck(ok=False, files=files, lines_changed=changed,
                          error=f"diff changes {changed} lines, limit is {max_changed_lines}")
    scratch = Path(tempfile.mkdtemp(prefix="driftguard-fix-"))
    try:
        copy = scratch / "shop"
        shutil.copytree(shop_dir, copy, ignore=COPY_IGNORE)
        problem = _git_apply(["--check"], diff, copy)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return PatchCheck(ok=problem is None, files=files, lines_changed=changed, error=problem)


def apply_to_copy(diff: str, shop_dir: Path, dest: Path) -> Path:
    """Copy the app to `dest`, apply the diff there and return `dest`. Raises if it does not apply."""
    copy = Path(dest)
    shutil.copytree(shop_dir, copy, ignore=COPY_IGNORE)
    problem = _git_apply([], diff, copy)
    if problem:
        shutil.rmtree(copy, ignore_errors=True)
        raise ValueError(problem)
    return copy
