from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from .schemas import ExpenseIn


class BookIn(BaseModel):
    year: int = Field(ge=1900, le=2200)
    copy_budget_from: int | None = Field(default=None, ge=1)


class BudgetIn(BaseModel):
    id: int | None = None
    parent_id: int | None = None
    level: int = Field(ge=1, le=3)
    name: str = Field(min_length=1, max_length=80)
    budget_krw: int = Field(default=0, ge=0, le=10**12, strict=True)
    detail: str = Field(default="", max_length=2000)
    sort_order: int = 0
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def name_clean(cls, v):
        if not v.strip():
            raise ValueError("항목명을 입력하세요.")
        return v.strip()


class BudgetSave(BaseModel):
    version: int
    items: list[BudgetIn] = Field(max_length=2000)


class EntryIn(BaseModel):
    id: int | None = None
    transaction_date: date | None = None
    budget_item_id: int | None = Field(default=None, ge=1)
    description: str = Field(default="", max_length=500)
    income_krw: int | None = Field(default=0, ge=0, le=10**12, strict=True)
    expense_krw: int | None = Field(default=0, ge=0, le=10**12, strict=True)
    entry_type: Literal["income", "expense", "carryover", "cashback"] = "expense"
    review_status: Literal["확인됨", "검토 필요"] = "확인됨"
    sort_order: int = 0
    note: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def one_side(self):
        if self.income_krw and self.expense_krw:
            raise ValueError("한 거래에는 수입과 지출을 동시에 입력할 수 없습니다.")
        if self.entry_type in ("carryover", "cashback", "income") and self.expense_krw:
            raise ValueError("수입·이월·캐시백 거래는 수입 칸에 입력하세요.")
        return self


class EntrySave(BaseModel):
    version: int
    entries: list[EntryIn] = Field(max_length=10000)
