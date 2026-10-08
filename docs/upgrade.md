# UPGRADE.md — Hàng đợi nâng cấp (đã phân tích, CHƯA xếp lịch)

Tài liệu này giữ những hạng mục **đã được phân tích kỹ nhưng người dùng quyết định hoãn**, kèm đủ bằng
chứng, đường dẫn file thật, ước lượng công và **các câu hỏi còn treo** — để khi mở lại không phải điều
tra lại từ đầu và không mất quyết định cũ.

Quy ước:

- Mỗi hạng mục có mã `U-xx`, trạng thái (`CHỜ` / `CHỜ NGƯỜI DÙNG` / `ĐÃ LÀM`), độ ưu tiên, và ngày ghi.
- **Không tự ý triển khai** bất kỳ mục nào ở đây khi chưa được chốt lịch — đây là hàng đợi, không phải việc đang làm.
- Khi một mục được làm xong: đổi trạng thái thành `ĐÃ LÀM`, ghi commit, và **giữ nguyên phần phân tích** làm bằng chứng quyết định.
- Số liệu giá/hạn mức của nhà cung cấp bên ngoài là **tại thời điểm ghi** — phải kiểm tra lại trước khi cam kết với khách/đội.

## Mục lục

| Mã | Hạng mục | Trạng thái | Ưu tiên | Ghi ngày |
|---|---|---|---|---|
| U-01 | Hội thoại giọng nói trực tiếp Sale ↔ Copilot | CHỜ | Sau khi hết bug MVP | 2026-10-08 |
| U-02 | Giọng đọc TTS tiếng Việt (3 lỗi đã chẩn đoán, sửa 0 đồng) | CHỜ | Cao hơn U-01 nếu bật đọc thành tiếng | 2026-10-08 |
| U-03 | Bốn phần còn thiếu của đợt giao STT (`ebfe613`) | CHỜ | Thấp | 2026-10-08 |
| U-04 | CI cài theo `requirements.lock.txt` + chờ kết quả đối chiếu env trên VM | CHỜ NGƯỜI DÙNG | Trung bình | 2026-10-08 |

---

## U-01 — Hội thoại giọng nói trực tiếp Sale ↔ Copilot

**Trạng thái:** CHỜ · **Ưu tiên:** sau bug MVP · **Ghi ngày:** 2026-10-08

### Bối cảnh và quyết định của người dùng (2026-10-08)

Người dùng xác nhận ba điều, theo đúng thứ tự ưu tiên của họ:

1. "Mục đích chính ban đầu — chế độ nói để chuyển hoá thành text — như hiện nay thì **OK rồi**."
2. "Chế độ đọc lại thành voice từ câu trả lời của AI **không phải điểm ưu tiên tuyệt đối**."
3. "Cái tôi nghĩ tốt hơn là **tính năng giao tiếp trực tiếp bằng giọng nói giữa Sale và Copilot**."

và chốt: *"Tạm ghi lại phần này vào chế độ chờ nâng cấp… hiện tại chưa có thời gian, ưu tiên cho các
tính năng MVP còn đang nhiều bug."*

### Đã có gì (nền móng — KHÔNG phải làm lại)

Đợt giao `ebfe613` (2026-10-08) đã dựng xong **chân ASR** của vòng hội thoại:

- `src/services/stt_providers.py` — danh mục nhà cung cấp `groq → openai → browser`, khoá **DB đè `.env`**
  (bảng `stt_providers`, mã hoá Fernet), chuỗi fallback theo `priority`, hạn mức phút audio/ngày,
  `normalize_transcript()` sửa mã căn/thuật ngữ, ghi sổ `llm_usage.jsonl` với `kind = "stt"`.
- `src/api/endpoints/stt.py` — `POST /api/v1/stt/transcribe` (multipart, bắt buộc phiên nhân viên, trần
  dung lượng, 415/422/413/429/503/502 rõ ràng), `GET /health`, `GET /quota`, 4 endpoint ADMIN cấu hình nhà cung cấp.
- `frontend/packages/ui/src/lib/voiceRecorder.ts` — `MediaRecorder` (ưu tiên webm/opus, mp4 cho Safari),
  tự dừng ở trần backend, lỗi micro dịch sang tiếng Việt.
