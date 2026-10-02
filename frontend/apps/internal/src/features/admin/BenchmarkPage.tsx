import { CheckCircle2, CircleSlash, FlaskConical, Loader2, Play, ShieldCheck, XCircle } from 'lucide-react'
import { useState } from 'react'
import { errorMessage } from '@pricepolicy/api-client/errors'
import { useRunBenchmark } from '@pricepolicy/api-client/hooks'
import { EmptyState, ErrorState, LoadingState, PageHeader, StatCard } from '@pricepolicy/ui/components/common/PageStates'
import { MoneyText } from '@pricepolicy/ui/components/common/MoneyText'
import { Badge } from '@pricepolicy/ui/components/ui/badge'
import { Button } from '@pricepolicy/ui/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@pricepolicy/ui/components/ui/table'
import { formatDateTime, formatPercent, formatVnd } from '@pricepolicy/ui/lib/format'

/** Formula Regression Benchmark 1-click (MVP-05) — 17 golden case, so khớp tuyệt đối Δ = 0 VNĐ. */
export function BenchmarkPage() {
  const run = useRunBenchmark()
  const [count, setCount] = useState(0)
  const data = run.data

  return (
    <div className="space-y-6">
      <PageHeader
        title="Kiểm thử công thức"
        description="Chạy lại 17 ca vàng FCS v2.6 trên engine tính giá thật — mỗi ca phải khớp tuyệt đối Δ = 0 VNĐ."
        actions={
          <Button
            onClick={() => {
              setCount((c) => c + 1)
              run.mutate(count + 1)
            }}
            disabled={run.isPending}
            data-testid="run-benchmark"
          >
            {run.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />} Chạy 17 ca kiểm thử
          </Button>
        }
      />
      {run.isError && <ErrorState error={new Error(errorMessage(run.error))} onRetry={() => run.mutate(count)} />}
      {!data && !run.isError && (run.isPending ? <LoadingState label="Đang chạy kiểm thử…" /> : <EmptyState icon={FlaskConical} title="Chưa chạy lần nào trong phiên" />)}
      {data && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard label="Khớp tuyệt đối" value={`${data.passed}/${data.total}`} tone={data.passed === data.total ? 'success' : 'danger'} />
            <StatCard label="Tỷ lệ" value={formatPercent(data.exact_match_rate)} />
            <StatCard label="Tổng sai lệch" value={formatVnd(data.cases.reduce((s, c) => s + c.delta_vnd, 0))} />
            <StatCard label="Lần chạy" value={data.run_id} hint={formatDateTime(data.finished_at)} />
          </div>
          {data.policy_id && (
            <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card px-4 py-3 text-sm">
              <ShieldCheck className="h-4 w-4 text-muted-foreground" />
              <span className="text-muted-foreground">Văn bản đối chiếu:</span>
              <span className="font-medium">
                {data.policy_id} · {data.policy_version}
              </span>
              {data.policy_alignment === 'MATCH' ? (
                <Badge variant="success" data-testid="policy-alignment">
                  Khớp bộ ca vàng {data.golden_policy_ref}
                </Badge>
              ) : (
                <Badge variant="warning" data-testid="policy-alignment">
                  Lệch bộ ca vàng {data.golden_policy_ref} — cần cập nhật golden fixture
                </Badge>
              )}
            </div>
          )}
          <div className="overflow-x-auto rounded-xl border border-border bg-card">
            <Table data-testid="benchmark-table">
              <TableHeader>
                <TableRow>
                  <TableHead>Ca</TableHead>
                  <TableHead className="text-right">Giá niêm yết</TableHead>
                  <TableHead className="text-right">Kỳ vọng</TableHead>
                  <TableHead className="text-right">Thực tế</TableHead>
                  <TableHead className="text-right">Δ</TableHead>
                  <TableHead className="text-right">Thời gian</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.cases.map((c) => (
                  <TableRow key={c.case_id} data-testid={`benchmark-row-${c.case_id}`}>
                    <TableCell>
                      <p className="font-medium">{c.case_id}</p>
                      <p className="text-xs text-muted-foreground">{c.name}</p>
                    </TableCell>
                    <TableCell className="text-right">
                      <MoneyText amount={c.listed_price_before_tax_vnd} size="sm" />
                    </TableCell>
                    {c.actual ? (
                      <>
                        <TableCell className="text-right">
                          <MoneyText amount={c.expected?.total_contract_price_vnd ?? 0} size="sm" />
                        </TableCell>
                        <TableCell className="text-right">
                          <MoneyText amount={c.actual.total_contract_price_vnd} size="sm" />
                        </TableCell>
                      </>
                    ) : (
                      <TableCell className="text-right text-xs text-muted-foreground" colSpan={2}>
                        Chặn nghiệp vụ trước khi tính giá — không có số tiền để đối soát
                      </TableCell>
                    )}
                    <TableCell className="text-right tabular-nums">{c.delta_vnd}</TableCell>
                    <TableCell className="text-right tabular-nums text-xs text-muted-foreground">
                      {c.execution_time_ms === undefined ? '—' : `${c.execution_time_ms.toFixed(1)} ms`}
                    </TableCell>
                    <TableCell>
                      {c.passed ? (
                        c.status === 'EXCEPTION_HANDLED' ? (
                          <CircleSlash className="h-4 w-4 text-muted-foreground" aria-label="Chặn nghiệp vụ đúng" />
                        ) : (
                          <CheckCircle2 className="h-4 w-4 text-success" aria-label="Đạt" />
                        )
                      ) : (
                        <XCircle className="h-4 w-4 text-destructive" aria-label="Không đạt" />
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </>
      )}
    </div>
  )
}
