# API Integration — Frontend PricePolicy

Tài liệu ghép nối frontend ↔ FastAPI cho TechLead và dev backend. Nguồn sự thật là code:

| Nội dung | File |
| :--- | :--- |
| Danh bạ endpoint (method, path, nguồn, quyền) | [`packages/api-client/src/endpoints.ts`](packages/api-client/src/endpoints.ts) |
| Kiểu dữ liệu hợp đồng (wire format, snake_case) | [`packages/api-client/src/contracts/`](packages/api-client/src/contracts/) |
| Header, lỗi, timeout | [`packages/api-client/src/http.ts`](packages/api-client/src/http.ts), [`errors.ts`](packages/api-client/src/errors.ts) |
| SSE client (reconnect, Last-Event-ID, 410) | [`packages/api-client/src/sse.ts`](packages/api-client/src/sse.ts) |
| Hành vi tham chiếu phía server (mock) | [`packages/mock-server/src/`](packages/mock-server/src/) |
| **Đặc tả chạy được** — 18 kịch bản đầu-cuối | [`packages/mock-server/src/scenarios.test.ts`](packages/mock-server/src/scenarios.test.ts) |

> `src/contracts/` và `src/api/endpoints/` của backend **chưa có trong repo** (mọi nhánh). Toàn bộ type
> được dẫn xuất từ TD-4.1, Implement plan §5/§10, PRD v2.2 và CodeBaseIndex. Khi TechLead khoá
> contract, thay `packages/api-client/src/contracts/` bằng type sinh từ OpenAPI (vd. `openapi-typescript`)
> — tên field đã giữ nguyên snake_case nên màn hình không phải sửa.

---

## 0. Hai UI riêng biệt

Đã chọn **Phương án A**: monorepo npm workspaces —

```
apps/customer         UI Khách hàng, công khai, không đăng nhập — origin riêng (:5173 dev)
apps/internal         UI Nội bộ: Sale, Quản lý, Quản trị chính sách — origin riêng (:5174 dev)
packages/api-client   API client dùng chung (contracts, http, SSE, hooks từ src/contracts/) — cả 2 app phụ thuộc
packages/ui           Component dùng chung (shadcn primitives, MoneyText, Evidence, ReferencePlanView…)
packages/mock-server  Backend giả lập
```

Lý do chọn A thay vì Next.js route group (Phương án B): `apps/*` đã là Vite + React Router sẵn có
(xem lịch sử repo), tách thành 2 entry point Vite là thay đổi cấu trúc tối thiểu, giữ nguyên toàn bộ
component/engine đã viết; route group của Next.js đòi hỏi viết lại routing/build từ đầu. Nếu TechLead
quyết định chuyển cả hệ thống sang Next.js sau này, `packages/api-client` và `packages/ui` không đổi —
chỉ viết lại `apps/*`.

**Không có link hay menu nào nối 2 app** (đã bỏ nút "Cổng nhân viên" từng có ở footer Khách hàng) —
hai bên chỉ gặp nhau qua dữ liệu dùng chung trên `packages/mock-server`: khách bàn giao (handoff) ở
`apps/customer` → dossier xuất hiện ngay trong `/sale/leads` ở `apps/internal`, vì cả hai gọi cùng một
tiến trình server, không phải 2 bản MSW độc lập trong 2 tab trình duyệt.

**Endpoint** lấy đúng từ danh bạ `packages/api-client/src/endpoints.ts` (dẫn xuất từ TD-4.4 +
CodeBaseIndex's `src/api/endpoints/pre_sales.py` và `leads.py` — hai file này **chưa có trong repo
backend**, xem cảnh báo đầu tài liệu); không tự đặt thêm path ngoài bảng ở §2.

**Mock server dùng chung**: `packages/mock-server` chạy như **tiến trình Node thật trên cổng TCP thật**
(`npm run dev:mock`, mặc định `:8787`) — KHÔNG phải MSW chặn request trong từng tab trình duyệt như
kiểu SPA gộp trước đây. Lý do bắt buộc: hai app là hai origin thật; nếu mỗi app tự chạy MSW riêng thì
state (dossier, quote, session) sẽ tách rời theo từng tab, không thể tái hiện "khách handoff xong →
dossier hiện ngay trong inbox Sale". Một tiến trình Node dùng chung một `MockDb` trong bộ nhớ giải
quyết đúng yêu cầu này; đã kiểm chứng bằng kịch bản đầu-cuối thật (2 trang trình duyệt, 2 origin khác
nhau, cùng gọi `:8787`) — xem §5.

