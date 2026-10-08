/**
 * Ghi âm micro bằng `MediaRecorder` để gửi lên backend nghe bằng **Whisper**.
 *
 * Vì sao thêm đường này dù `speech.ts` đã có Web Speech API:
 * - Web Speech API chỉ sống trên Chrome/Edge/Cốc Cốc, và **audio đi qua máy chủ của hãng trình duyệt** —
 *   mình không log được, không đo được chất lượng, không bias được từ vựng dự án.
 * - Whisper phía backend nhận `prompt` là danh sách mã căn/thuật ngữ nên "ZEN-A-1205" không còn ra
 *   "ZEN A 1205" — sai một ký tự là Copilot tra sai căn.
 * Web Speech API vẫn được GIỮ LÀM LƯỚI AN TOÀN: backend chưa cấu hình khoá Groq hoặc hết hạn mức thì
 * giao diện tự rơi về `createSpeechToText` (xem `SalesWorkspacePage`).
 *
 * Nguyên tắc giống `speech.ts`: **không ném lỗi ra ngoài** — máy không có micro hay người dùng chặn quyền
 * thì trả về lý do bằng tiếng Việt để UI nói thật với Sale, thay vì im lặng.
 */

export interface RecordedClip {
  /** Audio đã ghi (webm/opus trên Chrome, mp4 trên Safari). */
  blob: Blob
  mimeType: string
  /** Thời lượng ghi thực tế (làm tròn giây) — để UI báo "câu quá ngắn" trước khi tốn một lượt gọi. */
  seconds: number
}

export interface VoiceRecorderOptions {
  /** Tự dừng sau số giây này (mặc định 120 — khớp trần `STT_MAX_DURATION_SECONDS` phía backend). */
  maxSeconds?: number
  /** Ép kiểu MIME; bỏ trống thì tự chọn kiểu đầu tiên trình duyệt hỗ trợ. */
  mimeType?: string
  /** Ghi xong một câu: nhận blob để gửi lên backend. */
  onStop?: (clip: RecordedClip) => void
  /** Lý do lỗi đã dịch sang tiếng Việt. */
  onError?: (message: string) => void
  /** Đổi trạng thái ghi (để tô sáng nút micro). */
  onStateChange?: (recording: boolean) => void
}

export interface VoiceRecorderController {
  supported: boolean
  start(): Promise<void>
  /** Dừng và LẤY kết quả (onStop sẽ được gọi). */
  stop(): void
  /** Dừng và BỎ kết quả (Sale bấm nhầm micro). */
  cancel(): void
  isRecording(): boolean
}

/** Thứ tự ưu tiên: opus trong webm nhỏ và rõ nhất cho giọng nói; mp4 để Safari/iOS không bị loại. */
export const AUDIO_MIME_CANDIDATES: readonly string[] = [
  'audio/webm;codecs=opus',
  'audio/webm',
  'audio/ogg;codecs=opus',
  'audio/mp4',
]

export const VOICE_RECORDER_UNSUPPORTED_MESSAGE =
  'Trình duyệt này không hỗ trợ ghi âm để gửi trợ lý. Anh/chị dùng Chrome, Edge hoặc Cốc Cốc giúp em.'

/** Ghi âm ngắn hơn mức này thì gần chắc là bấm nhầm — không đáng tốn một lượt gọi nhà cung cấp. */
export const MIN_CLIP_SECONDS = 1

const MIC_ERROR_MESSAGES: Record<string, string> = {
  NotAllowedError: 'Micro đang bị chặn. Anh/chị bấm biểu tượng ổ khóa trên thanh địa chỉ và cho phép micro.',
  PermissionDeniedError: 'Micro đang bị chặn. Anh/chị bấm biểu tượng ổ khóa trên thanh địa chỉ và cho phép micro.',
  NotFoundError: 'Không tìm thấy micro. Anh/chị kiểm tra tai nghe/micro rồi thử lại.',
  DevicesNotFoundError: 'Không tìm thấy micro. Anh/chị kiểm tra tai nghe/micro rồi thử lại.',
  NotReadableError: 'Micro đang bị ứng dụng khác chiếm. Anh/chị tắt Zoom/Zalo rồi thử lại.',
  TrackStartError: 'Micro đang bị ứng dụng khác chiếm. Anh/chị tắt Zoom/Zalo rồi thử lại.',
  OverconstrainedError: 'Không đáp ứng được yêu cầu về micro. Anh/chị thử tai nghe/micro khác giúp em.',
  SecurityError: 'Trình duyệt chặn ghi âm vì trang không chạy qua HTTPS.',
  AbortError: 'Đã dừng ghi âm.',
  InvalidStateError: 'Trình duyệt chưa sẵn sàng ghi âm. Anh/chị bấm lại lần nữa giúp em.',
  QuotaExceededError: 'Hết dung lượng ghi âm tạm thời của trình duyệt.',
}

