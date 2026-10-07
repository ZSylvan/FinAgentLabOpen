from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CHECKER = (
    PROJECT_ROOT
    / "scripts"
    / "maintenance"
    / "check_brand_consistency.py"
)


def run_checker(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_rejects_legacy_product_brand_in_regular_content(
    tmp_path: Path,
) -> None:
    legacy_brand = "Trading" + "Agents"
    (tmp_path / "README.md").write_text(
        f"# FinAgentLab\n\nPreviously called {legacy_brand}.\n",
        encoding="utf-8",
    )

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert "README.md:3" in result.stdout


def test_allows_minimum_attribution_in_legal_whitelist(tmp_path: Path) -> None:
    legacy_brand = "Trading" + "Agents"
    upstream_owner = "Tauric" + "Research"
    (tmp_path / "THIRD_PARTY_NOTICES.md").write_text(
        f"{legacy_brand} copyright {upstream_owner}; Apache-2.0.\n",
        encoding="utf-8",
    )

    result = run_checker(tmp_path)

    assert result.returncode == 0
    assert "Brand consistency check passed" in result.stdout


def test_rejects_legacy_contact_and_repository_link(tmp_path: Path) -> None:
    old_email = "hs" + "liup" + "@163.com"
    old_repository = (
        "github.com/" + "Tauric" + "Research/" + "Trading" + "Agents"
    )
    (tmp_path / "help.md").write_text(
        f"Contact {old_email}; source: https://{old_repository}\n",
        encoding="utf-8",
    )

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert "help.md:1" in result.stdout


def test_rejects_legacy_brand_in_binary_asset_name(tmp_path: Path) -> None:
    legacy_brand = "Trading" + "Agents"
    asset = tmp_path / f"{legacy_brand}_paper.pdf"
    asset.write_bytes(b"%PDF-1.4\n\xff\x00")

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert asset.name in result.stdout
