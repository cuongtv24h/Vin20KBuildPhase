# API Integration — Frontend PricePolicy

Tài liệu ghép nối frontend ↔ FastAPI cho TechLead và dev backend. Nguồn sự thật là code:

| Nội dung | File |
| :--- | :--- |
| Danh bạ endpoint (method, path, nguồn, quyền) | [`src/api/endpoints.ts`](src/api/endpoints.ts) |
| Kiểu dữ liệu hợp đồng (wire format, snake_case) | [`src/api/contracts/`](src/api/contracts/) |
| Header, lỗi, timeout | [`src/api/http.ts`](src/api/http.ts), [`src/api/errors.ts`](src/api/errors.ts) |
| SSE client (reconnect, Last-Event-ID, 410) | [`src/api/sse.ts`](src/api/sse.ts) |
| Hành vi tham chiếu phía server (mock) | [`src/mocks/`](src/mocks/) |
| **Đặc tả chạy được** — 18 kịch bản đầu-cuối | [`src/mocks/scenarios.test.ts`](src/mocks/scenarios.test.ts) |

> `src/contracts/` và `src/api/endpoints/` của backend **chưa có trong repo** (mọi nhánh). Toàn bộ type
> được dẫn xuất từ TD-4.1, Implement plan §5/§10, PRD v2.2 và CodeBaseIndex. Khi TechLead khoá
> contract, thay `src/api/contracts/` bằng type sinh từ OpenAPI (vd. `openapi-typescript`) — tên
> field đã giữ nguyên snake_case nên màn hình không phải sửa.

---

## 1. Bật / tắt mock

```bash
cp .env.example .env.local
```

| Biến | Giá trị | Ý nghĩa |
| :--- | :--- | :--- |
| `NEXT_PUBLIC_API_MODE` | `mock` (mặc định) \| `real` | `mock`: MSW chặn request trong trình duyệt. `real`: gọi FastAPI. |
| `NEXT_PUBLIC_API_BASE_URL` | `/api/v1` | Base URL. Với `npm run dev`, `/api/*` được proxy tới `API_PROXY_TARGET`. |
| `API_PROXY_TARGET` | `http://localhost:8000` | Chỉ dùng cho Vite dev server (không lộ ra trình duyệt). |

Đổi sang backend thật: `NEXT_PUBLIC_API_MODE=real`, khởi động lại `npm run dev`. **Không sửa file nào trong
`src/features/` hay `src/components/`** — cả hai chế độ chạy cùng một `http.ts`/`client.ts`/hooks;
MSW chỉ thay thế tầng mạng. `main.tsx` import động `src/mocks/browser.ts` theo biến môi trường nên bản build
`real` **không chứa** MSW hay dữ liệu mock (đã kiểm tra).

> Frontend hiện là **Vite + React Router**, không phải Next.js như TD-4.1 ghi. Biến vẫn đặt tiền tố
> `NEXT_PUBLIC_` (bật qua `envPrefix` trong `vite.config.ts`) để không đổi `.env` nếu sau này chuyển.

Kiểm tra quy ước "component không import mock":

```bash
grep -rnE "from ['\"](@/mocks|msw)" src/features src/components   # phải rỗng
```

### Công cụ môi trường mock (chỉ `npm run dev` + mode mock)

Nút tròn góc dưới phải mở **Mock backend panel**: độ trễ 200–800ms / mạng chậm, tỷ lệ lỗi 500 (0/30/100%),
Agent chậm (vượt deadline 10s), ngắt SSE giữa chừng, replay hết hạn (410), PDF worker lỗi, đăng nhập
nhanh 4 vai trò, **Reset demo**. Panel gọi `/__mock/*` qua HTTP — không import mã mock. Dữ liệu mock
lưu `localStorage` (giữ qua reload, đồng bộ giữa các tab); mật khẩu mọi tài khoản: `Vland@2026`.

---

## 2. Endpoint → hook → màn hình

Base `/api/v1`. **Nguồn**: `TD-4.4` = có trong 29 endpoint theo CodeBaseIndex; `ĐỀ XUẤT` = UI cần, chưa có
trong TD-4.4 (xem §3).

