import { useMemo } from 'react'
import { Clock, CornerDownLeft } from 'lucide-react'
import { cn } from '@pricepolicy/ui/lib/utils'
import { filterCommands, type SlashCommand } from '@pricepolicy/ui/lib/slashCommands'

interface SlashCommandPaletteProps {
  open: boolean
  /** Toàn bộ lệnh khả dụng. */
  commands: SlashCommand[]
  /** Chuỗi người dùng đã gõ (bắt đầu bằng "/"). */
  query: string
  /** Lệnh dùng gần đây (mới nhất trước) — hiển thị nhóm đầu. */
  recent?: string[]
  activeIndex: number
  onActiveIndexChange: (index: number) => void
  onSelect: (command: SlashCommand) => void
}

/**
 * Palette lệnh gạch chéo có tìm kiếm + điều hướng bàn phím + nhóm "dùng gần đây".
 *
 * Thay cho danh sách hardcode trước đây (không render, không tìm kiếm được): mọi lệnh đều
 * hiện ra, lọc theo từ khoá không dấu, và mục đang chọn được đánh dấu bằng aria-activedescendant.
 */
export function SlashCommandPalette({
  open,
  commands,
  query,
  recent = [],
  activeIndex,
  onActiveIndexChange,
  onSelect,
}: SlashCommandPaletteProps) {
  const filtered = useMemo(() => filterCommands(commands, query), [commands, query])
  const recentSet = useMemo(() => new Set(recent), [recent])
  const ordered = useMemo(
    () => [...filtered].sort((a, b) => Number(recentSet.has(b.cmd)) - Number(recentSet.has(a.cmd))),
    [filtered, recentSet],
  )

  if (!open) return null

  if (!ordered.length) {
    return (
      <div
        role="status"
        className="absolute bottom-full left-0 right-0 z-30 mb-2 rounded-xl border border-border bg-card p-3 text-xs text-muted-foreground shadow-lg"
      >
        Không có lệnh nào khớp “{query}”. Anh/chị cứ gõ câu tự nhiên, Copilot vẫn hiểu.
      </div>
    )
  }

  return (
    <div
      role="listbox"
      aria-label="Danh sách lệnh gạch chéo"
      aria-activedescendant={`slash-item-${activeIndex}`}
      className="absolute bottom-full left-0 right-0 z-30 mb-2 max-h-72 overflow-y-auto rounded-xl border border-border bg-card py-1 text-xs shadow-lg"
    >
      {ordered.map((command, index) => {
        const Icon = command.icon
        const isActive = index === activeIndex
        const isRecent = recentSet.has(command.cmd)
        return (
          <button
            key={command.cmd}
            id={`slash-item-${index}`}
            role="option"
            aria-selected={isActive}
            type="button"
            onMouseEnter={() => onActiveIndexChange(index)}
            onClick={() => onSelect(command)}
            className={cn(
              'flex w-full items-center gap-2.5 px-3 py-2 text-left transition-colors',
              isActive ? 'bg-primary/10' : 'hover:bg-muted/60',
            )}
          >
            {Icon ? <Icon className="h-3.5 w-3.5 shrink-0 text-primary" /> : <span className="w-3.5" />}
            <span className="min-w-0 flex-1">
              <span className="block truncate font-medium text-foreground">{command.label}</span>
              <span className="block truncate text-xs text-muted-foreground">
                {command.cmd}
                {command.hint ? ` · ${command.hint}` : ''}
              </span>
            </span>
            {isRecent && (
              <span className="flex shrink-0 items-center gap-1 rounded-full bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                <Clock className="h-3 w-3" /> gần đây
              </span>
            )}
            {isActive && <CornerDownLeft className="h-3 w-3 shrink-0 text-muted-foreground" />}
          </button>
        )
      })}
    </div>
  )
}
