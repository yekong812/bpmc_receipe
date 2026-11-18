"""Year-scoped workbook previews and formatted exports for ordinary/B ledgers."""

import io
import re
import zipfile
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.workbook.defined_name import DefinedName
from .excel import parse_date
from .annual_schemas import EntryIn

LEDGER_B = ["날짜", "내용", "수입", "지출", "영수증번호"]
LEDGER_O = ["날짜", "항", "목", "내용", "수입", "지출", "영수증번호"]


def money(v):
    if v in (None, "", "-"):
        return 0
    d = Decimal(re.sub(r"[₩원,\s]", "", str(v)))
    if not d.is_finite() or d != d.to_integral_value() or d < 0 or d > 10**12:
        raise ValueError("금액은 0 이상의 정수 원 단위입니다.")
    return int(d)


def parse_workbook(data, book, target="entries", mapping=None, sheet_name=""):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if sum(i.file_size for i in z.infolist()) > 80 * 1024**2:
            raise ValueError("Excel 압축 해제 크기 제한 초과")
    wb = load_workbook(io.BytesIO(data), data_only=True)
    fw = load_workbook(io.BytesIO(data), data_only=False)
    preferred = (
        "예산 현황"
        if target == "budget"
        else "경상비 장부" if book.kind == "ordinary" else "B 장부"
    )
    ws = wb[sheet_name or (preferred if preferred in wb.sheetnames else wb.sheetnames[0])]
    if ws.max_row > 10000 or ws.max_column > 100:
        raise ValueError("최대 10,000행, 100열까지 지원합니다.")
    required = (
        ["관", "항", "목", "예산"] if target == "budget" else ["날짜", "내용", "수입", "지출"]
    )
    columns = {}
    header = None
    aliases = {
        "거래일": "날짜",
        "지출일": "날짜",
        "품목": "내용",
        "수입금액": "수입",
        "지출금액": "지출",
        "세부내용": "세부내용",
    }
    for row in ws.iter_rows(max_row=min(50, ws.max_row)):
        found = {}
        for c in row:
            name = re.sub(r"\s", "", str(c.value or ""))
            name = aliases.get(name, name)
            if "예산" in name and target == "budget":
                name = "예산"
            if name not in found:
                found[name] = c.column
        if all(x in found for x in required):
            columns = found
            header = row[0].row
            break
    if mapping:
        header = int(mapping.get("header_row", 1))
        columns = {k: int(v) for k, v in mapping.items() if k != "header_row" and v}
        if any(v < 1 or v > 100 for v in columns.values()) or header < 1 or header > 10000:
            raise ValueError("올바른 헤더 행/열 번호를 입력하세요.")
    result = {
        "rows": [],
        "errors": [],
        "warnings": [],
        "needs_mapping": not header or any(k not in columns for k in required),
        "sample": [],
        "sheets": wb.sheetnames,
        "sheet_name": ws.title,
        "target": target,
    }
    if result["needs_mapping"]:
        result["sample"] = [
            [str(c.value or "") for c in row] for row in ws.iter_rows(max_row=min(15, ws.max_row))
        ]
        return result
    merged = {}
    for area in ws.merged_cells.ranges:
        for row in range(area.min_row, area.max_row + 1):
            for col in range(area.min_col, area.max_col + 1):
                merged[row, col] = ws.cell(area.min_row, area.min_col).value
    previous = None
    prior = {"관": "", "항": ""}
    seen = set()
    for n in range(header + 1, ws.max_row + 1):

        def value(key):
            col = columns.get(key)
            return merged.get((n, col), ws.cell(n, col).value) if col else None

        try:
            if not any(value(k) is not None for k in required):
                continue
            if any(
                str(value(k) or "").strip() in ["합계", "총계", "소계"]
                or str(value(k) or "").strip().endswith(" 소계")
                for k in ["날짜", "내용", "목"]
            ):
                continue
            for key in required:
                c = fw[ws.title].cell(n, columns[key])
                if c.data_type == "f" and value(key) is None:
                    raise ValueError("계산값 없는 수식입니다. Excel에서 재계산 후 저장하세요.")
            if target == "budget":
                for k in ["관", "항"]:
                    if value(k):
                        prior[k] = str(value(k)).strip()
                leaf = str(value("목") or "").strip()
                if not leaf:
                    continue
                if not all(prior.values()):
                    raise ValueError("관·항·목 계층을 모두 지정하세요.")
                row = {
                    "division": prior["관"],
                    "section": prior["항"],
                    "name": leaf,
                    "budget_krw": money(value("예산")),
                    "imported_spent_krw": (
                        money(value("실지출")) if value("실지출") is not None else None
                    ),
                    "detail": str(value("세부내용") or ""),
                    "source_row": n,
                }
                if (
                    any(len(row[k]) > 80 for k in ["division", "section", "name"])
                    or len(row["detail"]) > 2000
                ):
                    raise ValueError("항목명은 80자, 세부내용은 2,000자 이내입니다.")
                sig = (row["division"], row["section"], row["name"])
            else:
                raw = value("날짜")
                if raw is None:
                    if previous is None:
                        raise ValueError("첫 거래 날짜가 비어 있습니다.")
                    day = previous
                    result["warnings"].append(f"{n}행: 이전 날짜를 이어받았습니다.")
                else:
                    day, inferred = parse_date(raw, book.year)
                    if inferred:
                        result["warnings"].append(f"{n}행: 장부 연도 {book.year}년 적용")
                if int(day[:4]) != book.year:
                    raise ValueError(f"{book.year}년 장부에 다른 연도 거래를 넣을 수 없습니다.")
                previous = day
                income = money(value("수입"))
                expense = money(value("지출"))
                description = str(value("내용") or "").strip()
                if not description:
                    raise ValueError("내용을 입력하세요.")
                kind = (
                    "carryover"
                    if "이월" in description and income
                    else (
                        "cashback"
                        if "캐시백" in description and income
                        else "income" if income else "expense"
                    )
                )
                if value("거래유형") in ["income", "expense", "carryover", "cashback"]:
                    kind = value("거래유형")
                valid = EntryIn(
                    transaction_date=day,
                    description=description,
                    income_krw=income,
                    expense_krw=expense,
                    entry_type=kind,
                )
                row = {
                    **valid.model_dump(mode="json"),
                    "section": str(value("항") or "").strip(),
                    "budget_name": str(value("목") or "").strip(),
                    "source_row": n,
                }
                sig = (day, description, income, expense)
            if sig in seen:
                result["warnings"].append(f"{n}행: 파일 내 중복 후보")
            seen.add(sig)
            result["rows"].append(row)
        except (ValueError, InvalidOperation, OverflowError) as exc:
            result["errors"].append({"row": n, "message": str(exc)})
    return result


