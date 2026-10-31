import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import App from './App'

const merchants = [{ id: 'M-1', name: 'Test Store', owner_name: 'Owner', category: 'Kirana', city: 'Delhi' }]
const ticket = {
  id: 7, merchant_id: 'M-1', merchant_name: 'Test Store', channel: 'voice', status: 'resolved', category: 'failed_payment', resolved_by: 'ai',
  created_at: '', closed_at: '', first_message: 'Voice call', escalation_reason: null, resolution_summary: 's', escalation: null,
  call: { status: 'completed', phone_last4: '3210', transcript: 'assistant: hello', duration_seconds: 40, created_at: '', ended_at: '' },
  actions: [{ id: 1, step: 1, tool: 'initiate_refund', args: {}, result: {}, allowed: true, created_at: '' }],
  messages: [{ id: 2, role: 'agent', kind: 'notification', content: 'Refund of INR 850 initiated.', created_at: '' }],
}

afterEach(() => vi.unstubAllGlobals())

test('merchant starts a call and sees the steps and outcome', async () => {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const body = url.endsWith('/merchants') ? merchants : url.endsWith('/calls') && init?.method === 'POST' ? { ticket_id: 7, call_id: 'ex1' } : ticket
    return new Response(JSON.stringify(body), { status: 200 })
  })
  vi.stubGlobal('fetch', fetchMock)
  render(<App />)
  await screen.findByRole('option', { name: /Test Store/ })
  const call = screen.getByRole('button', { name: 'Call me' })
  expect(call).toBeDisabled()
  await userEvent.type(screen.getByLabelText(/Your phone number/), '+919876543210')
  await userEvent.click(call)
  expect(await screen.findByText('Refunding the payment')).toBeInTheDocument()
  expect(screen.getByText('Call finished: your issue is resolved')).toBeInTheDocument()
  expect(screen.getByText('Refund of INR 850 initiated.')).toBeInTheDocument()
  const post = fetchMock.mock.calls.find(([u]) => String(u).endsWith('/calls'))!
  expect(JSON.parse((post[1] as RequestInit).body as string)).toEqual({ merchant_id: 'M-1', phone: '+919876543210' })
})

test('a number without a country code cannot be called', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(merchants), { status: 200 })))
  render(<App />)
  await screen.findByRole('option', { name: /Test Store/ })
  await userEvent.type(screen.getByLabelText(/Your phone number/), '9876543210')
  expect(screen.getByRole('button', { name: 'Call me' })).toBeDisabled()
})

test('the ops console shows an empty state', async () => {
  const metrics = { total_tickets: 0, resolved_by_ai: 0, resolved_by_human: 0, escalated_open: 0, in_progress: 0, auto_resolution_rate: null,
    avg_ai_resolution_seconds: null, escalations_by_reason: [], blocked_actions: 0, unsafe_actions: 0, refund_limit_inr: 2000 }
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith('/metrics') ? metrics : []), { status: 200 })))
  render(<App />)
  await userEvent.click(screen.getByRole('button', { name: 'Ops console' }))
  await waitFor(() => expect(screen.getByText(/No tickets yet/)).toBeInTheDocument())
})
