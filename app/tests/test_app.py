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


def test_qualification_export_returns_xlsx():
    client = TestClient(app)
    response = client.get("/api/qualification/export")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
