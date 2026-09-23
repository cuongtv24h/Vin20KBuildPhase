import { CheckCircle2, FlaskConical, XCircle } from 'lucide-react'
import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { runBenchmarkSuite, summarizeBenchmark } from '@/engine/benchmark'
import { formatNumber } from '@/lib/format'
import type { BenchmarkRunResult } from '@/types/domain'

export function BenchmarkPage() {
  const [results, setResults] = useState<BenchmarkRunResult[] | null>(null)

  const summary = results ? summarizeBenchmark(results) : null

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1">
          <h1 className="font-display text-2xl font-semibold tracking-tight sm:text-3xl">Formula Regression Benchmark</h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            15 test case cố định (khoá cứng trong code) đối soát công thức tính giá — TC-01 tái sử dụng đúng ví dụ
            minh hoạ tại PRD §7/§8 (căn ZEN-A-1205).
          </p>
        </div>
        <Button size="lg" onClick={() => setResults(runBenchmarkSuite())}>
          <FlaskConical className="h-4 w-4" /> Chạy Benchmark
        </Button>
      </div>

      {summary && (
        <Card className={summary.exactMatchRate === 1 ? 'border-success/40 bg-success/5' : 'border-destructive/40 bg-destructive/5'}>
          <CardContent className="space-y-3 p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                {summary.exactMatchRate === 1 ? (
                  <CheckCircle2 className="h-5 w-5 text-success" />
                ) : (
                  <XCircle className="h-5 w-5 text-destructive" />
                )}
                <p className="font-display text-2xl font-semibold tabular-nums">
                  {(summary.exactMatchRate * 100).toFixed(2)}% Exact Match
                </p>
              </div>
              <p className="text-sm text-muted-foreground">
                {summary.passedCount}/{summary.total} test case khớp tuyệt đối
              </p>
            </div>
            <Progress value={summary.exactMatchRate * 100} />
          </CardContent>
        </Card>
      )}

      {results && (
        <div className="overflow-x-auto rounded-lg border border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Mã</TableHead>
                <TableHead>Mô tả</TableHead>
                <TableHead className="text-right">Net Price kỳ vọng</TableHead>
                <TableHead className="text-right">Net Price thực tế</TableHead>
                <TableHead className="text-right">Δ Sai lệch</TableHead>
                <TableHead>Kết quả</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {results.map((r) => (
                <TableRow key={r.case.id}>
                  <TableCell className="font-medium">{r.case.id}</TableCell>
                  <TableCell className="max-w-xs text-xs leading-snug text-muted-foreground">{r.case.name}</TableCell>
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
      )}

      {!results && (
        <div className="rounded-lg border border-dashed border-border p-10 text-center text-sm text-muted-foreground">
          Bấm "Chạy Benchmark" để đối soát công thức tính giá với 15 test case chuẩn.
        </div>
      )}
    </div>
  )
}
