import { AlertTriangle, Copy, MessageSquareWarning, RefreshCw, Sparkles, ThumbsDown, ThumbsUp } from 'lucide-react'
import { useMemo, useState } from 'react'
import { errorMessage } from '@pricepolicy/api-client/errors'
import { useCopilotFeedbackRecent, useCopilotFeedbackSummary } from '@pricepolicy/api-client/hooks'
import type { CopilotFeedbackEntry } from '@pricepolicy/api-client/contracts'
import { EmptyState, ErrorState, LoadingState, PageHeader, StatCard } from '@pricepolicy/ui/components/common/PageStates'
import { Badge } from '@pricepolicy/ui/components/ui/badge'
import { Button } from '@pricepolicy/ui/components/ui/button'
import { Card, CardContent } from '@pricepolicy/ui/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@pricepolicy/ui/components/ui/table'
import { toast } from '@pricepolicy/ui/state/toastStore'
import { cn } from '@pricepolicy/ui/lib/utils'

type RatingFilter = 'all' | -1 | 1

const FILTER_LABEL: Record<RatingFilter, string> = {
  all: 'Tất cả',
  '-1': 'Chưa đạt',
  1: 'Hữu ích',
}

const MODE_LABEL: Record<string, string> = {
  react: 'ReAct (LLM)',
  offline_react: 'ReAct dự phòng',
  guardrail: 'Guardrail chặn',
}

/**
 * Trang Quản trị chất lượng Copilot (P2 — học từ phản hồi).
 *
 * Đây là "màn hình điều khiển" cho vòng lặp cải thiện Copilot: Sale bấm 👍/👎 ở Workspace,
 * dữ liệu chảy về đây để người quản trị thấy (1) chất lượng đang đi lên hay xuống,
 * (2) Copilot hay trả lời kém ở nhóm câu hỏi / tool nào, (3) nguyên văn lượt bị chê để sửa prompt.
 *
 * Lưu ý quyền riêng tư: nội dung hội thoại đã được **server che PII** (SĐT/email) trước khi trả về;
 * trang này không gọi API nào khác và không hiển thị dữ liệu khách.
 */
