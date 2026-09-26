import { CheckCircle2, FlaskConical, Loader2, XCircle } from 'lucide-react'
import { errorMessage } from '@/api/errors'
import { useRunFormulaRegression } from '@/api/hooks'
import { EmptyState, PageHeader } from '@/components/common/PageStates'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { summarizeBenchmark } from '@/engine/benchmark'
import { formatNumber } from '@/lib/format'

export function FormulaTestsPage() {
  const run = useRunFormulaRegression()
  const results = run.data
  const summary = results ? summarizeBenchmark(results) : null

  return (
    <div className="space-y-6">
      <PageHeader
        title="Kiểm thử công thức"
        description="Bộ ca kiểm thử cố định đối soát công thức tính giá (chiết khấu → trước thuế → VAT 10% → KPBT 2%)."
        actions={
          <Button onClick={() => run.mutate()} disabled={run.isPending}>
            {run.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <FlaskConical className="h-4 w-4" />} Chạy kiểm thử
          </Button>
        }
      />
      {run.isError && <p className="text-sm text-destructive">{errorMessage(run.error)}</p>}

      {summary && (
        <Card className={summary.exactMatchRate === 1 ? 'border-success/40 bg-success/5' : 'border-destructive/40 bg-destructive/5'}>
          <CardContent className="space-y-3 p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="inline-flex items-center gap-2 font-display text-2xl font-semibold tabular-nums">
                {summary.exactMatchRate === 1 ? <CheckCircle2 className="h-5 w-5 text-success" /> : <XCircle className="h-5 w-5 text-destructive" />}
                {(summary.exactMatchRate * 100).toFixed(0)}% khớp tuyệt đối
              </p>
              <p className="text-sm text-muted-foreground">
                {summary.passedCount}/{summary.total} ca kiểm thử
              </p>
            </div>
            <Progress value={summary.exactMatchRate * 100} />
          </CardContent>
        </Card>
      )}

      {results ? (
        <div className="overflow-x-auto rounded-xl border border-border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Mã</TableHead>
                <TableHead>Mô tả</TableHead>
                <TableHead className="text-right">Kỳ vọng</TableHead>
                <TableHead className="text-right">Thực tế</TableHead>
                <TableHead className="text-right">Sai lệch</TableHead>
                <TableHead>Kết quả</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {results.map((r) => (
                <TableRow key={r.case.id}>
                  <TableCell className="font-medium">{r.case.id}</TableCell>
                  <TableCell className="max-w-xs text-xs text-muted-foreground">{r.case.name}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatNumber(r.case.expected.netPrice)}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatNumber(r.actual.netPrice)}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatNumber(r.deltaVnd)}</TableCell>
                  <TableCell>
                    {r.passed ? (
                      <Badge variant="success">
                        <CheckCircle2 className="h-3 w-3" /> Đạt
                      </Badge>
                    ) : (
                      <Badge variant="danger">
                        <XCircle className="h-3 w-3" /> Lệch
                      </Badge>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : (
        !run.isPending && <EmptyState icon={FlaskConical} title="Chưa chạy kiểm thử" />
      )}
    </div>
  )
}
