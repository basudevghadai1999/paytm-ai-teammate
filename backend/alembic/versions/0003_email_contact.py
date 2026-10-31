"""contact email on tickets, email channel on messages, support-alert marker (tm_* objects only)"""
revision = "0003"
down_revision = "0002"

from alembic import op

SCHEMA = """
alter table tm_tickets add column contact_email text;
alter table tm_messages add column channel text not null default 'simulated' check (channel in ('simulated','email'));
alter table tm_messages add column provider_id text;
alter table tm_escalations add column alerted_at timestamptz;
"""


def upgrade() -> None:
    op.execute(SCHEMA)


def downgrade() -> None:
    op.execute("alter table tm_escalations drop column if exists alerted_at")
    op.execute("alter table tm_messages drop column if exists provider_id, drop column if exists channel")
    op.execute("alter table tm_tickets drop column if exists contact_email")
