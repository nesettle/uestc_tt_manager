from app.runtime import (
    DEFAULT_APPDATA_SUBDIR,
    USER_DATA_ENV,
    detect_webview2_version,
    get_runtime_paths,
    reset_runtime_paths_cache,
)


def test_runtime_paths_use_override(monkeypatch, tmp_path):
    monkeypatch.setenv(USER_DATA_ENV, str(tmp_path / "desktop-data"))
    reset_runtime_paths_cache()
    paths = get_runtime_paths()
    assert str(paths.user_data_root).endswith("desktop-data")
    assert paths.data_dir == paths.user_data_root / "data"
    assert paths.runs_dir == paths.user_data_root / "runs"
    reset_runtime_paths_cache()


def test_detect_webview2_returns_string():
    version = detect_webview2_version()
    assert isinstance(version, str)


def test_runtime_paths_default_subdir_name_present():
    assert DEFAULT_APPDATA_SUBDIR == "UESTC TT Manager"
