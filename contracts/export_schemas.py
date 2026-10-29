"""
Export Pydantic models to JSON Schemas for CI validation and Role C's TypeScript UI.
Can be executed as:
  python contracts/export_schemas.py
or:
  python -m contracts.export_schemas
"""

import json
import sys
from pathlib import Path

# Ensure project root is in sys.path when executed directly
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from contracts.models import Scenario, Result

SCHEMAS_DIR = Path(__file__).parent / "schemas"


def export_schemas() -> None:
    SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)

    scenario_schema = Scenario.model_json_schema()
    result_schema = Result.model_json_schema()

    scenario_path = SCHEMAS_DIR / "scenario.schema.json"
    result_path = SCHEMAS_DIR / "result.schema.json"

    scenario_path.write_text(json.dumps(scenario_schema, indent=2), encoding="utf-8")
    result_path.write_text(json.dumps(result_schema, indent=2), encoding="utf-8")

    print(f"Exported JSON schemas:")
    print(f"  - {scenario_path}")
    print(f"  - {result_path}")


if __name__ == "__main__":
    export_schemas()