### TL-3 — Cấu hình CORS/CSRF cho 2 origin

`packages/mock-server/src/server.ts` tự bật CORS cho `http://localhost:5173` và `:5174` (đọc từ env
`MOCK_SERVER_CORS_ORIGINS`, phân tách bằng dấu phẩy). **Backend thật phải cấu hình CORS tương đương**
khi lên staging/production (2 domain thật của 2 app):

| Header | Giá trị |
| :--- | :--- |
| `Access-Control-Allow-Origin` | Phản chiếu đúng origin gọi tới (không dùng `*` vì có `Authorization`) |
| `Access-Control-Allow-Methods` | `GET, POST, PATCH, PUT, DELETE, OPTIONS` |
| `Access-Control-Allow-Headers` | `Content-Type, Authorization, Idempotency-Key, If-Match, X-Correlation-ID, X-Reauth-Token, Last-Event-ID, Cache-Control` — **thiếu `Cache-Control` sẽ chặn SSE** (`sse.ts` gửi `Cache-Control: no-cache` trên mọi request stream, kể cả `/pre-sales/.../events`) |
| `Access-Control-Expose-Headers` | `Idempotent-Replayed, X-Action` (client đọc 2 header này) |

Xác thực dùng Bearer token trong header (không dùng cookie) nên **không cần** `Access-Control-Allow-Credentials`
và không có rủi ro CSRF theo kiểu cookie — `X-Correlation-ID` + `Idempotency-Key` đã đủ chặn replay.
`/public/*` và `/pre-sales/*` không yêu cầu `Authorization` (đúng thiết kế UI Khách hàng không đăng nhập).

---

## 1. Bật / tắt mock

Mỗi app có `.env.example` riêng (`apps/customer/.env.example`, `apps/internal/.env.example`):

```bash
cp apps/customer/.env.example apps/customer/.env.local
cp apps/internal/.env.example apps/internal/.env.local
```

