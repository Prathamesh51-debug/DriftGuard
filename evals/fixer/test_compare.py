from pathlib import Path

from evals.fixer.compare import score_against_known

ROOT = Path(__file__).resolve().parents[2]
GOOD = (ROOT / "ai" / "fixer" / "tests" / "bug01_fix.diff").read_text(encoding="utf-8")


def test_identical_patch_scores_full():
    assert score_against_known(GOOD, GOOD) == {"same_files": True, "added_line_overlap": 1.0}


def test_different_file_and_code_scores_zero():
    other = "--- a/src/server.ts\n+++ b/src/server.ts\n@@ -1 +1,2 @@\n a\n+console.log('x')\n"
    score = score_against_known(other, GOOD)
    assert score["same_files"] is False and score["added_line_overlap"] == 0.0
