import { Loader2, SendHorizonal, Sparkles } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ActivePolicyBanner } from '@/components/ConflictBanner'
import { QuoteDetail } from '@/components/QuoteDetail'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { getPolicyForDate } from '@/data/policies.mock'
import { listUnits } from '@/data/units.mock'
import { formatVnd } from '@/lib/format'
import { useAppStore } from '@/state/appStore'
import type { CustomerSegment, OptimizationObjective } from '@/types/domain'

const OBJECTIVE_OPTIONS: { value: OptimizationObjective; label: string; hint: string }[] = [
  { value: 'MIN_NET_PRICE', label: 'Giá mua sau ưu đãi thấp nhất', hint: 'Phù hợp khách thanh toán sớm để hưởng chiết khấu tối đa.' },
  { value: 'MIN_INITIAL_OUTFLOW', label: 'Số tiền đợt 1 thấp nhất', hint: 'Phù hợp khách có vốn tự có hạn chế, ưu tiên vay hỗ trợ lãi suất.' },
  { value: 'MIN_TOTAL_CASH_OUTFLOW', label: 'Tổng dòng tiền thực tế thấp nhất', hint: 'Tối thiểu hoá tiền mặt phải chi đến khi bàn giao.' },
  { value: 'MAX_BENEFIT_VALUE', label: 'Giá trị ưu đãi & quà tặng lớn nhất', hint: 'Tối đa hoá tổng giá trị voucher, quà tặng quy đổi.' },
]

const UNITS = listUnits()

