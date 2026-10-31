"""Public sign-in page. Self-contained HTML (no assets of ours): the React app itself is behind sign-in.
Every claim here must match what the product actually does. Sample figures are labelled as illustrative."""

ICON = {
    "phone": '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2Z"/>',
    "brain": '<path d="M9 4a3 3 0 0 0-3 3v1a3 3 0 0 0-2 3 3 3 0 0 0 2 2.8V15a3 3 0 0 0 3 3h1V4H9Zm6 0a3 3 0 0 1 3 3v1a3 3 0 0 1 2 3 3 3 0 0 1-2 2.8V15a3 3 0 0 1-3 3h-1V4h1Z"/>',
    "bolt": '<path d="M13 2 4 14h6l-1 8 9-12h-6l1-8Z"/>',
    "alert": '<path d="M12 3 2 20h20L12 3Zm0 6v5m0 3v.5"/>',
    "shield": '<path d="M12 3 4 6v5c0 5 3.5 8.5 8 10 4.5-1.5 8-5 8-10V6l-8-3Z"/><path d="m8.5 12 2.5 2.5L16 9.5"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
    "list": '<path d="M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01"/>',
    "lane": '<path d="M5 20 9 4m10 16L15 4M12 6v2m0 4v2m0 4v2"/>',
}


def _icon(k: str) -> str:
    return f'<svg viewBox="0 0 24 24" aria-hidden="true">{ICON[k]}</svg>'


STEPS = [
    ("01", "Call", "phone", "The teammate calls the merchant, greets them by name, and asks what is wrong, in Hindi or English."),
    ("02", "Understand", "brain", "It looks up the merchant's settlements, payments and soundbox before it says anything about them."),
    ("03", "Act", "bolt", "It refunds within the limit, raises a replacement soundbox, and emails a confirmation, only through guarded tools."),
    ("04", "Hand over", "alert", "Risky cases and emergencies go to a person with a summary, the steps tried and a recommendation."),
]

CAPS = [
    ("globe", "Speaks the merchant's language", "Hindi and English, mixed or not. The agent mirrors how the merchant talks and keeps sentences short."),
    ("shield", "Rules enforced in code", "Refund limit, one refund per payment, merchant isolation and eligibility checks live in code. A clever sentence cannot talk it past them."),
    ("mail", "Confirmation by email", "A real email confirms what was done. The agent may only say it emailed you if an email was actually sent."),
    ("alert", "Emergencies reach a human", "Fraud, a hacked account, a legal threat or a distressed merchant escalate at once and alert the support inbox by email."),
    ("lane", "Stays in its lane", "It only handles Paytm merchant support. Anything else is declined politely, without answering and without touching an account."),
    ("list", "Everything is audited", "Every tool call, allowed or blocked, is logged and shown in the ops console with the call transcript."),
]

