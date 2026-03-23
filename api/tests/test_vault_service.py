# api/tests/test_vault_service.py
"""
Unit tests for LocalVaultService — local filesystem vault backend.

All tests use tmp_path for full isolation; settings.local_storage_path is
monkeypatched at the module level so no real storage is ever touched.
"""

import pytest

import app.services.vault_service as vault_module
from app.services.vault_service import ALLOWED_DIRECTORIES, LocalVaultService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def service(tmp_path, monkeypatch):
    """Return a LocalVaultService wired to tmp_path with tenant 'test-tenant'."""
    monkeypatch.setattr(vault_module.settings, "local_storage_path", str(tmp_path))
    return LocalVaultService("test-tenant")


# ---------------------------------------------------------------------------
# 1. Write then read — content round-trips correctly
# ---------------------------------------------------------------------------


def test_write_and_read_file(service):
    path = "01-Clients/client-alpha/profile.md"
    content = "# Client Alpha\n\nDiagnosis: ASD Level 2\n"

    service.write_file(path, content)
    result = service.read_file(path)

    assert result == content


# ---------------------------------------------------------------------------
# 2. Read a file that has never been written returns None
# ---------------------------------------------------------------------------


def test_read_nonexistent_returns_none(service):
    result = service.read_file("01-Clients/nobody/missing.md")
    assert result is None


# ---------------------------------------------------------------------------
# 3. Writing to a directory outside ALLOWED_DIRECTORIES raises ValueError
# ---------------------------------------------------------------------------


def test_write_invalid_directory_rejected(service):
    with pytest.raises(ValueError, match="outside the allowed directory tree"):
        service.write_file("invalid-dir/file.md", "bad content")


def test_write_root_level_path_rejected(service):
    """A path with no directory component is also outside allowed dirs."""
    with pytest.raises(ValueError):
        service.write_file("loose-file.md", "bad content")


def test_write_traversal_attempt_rejected(service):
    """Paths that look like traversal should be rejected by the top-level check."""
    with pytest.raises(ValueError):
        service.write_file("../escape/file.md", "bad content")


# ---------------------------------------------------------------------------
# 4. append_file on a non-existent file creates it with the skeleton header
# ---------------------------------------------------------------------------


def test_append_creates_file_with_skeleton(service):
    path = "02-Sessions/2026-01/session-log.md"
    appended = "Target: manding\nTrials: 10/10\n"

    service.append_file(path, appended)
    result = service.read_file(path)

    assert result is not None
    # Skeleton header must use the bare filename without extension
    assert result.startswith("# session-log\n\n")
    # Appended content must appear after the header
    assert "Target: manding" in result
    assert "Trials: 10/10" in result


def test_append_creates_file_exists_afterward(service):
    path = "04-Supervision/2026-Q1/notes.md"
    service.append_file(path, "First entry")
    assert service.file_exists(path) is True


# ---------------------------------------------------------------------------
# 5. append_file on an existing file adds content without overwriting
# ---------------------------------------------------------------------------


def test_append_to_existing_file(service):
    path = "02-Sessions/2026-01/running-log.md"
    initial = "# running-log\n\nFirst session note.\n"
    service.write_file(path, initial)

    service.append_file(path, "Second session note.")
    result = service.read_file(path)

    assert "First session note." in result
    assert "Second session note." in result


def test_append_preserves_all_previous_content(service):
    path = "02-Sessions/2026-01/multi.md"
    service.write_file(path, "# multi\n\nLine A.\n")
    service.append_file(path, "Line B.")
    service.append_file(path, "Line C.")

    result = service.read_file(path)
    assert "Line A." in result
    assert "Line B." in result
    assert "Line C." in result


# ---------------------------------------------------------------------------
# 6. file_exists — false before write, true after
# ---------------------------------------------------------------------------


def test_file_exists_false_before_write(service):
    assert service.file_exists("01-Clients/ghost/profile.md") is False


def test_file_exists_true_after_write(service):
    path = "01-Clients/real/profile.md"
    service.write_file(path, "exists now")
    assert service.file_exists(path) is True


def test_file_exists_returns_bool_type(service):
    result = service.file_exists("01-Clients/missing.md")
    assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# 7. list_directory — returns names of items created inside it
# ---------------------------------------------------------------------------


def test_list_directory_returns_created_files(service):
    service.write_file("03-Staff/alice.md", "Alice")
    service.write_file("03-Staff/bob.md", "Bob")

    items = service.list_directory("03-Staff")

    assert "alice.md" in items
    assert "bob.md" in items


