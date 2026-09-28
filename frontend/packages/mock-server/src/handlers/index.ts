import { registerSeeder } from '../db'
import { buildSeedState } from '../seed'
import { catalogHandlers } from './catalog'
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
  ...devtoolHandlers,
]
