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
