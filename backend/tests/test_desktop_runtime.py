from pathlib import Path

import pytest

from app.desktop_runtime import bundle_path, desktop_data_dir


def test_source_bundle_path_resolves_backend_resource():
    assert bundle_path("alembic.ini").is_file()


def test_bundle_path_rejects_path_escape():
    with pytest.raises(ValueError):
        bundle_path("../.env")


def test_desktop_data_dir_honors_explicit_user_path(monkeypatch, tmp_path: Path):
    target = tmp_path / "用户数据"
    monkeypatch.setenv("APP_DATA_DIR", str(target))
    assert desktop_data_dir() == target.resolve()
