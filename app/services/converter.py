from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl import Workbook

from app.services.common import ensure_run_dir, write_csv, write_json
from app.settings import VENDOR_DIR
from app.tasks import TaskContext


VENDOR_SCRIPT = VENDOR_DIR / "UESTC_TT_registration_converter" / "UESTC_TT_Cup_transform.py"
CONVERTER_COLUMNS = [
    "队名或单位",
    "领队",
    "主教练",
    "组别",
    "项目(必填)",
    "种子号",
    "队内序号",
    "团体名(必填)",
    "队员(必填)",
    "团体项目",
    "性别(必填)",
    "身份证号",
    "手机",
    "队员备注",
    "附加",
]


def _load_vendor_module() -> Any:
    spec = importlib.util.spec_from_file_location("uestc_vendor_transform", VENDOR_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载转换器脚本: {VENDOR_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _project_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned = []
    for item in records:
        row = {}
        for key in CONVERTER_COLUMNS:
            row[key] = item.get(key) or item.get(key + ":") or ""
        cleaned.append(row)
    return cleaned


def _write_multi_sheet_workbook(path: Path, sheets: dict[str, list[dict[str, Any]]]) -> None:
    workbook = Workbook()
    first_sheet = workbook.active
    first_sheet.title = list(sheets.keys())[0]
    for sheet_name, rows in sheets.items():
        sheet = first_sheet if sheet_name == first_sheet.title else workbook.create_sheet(title=sheet_name)
        sheet.append(CONVERTER_COLUMNS)
        for row in rows:
            sheet.append([row.get(column, "") for column in CONVERTER_COLUMNS])
    workbook.save(path)


def _build_duplicate_groups(
    dup_names: dict[str, list[int]],
    dup_subs: dict[str, list[int]],
    dup_pairs: dict[Any, list[int]],
) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for name, indices in dup_names.items():
        groups.append(
            {
                "group_id": f"singles-name::{name}",
                "sheet": "单打",
                "label": f"单打同名：{name}",
                "type": "singles_duplicate_name",
                "occurrences": [[idx] for idx in indices],
                "keep_rule": "保留第一条",
            }
        )
    for name, indices in dup_subs.items():
        groups.append(
            {
                "group_id": f"singles-submission::{name}",
                "sheet": "单打",
                "label": f"单打重复提交：{name}",
                "type": "singles_duplicate_submission",
                "occurrences": [[idx] for idx in indices],
                "keep_rule": "保留第一条",
            }
        )
    for combo_key, row_indices in dup_pairs.items():
        sorted_indices = sorted(row_indices)
        occurrences = [sorted_indices[i : i + 2] for i in range(0, len(sorted_indices), 2)]
        project, p1, p2 = combo_key
        groups.append(
            {
                "group_id": f"doubles::{project}::{p1}::{p2}",
                "sheet": "双打",
                "label": f"双打重复组合：{project} {p1}/{p2}",
                "type": "doubles_duplicate_pair",
                "occurrences": occurrences,
                "keep_rule": "保留第一组",
            }
        )
    return groups


def _stage_uploaded_files(run_dir: Path, uploaded_files: dict[str, dict[str, Any]] | None) -> dict[str, str]:
    resolved: dict[str, str] = {}
    if not uploaded_files:
        return resolved
    upload_dir = run_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    for key, meta in uploaded_files.items():
        filename = str(meta.get("filename", "")).strip() or f"{key}.xlsx"
        content = meta.get("content", b"")
        target = upload_dir / filename
        target.write_bytes(content)
        resolved[key] = str(target)
    return resolved


def prepare_conversion(
    ctx: TaskContext,
    singles_file: str,
    doubles_file: str,
    team_file: str,
    uploaded_files: dict[str, dict[str, Any]] | None = None,
) -> dict:
    if not any([singles_file, doubles_file, team_file, uploaded_files]):
        raise RuntimeError("请至少提供一个报名文件路径或上传文件")

    run_dir = ensure_run_dir("converter")
    staged_files = _stage_uploaded_files(run_dir, uploaded_files)
    singles_path = staged_files.get("singles_file", singles_file)
    doubles_path = staged_files.get("doubles_file", doubles_file)
    team_path = staged_files.get("team_file", team_file)

    module = _load_vendor_module()
    singles_records = []
    dup_names = {}
    dup_subs = {}
    doubles_records = []
    dup_pairs = {}
    team_records = []

    if singles_path:
        ctx.set_message("处理单打报名表")
        singles_records, dup_names, dup_subs = module.process_singles(pd.read_excel(singles_path))
    if doubles_path:
        ctx.set_message("处理双打报名表")
        doubles_records, dup_pairs = module.process_doubles(pd.read_excel(doubles_path))
    if team_path:
        ctx.set_message("处理团体报名表")
        team_records = module.process_team(pd.read_excel(team_path))

    sheets = {
        "单打": _project_rows(singles_records),
        "双打": _project_rows(doubles_records),
        "团体": _project_rows(team_records),
    }
    sheet_output = run_dir / "sheet_output.xlsx"
    _write_multi_sheet_workbook(sheet_output, sheets)

    duplicate_groups = _build_duplicate_groups(dup_names, dup_subs, dup_pairs)
    duplicate_review_rows = [
        {
            "group_id": group["group_id"],
            "sheet": group["sheet"],
            "label": group["label"],
            "type": group["type"],
            "occurrence_count": len(group["occurrences"]),
            "keep_rule": group["keep_rule"],
        }
        for group in duplicate_groups
    ]
    write_csv(run_dir / "duplicate_review.csv", duplicate_review_rows)

    duplicate_summary = {
        "run_dir": str(run_dir),
        "sheet_output": str(sheet_output),
        "group_count": len(duplicate_groups),
        "groups": duplicate_groups,
    }
    write_json(run_dir / "duplicate_summary.json", duplicate_summary)

    session_payload = {
        "run_dir": str(run_dir),
        "source_files": {"singles": singles_path, "doubles": doubles_path, "team": team_path},
        "sheet_output": str(sheet_output),
        "sheets": sheets,
        "duplicate_groups": duplicate_groups,
    }
    write_json(run_dir / "converter_session.json", session_payload)

    summary = {
        "run_dir": str(run_dir),
        "sheet_output": str(sheet_output),
        "duplicate_review_file": str(run_dir / "duplicate_review.csv"),
        "duplicate_summary_file": str(run_dir / "duplicate_summary.json"),
        "duplicate_groups": duplicate_groups,
        "singles_rows": len(sheets["单打"]),
        "doubles_rows": len(sheets["双打"]),
        "team_rows": len(sheets["团体"]),
    }
    write_json(run_dir / "summary.json", summary)
    return summary


def confirm_dedupe(ctx: TaskContext, run_dir: str) -> dict:
    run_path = Path(run_dir)
    session_path = run_path / "converter_session.json"
    if not session_path.exists():
        raise RuntimeError("未找到转换会话，请先执行查重预处理")
    session = json.loads(session_path.read_text(encoding="utf-8"))
    sheets: dict[str, list[dict[str, Any]]] = session["sheets"]
    duplicate_groups: list[dict[str, Any]] = session["duplicate_groups"]

    to_remove: dict[str, set[int]] = {"单打": set(), "双打": set(), "团体": set()}
    total_groups = len(duplicate_groups)
    for index, group in enumerate(duplicate_groups, start=1):
        ctx.set_progress(index, total_groups or 1, f"删重处理：{group['label']}")
        for occurrence in group["occurrences"][1:]:
            for row_index in occurrence:
                to_remove[group["sheet"]].add(row_index)

    deduped_sheets: dict[str, list[dict[str, Any]]] = {}
    for sheet_name, rows in sheets.items():
        deduped_sheets[sheet_name] = [
            row for idx, row in enumerate(rows) if idx not in to_remove.get(sheet_name, set())
        ]

    preview_path = run_path / "upload_preview.xlsx"
    final_path = run_path / "优赛上传表.xlsx"
    _write_multi_sheet_workbook(preview_path, sheets)
    _write_multi_sheet_workbook(final_path, deduped_sheets)

    summary = {
        "run_dir": str(run_path),
        "sheet_output": session["sheet_output"],
        "preview_file": str(preview_path),
        "final_file": str(final_path),
        "removed_counts": {sheet: len(indices) for sheet, indices in to_remove.items()},
        "remaining_counts": {sheet: len(rows) for sheet, rows in deduped_sheets.items()},
    }
    write_json(run_path / "summary.json", summary)
    return summary
