"""Fail when legacy product branding leaks outside legal notice files."""

from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


SKIPPED_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".understand-anything",
    ".venv",
    "__pycache__",
    "dist",
    "htmlcov",
    "node_modules",
    "release",
    "runtime",
    "temp",
    "vendors",
}
LEGAL_WHITELIST = {"LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md"}
MAX_TEXT_FILE_SIZE = 5 * 1024 * 1024


def _legacy(*parts: str) -> str:
    """Keep the checker's own source free of the literals it rejects."""
    return "".join(parts)


FORBIDDEN_PATTERNS = {
    "legacy product brand": re.compile(_legacy("Trading", "Agents")),
    "legacy community brand": re.compile(_legacy("Trading", "Agents-CN")),
    "legacy upstream owner": re.compile(
        rf"{_legacy('Tauric', 'Research')}|{_legacy('Tauric', ' Research')}"
    ),
    "legacy maintainer name": re.compile(
        _legacy("hsliu", "ping"), re.IGNORECASE
    ),
    "legacy maintainer handle": re.compile(
        _legacy("hs", "liup"), re.IGNORECASE
    ),
    "legacy contact": re.compile(
        rf"{re.escape(_legacy('hs', 'liup', '@163.com'))}|"
        rf"{_legacy('109', '1917201')}|{_legacy('782', '124367')}"
    ),
    "legacy repository placeholder": re.compile(
        re.escape(_legacy("YOUR_", "USERNAME/FinAgentLab")), re.IGNORECASE
    ),
    "legacy repository": re.compile(
        re.escape(_legacy("github.com/", "hsliu", "ping/FinAgentLab")),
        re.IGNORECASE,
    ),
    "legacy marketing site": re.compile(
        re.escape(_legacy("trading", "agents-ai.com")), re.IGNORECASE
    ),
}


@dataclass(frozen=True)
class Violation:
    path: Path
    line: int
    category: str


def _is_legal_whitelist(path: Path) -> bool:
    return path.name in LEGAL_WHITELIST


def _candidate_paths(root: Path):
    if (root / ".git").exists():
        result = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            for raw_path in result.stdout.split(b"\0"):
                if raw_path:
                    decoded = raw_path.decode(
                        "utf-8", errors="surrogateescape"
                    )
                    yield root / decoded
            return

    yield from root.rglob("*")


def _iter_candidate_files(root: Path):
    for path in _candidate_paths(root):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in SKIPPED_DIRECTORIES for part in relative.parts):
            continue
        if _is_legal_whitelist(relative):
            continue
        yield relative, path


def find_violations(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    for relative, path in _iter_candidate_files(root):
        relative_text = relative.as_posix()
        for category, pattern in FORBIDDEN_PATTERNS.items():
            if pattern.search(relative_text):
                violations.append(Violation(relative, 0, category))

        try:
            if path.stat().st_size > MAX_TEXT_FILE_SIZE:
                continue
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_number, line in enumerate(content.splitlines(), start=1):
            for category, pattern in FORBIDDEN_PATTERNS.items():
                if pattern.search(line):
                    violations.append(
                        Violation(relative, line_number, category)
                    )
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root to scan (defaults to this repository).",
    )
    args = parser.parse_args()
    root = args.root.resolve()

    violations = find_violations(root)
    if violations:
        print("Brand consistency check failed:")
        for violation in violations:
            location = violation.path.as_posix()
            if violation.line:
                location = f"{location}:{violation.line}"
            print(
                f"- {location}: {violation.category}"
            )
        return 1

    print("Brand consistency check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
