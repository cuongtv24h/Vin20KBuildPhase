# Hướng dẫn ghép nối Backend

Tài liệu cho dev backend hiện thực API mà frontend PricePolicy đang gọi. Nguồn sự thật về kiểu dữ
liệu là code, không phải tài liệu này:

| Nội dung | File |
| :--- | :--- |
| Domain model (enum trạng thái, entity) | [`src/types/domain.ts`](../src/types/domain.ts) |
| DTO request/response + interface `ApiClient` + route REST (`@endpoint`) | [`src/api/contracts.ts`](../src/api/contracts.ts) |
| Client HTTP thật (URL, header, SSE) | [`src/api/http/httpClient.ts`](../src/api/http/httpClient.ts) |
| Máy trạng thái hồ sơ + quyền theo vai trò | [`src/engine/workflow.ts`](../src/engine/workflow.ts) |
| Hành vi tham chiếu phía server (validate, quyền, side-effect) | [`src/api/mock/services.ts`](../src/api/mock/services.ts), [`src/api/mock/mockClient.ts`](../src/api/mock/mockClient.ts) |
| Test tích hợp mô tả hành vi mong đợi | [`src/api/mock/mockClient.test.ts`](../src/api/mock/mockClient.test.ts) |

Backend mock trong `src/api/mock/` chính là **bản đặc tả chạy được**: backend thật cần trả đúng
kết quả mà `mockClient.test.ts` kiểm tra.

## 1. Bật chế độ gọi backend thật

```bash
cp .env.example .env.local
# sửa: VITE_API_MODE=http
npm run dev
```

Với `VITE_API_BASE_URL=/api/v1`, Vite dev server chuyển tiếp `/api/*` tới `VITE_API_PROXY_TARGET`
(mặc định `http://localhost:8000`, khớp `app.include_router(router, prefix="/api/v1")` trong
`src/main.py`). Không cần sửa màn hình nào.

## 2. Quy ước chung

- **JSON, camelCase** đúng tên field trong `contracts.ts` / `domain.ts` (Pydantic: dùng
  `alias_generator=to_camel`, `populate_by_name=True`).
- **Xác thực:** `POST /auth/login` trả `AuthSession { accessToken, expiresAt, user }`. Mọi request
  nội bộ gửi `Authorization: Bearer <accessToken>`. Các route `/public/*` không cần token.
- **Lỗi:** status ≠ 2xx với body `{ "code": "INVALID_TRANSITION", "message": "..." }`. `message`
  được hiển thị thẳng cho người dùng (tiếng Việt). Frontend xử lý:
  - `401` → xoá phiên, đưa về `/login`;
  - `403` quyền, `404` không tồn tại, `409` sai trạng thái, `410` link báo giá hết hạn, `422` validate.
- **Tiền:** số nguyên VNĐ (không số thực). Làm tròn từng bước theo `src/engine/calculator.ts`.
- **Tỷ lệ:** số thập phân (`0.085` = 8,5%).
- **Ngày:** ngày nghiệp vụ `YYYY-MM-DD` (`transactionDate`, `effectiveFrom/To`); thời điểm ISO 8601 UTC (`createdAt`, `at`…).
- **Mã định danh** do server sinh: `QUO-YYYY-MM-NNNNN`, `LEAD-YYYY-NNNN`, `EVT-NNNNNN`, `shareToken` ngẫu nhiên ≥ 16 ký tự.

## 3. Vai trò

| `UserRole` | Người dùng | Điểm vào frontend |
| :--- | :--- | :--- |
| `SALE` | Chuyên viên kinh doanh | `/sale` |
| `MANAGER` | Quản lý kinh doanh | `/manager` |
| `SALE_ADMIN` | Admin Sale | `/admin` |
| _(không đăng nhập)_ | Khách hàng pre-sale | `/`, `/units/{unitCode}`, `/quote/{shareToken}` |

## 4. Danh sách endpoint

Base: `/api/v1`. Cột **Quyền** là vai trò được phép; server phải tự lọc dữ liệu theo quyền.