export function SalesCopilotPage() {
  const submitFromCopilot = useAppStore((s) => s.submitFromCopilot)
  const sendForReview = useAppStore((s) => s.sendForReview)
  const quotes = useAppStore((s) => s.quotes)

  const [unitCode, setUnitCode] = useState(UNITS[0]?.unitCode ?? '')
  const [transactionDate, setTransactionDate] = useState('2026-09-10')
  const [customerSegment, setCustomerSegment] = useState<CustomerSegment>('EXISTING_RESIDENT')
  const [unitsQuantity, setUnitsQuantity] = useState(1)
  const [customerName, setCustomerName] = useState('Khách hàng Nguyễn Văn A')
  const [salesRepName, setSalesRepName] = useState('Hoàng Nam')
  const [selectedRuleCodes, setSelectedRuleCodes] = useState<string[]>([])
  const [objective, setObjective] = useState<OptimizationObjective>('MIN_NET_PRICE')
  const [activeQuoteId, setActiveQuoteId] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const selectedUnit = useMemo(() => UNITS.find((u) => u.unitCode === unitCode), [unitCode])
  const previewPolicy = useMemo(
    () => (selectedUnit ? getPolicyForDate(selectedUnit.projectId, transactionDate) : null),
    [selectedUnit, transactionDate],
  )
  const selectableRules = useMemo(
    () => previewPolicy?.rules.filter((r) => r.isSelectable) ?? [],
    [previewPolicy],
  )
  // Bỏ các ruleCode không còn khả dụng ở phiên bản chính sách hiện tại (ví dụ sau khi đổi ngày
  // giao dịch) mà không cần đồng bộ qua effect — tính trực tiếp trong lúc render.
  const activeRuleCodes = useMemo(
    () => selectedRuleCodes.filter((code) => selectableRules.some((r) => r.ruleCode === code)),
    [selectedRuleCodes, selectableRules],
  )

  const activeQuote = useMemo(() => quotes.find((q) => q.quoteId === activeQuoteId) ?? null, [quotes, activeQuoteId])

  function toggleRule(ruleCode: string, checked: boolean) {
    setSelectedRuleCodes((prev) => (checked ? [...prev, ruleCode] : prev.filter((c) => c !== ruleCode)))
  }

  function handleSubmit() {
    if (!selectedUnit) return
    setIsSubmitting(true)
    const quote = submitFromCopilot({
      unitCode: selectedUnit.unitCode,
      transactionDate,
      customerSegment,
      unitsQuantity,
      selectedRuleCodes: activeRuleCodes,
      objective,
      customerName,
      salesRepName,
    })
    setActiveQuoteId(quote.quoteId)
    setIsSubmitting(false)
  }

  function handleSendForReview() {
    if (!activeQuote) return
    sendForReview(activeQuote.quoteId)
  }

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="font-display text-2xl font-semibold tracking-tight sm:text-3xl">Sales Copilot Workspace</h1>
        <p className="text-sm text-muted-foreground">
          Nhập bối cảnh giao dịch — hệ thống tự tra cứu chính sách theo ngày, quét xung đột và so sánh 3 phương án
          thanh toán.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[380px,1fr]">
        <Card className="h-fit">
          <CardHeader>
            <CardTitle>Bối cảnh giao dịch</CardTitle>
            <CardDescription>Toàn bộ tính toán là mock, chạy hoàn toàn phía trình duyệt.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="unit">Mã căn hộ</Label>
              <Select value={unitCode} onValueChange={setUnitCode}>
                <SelectTrigger id="unit">
                  <SelectValue placeholder="Chọn căn hộ" />
                </SelectTrigger>
                <SelectContent>
                  {UNITS.map((u) => (
                    <SelectItem key={u.unitCode} value={u.unitCode}>
                      {u.unitCode} — {u.projectName} ({formatVnd(u.listedPrice)})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selectedUnit && (
                <p className="text-xs text-muted-foreground">
                  {selectedUnit.block}, tầng {selectedUnit.floor} · {selectedUnit.areaM2}m² · {selectedUnit.bedrooms}PN ·{' '}
                  {selectedUnit.view}
                </p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="txDate">Ngày giao dịch</Label>
                <Input id="txDate" type="date" value={transactionDate} onChange={(e) => setTransactionDate(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="qty">Số lượng căn mua</Label>
                <Input
                  id="qty"
                  type="number"
                  min={1}
                  value={unitsQuantity}
                  onChange={(e) => setUnitsQuantity(Math.max(1, Number(e.target.value) || 1))}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="segment">Phân khúc khách hàng</Label>
              <Select value={customerSegment} onValueChange={(v) => setCustomerSegment(v as CustomerSegment)}>
                <SelectTrigger id="segment">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="EXISTING_RESIDENT">Cư dân hiện hữu</SelectItem>
                  <SelectItem value="NEW_CUSTOMER">Khách hàng mới</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="customerName">Tên khách hàng</Label>
                <Input id="customerName" value={customerName} onChange={(e) => setCustomerName(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="salesRep">Nhân viên kinh doanh</Label>
                <Input id="salesRep" value={salesRepName} onChange={(e) => setSalesRepName(e.target.value)} />
              </div>
            </div>

            <Separator />

            {previewPolicy ? (
              <ActivePolicyBanner
                policy={{
                  title: previewPolicy.title,
                  version: previewPolicy.version,
                  effectiveFrom: previewPolicy.effectiveFrom,
                  effectiveTo: previewPolicy.effectiveTo,
                }}
              />
            ) : (
              <p className="rounded-md border border-dashed border-border p-3 text-xs text-muted-foreground">
                Không có chính sách nào còn hiệu lực tại ngày giao dịch này cho dự án đã chọn.
              </p>
            )}

            <div className="space-y-2">
              <Label>Ưu đãi muốn xét</Label>
              {selectableRules.length === 0 && (
                <p className="text-xs text-muted-foreground">Chưa có ưu đãi tuỳ chọn nào khả dụng.</p>
              )}
              <div className="space-y-2.5">
                {selectableRules.map((rule) => (
                  <label key={rule.ruleCode} className="flex cursor-pointer items-start gap-2.5 rounded-md border border-border p-2.5 hover:bg-muted/50">
                    <Checkbox
                      checked={activeRuleCodes.includes(rule.ruleCode)}
                      onCheckedChange={(checked) => toggleRule(rule.ruleCode, checked === true)}
                      className="mt-0.5"
                    />
                    <span>
                      <span className="block text-sm font-medium leading-tight">{rule.title}</span>
                      <span className="block text-xs text-muted-foreground">{rule.source.clauseTitle}</span>
                    </span>
                  </label>
                ))}
              </div>
            </div>

            <Separator />

            <div className="space-y-2">
              <Label>Tiêu chí tối ưu hóa</Label>
              <RadioGroup value={objective} onValueChange={(v) => setObjective(v as OptimizationObjective)}>
                {OBJECTIVE_OPTIONS.map((opt) => (
                  <label
                    key={opt.value}
                    className="flex cursor-pointer items-start gap-2.5 rounded-md border border-border p-2.5 hover:bg-muted/50"
                  >
                    <RadioGroupItem value={opt.value} className="mt-0.5" />
                    <span>
                      <span className="block text-sm font-medium leading-tight">{opt.label}</span>
                      <span className="block text-xs text-muted-foreground">{opt.hint}</span>
                    </span>
                  </label>
                ))}
              </RadioGroup>
            </div>

            <Button className="w-full" size="lg" onClick={handleSubmit} disabled={!selectedUnit || isSubmitting}>
              {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              Phân tích & Tính toán
            </Button>
          </CardContent>
        </Card>

        <div className="space-y-4">
          {!activeQuote && (
            <Card className="flex h-full min-h-[320px] items-center justify-center border-dashed">
              <CardContent className="max-w-sm p-8 text-center">
                <Sparkles className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                  Điền bối cảnh giao dịch bên trái và bấm "Phân tích & Tính toán" để xem kết quả Preflight, 3 phương
                  án thanh toán và đề xuất tối ưu.
                </p>
              </CardContent>
            </Card>
          )}

          {activeQuote && (
            <>
              <QuoteDetail quote={activeQuote} />
              {activeQuote.status === 'DRAFT' && (
                <Card>
                  <CardContent className="flex flex-col items-start gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
                    <p className="text-sm text-muted-foreground">
                      Hồ sơ đã sẵn sàng. Gửi sang hàng đợi thẩm định của Quản lý bán hàng để xin phê duyệt phát hành.
                    </p>
                    <Button onClick={handleSendForReview}>
                      <SendHorizonal className="h-4 w-4" /> Gửi duyệt Quản lý
                    </Button>
                  </CardContent>
                </Card>
              )}
              {activeQuote.status === 'READY_FOR_REVIEW' && (
                <Card className="border-primary/30 bg-primary/[0.03]">
                  <CardContent className="p-4 text-sm">
                    Hồ sơ đang chờ Quản lý duyệt. Theo dõi tại{' '}
                    <Link to="/manager" className="font-medium text-primary underline underline-offset-2">
                      Duyệt hồ sơ
                    </Link>
                    .
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
