import type { ComponentType } from 'react'

export interface SlashCommand {
  cmd: string
  label: string
  hint?: string
  /** Từ khoá phụ để tìm kiếm không dấu (ví dụ "khach", "bao gia"). */
  keywords?: string[]
  icon?: ComponentType<{ className?: string }>
}

/** Bỏ dấu tiếng Việt để gõ "bao gia" vẫn khớp "/baogia". */
export const normalizeCommandText = (text: string) =>
  text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')

export function filterCommands(commands: SlashCommand[], query: string): SlashCommand[] {
  const needle = normalizeCommandText(query.replace(/^\//, '').trim())
  if (!needle) return commands
  return commands.filter((c) => {
    const haystack = normalizeCommandText([c.cmd, c.label, ...(c.keywords ?? [])].join(' '))
    return needle.split(/\s+/).every((token) => haystack.includes(token))
  })
}
