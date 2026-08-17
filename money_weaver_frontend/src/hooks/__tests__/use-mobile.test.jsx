import { renderHook } from '@testing-library/react'
import { test, expect } from 'vitest'
import { useIsMobile } from '../use-mobile'

test('is not mobile at desktop width', () => {
  const { result } = renderHook(() => useIsMobile())
  expect(result.current).toBe(false)
})

test('is mobile below the breakpoint', () => {
  Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 500 })
  const { result } = renderHook(() => useIsMobile())
  expect(result.current).toBe(true)
})