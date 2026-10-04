import { AlertCircle, CheckCircle2, ExternalLink, KeyRound, Loader2, Plus, RefreshCw, Trash2, Volume2, Zap } from 'lucide-react'
import { useState } from 'react'

import type { LlmProvider, LlmProviderPayload, LlmProviderTestResult } from '@pricepolicy/api-client/contracts'
import {
  useCreateLlmProvider,
  useDeleteLlmProvider,
  useLlmProviders,
  useLlmUsageRecords,
  useLlmUsageSummary,
  useTestLlmProvider,
  useTtsSettings,
  useUpdateLlmProvider,
  useUpdateTtsSettings,
} from '@pricepolicy/api-client/hooks'
import { Badge } from '@pricepolicy/ui/components/ui/badge'
import { Button } from '@pricepolicy/ui/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@pricepolicy/ui/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@pricepolicy/ui/components/ui/dialog'
import { Input } from '@pricepolicy/ui/components/ui/input'
import { Label } from '@pricepolicy/ui/components/ui/label'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@pricepolicy/ui/components/ui/table'
import { toast } from '@pricepolicy/ui/state/toastStore'

import { TtsProvidersCard, TtsProvidersFootnote } from './TtsProvidersCard'

const EMPTY_FORM: LlmProviderPayload = {
  name: '',
  provider: 'openai',
  base_url: '',
  model_name: 'gpt-4o-mini',
  api_key: '',
  input_price_per_1m: 0.15,
  output_price_per_1m: 0.6,
  currency: 'USD',
  temperature: 0.2,
  priority: 10,
  is_active: true,
}

const fmtNumber = (n: number, digits = 2) =>
  n.toLocaleString('vi-VN', { minimumFractionDigits: digits, maximumFractionDigits: digits })

const fmtMoney = (n: number, currency: string) => `${fmtNumber(n, 4)} ${currency}`