CSS = """
:root{--navy:#0b2a6f;--navy2:#12348a;--blue:#2b4fd0;--sky:#00b9f5;--sky2:#4fb7f6;--tint:#e8f6fe;--tint2:#f4faff;--line:#d9e8f5;--text:#0f1f45;--muted:#5a6b8c;--ok:#14a86a}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;font-family:Inter,system-ui,-apple-system,sans-serif;color:var(--text);background:var(--tint2);line-height:1.55;-webkit-font-smoothing:antialiased}
a{color:inherit}:focus-visible{outline:2px solid var(--sky);outline-offset:3px;border-radius:6px}
.wrap{max-width:1120px;margin:0 auto;padding:0 clamp(18px,4vw,32px)}
header.nav{position:sticky;top:0;z-index:10;background:rgba(11,42,111,.96);backdrop-filter:blur(8px);color:#fff}
.nav-in{display:flex;align-items:center;gap:16px;height:64px}
.brand{display:flex;align-items:center;gap:10px;font-weight:800;font-size:18px;text-decoration:none;margin-right:auto}.brand b{color:var(--sky2)}
.mark{width:28px;height:28px;border-radius:9px;background:linear-gradient(135deg,var(--sky),var(--blue));position:relative;flex:none}
.mark:after{content:'';position:absolute;inset:7px 8px 8px 7px;border:2.5px solid #fff;border-radius:99px 99px 99px 4px}
.navlinks{display:flex;gap:22px;font-size:14px;font-weight:500}.navlinks a{text-decoration:none;color:#cfe0ff}.navlinks a:hover{color:#fff}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:10px;font:inherit;font-weight:700;text-decoration:none;border:0;border-radius:999px;padding:12px 24px;cursor:pointer;transition:transform .12s,box-shadow .12s,background .12s}
.btn:hover{transform:translateY(-1px)}.btn.primary{background:var(--sky);color:#04243f;box-shadow:0 8px 22px rgba(0,185,245,.35)}.btn.primary:hover{background:#18c4ff}
.btn.ghost{background:transparent;color:#fff;border:1px solid rgba(255,255,255,.4)}.btn.ghost:hover{background:rgba(255,255,255,.1)}.btn.lg{padding:15px 30px;font-size:16px}.btn.sm{padding:9px 18px;font-size:14px}
.btn svg{width:20px;height:20px;flex:none}.g{background:#fff;border-radius:50%;padding:2px}
.hero{position:relative;overflow:hidden;color:#fff;background:linear-gradient(135deg,var(--navy) 0%,var(--blue) 100%)}
.hero:before,.hero:after{content:'';position:absolute;border-radius:50%;pointer-events:none}
.hero:before{width:520px;height:520px;right:-140px;top:-230px;border:70px solid var(--sky2);opacity:.45}
.hero:after{width:300px;height:300px;left:-90px;bottom:-170px;border:46px solid #fff;opacity:.1}
.hero-in{position:relative;display:grid;grid-template-columns:1.1fr .9fr;gap:48px;align-items:center;padding:clamp(40px,7vw,84px) 0}
.pill{display:inline-flex;align-items:center;gap:8px;font-size:12px;font-weight:700;letter-spacing:.06em;padding:6px 14px;border-radius:999px;background:rgba(79,183,246,.2);border:1px solid rgba(79,183,246,.45);color:#c6e8ff;margin:0 0 18px}
.pill i{width:8px;height:8px;border-radius:50%;background:var(--sky2)}
h1{font-size:clamp(34px,5.2vw,58px);line-height:1.06;letter-spacing:-.02em;margin:0 0 16px;font-weight:800}
.lead{font-size:18px;color:#d3e4ff;max-width:52ch;margin:0 0 26px}
.cta{display:flex;gap:12px;flex-wrap:wrap;align-items:center}.note{font-size:13px;color:#b7cdf3;margin:14px 0 0}
.checks{list-style:none;padding:0;margin:26px 0 0;display:grid;gap:8px;font-size:15px;color:#e1ecff}
.checks li{display:flex;gap:10px;align-items:flex-start}.checks li:before{content:'✓';display:grid;place-items:center;width:20px;height:20px;border-radius:50%;background:rgba(0,185,245,.25);color:#7fe0ff;font-size:12px;font-weight:800;flex:none;margin-top:2px}
.call{background:#fff;color:var(--text);border-radius:22px;padding:20px;box-shadow:0 24px 60px rgba(4,20,70,.35)}
.call-h{display:flex;align-items:center;gap:10px;font-weight:700;color:var(--navy)}.call-h i{width:12px;height:12px;border-radius:50%;background:var(--ok);box-shadow:0 0 0 4px rgba(20,168,106,.18)}
.call-h em{margin-left:auto;font-style:normal;font-size:11px;font-weight:600;color:var(--muted);background:var(--tint);padding:3px 10px;border-radius:99px}
.call ol{list-style:none;margin:14px 0 0;padding:0;display:grid;gap:8px}
.call li{display:flex;align-items:center;gap:10px;border:1px solid var(--line);background:var(--tint2);border-radius:12px;padding:9px 12px;font-weight:500;font-size:14px}
.call li:before{content:'✓';display:grid;place-items:center;width:22px;height:22px;border-radius:50%;background:#dff6ea;color:var(--ok);font-weight:800;font-size:12px;flex:none}
.mail{margin-top:12px;border:1.5px solid var(--ok);background:#effaf4;border-radius:14px;padding:10px 14px;font-size:13px}.mail small{display:block;font-size:10.5px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--ok)}
section.sec{padding:clamp(48px,7vw,84px) 0}section.alt{background:#fff;border-block:1px solid var(--line)}
.eyebrow{font-size:12px;font-weight:700;letter-spacing:.1em;color:var(--blue);margin:0 0 8px}
h2{font-size:clamp(26px,3.6vw,38px);line-height:1.15;letter-spacing:-.015em;margin:0 0 10px;color:var(--navy);font-weight:800}
.intro{color:var(--muted);max-width:62ch;margin:0 0 30px;font-size:17px}
.grid{display:grid;gap:16px}.g4{grid-template-columns:repeat(4,1fr)}.g3{grid-template-columns:repeat(3,1fr)}
.card{background:#fff;border:1px solid var(--line);border-radius:18px;padding:22px;box-shadow:0 2px 12px rgba(11,42,111,.05)}
.card h3{margin:14px 0 6px;font-size:18px;color:var(--navy)}.card p{margin:0;color:var(--muted);font-size:15px}
.ic{width:46px;height:46px;border-radius:14px;display:grid;place-items:center;background:var(--tint);color:var(--blue)}
.ic svg{width:24px;height:24px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.step .n{float:right;font-weight:800;font-size:13px;color:#9db4de}
.preview{border:1px solid var(--line);border-radius:20px;overflow:hidden;background:#fff;box-shadow:0 18px 44px rgba(11,42,111,.12)}
.pbar{display:flex;align-items:center;gap:7px;padding:12px 16px;background:var(--navy);color:#cfe0ff;font-size:13px}.pbar i{width:10px;height:10px;border-radius:50%;background:rgba(255,255,255,.3)}.pbar span{margin-left:8px;font-weight:600}.pbar em{margin-left:auto;font-style:normal;font-size:11px;color:#9fc0f2}
.pbody{padding:18px;display:grid;gap:14px}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.stat{border:1px solid var(--line);border-radius:12px;padding:10px 12px;position:relative;overflow:hidden}.stat:before{content:'';position:absolute;left:0;top:0;bottom:0;width:4px;background:linear-gradient(var(--sky),var(--blue))}
.stat small{display:block;color:var(--muted);font-size:12px}.stat b{font-size:22px;color:var(--navy)}
.rows{display:grid;gap:8px}.row{display:flex;align-items:center;gap:10px;border:1px solid var(--line);border-radius:12px;padding:10px 12px;font-size:14px}.row span{flex:1}.row small{display:block;color:var(--muted);font-size:12px}
.tag{font-size:11px;font-weight:700;padding:3px 10px;border-radius:99px;white-space:nowrap}.t-ok{background:#dff6ea;color:var(--ok)}.t-warn{background:#fff0d4;color:#b36200}.t-bad{background:#fde7e7;color:#d64545}
.honest{display:grid;grid-template-columns:1fr 1fr;gap:16px}.honest .card h3{margin-top:0}.honest ul{margin:8px 0 0;padding-left:20px;color:var(--muted)}
.signin{background:linear-gradient(135deg,var(--navy),var(--blue));color:#fff;border-radius:26px;padding:clamp(28px,5vw,52px);text-align:center;position:relative;overflow:hidden}
.signin:before{content:'';position:absolute;width:300px;height:300px;border-radius:50%;border:44px solid var(--sky2);opacity:.35;right:-90px;top:-130px}
.signin h2{color:#fff;position:relative}.signin p{position:relative;color:#d3e4ff;max-width:56ch;margin:0 auto 22px}.signin .btn{position:relative}
footer{padding:28px 0 40px;color:var(--muted);font-size:13px;text-align:center}
@media(max-width:900px){.hero-in{grid-template-columns:1fr;gap:34px}.g4{grid-template-columns:1fr 1fr}.g3{grid-template-columns:1fr 1fr}.stats{grid-template-columns:1fr 1fr}.navlinks{display:none}}
@media(max-width:600px){.g4,.g3,.honest{grid-template-columns:1fr}.lead{font-size:16px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}.btn{transition:none}}
"""

