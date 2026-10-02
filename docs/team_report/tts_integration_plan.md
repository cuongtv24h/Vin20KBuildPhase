# Phương án tích hợp TTS — Copilot đọc câu trả lời thành tiếng

> Trạng thái: **đã có bản chạy được** (đọc bằng giọng trình duyệt + cấu hình giọng ở DB + đo chi phí quy
> đổi + phản hồi chất lượng giọng). Endpoint tổng hợp audio phía server là **bước kế tiếp** — hợp đồng
> đã chốt trong tài liệu này (§7), chưa nối vì cần chốt ngân sách và chính sách dữ liệu (§6).
>
> Đơn giá trong tài liệu là **giá niêm yết** của nhà cung cấp tại mốc ghi kèm; phải đối chiếu lại trước khi
> quyết toán. Tỷ giá quy đổi dùng cho ước tính: **1 USD ≈ 26.300 VND**.

---

## 1. TL;DR — chọn gì cho việc gì

| Bối cảnh | Phương án | Chi phí | Trạng thái |
| :--- | :--- | :--- | :--- |
| Demo, nội bộ nhỏ, thử trải nghiệm nhanh | **Đọc bằng Web Speech API trong trình duyệt** | 0 đồng | ✅ **đã chạy** (nút “Đọc” từng câu trả lời, bật “Tự đọc”) |
| Triển khai chính thức cho toàn công ty, cần giọng đồng nhất + tiếng Việt chuẩn | **Gọi API TTS qua backend** (`/api/v1/tts/speak`) | 127.000–237.000 VND/người/tháng nếu nghe ~30 lượt/ngày | 🔜 có hợp đồng + ngân sách ước tính, chưa nối |
| Quy mô lớn (hàng nghìn người dùng thường xuyên) hoặc yêu cầu dữ liệu không ra ngoài | **Self-host model tiếng Việt** (ví dụ VieNeu-TTS, Apache 2.0, chạy CPU/ONNX) | Chi phí cố định (1 máy/1 GPU), biên gần 0 | 🔜 cân nhắc ở M4 |

Ba kết luận quan trọng, nói thẳng:

1. **Đừng bật “tự đọc” cho 20.000 Sale bằng API trả phí trước khi đo.** Với giả định mỗi người nghe 30
   lượt/ngày × 600 ký tự, toàn công ty tiêu thụ ~8 tỷ ký tự/tháng ≈ **840 triệu VND/tháng** ở mức giá rẻ
   nhất (Google WaveNet 4 USD/1M). Con số này chỉ hợp lý nếu bật theo yêu cầu (Sale bấm nghe) hoặc đọc
   bản tóm tắt, không phải đọc toàn văn mọi lượt.
2. **Giọng trình duyệt không phải phương án tạm cho có**: nó là phương án *mặc định* hợp lý cho phần lớn
   nhân viên (0 đồng, không cần khoá, không gửi nội dung ra ngoài máy). Nâng lên API trả phí là để **đồng
   nhất giọng và kiểm soát chất lượng**, không phải để “chạy được”.
3. **Đọc to là rò rỉ**: câu trả lời của Copilot có số điện thoại/email khách và con số chiết khấu. Phải
   che PII trước khi đọc (§5) — nếu không, tính năng tiện lại thành lỗi bảo mật ngay cạnh khách.

---

## 2. Kiến trúc: hai đường đi, một hợp đồng thiết lập

```
                      ┌──────────────── GET/PUT /api/v1/settings/tts ────────────────┐
                      │  (đã có) danh mục nhà cung cấp + đơn giá + giọng + tốc độ   │
                      │  mặc định hệ thống (ADMIN/MANAGER) vs hồ sơ riêng (Sale)     │
                      └───────────────┬───────────────────────────┬─────────────────┘
                                      │                           │
                     provider = browser                provider = openai | google_cloud |
                                      │                azure | viettel | vbee | fpt
                                      ▼                           ▼
                     ┌────────────────────────┐   ┌──────────────────────────────────────┐
                     │ Web Speech API (máy)   │   │ POST /api/v1/tts/speak  (🔜 kế tiếp) │
                     │ 0đ · 0 dữ liệu ra ngoài│   │  backend giữ khoá, cache audio, ghi  │
                     │ giọng tuỳ máy          │   │  chi phí vào llm_usage.jsonl         │
                     └────────────────────────┘   └──────────────────────────────────────┘
```

