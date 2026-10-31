import { useEffect, useRef } from 'react'

/** A quiet living background: drifting points that join up when close and lean away from the pointer. Pure canvas, no dependencies.
 *  Skips itself under reduced motion (draws one still frame), pauses when the tab is hidden, and caps the pixel ratio at 2. */
const COLORS: [number, number, number][] = [[0, 185, 245], [43, 79, 208], [11, 42, 111]]

type P = { x: number; y: number; vx: number; vy: number; r: number; c: [number, number, number]; a: number }

export default function Field() {
  const ref = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const canvas = ref.current
    if (!canvas || /jsdom/i.test(navigator.userAgent)) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const still = matchMedia('(prefers-reduced-motion: reduce)').matches
    let w = 0, h = 0, dpr = 1, raf = 0, pts: P[] = []
    const mouse = { x: -9999, y: -9999 }
    const rnd = (a: number, b: number) => a + Math.random() * (b - a)

    const size = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      w = innerWidth; h = innerHeight
      canvas.width = w * dpr; canvas.height = h * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      const n = Math.round(Math.min(150, Math.max(46, (w * h) / 12000)))  // fewer on small screens
      pts = Array.from({ length: n }, () => ({
        x: rnd(0, w), y: rnd(0, h), vx: rnd(-0.18, 0.18), vy: rnd(-0.14, 0.14), r: rnd(0.8, 2.3),
        c: COLORS[Math.floor(Math.random() * COLORS.length)], a: rnd(0.25, 0.7)
      }))
    }

    const draw = (move: boolean) => {
      ctx.clearRect(0, 0, w, h)
      for (const p of pts) {
        if (move) {
          const dx = p.x - mouse.x, dy = p.y - mouse.y, d2 = dx * dx + dy * dy
          if (d2 < 150 * 150) { const d = Math.sqrt(d2) || 1, f = (1 - d / 150) * 1.6; p.x += (dx / d) * f; p.y += (dy / d) * f }
          p.x += p.vx; p.y += p.vy
          if (p.x < -10) p.x = w + 10; else if (p.x > w + 10) p.x = -10
          if (p.y < -10) p.y = h + 10; else if (p.y > h + 10) p.y = -10
        }
        ctx.fillStyle = `rgba(${p.c[0]},${p.c[1]},${p.c[2]},${p.a})`
        ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, 6.2832); ctx.fill()
      }
      ctx.lineWidth = 1
      for (let i = 0; i < pts.length; i++) for (let j = i + 1; j < pts.length; j++) {
        const a = pts[i], b = pts[j], dx = a.x - b.x, dy = a.y - b.y, d2 = dx * dx + dy * dy
        if (d2 < 120 * 120) { ctx.strokeStyle = `rgba(43,79,208,${(1 - Math.sqrt(d2) / 120) * 0.16})`; ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke() }
      }
    }
    const loop = () => { draw(true); raf = requestAnimationFrame(loop) }

    let debounce = 0
    const onResize = () => { clearTimeout(debounce); debounce = window.setTimeout(() => { size(); if (still) draw(false) }, 140) }
    const onMove = (e: PointerEvent) => { mouse.x = e.clientX; mouse.y = e.clientY }
    const onLeave = () => { mouse.x = mouse.y = -9999 }
    const onVis = () => { cancelAnimationFrame(raf); if (!document.hidden && !still) raf = requestAnimationFrame(loop) }

    size()
    if (still) draw(false); else raf = requestAnimationFrame(loop)
    addEventListener('resize', onResize); addEventListener('pointermove', onMove); document.addEventListener('pointerleave', onLeave)
    document.addEventListener('visibilitychange', onVis)
    return () => {
      cancelAnimationFrame(raf); clearTimeout(debounce)
      removeEventListener('resize', onResize); removeEventListener('pointermove', onMove); document.removeEventListener('pointerleave', onLeave)
      document.removeEventListener('visibilitychange', onVis)
    }
  }, [])
  return <canvas ref={ref} className="field" aria-hidden="true" />
}