/** Dịch lỗi `getUserMedia`/`MediaRecorder` sang câu người Sale hiểu và làm theo được. */
export function describeMediaError(name: string, message?: string): string {
  return MIC_ERROR_MESSAGES[name] ?? `Không ghi âm được (${name || message || 'không rõ nguyên nhân'}).`
}

/**
 * Chọn kiểu MIME trình duyệt hỗ trợ. Nhận hàm kiểm tra để **test được trong Node** (nơi không có
 * `MediaRecorder`), thay vì gọi thẳng API toàn cục.
 */
export function pickAudioMimeType(isSupported: (mimeType: string) => boolean, preferred?: string): string | null {
  if (preferred && isSupported(preferred)) return preferred
  for (const candidate of AUDIO_MIME_CANDIDATES) {
    if (isSupported(candidate)) return candidate
  }
  return null
}

export function isVoiceRecorderSupported(): boolean {
  if (typeof navigator === 'undefined' || typeof MediaRecorder === 'undefined') return false
  const devices = (navigator as Navigator).mediaDevices
  return Boolean(devices && typeof devices.getUserMedia === 'function')
}

/**
 * Tạo bộ ghi âm micro. Mỗi lần `stop()` là MỘT clip → một lượt gửi lên backend nghe.
 *
 * `start(250)` (timeslice) để nếu trình duyệt sập giữa chừng vẫn còn dữ liệu, và `maxSeconds` tự dừng
 * khi Sale quên tắt micro — trần này khớp `STT_MAX_DURATION_SECONDS` nên không bị backend từ chối 413.
 */
export function createVoiceRecorder(options: VoiceRecorderOptions = {}): VoiceRecorderController {
  const maxSeconds = Math.max(5, options.maxSeconds ?? 120)
  let recorder: MediaRecorder | null = null
  let stream: MediaStream | null = null
  let chunks: Blob[] = []
  let recording = false
  let cancelled = false
  let startedAt = 0
  let autoStopTimer: ReturnType<typeof setTimeout> | null = null

  const setState = (next: boolean) => {
    if (recording === next) return
    recording = next
    options.onStateChange?.(next)
  }

  const cleanup = () => {
    stream?.getTracks().forEach((track) => track.stop())
    stream = null
    recorder = null
    if (autoStopTimer) {
      clearTimeout(autoStopTimer)
      autoStopTimer = null
    }
  }

  const stopRecording = () => {
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop()
      return
    }
    cleanup()
    setState(false)
  }

  const controller: VoiceRecorderController = {
    supported: isVoiceRecorderSupported(),

    async start() {
      if (!isVoiceRecorderSupported()) {
        options.onError?.(VOICE_RECORDER_UNSUPPORTED_MESSAGE)
        return
      }
      if (recording) return

      let captured: MediaStream
      try {
        captured = await navigator.mediaDevices.getUserMedia({
          audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
        })
      } catch (error) {
        const domError = error as DOMException
        options.onError?.(describeMediaError(domError?.name ?? '', domError?.message))
        return
      }
      stream = captured

      const mimeType = pickAudioMimeType((candidate) => MediaRecorder.isTypeSupported(candidate), options.mimeType)
      try {
        recorder = mimeType
          ? new MediaRecorder(stream, { mimeType, audioBitsPerSecond: 32_000 })
          : new MediaRecorder(stream)
      } catch (error) {
        cleanup()
        const err = error as Error
        options.onError?.(describeMediaError(err?.name ?? '', err?.message))
        return
      }

      chunks = []
      cancelled = false
      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data && event.data.size > 0) chunks.push(event.data)
      }
      recorder.onerror = () => {
        cleanup()
        setState(false)
        options.onError?.('Ghi âm bị lỗi giữa chừng. Anh/chị bấm micro thử lại, hoặc gõ câu hỏi giúp em.')
      }
      recorder.onstop = () => {
        const seconds = Math.max(1, Math.round((Date.now() - startedAt) / 1000))
        const usedType = recorder?.mimeType || mimeType || 'audio/webm'
        const blob = new Blob(chunks, { type: usedType })
        const wasCancelled = cancelled
        cleanup()
        setState(false)
        if (wasCancelled) return
        if (blob.size === 0) {
          options.onError?.('Không ghi được âm thanh nào. Anh/chị kiểm tra micro rồi bấm lại giúp em.')
          return
        }
        if (seconds < MIN_CLIP_SECONDS) {
          options.onError?.('Câu nói ngắn quá, em chưa nghe kịp. Anh/chị bấm micro và nói lại giúp em.')
          return
        }
        options.onStop?.({ blob, mimeType: usedType, seconds })
      }

      startedAt = Date.now()
      recorder.start(250)
      setState(true)
      autoStopTimer = setTimeout(stopRecording, maxSeconds * 1000)
    },

    stop: stopRecording,

    cancel() {
      cancelled = true
      stopRecording()
    },

    isRecording: () => recording,
  }

  return controller
}
