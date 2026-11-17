from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator


class EventIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    event_date: date | None = None
    start_date: date
    end_date: date
    status: Literal["작성중", "검토중", "최종 확정", "재수정중", "완료"] = "작성중"

    @field_validator("name")
    @classmethod
    def name_clean(cls, v):
        if not v.strip():
            raise ValueError("행사명을 입력하세요.")
        return v.strip()

    @model_validator(mode="after")
    def dates(self):
        if self.end_date < self.start_date:
            raise ValueError("종료일은 시작일 이후여야 합니다.")
        return self


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    color: str = Field(default="#dbeafe", pattern=r"^#[0-9a-fA-F]{6}$")
    sort_order: int = 0
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def clean(cls, v):
        if not v.strip():
            raise ValueError("항목명을 입력하세요.")
        return v.strip()


class ExpenseIn(BaseModel):
    id: int | None = None
    category_id: int | None = None
    expense_date: date | None = None
    item_name: str = Field(default="", max_length=500)
    amount_krw: int | None = Field(default=None, ge=0, le=10**12)
    review_status: Literal["확인됨", "검토 필요"] = "확인됨"
    vendor: str = Field(default="", max_length=200)
    purchased: bool = False
    sort_order: int = 0
    note: str = Field(default="", max_length=2000)

    @field_validator("amount_krw", mode="before")
    @classmethod
    def money(cls, v):
        if v is None:
            return None
        d = Decimal(str(v))
        if not d.is_finite() or d != d.to_integral_value():
            raise ValueError("금액은 정수 원 단위로 입력하세요.")
        return int(d)

    @field_validator("item_name")
    @classmethod
    def clean(cls, v):
        return v.strip()


class BulkIn(BaseModel):
    version: int
    expenses: list[ExpenseIn] = Field(max_length=5000)


class ReceiptIn(BaseModel):
    transaction_at: datetime | date | None = None
    merchant: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=1000)
    final_amount_krw: int | None = Field(default=None, ge=0, le=10**12)
    review_reason: str = Field(default="", max_length=2000)

    @field_validator("transaction_at", mode="before")
    @classmethod
    def keep_date_precision(cls, v):
        if isinstance(v, str) and len(v) == 10:
            return date.fromisoformat(v)
        return v


class LinkIn(BaseModel):
    expense_id: int
    receipt_id: int
    allocated_amount_krw: int = Field(ge=0, le=10**12)


class CommitIn(BaseModel):
    job_id: str
    mode: Literal["append", "replace"] = "append"
    confirm_replace: bool = False
    accept_warnings: bool = False
    category_mapping: dict[str, str | None] = Field(default_factory=dict)


class CopyIn(BaseModel):
    source_event_id: int


class RevisionIn(BaseModel):
    version: int


class FinalizeIn(RevisionIn):
    approval_reason: str = Field(default="", max_length=2000)
    acknowledge_warnings: bool = False