### Auth
| Method | Path | Quyền | Request | Response |
| :--- | :--- | :--- | :--- | :--- |
| POST | `/auth/login` | công khai | `LoginRequest` | `AuthSession` |
| POST | `/auth/logout` | đã đăng nhập | — | `204` |

### Catalog (đọc)
| Method | Path | Quyền | Request | Response |
| :--- | :--- | :--- | :--- | :--- |
| GET | `/projects` | nội bộ | — | `Project[]` |
| GET | `/units?projectId=&status=&bedrooms=` | công khai | `UnitFilter` | `ApartmentUnit[]` |
| GET | `/units/{unitCode}` | công khai | — | `ApartmentUnit` |
| GET | `/payment-plans` | nội bộ | — | `PaymentPlanConfig[]` |
| GET | `/policies/active?projectId=&date=` | nội bộ | — | `PolicyVersion \| null` — chỉ xét `status = PUBLISHED` |

### Public (khách hàng)
| Method | Path | Request | Response | Ghi chú |
| :--- | :--- | :--- | :--- | :--- |
| GET | `/public/projects` | — | `ProjectOverview[]` | Chính sách đang hiệu lực **hôm nay** |
| POST | `/public/estimates` | `EstimateRequest` | `PriceEstimate` | Giá tham khảo, xem `src/engine/estimate.ts` |
| POST | `/public/leads` | `CreateLeadRequest` | `LeadReceipt` | Tạo `Lead` trạng thái `NEW`, chưa gán Sale |
| GET | `/public/quotes/{shareToken}` | — | `CustomerQuoteView` | Lần mở đầu ghi `distribution.viewedAt` + event `CUSTOMER_VIEWED`. `404` nếu không có / chưa `APPROVED`, `410` nếu quá `expiresAt` |
| POST | `/public/quotes/{shareToken}/response` | `CustomerResponseRequest` | `CustomerQuoteView` | Ghi `customerResponse` + event `CUSTOMER_RESPONDED`; `ACCEPTED` → lead `CUSTOMER_ACCEPTED` |
| GET | `/public/quotes/{shareToken}/verify` | — | `QuoteVerification` | Băm lại snapshot đã lưu, so với hash đã ký |

`CustomerQuoteView` **không được** chứa `riskFlag`, ghi chú nội bộ của Quản lý hay dữ liệu Sale khác.

### Leads (Sale)
| Method | Path | Quyền | Request | Response | Ghi chú |
| :--- | :--- | :--- | :--- | :--- | :--- |
| GET | `/leads?scope=MINE\|UNASSIGNED\|ALL` | nội bộ | — | `Lead[]` | |
| GET | `/leads/{leadId}` | nội bộ | — | `Lead` | |
| POST | `/leads/{leadId}/claim` | `SALE` | — | `Lead` | Gán cho người gọi; `409 LEAD_ALREADY_ASSIGNED` nếu người khác đã nhận; `NEW → IN_PROGRESS` |
| PATCH | `/leads/{leadId}` | `SALE` (người phụ trách) | `UpdateLeadStatusRequest` | `Lead` | |

