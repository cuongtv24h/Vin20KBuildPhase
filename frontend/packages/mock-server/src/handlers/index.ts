import { registerSeeder } from '../db'
import { buildSeedState } from '../seed'
import { adminCpHandlers } from './admin_cp'
import { catalogHandlers } from './catalog'
import { copilotHandlers } from './copilot'
import { quoteHandlers } from './quotes'
import { adminHandlers, complianceHandlers, devtoolHandlers, leadHandlers, preSalesHandlers } from './workflows'

registerSeeder(() => buildSeedState())

export const handlers = [
  ...catalogHandlers,
  ...quoteHandlers,
  ...leadHandlers,
  ...preSalesHandlers,
  ...complianceHandlers,
  ...adminHandlers,
  ...copilotHandlers,
  ...adminCpHandlers,
  ...devtoolHandlers,
]