- `frontend/apps/internal/src/features/sale/SalesWorkspacePage.tsx` — `toggleVoiceInput` / `uploadVoiceClip`:
  có nhà cung cấp API thì ghi âm → upload → chữ vào ô nhập; chưa có thì rơi về Web Speech API.
- `scripts/check_stt_groq.py` — kiểm tra khoá/độ trễ/chất lượng tiếng Việt ngay trên VM.

Ranh giới kiến trúc đã chốt và **phải giữ**: ASR chỉ là "bàn phím bằng giọng nói" — chữ đi vào đúng
`POST /api/v1/copilot/chat`, không đưa audio vào graph, không đụng grounding/verifier/compliance.

### Khoảng cách: hiện tại là "nói thay gõ", chưa phải hội thoại

```
HIỆN NAY : bấm micro → nói → BẤM DỪNG → Whisper ra chữ → chữ vào ô nhập
           → SALE ĐỌC LẠI + BẤM GỬI → Copilot trả lời BẰNG CHỮ (dài, có bảng, citation)

MỤC TIÊU : Sale nói → TỰ phát hiện hết câu → Whisper → Copilot (trả lời NGẮN, dạng nói)
           → ĐỌC TO 1-2 câu kết luận → TỰ mở micro lại → Sale có thể NÓI CHEN để ngắt
```

Năm mảnh còn thiếu (đã xác minh file cần sửa):

| # | Mảnh | Hiện trạng | Nơi sửa |
|---|---|---|---|
| 1 | **VAD — tự phát hiện hết câu** | Sale phải bấm micro lần hai | `frontend/packages/ui/src/lib/voiceRecorder.ts`: thêm WebAudio `AnalyserNode`, RMS dưới ngưỡng ~700ms thì chốt câu. Groq Whisper là **batch, không có transcript tạm** ⇒ VAD bắt buộc ở client |
| 2 | **Tự gửi** | Chữ đổ vào ô nhập, chờ bấm Gửi | `SalesWorkspacePage.uploadVoiceClip`: auto-submit + ngưỡng thời lượng tối thiểu + "Hoàn tác 3 giây" |
| 3 | **Hình dạng câu trả lời ở chế độ thoại** | Trả lời dài, có bảng + citation — đọc lên vô dụng | Thêm `modality: "voice"` vào `CopilotChatRequest` (`src/api/endpoints/copilot.py:40`) → truyền vào `build_system_prompt()` (`src/agents/copilot/prompts.py:237`): 2-3 câu, không bảng, không markdown, số đọc được. **Bản đầy đủ vẫn render trên màn hình** |
| 4 | **Nói lại câu trả lời** | TTS đang đọc bằng giọng Windows/Anh (xem U-02), không được ưu tiên | Chỉ đọc **1-2 câu kết luận** (~150 ký tự), trích bằng `reply_format.structure_sections()` / `_split_sentences()` sẵn có — **không gọi LLM lần hai** |
| 5 | **Barge-in + mở lại micro** | Chưa có | Đang đọc mà Sale nói → dừng phát + **huỷ SSE** ngay; đọc xong → tự nghe tiếp; im lặng 5 phút → tự thoát phiên thoại |

### Ngân sách độ trễ (phải nói thật, đừng hứa "như gọi điện")

| Chặng | Thời gian |
|---|---|
| Chốt câu (im lặng ~700ms) | ~0,7s |
| Whisper Groq turbo (clip 10-15s) | ~0,5-1,5s (đo công khai: 4 phút audio trong 1,53s ≈ 160× realtime) |
| **Copilot (LLM + tool + grounding)** | **3-8s — chặng lâu nhất**, lượt gọi tool còn lâu hơn |
| Đọc 1 câu (~150 ký tự) | ~0,3-1s |
| **Tổng một lượt thoại** | **5-11s** |

Ba cách che độ trễ, đều dùng hạ tầng sẵn có:

1. **Câu đệm phát tức thì**: tổng hợp sẵn 3-4 câu ("Dạ em tra chính sách căn này giúp anh/chị…") rồi cache —
   `tts_speak` **đã cache theo nội dung**, nên phát lại là 0 đồng và gần như 0 độ trễ.
2. **Phát câu đầu tiên ngay khi SSE trả đủ câu đó**, phần còn lại vẫn chạy nền (`POST /copilot/chat/stream`).
3. Trạng thái rõ trên UI: đang nghe → đang tra → đang trả lời.

