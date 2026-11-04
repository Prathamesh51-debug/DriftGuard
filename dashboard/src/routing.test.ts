import { describe, expect, it } from 'vitest'
import { dashboardSurface, initialLiveView } from './routing'

describe('dashboardSurface', () => {
  it('opens the API-backed dashboard at the homepage and on its live route', () => {
    expect(dashboardSurface('/')).toBe('live')
    expect(dashboardSurface('/preview')).toBe('live')
    expect(dashboardSurface('/live')).toBe('live')
    expect(dashboardSurface('/live/')).toBe('live')
    expect(dashboardSurface('/typo')).toBe('not-found')
  })
})

describe('initialLiveView', () => {
  it('opens Studio from the Ask Studio deep link and defaults to runs otherwise', () => {
    expect(initialLiveView('?view=studio')).toBe('studio')
    expect(initialLiveView('?view=runs')).toBe('runs')
    expect(initialLiveView('')).toBe('runs')
  })
})
