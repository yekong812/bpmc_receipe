"""Repair the analysis-job FK for databases upgraded during v4 development.
Fresh installations already have this column from 0004; existing records are preserved.
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("receipt_extractions")}
    if "processing_job_id" not in columns:
        with op.batch_alter_table("receipt_extractions") as b:
            b.add_column(
                sa.Column(
                    "processing_job_id",
                    sa.String,
                    sa.ForeignKey(
                        "processing_jobs.id",
                        ondelete="SET NULL",
                        name="fk_extractions_processing_job",
                    ),
                    nullable=True,
                )
            )


def downgrade():
    # Retain the correlation column: old analyses and their usage must remain readable.
    pass
