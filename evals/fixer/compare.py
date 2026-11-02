"""Score a generated patch against the curated fix in targets/known-fixes/.

Planner Ref: Part 8 (Fixer eval table). A patch is never judged by text match alone: the
real test is the chaos re-run going green. This score is the fast, free first check.
"""

from typing import Dict, Set


def _files(diff: str) -> Set[str]:
    return {line[4:].strip().removeprefix("b/") for line in diff.split("\n") if line.startswith("+++ ")}


def _added(diff: str) -> Set[str]:
    return {
        line[1:].strip()
        for line in diff.split("\n")
        if line.startswith("+") and not line.startswith("+++") and line[1:].strip()
    }


def score_against_known(generated: str, known: str) -> Dict[str, object]:
    """Compare which files a patch touches and how much of its added code matches the curated fix."""
    got, want = _added(generated), _added(known)
    union = got | want
    return {
        "same_files": _files(generated) == _files(known),
        "added_line_overlap": round(len(got & want) / len(union), 2) if union else 1.0,
    }
