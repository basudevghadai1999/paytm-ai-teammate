import { createElement, useEffect, useRef, useState } from 'react'
import type { CSSProperties, ReactNode } from 'react'
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

// ---- motion helpers. Everything here degrades to "already visible" without IntersectionObserver or with reduced motion.
export const reducedMotion = () => typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches

/** Fades and lifts its children in once, when they first scroll into view. */
export function Reveal({ children, delay = 0, as = 'div', className = '' }: { children: ReactNode; delay?: number; as?: 'div' | 'li' | 'p' | 'section'; className?: string }) {
  const ref = useRef<HTMLElement>(null)
  const [seen, setSeen] = useState(() => typeof IntersectionObserver === 'undefined' || reducedMotion())
  useEffect(() => {
    const el = ref.current
    if (seen || !el) return
    const io = new IntersectionObserver(es => { if (es.some(e => e.isIntersecting)) { setSeen(true); io.disconnect() } }, { threshold: 0.15 })
    io.observe(el)
    return () => io.disconnect()
  }, [seen])
  return createElement(as, { ref, className: `rv${seen ? ' in' : ''} ${className}`.trim(), style: { '--d': `${delay}ms` } as CSSProperties }, children)
}

/** Headline split into words that resolve one after another. The full text stays readable to screen readers. */
export function Words({ text, accent = '' }: { text: string; accent?: string }) {
  const [on, setOn] = useState(() => reducedMotion())
  useEffect(() => { const t = setTimeout(() => setOn(true), 60); return () => clearTimeout(t) }, [])
  let i = 0
  const word = (w: string, em: boolean) => <span key={`${em}-${i}-${w}`} className={`wd${on ? ' in' : ''}`} style={{ '--d': `${i++ * 70}ms` } as CSSProperties} aria-hidden="true">{em ? <em>{w}</em> : w}{' '}</span>
  return <>
    <span className="sr-only">{text} {accent}</span>
    {text.split(' ').filter(Boolean).map(w => word(w, false))}
    {accent.split(' ').filter(Boolean).map(w => word(w, true))}
  </>
}

/** A number that counts up once it is on screen. */
export function Count({ to, suffix = '' }: { to: number; suffix?: string }) {
  const ref = useRef<HTMLSpanElement>(null)
  const [v, setV] = useState(() => (typeof IntersectionObserver === 'undefined' || reducedMotion() ? to : 0))
  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined' || reducedMotion()) { setV(to); return }
    const el = ref.current
    if (!el) return
    let raf = 0
    const io = new IntersectionObserver(es => {
      if (!es.some(e => e.isIntersecting)) return
      io.disconnect()
      const t0 = performance.now()
      const step = (t: number) => { const k = Math.min(1, (t - t0) / 1400); setV(Math.round(to * (1 - Math.pow(1 - k, 3)))); if (k < 1) raf = requestAnimationFrame(step) }
      raf = requestAnimationFrame(step)
    }, { threshold: 0.6 })
    io.observe(el)
    return () => { io.disconnect(); cancelAnimationFrame(raf) }
  }, [to])
  return <span ref={ref}>{v}{suffix}</span>
}