| Biến | Giá trị mặc định | Ý nghĩa |
| :--- | :--- | :--- |
| `NEXT_PUBLIC_API_MODE` | `mock` | `mock`: gọi `packages/mock-server`. `real`: gọi FastAPI thật. |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8787/api/v1` | **Bắt buộc URL tuyệt đối** — 2 app và API là 3 origin khác nhau, gọi qua CORS, không qua proxy của Vite dev server (khác bản SPA gộp trước đây). |

Đổi sang backend thật: sửa `NEXT_PUBLIC_API_BASE_URL` trỏ tới FastAPI, đặt `NEXT_PUBLIC_API_MODE=real`,
khởi động lại `npm run dev:customer` / `dev:internal`. **Không sửa file nào trong `apps/*/src/features/`
hay `packages/ui/`** — cả hai chế độ chạy cùng một `http.ts`/`client.ts`/hooks; chỉ đổi URL đích. Bản
build `real` (`import.meta.env.NEXT_PUBLIC_API_MODE === 'real'`) không tải panel dev-tools (đã kiểm tra
qua `IS_DEV_TOOLS_ENABLED`).

> Frontend hiện là **Vite + React Router**, không phải Next.js như TD-4.1 ghi. Biến vẫn đặt tiền tố
> `NEXT_PUBLIC_` (bật qua `envPrefix` trong mỗi `vite.config.ts`) để không đổi `.env` nếu sau này chuyển.

Kiểm tra quy ước "component không import mock":

```bash
grep -rnE "from ['\"]@pricepolicy/mock-server" apps   # phải rỗng
```

### Công cụ môi trường mock (chỉ `apps/internal`, chạy `npm run dev:internal` + `dev:mock`)

Nút tròn góc dưới phải mở **Mock backend panel**: độ trễ 200–800ms / mạng chậm, tỷ lệ lỗi 500 (0/30/100%),
Agent chậm (vượt deadline 10s), ngắt SSE giữa chừng, replay hết hạn (410), PDF worker lỗi, đăng nhập
nhanh 4 vai trò, **Reset demo**. Panel gọi `{API_BASE_URL_origin}/__mock/*` trực tiếp qua HTTP (cross-origin,
CORS) — không import mã mock. `apps/customer` không có panel này (không đăng nhập nội bộ, không cần).
Dữ liệu mock sống trong bộ nhớ tiến trình `packages/mock-server` — mất khi dừng tiến trình, seed lại
mỗi lần `npm run dev:mock`; mật khẩu mọi tài khoản nội bộ: `Vland@2026`.

---

## 2. Endpoint → hook → màn hình

Base `/api/v1`. **Nguồn**: `TD-4.4` = có trong 29 endpoint theo CodeBaseIndex; `ĐỀ XUẤT` = UI cần, chưa có
trong TD-4.4 (xem §3).

| Method & path | Nguồn | Quyền | Hook | App · Màn hình |
| :--- | :--- | :--- | :--- | :--- |
| `POST /quotes` → **202** | TD-4.4 | SALE | `useCreateQuote` | Nội bộ · Báo giá khách tại sàn |
| `GET /quotes/{id}?version=` | TD-4.4 (`version` ĐỀ XUẤT) | staff | `useQuote` | Nội bộ · Chi tiết báo giá (Sale), Workspace (Quản lý) |
| `GET /quotes/{id}/events` (SSE) | TD-4.4 | staff | `useQuoteEvents` | Nội bộ · Tiến trình Agent |
| `GET /quotes/{id}/evidence?version=` | TD-4.4 | staff | `useQuoteEvidence` | Nội bộ · Why/Why-not, panel chứng cứ, luận điểm |
| `GET /quotes/{id}/audit` | TD-4.4 | staff | `useQuoteAudit` | Nội bộ · Nhật ký hồ sơ (hash chain) |
| `GET /quotes/{id}/pdf` | TD-4.4 | staff | `useQuotePdf` | Nội bộ · Thẻ PDF (Quản lý) |
| `POST /quotes/{id}/approve` | TD-4.4 | MANAGER | `useApproveQuote` | Nội bộ · Workspace — Ký duyệt |
| `POST /quotes/{id}/reject` | TD-4.4 | MANAGER | `useRejectQuote` | Nội bộ · Workspace — Từ chối |
| `POST /quotes/{id}/revision` | TD-4.4 | MANAGER | `useRequestRevision` | Nội bộ · Workspace — Yêu cầu sửa |
| `POST /quotes/{id}/pdf-retry` | TD-4.4 | MANAGER | `useRetryPdf` | Nội bộ · Thẻ PDF khi `FAILED` |
| `GET /quotes?status=A,B&source_dossier_id=` | ĐỀ XUẤT | staff | `useQuotes` | Nội bộ · Danh sách báo giá, hàng đợi duyệt, badge menu |
| `POST /quotes/{id}/submit` | ĐỀ XUẤT | SALE | `useSubmitQuote` | Nội bộ · Gửi Quản lý duyệt |
| `POST /quotes/{id}/versions` → **202** | ĐỀ XUẤT | SALE | `useNewQuoteVersion` | Nội bộ · Chỉnh sửa & phân tích lại |
| `GET /leads` | TD-4.4 | SALE | `useLeads`, `useLead` | Nội bộ · Hộp hồ sơ khách, form báo giá |
| `POST /leads/{id}/convert-to-quote` → **202** | TD-4.4 | SALE | `useConvertLead` | Nội bộ · Lập báo giá chính thức từ dossier |
| `POST /pre-sales/sessions` | TD-4.4* | public | `useStartPreSales` | Khách hàng · Tư vấn tài chính |
| `GET /pre-sales/sessions/{id}` | TD-4.4* | public | `usePreSalesSession` | Khách hàng · Tư vấn tài chính (khôi phục phiên) |
| `POST /pre-sales/sessions/{id}/messages` | TD-4.4* | public | `useSendPreSalesMessage` | Khách hàng · Chat dẫn dắt |
| `POST /pre-sales/sessions/{id}/constraints/confirm` | TD-4.4* | public | `useConfirmConstraints` | Khách hàng · Xác nhận thông tin |
| `POST /pre-sales/sessions/{id}/plan` → **202** | TD-4.4* | public | `useGeneratePlan` | Khách hàng · Kích hoạt lập phương án |
| `GET /pre-sales/sessions/{id}/events` (SSE) | ĐỀ XUẤT | public | `usePreSalesEvents` | Khách hàng · Tiến trình lập phương án ("Đang tính phương án…") |
| `POST /pre-sales/sessions/{id}/handoff` | TD-4.4* | public | `useHandoff` | Khách hàng · Đồng ý bàn giao cho Sale |
| `POST /compliance/check-message` | TD-4.4 | SALE | `useComplianceCheck` | Nội bộ · Composer (debounce 500ms) |
| `POST /messages/send` | TD-4.4 | SALE | `useSendMessage` | Nội bộ · Composer — cổng gửi duy nhất |
| `POST /compliance/draft-message` | ĐỀ XUẤT | SALE | `useDraftMessage` | Nội bộ · Composer — Tạo tin đề xuất |
| `POST /policies/extract-rules` (multipart) | TD-4.4 | POLICY_ADMIN | `useExtractRules` | Nội bộ · Tải lên văn bản |
| `POST /policies/{id}/rules/test` | TD-4.4 | POLICY_ADMIN | `useTestRules` | Nội bộ · Kiểm tra trước ban hành |
| `POST /policies/{id}/publish` | TD-4.4 | POLICY_ADMIN | `usePublishPolicy` | Nội bộ · Ban hành |
| `POST /evaluation/benchmark-runs` | TD-4.4 | POLICY_ADMIN | `useRunBenchmark` | Nội bộ · Kiểm thử công thức |
| `GET /policies?project_id=&status=` | ĐỀ XUẤT | staff | `usePolicies` | Nội bộ · Danh sách chính sách, chọn văn bản trong form |
| `GET /policies/{id}` | ĐỀ XUẤT | staff | `usePolicy` | Nội bộ · Chi tiết chính sách, form báo giá |
| `GET /policies/active?project_id=&date=` | ĐỀ XUẤT | staff | `useActivePolicy` | Nội bộ · Form báo giá (Time-Travel) |
| `GET /units?project_id=` | ĐỀ XUẤT | public | `useUnits` | Nội bộ · Form báo giá |
| `GET /public/projects` | ĐỀ XUẤT | public | `useProjectOverviews` | Khách hàng · Trang chủ |
| `POST /auth/login`, `POST /auth/logout` | ĐỀ XUẤT | — | `useLogin` | Nội bộ · Đăng nhập |
| `POST /auth/reauth` | ĐỀ XUẤT | MANAGER | `useReauth` | Nội bộ · Dialog ký duyệt |

\* CodeBaseIndex chỉ ghi "6 endpoint Pre-Sales sessions"; đường dẫn chi tiết (kể cả SSE, endpoint thứ 7,
[ĐỀ XUẤT]) là suy luận từ TD-4.1 §3.1 áp dụng cho luồng Pre-Sales.
Endpoint TD-4.4 chưa dùng: `POST /quotes/{id}/exception` (N-18, TGĐ), `GET /.well-known/jwks.json`.

Test `scenarios.test.ts › Mọi endpoint trong danh bạ đều có handler mock` bảo đảm bảng trên và mock luôn khớp.

---

## 3. Việc cần TechLead chốt

### 3.1 Câu hỏi mở

1. **Đường dẫn SSE quote**: TD-4.1 §3.1 ghi `/quotes/{id}/stream`, CodeBaseIndex ghi `/quotes/{id}/events`.
   Client dùng `stream_url` do 202 trả về; chỉ khi tải lại trang mới dùng `ENDPOINTS.quoteEvents`
   (hiện `/events`). Chốt xong chỉ sửa **một dòng** trong `endpoints.ts`.
2. **SSE Pre-Sales**: TD-4.4 chưa liệt kê endpoint stream cho Pre-Sales — `GET /pre-sales/sessions/{id}/events`
   là [ĐỀ XUẤT], theo đúng mẫu `stream_url` + SSE của quote (TD-4.1 §3.1) áp cho luồng lập phương án
   tham khảo (F3/F5), event duy nhất `PRE_SALES_PLAN_READY`. Nếu TechLead có thiết kế khác (vd. tái dùng
   `session_id` làm kênh chung cho nhiều loại sự kiện Pre-Sales khác), cần đối chiếu lại.
3. **6 objectives**: CodeBaseIndex nói `OptimizationObjective` có 6 giá trị, PRD chỉ định nghĩa 4
   (`MIN_NET_PRICE`, `MIN_INITIAL_OUTFLOW`, `MIN_TOTAL_CASH_OUTFLOW`, `MAX_BENEFIT_VALUE`). Cần tên 2 giá trị còn lại.
4. **Bước gửi duyệt**: TD-4.1 cho `quote_ready` mang `READY_FOR_REVIEW` trực tiếp; PRD và brief có bước
   Sale "gửi duyệt" từ `DRAFT`. Frontend theo PRD (`DRAFT` → `POST /submit` → `READY_FOR_REVIEW`).
5. **`POST /quotes/{id}/revision`**: frontend hiểu là lệnh của **Quản lý** yêu cầu sửa; Sale tạo phiên bản
   mới qua `POST /quotes/{id}/versions` [ĐỀ XUẤT]. Nếu `revision` là lệnh của Sale thì đổi 2 dòng trong `endpoints.ts`.
6. **Mã lỗi OCC**: TD-4.1 dùng `409 STALE_QUOTE_VERSION`; CodeBaseIndex nhắc `get_if_match_etag` (412).
   Client xử lý cả hai như nhau (`isStaleVersion`).
7. **Scenario code**: dùng `PA-CHUDONG | PA-NHANH | PA-VAY` (CodeBaseIndex). Implement plan còn nhắc `PA-CHUAN`.

### 3.2 Field đề xuất bổ sung contract

Các field dưới đây có trong type nhưng **không có** trong tài liệu nào — đánh dấu `[ĐỀ XUẤT]` trong code:

| Model | Field | Lý do |
| :--- | :--- | :--- |
| `TransactionContext` | `requested_policy_id: string \| null` | Sale viện dẫn văn bản cụ thể → phát hiện `EXPIRED` (FAIL-02). `null` = tra cứu theo ngày. |
| `RuleEvaluation` | `effect: 'PRICE_REDUCTION' \| 'IN_KIND' \| 'FINANCING'` | Breakdown phải ghi quà hiện vật "không trừ vào giá" (PRD §7). |
| `EvidenceBackedClaim` | `direction: 'WHY' \| 'WHY_NOT'`, `rule_code`, `decision_status` | Tách mục "Why not?" và mở chứng cứ theo điều khoản. |
| `Quote` | `versions: QuoteVersionSummary[]`, `missing_fields`, `abstention`, `submitted_at` | Xem bản cũ (chỉ đọc), hiển thị NEEDS_INPUT, loại dừng an toàn. |
| `ChatMessage` | `suggestions: string[]` | Chip trả lời nhanh cho câu hỏi dẫn dắt (D3-1). |
| `PreSalesSession` | `stream_url?: string` | Cùng mẫu với `QuoteAccepted.stream_url` — chỉ có khi đang lập phương án. |
| `Recommendation` | `comparisons[].delta_vnd` | UI dựng câu "Theo tiêu chí X, phương án Y giảm … so với …" từ số liệu. |
| `ErrorCode` | `POLICY_AMBIGUOUS`, `IDEMPOTENCY_KEY_REQUIRED`, `REAUTH_REQUIRED` | Chưa có trong Error Catalog TL-0.3. |
| Enum | Giá trị `LeadDossierStatus`, `PreSalesSessionStatus`, `ApprovalDecision` | Tài liệu chỉ nêu tên enum, không nêu giá trị. |

---

## 4. Quy ước giao thức (backend phải tuân theo)

**Wire format**: JSON snake_case đúng như `packages/api-client/src/contracts/`. Tiền là số nguyên VNĐ
(`*_vnd`), tỷ lệ thập phân, ngày nghiệp vụ `YYYY-MM-DD`, thời điểm ISO 8601 UTC.

**Header gửi đi** (`http.ts`, `sse.ts`):

| Header | Khi nào |
| :--- | :--- |
| `Authorization: Bearer <access_token>` | Mọi route nội bộ (không gửi ở `/public/*`, `/pre-sales/*`) |
| `Idempotency-Key: <uuid>` | **Mọi POST**. Cùng thao tác thử lại (timeout, lỗi mạng) dùng lại đúng key; payload khác → key mới. |
| `If-Match: "v<quote_version>"` | `submit`, `versions`, `approve`, `reject`, `revision` |
| `X-Reauth-Token` | `approve` — lấy từ `POST /auth/reauth`, dùng một lần |
| `X-Correlation-ID: <uuid>` | Mọi request |
| `Cache-Control: no-cache` | Mọi kết nối SSE (`quotes/.../events`, `pre-sales/.../events`) — **phải nằm trong CORS allow-list** (xem §0 TL-3) |
| `Last-Event-ID` | SSE reconnect |

**Lỗi**: body `{ "code": ErrorCode, "message": "…" }` (client cũng đọc `{ error: {…} }` và FastAPI `{ detail }`).
`message` hiển thị thẳng cho người dùng (tiếng Việt). Client xử lý:

| Status / code | Hành vi UI |
| :--- | :--- |
| `401` | Nội bộ: xoá phiên → `/login` (giữ đường dẫn để quay lại). Khách hàng: không có phiên, không áp dụng. |
| `403 SOD_VIOLATION` / `REAUTH_REQUIRED` / `FORBIDDEN` | Hiện thông báo, không xoá phiên |
| `409 STALE_QUOTE_VERSION` (hoặc `412`) | Tự tải lại quote, báo "đã có phiên bản mới" |
| `409 IDEMPOTENCY_KEY_REUSE_PAYLOAD_MISMATCH` | Báo lỗi |
| `409 PDF_NOT_READY` | Ẩn nút tải |
| `410` (Pre-Sales session) | Khách hàng: phiên hết hạn → tự mở phiên mới, không kẹt màn lỗi |
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

**SSE Pre-Sales** `GET /pre-sales/sessions/{id}/events` — cùng cơ chế (`subscribeSse()` dùng chung), đơn
giản hơn vì không có "phiên bản": `POST .../plan` trả **202** với `session` mang `stream_url`; khi phương
án tính xong, server phát đúng 1 sự kiện `PRE_SALES_PLAN_READY` rồi đóng stream — client refetch
`GET /pre-sales/sessions/{id}` để lấy `plan`. Không yêu cầu `Authorization` (public). D3-1: UI chỉ hiện 4
bước nghiệp vụ thân thiện (Đã hiểu nhu cầu → Đang kiểm tra chính sách → Đang tính phương án → Đã kiểm
tra điều kiện), không lộ SSE/kỹ thuật; việc "khi nào thật sự xong" do sự kiện SSE thật quyết định.

**PDF**: sau `approve`, `pdf_status` đi `PENDING → GENERATING → PDF_ISSUED` (hoặc `FAILED` → `pdf-retry`).
UI chỉ hiện "Đã phát hành" và nút tải khi `PDF_ISSUED`; trong lúc chờ, `GET /quotes/{id}` được poll mỗi 1,5s.
Sale không có nút duyệt, không có nút xuất PDF.

---

## 5. Kịch bản mock (quyết định bởi input, không có nút chọn kịch bản)

| Kịch bản | Input | Kết quả |
| :--- | :--- | :--- |
| **DoD** — 2 app thật | `apps/customer`: chat → xác nhận → SSE lập phương án → bàn giao (consent) | Dossier hiện **ngay** trong `/sale/leads` ở `apps/internal` (origin khác) → Sale lập báo giá chính thức (tính lại, không kế thừa số Pre-Sales) → gửi duyệt → Quản lý ký (re-auth) → `PDF_ISSUED` |
| FAIL-01 | *Gói hỗ trợ nội thất* + *Thanh toán sớm 95%* | `ABSTAINED` / CONFLICT cấp 1, trích **Điều 6, Khoản 2** |
| FAIL-02 | Ngày `2026-07-15`, văn bản chính sách `v3.1` | `ABSTAINED` / EXPIRED |
| FAIL-03 | *Ưu đãi khách hàng đặc biệt theo quyết định riêng* | `ABSTAINED` / AMBIGUOUS (cờ vàng), vào tab Ngoại lệ của Quản lý |
| FAIL-04 | Căn **ZEN-B-1108** (bảng hàng đồng bộ lỗi giá) | `CALCULATION_FAILED`, bảng lỗi cấp trường |
| FAIL-05 | Quản lý chọn *"Bổ sung sổ hộ khẩu."* → Từ chối | `REJECTED`, Sale thấy ghi chú |
| NEEDS_INPUT | Xoá ngày giao dịch | `NEEDS_INPUT` |
| SoD | Quản lý mở hồ sơ do chính mình lập | Ẩn nút duyệt; server trả `403 SOD_VIOLATION` |
| F8 | Composer: *"chắc chắn được vay 70%"*, *"miễn cả gốc và lãi"* | `PROHIBITED`, khoá gửi; *Tạo tin đề xuất* → gửi được |

Chạy lại các kịch bản FAIL/F8/SoD trên Node: `npm test` (dùng đúng API client + SSE client của ứng
dụng, chạy trên `packages/mock-server`). Kịch bản **DoD** đã kiểm chứng thủ công bằng 2 trang trình
duyệt thật ở 2 origin `:5173`/`:5174` cùng gọi `packages/mock-server` thật ở `:8787` — không có lỗi
console, không lỗi CORS. Chính sách Zen v3.1 hiệu lực **01/08 – 31/10/2026**; demo ngoài dải này thì
chọn ngày giao dịch trong dải.
