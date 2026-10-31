"""tm_* tables for the Paytm AI Teammate (shared database: COOLops tables are never touched)"""
revision = "0001"
down_revision = None

from alembic import op

TABLES = ["tm_escalations", "tm_actions", "tm_messages", "tm_tickets", "tm_settlements", "tm_transactions", "tm_merchants"]

SCHEMA = """
create table tm_merchants (
  id text primary key,
  name text not null,
  owner_name text not null,
  category text not null,
  city text not null,
  kyc_status text not null default 'verified' check (kyc_status in ('verified','pending_review')),
  device_id text,
  device_status text check (device_status in ('active','faulty','replacement_requested'))
);

create table tm_transactions (
  id text primary key,
  merchant_id text not null references tm_merchants(id),
  amount_inr integer not null check (amount_inr > 0),
  mode text not null check (mode in ('upi','card','wallet','qr')),
  status text not null check (status in ('success','failed','refunded')),
  customer_debited boolean not null default true,
  customer_name text not null,
  created_at timestamptz not null default now()
);
create index tm_transactions_merchant on tm_transactions (merchant_id, created_at desc);

create table tm_settlements (
  id text primary key,
  merchant_id text not null references tm_merchants(id),
  amount_inr integer not null check (amount_inr > 0),
  expected_date date not null,
  status text not null check (status in ('settled','pending','on_hold')),
  hold_reason text,
  created_at timestamptz not null default now()
);
create index tm_settlements_merchant on tm_settlements (merchant_id, expected_date desc);

create table tm_tickets (
  id bigint generated always as identity primary key,
  merchant_id text not null references tm_merchants(id),
  status text not null default 'open' check (status in ('open','awaiting_merchant','resolved','escalated')),
  category text,
  resolution_summary text,
  resolved_by text check (resolved_by in ('ai','human')),
  created_at timestamptz not null default now(),
  closed_at timestamptz
);
create index tm_tickets_created on tm_tickets (created_at desc);

create table tm_messages (
  id bigint generated always as identity primary key,
  ticket_id bigint not null references tm_tickets(id),
  role text not null check (role in ('merchant','agent','human')),
  kind text not null default 'chat' check (kind in ('chat','notification')),
  content text not null,
  created_at timestamptz not null default now()
);
create index tm_messages_ticket on tm_messages (ticket_id, id);

create table tm_actions (
  id bigint generated always as identity primary key,
  ticket_id bigint not null references tm_tickets(id),
  step integer not null,
  tool text not null,
  args jsonb not null default '{}',
  result jsonb not null default '{}',
  allowed boolean not null,
  created_at timestamptz not null default now()
);
create index tm_actions_ticket on tm_actions (ticket_id, id);

create table tm_escalations (
  id bigint generated always as identity primary key,
  ticket_id bigint not null references tm_tickets(id),
  reason text not null,
  summary text not null,
  attempted_steps jsonb not null default '[]',
  recommended_action text not null,
  status text not null default 'open' check (status in ('open','resolved')),
  resolution_note text,
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);
create index tm_escalations_status on tm_escalations (status, created_at desc);
"""

# Grants only on tm_* tables (identity columns need no separate sequence grant); skipped where the runtime role does not exist (e.g. a bare local database).
GRANTS = """
do $$ begin
  if exists (select 1 from pg_roles where rolname = 'coolops_app') then
    grant select, insert, update, delete on tm_merchants, tm_transactions, tm_settlements, tm_tickets,
      tm_messages, tm_actions, tm_escalations to coolops_app;
  end if;
end $$;
"""


def upgrade() -> None:
    op.execute(SCHEMA)
    op.execute(GRANTS)


def downgrade() -> None:
    for t in TABLES:
        op.execute(f"drop table if exists {t} cascade")
