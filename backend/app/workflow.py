"""Draft validation, audit records and final snapshot exports."""

import csv
import hashlib
import io
import json
import shutil
import uuid
import zipfile
from pathlib import Path
from types import SimpleNamespace
from fastapi import HTTPException
from sqlalchemy import select
from .db import STORAGE
from .models import Event, Expense, Receipt, Link, Category, FinalVersion, ChangeLog
from .excel import export_excel

FINAL = "최종 확정"


def editable(db, event_id):
    e = db.get(Event, event_id)
    if e and e.status == FINAL:
        raise HTTPException(409, "확정본은 잠겨 있습니다. 수정 재오픈 후 편집하세요.")
    return e


def audit(db, event_id, field, old, new, expense_id=None, source="user"):
    if old == new:
        return
    db.add(
        ChangeLog(
            event_id=event_id,
            expense_id=expense_id,
            field_name=field,
            old_value=json.dumps(old, ensure_ascii=False),
            new_value=json.dumps(new, ensure_ascii=False),
            change_source=source,
        )
    )


def check(db, e):
    errors = []
    warnings = []
    xs = list(db.scalars(select(Expense).where(Expense.event_id == e.id)))
    rs = list(db.scalars(select(Receipt).where(Receipt.event_id == e.id)))
    links = list(db.scalars(select(Link).join(Expense).where(Expense.event_id == e.id)))
    if not e.event_date:
        errors.append("행사 날짜를 입력하세요.")
    if not xs:
        errors.append("지출 행이 없습니다.")
    for i, x in enumerate(sorted(xs, key=lambda x: (x.sort_order, x.id)), 1):
        if (
            not x.expense_date
            or x.amount_krw is None
            or not x.item_name.strip()
            or not x.category_id
        ):
            errors.append(f"{i}행: 지출일·항목·품목·금액 필수값을 입력하세요.")
        if x.review_status != "확인됨":
            errors.append(f"{i}행: 지출 검토 완료를 확인하세요.")
        attached = [l for l in links if l.expense_id == x.id]
        if not attached:
            warnings.append(f"{i}행: 영수증 미첨부" + (f" ({x.note})" if x.note else ""))
        elif any(l.allocated_amount_krw is None for l in attached):
            errors.append(f"{i}행: 영수증 배분금액을 입력하세요.")
        elif sum(l.allocated_amount_krw for l in attached) != (x.amount_krw or 0):
            warnings.append(
                f"{i}행: 지출과 영수증 배분액 차이" + (f" ({x.note})" if x.note else "")
            )
    for r in rs:
        if r.ocr_status == "제외":
            continue
        if r.ocr_status != "확인됨":
            errors.append(f"{r.original_name}: 영수증 검토를 완료하세요.")
        elif not r.transaction_at or len(r.transaction_at) < 16 or r.final_amount_krw is None:
            warnings.append(f"{r.original_name}: 일시 또는 금액 불명, ZIP 검토 폴더에 포함")
    return {
        "errors": errors,
        "warnings": warnings,
        "expense_count": len(xs),
        "total_krw": sum(x.amount_krw or 0 for x in xs),
        "version": e.version,
        "can_finalize": not errors,
    }


def version_row(db, e, version=None):
    number = version or e.latest_final_version
    row = db.scalar(
        select(FinalVersion).where(FinalVersion.event_id == e.id, FinalVersion.version_no == number)
    )
    if not row:
        raise HTTPException(404, "확정 버전을 찾을 수 없습니다.")
    return row


def snapshot_excel(snapshot):
    obj = lambda x: SimpleNamespace(**x)
    e = obj(snapshot)
    e.status = f'최종 확정 v{snapshot["final_version"]}'
    return export_excel(
        e,
        list(map(obj, snapshot["categories"])),
        list(map(obj, snapshot["expenses"])),
        list(map(obj, snapshot["receipts"])),
        list(map(obj, snapshot["links"])),
    )


def receipt_archive(snapshot):
    rs = sorted(
        snapshot["receipts"],
        key=lambda r: ((r["transaction_at"] or "9999"), r["original_name"], r["id"]),
    )
    out = io.BytesIO()
    summary = io.StringIO()
    writer = csv.writer(summary)
    writer.writerow(["순번", "원본명", "거래일시", "최종금액", "검토상태", "ZIP경로"])
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for i, r in enumerate(rs, 1):
            known = (
                r["transaction_at"]
                and len(r["transaction_at"]) >= 16
                and r["final_amount_krw"] is not None
            )
            folder = (
                "excluded"
                if r["ocr_status"] == "제외"
                else "receipts" if known else "review_required"
            )
            amount = str(r["final_amount_krw"]) if r["final_amount_krw"] is not None else "unknown"
            name = f'{folder}/{i}_{amount}{Path(r["stored_path"]).suffix}'
            p = STORAGE / r["stored_path"]
            if not p.is_file():
                raise HTTPException(409, "보관된 원본 파일이 없습니다. 백업 상태를 확인하세요.")
            if hashlib.sha256(p.read_bytes()).hexdigest() != r["sha256"]:
                raise HTTPException(409, "영수증 원본 해시가 일치하지 않습니다.")
            archive.write(p, name)
            # CSV text cells are escaped to avoid spreadsheet formula interpretation.
            safe = lambda value: (
                "'" + str(value) if str(value).startswith(("=", "+", "-", "@")) else value
            )
            writer.writerow(
                [
                    i,
                    safe(r["original_name"]),
                    r["transaction_at"],
                    r["final_amount_krw"],
                    r["ocr_status"],
                    name,
                ]
            )
        archive.writestr("receipts_summary.csv", "\ufeff" + summary.getvalue())
    return out.getvalue()