| Method & path | Nguồn | Quyền | Hook | Màn hình |
| :--- | :--- | :--- | :--- | :--- |
| `POST /quotes` → **202** | TD-4.4 | SALE | `useCreateQuote` | Báo giá khách tại sàn |
| `GET /quotes/{id}?version=` | TD-4.4 (`version` ĐỀ XUẤT) | staff | `useQuote` | Chi tiết báo giá (Sale), Workspace (Quản lý) |
| `GET /quotes/{id}/events` (SSE) | TD-4.4 | staff | `useQuoteEvents` | Tiến trình Agent |
| `GET /quotes/{id}/evidence?version=` | TD-4.4 | staff | `useQuoteEvidence` | Why/Why-not, panel chứng cứ, luận điểm |
| `GET /quotes/{id}/audit` | TD-4.4 | staff | `useQuoteAudit` | Nhật ký hồ sơ (hash chain) |
| `GET /quotes/{id}/pdf` | TD-4.4 | staff | `useQuotePdf` | Thẻ PDF (Quản lý) |
| `POST /quotes/{id}/approve` | TD-4.4 | MANAGER | `useApproveQuote` | Workspace — Ký duyệt |
| `POST /quotes/{id}/reject` | TD-4.4 | MANAGER | `useRejectQuote` | Workspace — Từ chối |
| `POST /quotes/{id}/revision` | TD-4.4 | MANAGER | `useRequestRevision` | Workspace — Yêu cầu sửa |
| `POST /quotes/{id}/pdf-retry` | TD-4.4 | MANAGER | `useRetryPdf` | Thẻ PDF khi `FAILED` |
| `GET /quotes?status=A,B&source_dossier_id=` | ĐỀ XUẤT | staff | `useQuotes` | Danh sách báo giá, hàng đợi duyệt, badge menu |
| `POST /quotes/{id}/submit` | ĐỀ XUẤT | SALE | `useSubmitQuote` | Gửi Quản lý duyệt |
| `POST /quotes/{id}/versions` → **202** | ĐỀ XUẤT | SALE | `useNewQuoteVersion` | Chỉnh sửa & phân tích lại |
| `GET /leads` | TD-4.4 | SALE | `useLeads`, `useLead` | Hộp hồ sơ khách, form báo giá |
| `POST /leads/{id}/convert-to-quote` → **202** | TD-4.4 | SALE | `useConvertLead` | Lập báo giá chính thức từ dossier |
| `POST /pre-sales/sessions` | TD-4.4* | public | `useStartPreSales` | Tư vấn tài chính |
| `GET /pre-sales/sessions/{id}` | TD-4.4* | public | `usePreSalesSession` | Tư vấn tài chính (khôi phục phiên) |
| `POST /pre-sales/sessions/{id}/messages` | TD-4.4* | public | `useSendPreSalesMessage` | Chat dẫn dắt |
| `POST /pre-sales/sessions/{id}/constraints/confirm` | TD-4.4* | public | `useConfirmConstraints` | Xác nhận thông tin |
| `POST /pre-sales/sessions/{id}/plan` | TD-4.4* | public | `useGeneratePlan` | Phương án tham khảo |
| `POST /pre-sales/sessions/{id}/handoff` | TD-4.4* | public | `useHandoff` | Đồng ý bàn giao cho Sale |
| `POST /compliance/check-message` | TD-4.4 | SALE | `useComplianceCheck` | Composer (debounce 500ms) |
| `POST /messages/send` | TD-4.4 | SALE | `useSendMessage` | Composer — cổng gửi duy nhất |
| `POST /compliance/draft-message` | ĐỀ XUẤT | SALE | `useDraftMessage` | Composer — Tạo tin đề xuất |
| `POST /policies/extract-rules` (multipart) | TD-4.4 | POLICY_ADMIN | `useExtractRules` | Tải lên văn bản |
| `POST /policies/{id}/rules/test` | TD-4.4 | POLICY_ADMIN | `useTestRules` | Kiểm tra trước ban hành |
| `POST /policies/{id}/publish` | TD-4.4 | POLICY_ADMIN | `usePublishPolicy` | Ban hành |
| `POST /evaluation/benchmark-runs` | TD-4.4 | POLICY_ADMIN | `useRunBenchmark` | Kiểm thử công thức |
| `GET /policies?project_id=&status=` | ĐỀ XUẤT | staff | `usePolicies` | Danh sách chính sách, chọn văn bản trong form |
| `GET /policies/{id}` | ĐỀ XUẤT | staff | `usePolicy` | Chi tiết chính sách, form báo giá |
| `GET /policies/active?project_id=&date=` | ĐỀ XUẤT | staff | `useActivePolicy` | Form báo giá (Time-Travel) |
| `GET /units?project_id=` | ĐỀ XUẤT | public | `useUnits` | Trang chủ, form báo giá |
| `GET /public/projects` | ĐỀ XUẤT | public | `useProjectOverviews` | Trang chủ khách hàng |
| `POST /auth/login`, `POST /auth/logout` | ĐỀ XUẤT | — | `useLogin` | Đăng nhập |
| `POST /auth/reauth` | ĐỀ XUẤT | MANAGER | `useReauth` | Dialog ký duyệt |

