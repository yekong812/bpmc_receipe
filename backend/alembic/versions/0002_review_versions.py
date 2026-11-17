"""Receipt drafts and immutable final versions."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("events") as b:
        b.add_column(sa.Column("event_date", sa.String, nullable=True))
        b.add_column(
            sa.Column("latest_final_version", sa.Integer, nullable=False, server_default="0")
        )
    op.execute("UPDATE events SET event_date=end_date")
    op.execute("UPDATE events SET status='검토중' WHERE status='완료'")
    op.execute("CREATE TEMP TABLE saved_links AS SELECT * FROM expense_receipts")
    op.drop_table("expense_receipts")
    with op.batch_alter_table("expenses") as b:
        b.alter_column("category_id", existing_type=sa.Integer, nullable=True)
        b.alter_column("expense_date", existing_type=sa.String, nullable=True)
        b.alter_column("amount_krw", existing_type=sa.Integer, nullable=True)
        b.add_column(sa.Column("source_type", sa.String, nullable=False, server_default="manual"))
        b.add_column(sa.Column("review_status", sa.String, nullable=False, server_default="확인됨"))
        b.add_column(sa.Column("edited_by", sa.String, nullable=False, server_default="local-user"))
        b.add_column(sa.Column("edited_at", sa.String, nullable=False, server_default=""))
    with op.batch_alter_table("receipts") as b:
        b.add_column(sa.Column("edited_at", sa.String, nullable=True))
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
        sa.Column("allocated_amount_krw", sa.Integer, nullable=True),
    )
    op.execute("INSERT INTO expense_receipts SELECT * FROM saved_links")
    op.execute("DROP TABLE saved_links")
    op.create_table(
        "event_final_versions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "event_id", sa.Integer, sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("version_no", sa.Integer, nullable=False),
        sa.Column("snapshot_json", sa.Text, nullable=False),
        sa.Column("finalized_at", sa.String, nullable=False),
        sa.Column("finalized_by", sa.String, nullable=False),
        sa.Column("total_krw", sa.Integer, nullable=False),
        sa.Column("approval_reason", sa.String, nullable=False),
        sa.UniqueConstraint("event_id", "version_no"),
    )
    op.create_table(
        "receipt_extractions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "receipt_id",
            sa.Integer,
            sa.ForeignKey("receipts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ocr_raw_text", sa.Text, nullable=False),
        sa.Column("extracted_json", sa.Text, nullable=False),
        sa.Column("model_name", sa.String, nullable=False),
        sa.Column("analyzed_at", sa.String, nullable=False),
    )
    op.create_table(
        "expense_change_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "event_id", sa.Integer, sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("expense_id", sa.Integer),
        sa.Column("field_name", sa.String, nullable=False),
        sa.Column("old_value", sa.Text, nullable=False),
        sa.Column("new_value", sa.Text, nullable=False),
        sa.Column("changed_at", sa.String, nullable=False),
        sa.Column("change_source", sa.String, nullable=False),
    )
    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column(
            "event_id", sa.Integer, sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("processed", sa.Integer, nullable=False),
        sa.Column("total", sa.Integer, nullable=False),
        sa.Column("error_message", sa.String, nullable=False),
        sa.Column("created_at", sa.String, nullable=False),
    )
    # Snapshots have no update path, and are protected against accidental SQL updates.
    op.execute(
        "CREATE TRIGGER immutable_final_versions BEFORE UPDATE ON event_final_versions BEGIN SELECT RAISE(ABORT, 'final versions are immutable'); END"
    )


def downgrade():
    raise RuntimeError("Final version history must be preserved; restore a backup to downgrade.")
