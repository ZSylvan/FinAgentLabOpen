#!/usr/bin/env python3
"""Validate FinAgentLab's consolidated license and attribution files."""

from __future__ import annotations

import sys
from pathlib import Path


def require_text(path: Path, required: tuple[str, ...]) -> bool:
    if not path.is_file():
        print(f"Missing legal file: {path.name}")
        return False

    content = path.read_text(encoding="utf-8")
    missing = [item for item in required if item not in content]
    if missing:
        print(f"{path.name} is missing required markers: {', '.join(missing)}")
        return False

    print(f"OK: {path.name}")
    return True


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    checks = (
        require_text(
            project_root / "LICENSE",
            ("Apache License", "non-commercial", "THIRD_PARTY_NOTICES.md"),
        ),
        require_text(
            project_root / "THIRD_PARTY_NOTICES.md",
            ("Apache License 2.0", "inherited", "contributors"),
        ),
        require_text(
            project_root / "docs" / "legal" / "AUTHORIZATION_SCOPE.md",
            ("non-commercial", "does not cover", "private authorization"),
        ),
    )
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