### Chi phí (số liệu 2026-10-08, phải kiểm tra lại khi mở việc)

- **Groq Whisper free tier**: 20 request/phút · 2.000 request/ngày · 7.200 giây audio/giờ · 28.800 giây
  audio/ngày (8 giờ) · file ≤ 25 MB · không cần thẻ. Vượt: `whisper-large-v3-turbo` 0,04 USD/giờ,
  `whisper-large-v3` 0,111 USD/giờ (tính tối thiểu 10s/request). Hệ thống đã tự chặn ở
  `STT_DAILY_MINUTES_BUDGET` (mặc định 60 phút/ngày) để không chạm trần free giữa demo.
- **Đọc câu kết luận**: chỉ ~150 ký tự/lượt ⇒ **50.000 ký tự miễn phí của Viettel AI ≈ 330 lượt thoại**;
  hoặc **0 đồng** nếu dùng giọng Natural của Edge (xem U-02). Đây là điểm khiến "không ưu tiên TTS"
  và "hội thoại giọng nói" **không mâu thuẫn**: không cần TTS tốt cho câu trả lời dài, chỉ cần đọc một câu.
- **Bẫy đã xác minh**: **Groq TTS (Orpheus) chỉ có tiếng Anh và tiếng Ả Rập, không có tiếng Việt** ⇒
  đừng mong dùng chung khoá Groq của Whisper cho chiều đọc.

### Quyết định kiến trúc: KHÔNG dùng Realtime speech-to-speech

OpenAI Realtime / Gemini Live cho VAD sẵn và độ trễ dưới 1 giây, nhưng **đi vòng qua Copilot graph** ⇒
mất grounding, verifier, compliance và các tool tra giỏ hàng/chính sách — mất đúng thứ làm sản phẩm này
đáng giá. Chỉ cân nhắc sau này cho chế độ "gọi điện thoại", và khi đó vẫn phải giữ tool-calling của mình.

### Ba nấc triển khai (chọn nấc nào làm nấc đó)

| Nấc | Nội dung | Cần TTS? | Công ước lượng |
|---|---|---|---|
| **1 — "Rảnh tay"** | VAD + auto-send + `modality=voice` (trả lời ngắn trên màn hình) + phiên thoại có timeout an toàn | Không | ~1 ngày (chủ yếu FE + 1 trường request + prompt) |
| **2 — "Thoại một chiều"** | Nấc 1 + đọc 1-2 câu kết luận (Edge Natural 0đ hoặc token Viettel) + barge-in | Có, mức tối thiểu | + ~nửa ngày. **Khuyên làm cho Demo Day** |
| **3 — "Phiên thoại liên tục"** | Tự mở lại micro, câu đệm cache, stream câu đầu, ghi sổ độ trễ từng chặng | Có | + ~1 ngày |

### Tiêu chí nghiệm thu đề xuất (viết sẵn để khỏi bàn lại)

- Nấc 1: Sale nói 3 lượt liên tiếp **không chạm màn hình** (trừ lúc vào/thoát phiên thoại); mỗi lượt chữ
  được gửi tự động; VAD cắt sai thì hoàn tác được trong 3 giây; im lặng 5 phút tự thoát; không lượt nào
  vượt hạn mức mà không báo trước.
- Nấc 2: câu kết luận được đọc bằng **giọng tiếng Việt** (không bao giờ bằng giọng Anh); Sale nói chen
  thì audio dừng trong < 300ms và SSE bị huỷ; mỗi lượt thoại ghi sổ đủ `stt` + `tts` + tổng độ trễ.
- Cả hai: **850 test backend và 135 test FE vẫn xanh**, `ruff check .` sạch, mock-server có handler cho
  phiên thoại để dev không cần backend.

### Bốn câu hỏi CÒN TREO (người dùng chưa trả lời — hỏi lại trước khi làm)

1. Làm **Nấc 1** thôi hay **Nấc 1 + 2**?
2. Chế độ thoại: Copilot trả lời **2-3 câu, không bảng**, bản đầy đủ vẫn hiện trên màn hình — đồng ý?
3. Auto-send có kèm **"Hoàn tác 3 giây"** không? (khuyến nghị: có, vì VAD sẽ có lúc cắt sai)
4. Giọng đọc câu kết luận: **Edge Natural (0đ, phụ thuộc trình duyệt)** hay **token Viettel AI (50k ký tự
   free, đồng nhất mọi máy)**?