Điểm cốt lõi: **UI không đổi khi nâng cấp**. `SalesWorkspacePage` chỉ hỏi “giọng nào, tốc độ bao nhiêu,
tối đa bao nhiêu ký tự” rồi phát audio; việc audio đến từ máy hay từ backend là chuyện của tầng dưới.
Đó là lý do hôm nay đã làm `GET/PUT /api/v1/settings/tts` **trước** khi làm endpoint tổng hợp.

---

## 3. Phương án A — đọc tại trình duyệt (đã chạy)

| Việc | Ở đâu | Ghi chú |
| :--- | :--- | :--- |
| Phát audio | `frontend/packages/ui/src/lib/speech.ts` | `speakText()`, `stopSpeaking()`, `listLocalVoices()`, `toSpeakableText()` |
| Nút “Đọc” từng câu trả lời | `SalesWorkspacePage` (dưới mỗi bong bóng trả lời) | Bấm lần hai = dừng (barge-in) |
| “Tự đọc mỗi câu trả lời mới” | Hộp thoại **Giọng đọc** ở header workspace | Lưu vào hồ sơ riêng; Admin/MANAGER đặt mặc định cho cả công ty |
| Dọn văn bản trước khi đọc | `toSpeakableText()` | Bỏ markdown/citation/emoji — không đọc cả dấu `*` hay “Điều 4 Khoản 2b” trong ngoặc |

**Giới hạn đã biết (nói thật):**

- Chất lượng/âm sắc **tuỳ máy**: Windows/macOS/Android mỗi nơi một giọng, không đồng nhất thương hiệu.
- Máy chưa cài gói giọng tiếng Việt thì đọc bằng giọng mặc định — UI đã báo “Máy này chưa có giọng tiếng
  Việt” thay vì im lặng.
- Không kiểm soát được cách đọc **số tiền/số căn** (một số giọng đọc “1205” thành “một hai không năm”).
  Muốn chuẩn phải chèn dấu phân cách khi tiền xử lý văn bản.
- Không đo được chi phí (vì không có chi phí) và không có log phục vụ kiểm toán.

---

## 4. Phương án B — gọi API TTS qua backend (bước kế tiếp)

### 4.1 Vì sao phải đi qua backend, không gọi trực tiếp từ trình duyệt

| Lý do | Chi tiết |
| :--- | :--- |
| Khoá API | Không được nhúng khoá vào bundle JS — ai cũng đọc được. Backend giữ khoá, UI chỉ biết **có/không có khoá**. |
| Chi phí | Mỗi lượt đọc phải ghi vào `llm_usage.jsonl` để tab “Chi phí & hiệu năng” tính đúng như phần LLM. Gọi từ trình duyệt là mất số liệu. |
| Cache | Cùng một câu trả lời được đọc lại (bấm nghe lại, nhiều người hỏi cùng câu) → cache theo hash văn bản + giọng, tiết kiệm 20–40% chi phí thực tế. |
| Kiểm soát | Giới hạn ký tự/lượt, chặn đọc nội dung ngoài phạm vi, ghi log ai đọc gì (kiểm toán), tránh lạm dụng. |
| Che PII | Chỗ duy nhất nhìn thấy **toàn văn câu trả lời trước khi phát** là server — nơi tốt nhất để che số điện thoại/email. |

### 4.2 Trình tự một lượt đọc

