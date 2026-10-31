import { useCallback, useEffect, useState } from 'react'
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from './api'
import type { Metrics, Ticket, TicketRow } from './api'
import { StatusPill, fmtPct, fmtSeconds, reasonLabel } from './ui'

function usePoll<T>(fn: () => Promise<T>, ms: number) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState('')
  const refresh = useCallback(() => fn().then(d => { setData(d); setError('') }).catch(e => setError(e.message)), [fn])
  useEffect(() => {
    void refresh()
    const id = setInterval(() => { if (!document.hidden) void refresh() }, ms)
    return () => clearInterval(id)
  }, [refresh, ms])
  return { data, error, refresh }
}

function MetricsView({ m }: { m: Metrics }) {
  const cards: [string, string][] = [
    ['Auto-resolution rate', fmtPct(m.auto_resolution_rate)],
    ['Avg AI resolution time', fmtSeconds(m.avg_ai_resolution_seconds)],
    ['Support tickets', String(m.total_tickets)],
    ['Out of scope', String(m.out_of_scope)],
    ['Open escalations', String(m.escalated_open)],
    ['Blocked actions', String(m.blocked_actions)],
    ['Unsafe actions', String(m.unsafe_actions)],
  ]
  const chart = m.escalations_by_reason.map(r => ({ reason: reasonLabel(r.reason), n: r.n }))
  return (
    <div className="metrics">
      <div className="cards">{cards.map(([k, v]) => <div key={k} className="card"><span className="muted">{k}</span><strong>{v}</strong></div>)}</div>
      {chart.length > 0 && (
        <div className="chart" aria-label="Escalations by reason">
          <span className="muted">Escalations by reason</span>
          <ResponsiveContainer width="100%" height={140}>
            <BarChart data={chart} layout="vertical" margin={{ left: 10 }}>
              <XAxis type="number" allowDecimals={false} hide />
              <YAxis type="category" dataKey="reason" width={140} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="n" fill="#00baf2" radius={4} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}

function TicketDetail({ id, onChanged }: { id: number; onChanged: () => void }) {
  const fetchOne = useCallback(() => api.ticket(id), [id])
  const { data: t, refresh } = usePoll<Ticket>(fetchOne, 3000)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  if (!t) return <div className="detail muted">Loading…</div>
  const esc = t.escalation

  async function resolve() {
    if (!esc || !note.trim()) return
    setBusy(true)
    try { await api.resolveEscalation(esc.id, note.trim()); setNote(''); await refresh(); onChanged() } finally { setBusy(false) }
  }

  return (
    <div className="detail">
      <h3>Ticket #{t.id} · {t.merchant_name} <StatusPill status={t.status} /></h3>
      {esc && (
        <div className="escalation">
          <h4>Escalation: {reasonLabel(esc.reason)}</h4>
          <p>{esc.summary}</p>
          <p><strong>Steps attempted:</strong> {esc.attempted_steps.length ? esc.attempted_steps.join(' · ') : 'none'}</p>
          <p><strong>Recommended:</strong> {esc.recommended_action}</p>
          {esc.status === 'open'
            ? <form onSubmit={e => { e.preventDefault(); void resolve() }}>
                <input value={note} onChange={e => setNote(e.target.value)} placeholder="Resolution note sent to the merchant" aria-label="Resolution note" />
                <button type="submit" disabled={busy || !note.trim()}>Resolve</button>
              </form>
            : <p className="muted">Resolved by a human: {esc.resolution_note}</p>}
        </div>
      )}
      {t.call && (
        <div className="callbox">
          <strong>Call</strong> · {t.call.status}{t.call.duration_seconds ? ` · ${t.call.duration_seconds}s` : ''}{t.call.phone_last4 ? ` · ••••${t.call.phone_last4}` : ''}
          {t.call.transfer_status && <div className="xfer">Live transfer to support: <b>{t.call.transfer_status}</b>{t.call.transfer_failure ? ` (${t.call.transfer_failure})` : ''}</div>}
          {t.call.transcript && <pre>{t.call.transcript}</pre>}
        </div>
      )}
      <h4>Conversation</h4>
      <ul className="thread">{t.messages.map(m => <li key={m.id}><strong>{m.role}{m.kind === 'notification' ? (m.channel === 'email' ? ' (email)' : ' (logged)') : ''}:</strong> {m.content}</li>)}</ul>
      <h4>Agent steps</h4>
      {t.actions.length === 0 && <p className="muted">No tool calls.</p>}
      <ol className="trace">
        {t.actions.map(a => (
          <li key={a.id} className={a.allowed ? '' : 'blocked'}>
            <code>{a.tool}</code> <span className={`tag ${a.allowed ? 'tag--ok' : 'tag--blocked'}`}>{a.allowed ? 'allowed' : 'blocked'}</span>
            <pre>{JSON.stringify(a.args)} → {JSON.stringify(a.result)}</pre>
          </li>
        ))}
      </ol>
    </div>
  )
}

export default function Console() {
  const fetchTickets = useCallback(() => api.tickets(), [])
  const fetchMetrics = useCallback(() => api.metrics(), [])
  const tickets = usePoll<TicketRow[]>(fetchTickets, 3000)
  const metrics = usePoll<Metrics>(fetchMetrics, 3000)
  const [sel, setSel] = useState<number | null>(null)
  const [msg, setMsg] = useState('')

  const changed = () => { void tickets.refresh(); void metrics.refresh() }
  async function reset() {
    if (!window.confirm('Reset all demo data? This deletes every ticket.')) return
    try { await api.reset(); setSel(null); setMsg(''); changed() } catch (e) { setMsg(e instanceof Error ? e.message : 'Reset failed') }
  }

  return (
    <section className="console" aria-label="Ops console">
      <div className="console__bar"><div><p className="eyebrow plain">[ OPS CONSOLE ]</p><h2 className="display display--mid">Every call, step and <em>escalation</em></h2></div><button className="ghost" onClick={() => void reset()}>Reset demo data</button></div>
      {(msg || tickets.error) && <p className="error" role="alert">{msg || tickets.error}</p>}
      {metrics.data && <MetricsView m={metrics.data} />}
      <div className="console__grid">
        <div className="tablewrap">
          <table>
            <thead><tr><th>#</th><th>Merchant</th><th>Issue</th><th>Status</th><th>By</th></tr></thead>
            <tbody>
              {(tickets.data ?? []).map(t => (
                <tr key={t.id} className={sel === t.id ? 'sel' : ''} onClick={() => setSel(t.id)} tabIndex={0} onKeyDown={e => { if (e.key === 'Enter') setSel(t.id) }}>
                  <td>{t.id}</td><td>{t.merchant_name}{t.channel === 'voice' && <span className="tag tag--call">call</span>}</td><td className="clip">{t.first_message}</td>
                  <td><StatusPill status={t.status} /></td><td>{t.resolved_by ?? (t.escalation_reason ? reasonLabel(t.escalation_reason) : '')}</td>
                </tr>
              ))}
              {tickets.data?.length === 0 && <tr><td colSpan={5} className="muted">No tickets yet. Raise one from the Merchant chat tab.</td></tr>}
            </tbody>
          </table>
        </div>
        {sel !== null ? <TicketDetail id={sel} onChanged={changed} /> : <div className="detail muted">Select a ticket to see the conversation and every agent step.</div>}
      </div>
    </section>
  )
}