export function CopilotQualityPage() {
  const [filter, setFilter] = useState<RatingFilter>('all')
  const summary = useCopilotFeedbackSummary()
  const recent = useCopilotFeedbackRecent(filter === 'all' ? { limit: 50 } : { limit: 50, rating: filter })

  const data = summary.data
  const items = recent.data?.items ?? []

  const trend = useMemo(() => {
    const rows = data?.by_day ?? []
    const max = Math.max(1, ...rows.map((r) => r.up + r.down))
    return { rows, max }
  }, [data])

  const copyEntry = (entry: CopilotFeedbackEntry) => {
    const lines = [
      `Thời điểm: ${entry.recorded_at ?? '—'}`,
      `Câu hỏi: ${entry.message}`,
      `Trả lời: ${entry.reply || '(trống)'}`,
      entry.comment ? `Lý do Sale nêu: ${entry.comment}` : null,
      entry.tags.length ? `Nhãn: ${entry.tags.join(', ')}` : null,
      `Chế độ: ${MODE_LABEL[entry.mode ?? ''] ?? entry.mode ?? '—'}`,
    ].filter(Boolean)
    void navigator.clipboard?.writeText(lines.join('\n')).then(
      () => toast.success('Đã sao chép lượt phản hồi để đưa vào biên bản cải tiến'),
      () => toast.error('Trình duyệt chặn clipboard — anh/chị sao chép thủ công'),
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Chất lượng trợ lý"
        title="Đánh giá chất lượng Copilot"
        description="Tổng hợp phản hồi 👍/👎 của Sale ở Sales Workspace. Dữ liệu này cũng được nạp lại vào prompt dưới dạng “điều cần tránh”."
        actions={
          <Button variant="outline" onClick={() => void Promise.all([summary.refetch(), recent.refetch()])} disabled={summary.isFetching || recent.isFetching}>
            <RefreshCw className={cn('h-4 w-4', (summary.isFetching || recent.isFetching) && 'animate-spin')} /> Làm mới
          </Button>
        }
      />

      {summary.isLoading && <LoadingState label="Đang tải thống kê chất lượng…" />}
      {summary.isError && <ErrorState error={new Error(errorMessage(summary.error))} onRetry={() => void summary.refetch()} />}

      {data && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard
              label="Tổng phản hồi"
              value={data.total}
              hint={`${data.up} hữu ích · ${data.down} chưa đạt · ${data.neutral} trung tính`}
              icon={Sparkles}
            />
            <StatCard
              label="Tỉ lệ hài lòng"
              value={data.satisfaction_rate === null ? '—' : `${Math.round(data.satisfaction_rate * 100)}%`}
              tone={
                data.satisfaction_rate === null ? 'default' : data.satisfaction_rate >= 0.8 ? 'success' : data.satisfaction_rate >= 0.6 ? 'warning' : 'danger'
              }
              hint={data.up + data.down > 0 ? `trên ${data.up + data.down} lượt có đánh giá` : 'chưa có lượt nào được đánh giá'}
              icon={ThumbsUp}
            />
            <StatCard label="Lượt chưa đạt" value={data.down} tone={data.down > 0 ? 'danger' : 'default'} icon={ThumbsDown} />
            <StatCard
              label="Nhãn bị chê nhiều nhất"
              value={data.top_negative_tags[0]?.[0] ?? '—'}
              hint={data.top_negative_tags[0] ? `${data.top_negative_tags[0][1]} lượt` : 'chưa ghi nhận nhãn nào'}
              tone="warning"
              icon={AlertTriangle}
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardContent className="space-y-3 p-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold">Xu hướng 14 ngày</p>
                  <span className="text-[11px] text-muted-foreground">
                    <span className="mr-2 inline-block h-2 w-2 rounded-sm bg-success align-middle" /> hữu ích
                    <span className="mx-2 ml-4 inline-block h-2 w-2 rounded-sm bg-destructive align-middle" /> chưa đạt
                  </span>
                </div>
                {trend.rows.length === 0 ? (
                  <p className="py-6 text-center text-xs text-muted-foreground">Chưa có phản hồi nào để vẽ xu hướng.</p>
                ) : (
                  <div className="flex h-32 items-end gap-1.5" role="img" aria-label="Biểu đồ phản hồi 14 ngày gần nhất">
                    {trend.rows.map((row) => {
                      const total = row.up + row.down
                      return (
                        <div key={row.date} className="flex flex-1 flex-col items-center gap-1" title={`${row.date}: ${row.up} hữu ích · ${row.down} chưa đạt`}>
                          <div className="flex w-full flex-col justify-end gap-0.5" style={{ height: '100px' }}>
                            <div className="w-full rounded-t-sm bg-destructive/80" style={{ height: `${(row.down / trend.max) * 100}%` }} />
                            <div className="w-full rounded-b-sm bg-success/80" style={{ height: `${(row.up / trend.max) * 100}%` }} />
                          </div>
                          <span className={cn('text-[9px] tabular-nums', total === 0 ? 'text-muted-foreground/50' : 'text-muted-foreground')}>
                            {row.date.slice(8)}
                          </span>
                        </div>
                      )
                    })}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardContent className="space-y-3 p-4">
                <p className="text-sm font-semibold">Cần cải thiện ở đâu</p>
                <div className="space-y-2 text-xs">
                  <div>
                    <p className="mb-1 text-[11px] font-medium text-muted-foreground">Tool xuất hiện ở lượt bị chê</p>
                    {(data.top_failing_tools ?? []).length === 0 ? (
                      <p className="text-muted-foreground">Chưa có dữ liệu.</p>
                    ) : (
                      <ul className="space-y-1">
                        {(data.top_failing_tools ?? []).map(([tool, count]) => (
                          <li key={tool} className="flex items-center justify-between gap-2">
                            <code className="truncate rounded bg-muted px-1.5 py-0.5 text-[11px]">{tool}</code>
                            <span className="shrink-0 tabular-nums text-muted-foreground">{count} lượt</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                  <div>
                    <p className="mb-1 text-[11px] font-medium text-muted-foreground">Chế độ trả lời</p>
                    {(data.by_mode ?? []).length === 0 ? (
                      <p className="text-muted-foreground">Chưa có dữ liệu.</p>
                    ) : (
                      <ul className="space-y-1">
                        {(data.by_mode ?? []).map((row) => (
                          <li key={row.mode} className="flex items-center justify-between gap-2">
                            <span>{MODE_LABEL[row.mode] ?? row.mode}</span>
                            <span className="tabular-nums text-muted-foreground">{row.count}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </>
      )}

      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm font-semibold">Phản hồi chi tiết</p>
          <div className="flex gap-1.5">
            {(['all', -1, 1] as RatingFilter[]).map((value) => (
              <Button
                key={String(value)}
                size="sm"
                variant={filter === value ? 'default' : 'outline'}
                className="h-7 text-xs"
                onClick={() => setFilter(value)}
              >
                {FILTER_LABEL[value]}
              </Button>
            ))}
          </div>
        </div>

        {recent.isLoading && <LoadingState label="Đang tải phản hồi…" />}
        {recent.isError && <ErrorState error={new Error(errorMessage(recent.error))} onRetry={() => void recent.refetch()} />}
        {!recent.isLoading && !recent.isError && items.length === 0 && (
          <EmptyState
            icon={MessageSquareWarning}
            title="Chưa có phản hồi nào khớp bộ lọc"
            description="Sale bấm 👍/👎 ngay dưới câu trả lời của Copilot ở Sales Workspace; phản hồi sẽ hiện ở đây kèm nội dung đã che PII."
          />
        )}

        {items.length > 0 && (
          <div className="overflow-x-auto rounded-xl border border-border bg-card">
            <Table data-testid="copilot-feedback-table">
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[130px]">Thời điểm</TableHead>
                  <TableHead>Nội dung lượt hỏi — trả lời</TableHead>
                  <TableHead className="w-[190px]">Đánh giá</TableHead>
                  <TableHead className="w-[120px]">Chế độ</TableHead>
                  <TableHead className="w-[60px]" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((entry, idx) => (
                  <TableRow key={`${entry.recorded_at}-${idx}`}>
                    <TableCell className="align-top text-[11px] text-muted-foreground">
                      {entry.recorded_at ? entry.recorded_at.replace('T', ' ').slice(0, 16) : '—'}
                    </TableCell>
                    <TableCell className="align-top">
                      <p className="text-xs font-medium text-foreground">{entry.message}</p>
                      <p className="mt-1 line-clamp-3 text-[11px] text-muted-foreground">{entry.reply || '(Copilot không có nội dung)'}</p>
                      {entry.tools_used.length > 0 && (
                        <p className="mt-1 flex flex-wrap gap-1">
                          {entry.tools_used.map((tool) => (
                            <code key={tool} className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                              {tool}
                            </code>
                          ))}
                        </p>
                      )}
                    </TableCell>
                    <TableCell className="align-top">
                      <Badge variant={entry.rating > 0 ? 'success' : entry.rating < 0 ? 'danger' : 'outline'} className="gap-1">
                        {entry.rating > 0 ? <ThumbsUp className="h-3 w-3" /> : entry.rating < 0 ? <ThumbsDown className="h-3 w-3" /> : null}
                        {entry.rating > 0 ? 'Hữu ích' : entry.rating < 0 ? 'Chưa đạt' : 'Trung tính'}
                      </Badge>
                      {entry.comment && <p className="mt-1 text-[11px] text-muted-foreground">“{entry.comment}”</p>}
                      {entry.tags.length > 0 && (
                        <p className="mt-1 flex flex-wrap gap-1">
                          {entry.tags.map((tag) => (
                            <span key={tag} className="rounded-full bg-warning/15 px-1.5 py-0.5 text-[10px] text-warning">
                              {tag}
                            </span>
                          ))}
                        </p>
                      )}
                    </TableCell>
                    <TableCell className="align-top text-[11px]">{MODE_LABEL[entry.mode ?? ''] ?? entry.mode ?? '—'}</TableCell>
                    <TableCell className="align-top">
                      <Button size="icon" variant="ghost" className="h-7 w-7" title="Sao chép lượt này" onClick={() => copyEntry(entry)}>
                        <Copy className="h-3.5 w-3.5" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </div>
  )
}
