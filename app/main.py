from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.services import compare, converter, jinshuju, notify, qualification
from app.settings import AppConfig, DiscoveredForm, FORM_EXPORTS_DIR, TEMPLATES_DIR, load_config, save_config
from app.services.common import ensure_run_dir
from app.tasks import task_manager


app = FastAPI(title="UESTC TT Manager")
app.mount("/static", StaticFiles(directory=str(Path(__file__).resolve().parent / "static")), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _config_from_request(payload: dict[str, Any]) -> AppConfig:
    current = load_config().to_dict()
    current.update(payload)
    return AppConfig.from_dict(current)


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html", {"config": load_config().to_dict()})


@app.get("/api/config")
def get_config() -> JSONResponse:
    return JSONResponse(load_config().to_dict())


@app.post("/api/config")
async def update_config(request: Request) -> JSONResponse:
    payload = await request.json()
    config = _config_from_request(payload)
    save_config(config)
    return JSONResponse(config.to_dict())


@app.get("/api/qualification/current")
def qualification_current() -> JSONResponse:
    return JSONResponse(qualification.current_master_preview())


@app.get("/api/qualification/export")
def qualification_export() -> FileResponse:
    export_file = qualification.export_master_file()
    return FileResponse(
        path=str(export_file),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="qualification_master.xlsx",
    )


@app.post("/api/jinshuju/session/check")
async def check_jinshuju_session(request: Request) -> JSONResponse:
    payload = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    config = _config_from_request(payload or {})
    state = task_manager.submit("jinshuju_session_check", jinshuju.check_session, config)
    return JSONResponse({"task_id": state.id})


@app.post("/api/jinshuju/forms/discover")
async def discover_jinshuju_forms(request: Request) -> JSONResponse:
    payload = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    config = _config_from_request(payload or {})

    def run(ctx, cfg: AppConfig):
        forms = jinshuju.discover_forms(ctx, cfg)
        cfg.discovered_forms = [DiscoveredForm(**item) for item in forms]
        save_config(cfg)
        return {"forms": forms}

    state = task_manager.submit("jinshuju_forms_discover", run, config)
    return JSONResponse({"task_id": state.id})


@app.post("/api/jinshuju/forms/export")
async def export_jinshuju_form(request: Request) -> JSONResponse:
    payload = await request.json()
    config = load_config()
    binding_name = str(payload.get("binding", "")).strip()
    form_title = str(payload.get("form_title", "")).strip()
    entries_url = str(payload.get("entries_url", "")).strip()
    download_format = str(payload.get("download_format", "xlsx")).strip() or "xlsx"

    if binding_name:
        binding = getattr(config, binding_name, None)
        if binding is None:
            raise HTTPException(status_code=400, detail="未知的表单绑定名称")
        form_title = form_title or binding.title
        entries_url = entries_url or binding.entries_url
    if not form_title and not entries_url:
        raise HTTPException(status_code=400, detail="缺少 form_title 或 entries_url")

    run_dir = ensure_run_dir("jinshuju-export")
    state = task_manager.submit(
        "jinshuju_forms_export",
        jinshuju.export_form_snapshot,
        config,
        form_title=form_title,
        entries_url=entries_url,
        download_format=download_format,
        run_dir=run_dir,
        export_tag=binding_name or "manual_export",
    )
    return JSONResponse({"task_id": state.id})


@app.get("/api/jinshuju/form-exports-dir")
def get_jinshuju_form_exports_dir() -> JSONResponse:
    FORM_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return JSONResponse({"path": str(FORM_EXPORTS_DIR)})


@app.post("/api/jinshuju/form-exports/open")
def open_jinshuju_form_exports_dir() -> JSONResponse:
    FORM_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(["explorer.exe", str(FORM_EXPORTS_DIR)])
    return JSONResponse({"path": str(FORM_EXPORTS_DIR), "opened": True})


@app.post("/api/qualification/resolve")
async def qualification_resolve(request: Request) -> JSONResponse:
    payload = await request.json()
    config = _config_from_request(payload)
    state = task_manager.submit(
        "qualification_resolve",
        qualification.resolve_names,
        config,
        str(payload.get("names", "")),
    )
    return JSONResponse({"task_id": state.id})


@app.post("/api/qualification/apply")
async def qualification_apply(request: Request) -> JSONResponse:
    payload = await request.json()
    state = task_manager.submit(
        "qualification_apply",
        qualification.apply_updates,
        load_config(),
        payload.get("selections") or [],
    )
    return JSONResponse({"task_id": state.id})


@app.post("/api/qualification/delete")
async def qualification_delete(request: Request) -> JSONResponse:
    payload = await request.json()
    state = task_manager.submit(
        "qualification_delete",
        qualification.delete_rows,
        payload.get("rows") or [],
    )
    return JSONResponse({"task_id": state.id})


@app.post("/api/compare/singles-vs-qualification-form")
async def compare_singles_qualification_form(request: Request) -> JSONResponse:
    payload = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    config = _config_from_request(payload or {})
    state = task_manager.submit(
        "compare_singles_vs_qualification_form",
        compare.compare_singles_vs_qualification_form,
        config,
    )
    return JSONResponse({"task_id": state.id})


@app.post("/api/compare/qualified-vs-singles")
async def compare_qualified_singles(request: Request) -> JSONResponse:
    payload = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    config = _config_from_request(payload or {})
    state = task_manager.submit(
        "compare_qualified_vs_singles",
        compare.compare_qualified_vs_singles,
        config,
    )
    return JSONResponse({"task_id": state.id})


@app.post("/api/notify/precheck")
async def notify_precheck(request: Request) -> JSONResponse:
    payload = await request.json()
    state = task_manager.submit("notify_precheck", notify.precheck, load_config(), payload.get("rows") or [])
    return JSONResponse({"task_id": state.id})


@app.post("/api/notify/send")
async def notify_send(request: Request) -> JSONResponse:
    payload = await request.json()
    state = task_manager.submit("notify_send", notify.send, load_config(), payload.get("rows") or [])
    return JSONResponse({"task_id": state.id})


@app.post("/api/converter/prepare")
async def converter_prepare(
    request: Request,
    singles_upload: UploadFile | None = File(default=None),
    doubles_upload: UploadFile | None = File(default=None),
    team_upload: UploadFile | None = File(default=None),
    singles_file: str = Form(default=""),
    doubles_file: str = Form(default=""),
    team_file: str = Form(default=""),
) -> JSONResponse:
    uploaded_files = None
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        payload = await request.json()
        singles_file = str(payload.get("singles_file", "")).strip()
        doubles_file = str(payload.get("doubles_file", "")).strip()
        team_file = str(payload.get("team_file", "")).strip()
    else:
        uploaded_files = {}
        for key, upload in (
            ("singles_file", singles_upload),
            ("doubles_file", doubles_upload),
            ("team_file", team_upload),
        ):
            if upload is not None and upload.filename:
                uploaded_files[key] = {
                    "filename": upload.filename,
                    "content": await upload.read(),
                }
        if not uploaded_files:
            uploaded_files = None

    state = task_manager.submit(
        "converter_prepare",
        converter.prepare_conversion,
        str(singles_file).strip(),
        str(doubles_file).strip(),
        str(team_file).strip(),
        uploaded_files,
    )
    return JSONResponse({"task_id": state.id})


@app.post("/api/converter/confirm-dedupe")
async def converter_confirm(request: Request) -> JSONResponse:
    payload = await request.json()
    run_dir = str(payload.get("run_dir", "")).strip()
    if not run_dir:
        raise HTTPException(status_code=400, detail="缺少 run_dir")
    state = task_manager.submit("converter_confirm_dedupe", converter.confirm_dedupe, run_dir)
    return JSONResponse({"task_id": state.id})


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str) -> JSONResponse:
    state = task_manager.get(task_id)
    if state is None:
        raise HTTPException(status_code=404, detail="task not found")
    return JSONResponse(state.to_dict())