### Bẫy kỹ thuật đã biết (đỡ mất công tìm lại)

- `speechSynthesis.getVoices()` **rỗng/chưa đủ ở lần gọi đầu**; giọng đám mây chỉ xuất hiện sau sự kiện
  `voiceschanged` — phải chờ, không đọc đồng bộ rồi kết luận "máy không có giọng Việt".
- Giọng **Natural của Windows chỉ hiện trong Edge**, không hiện trong Chrome/Firefox.
- Quyền micro cần **HTTPS** (bản live `demoday.work.gd` đã có) và có thể bị chặn theo origin.
- Barge-in phải **huỷ cả SSE đang chạy**, không chỉ dừng audio — nếu không lượt trả lời cũ vẫn đổ vào
  lịch sử sau khi Sale đã nói câu mới.
- Không auto-listen vô hạn: tốn quota Whisper, và micro mở liên tục là vấn đề riêng tư — phải có timeout.

---

## U-02 — Giọng đọc TTS tiếng Việt (sửa 0 đồng, đã chẩn đoán xong)

**Trạng thái:** CHỜ · **Ưu tiên:** cao hơn U-01 nếu bật đọc thành tiếng; là **điều kiện tiên quyết của U-01 nấc 2** · **Ghi ngày:** 2026-10-08

### Triệu chứng người dùng báo

"TTS hiện tại vẫn chưa tích hợp được tiếng Việt, vẫn đang dùng của Windows, khá tệ và chỉ tiếng Anh."

### Ba nguyên nhân đã xác minh trong code (không phải do Windows dở)

1. **VM đang chạy provider `browser`**: `default_tts_settings()` (`src/services/tts_providers.py:603-619`)
   thấy `TTS_PROVIDER` rỗng thì rơi về `browser` với giọng mặc định `vi-VN`; VM chưa dán khoá nhà cung
   cấp trả phí nào ⇒ mọi câu đều đọc bằng Web Speech API của trình duyệt.
2. **`speakText()` không chờ danh sách giọng**: `frontend/packages/ui/src/lib/speech.ts:68` gọi
   `getVoices()` một lần, đồng bộ — Chrome/Edge chỉ trả giọng đám mây sau `voiceschanged`, nên lần bấm
   đầu tiên thường không khớp được giọng nào.
3. **Không khớp giọng Việt thì VẪN ĐỌC**: `if (match) utterance.voice = match` — không khớp thì để
   `voice = null`, trình duyệt dùng giọng mặc định của HĐH (Windows: Microsoft Zira/David, **tiếng Anh**).
   Code chỉ toast "Máy chưa cài giọng tiếng Việt — đang đọc bằng giọng mặc định của hệ thống" **rồi đọc tiếp**.
   Đây là lỗi của mình: thà từ chối còn hơn đọc sai ngôn ngữ. (Chính note trong catalog đã viết
   "không chạy khi máy không có giọng tiếng Việt" — code không hành xử đúng như note.)

### Sửa đề xuất (~1 buổi, 0 đồng, 1 file + test)

Sửa `frontend/packages/ui/src/lib/speech.ts`:

- (a) Chờ `voiceschanged` / cache danh sách giọng trước khi đọc (preload lúc app khởi động).
- (b) Xếp hạng ưu tiên: giọng **Natural** của Edge (`Microsoft HoaiMy/NamMinh Online (Natural)`) →
  `Google Tiếng Việt` → bất kỳ giọng `vi-*` nào.