\* CodeBaseIndex chỉ ghi "6 endpoint Pre-Sales sessions"; đường dẫn chi tiết là suy luận.
Endpoint TD-4.4 chưa dùng: `POST /quotes/{id}/exception` (N-18, TGĐ), `GET /.well-known/jwks.json`.

Test `scenarios.test.ts › Mọi endpoint trong danh bạ đều có handler mock` bảo đảm bảng trên và mock luôn khớp.

---

## 3. Việc cần TechLead chốt

### 3.1 Câu hỏi mở

1. **Đường dẫn SSE**: TD-4.1 §3.1 ghi `/quotes/{id}/stream`, CodeBaseIndex ghi `/quotes/{id}/events`.
   Client dùng `stream_url` do 202 trả về; chỉ khi tải lại trang mới dùng `ENDPOINTS.quoteEvents`
   (hiện `/events`). Chốt xong chỉ sửa **một dòng** trong `endpoints.ts`.
2. **6 objectives**: CodeBaseIndex nói `OptimizationObjective` có 6 giá trị, PRD chỉ định nghĩa 4
   (`MIN_NET_PRICE`, `MIN_INITIAL_OUTFLOW`, `MIN_TOTAL_CASH_OUTFLOW`, `MAX_BENEFIT_VALUE`). Cần tên 2 giá trị còn lại.
3. **Bước gửi duyệt**: TD-4.1 cho `quote_ready` mang `READY_FOR_REVIEW` trực tiếp; PRD và brief có bước
   Sale "gửi duyệt" từ `DRAFT`. Frontend theo PRD (`DRAFT` → `POST /submit` → `READY_FOR_REVIEW`).
4. **`POST /quotes/{id}/revision`**: frontend hiểu là lệnh của **Quản lý** yêu cầu sửa; Sale tạo phiên bản
   mới qua `POST /quotes/{id}/versions` [ĐỀ XUẤT]. Nếu `revision` là lệnh của Sale thì đổi 2 dòng trong `endpoints.ts`.
5. **Mã lỗi OCC**: TD-4.1 dùng `409 STALE_QUOTE_VERSION`; CodeBaseIndex nhắc `get_if_match_etag` (412).
   Client xử lý cả hai như nhau (`isStaleVersion`).
6. **Scenario code**: dùng `PA-CHUDONG | PA-NHANH | PA-VAY` (CodeBaseIndex). Implement plan còn nhắc `PA-CHUAN`.

### 3.2 Field đề xuất bổ sung contract

Các field dưới đây có trong type nhưng **không có** trong tài liệu nào — đánh dấu `[ĐỀ XUẤT]` trong code:

| Model | Field | Lý do |
| :--- | :--- | :--- |
| `TransactionContext` | `requested_policy_id: string \| null` | Sale viện dẫn văn bản cụ thể → phát hiện `EXPIRED` (FAIL-02). `null` = tra cứu theo ngày. |
| `RuleEvaluation` | `effect: 'PRICE_REDUCTION' \| 'IN_KIND' \| 'FINANCING'` | Breakdown phải ghi quà hiện vật "không trừ vào giá" (PRD §7). |
| `EvidenceBackedClaim` | `direction: 'WHY' \| 'WHY_NOT'`, `rule_code`, `decision_status` | Tách mục "Why not?" và mở chứng cứ theo điều khoản. |
| `Quote` | `versions: QuoteVersionSummary[]`, `missing_fields`, `abstention`, `submitted_at` | Xem bản cũ (chỉ đọc), hiển thị NEEDS_INPUT, loại dừng an toàn. |
| `ChatMessage` | `suggestions: string[]` | Chip trả lời nhanh cho câu hỏi dẫn dắt (D3-1). |
| `Recommendation` | `comparisons[].delta_vnd` | UI dựng câu "Theo tiêu chí X, phương án Y giảm … so với …" từ số liệu. |
| `ErrorCode` | `POLICY_AMBIGUOUS`, `IDEMPOTENCY_KEY_REQUIRED`, `REAUTH_REQUIRED` | Chưa có trong Error Catalog TL-0.3. |
| Enum | Giá trị `LeadDossierStatus`, `PreSalesSessionStatus`, `ApprovalDecision` | Tài liệu chỉ nêu tên enum, không nêu giá trị. |

---

## 4. Quy ước giao thức (backend phải tuân theo)

**Wire format**: JSON snake_case đúng như `src/api/contracts/`. Tiền là số nguyên VNĐ (`*_vnd`), tỷ lệ thập
phân, ngày nghiệp vụ `YYYY-MM-DD`, thời điểm ISO 8601 UTC.

**Header gửi đi** (`http.ts`):

| Header | Khi nào |
| :--- | :--- |
| `Authorization: Bearer <access_token>` | Mọi route nội bộ |
| `Idempotency-Key: <uuid>` | **Mọi POST**. Cùng thao tác thử lại (timeout, lỗi mạng) dùng lại đúng key; payload khác → key mới. |
| `If-Match: "v<quote_version>"` | `submit`, `versions`, `approve`, `reject`, `revision` |
| `X-Reauth-Token` | `approve` — lấy từ `POST /auth/reauth`, dùng một lần |
| `X-Correlation-ID: <uuid>` | Mọi request |

**Lỗi**: body `{ "code": ErrorCode, "message": "…" }` (client cũng đọc `{ error: {…} }` và FastAPI `{ detail }`).
`message` hiển thị thẳng cho người dùng (tiếng Việt). Client xử lý:

| Status / code | Hành vi UI |
| :--- | :--- |
| `401` | Xoá phiên → `/login` (giữ đường dẫn để quay lại) |
| `403 SOD_VIOLATION` / `REAUTH_REQUIRED` / `FORBIDDEN` | Hiện thông báo, không xoá phiên |
| `409 STALE_QUOTE_VERSION` (hoặc `412`) | Tự tải lại quote, báo "đã có phiên bản mới" |
| `409 IDEMPOTENCY_KEY_REUSE_PAYLOAD_MISMATCH` | Báo lỗi |
| `409 PDF_NOT_READY` | Ẩn nút tải |
| `422 COMPLIANCE_BLOCKED` | Composer: không gửi, không hiện "đã gửi" |
| Quá 10s / lỗi mạng | `TIMEOUT` / `NETWORK_ERROR`, màn hình hiện lỗi + Thử lại |

Idempotency (mock làm đúng như vậy): thiếu key → `400 IDEMPOTENCY_KEY_REQUIRED`; cùng key + cùng
fingerprint (`method:path:actor:If-Match:body`) → trả lại response cũ kèm `Idempotent-Replayed: true`;
khác fingerprint → `409`.

**Tạo quote** (TD-4.1 §3.1): `POST /quotes` trả **202** ≤ 200ms:
`{ "quote_id", "quote_version", "status": "ANALYZING", "stream_url" }`. Trong lúc phân tích,
`GET /quotes/{id}` trả `status: "ANALYZING"`.

**SSE** `GET /quotes/{id}/events`:

```
: ping                                     ← ngay khi mở + mỗi 15s (không phải business event)

id: QUO-2026-09-00007:v1:000001
event: step_update
data: {"event_id":"QUO-2026-09-00007:v1:000001","event_seq":1,"event_type":"step_update","quote_id":"QUO-2026-09-00007","quote_version":1,"schema_version":"sse-event.v1","correlation_id":"…","occurred_at":"…","session_id":null,"payload":{"node":"POLICY_LOOKUP","seq":1}}

… VECTOR_RETRIEVAL, DETERMINISTIC_CALCULATION (chỉ các node đã chạy) …

id: QUO-2026-09-00007:v1:000004
event: quote_ready
data: {…"payload":{"quote_id":"QUO-2026-09-00007","status":"DRAFT","seq":4}}
```

- `quote_ready` là sự kiện kết thúc; `status` có thể là `DRAFT`, `ABSTAINED`, `NEEDS_INPUT`, `CALCULATION_FAILED`.
- Kết nối mới **không** có `Last-Event-ID` → server phát lại toàn bộ sự kiện của phiên bản hiện tại.
- Reconnect có `Last-Event-ID` → chỉ phát `event_seq` lớn hơn. Không phát lại được (quá 24h, khác phiên bản)
  → **410** + `X-Action: RESYNC_FULL_STATE`; client gọi `GET /quotes/{id}` rồi nối lại từ đầu.
- Client stream bằng `fetch` (gửi được `Authorization` + `Last-Event-ID`), loại trùng `event_id`, backoff
  0,5 → 8s, coi mất kết nối khi 20s không nhận byte nào. Proxy/Nginx phải tắt buffering.
- Deadline 10s phía client: chưa có `quote_ready` → hiện trạng thái dừng an toàn, vẫn nghe tiếp và tự cập nhật khi có kết quả.

**PDF**: sau `approve`, `pdf_status` đi `PENDING → GENERATING → PDF_ISSUED` (hoặc `FAILED` → `pdf-retry`).
UI chỉ hiện "Đã phát hành" và nút tải khi `PDF_ISSUED`; trong lúc chờ, `GET /quotes/{id}` được poll mỗi 1,5s.
Sale không có nút duyệt, không có nút xuất PDF.

---

## 5. Kịch bản mock (quyết định bởi input, không có nút chọn kịch bản)

| Kịch bản | Input | Kết quả |
| :--- | :--- | :--- |
| Happy path | Dossier *Nguyễn Văn An* → Lập báo giá, chọn *Chiết khấu thanh toán sớm 95%* (+ *Smarthome*) | 3 phương án, PA-NHANH = **4.233.600.000 đ** (PRD §7) → Gửi duyệt → Quản lý ký (mật khẩu) → `PDF_ISSUED` |
| FAIL-01 | *Gói hỗ trợ nội thất* + *Thanh toán sớm 95%* | `ABSTAINED` / CONFLICT cấp 1, trích **Điều 6, Khoản 2** |
| FAIL-02 | Ngày `2026-07-15`, văn bản chính sách `v3.1` | `ABSTAINED` / EXPIRED |
| FAIL-03 | *Ưu đãi khách hàng đặc biệt theo quyết định riêng* | `ABSTAINED` / AMBIGUOUS (cờ vàng), vào tab Ngoại lệ của Quản lý |
| FAIL-04 | Căn **ZEN-B-1108** (bảng hàng đồng bộ lỗi giá) | `CALCULATION_FAILED`, bảng lỗi cấp trường |
| FAIL-05 | Quản lý chọn *"Bổ sung sổ hộ khẩu."* → Từ chối | `REJECTED`, Sale thấy ghi chú |
| NEEDS_INPUT | Xoá ngày giao dịch | `NEEDS_INPUT` |
| SoD | Quản lý mở hồ sơ *Lâm Chí Thành* (do chính mình lập) | Ẩn nút duyệt; server trả `403 SOD_VIOLATION` |
| F8 | Composer: *"chắc chắn được vay 70%"*, *"miễn cả gốc và lãi"* | `PROHIBITED`, khoá gửi; *Tạo tin đề xuất* → gửi được |

Chạy lại toàn bộ trên Node: `npm test` (dùng đúng API client + SSE client của ứng dụng với MSW).
Chính sách Zen v3.1 hiệu lực **01/08 – 31/10/2026**; demo ngoài dải này thì chọn ngày giao dịch trong dải.