GOOGLE = ('<svg class="g" viewBox="0 0 48 48" aria-hidden="true"><path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.9 6.1C12.4 13.6 17.7 9.5 24 9.5z"/>'
          '<path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 3-2.3 5.5-4.8 7.2l7.5 5.8c4.4-4.1 7.1-10.1 7.1-17.5z"/>'
          '<path fill="#FBBC05" d="M10.5 28.7a14.5 14.5 0 0 1 0-9.4l-7.9-6.1a24 24 0 0 0 0 21.6l7.9-6.1z"/>'
          '<path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.5-5.8c-2.1 1.4-4.8 2.3-8.4 2.3-6.3 0-11.6-4.1-13.5-9.8l-7.9 6.1C6.5 42.6 14.6 48 24 48z"/></svg>')


def page() -> str:
    steps = "".join(f'<li class="card step"><span class="n">{n}</span><span class="ic">{_icon(i)}</span><h3>{t}</h3><p>{d}</p></li>' for n, t, i, d in STEPS)
    caps = "".join(f'<li class="card"><span class="ic">{_icon(i)}</span><h3>{t}</h3><p>{d}</p></li>' for i, t, d in CAPS)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Paytm AI Teammate: sign in</title><meta name="robots" content="noindex,nofollow"><meta name="theme-color" content="#0b2a6f">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet"><style>{CSS}</style></head><body>
