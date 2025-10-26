import '@testing-library/jest-dom'
import { vi } from 'vitest'

// Mock IntersectionObserver
vi.stubGlobal('IntersectionObserver', class IntersectionObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  unobserve() {}
})

// Mock ResizeObserver
vi.stubGlobal('ResizeObserver', class ResizeObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  unobserve() {}
})

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => {},
  }),
})