```
Sale bấm "Đọc"  →  POST /api/v1/tts/speak {text, provider?, voice?, speed?, conversation_id?}
                →  backend: chuẩn hoá + che PII + cắt theo max_chars
                →  cache có? trả audio luôn (0 đồng)
                →  chưa có? gọi nhà cung cấp → ghi usage (chars, latency, ok, cost) → trả audio
                →  UI: HTMLAudioElement phát; bấm lần hai = huỷ + báo "nghe xong/chưa ổn"
```

### 4.3 Bảng giá niêm yết (đơn vị gốc + quy đổi/1M ký tự)

| Nhà cung cấp | Giọng tiếng Việt | Đơn giá niêm yết | ≈ VND/1M ký tự | Nhận xét cho dự án này |
| :--- | :--- | :--- | ---: | :--- |
| **Trình duyệt (Web Speech)** | Có (theo hệ điều hành) | 0 | **0** | Mặc định hiện tại; không đồng nhất giọng |
| **Google Cloud TTS** | `vi-VN` WaveNet/Neural2 | 4 USD/1M (WaveNet, miễn phí 4M/tháng); 16 USD/1M (Neural2, miễn phí 1M/tháng) | **105.000** / 420.000 | Rẻ nhất trong nhóm API; có hạn mức miễn phí hằng tháng — nên thử trước |
| **Azure AI Speech** | `vi-VN-HoaiMy` (nữ), `vi-VN-NamMinh` (nam) | 16 USD/1M | **420.000** | Hai giọng VN ổn định, có SSML để ngắt nghỉ theo câu |
| **OpenAI TTS** | Giọng đa ngôn ngữ (`alloy`, `nova`, `onyx`…) | `tts-1` 15 USD/1M; `tts-1-hd` 30 USD/1M | **394.000** / 789.000 | Dùng chung khoá với LLM; hỗ trợ streaming |
| **Viettel AI TTS** | Nữ/nam Hà Nội, Sài Gòn | 320.000 VNĐ/1M (không thuê bao) | **320.000** | Trong nước, dữ liệu không ra ngoài; bảng giá công bố từ 2022 — cần xác nhận lại |
| **Vbee AIVoice** | 200+ giọng, 3 miền | Gói 149.000đ/125k ký tự (≈1.192.000đ/1M) → gói VIP 299.000đ/500k (≈598.000đ/1M) | **598.000** | Giọng Việt tốt, có nhân bản giọng; tính theo gói nên phải quy đổi theo ký tự thực dùng |
| **FPT.AI Voice** | `banmai`, `lannhi`, `leminh`… | Tham khảo từ 500.000đ/1,5M ký tự | **≈333.000** | Dễ ký hợp đồng nội địa |
| **Self-host (VieNeu-TTS v3 Turbo)** | 25 giọng dựng sẵn, có nhân bản | 0 đồng/lượt (Apache 2.0) | **0** + chi phí hạ tầng | Chạy CPU/ONNX, có API server; cần người vận hành model |

*(Nguồn giá: trang giá công bố của nhà cung cấp, tra ngày 2026-10-02; riêng Viettel là bảng giá 2022-12-26
và Vbee/FPT là mức gói tham khảo 2026-02-23 — **số cũ trong tài liệu, phải xác nhận lại**.)*

### 4.4 Bài toán chi phí — con số cụ thể để quyết định

Giả định một lượt đọc trung bình **600 ký tự** (câu trả lời của Copilot thường 300–900 ký tự) và một Sale
nghe **30 lượt/ngày** (~0,4M ký tự/tháng):

| Nhà cung cấp | 1 người/tháng | 100 người/tháng | 1.000 người/tháng | 20.000 người/tháng |
| :--- | ---: | ---: | ---: | ---: |
| Google WaveNet (4 USD/1M) | ≈ 1,6 USD ≈ **42.000đ** | ≈ 4,2 triệu đ | ≈ 42 triệu đ | ≈ **840 triệu đ** |
| Viettel (320.000đ/1M) | **127.000đ** | 12,7 triệu đ | 127 triệu đ | **2,5 tỷ đ** |
| OpenAI tts-1 (15 USD/1M) | ≈ **158.000đ** | 15,8 triệu đ | 158 triệu đ | **3,2 tỷ đ** |
| Azure / Neural2 (16 USD/1M) | ≈ **168.000đ** | 16,8 triệu đ | 168 triệu đ | **3,4 tỷ đ** |

