from datetime import datetime, timezone
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def now():
    return datetime.now(timezone.utc).isoformat()


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    event_date: Mapped[str | None]
    latest_final_version: Mapped[int] = mapped_column(default=0)
    start_date: Mapped[str]
    end_date: Mapped[str]
    status: Mapped[str] = mapped_column(default="작성중")
    created_at: Mapped[str] = mapped_column(default=now)
    updated_at: Mapped[str] = mapped_column(default=now)
    version: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": version, "version_id_generator": False}


class Category(Base):
    __tablename__ = "event_categories"
    __table_args__ = (UniqueConstraint("event_id", "name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    name: Mapped[str]
    color: Mapped[str] = mapped_column(default="#dbeafe")
    sort_order: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)


class Expense(Base):
    __tablename__ = "expenses"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("event_categories.id"))
    expense_date: Mapped[str | None]
    item_name: Mapped[str]
    amount_krw: Mapped[int | None]
    vendor: Mapped[str] = mapped_column(default="")
    purchased: Mapped[bool] = mapped_column(default=False)
    sort_order: Mapped[int] = mapped_column(default=0)
    note: Mapped[str] = mapped_column(default="")

    source_type: Mapped[str] = mapped_column(default="manual")
    review_status: Mapped[str] = mapped_column(default="확인됨")
    edited_by: Mapped[str] = mapped_column(default="local-user")
    edited_at: Mapped[str] = mapped_column(default=now)


class Receipt(Base):
    __tablename__ = "receipts"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    original_name: Mapped[str]
    stored_path: Mapped[str]
    sha256: Mapped[str]
    transaction_at: Mapped[str | None]
    merchant: Mapped[str] = mapped_column(default="")
    description: Mapped[str] = mapped_column(default="")
    final_amount_krw: Mapped[int | None]
    ocr_status: Mapped[str] = mapped_column(default="대기")
    review_reason: Mapped[str] = mapped_column(default="")
    ocr_text: Mapped[str] = mapped_column(default="")
    edited_at: Mapped[str | None]


class Link(Base):
    __tablename__ = "expense_receipts"
    expense_id: Mapped[int] = mapped_column(
        ForeignKey("expenses.id", ondelete="CASCADE"), primary_key=True
    )
    receipt_id: Mapped[int] = mapped_column(
        ForeignKey("receipts.id", ondelete="CASCADE"), primary_key=True
    )
    allocated_amount_krw: Mapped[int | None]


class ImportJob(Base):
    __tablename__ = "import_jobs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    filename: Mapped[str]
    payload: Mapped[str]
    status: Mapped[str] = mapped_column(default="preview")
    created_at: Mapped[str] = mapped_column(default=now)


class FinalVersion(Base):
    __tablename__ = "event_final_versions"
    __table_args__ = (UniqueConstraint("event_id", "version_no"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    version_no: Mapped[int]
    snapshot_json: Mapped[str]
    finalized_at: Mapped[str] = mapped_column(default=now)
    finalized_by: Mapped[str] = mapped_column(default="local-user")
    total_krw: Mapped[int]
    approval_reason: Mapped[str] = mapped_column(default="")


class Extraction(Base):
    __tablename__ = "receipt_extractions"
    id: Mapped[int] = mapped_column(primary_key=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("receipts.id", ondelete="CASCADE"))
    ocr_raw_text: Mapped[str]
    extracted_json: Mapped[str]
    model_name: Mapped[str] = mapped_column(default="PaddleOCR / rules")
    analyzed_at: Mapped[str] = mapped_column(default=now)
    input_kind: Mapped[str] = mapped_column(default="ocr")
    usage_json: Mapped[str] = mapped_column(default="{}")
    estimated_cost_usd: Mapped[str | None]
    error_message: Mapped[str] = mapped_column(default="")


class ChangeLog(Base):
    __tablename__ = "expense_change_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    expense_id: Mapped[int | None]
    field_name: Mapped[str]
    old_value: Mapped[str]
    new_value: Mapped[str]
    changed_at: Mapped[str] = mapped_column(default=now)
    change_source: Mapped[str] = mapped_column(default="user")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(default="running")
    processed: Mapped[int] = mapped_column(default=0)
    total: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str] = mapped_column(default="")
    created_at: Mapped[str] = mapped_column(default=now)
