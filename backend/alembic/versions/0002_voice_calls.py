"""voice channel: caller phone on merchants, ticket channel, tm_calls (tm_* objects only)"""
revision = "0002"
down_revision = "0001"

from alembic import op

SCHEMA = """
alter table tm_tickets add column channel text not null default 'chat' check (channel in ('chat','voice'));

create table tm_calls (
  id bigint generated always as identity primary key,
  ticket_id bigint not null references tm_tickets(id),
  merchant_id text not null references tm_merchants(id),
  provider_call_id text not null unique,
  status text not null default 'queued',
  phone_last4 text,
  transcript text,
  duration_seconds integer,
  created_at timestamptz not null default now(),
  ended_at timestamptz
);
create index tm_calls_ticket on tm_calls (ticket_id);
"""

GRANTS = """
do $$ begin
  if exists (select 1 from pg_roles where rolname = 'coolops_app') then
    grant select, insert, update, delete on tm_calls to coolops_app;
  end if;
end $$;
"""


def upgrade() -> None:
    op.execute(SCHEMA)
    op.execute(GRANTS)


def downgrade() -> None:
    op.execute("drop table if exists tm_calls cascade")
    op.execute("alter table tm_tickets drop column if exists channel")
