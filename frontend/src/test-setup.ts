import '@testing-library/jest-dom/vitest'

class RO { observe() {} unobserve() {} disconnect() {} }
globalThis.ResizeObserver = globalThis.ResizeObserver ?? (RO as unknown as typeof ResizeObserver)

const store = new Map<string, string>()
Object.defineProperty(globalThis, 'localStorage', {
  value: { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => void store.set(k, v), removeItem: (k: string) => void store.delete(k), clear: () => store.clear() },
})

// jsdom has no layout: scrolling is a no-op in tests
Element.prototype.scrollIntoView = Element.prototype.scrollIntoView ?? (() => {})