def test_list_directory_empty_for_missing_path(service):
    result = service.list_directory("03-Staff/no-such-dir")
    assert result == []


def test_list_directory_does_not_include_sibling_dirs(service):
    service.write_file("03-Staff/hr/alice.md", "Alice")
    service.write_file("03-Staff/hr/bob.md", "Bob")

    items = service.list_directory("03-Staff/hr")
    assert set(items) == {"alice.md", "bob.md"}


# ---------------------------------------------------------------------------
# 8. upload_raw_file / read_raw_file — bytes round-trip correctly
# ---------------------------------------------------------------------------


def test_upload_and_read_raw_file(service):
    raw = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32  # fake PNG header
    upload_path = "session-2026-01-15.png"

    service.upload_raw_file(upload_path, raw, "image/png")
    result = service.read_raw_file(upload_path)

    assert result == raw


def test_upload_raw_file_is_stored_under_uploads(service, tmp_path):
    raw = b"raw csv data"
    service.upload_raw_file("data.csv", raw, "text/csv")

    uploads_file = (
        tmp_path / "tenants" / "test-tenant" / "uploads" / "data.csv"
    )
    assert uploads_file.exists()
    assert uploads_file.read_bytes() == raw


def test_upload_empty_bytes(service):
    service.upload_raw_file("empty.bin", b"", "application/octet-stream")
    assert service.read_raw_file("empty.bin") == b""


def test_upload_large_bytes(service):
    large = b"x" * (1024 * 1024)  # 1 MB
    service.upload_raw_file("big.bin", large, "application/octet-stream")
    assert service.read_raw_file("big.bin") == large


# ---------------------------------------------------------------------------
# 9. write_file works for every one of the 7 ALLOWED_DIRECTORIES
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("top_dir", sorted(ALLOWED_DIRECTORIES))
def test_write_to_each_allowed_directory(service, top_dir):
    path = f"{top_dir}/test-file.md"
    content = f"Content inside {top_dir}"

    service.write_file(path, content)
    assert service.read_file(path) == content


# ---------------------------------------------------------------------------
# Additional edge-case tests
# ---------------------------------------------------------------------------


def test_write_overwrites_existing_content(service):
    path = "01-Clients/overwrite-me.md"
    service.write_file(path, "original content")
    service.write_file(path, "replacement content")
    assert service.read_file(path) == "replacement content"


def test_write_creates_nested_directories(service, tmp_path):
    deep_path = "01-Clients/a/b/c/deep.md"
    service.write_file(deep_path, "deep content")

    expected = (
        tmp_path / "tenants" / "test-tenant" / "vault"
        / "01-Clients" / "a" / "b" / "c" / "deep.md"
    )
    assert expected.exists()


def test_tenant_isolation(tmp_path, monkeypatch):
    """Two services with different tenant_ids must not share files."""
    monkeypatch.setattr(vault_module.settings, "local_storage_path", str(tmp_path))

    svc_a = LocalVaultService("tenant-a")
    svc_b = LocalVaultService("tenant-b")

    svc_a.write_file("01-Clients/shared-name.md", "Tenant A content")

    # Tenant B must not see tenant A's file
    assert svc_b.read_file("01-Clients/shared-name.md") is None
    assert svc_b.file_exists("01-Clients/shared-name.md") is False


def test_write_unicode_content(service):
    path = "05-Communication/家长信.md"
    content = "亲爱的家长：\n\n孩子今天表现很棒！\U0001F600\n"

    service.write_file(path, content)
    assert service.read_file(path) == content


def test_write_and_read_empty_string(service):
    path = "06-Templates/empty.md"
    service.write_file(path, "")
    assert service.read_file(path) == ""


def test_append_skeleton_uses_filename_without_extension(service):
    """The skeleton header must strip the .md extension from the filename."""
    service.append_file("04-Supervision/weekly-review.md", "Some content")
    result = service.read_file("04-Supervision/weekly-review.md")
    assert "# weekly-review\n" in result
    assert "# weekly-review.md" not in result


def test_base_path_structure(service, tmp_path):
    """Vault files must be stored under {tmp_path}/tenants/{tenant_id}/vault/."""
    service.write_file("01-Clients/proof.md", "proof")
    expected = tmp_path / "tenants" / "test-tenant" / "vault" / "01-Clients" / "proof.md"
    assert expected.exists()