### Quotes
| Method | Path | Quyền | Request | Response | Ghi chú |
| :--- | :--- | :--- | :--- | :--- | :--- |
| GET | `/quotes?status=A,B&leadId=` | nội bộ | — | `Quote[]` | `SALE` chỉ nhận hồ sơ `ownerId = mình`; sắp xếp mới nhất trước |
| GET | `/quotes/{quoteId}` | nội bộ | — | `Quote` | `SALE` khác chủ → `403` |
| POST | `/quotes/preflight` | `SALE` | `PreflightRequest` | `PreflightResult` | Không lưu. Gọi mỗi lần Sale tick ưu đãi |
| POST | `/quotes` | `SALE` | `CreateQuoteRequest` | `202 { quoteId }` | Chạy pipeline phân tích (mục 6) |
| POST | `/quotes/{quoteId}/revisions` | `SALE` (chủ) | `CreateQuoteRequest` | `202 { quoteId }` | `version + 1`, xoá `approval` cũ |
| GET | `/quotes/{quoteId}/events` | `SALE` (chủ) | `?access_token=` | SSE | Mục 6 |
| POST | `/quotes/{quoteId}/submit` | `SALE` (chủ) | — | `Quote` | `DRAFT → READY_FOR_REVIEW` |
| POST | `/quotes/{quoteId}/decision` | `MANAGER` | `ApprovalDecisionRequest` | `Quote` | `notes` bắt buộc khi `REJECTED`/`NEEDS_REVISION` (`422`) |
| POST | `/quotes/{quoteId}/share` | `SALE` (chủ) | `ShareQuoteRequest` | `Quote` | Chỉ khi `APPROVED`. Giữ nguyên `shareToken` nếu gửi lại; `expiresAt = sharedAt + 7 ngày`; lead → `QUOTE_SENT` |
| GET | `/quotes/{quoteId}/verify` | nội bộ | — | `QuoteVerification` | |

### Policies & bảng hàng (Admin Sale)
| Method | Path | Quyền | Request | Response | Ghi chú |
| :--- | :--- | :--- | :--- | :--- | :--- |
| GET | `/policies` | nội bộ | — | `PolicyVersion[]` | Mới nhất theo `effectiveFrom` trước |
| GET | `/policies/{policyId}` | nội bộ | — | `PolicyVersion` | |
| POST | `/policies` | `SALE_ADMIN` | `CreatePolicyDraftRequest` | `PolicyVersion` | Nhân bản thành `DRAFT`, xoá văn bản gốc |
| PATCH | `/policies/{policyId}` | `SALE_ADMIN` | `UpdatePolicyDraftRequest` | `PolicyVersion` | Chỉ `DRAFT` (`409 POLICY_LOCKED`) |
| POST | `/policies/{policyId}/checks` | `SALE_ADMIN` | — | `PublishCheckReport` | Xem `src/engine/policyChecks.ts` |
| POST | `/policies/{policyId}/publish` | `SALE_ADMIN` | — | `PolicyVersion` | Chạy lại checks; có `FAIL` → `422 PUBLISH_CHECKS_FAILED` |
| POST | `/policies/{policyId}/archive` | `SALE_ADMIN` | — | `PolicyVersion` | |
| PATCH | `/units/{unitCode}` | `SALE_ADMIN` | `UpdateUnitRequest` | `ApartmentUnit` | |
| POST | `/qa/formula-regression` | `SALE_ADMIN` | — | `BenchmarkRunResult[]` | 15 ca trong `src/engine/benchmark.ts` |

## 5. Máy trạng thái

### Hồ sơ báo giá (`WorkflowStatus`)

```
                       ┌──────────── revise (SALE) ─────────────┐
                       ▼                                        │
POST /quotes ──▶ DRAFT | ABSTAINED | CALCULATION_FAILED ────────┤
                   │        │                                   │
         submit    │        │ (tự động vào hàng đợi ngoại lệ)   │
                   ▼        ▼                                   │
          READY_FOR_REVIEW  ABSTAINED ── decide ──▶ NEEDS_REVISION ─┘
                   │                          └──▶ REJECTED
                   └── decide ──▶ APPROVED ──share──▶ APPROVED (+distribution)
                              ├─▶ NEEDS_REVISION
                              └─▶ REJECTED
```

| Hành động | Từ trạng thái | Vai trò |
| :--- | :--- | :--- |
| `SUBMIT` | `DRAFT` | `SALE` |
| `REVISE` | `DRAFT`, `ABSTAINED`, `CALCULATION_FAILED`, `NEEDS_REVISION` | `SALE` |
| `APPROVE` | `READY_FOR_REVIEW` | `MANAGER` |
| `REJECT`, `REQUEST_REVISION` | `READY_FOR_REVIEW`, `ABSTAINED` | `MANAGER` |
| `SHARE` | `APPROVED` | `SALE` |

