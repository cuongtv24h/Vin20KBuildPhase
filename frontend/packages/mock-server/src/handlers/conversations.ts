import type { CopilotConversationDetail, CopilotConversationMessage, CopilotConversationSummary } from '@pricepolicy/api-client/contracts'
import { onReset } from '../db'
import { MockError, notFound } from '../services/errors'
import { route } from './route'

/**
 * Lịch sử hội thoại Copilot (mock) — song song với `src/api/endpoints/copilot.py`.
 *
 * Vì sao cần: hội thoại trước đây chỉ sống trong state React nên đổi trang là mất. Mock giữ
 * hội thoại **theo từng nhân viên** trong bộ nhớ tiến trình, đủ để dev/demo thấy đúng hành vi
 * "rời trang → quay lại vẫn còn, tra cứu được cuộc cũ".
 */

const MAX_CONVERSATIONS_PER_USER = 50
const MAX_MESSAGES = 200

interface StoredConversation {
  conversation_id: string
  user_id: string
  title: string
  created_at: string
  updated_at: string
  messages: CopilotConversationMessage[]
}

let conversations: StoredConversation[] = []
let seq = 0

onReset(() => {
  conversations = []
  seq = 0
})

const nowIso = () => new Date().toISOString()

const titleFrom = (text: string) => {
  const clean = text.replace(/\s+/g, ' ').trim()
  if (!clean) return 'Cuộc trò chuyện mới'
  return clean.length <= 80 ? clean : `${clean.slice(0, 79).trimEnd()}…`
}

const toSummary = (c: StoredConversation): CopilotConversationSummary => ({
  conversation_id: c.conversation_id,
  title: c.title,
  created_at: c.created_at,
  updated_at: c.updated_at,
  message_count: c.messages.length,
  last_message: [...c.messages].reverse().find((m) => m.role === 'assistant')?.content.slice(0, 160) ?? '',
})

const toDetail = (c: StoredConversation): CopilotConversationDetail => ({ ...toSummary(c), messages: c.messages })

const mine = (userId: string) => conversations.filter((c) => c.user_id === userId)

function trim(userId: string) {
  const own = mine(userId)
  if (own.length <= MAX_CONVERSATIONS_PER_USER) return
  const keep = new Set(
    [...own].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).slice(0, MAX_CONVERSATIONS_PER_USER).map((c) => c.conversation_id),
  )
  conversations = conversations.filter((c) => c.user_id !== userId || keep.has(c.conversation_id))
}

export const conversationHandlers = [
  route('copilotConversations', ({ staff }) => {
    const items = mine(staff().user_id)
      .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
      .slice(0, 30)
      .map(toSummary)
    return { body: { total: items.length, items } }
  }),

  route('copilotConversationCreate', ({ staff, now }) => {
    const conversation: StoredConversation = {
      conversation_id: `CNV-${String((seq += 1)).padStart(6, '0')}`,
      user_id: staff().user_id,
      title: 'Cuộc trò chuyện mới',
      created_at: new Date(now).toISOString(),
      updated_at: new Date(now).toISOString(),
      messages: [],
    }
    conversations = [conversation, ...conversations]
    trim(conversation.user_id)
    return { status: 201, body: toDetail(conversation) }
  }),

  route('copilotConversationDetail', ({ params, staff }) => {
    const conversation = mine(staff().user_id).find((c) => c.conversation_id === params.conversation_id)
    if (!conversation) throw notFound('cuộc hội thoại')
    return { body: toDetail(conversation) }
  }),

  route('copilotConversationTurn', async ({ staff, json, now }) => {
    const body = await json<{
      conversation_id?: string | null
      user_message: string
      assistant_message: string
      citations?: unknown[]
      action_type?: string | null
    }>()
    if (!body?.user_message?.trim() && !body?.assistant_message?.trim()) {
      throw new MockError(422, 'INPUT_VALIDATION_ERROR', 'Lượt hội thoại phải có nội dung.')
    }
    const userId = staff().user_id
    let conversation = body.conversation_id ? mine(userId).find((c) => c.conversation_id === body.conversation_id) : undefined
    if (!conversation) {
      conversation = {
        conversation_id: `CNV-${String((seq += 1)).padStart(6, '0')}`,
        user_id: userId,
        title: titleFrom(body.user_message),
        created_at: new Date(now).toISOString(),
        updated_at: new Date(now).toISOString(),
        messages: [],
      }
      conversations = [conversation, ...conversations]
    }
    const at = new Date(now).toISOString()
    if (body.user_message?.trim()) conversation.messages.push({ role: 'user', content: body.user_message.trim(), at })
    if (body.assistant_message?.trim()) {
      conversation.messages.push({
        role: 'assistant',
        content: body.assistant_message.trim(),
        at,
        citations: (body.citations as CopilotConversationMessage['citations']) ?? [],
        action_type: body.action_type ?? null,
      })
    }
    conversation.messages = conversation.messages.slice(-MAX_MESSAGES)
    if (conversation.title === 'Cuộc trò chuyện mới' && body.user_message?.trim()) conversation.title = titleFrom(body.user_message)
    conversation.updated_at = at
    trim(userId)
    return { status: 201, body: toDetail(conversation) }
  }),

  route('copilotConversationRename', async ({ params, staff, json, now }) => {
    const body = await json<{ title: string }>()
    const conversation = mine(staff().user_id).find((c) => c.conversation_id === params.conversation_id)
    if (!conversation) throw notFound('cuộc hội thoại')
    conversation.title = body?.title?.trim() || conversation.title
    conversation.updated_at = new Date(now).toISOString()
    return { body: toSummary(conversation) }
  }),

  route('copilotConversationDelete', ({ params, staff }) => {
    const userId = staff().user_id
    const existing = mine(userId).find((c) => c.conversation_id === params.conversation_id)
    if (!existing) throw notFound('cuộc hội thoại')
    conversations = conversations.filter((c) => !(c.user_id === userId && c.conversation_id === params.conversation_id))
    return { body: { ok: true, conversation_id: params.conversation_id } }
  }),
]
