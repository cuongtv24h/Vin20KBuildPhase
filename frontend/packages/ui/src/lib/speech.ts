/**
 * Đọc câu trả lời Copilot bằng **Web Speech API** của trình duyệt.
 *
 * Vì sao bắt đầu từ đây: máy nào cũng có sẵn, 0 đồng, không cần khoá API — nên Sale nghe được ngay
 * hôm nay; còn nhà cung cấp TTS trả phí (`tts_providers` phía backend) là bước nâng cấp giọng đọc
 * cho đồng nhất toàn hệ thống. Hai đường đi dùng chung một hợp đồng thiết lập (`/settings/tts`).
 *
 * Toàn bộ hàm ở đây **không ném lỗi ra ngoài**: máy không có giọng tiếng Việt hay trình duyệt không
 * hỗ trợ thì trả về lý do để UI nói thật với người dùng, thay vì im lặng.
 */

export interface SpeakOptions {
  /** Mã giọng (`vi-VN`, `vi-VN-Wavenet-A`…) — nhà cung cấp trình duyệt dùng mã ngôn ngữ. */
  voice?: string
  /** Tốc độ đọc 0.5–2.0. */
  speed?: number
  /** Tiếng Việt: giọng đọc từ chối đọc nếu văn bản quá dài → cắt bớt. */
  maxChars?: number
  onEnd?: () => void
  onError?: (reason: string) => void
}

export interface SpeakResult {
  ok: boolean
  reason?: string
  /** Số ký tự thực sự được đọc (sau khi cắt theo `maxChars`). */
  chars: number
  /** Mã giọng/ngôn ngữ đã dùng. */
  voiceUsed?: string
}

export const isSpeechSupported = () =>
  typeof window !== 'undefined' && 'speechSynthesis' in window && typeof window.SpeechSynthesisUtterance === 'function'

/**
 * Dọn văn bản trước khi đọc: bỏ markdown/citation/ký tự trang trí để giọng đọc không đọc cả dấu
 * sao hay số hiệu điều khoản trong ngoặc.
 */