def export_book(snapshot):
    annual = snapshot["annual"]
    book = annual["book"]
    ordinary = book["kind"] == "ordinary"
    year = book["year"]
    budgets = annual["budget"]
    entries = annual["entries"]
    items = {b["id"]: b for b in budgets}
    wb = Workbook()
    ledger = wb.active
    ledger.title = "경상비 장부" if ordinary else "B 장부"
    headers = LEDGER_O if ordinary else LEDGER_B
    ledger.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    ledger.cell(
        1,
        1,
        f"{year}년 {ledger.title}"
        + (
            f' · 확정 v{snapshot["final_version"]}'
            if snapshot.get("final_version")
            else " · 미확정 초안"
        ),
    )
    for i, name in enumerate(headers, 1):
        ledger.cell(3, i, name)
    links = snapshot["links"]
    receipt_numbers = {
        r["id"]: r.get("receipt_number") or i for i, r in enumerate(snapshot["receipts"], 1)
    }
    for n, e in enumerate(entries, 4):
        leaf = items.get(e["budget_item_id"])
        section = items.get(leaf["parent_id"]) if leaf else None
        refs = ", ".join(
            str(receipt_numbers[l["receipt_id"]])
            for l in links
            if l["expense_id"] == e["expense_id"]
        )
        values = (
            [date.fromisoformat(e["transaction_date"]) if e["transaction_date"] else None]
            + (
                [section["name"] if section else "", leaf["name"] if leaf else ""]
                if ordinary
                else []
            )
            + [e["description"], e["income_krw"], e["expense_krw"], refs]
        )
        for col, val in enumerate(values, 1):
            ledger.cell(n, col, val)
        ledger.cell(n, 1).number_format = "yyyy.mm.dd"
    # An auxiliary column preserves carryover/cashback types through round trips.
    ledger.cell(3, len(headers) + 2, "거래유형")
    for n, e in enumerate(entries, 4):
        ledger.cell(n, len(headers) + 2, e["entry_type"])
    ledger.column_dimensions[get_column_letter(len(headers) + 2)].hidden = True
    last = 4 + len(entries)
    ledger.cell(last, 1, "합계")
    income_col = 5 if ordinary else 3
    expense_col = 6 if ordinary else 4
    ledger.cell(last, income_col, sum(e["income_krw"] or 0 for e in entries))
    ledger.cell(last, expense_col, sum(e["expense_krw"] or 0 for e in entries))
    ledger.cell(3, len(headers) + 4, "수입합계")
    ledger.cell(3, len(headers) + 5, sum(e["income_krw"] or 0 for e in entries))
    ledger.cell(4, len(headers) + 4, "지출합계")
    ledger.cell(4, len(headers) + 5, sum(e["expense_krw"] or 0 for e in entries))
    ledger.cell(5, len(headers) + 4, "수지차액")
    ledger.cell(
        5, len(headers) + 5, sum((e["income_krw"] or 0) - (e["expense_krw"] or 0) for e in entries)
    )
    if ordinary:
        ws = wb.create_sheet("예산 현황", 0)
        ws.merge_cells("A1:H1")
        ws["A1"] = f"{year}년 예산 현황" + (
            " · 미확정 초안" if not snapshot.get("final_version") else ""
        )
        for c, h in enumerate(
            ["관", "항", "목", f"{year} 예산", "세부내용", "실지출", "잔액", "비율"], 1
        ):
            ws.cell(3, c, h)
        n = 4
        groups = {}
        for leaf in [b for b in budgets if b["level"] == 3]:
            section = items[leaf["parent_id"]]
            division = items[section["parent_id"]]
            groups.setdefault((division["id"], section["id"]), []).append(leaf)
        for (div_id, sec_id), leaves in groups.items():
            start = n
            budget_sum = spent_sum = 0
            for leaf in leaves:
                spent = sum(
                    e["expense_krw"] or 0 for e in entries if e["budget_item_id"] == leaf["id"]
                )
                budget_sum += leaf["budget_krw"]
                spent_sum += spent
                for c, v in enumerate(
                    [
                        items[div_id]["name"],
                        items[sec_id]["name"],
                        leaf["name"],
                        leaf["budget_krw"],
                        leaf["detail"],
                        spent,
                        leaf["budget_krw"] - spent,
                        spent / leaf["budget_krw"] if leaf["budget_krw"] else None,
                    ],
                    1,
                ):
                    ws.cell(n, c, v)
                ws.cell(n, 8).number_format = "0.0%"
                n += 1
            if n - start > 1:
                ws.merge_cells(start_row=start, start_column=1, end_row=n - 1, end_column=1)
                ws.merge_cells(start_row=start, start_column=2, end_row=n - 1, end_column=2)
            ws.cell(n, 3, items[sec_id]["name"] + " 소계")
            ws.cell(n, 4, budget_sum)
            ws.cell(n, 6, spent_sum)
            ws.cell(n, 7, budget_sum - spent_sum)
            n += 1
        ws.cell(n, 3, "합계")
        ws.cell(n, 4, sum(b["budget_krw"] for b in budgets if b["level"] == 3))
        ws.cell(n, 6, sum(e["expense_krw"] or 0 for e in entries))
        ws.cell(n, 7, ws.cell(n, 4).value - ws.cell(n, 6).value)
        active = [b for b in budgets if b["level"] == 3 and b["is_active"]]
        if active:
            options = wb.create_sheet("항목목록")
            options.sheet_state = "hidden"
            for i, b in enumerate(active, 1):
                options.cell(i, 1, b["name"])
            wb.defined_names.add(
                DefinedName("BudgetLeaves", attr_text=f"'항목목록'!$A$1:$A${len(active)}")
            )
            dv = DataValidation(type="list", formula1="BudgetLeaves")
            ledger.add_data_validation(dv)
            dv.add("C4:C10000")
    thin = Side(style="thin", color="DCE5D9")
    for ws in wb:
        if ws.sheet_state == "hidden":
            continue
        ws.freeze_panes = "B4"
        ws.sheet_view.showGridLines = False
        ws.page_setup.orientation = "landscape"
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth = 1
        ws.print_title_rows = "1:3"
        ws.print_area = ws.dimensions
        for col in range(1, ws.max_column + 1):
            ws.column_dimensions[get_column_letter(col)].width = (
                18 if col != (4 if ordinary and ws is ledger else 2) else 38
            )
        for row in ws:
            for cell in row:
                if cell.row in [1, 3]:
                    cell.fill = PatternFill("solid", fgColor="DDECDD")
                    cell.font = Font(bold=True, size=16 if cell.row == 1 else 11)
                if cell.value is not None:
                    cell.border = Border(bottom=thin)
                    cell.alignment = Alignment(
                        vertical="center",
                        horizontal="right" if isinstance(cell.value, (int, float)) else "left",
                    )
                    if isinstance(cell.value, (int, float)) and cell.number_format == "General":
                        cell.number_format = "₩#,##0"
                    if isinstance(cell.value, str) and cell.value.startswith(("=", "+", "-", "@")):
                        cell.data_type = "s"
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
