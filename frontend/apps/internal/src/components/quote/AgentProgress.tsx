import { CheckCircle2, Circle, Loader2, RefreshCw, ShieldAlert, Wifi, WifiOff } from 'lucide-react'
import type { AgentProgress as Progress } from '@pricepolicy/api-client/hooks'
import { AGENT_STEPS } from '@pricepolicy/api-client/contracts'
import { Alert, AlertDescription, AlertTitle } from '@pricepolicy/ui/components/ui/alert'
import { Button } from '@pricepolicy/ui/components/ui/button'
import { Card, CardContent } from '@pricepolicy/ui/components/ui/card'
import { AGENT_STEP_LABEL } from '@pricepolicy/ui/lib/labels'
import { cn } from '@pricepolicy/ui/lib/utils'

const CONNECTION: Record<Progress['connection'], { label: string; tone: string; live: boolean }> = {
  idle: { label: 'Đang chuẩn bị', tone: 'text-muted-foreground', live: false },
  connecting: { label: 'Đang kết nối', tone: 'text-muted-foreground', live: false },
  open: { label: 'Trực tiếp', tone: 'text-success', live: true },
  reconnecting: { label: 'Đang kết nối lại', tone: 'text-warning', live: false },
  resyncing: { label: 'Đang đồng bộ lại', tone: 'text-warning', live: false },
  closed: { label: 'Đã đóng', tone: 'text-muted-foreground', live: false },
  unauthorized: { label: 'Phiên hết hạn', tone: 'text-destructive', live: false },
}

/** Tiến trình Agent theo SSE — không hiển thị suy luận kỹ thuật, chỉ các bước nghiệp vụ. */
export function AgentProgress({ progress, onRecheck }: { progress: Progress; onRecheck: () => void }) {
  const conn = CONNECTION[progress.connection]
  const nextIndex = progress.completedSteps.length

  if (progress.timedOut) {
    return (
      <Alert variant="destructive" data-testid="analysis-timeout">
        <ShieldAlert />
        <AlertTitle>Quá 10 giây chưa có kết quả — đã dừng chờ</AlertTitle>
        <AlertDescription className="space-y-3 text-foreground/80">
          <p>Hồ sơ không được tính giá tạm hay suy đoán. Kết quả sẽ tự cập nhật nếu hệ thống hoàn tất sau đó.</p>
          <Button variant="outline" size="sm" onClick={onRecheck}>
            <RefreshCw className="h-4 w-4" /> Kiểm tra lại
          </Button>
        </AlertDescription>
      </Alert>
    )
  }

  return (
    <Card data-testid="agent-progress">
      <CardContent className="space-y-4 p-5">
        <div className="flex items-center justify-between">
          <p className="font-medium">Đang phân tích hồ sơ</p>
          <span className={cn('inline-flex items-center gap-1.5 text-xs font-medium', conn.tone)} data-connection={progress.connection}>
            {conn.live ? <Wifi className="h-3.5 w-3.5" /> : <WifiOff className="h-3.5 w-3.5" />}
            {conn.label}
            {progress.reconnects > 0 && <span className="text-muted-foreground">· nối lại {progress.reconnects} lần</span>}
          </span>
        </div>
        <ol className="grid gap-3 sm:grid-cols-3">
          {AGENT_STEPS.map((step, i) => {
            const done = progress.completedSteps.includes(step)
            const running = !done && i === nextIndex && !progress.finalStatus
            return (
              <li key={step} className="flex items-start gap-2" data-step={step} data-state={done ? 'done' : running ? 'running' : 'pending'}>
                {done ? (
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                ) : running ? (
                  <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-primary" />
                ) : (
                  <Circle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground/40" />
                )}
                <span className={cn('text-sm leading-tight', done || running ? 'font-medium' : 'text-muted-foreground')}>{AGENT_STEP_LABEL[step]}</span>
              </li>
            )
          })}
        </ol>
        <div className="h-1 overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-primary transition-all duration-700"
            style={{ width: `${progress.finalStatus ? 100 : Math.max(8, (nextIndex / (AGENT_STEPS.length + 1)) * 100)}%` }}
          />
        </div>
      </CardContent>
    </Card>
  )
}
