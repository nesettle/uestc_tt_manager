from __future__ import annotations

from pathlib import Path

from app.domain import QualificationRecord
from app.services import jinshuju, qualification
from app.services.common import (
    compare_records,
    dedupe_form_records,
    dedupe_qualifications,
    duplicate_row_to_row,
    ensure_run_dir,
    form_record_to_compare_row,
    load_form_records_from_export,
    qualification_record_to_compare_row,
    write_csv,
    write_json,
)
from app.settings import AppConfig
from app.tasks import TaskContext


def _form_records_to_qualification(records, source_label: str) -> list[QualificationRecord]:
    results: list[QualificationRecord] = []
    for record in records:
        results.append(
            QualificationRecord(
                source=record.source,
                sheet=source_label,
                row_number=record.row_number,
                name=record.name,
                college=record.college,
                qq=record.qq,
                normalized_name=record.normalized_name,
                normalized_college=record.normalized_college,
                normalized_qq=record.normalized_qq,
            )
        )
    return results


def _write_compare_outputs(
    *,
    run_dir,
    output_csv_name: str,
    rows: list[dict[str, str]],
    matched: list[dict[str, str]],
    qualification_duplicates,
    form_duplicates,
    summary: dict,
) -> dict:
    write_csv(run_dir / output_csv_name, rows)
    write_csv(run_dir / "matched.csv", matched)
    write_csv(
        run_dir / "qualification_duplicates.csv",
        [duplicate_row_to_row(item) for item in qualification_duplicates],
    )
    write_csv(
        run_dir / "form_duplicates.csv",
        [duplicate_row_to_row(item) for item in form_duplicates],
    )
    write_json(run_dir / "summary.json", summary)
    return summary


def compare_singles_vs_qualification_form(ctx: TaskContext, config: AppConfig) -> dict:
    if not (config.qualification_form.title or config.qualification_form.entries_url):
        raise RuntimeError("请先配置资格赛报名表")
    if not (config.singles_form.title or config.singles_form.entries_url):
        raise RuntimeError("请先配置正赛单打报名表")

    run_dir = ensure_run_dir("compare-singles-qualification-form")
    qualification_export = jinshuju.export_form_snapshot(
        ctx,
        config,
        run_dir=run_dir,
        form_title=config.qualification_form.title,
        entries_url=config.qualification_form.entries_url,
        export_tag="qualification_form",
    )
    singles_export = jinshuju.export_form_snapshot(
        ctx,
        config,
        run_dir=run_dir,
        form_title=config.singles_form.title,
        entries_url=config.singles_form.entries_url,
        export_tag="singles_form",
    )

    qualification_records = load_form_records_from_export(Path(qualification_export["export_file"]))
    singles_records = load_form_records_from_export(Path(singles_export["export_file"]))
    qualification_side, qualification_duplicates = dedupe_qualifications(
        _form_records_to_qualification(qualification_records, "资格赛报名表")
    )
    singles_side, form_duplicates = dedupe_form_records(singles_records)
    matched, _, registered_not_qualified = compare_records(qualification_side, singles_side)

    reason = "报名于正赛单打，但未在资格赛报名表中找到"
    registered_rows = [form_record_to_compare_row(item, reason) for item in registered_not_qualified]
    matched_rows = []
    for item in matched:
        match_key = item["qualification_qq"] or f"{item['qualification_name']}|{item['qualification_college']}"
        matched_rows.append(
            {
                "name": item["qualification_name"],
                "college": item["qualification_college"],
                "qq": item["qualification_qq"],
                "source": item["qualification_source"],
                "match_key": match_key,
                "reason": item["match_type"],
                "form_name": item["form_name"],
                "form_college": item["form_college"],
                "form_qq": item["form_qq"],
                "form_source": item["form_source"],
            }
        )

    summary = {
        "run_dir": str(run_dir),
        "qualification_export": qualification_export["export_file"],
        "singles_export": singles_export["export_file"],
        "qualification_total": len(qualification_side),
        "singles_total": len(singles_side),
        "matched_total": len(matched_rows),
        "registered_not_in_qualification_form_total": len(registered_rows),
        "qualification_duplicates_total": len(qualification_duplicates),
        "form_duplicates_total": len(form_duplicates),
        "rows": registered_rows,
    }
    return _write_compare_outputs(
        run_dir=run_dir,
        output_csv_name="registered_singles_not_in_qualification_form.csv",
        rows=registered_rows,
        matched=matched_rows,
        qualification_duplicates=qualification_duplicates,
        form_duplicates=form_duplicates,
        summary=summary,
    )


def compare_qualified_vs_singles(ctx: TaskContext, config: AppConfig) -> dict:
    if not (config.singles_form.title or config.singles_form.entries_url):
        raise RuntimeError("请先配置正赛单打报名表")

    run_dir = ensure_run_dir("compare-qualified-singles")
    singles_export = jinshuju.export_form_snapshot(
        ctx,
        config,
        run_dir=run_dir,
        form_title=config.singles_form.title,
        entries_url=config.singles_form.entries_url,
        export_tag="singles_form",
    )
    qualification_records = qualification.load_master_as_qualification_records()
    qualification_side, qualification_duplicates = dedupe_qualifications(qualification_records)
    singles_records = load_form_records_from_export(Path(singles_export["export_file"]))
    singles_side, form_duplicates = dedupe_form_records(singles_records)
    matched, qualified_not_registered, _ = compare_records(qualification_side, singles_side)

    reason = "拥有本地正赛资格，但未在正赛单打报名表中找到"
    qualified_rows = [qualification_record_to_compare_row(item, reason) for item in qualified_not_registered]
    matched_rows = []
    for item in matched:
        match_key = item["qualification_qq"] or f"{item['qualification_name']}|{item['qualification_college']}"
        matched_rows.append(
            {
                "name": item["qualification_name"],
                "college": item["qualification_college"],
                "qq": item["qualification_qq"],
                "source": item["qualification_source"],
                "match_key": match_key,
                "reason": item["match_type"],
                "form_name": item["form_name"],
                "form_college": item["form_college"],
                "form_qq": item["form_qq"],
                "form_source": item["form_source"],
            }
        )

    summary = {
        "run_dir": str(run_dir),
        "singles_export": singles_export["export_file"],
        "qualification_total": len(qualification_side),
        "singles_total": len(singles_side),
        "matched_total": len(matched_rows),
        "qualified_not_registered_total": len(qualified_rows),
        "qualification_duplicates_total": len(qualification_duplicates),
        "form_duplicates_total": len(form_duplicates),
        "rows": qualified_rows,
    }
    return _write_compare_outputs(
        run_dir=run_dir,
        output_csv_name="qualified_not_registered_singles.csv",
        rows=qualified_rows,
        matched=matched_rows,
        qualification_duplicates=qualification_duplicates,
        form_duplicates=form_duplicates,
        summary=summary,
    )
