"""Annual independent ordinary/B ledgers and stable receipt numbers."""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("receipt_extractions") as b:
        b.add_column(
            sa.Column(
                "processing_job_id",
                sa.String,
                sa.ForeignKey(
                    "processing_jobs.id", ondelete="SET NULL", name="fk_extractions_processing_job"
                ),
                nullable=True,
            )
        )
    op.add_column(
        "events", sa.Column("scope_type", sa.String, nullable=False, server_default="event")
    )
    op.add_column("receipts", sa.Column("receipt_number", sa.Integer, nullable=True))
    op.execute(
        "UPDATE receipts SET receipt_number=(SELECT COUNT(*) FROM receipts r WHERE r.event_id=receipts.event_id AND r.id<=receipts.id)"
    )
    op.create_index(
        "unique_scope_receipt_number", "receipts", ["event_id", "receipt_number"], unique=True
    )
    op.create_table(
        "annual_books",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("kind", sa.String, nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column(
            "owner_event_id",
            sa.Integer,
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("created_at", sa.String, nullable=False),
        sa.UniqueConstraint("kind", "year"),
        sa.CheckConstraint("kind IN ('ordinary','b')"),
    )
    op.create_table(
        "ordinary_budget_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "book_id",
            sa.Integer,
            sa.ForeignKey("annual_books.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("parent_id", sa.Integer, sa.ForeignKey("ordinary_budget_items.id")),
        sa.Column("level", sa.Integer, nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("budget_krw", sa.Integer, nullable=False),
        sa.Column("detail", sa.String, nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False),
        sa.Column("category_id", sa.Integer, sa.ForeignKey("event_categories.id")),
        sa.Column("updated_at", sa.String, nullable=False),
        sa.CheckConstraint("level BETWEEN 1 AND 3"),
        sa.CheckConstraint("budget_krw >= 0"),
    )
    op.create_table(
        "annual_entries",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "book_id",
            sa.Integer,
            sa.ForeignKey("annual_books.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "expense_id",
            sa.Integer,
            sa.ForeignKey("expenses.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("transaction_date", sa.String),
        sa.Column("budget_item_id", sa.Integer, sa.ForeignKey("ordinary_budget_items.id")),
        sa.Column("description", sa.String, nullable=False),
        sa.Column("income_krw", sa.Integer),
        sa.Column("expense_krw", sa.Integer),
        sa.Column("entry_type", sa.String, nullable=False),
        sa.Column("review_status", sa.String, nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False),
        sa.Column("note", sa.String, nullable=False),
        sa.Column("source_type", sa.String, nullable=False),
        sa.Column("updated_at", sa.String, nullable=False),
        sa.CheckConstraint("income_krw IS NULL OR income_krw>=0"),
        sa.CheckConstraint("expense_krw IS NULL OR expense_krw>=0"),
        sa.CheckConstraint("NOT (income_krw>0 AND expense_krw>0)"),
    )


def downgrade():
    raise RuntimeError("Annual books contain financial records. Restore a backup to downgrade.")
