/**
 * Vitest 全局 setup。
 * - 注册 jest-dom 的 vitest 版匹配器（toBeInTheDocument 等）
 * - 每个 case 后自动卸载 React 组件，避免跨用例污染
 */
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(() => {
  cleanup()
})
