from __future__ import annotations

from sbfp_platform.privacy.pii_scanner import scan


def test_scanner_finds_identifier_like_values(tmp_path) -> None:
    (tmp_path / "unexpected.csv").write_text("name,lrn\nPerson,123456789012\n", encoding="utf-8")
    assert any("12-digit" in finding for finding in scan(tmp_path))


def test_scanner_ignores_generated_raw_folder(tmp_path) -> None:
    folder = tmp_path / "synthetic_raw"
    folder.mkdir()
    (folder / "submission.csv").write_text("lrn\n123456789012\n", encoding="utf-8")
    assert scan(tmp_path) == []


def test_scanner_checks_public_outputs_and_email_addresses(tmp_path) -> None:
    folder = tmp_path / "outputs" / "exports"
    folder.mkdir(parents=True)
    (folder / "public.csv").write_text("contact\nperson@example.org\n", encoding="utf-8")
    assert any("email address" in finding for finding in scan(tmp_path))


def test_scanner_ignores_gitignored_local_session_exports(tmp_path) -> None:
    (tmp_path / "2026-01-01-users-local.txt").write_text("account@example.org", encoding="utf-8")
    assert scan(tmp_path) == []
