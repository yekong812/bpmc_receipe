"""Record LLM source, usage and failures without storing credentials or images."""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("receipt_extractions") as b:
        b.add_column(sa.Column("input_kind", sa.String, nullable=False, server_default="ocr"))
        b.add_column(sa.Column("usage_json", sa.Text, nullable=False, server_default="{}"))
        b.add_column(sa.Column("estimated_cost_usd", sa.String, nullable=True))
        b.add_column(sa.Column("error_message", sa.String, nullable=False, server_default=""))


def downgrade():
    with op.batch_alter_table("receipt_extractions") as b:
        for name in ["error_message", "estimated_cost_usd", "usage_json", "input_kind"]:
            b.drop_column(name)
