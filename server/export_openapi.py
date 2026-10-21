"""Export FastAPI application OpenAPI schema to generated/openapi.json."""

import json
import sys
from pathlib import Path

# Ensure project root is in sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from server.main import app


def export_openapi() -> Path:
    """Generate and write the OpenAPI schema JSON."""
    schema = app.openapi()
    output_dir = project_root / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "openapi.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)
    return output_file


if __name__ == "__main__":
    out = export_openapi()
    print(f"OpenAPI schema exported to {out}")
