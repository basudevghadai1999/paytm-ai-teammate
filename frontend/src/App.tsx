import { useEffect, useState } from 'react'
import Call from './Call'
import Console from './Console'

export default function App() {
  const [view, setView] = useState<'chat' | 'console'>('chat')
  const [who, setWho] = useState('')
  useEffect(() => {
    fetch('/auth/me').then(r => r.json()).then(j => { if (j && typeof j.email === 'string') setWho(j.email) }).catch(() => {})
  }, [])
  return (
    <>
      <header className="top">
        <div className="brand"><span className="brand__mark" aria-hidden="true" />Paytm <b>AI Teammate</b></div>
        <nav aria-label="Views">
          <button aria-pressed={view === 'chat'} onClick={() => setView('chat')}>Merchant call</button>
          <button aria-pressed={view === 'console'} onClick={() => setView('console')}>Ops console</button>
        </nav>
        <span className="badge">Simulated systems</span>
        {who && <span className="who">{who} · <a href="/auth/logout">Sign out</a></span>}
      </header>
      <main>{view === 'chat' ? <Call /> : <Console />}</main>
    </>
  )
}
