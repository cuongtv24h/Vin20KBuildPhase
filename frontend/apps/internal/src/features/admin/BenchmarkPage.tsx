import { CheckCircle2, FlaskConical, Loader2, Play, XCircle } from 'lucide-react'
import { useState } from 'react'
import { errorMessage } from '@pricepolicy/api-client/errors'
import { useRunBenchmark } from '@pricepolicy/api-client/hooks'
import { EmptyState, ErrorState, LoadingState, PageHeader, StatCard } from '@pricepolicy/ui/components/common/PageStates'
import { MoneyText } from '@pricepolicy/ui/components/common/MoneyText'
import { Button } from '@pricepolicy/ui/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@pricepolicy/ui/components/ui/table'
import { formatDateTime, formatPercent, formatVnd } from '@pricepolicy/ui/lib/format'

/** Formula Regression Benchmark 1-click (MVP-05) — 15 golden case, so khớp tuyệt đối Δ = 0 VNĐ. */
export function BenchmarkPage() {
  const run = useRunBenchmark()
  const [count, setCount] = useState(0)
  const data = run.data

  return (
    <div className="space-y-6">
      <PageHeader
        title="Kiểm thử công thức"
        actions={
          <Button
            onClick={() => {
              setCount((c) => c + 1)
              run.mutate(count + 1)
            }}
            disabled={run.isPending}
            data-testid="run-benchmark"
          >
            {run.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />} Chạy 15 ca kiểm thử
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
          <div className="overflow-x-auto rounded-xl border border-border bg-card">
            <Table data-testid="benchmark-table">
              <TableHeader>
                <TableRow>
                  <TableHead>Ca</TableHead>
                  <TableHead className="text-right">Giá niêm yết</TableHead>
                  <TableHead className="text-right">Kỳ vọng</TableHead>
                  <TableHead className="text-right">Thực tế</TableHead>
                  <TableHead className="text-right">Δ</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.cases.map((c) => (
                  <TableRow key={c.case_id}>
                    <TableCell>
                      <p className="font-medium">{c.case_id}</p>
                      <p className="text-xs text-muted-foreground">{c.name}</p>
                    </TableCell>
                    <TableCell className="text-right">
                      <MoneyText amount={c.listed_price_before_tax_vnd} size="sm" />
                    </TableCell>
                    <TableCell className="text-right">
                      <MoneyText amount={c.expected.total_contract_price_vnd} size="sm" />
                    </TableCell>
                    <TableCell className="text-right">
                      <MoneyText amount={c.actual.total_contract_price_vnd} size="sm" />
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{c.delta_vnd}</TableCell>
                    <TableCell>{c.passed ? <CheckCircle2 className="h-4 w-4 text-success" /> : <XCircle className="h-4 w-4 text-destructive" />}</TableCell>
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
