export type Merchant = { id: string; name: string; owner_name: string; category: string; city: string }
export type Message = { id: number; role: 'merchant' | 'agent' | 'human'; kind: 'chat' | 'notification'; channel: 'simulated' | 'email'; content: string; created_at: string }
export type Action = { id: number; step: number; tool: string; args: Record<string, unknown>; result: Record<string, unknown>; allowed: boolean; created_at: string }
export type Escalation = { id: number; reason: string; summary: string; attempted_steps: string[]; recommended_action: string; status: 'open' | 'resolved'; resolution_note: string | null }
export type TicketStatus = 'open' | 'awaiting_merchant' | 'resolved' | 'escalated'
export type CallInfo = { status: string; phone_last4: string | null; transcript: string | null; duration_seconds: number | null; created_at: string; ended_at: string | null }
export type TicketRow = { id: number; merchant_name: string; channel: 'chat' | 'voice'; status: TicketStatus; category: string | null; resolved_by: 'ai' | 'human' | null; created_at: string; closed_at: string | null; first_message: string | null; escalation_reason: string | null }
export type Ticket = TicketRow & { merchant_id: string; resolution_summary: string | null; has_email: boolean; call: CallInfo | null; messages: Message[]; actions: Action[]; escalation: Escalation | null }
export type Metrics = {
  total_tickets: number; out_of_scope: number; resolved_by_ai: number; resolved_by_human: number; escalated_open: number; in_progress: number
  auto_resolution_rate: number | null; avg_ai_resolution_seconds: number | null
  escalations_by_reason: { reason: string; n: number }[]; blocked_actions: number; unsafe_actions: number; refund_limit_inr: number
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch('/api/v1' + path, { ...init, headers: { 'Content-Type': 'application/json' } })
  if (!r.ok) {
    let msg = `Request failed (${r.status})`
    try { const b = await r.json(); if (typeof b.detail === 'string') msg = b.detail } catch { /* keep default */ }
    throw new Error(msg)
  }
  return r.json() as Promise<T>
}
const post = <T,>(path: string, body?: unknown) => req<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

export const api = {
  merchants: () => req<Merchant[]>('/merchants'),
  startCall: (merchant_id: string, phone: string, email: string) => post<{ ticket_id: number; call_id: string }>('/calls', { merchant_id, phone, email }),
  createTicket: (merchant_id: string, message: string) => post<Ticket>('/tickets', { merchant_id, message }),
  reply: (id: number, message: string) => post<Ticket>(`/tickets/${id}/messages`, { message }),
  tickets: () => req<TicketRow[]>('/tickets'),
  ticket: (id: number) => req<Ticket>(`/tickets/${id}`),
  metrics: () => req<Metrics>('/metrics'),
  resolveEscalation: (id: number, note: string) => post<{ ok: boolean }>(`/escalations/${id}/resolve`, { note }),
  reset: () => post<{ ok: boolean }>('/demo/reset'),
}
