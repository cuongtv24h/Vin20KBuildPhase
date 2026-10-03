import { AlertCircle, CheckCircle2, KeyRound, Loader2, Plus, RefreshCw, Sparkles, Trash2, Volume2, Zap } from 'lucide-react'
import { useState } from 'react'

import type { TtsProviderAdmin, TtsProviderPayload, TtsProviderTestResult } from '@pricepolicy/api-client/contracts'
import {
  useCreateTtsProvider,
  useDeleteTtsProvider,
  useTestTtsProvider,
  useTtsProviders,
  useUpdateTtsProvider,
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

/**
 * Quản trị nhà cung cấp TTS (đợt 22) — **dùng lại cơ chế của tab “Nhà cung cấp LLM”**:
 * nhập khoá ngay trên giao diện (lưu DB đã mã hoá, chỉ trả dạng che), nút “Test kết nối”,
 * ưu tiên DB → ENV, và **thêm được nhà cung cấp mới ngoài danh mục dựng sẵn**
 * (self-host, gateway nội bộ, nhà cung cấp khác).
 */

type FormState = TtsProviderPayload & { voices_text: string }

const EMPTY_FORM: FormState = {
  provider: '',
  label: '',
  mode: 'api',
  base_url: '',
  default_model: '',
  env_key: '',
  price_per_1m_chars: 0,
  currency: 'VND',
  price_note: '',
  verified_at: new Date().toISOString().slice(0, 10),
  note: '',
  voices_text: '',
  supports_streaming: false,
  voice_cloning: false,
  api_key: '',
  priority: 50,
  is_active: true,
}

const fmtPrice = (value: number, currency: string) =>
  value === 0 ? 'Miễn phí' : `${value.toLocaleString('vi-VN')} ${currency}`

const voicesToText = (voices: TtsProviderAdmin['voices']) =>
  voices.map((v) => `${v.code} | ${v.label} | ${v.gender}`).join('\n')

const fromProvider = (p: TtsProviderAdmin): FormState => ({
  provider: p.provider,
  label: p.label,
  mode: p.mode,
  base_url: p.base_url,
  default_model: p.default_model,
  env_key: p.env_key,
  price_per_1m_chars: p.price_per_1m_chars,
  currency: p.currency,
  price_note: p.price_note,
  verified_at: p.verified_at,
  note: p.note,
  voices_text: voicesToText(p.voices),
  supports_streaming: p.supports_streaming,
  voice_cloning: p.voice_cloning,
  api_key: '',
  priority: p.priority,
  is_active: true,
})

function ProviderFormDialog({
  open,
  editing,
  preset,
  onClose,
}: {
  open: boolean
  /** Có bản ghi DB ⇒ sửa bản ghi đó. */
  editing: TtsProviderAdmin | null
  /** Nhà cung cấp dựng sẵn chưa có bản ghi ⇒ tạo bản ghi đè với dữ liệu điền sẵn. */
  preset: TtsProviderAdmin | null
  onClose: () => void
}) {
  const createProvider = useCreateTtsProvider()
  const updateProvider = useUpdateTtsProvider()
  const testProvider = useTestTtsProvider()
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [error, setError] = useState<string | null>(null)
  const [initialisedFor, setInitialisedFor] = useState<string | null>(null)
  /** Bản ghi vừa lưu trong hộp thoại này — có `provider_id` mới bật được nút “Test kết nối”. */
  const [saved, setSaved] = useState<TtsProviderAdmin | null>(null)
  const [testResult, setTestResult] = useState<TtsProviderTestResult | null>(null)

  const target = editing?.provider_id ?? (preset ? `preset:${preset.provider}` : 'new')
  if (open && initialisedFor !== target) {
    setInitialisedFor(target)
    setError(null)
    setSaved(null)
    setTestResult(null)
    setForm(editing ? fromProvider(editing) : preset ? { ...fromProvider(preset), api_key: '' } : EMPTY_FORM)
  }
  if (!open && initialisedFor !== null) setInitialisedFor(null)

  const pending = createProvider.isPending || updateProvider.isPending
  const testing = testProvider.isPending
  const updating = Boolean(editing || saved)

  async function submit() {
    setError(null)
    if (!form.provider.trim() || !form.label.trim()) {
      setError('Cần nhập mã nhà cung cấp (ví dụ vieneu) và tên hiển thị.')
      return
    }
    if (form.mode === 'api' && !editing && !saved?.api_key_configured && !form.api_key?.trim()) {
      setError('Cần nhập API key cho nhà cung cấp mới.')
      return
    }
    try {
      // Lưu xong KHÔNG đóng hộp thoại: giữ lại để bấm “Test kết nối” ngay với cấu hình vừa lưu.
      const targetId = editing?.provider_id ?? saved?.provider_id
      const payload: TtsProviderPayload = { ...form, api_key: form.api_key ?? '' }
      const result = targetId
        ? await updateProvider.mutateAsync({ providerId: targetId, payload })
        : await createProvider.mutateAsync(payload)
      setSaved(result)
      setTestResult(null)
      // Không giữ khoá thô trong state sau khi đã lưu; lần lưu sau để trống = giữ khoá cũ.
      setForm((f) => ({ ...f, api_key: '' }))
      toast.success(editing ? `Đã cập nhật ${result.label}` : `Đã khai báo nhà cung cấp ${result.label}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không lưu được nhà cung cấp TTS.')
    }
  }

  async function runTest() {
    const ref = saved?.provider_id
    if (!ref) return
    setTestResult(null)
    try {
      const result = await testProvider.mutateAsync(ref)
      setTestResult(result)
      if (result.ok) toast.success(`Kết nối OK (${result.latency_ms} ms)`)
      else toast.error(result.detail)
    } catch (err) {
      setTestResult({
        provider: saved?.provider ?? form.provider,
        ok: false,
        latency_ms: 0,
        status: 'ERROR',
        detail: err instanceof Error ? err.message : 'Không kiểm tra được kết nối.',
      })
    }
  }

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((f) => ({ ...f, [key]: value }))
    // Sửa tiếp sau khi lưu ⇒ cấu hình trên form khác bản đã lưu; bỏ kết quả test cũ để không gây hiểu nhầm.
    if (saved) {
      setSaved(null)
      setTestResult(null)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {editing ? `Sửa nhà cung cấp ${editing.label}` : preset ? `Khai báo cho ${preset.label}` : 'Thêm nhà cung cấp TTS'}
          </DialogTitle>
          <DialogDescription>
            Nhập ngay trên giao diện — không cần sửa biến môi trường. Khoá lưu trong hệ thống (đã mã hoá) và được ưu
            tiên hơn ENV; bỏ trống khoá khi sửa nghĩa là giữ khoá cũ. Nhà cung cấp không có trong danh mục dựng sẵn
            vẫn thêm được (ví dụ máy chủ TTS tự dựng trong công ty).
          </DialogDescription>
        </DialogHeader>

        {/* Chrome suy luận “ô text + ô password = form đăng nhập” ⇒ tắt tự điền (đúng lỗi đã gặp ở tab LLM). */}
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
            <Label htmlFor="tts-provider">Mã nhà cung cấp *</Label>
            <Input
              id="tts-provider"
              name="tts-provider"
              autoComplete="off"
              data-form-type="other"
              value={form.provider}
              disabled={Boolean(editing)}
              onChange={(e) => set('provider', e.target.value.toLowerCase().replace(/\s+/g, '_'))}
              placeholder="vieneu / azure / openai"
            />
            <p className="text-[11px] text-muted-foreground">
              Mã trùng nhà cung cấp dựng sẵn = bản ghi đè (giữ nguyên vị trí trong danh mục); mã mới = nhà cung cấp mới.
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="tts-label">Tên hiển thị *</Label>
            <Input
              id="tts-label"
              name="tts-label"
              autoComplete="off"
              data-form-type="other"
              value={form.label}
              onChange={(e) => set('label', e.target.value)}
              placeholder="VieNeu TTS (tự dựng)"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="tts-mode">Cách đọc</Label>
            <select
              id="tts-mode"
              className="w-full rounded-md border border-input bg-background px-2 py-2 text-sm"
              value={form.mode}
              onChange={(e) => set('mode', e.target.value as 'api' | 'browser')}
            >
              <option value="api">Gọi API (cần khoá)</option>
              <option value="browser">Đọc tại trình duyệt (không cần khoá)</option>
            </select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="tts-base">Base URL</Label>
            <Input
              id="tts-base"
              name="tts-base-url"
              type="url"
              inputMode="url"
              autoComplete="off"
              data-form-type="other"
              data-lpignore="true"
              data-1p-ignore
              data-bwignore
              value={form.base_url ?? ''}
              onChange={(e) => set('base_url', e.target.value)}
              placeholder="http://10.0.0.5:8080"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="tts-model">Model mặc định</Label>
            <Input
              id="tts-model"
              name="tts-model"
              autoComplete="off"
              data-form-type="other"
              value={form.default_model ?? ''}
              onChange={(e) => set('default_model', e.target.value)}
              placeholder="vieneu-v3 / tts-1 / vi-VN-Wavenet-A"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="tts-env">Biến ENV chứa khoá (đường lui)</Label>
            <Input
              id="tts-env"
              name="tts-env-key"
              autoComplete="off"
              data-form-type="other"
              value={form.env_key ?? ''}
              onChange={(e) => set('env_key', e.target.value.toUpperCase())}
              placeholder="VIENEU_TTS_TOKEN"
            />
            <p className="text-[11px] text-muted-foreground">Chỉ dùng khi hệ thống chưa có khoá lưu trong DB.</p>
          </div>

          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="tts-key">
              API key {editing || saved ? '(bỏ trống để giữ khoá cũ)' : form.mode === 'browser' ? '(không cần)' : '*'}
            </Label>
            {/* `new-password`: trình duyệt hiểu là khoá MỚI, không tự điền bản đã lưu và không hỏi lưu mật khẩu. */}
            <Input
              id="tts-key"
              name="tts-api-key"
              type="password"
              autoComplete="new-password"
              data-form-type="other"
              data-lpignore="true"
              data-1p-ignore
              data-bwignore
              disabled={form.mode === 'browser'}
              value={form.api_key ?? ''}
              onChange={(e) => set('api_key', e.target.value)}
              placeholder={
                editing?.api_key_masked
                  ? `${editing.api_key_masked} — nhập để thay mới`
                  : saved?.api_key_masked
                    ? `${saved.api_key_masked} — nhập để thay mới`
                    : 'sk-... / token nhà cung cấp'
              }
            />
            <p className="text-[11px] text-muted-foreground">
              Khoá được mã hoá khi lưu và chỉ hiển thị dạng che (ví dụ <code>sk-t…abcd</code>).
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="tts-price">Đơn giá / 1 triệu ký tự</Label>
            <Input
              id="tts-price"
              type="number"
              min="0"
              step="1"
              value={form.price_per_1m_chars}
              onChange={(e) => set('price_per_1m_chars', Number(e.target.value))}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="tts-currency">Đơn vị tiền tệ</Label>
            <Input
              id="tts-currency"
              name="tts-currency"
              autoComplete="off"
              data-form-type="other"
              value={form.currency}
              onChange={(e) => set('currency', e.target.value.toUpperCase())}
              placeholder="VND / USD"
            />
          </div>

          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="tts-price-note">Ghi chú giá (nguồn, mốc đối chiếu)</Label>
            <Input
              id="tts-price-note"
              name="tts-price-note"
              autoComplete="off"
              data-form-type="other"
              value={form.price_note ?? ''}
              onChange={(e) => set('price_note', e.target.value)}
              placeholder="Giá công bố 2026-01: 320.000 VNĐ/1M ký tự"
            />
          </div>

          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="tts-voices">Danh sách giọng (mỗi dòng: mã | nhãn | giới tính)</Label>
            <textarea
              id="tts-voices"
              name="tts-voices"
              rows={4}
              className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
              value={form.voices_text}
              onChange={(e) => set('voices_text', e.target.value)}
              placeholder={'vi-female-01 | Nữ miền Bắc | female\nvi-male-01 | Nam miền Bắc | male'}
            />
            <p className="text-[11px] text-muted-foreground">Để trống khi sửa = giữ danh sách giọng hiện có.</p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="tts-priority">Thứ tự hiển thị (số nhỏ trước)</Label>
            <Input
              id="tts-priority"
              type="number"
              min="0"
              value={form.priority}
              onChange={(e) => set('priority', Number(e.target.value))}
            />
          </div>

          <div className="flex flex-col gap-2 sm:col-span-2">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-input"
                checked={form.is_active}
                onChange={(e) => set('is_active', e.target.checked)}
              />
              Đang dùng (tắt để tạm ẩn khỏi danh sách chọn giọng đọc)
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-input"
                checked={form.supports_streaming ?? false}
                onChange={(e) => set('supports_streaming', e.target.checked)}
              />
              Hỗ trợ đọc theo luồng (streaming)
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-input"
                checked={form.voice_cloning ?? false}
                onChange={(e) => set('voice_cloning', e.target.checked)}
              />
              Hỗ trợ nhân bản giọng nói
            </label>
          </div>
        </form>

        {saved && (
          <div className="space-y-2">
            {testResult ? (
              <div
                className={
                  'flex items-start gap-2 rounded-lg border p-3 text-xs ' +
                  (testResult.ok
                    ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
                    : 'border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-500')
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
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                Đã lưu cấu hình — bấm “Test kết nối” để kiểm tra bằng khoá vừa lưu.
              </p>
            )}
          </div>
        )}

        <DialogFooter className="gap-2 sm:justify-between">
          <div>
            {saved && (
              <Button variant="outline" onClick={() => void runTest()} disabled={testing || pending}>
                {testing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Zap className="mr-2 h-4 w-4" />}
                Test kết nối
              </Button>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={onClose} disabled={pending}>
              {saved ? 'Đóng' : 'Hủy'}
            </Button>
            <Button onClick={() => void submit()} disabled={pending}>
              {pending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {updating ? 'Lưu thay đổi' : 'Khai báo'}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** Thẻ quản trị nhà cung cấp TTS + khoá API — thay cho bảng chỉ-đọc trước đây (đợt 22). */
export function TtsProvidersCard() {
  const { data, isLoading, isError, refetch } = useTtsProviders()
  const deleteProvider = useDeleteTtsProvider()
  const testProvider = useTestTtsProvider()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<TtsProviderAdmin | null>(null)
  const [preset, setPreset] = useState<TtsProviderAdmin | null>(null)
  const [testing, setTesting] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<TtsProviderAdmin | null>(null)

  const items = data?.items ?? []

  async function runTest(p: TtsProviderAdmin) {
    const ref = p.provider_id || p.provider
    setTesting(ref)
    try {
      const result = await testProvider.mutateAsync(ref)
      if (result.ok) toast.success(`${p.label}: kết nối OK (${result.latency_ms} ms)`)
      else toast.error(`${p.label}: ${result.detail}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Không kiểm tra được kết nối.')
    } finally {
      setTesting(null)
    }
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <CardTitle className="text-base">Nhà cung cấp TTS &amp; khoá API</CardTitle>
            <CardDescription>
              Nhập khoá ngay trên giao diện (lưu đã mã hoá, chỉ hiển thị dạng che) — không cần sửa biến môi trường.
              Khoá lưu trong hệ thống được ưu tiên hơn ENV. Thêm được cả nhà cung cấp ngoài danh mục dựng sẵn.
            </CardDescription>
            <p className="pt-1 text-[11px] text-muted-foreground">
              Đơn giá là giá niêm yết của nhà cung cấp, kèm mốc kiểm chứng — đối chiếu lại trước khi quyết toán.
              Nhà cung cấp gắn nhãn <strong>Tuỳ chỉnh</strong> là do quản trị viên tự thêm.
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Badge variant="outline" className="text-[11px]">
              Nguồn: {data?.source === 'db' ? 'DB + danh mục' : 'danh mục dựng sẵn'}
            </Badge>
            <Button variant="ghost" size="sm" className="h-8 px-2" onClick={() => refetch()} title="Tải lại">
              <RefreshCw className="h-3.5 w-3.5" />
            </Button>
            <Button
              size="sm"
              onClick={() => {
                setEditing(null)
                setPreset(null)
                setDialogOpen(true)
              }}
            >
              <Plus className="mr-2 h-4 w-4" />
              Thêm nhà cung cấp
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nhà cung cấp</TableHead>
              <TableHead className="text-right">Đơn giá / 1M ký tự</TableHead>
              <TableHead className="w-[190px]">Khoá API</TableHead>
              <TableHead className="w-[130px]">Kiểm tra</TableHead>
              <TableHead>Ghi chú</TableHead>
              <TableHead className="w-[130px] text-right">Thao tác</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={6} className="h-28 text-center text-muted-foreground">
                  <Loader2 className="mx-auto h-5 w-5 animate-spin" />
                </TableCell>
              </TableRow>
            ) : isError ? (
              <TableRow>
                <TableCell colSpan={6} className="h-28 text-center text-destructive">
                  Không tải được danh sách nhà cung cấp TTS.
                </TableCell>
              </TableRow>
            ) : items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="h-28 text-center text-muted-foreground">
                  Chưa có nhà cung cấp nào.
                </TableCell>
              </TableRow>
            ) : (
              items.map((p) => (
                <TableRow key={p.provider_id || p.provider} className={p.is_active ? '' : 'opacity-60'}>
                  <TableCell>
                    <div className="flex items-center gap-2 font-medium">
                      {p.label}
                      {p.custom && (
                        <Badge variant="outline" className="text-[10px]">
                          <Sparkles className="mr-1 h-3 w-3" />
                          Tuỳ chỉnh
                        </Badge>
                      )}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {p.provider}
                      {p.mode === 'browser' ? ' · đọc tại trình duyệt' : p.default_model ? ` · ${p.default_model}` : ''}
                      {p.base_url ? ` · ${p.base_url}` : ''}
                      {p.voices.length ? ` · ${p.voices.length} giọng` : ''}
                      {p.supports_streaming ? ' · có streaming' : ''}
                    </div>
                  </TableCell>
                  <TableCell className="text-right text-sm">{fmtPrice(p.price_per_1m_chars, p.currency)}</TableCell>
                  <TableCell>
                    {p.mode === 'browser' ? (
                      <span className="text-xs text-muted-foreground">Không cần</span>
                    ) : p.api_key_configured ? (
                      <div className="space-y-0.5">
                        <Badge className="bg-emerald-600 text-[10px] hover:bg-emerald-700">Đã có</Badge>
                        <div className="text-[11px] text-muted-foreground">{p.key_source_label}</div>
                        {p.api_key_masked && <div className="font-mono text-[11px] text-muted-foreground">{p.api_key_masked}</div>}
                      </div>
                    ) : (
                      <div className="space-y-0.5">
                        <Badge variant="outline" className="text-[10px] text-amber-600">
                          Chưa có
                        </Badge>
                        {p.env_key && <div className="text-[11px] text-muted-foreground">ENV: {p.env_key}</div>}
                      </div>
                    )}
                  </TableCell>
                  <TableCell>
                    {p.last_test_status ? (
                      <div className="flex items-center gap-1.5 text-xs">
                        {p.last_test_status === 'OK' ? (
                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                        ) : (
                          <AlertCircle className="h-3.5 w-3.5 text-amber-600" />
                        )}
                        <span>{p.last_test_status}</span>
                        {p.last_test_latency_ms != null && p.last_test_latency_ms > 0 && (
                          <span className="text-muted-foreground">{Math.round(p.last_test_latency_ms)} ms</span>
                        )}
                      </div>
                    ) : (
                      <span className="text-xs text-muted-foreground">Chưa kiểm tra</span>
                    )}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {p.price_note || p.note}
                    {p.verified_at && <div className="text-[11px]">Đối chiếu: {p.verified_at}</div>}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-muted-foreground hover:text-foreground"
                        title="Kiểm tra kết nối"
                        disabled={testing === (p.provider_id || p.provider)}
                        onClick={() => void runTest(p)}
                      >
                        {testing === (p.provider_id || p.provider) ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Zap className="h-4 w-4" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-muted-foreground hover:text-foreground"
                        title={p.has_db_row ? 'Sửa nhà cung cấp' : 'Khai báo khoá / đơn giá cho nhà cung cấp này'}
                        onClick={() => {
                          setEditing(p.has_db_row ? p : null)
                          setPreset(p.has_db_row ? null : p)
                          setDialogOpen(true)
                        }}
                      >
                        <KeyRound className="h-4 w-4" />
                      </Button>
                      {p.has_db_row && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-destructive/70 hover:bg-destructive/10 hover:text-destructive"
                          title="Xoá bản ghi"
                          onClick={() => setDeleting(p)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </CardContent>

      <ProviderFormDialog open={dialogOpen} editing={editing} preset={preset} onClose={() => setDialogOpen(false)} />

      {deleting && (
        <Dialog open onOpenChange={() => setDeleting(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-destructive">
                <Trash2 className="h-5 w-5" /> Xoá bản ghi nhà cung cấp
              </DialogTitle>
              <DialogDescription>
                Bạn có chắc muốn xoá bản ghi <strong>{deleting.label}</strong>?{' '}
                {deleting.custom
                  ? 'Đây là nhà cung cấp tự thêm nên sẽ biến mất khỏi danh sách chọn giọng đọc.'
                  : 'Đây là nhà cung cấp dựng sẵn — xoá chỉ bỏ phần khai báo này, nhà cung cấp vẫn còn trong danh mục với đơn giá gốc.'}
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
                    const result = await deleteProvider.mutateAsync(deleting.provider_id)
                    toast.success(
                      result.still_available
                        ? `Đã bỏ khai báo cho ${deleting.label} — danh mục gốc vẫn giữ nhà cung cấp này`
                        : `Đã xoá ${deleting.label}`,
                    )
                    if (result.used_by_scopes > 0) {
                      toast.error(
                        `Có ${result.used_by_scopes} thiết lập giọng đọc đang chọn nhà cung cấp này — hệ thống đã tự chuyển về giọng trình duyệt.`,
                      )
                    }
                    setDeleting(null)
                  } catch (err) {
                    toast.error(err instanceof Error ? err.message : 'Không xoá được bản ghi.')
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
    </Card>
  )
}

/** Ghi chú dưới cùng của tab giọng đọc — nhắc khoá lấy từ đâu và tài liệu kỹ thuật. */
export function TtsProvidersFootnote() {
  return (
    <div className="space-y-1">
      <p className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
        <Volume2 className="h-3 w-3" />
        Khoá API lấy theo thứ tự: khoá nhập trên giao diện (DB) → biến môi trường máy chủ → khoá nhà cung cấp LLM
        trùng tên. Tài liệu kỹ thuật: <code>docs/team_report/tts_integration_plan.md</code>. Lựa chọn riêng của
        từng nhân viên nằm trong workspace ở nút “Giọng đọc”.
      </p>
      <p className="text-[11px] text-muted-foreground">
        Mức độ hoàn thiện: màn hình này quản lý <strong>nhà cung cấp &amp; khoá</strong>. Tiếng đọc hiện vẫn do
        trình duyệt tổng hợp (0 đồng); đường gọi nhà cung cấp trả phí qua backend (đã chốt trong tài liệu §7) là
        bước kế tiếp — khi nối xong, các nhà cung cấp có khoá ở trên sẽ được dùng để đọc.
      </p>
    </div>
  )
}
