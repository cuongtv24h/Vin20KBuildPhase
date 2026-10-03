import { registerSeeder } from '../db'
import { buildSeedState } from '../seed'
import { adminCpHandlers } from './admin_cp'
import { catalogHandlers } from './catalog'
import { conversationHandlers } from './conversations'
import { copilotHandlers } from './copilot'
import { llmAdminHandlers } from './llmAdmin'
import { ttsHandlers } from './tts'
import { ttsAdminHandlers, ttsSpeakHandlers } from './ttsAdmin'
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
  ...conversationHandlers,
  ...llmAdminHandlers,
  ...ttsHandlers,
  ...ttsAdminHandlers,
  ...ttsSpeakHandlers,
  ...adminCpHandlers,
  ...devtoolHandlers,
]
