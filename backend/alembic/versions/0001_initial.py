"""Initial event expense schema."""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("start_date", sa.String, nullable=False),
        sa.Column("end_date", sa.String, nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("created_at", sa.String, nullable=False),
        sa.Column("updated_at", sa.String, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
    )
    op.create_table(
        "event_categories",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "event_id", sa.Integer, sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("color", sa.String, nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False),
        sa.UniqueConstraint("event_id", "name"),
    )
    op.create_table(
        "expenses",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "event_id", sa.Integer, sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("category_id", sa.Integer, sa.ForeignKey("event_categories.id"), nullable=False),
        sa.Column("expense_date", sa.String, nullable=False),
        sa.Column("item_name", sa.String, nullable=False),
        sa.Column("amount_krw", sa.Integer, nullable=False),
        sa.Column("vendor", sa.String, nullable=False),
        sa.Column("purchased", sa.Boolean, nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False),
        sa.Column("note", sa.String, nullable=False),
    )
    op.create_table(
        "receipts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "event_id", sa.Integer, sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("original_name", sa.String, nullable=False),
        sa.Column("stored_path", sa.String, nullable=False),
        sa.Column("transaction_at", sa.String),
        sa.Column("merchant", sa.String, nullable=False),
        sa.Column("description", sa.String, nullable=False),
        sa.Column("final_amount_krw", sa.Integer),
        sa.Column("ocr_status", sa.String, nullable=False),
        sa.Column("review_reason", sa.String, nullable=False),
        sa.Column("sha256", sa.String, nullable=False),
        sa.Column("ocr_text", sa.String, nullable=False),
    )
    op.create_table(
        "expense_receipts",
        sa.Column(
            "expense_id",
            sa.Integer,
            sa.ForeignKey("expenses.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "receipt_id",
            sa.Integer,
            sa.ForeignKey("receipts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("allocated_amount_krw", sa.Integer, nullable=False),
    )
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column(
            "event_id", sa.Integer, sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("filename", sa.String, nullable=False),
        sa.Column("payload", sa.String, nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("created_at", sa.String, nullable=False),
    )


def downgrade():
    for table in [
        "import_jobs",
        "expense_receipts",
        "receipts",
        "expenses",
        "event_categories",
        "events",
    ]:
        op.drop_table(table)