<header class="nav"><div class="wrap nav-in"><a class="brand" href="/auth/login"><span class="mark" aria-hidden="true"></span>Paytm <b>AI Teammate</b></a>
<nav class="navlinks" aria-label="Page"><a href="#how">How it works</a><a href="#capabilities">Capabilities</a><a href="#console">Ops console</a><a href="#honest">What is real</a></nav>
<a class="btn ghost sm" href="/auth/google">Sign in</a></div></header>
<main>
<section class="hero" aria-labelledby="t"><div class="wrap hero-in"><div>
<p class="pill"><i></i>AI VOICE SUPPORT FOR PAYTM MERCHANTS</p>
<h1 id="t">Every merchant issue,<br>sorted on one call.</h1>
<p class="lead">An AI teammate that phones the merchant, checks their account, takes the action, emails a confirmation, and brings in a person only when it should.</p>
<div class="cta"><a class="btn primary lg" href="/auth/google">{GOOGLE}Sign in with Google</a><a class="btn ghost lg" href="#how">See how it works <span aria-hidden="true">→</span></a></div>
<p class="note">Private development preview. Only approved Google accounts can sign in.</p>
<ul class="checks"><li>Speaks Hindi and English</li><li>Acts only within limits enforced in code</li><li>Sends emergencies to a human at once</li></ul></div>
<div class="call" role="img" aria-label="Illustration of a call: the agent checks, refunds, and emails a confirmation"><div class="call-h"><i></i>On the call: Priya Beauty Salon<em>Illustration</em></div>
<ol><li>Checking recent payments</li><li>Refunding the payment</li><li>Sending you a confirmation</li><li>Closing the ticket</li></ol>
<div class="mail"><small>Confirmation emailed to you</small>A refund of INR 850 has been initiated for your failed payment.</div></div></div></section>

<section class="sec" id="how" aria-labelledby="h-how"><div class="wrap"><p class="eyebrow">HOW IT WORKS</p><h2 id="h-how">From a phone call to a closed ticket</h2>
<p class="intro">One continuous workflow, with a person brought in whenever it matters.</p><ol class="grid g4" style="list-style:none;padding:0;margin:0">{steps}</ol></div></section>

<section class="sec alt" id="capabilities" aria-labelledby="h-cap"><div class="wrap"><p class="eyebrow">CAPABILITIES</p><h2 id="h-cap">Built to act, and to know when not to</h2>
<p class="intro">The model proposes. Deterministic code decides what is allowed, so safety does not depend on the prompt.</p><ul class="grid g3" style="list-style:none;padding:0;margin:0">{caps}</ul></div></section>

<section class="sec" id="console" aria-labelledby="h-con"><div class="wrap"><p class="eyebrow">OPS CONSOLE</p><h2 id="h-con">Every call, step and escalation in one place</h2>
<p class="intro">Support leads see what the AI did and why, and people pick up the cases that need them, with the full story.</p>
<div class="preview" role="img" aria-label="Illustrative preview of the ops console with sample data"><div class="pbar"><i></i><i></i><i></i><span>Ops console</span><em>Illustrative sample data</em></div>
<div class="pbody"><div class="stats"><div class="stat"><small>Calls handled</small><b>24</b></div><div class="stat"><small>Closed by AI</small><b>19</b></div><div class="stat"><small>Open escalations</small><b>2</b></div><div class="stat"><small>Unsafe actions</small><b>0</b></div></div>
<div class="rows"><div class="row"><span>Failed payment, customer debited<small>Refunded INR 850, confirmation emailed</small></span><em class="tag t-ok">Resolved by AI</em></div>
<div class="row"><span>Refund request above the limit<small>Blocked by the guardrail, case sent to a person</small></span><em class="tag t-warn">Escalated</em></div>
<div class="row"><span>Merchant reports a hacked account<small>Support inbox alerted by email</small></span><em class="tag t-bad">Emergency</em></div></div></div></div></div></section>

<section class="sec alt" id="honest" aria-labelledby="h-real"><div class="wrap"><p class="eyebrow">TRANSPARENCY</p><h2 id="h-real">What is real, and what is simulated</h2><p class="intro">This is a hackathon build, and it says so.</p>
<div class="honest"><div class="card"><h3>Real</h3><ul><li>The phone call to the merchant, in Hindi or English</li><li>The confirmation and acknowledgement emails</li><li>The guardrails, the audit log and the escalation to a human</li></ul></div>
<div class="card"><h3>Simulated for the demo</h3><ul><li>Payments, settlements and soundbox devices</li><li>The merchants and their data</li><li>Paytm's internal systems, which are not connected</li></ul></div></div></div></section>

<section class="sec"><div class="wrap"><div class="signin"><h2>Ready to take a look?</h2><p>Sign in with an approved Google account to place a test call and open the ops console.</p>
<a class="btn primary lg" href="/auth/google">{GOOGLE}Sign in with Google</a></div></div></section>
</main>
<footer><div class="wrap">Paytm AI Teammate · Track 3: Autonomous AI Teammates · Paytm AI Hackathon · Build for India</div></footer></body></html>"""
