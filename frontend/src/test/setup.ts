/**
 * Vitest 全局 setup。
 * - 注册 jest-dom 的 vitest 版匹配器（toBeInTheDocument 等）
 * - 每个 case 后自动卸载 React 组件，避免跨用例污染
 * - mock window.matchMedia（antd responsiveObserver 依赖，jsdom 默认无）
 */
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

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
    dispatchEvent: () => false,
  }),
})

afterEach(() => {
  cleanup()
})
