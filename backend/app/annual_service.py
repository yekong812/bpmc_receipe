"""Annual scopes share receipt/version services through an explicit owned Event FK.
The discriminated annual book and all entry/budget references are validated on every write.
"""

import json
from datetime import date as Date
from fastapi import HTTPException
from sqlalchemy import null, select
from .models import (
    AnnualBook,
    AnnualEntry,
    BudgetItem,
    Event,
    Expense,
    Category,
    Receipt,
    Link,
    FinalVersion,
    now,
)
from .workflow import audit

LABEL = {"ordinary": "경상비", "b": "B"}


def encode(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def get_book(db, kind, book_id):
    book = db.get(AnnualBook, book_id)
    if not book or book.kind != kind:
        raise HTTPException(404, "해당 메뉴의 연도별 장부를 찾을 수 없습니다.")
    return book


def by_event(db, event_id):
    return db.scalar(select(AnnualBook).where(AnnualBook.owner_event_id == event_id))


def budget_rows(db, book):
    return list(
        db.scalars(
            select(BudgetItem)
            .where(BudgetItem.book_id == book.id)
            .order_by(BudgetItem.sort_order, BudgetItem.id)
        )
    )


def entries(db, book):
    return list(
        db.scalars(
            select(AnnualEntry)
            .where(AnnualEntry.book_id == book.id)
            .order_by(
                AnnualEntry.transaction_date.is_(None),
                AnnualEntry.transaction_date,
                AnnualEntry.sort_order,
                AnnualEntry.id,
            )
        )
    )


def budget_path(item, items):
    lookup = {i.id: i for i in items}
    parts = [item.name]
    parent = item.parent_id
    while parent:
        p = lookup.get(parent)
        if not p:
            break
        parts.insert(0, p.name)
        parent = p.parent_id
    return " / ".join(parts)


def sync_budget_category(db, event, item, path):
    category = db.get(Category, item.category_id) if item.category_id else None
    if category is None:
        category = Category(event_id=event.id)
        db.add(category)
    category.name = path[:65] + f" #{item.id}"
    category.color = "#e4edda"
    category.sort_order = item.sort_order
    category.is_active = item.is_active
    db.flush()
    item.category_id = category.id
    return category


def ensure_other_budget_item(db, book, event):
    items = budget_rows(db, book)
    lookup = {(i.parent_id, i.name): i for i in items}
    parent = None
    for level in (1, 2, 3):
        item = lookup.get((parent, "기타"))
        if item is None:
            item = BudgetItem(
                book_id=book.id,
                parent_id=parent,
                level=level,
                name="기타",
                detail="미분류 거래 임시 항목",
            )
            db.add(item)
            db.flush()
            audit(db, event.id, "budget", None, encode(item))
        elif not item.is_active:
            before = encode(item)
            item.is_active = True
            item.updated_at = now()
            audit(db, event.id, "budget", before, encode(item))
        parent = item.id
    category = db.get(Category, item.category_id) if item.category_id else None
    if category is None or not category.is_active:
        sync_budget_category(db, event, item, "기타 / 기타 / 기타")
    return item


def context_categories(db, event):
    book = by_event(db, event.id)
    if book and book.kind == "b":
        return []
    if book:
        items = budget_rows(db, book)
        return [
            {"id": i.category_id, "budget_item_id": i.id, "name": budget_path(i, items)}
            for i in items
            if i.level == 3 and i.is_active and i.category_id
        ]
    return [
        {"id": c.id, "budget_item_id": None, "name": c.name}
        for c in db.scalars(
            select(Category).where(Category.event_id == event.id, Category.is_active == True)
        )
    ]


def sync_generated_entry(db, event, x, *, update_existing=False):
    book = by_event(db, event.id)
    if not book:
        return
    entry = db.scalar(select(AnnualEntry).where(AnnualEntry.expense_id == x.id))
    if entry and not update_existing:
        return
    date = x.expense_date
    if date and int(date[:4]) != book.year:
        x.expense_date = None
        x.note += "; AI 거래일이 장부 연도와 다릅니다. 올바른 연도 장부에서 처리하세요."
        date = None
    budget = (
        db.scalar(
            select(BudgetItem).where(
                BudgetItem.book_id == book.id,
                BudgetItem.category_id == x.category_id,
                BudgetItem.level == 3,
            )
        )
        if book.kind == "ordinary"
        else None
    )
    if entry is None:
        entry = AnnualEntry(book_id=book.id, expense_id=x.id, income_krw=0, entry_type="expense")
        db.add(entry)
    entry.transaction_date = date
    entry.budget_item_id = budget.id if budget else None
    entry.description = x.item_name
    entry.expense_krw = x.amount_krw if x.amount_krw is not None else null()
    entry.review_status = x.review_status
    entry.sort_order = x.sort_order
    entry.note = x.note
    entry.source_type = x.source_type
    entry.updated_at = now()


def apply_entry(db, book, event, obj, data):
    if data.transaction_date and data.transaction_date.year != book.year:
        raise HTTPException(
            422, f"거래일은 {book.year}년이어야 합니다. 다른 연도는 해당 연도 장부에 입력하세요."
        )
    budget = None
    if data.budget_item_id:
        budget = db.get(BudgetItem, data.budget_item_id)
        if book.kind != "ordinary" or not budget or budget.book_id != book.id or budget.level != 3:
            raise HTTPException(422, "같은 연도 장부의 목 항목만 선택할 수 있습니다.")
        if not budget.is_active and data.budget_item_id != obj.budget_item_id:
            raise HTTPException(422, "비활성 목은 신규 지정할 수 없습니다.")
    elif book.kind == "b" and data.budget_item_id is not None:
        raise HTTPException(422, "B 장부에는 예산 항목이 없습니다.")
    old = encode(obj) if obj.id else None
    for key, val in data.model_dump(exclude={"id"}).items():
        setattr(obj, key, val.isoformat() if isinstance(val, Date) else val)
    obj.updated_at = now()
    default = db.scalar(select(Category).where(Category.event_id == event.id).order_by(Category.id))
    x = db.get(Expense, obj.expense_id) if obj.expense_id else None
    if not x:
        x = Expense(event_id=event.id)
        db.add(x)
    x.category_id = budget.category_id if budget else default.id
    x.expense_date = obj.transaction_date
    x.item_name = obj.description
    x.amount_krw = obj.expense_krw
    x.vendor = x.vendor or ""
    x.purchased = False
    x.sort_order = obj.sort_order
    x.note = obj.note
    x.review_status = obj.review_status
    x.edited_by = "local-user"
    x.edited_at = now()
    x.source_type = obj.source_type or "manual"
    db.flush()
    obj.expense_id = x.id
    audit(
        db,
        event.id,
        "annual_entry",
        old,
        {k: v.isoformat() if hasattr(v, "isoformat") else v for k, v in data.model_dump().items()},
        x.id,
    )


def annual_snapshot(db, event):
    book = by_event(db, event.id)
    if not book:
        return None
    return {
        "book": encode(book),
        "budget": [encode(i) for i in budget_rows(db, book)],
        "entries": [encode(x) for x in entries(db, book)],
    }


def annual_check(db, event):
    book = by_event(db, event.id)
    errors = []
    warnings = []
    xs = entries(db, book)
    items = {i.id: i for i in budget_rows(db, book)}
    if not xs:
        errors.append("거래 행이 없습니다.")
    links = list(db.scalars(select(Link).join(Expense).where(Expense.event_id == event.id)))
    for n, x in enumerate(xs, 1):
        if (
            not x.transaction_date
            or int(x.transaction_date[:4]) != book.year
            or not x.description.strip()
            or x.income_krw is None
            or x.expense_krw is None
        ):
            errors.append(f"{n}행: 같은 연도의 날짜·내용·금액 필수값을 확인하세요.")
        if not (x.income_krw or x.expense_krw):
            errors.append(f"{n}행: 수입 또는 지출 금액을 입력하세요.")
        if x.review_status != "확인됨":
            errors.append(f"{n}행: 검토 완료를 확인하세요.")
        if (
            book.kind == "ordinary"
            and x.expense_krw
            and (x.budget_item_id not in items or items[x.budget_item_id].level != 3)
        ):
            errors.append(f"{n}행: 지출의 목 항목을 지정하세요.")
        attached = [l for l in links if l.expense_id == x.expense_id]
        if x.expense_krw:
            if not attached:
                warnings.append(f"{n}행: 영수증 없는 지출" + (f" ({x.note})" if x.note else ""))
            elif any(l.allocated_amount_krw is None for l in attached):
                errors.append(f"{n}행: 영수증 배분액을 확인하세요.")
            elif sum(l.allocated_amount_krw for l in attached) != x.expense_krw:
                warnings.append(f"{n}행: 영수증 배분액과 지출 차이")
        elif attached:
            errors.append(f"{n}행: 수입 거래에는 지출 영수증을 연결할 수 없습니다.")
    for r in db.scalars(select(Receipt).where(Receipt.event_id == event.id)):
        if r.ocr_status == "제외":
            continue
        if r.ocr_status != "확인됨":
            errors.append(f"{r.original_name}: 영수증 검토 필요")
        elif not r.transaction_at or len(r.transaction_at) < 16 or r.final_amount_krw is None:
            warnings.append(f"{r.original_name}: 일시·금액 미확인")
        elif int(r.transaction_at[:4]) != book.year:
            errors.append(f"{r.original_name}: 장부와 영수증 연도가 다릅니다.")
    return {
        "errors": errors,
        "warnings": warnings,
        "expense_count": len(xs),
        "total_krw": sum(x.expense_krw or 0 for x in xs),
        "version": event.version,
        "can_finalize": not errors,
    }


def totals(xs):
    get = lambda x, k: x.get(k) if isinstance(x, dict) else getattr(x, k)
    income = sum(get(x, "income_krw") or 0 for x in xs)
    expense = sum(get(x, "expense_krw") or 0 for x in xs)
    carry = sum((get(x, "income_krw") or 0) for x in xs if get(x, "entry_type") == "carryover")
    return {
        "income_krw": income,
        "expense_krw": expense,
        "balance_krw": income - expense,
        "carryover_krw": carry,
        "income_excluding_carryover_krw": income - carry,
    }


def book_detail(db, book):
    from .main import detail

    event = db.get(Event, book.owner_event_id)
    xs = entries(db, book)
    items = budget_rows(db, book)
    official = []
    if event.latest_final_version:
        final = db.scalar(
            select(FinalVersion).where(
                FinalVersion.event_id == event.id,
                FinalVersion.version_no == event.latest_final_version,
            )
        )
        official = json.loads(final.snapshot_json).get("annual", {}).get("entries", [])
    budget = []
    for i in items:
        spent = sum(x["expense_krw"] or 0 for x in official if x["budget_item_id"] == i.id)
        draft_spent = sum(x.expense_krw or 0 for x in xs if x.budget_item_id == i.id)
        budget.append(
            {
                **encode(i),
                "path": budget_path(i, items),
                "spent_krw": spent,
                "draft_spent_krw": draft_spent,
                "remaining_krw": i.budget_krw - spent,
                "ratio": spent / i.budget_krw * 100 if i.budget_krw else None,
            }
        )
    return {
        **encode(book),
        "name": event.name,
        "status": event.status,
        "version": event.version,
        "latest_final_version": event.latest_final_version,
        "updated_at": event.updated_at,
        "budget": budget,
        "entries": [encode(x) for x in xs],
        "totals": totals(official),
        "draft_totals": totals(xs),
        "total_budget_krw": sum(i.budget_krw for i in items if i.level == 3),
        "owner": detail(db, event),
    }