Sai bảng này → `409 INVALID_TRANSITION`. Hàng đợi của Quản lý = `READY_FOR_REVIEW` + `ABSTAINED`.

### Lịch sử (`Quote.history`)

Mỗi thao tác thêm một `QuoteEvent` (append-only): `CREATED`, `REVISED`, `SUBMITTED`, `ESCALATED`
(actorRole `SYSTEM`, khi kết quả `ABSTAINED`), `APPROVED`, `REJECTED`, `REVISION_REQUESTED`,
`SHARED`, `CUSTOMER_VIEWED`, `CUSTOMER_RESPONDED`. `note` mang ghi chú Quản lý / lời nhắn của khách.
Dashboard Quản lý tính thời gian ra quyết định từ các event này.

### Yêu cầu khách hàng (`LeadStatus`)

`NEW` —claim/tạo báo giá→ `IN_PROGRESS` —share→ `QUOTE_SENT` —khách ACCEPTED→ `CUSTOMER_ACCEPTED`. `CLOSED` do Sale đặt.

## 6. Pipeline phân tích & SSE

`POST /quotes` và `POST /quotes/{id}/revisions` trả `202 { quoteId }` ngay, sau đó frontend mở
`EventSource(GET /quotes/{id}/events?access_token=…)` (EventSource không gửi được header).

| SSE event | `data` | Ý nghĩa |
| :--- | :--- | :--- |
| `progress` | `AnalysisProgressEvent` | `{ stage, state, message? }` |
| `completed` | `{}` | Kết thúc; frontend gọi `GET /quotes/{id}` |

`stage` lần lượt: `POLICY_LOOKUP` → `PREFLIGHT` → `PRICING` → `RANKING`. `state`: `RUNNING`, `DONE`,
`BLOCKED` (dừng ở bước này), `SKIPPED` (các bước sau bước bị chặn). Chuỗi phát mẫu: xem
`replayProgress` trong `mockClient.ts`.

Kết quả cuối (logic tham chiếu `src/engine/quoteFactory.ts#analyzeQuote`):

1. Time-Travel: chọn chính sách `PUBLISHED` có `effectiveFrom ≤ transactionDate ≤ effectiveTo`.
   Không có → `ABSTAINED` (finding `EXPIRED`).
2. Preflight (`src/engine/conflictDetector.ts`): xung đột Cấp 1 `mutualExclusion`, Cấp 2
   `conditionalConflict`, Cấp 3 `isAmbiguous` → `ABSTAINED`.
3. Tính 3 phương án (`src/engine/calculator.ts`) — LLM **không** được tự tính số.
4. Validation gate lỗi → `CALCULATION_FAILED`.
5. Xếp hạng theo `objective` (`src/engine/recommend.ts`) → `DRAFT` + `recommendation`.
6. `riskFlag`: `RED` khi dừng/lỗi, `YELLOW` khi tổng chiết khấu ≥ 12%, còn lại `GREEN`.

## 7. Ký duyệt & xác thực

Khi `APPROVED`, server đóng băng `PolicySnapshot` (`buildSnapshot`), tính SHA-256 trên JSON chuẩn
hoá — key sắp xếp đệ quy (`src/lib/hash.ts#canonicalJsonStringify`) — lưu vào `snapshot`,
`snapshotHash`, `approval.signatureHex`. Bản production nên ký thêm bằng khoá của server (KMS);
frontend chỉ hiển thị và gọi `verify`.

## 8. Checklist ghép nối

- [ ] Hiện thực các route mục 4 với DTO khớp `contracts.ts`.
- [ ] Áp đúng bảng chuyển trạng thái mục 5 và lọc dữ liệu theo vai trò.
- [ ] Phát SSE `progress` / `completed` cho phân tích báo giá.
- [ ] Thông điệp lỗi tiếng Việt trong `message`.
- [ ] Chạy frontend với `VITE_API_MODE=http`, đi hết 4 luồng trong README.
- [ ] Chuyển các ca trong `mockClient.test.ts` thành test API phía backend.
