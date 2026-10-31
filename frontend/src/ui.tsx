import type { TicketStatus } from './api'

const LABEL: Record<TicketStatus, string> = { open: 'Working', awaiting_merchant: 'Waiting for you', resolved: 'Resolved', escalated: 'With a human' }

export function StatusPill({ status }: { status: TicketStatus }) {
  return <span className={`pill pill--${status}`}>{LABEL[status]}</span>
}

export const reasonLabel = (r: string) => r.replace(/_/g, ' ')

export function fmtSeconds(s: number | null) { return s === null ? 'n/a' : `${s.toFixed(1)}s` }
export function fmtPct(v: number | null) { return v === null ? 'n/a' : `${Math.round(v * 100)}%` }

const TOOL_LINES: Record<string, string> = {
  get_settlement_status: 'Checking your settlements', get_transaction: 'Looking up the payment', list_recent_transactions: 'Checking recent payments',
  get_device_status: 'Checking your soundbox', initiate_refund: 'Refunding the payment', raise_device_replacement: 'Requesting a replacement soundbox',
  send_notification: 'Sending you a confirmation', resolve_ticket: 'Closing the ticket', escalate_to_human: 'Passing this to our support team',
}
export const toolLine = (tool: string) => TOOL_LINES[tool] ?? tool