⇒ Ba cách giảm chi phí, áp dụng cùng lúc:

1. **Đọc theo yêu cầu, không tự đọc toàn bộ** (mặc định `auto_speak = false` như hiện tại).
2. **Đọc bản tóm tắt** thay vì toàn văn: Copilot đã có `reply`; sinh thêm `spoken_summary` (~150–200 ký tự,
   chỉ nêu kết luận + 1 con số chính) → giảm ~70% ký tự mà vẫn đủ thông tin khi đang lái xe/dẫn khách.
3. **Cache theo hash** (văn bản + giọng + tốc độ) — câu hỏi lặp lại giữa các Sale rất nhiều.

Với 20.000 người dùng, **self-host là phương án duy nhất có chi phí biên ~0**; API managed chỉ hợp lý ở
nhóm người dùng thường xuyên (ví dụ 1.000 người dùng nhiều) hoặc khi bật hạn mức theo người.

---

## 5. Phương án “AI tự đọc câu trả lời” — thiết kế trải nghiệm

Đã làm hôm nay: nút **Đọc** cho từng câu trả lời + công tắc **Tự đọc mỗi câu trả lời mới** (mặc định hệ
thống do ADMIN/MANAGER đặt, mỗi nhân viên tắt/đổi được cho riêng mình) + **phản hồi 👍/👎** để chọn giọng
theo dữ liệu thực tế.

Đề xuất hoàn thiện tiếp (theo thứ tự nên làm):

| # | Hạng mục | Vì sao | Cách làm |
| :--- | :--- | :--- | :--- |
| 1 | **Che PII trước khi đọc** | Đọc to số điện thoại/email khách giữa sàn là rò rỉ | Hàm `to_spoken_text()` phía server: SĐT → “số điện thoại của khách”, email → “email”, mã hồ sơ → giữ; cấm đọc trường nội bộ (lợi nhuận, giá sàn) |
| 2 | **Bản tóm tắt để đọc** | Câu trả lời dài đọc hết vừa lâu vừa tốn tiền | Thêm `spoken_summary` vào payload cuối (LLM viết lại 1 câu hoặc lấy `reply` cắt theo câu hoàn chỉnh) |
| 3 | **Streaming khi câu trả lời dài** | Chờ tổng hợp xong 900 ký tự mất 2–3 s | Chia câu trả lời theo câu, gọi TTS theo từng đoạn, phát nối tiếp (nhà cung cấp có streaming: OpenAI/Google/Azure) |
| 4 | **Barge-in & hàng đợi** | Sale bấm dừng/đổi câu liên tục | Đã có `stopSpeaking()`; khi nối backend thì huỷ `AbortController` + không phát audio về muộn |
| 5 | **Chế độ rảnh tay** | Sale đang lái xe/đang dẫn khách | Bật `auto_speak` + đọc tóm tắt + chặn đọc khi Sale đang gõ (tránh giọng đọc đè lên hội thoại) |
| 6 | **Hạn mức theo người/ngày** | Chặn một tài khoản bị lạm dụng làm cháy ngân sách | Đếm ký tự/ngày theo `user_id` trong `llm_usage.jsonl`; vượt hạn mức → tự chuyển về giọng trình duyệt và báo rõ |
| 7 | **Đo chất lượng giọng** | “Nghe có hiểu không” mới là tiêu chí, không phải “giọng có hay không” | Đã có 👍/👎 + `feedback_summary`; bổ sung khảo sát ngắn “nghe rõ số căn/số tiền không?” |

Lưu ý về **an toàn nội dung**: TTS không kiểm duyệt nội dung. Nếu sau này cho phép đọc cả câu hỏi của khách
hoặc tin nhắn Sale soạn, phải chạy qua guardrail như phần chat (đã có `guardrails.py`), không đọc thẳng.

