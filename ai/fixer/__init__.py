"""Fixer: drafts a patch for a failing Result and proves it applies to a copy of the app."""

from .bugs import BugEntry, find_bug, known_fix_candidates, load_bugs
from .fixer import FixProposal, propose_fix
from .llm import LLMClient, ScriptedLLM
from .patcher import PatchCheck, apply_to_copy, check_diff, normalize_diff

__all__ = [
    "BugEntry", "find_bug", "known_fix_candidates", "load_bugs",
    "FixProposal", "propose_fix",
    "LLMClient", "ScriptedLLM",
    "PatchCheck", "apply_to_copy", "check_diff", "normalize_diff",
]
