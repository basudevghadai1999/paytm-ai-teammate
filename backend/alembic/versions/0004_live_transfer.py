"""live transfer of emergency calls to a person: what Bolna reports about the transfer leg (tm_* objects only)"""
revision = "0004"
down_revision = "0003"

from alembic import op


def upgrade() -> None:
    op.execute("""
alter table tm_calls add column transfer_status text check (transfer_status in ('requested','attempted','transferred','failed'));
alter table tm_calls add column transfer_failure text;
""")


def downgrade() -> None:
    op.execute("alter table tm_calls drop column if exists transfer_failure, drop column if exists transfer_status")