---

## 6. Câu hỏi cần chốt trước khi nối API trả phí

1. **Ngân sách/tháng cho giọng đọc** là bao nhiêu, và ai giữ hạn mức? (Ảnh hưởng trực tiếp tới việc bật
   `auto_speak` toàn công ty hay chỉ cho nhóm dùng nhiều.)
2. **Dữ liệu có được gửi ra nhà cung cấp nước ngoài không?** Câu trả lời nằm trong hội thoại (tên khách,
   số điện thoại, giá). Nếu không được → chọn Viettel/Vbee/FPT hoặc self-host.
3. **Giọng nam hay nữ, miền nào?** Cần chốt để đặt mặc định; hiện hệ thống để Admin chọn và Sale ghi đè.
4. **Có cần nhân bản giọng thương hiệu** (giọng MC của dự án) không? Nếu có, phương án là Vbee/VieNeu/Azure
   custom voice — kèm yêu cầu pháp lý về quyền sử dụng giọng.

---

## 7. Hợp đồng API đề xuất cho bước kế tiếp

```http
POST /api/v1/tts/speak          (staff; Idempotency-Key bắt buộc như các POST khác)
{
  "text": "Dạ, căn ZEN-A-1205 còn hàng, giá 4,7 tỷ đã gồm VAT.",
  "provider": "google_cloud",     // bỏ trống = lấy thiết lập hiệu lực của người gọi
  "voice": "vi-VN-Wavenet-A",     // bỏ trống = lấy thiết lập hiệu lực
  "speed": 1.0,
  "conversation_id": "CNV-000012",// để gắn log + phản hồi giọng
  "summary_only": false           // true = chỉ đọc bản tóm tắt (tùy chọn của chế độ rảnh tay)
}
→ 200 { "audio_base64": "...", "mime": "audio/mpeg", "chars": 612, "cached": false,
        "cost": 0.002448, "currency": "USD", "provider": "google_cloud", "voice": "vi-VN-Wavenet-A",
        "latency_ms": 640 }
→ 402/403 khi vượt hạn mức hoặc thiếu quyền; 503 khi nhà cung cấp lỗi (UI tự lùi về giọng trình duyệt)
```

Kèm theo:

- Ghi mỗi lượt vào `llm_usage.jsonl` với `kind: "tts"` để tab **Chi phí & hiệu năng** cộng đúng (hiện log
  đang dành cho LLM: token vào/ra; cần thêm nhánh ký tự cho TTS thay vì nhồi vào token).
- Cache `data/tts_cache/<sha256(text|provider|voice|speed)>.<ext>` (kèm TTL/trần dung lượng) — dọn định kỳ.
- `GET /api/v1/tts/quota` trả hạn mức còn lại trong ngày cho người gọi.

---

## 8. Kiểm chứng phần đã làm (chạy thật)

| Lệnh / kịch bản | Kết quả |
| :--- | :--- |
| `.venv/bin/python -m pytest tests/test_api/test_tts_settings.py -q` | **9 passed** |
| `cd frontend && npx vitest run --root packages/mock-server src/tts.test.ts` | **5 passed** |
| `cd frontend && npm run lint` | 0 error, 124 warning (không tăng) |
| `cd frontend && npx tsc -b apps/internal` | exit 0 |
| Smoke: `GET /api/v1/settings/tts` (mock) | trả `effective.provider = browser`, `cost_hint.cost = 0`, danh mục 4 nhà cung cấp kèm cờ `api_key_configured` |
| Smoke: Sale `PUT scope=user` | lưu được, `cost_hint` đổi theo nhà cung cấp (Google 600 ký tự ≈ 0,0024 USD) |
| Smoke: Sale `PUT scope=default` | **403** kèm hướng dẫn; MANAGER/ADMIN đổi được |
| Smoke: 👍/👎 giọng đọc | `feedback_summary` = 1 ổn / 1 chưa ổn → 50% hài lòng |
