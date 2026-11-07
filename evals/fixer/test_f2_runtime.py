"""Runtime proof complements the conservative source-shape checks for F2."""
import shutil
import subprocess
from pathlib import Path

import pytest

from ai.fixer import apply_to_copy

ROOT = Path(__file__).resolve().parents[2]
SHOP = ROOT / "targets" / "demo-shop"
HARNESS = Path(__file__).with_name("check_f2_runtime.cjs")


@pytest.mark.parametrize("patched", [False, True], ids=["seeded-bug", "fixed"])
def test_create_retry_and_independent_equal_price_purchases(tmp_path, patched):
    node = shutil.which("node")
    if not node or not (SHOP / "node_modules/typescript").exists():
        pytest.skip("requires Node and npm install --prefix targets/demo-shop")
    shop = SHOP
    if patched:
        diff = (ROOT / "ai/fixer/known_fixes/BUG-02.diff").read_text(encoding="utf-8")
        shop = apply_to_copy(diff, SHOP, tmp_path / "shop")
    result = subprocess.run(
        [node, str(HARNESS), str(shop / "src/checkout.ts")],
        capture_output=True, text=True, timeout=20,
    )
    if patched:
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        assert result.returncode != 0
        assert "request ID is required" in result.stderr