function ProviderFormDialog({
  open,
  editing,
  onClose,
}: {
  open: boolean
  editing: LlmProvider | null
  onClose: () => void
}) {
  const createProvider = useCreateLlmProvider()
  const updateProvider = useUpdateLlmProvider()
  const testProvider = useTestLlmProvider()
  const [form, setForm] = useState<LlmProviderPayload>(EMPTY_FORM)
  const [error, setError] = useState<string | null>(null)
  const [initialisedFor, setInitialisedFor] = useState<string | null>(null)
  /** Nhà cung cấp vừa lưu trong hộp thoại này — có id mới bật được nút “Test kết nối”. */
  const [savedId, setSavedId] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<LlmProviderTestResult | null>(null)
  /** Bản che của khoá vừa lưu (khoá thô bị xoá khỏi form ngay sau khi lưu). */
  const [savedMasked, setSavedMasked] = useState<string | null>(null)

  // Nạp dữ liệu khi mở dialog (tạo mới → form trắng; sửa → dữ liệu hiện có, khoá để trống).
  const target = editing?.provider_id ?? 'new'
  if (open && initialisedFor !== target) {
    setInitialisedFor(target)
    setError(null)
    setSavedId(null)
    setTestResult(null)
    setSavedMasked(null)
    setForm(
      editing
        ? {
            name: editing.name,
            provider: editing.provider,
            base_url: editing.base_url ?? '',
            model_name: editing.model_name,
            api_key: '',
            input_price_per_1m: editing.input_price_per_1m,
            output_price_per_1m: editing.output_price_per_1m,
            currency: editing.currency,
            temperature: editing.temperature,
            priority: editing.priority,
            is_active: editing.is_active,
          }
        : EMPTY_FORM,
    )
  }
  if (!open && initialisedFor !== null) setInitialisedFor(null)

  const pending = createProvider.isPending || updateProvider.isPending
  const testing = testProvider.isPending

  async function submit() {
    setError(null)
    if (!form.name.trim() || !form.model_name.trim()) {
      setError('Cần nhập tên gợi nhớ và model.')
      return
    }
    if (!editing && !savedId && !form.api_key?.trim()) {
      setError('Cần nhập API key cho nhà cung cấp mới.')
      return
    }
    try {
      // Lưu xong KHÔNG đóng hộp thoại: giữ lại để Admin bấm “Test kết nối” ngay với cấu hình vừa lưu
      // (test luôn dùng bản đã lưu trong DB, nên phải lưu trước mới có ý nghĩa).
      // Đã lưu trong hộp thoại này rồi (savedId) thì lần bấm sau là CẬP NHẬT — nếu vẫn gọi create
      // sẽ sinh nhà cung cấp trùng, vì hộp thoại giờ không tự đóng sau khi lưu.
      const targetId = editing?.provider_id ?? savedId
      const saved = targetId
        ? await updateProvider.mutateAsync({ providerId: targetId, payload: form })
        : await createProvider.mutateAsync(form)
      setSavedId(saved.provider_id)
      setTestResult(null)
      setSavedMasked(saved.api_key_masked)
      // Không giữ khoá thô trong state sau khi đã lưu; lần lưu sau để trống = giữ khoá cũ.
      setForm((f) => ({ ...f, api_key: '' }))
      toast.success(editing ? `Đã cập nhật ${form.name}` : `Đã khai báo nhà cung cấp ${form.name}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không lưu được cấu hình nhà cung cấp.')
    }
  }

  /** Gọi nhà cung cấp thật (backend gọi `/models`) để biết cấu hình vừa lưu có dùng được không. */
  async function runTest() {
    if (!savedId) return
    setTestResult(null)
    try {
      const result = await testProvider.mutateAsync(savedId)
      setTestResult(result)
      if (result.ok) toast.success(`Kết nối OK (${result.latency_ms} ms)`)
      else toast.error(result.detail)
    } catch (err) {
      setTestResult({
        provider_id: savedId,
        ok: false,
        latency_ms: 0,
        status: 'ERROR',
        detail: err instanceof Error ? err.message : 'Không kiểm tra được kết nối.',
      })
    }
  }

  const set = <K extends keyof LlmProviderPayload>(key: K, value: LlmProviderPayload[K]) => {
    setForm((f) => ({ ...f, [key]: value }))
    // Sửa tiếp sau khi lưu ⇒ cấu hình trên form khác bản đã lưu; bỏ kết quả test cũ để không gây hiểu nhầm.
    if (savedId) {
      setSavedId(null)
      setTestResult(null)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{editing ? `Sửa nhà cung cấp ${editing.name}` : 'Khai báo nhà cung cấp LLM'}</DialogTitle>
          <DialogDescription>
            Khai báo ngay trong giao diện — không cần sửa biến môi trường. Nếu DB chưa có nhà cung cấp nào, hệ thống
            vẫn dùng cấu hình từ ENV làm phương án dự phòng.
          </DialogDescription>
        </DialogHeader>

        {/* Bọc trong <form autoComplete="off">: Chrome suy luận "ô text + ô password = form đăng nhập"
            rồi tự điền tài khoản/mật khẩu đã lưu vào Base URL và API key (đúng lỗi đã gặp). */}
        <form
          className="grid gap-4 sm:grid-cols-2"
          autoComplete="off"
          onSubmit={(e) => {
            e.preventDefault()
            void submit()
          }}
        >
          {error && (
            <div className="sm:col-span-2 flex items-center gap-2 rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {error}
            </div>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="llm-name">Tên gợi nhớ *</Label>
            <Input id="llm-name" name="llm-name" autoComplete="off" data-form-type="other" value={form.name} onChange={(e) => set('name', e.target.value)} placeholder="OpenAI chính" />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="llm-provider">Nhà cung cấp</Label>
            <Input id="llm-provider" name="llm-provider" autoComplete="off" data-form-type="other" value={form.provider} onChange={(e) => set('provider', e.target.value)} placeholder="openai / anthropic / gemini" />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="llm-model">Model *</Label>
            <Input id="llm-model" name="llm-model" autoComplete="off" data-form-type="other" value={form.model_name} onChange={(e) => set('model_name', e.target.value)} placeholder="gpt-4o-mini" />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="llm-base">Base URL</Label>
            <Input
              id="llm-base"
              name="llm-base-url"
              type="url"
              inputMode="url"
              autoComplete="off"
              data-form-type="other"
              data-lpignore="true"
              data-1p-ignore
              data-bwignore
              value={form.base_url ?? ''}
              onChange={(e) => set('base_url', e.target.value)}
              placeholder="https://api.openai.com/v1"
            />
          </div>

          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="llm-key">
              API key {editing || savedId ? '(bỏ trống để giữ khoá cũ)' : '*'}
            </Label>
            {/* `new-password` (không phải `off`): trình duyệt hiểu đây là khoá MỚI, không phải mật khẩu
                đăng nhập — nhờ vậy không tự điền bản đã lưu và cũng không hỏi "lưu mật khẩu?". */}
            <Input
              id="llm-key"
              name="llm-api-key"
              type="password"
              autoComplete="new-password"
              data-form-type="other"
              data-lpignore="true"
              data-1p-ignore
              data-bwignore
              value={form.api_key ?? ''}
              onChange={(e) => set('api_key', e.target.value)}
              placeholder={
                savedMasked ?? editing?.api_key_masked
                  ? `${savedMasked ?? editing?.api_key_masked} — nhập để thay mới`
                  : 'sk-...'
              }
            />
            <p className="text-xs text-muted-foreground">
              Khoá được mã hoá khi lưu và chỉ hiển thị dạng che (ví dụ <code>sk-t…abcd</code>).
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="llm-price-in">Đơn giá token vào / 1 triệu token</Label>
            <Input
              id="llm-price-in"
              type="number"
              step="0.0001"
              min="0"
              value={form.input_price_per_1m}
              onChange={(e) => set('input_price_per_1m', Number(e.target.value))}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="llm-price-out">Đơn giá token ra / 1 triệu token</Label>
            <Input
              id="llm-price-out"
              type="number"
              step="0.0001"
              min="0"
              value={form.output_price_per_1m}
              onChange={(e) => set('output_price_per_1m', Number(e.target.value))}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="llm-currency">Đơn vị tiền tệ</Label>
            <Input id="llm-currency" name="llm-currency" autoComplete="off" data-form-type="other" value={form.currency} onChange={(e) => set('currency', e.target.value.toUpperCase())} placeholder="USD" />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="llm-priority">Thứ tự ưu tiên (số nhỏ chạy trước)</Label>
            <Input
              id="llm-priority"
              type="number"
              min="0"
              value={form.priority}
              onChange={(e) => set('priority', Number(e.target.value))}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="llm-temp">Temperature</Label>
            <Input
              id="llm-temp"
              type="number"
              step="0.1"
              min="0"
              max="2"
              value={form.temperature}
              onChange={(e) => set('temperature', Number(e.target.value))}
            />
          </div>

          <label className="flex items-center gap-2 text-sm sm:col-span-2">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => set('is_active', e.target.checked)}
              className="h-4 w-4 rounded border-input"
            />
            Đang hoạt động (tắt để tạm dừng dùng nhà cung cấp này)
          </label>
        </form>

        {/* Kết quả kiểm tra kết nối — hiện ngay trong hộp thoại sau khi lưu. */}
        {savedId && (
          <div className="space-y-2">
            {testResult ? (
              <div
                className={
                  'flex items-start gap-2 rounded-lg border p-3 text-xs ' +
                  (testResult.ok
                    ? 'border-success/30 bg-success/10 text-success'
                    : 'border-warning/40 bg-warning/10 text-warning')
                }
              >
                {testResult.ok ? (
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
                ) : (
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                )}
                <div>
                  <p className="font-medium">
                    {testResult.ok ? 'Kết nối thành công' : 'Kết nối chưa dùng được'} · {testResult.status}
                    {testResult.latency_ms > 0 && ` · ${testResult.latency_ms} ms`}
                  </p>
                  {/* Chẩn đoán có thể nhiều dòng (ví dụ ca Cloudflare) — giữ nguyên xuống dòng cho dễ đọc. */}
                  <p className="mt-0.5 whitespace-pre-line">{testResult.detail}</p>
                </div>
              </div>
            ) : (
              <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <CheckCircle2 className="h-3.5 w-3.5 text-success" />
                Đã lưu cấu hình — bấm “Test kết nối” để gọi thử nhà cung cấp bằng khoá vừa lưu.
              </p>
            )}
          </div>
        )}

        <DialogFooter className="gap-2 sm:justify-between">
          <div>
            {savedId && (
              <Button variant="outline" onClick={() => void runTest()} disabled={testing || pending}>
                {testing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Zap className="mr-2 h-4 w-4" />}
                Test kết nối
              </Button>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={onClose} disabled={pending}>
              {savedId ? 'Đóng' : 'Hủy'}
            </Button>
            <Button onClick={() => void submit()} disabled={pending}>
              {pending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {editing || savedId ? 'Lưu thay đổi' : 'Khai báo'}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** Tab 2 — danh sách nhà cung cấp do Admin tự khai báo (kèm nút kiểm tra kết nối). */
export function LlmProvidersTab() {
  const { data, isLoading, isError, refetch } = useLlmProviders()
  const deleteProvider = useDeleteLlmProvider()
  const testProvider = useTestLlmProvider()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<LlmProvider | null>(null)
  const [testing, setTesting] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<LlmProvider | null>(null)

  const providers = data?.items ?? []
  const usingEnvFallback = data?.source !== 'db'

  async function runTest(provider: LlmProvider) {
    setTesting(provider.provider_id)
    try {
      const result = await testProvider.mutateAsync(provider.provider_id)
      if (result.ok) toast.success(`${provider.name}: kết nối OK (${result.latency_ms} ms)`)
      else toast.error(`${provider.name}: ${result.detail}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Không kiểm tra được kết nối.')
    } finally {
      setTesting(null)
    }
  }

  return (
    <div className="space-y-5">
      <Card className={usingEnvFallback ? 'border-warning/40 bg-warning/[0.04]' : ''}>
        <CardContent className="flex flex-col gap-3 p-4 text-sm sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-2">
            <KeyRound className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            <div>
              {data?.source === 'env' ? (
                <>
                  <p className="font-medium">Đang dùng API key từ biến môi trường (chưa khai báo nhà cung cấp nào trong hệ thống).</p>
                  <p className="text-xs text-muted-foreground">
                    Khai báo bên dưới để chủ động đổi khoá/đơn giá — khi có ít nhất một nhà cung cấp đang hoạt động,
                    hệ thống ưu tiên dùng cấu hình này thay cho ENV.
                  </p>
                </>
              ) : data?.source === 'none' ? (
                <>
                  <p className="font-medium">Chưa có nhà cung cấp LLM nào — trợ lý sẽ chạy ở chế độ suy luận tất định.</p>
                  <p className="text-xs text-muted-foreground">Khai báo nhà cung cấp + API key để bật trả lời bằng LLM thật.</p>
                </>
              ) : (
                <>
                  <p className="font-medium">Đang dùng cấu hình khai báo trong hệ thống (ưu tiên hơn biến môi trường).</p>
                  <p className="text-xs text-muted-foreground">
                    Thứ tự ưu tiên: số nhỏ chạy trước; nhà cung cấp lỗi sẽ tự chuyển sang nhà cung cấp kế tiếp.
                  </p>
                </>
              )}
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Badge variant="outline" className="text-xs">
              Nguồn: {data?.source === 'db' ? 'DB' : data?.source === 'env' ? 'ENV' : 'chưa có'}
            </Badge>
            <Button variant="ghost" size="sm" className="h-8 px-2" onClick={() => refetch()} title="Tải lại">
              <RefreshCw className="h-3.5 w-3.5" />
            </Button>
            <Button
              size="sm"
              onClick={() => {
                setEditing(null)
                setDialogOpen(true)
              }}
            >
              <Plus className="mr-2 h-4 w-4" />
              Khai báo nhà cung cấp
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Nhà cung cấp đã khai báo</CardTitle>
          <CardDescription>
            Đơn giá (đơn giá/1 triệu token) là cơ sở quy đổi chi phí ở tab “Chi phí và hiệu năng”.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[90px]">Ưu tiên</TableHead>
                <TableHead>Tên / Model</TableHead>
                <TableHead>API key</TableHead>
                <TableHead className="text-right">Đơn giá vào</TableHead>
                <TableHead className="text-right">Đơn giá ra</TableHead>
                <TableHead className="w-[130px]">Kiểm tra</TableHead>
                <TableHead className="w-[110px] text-right">Thao tác</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={7} className="h-28 text-center text-muted-foreground">
                    <Loader2 className="mx-auto h-5 w-5 animate-spin" />
                  </TableCell>
                </TableRow>
              ) : isError ? (
                <TableRow>
                  <TableCell colSpan={7} className="h-28 text-center text-destructive">
                    Không tải được danh sách nhà cung cấp.
                  </TableCell>
                </TableRow>
              ) : providers.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="h-28 text-center text-muted-foreground">
                    Chưa khai báo nhà cung cấp nào trong hệ thống.
                  </TableCell>
                </TableRow>
              ) : (
                providers.map((p) => (
                  <TableRow key={p.provider_id} className={p.is_active ? '' : 'opacity-60'}>
                    <TableCell>
                      <Badge variant={p.priority === 0 ? 'default' : 'outline'} className="text-xs">
                        {p.priority === 0 ? 'Chính' : `#${p.priority}`}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="font-medium">{p.name}</div>
                      <div className="text-xs text-muted-foreground">
                        {p.provider} · {p.model_name}
                        {p.base_url ? ` · ${p.base_url}` : ''}
                      </div>
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">{p.api_key_masked}</TableCell>
                    <TableCell className="text-right text-sm">{fmtNumber(p.input_price_per_1m, 4)}</TableCell>
                    <TableCell className="text-right text-sm">{fmtNumber(p.output_price_per_1m, 4)}</TableCell>
                    <TableCell>
                      {p.last_test_status ? (
                        <div className="flex items-center gap-1.5 text-xs">
                          {p.last_test_status === 'OK' ? (
                            <CheckCircle2 className="h-3.5 w-3.5 text-success" />
                          ) : (
                            <AlertCircle className="h-3.5 w-3.5 text-warning" />
                          )}
                          <span>{p.last_test_status}</span>
                          {p.last_test_latency_ms != null && (
                            <span className="text-muted-foreground">{p.last_test_latency_ms} ms</span>
                          )}
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground">Chưa kiểm tra</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-muted-foreground hover:text-foreground"
                          title="Kiểm tra kết nối"
                          disabled={testing === p.provider_id}
                          onClick={() => void runTest(p)}
                        >
                          {testing === p.provider_id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Zap className="h-4 w-4" />
                          )}
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-muted-foreground hover:text-foreground"
                          title="Sửa cấu hình"
                          onClick={() => {
                            setEditing(p)
                            setDialogOpen(true)
                          }}
                        >
                          <KeyRound className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-destructive/70 hover:bg-destructive/10 hover:text-destructive"
                          title="Xoá nhà cung cấp"
                          onClick={() => setDeleting(p)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <ProviderFormDialog open={dialogOpen} editing={editing} onClose={() => setDialogOpen(false)} />

      {deleting && (
        <Dialog open onOpenChange={() => setDeleting(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-destructive">
                <Trash2 className="h-5 w-5" /> Xoá nhà cung cấp
              </DialogTitle>
              <DialogDescription>
                Bạn có chắc muốn xoá <strong>{deleting.name}</strong>? Nếu đây là nhà cung cấp duy nhất trong DB, hệ
                thống sẽ quay lại dùng cấu hình từ biến môi trường (nếu có).
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDeleting(null)}>
                Hủy
              </Button>
              <Button
                variant="destructive"
                disabled={deleteProvider.isPending}
                onClick={async () => {
                  try {
                    await deleteProvider.mutateAsync(deleting.provider_id)
                    toast.success(`Đã xoá ${deleting.name}`)
                    setDeleting(null)
                  } catch (err) {
                    toast.error(err instanceof Error ? err.message : 'Không xoá được nhà cung cấp.')
                  }
                }}
              >
                {deleteProvider.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Xoá
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}

/** Tab 3 — đo lường: chi phí, token, độ trễ (p50/p95), tỉ lệ lỗi theo nhà cung cấp và theo ngày. */
export function LlmUsageTab() {
  const [days, setDays] = useState(14)
  const summary = useLlmUsageSummary(days)
  const records = useLlmUsageRecords(50)

  const s = summary.data
  const maxDayCost = Math.max(0, ...(s?.by_day.map((d) => d.cost) ?? [0]))

  return (
    <div className="space-y-5">
      <Card>
        <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-semibold">Đo lường mức tiêu thụ LLM</p>
            <p className="text-xs text-muted-foreground">
              Chi phí quy từ đơn giá Admin khai báo × token thực dùng. Số liệu ghi tại mỗi lượt gọi (kể cả lượt dự phòng).
            </p>
          </div>
          <div className="flex items-center gap-2">
            {[7, 14, 30].map((d) => (
              <Button
                key={d}
                size="sm"
                variant={days === d ? 'default' : 'outline'}
                className="h-8 text-xs"
                onClick={() => setDays(d)}
              >
                {d} ngày
              </Button>
            ))}
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              title="Tải lại"
              onClick={() => {
                void summary.refetch()
                void records.refetch()
              }}
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </Button>
          </div>
        </CardContent>
      </Card>

      {summary.isLoading ? (
        <Card>
          <CardContent className="flex h-32 items-center justify-center text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
          </CardContent>
        </Card>
      ) : summary.isError || !s ? (
        <Card>
          <CardContent className="flex h-32 items-center justify-center text-destructive">
            Không tải được số liệu chi phí.
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Card>
              <CardHeader className="p-4 pb-2">
                <CardDescription className="text-xs">Tổng chi phí ({days} ngày)</CardDescription>
                <CardTitle className="text-2xl">{fmtMoney(s.total_cost, s.currency)}</CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="p-4 pb-2">
                <CardDescription className="text-xs">Lượt gọi</CardDescription>
                <CardTitle className="text-2xl">{s.total_calls.toLocaleString('vi-VN')}</CardTitle>
                <p className="text-xs text-muted-foreground">
                  Lỗi {(s.error_rate * 100).toFixed(1)}% ({s.failed_calls} lượt)
                </p>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="p-4 pb-2">
                <CardDescription className="text-xs">Token dùng</CardDescription>
                <CardTitle className="text-2xl">{s.total_tokens.toLocaleString('vi-VN')}</CardTitle>
                <p className="text-xs text-muted-foreground">
                  vào {s.total_input_tokens.toLocaleString('vi-VN')} · ra {s.total_output_tokens.toLocaleString('vi-VN')}
                </p>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="p-4 pb-2">
                <CardDescription className="text-xs">Độ trễ p50 / p95</CardDescription>
                <CardTitle className="text-2xl">
                  {Math.round(s.p50_latency_ms)} / {Math.round(s.p95_latency_ms)} ms
                </CardTitle>
                <p className="text-xs text-muted-foreground">
                  Bình quân {fmtMoney(s.avg_cost_per_call, s.currency)}/lượt
                </p>
              </CardHeader>
            </Card>
          </div>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Theo nhà cung cấp / model</CardTitle>
              <CardDescription>Đối chiếu hiệu năng và chi phí giữa các model đang cấu hình.</CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Nhà cung cấp / Model</TableHead>
                    <TableHead className="text-right">Lượt</TableHead>
                    <TableHead className="text-right">Token</TableHead>
                    <TableHead className="text-right">Chi phí</TableHead>
                    <TableHead className="text-right">TB / p95 (ms)</TableHead>
                    <TableHead className="text-right">Tỉ lệ lỗi</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {s.by_provider.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">
                        Chưa có lượt gọi nào được ghi nhận trong {days} ngày gần đây.
                      </TableCell>
                    </TableRow>
                  ) : (
                    s.by_provider.map((row) => (
                      <TableRow key={`${row.provider}-${row.model_name}`}>
                        <TableCell>
                          <div className="font-medium">{row.provider}</div>
                          <div className="text-xs text-muted-foreground">{row.model_name}</div>
                        </TableCell>
                        <TableCell className="text-right text-sm">{row.calls.toLocaleString('vi-VN')}</TableCell>
                        <TableCell className="text-right text-sm">
                          {(row.input_tokens + row.output_tokens).toLocaleString('vi-VN')}
                        </TableCell>
                        <TableCell className="text-right text-sm">{fmtMoney(row.cost, s.currency)}</TableCell>
                        <TableCell className="text-right text-sm">
                          {Math.round(row.avg_latency_ms)} / {Math.round(row.p95_latency_ms)}
                        </TableCell>
                        <TableCell className="text-right text-sm">{(row.error_rate * 100).toFixed(1)}%</TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {s.by_day.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Chi phí theo ngày</CardTitle>
              </CardHeader>
              <CardContent className="space-y-1.5">
                {s.by_day.map((d) => (
                  <div key={d.day} className="flex items-center gap-3 text-xs">
                    <span className="w-24 shrink-0 font-mono text-muted-foreground">{d.day}</span>
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-primary/70"
                        style={{ width: `${maxDayCost > 0 ? Math.max(2, (d.cost / maxDayCost) * 100) : 0}%` }}
                      />
                    </div>
                    <span className="w-28 shrink-0 text-right">{fmtMoney(d.cost, s.currency)}</span>
                    <span className="w-20 shrink-0 text-right text-muted-foreground">{d.calls} lượt</span>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Lượt gọi gần nhất</CardTitle>
              <CardDescription>Log thô để đối chiếu khi chi phí tăng bất thường.</CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[150px]">Thời điểm</TableHead>
                    <TableHead>Model</TableHead>
                    <TableHead className="text-right">Token vào/ra</TableHead>
                    <TableHead className="text-right">Độ trễ</TableHead>
                    <TableHead className="text-right">Chi phí</TableHead>
                    <TableHead className="w-[90px]">Kết quả</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(records.data?.items ?? []).length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">
                        Chưa có lượt gọi nào được ghi nhận.
                      </TableCell>
                    </TableRow>
                  ) : (
                    (records.data?.items ?? []).map((r, idx) => (
                      <TableRow key={`${r.at}-${idx}`}>
                        <TableCell className="font-mono text-xs">{new Date(r.at).toLocaleString('vi-VN')}</TableCell>
                        <TableCell className="text-sm">
                          {r.provider} · {r.model_name}
                          {r.is_fallback && (
                            <Badge variant="outline" className="ml-2 text-xs">
                              dự phòng
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-right text-xs">
                          {r.input_tokens.toLocaleString('vi-VN')} / {r.output_tokens.toLocaleString('vi-VN')}
                        </TableCell>
                        <TableCell className="text-right text-xs">{Math.round(r.latency_ms)} ms</TableCell>
                        <TableCell className="text-right text-xs">{fmtMoney(r.cost, r.currency)}</TableCell>
                        <TableCell>
                          {r.ok ? (
                            <Badge variant="success" className="text-xs">OK</Badge>
                          ) : (
                            <Badge variant="destructive" className="text-xs">
                              {r.error ?? 'LỖI'}
                            </Badge>
                          )}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}

      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <ExternalLink className="h-3 w-3" />
        Cần đổi khoá hay thêm model? Sang tab “Nhà cung cấp LLM” để khai báo — không cần chỉnh ENV.
      </p>
    </div>
  )
}

/**
 * Tab 4 — Giọng đọc câu trả lời Copilot (TTS).
 *
 * Vì sao ở đây: Sale cần **nghe** câu trả lời (đang dẫn khách, đang lái xe). Tab này là chỗ Admin
 * quyết định giọng nào dùng chung cho cả công ty, xem đơn giá từng nhà cung cấp và tình trạng khoá —
 * tất cả bằng dữ liệu thật từ `/api/v1/settings/tts`, không phải bảng giá chép tay trong tài liệu.
 */
export function TtsTab() {
  const { data, isLoading, isError, refetch } = useTtsSettings()
  const update = useUpdateTtsSettings()

  const provider = data?.catalog.find((c) => c.provider === (data?.default.provider ?? 'browser'))
  const save = async (payload: Record<string, unknown>) => {
    try {
      await update.mutateAsync({ scope: 'default', ...payload })
      toast.success('Đã lưu giọng đọc dùng chung')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Không lưu được giọng đọc')
    }
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardContent className="space-y-3 p-4">
          <div className="flex items-start gap-2">
            <Volume2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            <div className="text-sm">
              <p className="font-medium">Copilot đọc câu trả lời thành tiếng</p>
              <p className="text-xs text-muted-foreground">
                Mặc định dùng giọng có sẵn trên máy nhân viên (0 đồng, không cần khoá). Khi chọn nhà cung cấp
                trả phí, cả công ty đọc cùng một giọng — chi phí quy theo đơn giá bên dưới và tính theo ký tự
                thực đọc. Mỗi nhân viên vẫn tự chỉnh giọng riêng cho mình trong workspace nếu muốn.
              </p>
            </div>
          </div>

          {isLoading ? (
            <div className="flex h-24 items-center justify-center text-muted-foreground">
              <Loader2 className="h-5 w-5 animate-spin" />
            </div>
          ) : isError || !data ? (
            <p className="text-sm text-destructive">Không tải được thiết lập giọng đọc.</p>
          ) : (
            <>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label>Nhà cung cấp dùng chung</Label>
                  <select
                    className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
                    value={data.default.provider}
                    onChange={(e) => {
                      const next = data.catalog.find((c) => c.provider === e.target.value)
                      void save({ provider: e.target.value, voice: next?.voices[0]?.code ?? 'vi-VN', model: next?.default_model ?? '' })
                    }}
                  >
                    {data.catalog.map((c) => (
                      <option key={c.provider} value={c.provider}>
                        {c.label} — {c.mode === 'browser' ? 'miễn phí' : `${c.price_per_1m_chars.toLocaleString('vi-VN')} ${c.currency}/1M ký tự`}
                        {c.mode === 'api' && !c.api_key_configured ? ' (chưa có khoá)' : ''}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1.5">
                  <Label>Giọng đọc dùng chung</Label>
                  <select
                    className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
                    value={data.default.voice}
                    onChange={(e) => void save({ voice: e.target.value })}
                  >
                    {(provider?.voices ?? []).map((v) => (
                      <option key={v.code} value={v.code}>
                        {v.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1.5">
                  <Label>Tốc độ đọc: {data.default.speed.toFixed(2)}×</Label>
                  <input
                    type="range"
                    min={0.5}
                    max={2}
                    step={0.05}
                    className="w-full"
                    value={data.default.speed}
                    onChange={(e) => void save({ speed: Number(e.target.value) })}
                  />
                </div>

                <div className="space-y-1.5">
                  <Label>Giới hạn ký tự mỗi lượt đọc</Label>
                  <Input
                    type="number"
                    min={50}
                    max={5000}
                    value={data.default.max_chars_per_turn}
                    onChange={(e) => void save({ max_chars_per_turn: Number(e.target.value) })}
                  />
                  <p className="text-xs text-muted-foreground">
                    Câu trả lời dài hơn sẽ chỉ đọc phần đầu — vừa đỡ tốn tiền vừa không bắt khách chờ.
                  </p>
                </div>
              </div>

              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  className="h-4 w-4"
                  checked={data.default.auto_speak}
                  onChange={(e) => void save({ auto_speak: e.target.checked })}
                />
                Tự đọc mỗi câu trả lời mới (mặc định cho nhân viên, ai cũng tắt được cho riêng mình)
              </label>

              <div className="flex flex-wrap items-center gap-3 rounded-lg bg-muted/40 p-3 text-xs">
                <span>
                  Chi phí tối đa mỗi lượt đọc:{' '}
                  <strong>
                    {data.cost_hint.cost.toLocaleString('vi-VN', { maximumFractionDigits: 4 })} {data.cost_hint.currency}
                  </strong>{' '}
                  cho {data.cost_hint.chars} ký tự
                </span>
                <span className="text-muted-foreground">
                  · Giọng {data.effective.voice} được đánh giá: {data.feedback_summary.up} ổn /{' '}
                  {data.feedback_summary.down} chưa ổn
                  {data.feedback_summary.satisfaction != null
                    ? ` (${Math.round(data.feedback_summary.satisfaction * 100)}% hài lòng)`
                    : ''}
                </span>
                <Button variant="ghost" size="sm" className="ml-auto h-7 px-2" onClick={() => refetch()}>
                  <RefreshCw className="h-3.5 w-3.5" />
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <TtsProvidersCard />

      <TtsProvidersFootnote />
    </div>
  )
}
