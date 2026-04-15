from fastapi.testclient import TestClient

from app.main import app


class DummyState:
    def __init__(self, task_id: str = "task-123") -> None:
        self.id = task_id


def test_index_page_renders():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "成电杯报名数据管理系统" in response.text
    assert "首次启动说明" in response.text


def test_export_route_returns_task_id(monkeypatch):
    client = TestClient(app)

    def fake_submit(*args, **kwargs):
        return DummyState("export-task")

    monkeypatch.setattr("app.main.task_manager.submit", fake_submit)
    response = client.post(
        "/api/jinshuju/forms/export",
        json={"form_title": "测试表单"},
    )
    assert response.status_code == 200
    assert response.json()["task_id"] == "export-task"


def test_form_exports_dir_route_returns_path():
    client = TestClient(app)
    response = client.get("/api/jinshuju/form-exports-dir")
    assert response.status_code == 200
    assert response.json()["path"].endswith("data\\form_exports")


def test_open_form_exports_dir_opens_explorer(monkeypatch):
    client = TestClient(app)
    captured = {}

    def fake_popen(args):
        captured["args"] = args
        return None

    monkeypatch.setattr("app.main.subprocess.Popen", fake_popen)
    response = client.post("/api/jinshuju/form-exports/open")
    assert response.status_code == 200
    assert response.json()["opened"] is True
    assert captured["args"][0].lower() == "explorer.exe"
    assert str(captured["args"][1]).endswith("data\\form_exports")


def test_runtime_paths_route_returns_summary(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        "app.main.runtime_summary",
        lambda: {"desktop_mode": False, "frozen": False, "paths": {"user_data_root": r"C:\demo"}},
    )
    response = client.get("/api/runtime/paths")
    assert response.status_code == 200
    assert response.json()["paths"]["user_data_root"] == r"C:\demo"


def test_runtime_check_route_includes_napcat(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        "app.main.runtime_summary",
        lambda: {"desktop_mode": True, "frozen": False, "paths": {"user_data_root": r"C:\demo"}},
    )
    monkeypatch.setattr(
        "app.main.notify.system_check",
        lambda config: {"connected": False, "message": "尚未配置"},
    )
    response = client.get("/api/runtime/check")
    assert response.status_code == 200
    assert response.json()["napcat"]["message"] == "尚未配置"


def test_open_data_dir_calls_explorer(monkeypatch):
    client = TestClient(app)
    captured = {}

    def fake_open(path):
        captured["path"] = str(path)

    class DummyPaths:
        user_data_root = r"C:\demo-data"

    monkeypatch.setattr("app.main.explorer_open", fake_open)
    monkeypatch.setattr("app.main.get_runtime_paths", lambda: DummyPaths())
    response = client.post("/api/runtime/open-data-dir")
    assert response.status_code == 200
    assert response.json()["path"] == r"C:\demo-data"
    assert captured["path"] == r"C:\demo-data"


def test_open_runs_dir_calls_explorer(monkeypatch):
    client = TestClient(app)
    captured = {}

    def fake_open(path):
        captured["path"] = str(path)

    monkeypatch.setattr("app.main.explorer_open", fake_open)
    response = client.post("/api/runtime/open-runs-dir")
    assert response.status_code == 200
    assert captured["path"].endswith("runs")


def test_converter_prepare_accepts_json(monkeypatch):
    client = TestClient(app)

    def fake_submit(*args, **kwargs):
        return DummyState("converter-task")

    monkeypatch.setattr("app.main.task_manager.submit", fake_submit)
    response = client.post(
        "/api/converter/prepare",
        json={"singles_file": r"C:\fake.xlsx"},
    )
    assert response.status_code == 200
    assert response.json()["task_id"] == "converter-task"


def test_qualification_resolve_uses_request_binding(monkeypatch):
    client = TestClient(app)
    captured = {}

    def fake_submit(kind, func, config, names):
        captured["kind"] = kind
        captured["config"] = config
        captured["names"] = names
        return DummyState("resolve-task")

    monkeypatch.setattr("app.main.task_manager.submit", fake_submit)
    response = client.post(
        "/api/qualification/resolve",
        json={
            "names": "张三",
            "qualification_form": {
                "title": "资格赛报名表",
                "entries_url": "https://jinshuju.net/forms/demo/entries",
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["task_id"] == "resolve-task"
    assert captured["config"].qualification_form.title == "资格赛报名表"
    assert captured["config"].qualification_form.entries_url == "https://jinshuju.net/forms/demo/entries"
    assert captured["names"] == "张三"


def test_qualification_delete_submits_rows(monkeypatch):
    client = TestClient(app)
    captured = {}

    def fake_submit(kind, func, rows):
        captured["kind"] = kind
        captured["rows"] = rows
        return DummyState("delete-task")

    monkeypatch.setattr("app.main.task_manager.submit", fake_submit)
    response = client.post(
        "/api/qualification/delete",
        json={"rows": [{"row_number": 2}, {"row_number": 5}]},
    )
    assert response.status_code == 200
    assert response.json()["task_id"] == "delete-task"
    assert captured["kind"] == "qualification_delete"
    assert captured["rows"] == [{"row_number": 2}, {"row_number": 5}]


def test_qualification_export_returns_xlsx():
    client = TestClient(app)
    response = client.get("/api/qualification/export")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