export function toSpeakableText(raw: string): string {
  return raw
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // link markdown → nhãn
    .replace(/[*_`>#]/g, '')
    .replace(/\((?:Điều|Khoản|Mục)[^)]*\)/gi, ', ')
    .replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/gu, '') // emoji
    .replace(/\s+/g, ' ')
    .trim()
}

let currentUtterance: SpeechSynthesisUtterance | null = null

/** Dừng ngay câu đang đọc (bấm lần hai / đổi câu / rời trang). */
export function stopSpeaking() {
  if (!isSpeechSupported()) return
  try {
    window.speechSynthesis.cancel()
  } catch {
    /* một số trình duyệt ném lỗi khi chưa từng đọc gì — bỏ qua */
  }
  currentUtterance = null
}

/**
 * Đọc một đoạn văn bản. Trả về ngay kết quả "bắt đầu được hay không"; `onEnd` báo khi đọc xong.
 *
 * Nếu máy không có giọng tiếng Việt, hàm vẫn đọc bằng giọng mặc định của hệ thống nhưng báo
 * `reason` để UI nhắc người dùng (tránh hiểu nhầm là lỗi hệ thống).
 */
export function speakText(text: string, options: SpeakOptions = {}): SpeakResult {
  const clean = toSpeakableText(text)
  const maxChars = options.maxChars ?? 600
  const spoken = clean.length > maxChars ? `${clean.slice(0, maxChars).trimEnd()}…` : clean

  if (!isSpeechSupported()) {
    const reason = 'Trình duyệt không hỗ trợ đọc thành tiếng (Web Speech API).'
    options.onError?.(reason)
    return { ok: false, reason, chars: 0 }
  }
  if (!spoken) {
    const reason = 'Không có nội dung để đọc.'
    options.onError?.(reason)
    return { ok: false, reason, chars: 0 }
  }

  stopSpeaking()

  const utterance = new SpeechSynthesisUtterance(spoken)
  const wanted = options.voice?.trim() || 'vi-VN'
  const voices = window.speechSynthesis.getVoices()
  // Khớp mã giọng theo: chính xác → cùng ngôn ngữ (vi-VN → vi-*) → mặc định của máy.
  const match =
    voices.find((v) => v.voiceURI === wanted || v.name === wanted) ??
    voices.find((v) => v.lang?.toLowerCase() === wanted.toLowerCase()) ??
    voices.find((v) => wanted.toLowerCase().startsWith('vi') && v.lang?.toLowerCase().startsWith('vi'))
  if (match) utterance.voice = match
  utterance.lang = match?.lang ?? wanted
  utterance.rate = Math.min(Math.max(options.speed ?? 1, 0.5), 2)

  let reason: string | undefined
  if (wanted.toLowerCase().startsWith('vi') && !voices.some((v) => v.lang?.toLowerCase().startsWith('vi'))) {
    reason = 'Máy chưa cài giọng tiếng Việt — đang đọc bằng giọng mặc định của hệ thống.'
  }

  utterance.onend = () => {
    currentUtterance = null
    options.onEnd?.()
  }
  utterance.onerror = (event) => {
    currentUtterance = null
    const message = `Không đọc được câu trả lời (${event.error ?? 'lỗi không xác định'}).`
    options.onError?.(message)
  }

  currentUtterance = utterance
  try {
    window.speechSynthesis.speak(utterance)
  } catch {
    const message = 'Trình duyệt chặn đọc thành tiếng — cần thao tác trực tiếp của người dùng.'
    options.onError?.(message)
    return { ok: false, reason: message, chars: spoken.length }
  }

  return { ok: true, reason, chars: spoken.length, voiceUsed: utterance.voice?.lang ?? utterance.lang }
}

/** Đang đọc hay không (để vẽ trạng thái nút 🔊/⏹). */
export const isSpeaking = () => isSpeechSupported() && window.speechSynthesis.speaking

/**
 * Danh sách giọng có sẵn trên máy. `getVoices()` ban đầu có thể rỗng nên phải nghe `voiceschanged`.
 */
export function listLocalVoices(): Promise<Array<{ code: string; label: string }>> {
  if (!isSpeechSupported()) return Promise.resolve([])
  const read = () =>
    window.speechSynthesis
      .getVoices()
      .filter((v) => v.lang?.toLowerCase().startsWith('vi'))
      .map((v) => ({ code: v.voiceURI || v.lang, label: `${v.name} (${v.lang})` }))

  const immediate = read()
  if (immediate.length) return Promise.resolve(immediate)

  return new Promise((resolve) => {
    const timer = setTimeout(() => resolve(read()), 1_200)
    window.speechSynthesis.onvoiceschanged = () => {
      clearTimeout(timer)
      resolve(read())
    }
  })
}

// ─── Nhập liệu bằng giọng nói (Web Speech API — "rảnh tay") ────────────────────────────────
//
// Dùng chung Web Speech API với TTS: máy nào chạy được TTS của trình duyệt thì thường cũng có
// nhận dạng giọng nói (Chrome/Edge/Cốc Cốc; Safari/Firefox không có). 0 đồng, không cần khoá API.
// Lưu ý trung thực với người dùng: Chrome gửi audio lên dịch vụ nhận dạng của Google — đây là
// giới hạn của trình duyệt, muốn tránh thì phải tự chạy model nhận dạng tại chỗ (việc của đợt sau).
//
// Toàn bộ hàm ở đây không ném lỗi ra ngoài: trình duyệt không hỗ trợ / bị chặn micro / mất mạng đều
// trả về lý do để UI nói thật với người dùng.

/** Kết quả nhận dạng tối thiểu (TS không có sẵn kiểu của Web Speech API). */
export interface SpeechResultLike {
  isFinal: boolean
  length: number
  [index: number]: { transcript: string }
}

export interface SpeechEventLike {
  resultIndex: number
  results: { length: number; [index: number]: SpeechResultLike }
}

export interface SpeechErrorLike {
  error?: string
  message?: string
}

/** Bề mặt của `SpeechRecognition` mà lớp này dùng — đủ để thay bằng đối tượng giả trong test. */
export interface SpeechRecognitionLike {
  lang: string
  continuous: boolean
  interimResults: boolean
  maxAlternatives: number
  start(): void
  stop(): void
  abort(): void
  onresult: ((event: SpeechEventLike) => void) | null
  onerror: ((event: SpeechErrorLike) => void) | null
  onend: (() => void) | null
  onstart: (() => void) | null
}

export type SpeechRecognitionCtor = new () => SpeechRecognitionLike

/** Tìm constructor nhận dạng giọng nói của trình duyệt (Chrome/Edge dùng tiền tố `webkit`). */
export function getSpeechRecognitionCtor(): SpeechRecognitionCtor | null {
  if (typeof window === 'undefined') return null
  const scope = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor
    webkitSpeechRecognition?: SpeechRecognitionCtor
  }
  return scope.SpeechRecognition ?? scope.webkitSpeechRecognition ?? null
}

export const isSpeechToTextSupported = () => getSpeechRecognitionCtor() !== null

/** Câu giải thích khi trình duyệt không hỗ trợ — nói rõ phải làm gì, không im lặng. */
export const SPEECH_TO_TEXT_UNSUPPORTED_MESSAGE =
  'Trình duyệt này không hỗ trợ nhập bằng giọng nói. Anh/chị dùng Chrome, Edge hoặc Cốc Cốc giúp em.'

export interface SpeechToTextOptions {
  /** Ngôn ngữ nhận dạng — mặc định tiếng Việt. */
  lang?: string
  /** `true` = chế độ rảnh tay: tự nghe lại sau mỗi lần trình duyệt tự dừng. */
  continuous?: boolean
  /** Hiện chữ ngay khi đang nói (người dùng thấy máy đang nghe đúng). */
  interimResults?: boolean
  /** Chữ tạm khi đang nói — UI hiển thị để người dùng biết máy đang nghe. */
  onPartial?: (text: string) => void
  /** Câu đã chốt (trình duyệt trả kết quả cuối) — UI ghép vào ô nhập. */
  onFinal?: (text: string) => void
  /** Đổi trạng thái nghe (để tô sáng nút micro). */
  onStateChange?: (listening: boolean) => void
  /** Lỗi cần hiển thị cho người dùng (đã dịch sang tiếng Việt). */
  onError?: (message: string) => void
}

export interface SpeechToTextController {
  supported: boolean
  start(): void
  stop(): void
  isListening(): boolean
}

const MIC_ERROR_MESSAGES: Record<string, string> = {
  'not-allowed': 'Micro đang bị chặn. Anh/chị bấm vào biểu tượng ổ khóa trên thanh địa chỉ và cho phép micro.',
  'service-not-allowed': 'Trình duyệt từ chối dịch vụ nhận dạng giọng nói. Kiểm tra quyền micro và thử lại.',
  'audio-capture': 'Không tìm thấy micro. Anh/chị kiểm tra tai nghe/micro rồi thử lại.',
  network: 'Nhận dạng giọng nói cần mạng — kết nối đang gián đoạn, anh/chị thử lại.',
  'no-speech': '', // im lặng vài giây: bình thường, không cần báo lỗi
  aborted: '',
}

/**
 * Tạo bộ điều khiển nhập liệu bằng giọng nói.
 *
 * Chế độ rảnh tay: `continuous = true`, và nếu trình duyệt tự dừng (Chrome dừng sau một khoảng
 * im lặng) thì **tự nghe lại** cho tới khi người dùng bấm dừng — đúng nghĩa "nói liên tục không
 * cần chạm máy".
 */
export function createSpeechToText(options: SpeechToTextOptions = {}): SpeechToTextController {
  const Ctor = getSpeechRecognitionCtor()
  if (!Ctor) {
    return {
      supported: false,
      start: () => options.onError?.(SPEECH_TO_TEXT_UNSUPPORTED_MESSAGE),
      stop: () => undefined,
      isListening: () => false,
    }
  }

  const recognition = new Ctor()
  recognition.lang = options.lang ?? 'vi-VN'
  recognition.continuous = options.continuous ?? true
  recognition.interimResults = options.interimResults ?? true
  recognition.maxAlternatives = 1

  let listening = false
  /** Người dùng còn muốn nghe hay đã bấm dừng (khác với việc trình duyệt tự dừng). */
  let wanted = false
  let restartTimer: ReturnType<typeof setTimeout> | null = null

  const setListening = (next: boolean) => {
    if (listening === next) return
    listening = next
    options.onStateChange?.(next)
  }

  recognition.onstart = () => setListening(true)

  recognition.onresult = (event) => {
    let partial = ''
    let final = ''
    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      const result = event.results[i]
      const text = result?.[0]?.transcript ?? ''
      if (result?.isFinal) final += text
      else partial += text
    }
    if (final) options.onFinal?.(final.trim())
    if (partial) options.onPartial?.(partial.trim())
  }

  recognition.onerror = (event) => {
    const code = event.error ?? ''
    const message = MIC_ERROR_MESSAGES[code] ?? `Lỗi nhận dạng giọng nói: ${event.message || code || 'không rõ'}`
    // `no-speech`/`aborted` là chuyện bình thường trong chế độ rảnh tay → không làm phiền người dùng.
    if (message) options.onError?.(message)
    if (code === 'not-allowed' || code === 'service-not-allowed' || code === 'audio-capture') wanted = false
    setListening(false)
  }

  recognition.onend = () => {
    setListening(false)
    // Rảnh tay: trình duyệt tự dừng sau quãng im lặng → nghe lại, trừ khi người dùng đã bấm dừng.
    if (!wanted) return
    restartTimer = setTimeout(() => {
      if (!wanted) return
      try {
        recognition.start()
      } catch {
        /* đang chạy rồi thì bỏ qua */
      }
    }, 250)
  }

  return {
    supported: true,
    start: () => {
      wanted = true
      try {
        recognition.start()
      } catch {
        /* gọi start hai lần liên tiếp: trình duyệt ném lỗi, coi như đang nghe */
        setListening(true)
      }
    },
    stop: () => {
      wanted = false
      if (restartTimer) clearTimeout(restartTimer)
      try {
        recognition.stop()
      } catch {
        /* chưa chạy thì thôi */
      }
      setListening(false)
    },
    isListening: () => listening,
  }
}
