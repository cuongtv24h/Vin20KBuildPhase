import { setupServer } from 'msw/node'
import { handlers } from './handlers'

/** Backend giả lập cho test Vitest — cùng handler với trình duyệt. */
export const server = setupServer(...handlers)