- (c) **Từ chối đọc khi không có giọng tiếng Việt**: trả `ok: false` kèm câu chỉ dẫn làm theo được
  ("Mở bằng Microsoft Edge để có giọng tiếng Việt tự nhiên, hoặc cài language pack tiếng Việt trong
  Windows Settings") — thay vì đọc bằng giọng Anh.
- (d) Hiện rõ **đang đọc bằng giọng nào** để Sale không phải đoán.
- Test thêm vào `frontend/packages/ui/src/lib/speech.test.ts` (file test đã có sẵn).

### Kèm theo (quyết định sản phẩm, không phải kỹ thuật)

- Giữ **TTS ở vai phụ**: `auto_speak` mặc định TẮT (hiện đã tắt), chỉ còn nút "Đọc to" đọc **phần kết luận**.
- Nếu muốn chất lượng **đồng nhất mọi máy** (không phụ thuộc trình duyệt): ADMIN dán token **Viettel AI**
  (50.000 ký tự free cho tài khoản mới, 9 giọng 3 miền) hoặc **FPT.AI** vào trang quản trị TTS sẵn có
  (`TtsProvidersCard.tsx`) — **không cần viết adapter mới** vì cả hai đã có trong `TTS_PROVIDER_CATALOG`;
  đặt `TTS_DAILY_CHAR_BUDGET` thấp để không lố hạn mức free.
- Cả hai vendor trên đều cần tài khoản/token do người dùng cấp — **đây là việc của người dùng, không phải của code**.

---

## U-03 — Bốn phần còn thiếu của đợt giao STT (`ebfe613`)

**Trạng thái:** CHỜ · **Ưu tiên:** thấp (không chặn gì) · **Ghi ngày:** 2026-10-08

Đợt giao STT đã cố ý dừng ở mức "chạy được end-to-end"; bốn việc sau chưa làm:

1. **Màn hình quản trị STT dạng card**: hiện cấu hình nhà cung cấp nghe-nói qua `.env` hoặc API
   (`PUT /api/v1/stt/providers/groq`). Có thể nhân bản `frontend/apps/internal/src/features/admin/TtsProvidersCard.tsx`
   thành `SttProvidersCard.tsx` (dán khoá, test, bật/tắt, khai ZDR, xem hạn mức).
2. **Đánh dấu lượt hội thoại `input_modality: voice|text`**: để đo tỉ lệ Sale dùng giọng nói và so sánh
   chất lượng câu hỏi vào bằng hai đường. Hiện chỉ có sổ `llm_usage.jsonl` (`kind = "stt"`) nên biết
   **số lượt**, chưa biết lượt đó có thành câu hỏi Copilot hay không.
3. **`eval/asr/` (thư mục MỚI, chưa tạo) — đo WER tiếng Việt**: bộ clip thật chứa mã căn/tên dự án/thuật ngữ
   (`ZEN-A-1205`, `KPBT`, "ân hạn", "3,864 tỷ") để đo `whisper-large-v3-turbo` so với `large-v3` và so với
   Web Speech API; từ đó chọn model mặc định bằng số liệu thay vì cảm tính. **Lưu ý**: không commit file
   audio vào repo (theo quy ước giữ repo gọn) — sinh clip trong test hoặc để ngoài git.
4. **Chuẩn hoá số đọc bằng chữ**: `normalize_transcript()` mới xử lý "3 phẩy 864 tỷ" → "3,864 tỷ";
   chưa xử lý "ba tỷ tám trăm sáu mươi tư triệu" hay số điện thoại đọc từng chữ. Cần mở rộng khi có dữ liệu thật từ mục 3.

---

## U-04 — CI cài theo lock + chờ kết quả đối chiếu env trên VM

**Trạng thái:** CHỜ NGƯỜI DÙNG · **Ưu tiên:** trung bình · **Ghi ngày:** 2026-10-08

1. **CI vẫn cài `requirements.txt` (range), chưa cài `requirements.lock.txt`** (129 pin). Đổi sang lock để
   CI tái lập đúng bộ đã kiểm thử. Việc này nhỏ nhưng phải làm **sau** mục 2 để không khoá sai phiên bản.
2. **Đang chờ người dùng chạy trên VM**: `.venv/bin/python scripts/check_env_drift.py` và dán output
   (~5-10 dòng). Kết quả "KHỚP toàn bộ 129 gói chốt" thì chuyển CI sang lock ngay; nếu lệch thì sửa
   lock theo đúng bộ VM đang chạy (quyết định cũ của người dùng: `pin_to_vm` — **không** áp lock suy ra
   từ sandbox xuống production).
3. Ghi chú: `requirements.txt` đã được chứng minh **không hạ cấp** VM (đối chiếu dry-run resolve bộ
   gốc không chặn trên = 127 gói, trùng phiên bản với lock); chi tiết ở `docs/CODEBASE_MAP.md` §9.
