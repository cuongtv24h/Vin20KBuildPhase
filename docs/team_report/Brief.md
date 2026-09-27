# BẢN TÓM TẮT DỰ ÁN (PROJECT BRIEF)
## PRICEPOLICY AI AGENT – NỀN TẢNG BẢO CHỨNG ĐỊNH GIÁ & QUẢN TRỊ CHÍNH SÁCH BÁN HÀNG BẤT ĐỘNG SẢN VLANDFUTURE
**Mã đề tài:** BDS020-06  
**Lĩnh vực:** Bất động sản – Kinh doanh O2O (Online to Offline)  
**Khối nghiệp vụ:** Hệ sinh thái Kinh doanh Bất động sản VLandFuture  
**Phiên bản tài liệu:** v1.0 — Official Submission Brief  
**Tài liệu tham chiếu chi tiết:** 
- PRD & Business Requirement: [1.requirement-analysis.md](1.requirement-analysis.md)
- Product Discovery & Strategy: [2.product-discovery.md](2.product-discovery.md)
- Kiến trúc Tổng thể: [3.architecture-design.md](3.architecture-design.md)
- Kiến trúc Triển khai & Hạ tầng: [4-technical-design/4.1-technical-architecture-runtime-deployment.md](4-technical-design/4.1-technical-architecture-runtime-deployment.md)
- Đặc tả Dữ liệu & Số học: [4-technical-design/4.2-domain-data-financial-design.md](4-technical-design/4.2-domain-data-financial-design.md)
- Quy trình Giao diện: [Wireframe_UI_Flow.md](Wireframe_UI_Flow.md)

---

# 1. TỔNG QUAN DỰ ÁN & VẤN ĐỀ NGHIỆP VỤ (EXECUTIVE SUMMARY & PROBLEM)

### 1.1 Thực trạng Ngành Bất động sản
Trong mô hình kinh doanh bất động sản hiện đại, chính sách bán hàng của Chủ đầu tư là công cụ kích cầu quan trọng nhất nhưng cũng phức tạp nhất. Một chính sách bán hàng thường có cấu trúc **đa tầng, nhiều lớp**:
- Chiết khấu thanh toán sớm theo tiến độ (5% – 12%).
- Hỗ trợ lãi suất ngân hàng (HTLS 0% kèm ân hạn nợ gốc).
- Quà tặng mùa vụ, gói nội thất, voucher nghỉ dưỡng, phí quản lý.
- Ưu đãi khách hàng thân thiết, khách mua sỉ, hoặc các chính sách theo sự kiện mở bán.
- Các văn bản chính sách thay đổi liên tục theo từng tuần, từng đợt mở bán (Time-travel Policy Versioning).

### 1.2 Nỗi đau Doanh nghiệp & Rủi ro Vận hành
1. **Đối với Nhân viên Kinh doanh (Sales Executive):**  
   - Phải tính toán thủ công bằng các bảng Excel rời rạc hoặc nhẩm tay, mất từ **60 đến 120 phút** cho mỗi khách hàng.
   - Thường xuyên nhầm lẫn giữa các điều khoản loại trừ (ví dụ: đã chọn gói vay 0% lại cộng dồn chiết khấu trả nhanh).
   - Không thể giải thích minh bạch cho khách hàng lý do tại sao khoản ưu đãi này được áp dụng còn khoản kia bị loại trừ (*"Why not?"*), làm giảm niềm tin và kéo dài thời gian chốt deal.
2. **Đối với Cấp Quản lý (Sales Manager):**  
   - Tình trạng *"duyệt niềm tin"* qua tin nhắn chụp màn hình Zalo, thiếu cơ sở kiểm chứng.
   - Nguy cơ thất thoát doanh thu từ **2% đến 6%** tổng giá trị giao dịch do nhân viên áp dụng sai chính sách hoặc chiết khấu vượt thẩm quyền.
3. **Đối với Doanh nghiệp & Pháp chế:**  
   - Thiếu bằng chứng kiểm toán (Audit Trail) lưu giữ nguyên trạng chính sách tại thời điểm phát hành báo giá, dễ dẫn đến khiếu nại và tranh chấp pháp lý khi giá trị mỗi căn hộ lên tới hàng tỷ hoặc hàng chục tỷ đồng.

---

# 2. GIẢI PHÁP ĐỀ XUẤT: PRICEPOLICY AI AGENT (THE SOLUTION)

**PricePolicy AI Agent** không phải là một chatbot thông thường hay bảng tính điện tử bọc web, mà là một **Hệ thống AI Hỗ trợ Ra quyết định Thẩm quyền (AI-Powered Commercial Decision Support System)** đóng vai trò là **"Tầng Bảo chứng Niềm tin (The Trust Layer)"** giữa Chủ đầu tư, Đội ngũ kinh doanh và Khách hàng.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            NGUỒN CHÍNH SÁCH BÁN HÀNG                        │
│                   (Văn bản PDF, Quy định mở bán, Bảng hàng)                 │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                 PRICEPOLICY AI AGENT: TẦNG BẢO CHỨNG NIỀM TIN               │
│  ┌─────────────────────────┐                ┌────────────────────────────┐  │
│  │     NHẬN THỨC & SUY LUẬN│                │     CÔNG CỤ SỐ HỌC XÁC ĐỊNH │  │
│  │   (LLM + Policy RAG)    │───────────────▶│ (Deterministic Calculator) │  │
│  │ • Trích xuất điều khoản │                │ • 100% Python Decimal      │  │
│  │ • Bắt xung đột 3 cấp    │                │ • 0-float, sai số 0 VNĐ    │  │
│  │ • Lập kịch bản tối ưu   │                │ • Dual Reconciliation      │  │
│  └─────────────────────────┘                └────────────────────────────┘  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│           CỔNG PHÊ DUYỆT CON NGƯỜI (HUMAN-IN-THE-LOOP APPROVAL GATE)        │
│    • Quản lý thẩm định qua bảng cờ cảnh báo rủi ro (Green / Yellow / Red)   │
│    • Ký số xác thực cục bộ Ed25519 (RFC 8032) & Đóng băng Snapshot          │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│               XUẤT BẢN FILE BÁO GIÁ PDF CÓ MÃ QR KIỂM THỰC ĐỘC LẬP          │
│        (Khách hàng quét mã QR đối soát toàn vẹn dữ liệu trong 1 giây)       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Bốn Trụ cột Công nghệ Khác biệt
1. **Tách biệt Triệt để Giữa Nhận thức và Tính toán (Separation of Concerns):**  
   - LLM chỉ chịu trách nhiệm đọc hiểu văn bản chính sách, ánh xạ điều kiện khách hàng và phát hiện xung đột.  
   - Toàn bộ phép tính tài chính được ủy quyền cho **Deterministic Calculation Engine** viết bằng Python với module `decimal.Decimal` (độ chính xác 28 chữ số, 0-float), đảm bảo **sai số tuyệt đối $\Delta = 0$ VNĐ**.
2. **Quản trị Phiên bản Chính sách theo Trục Thời gian (Time-travel Versioning):**  
   - Tự động áp dụng đúng chính sách có hiệu lực tại ngày giao dịch; PostgreSQL Exclusion Constraint (`btree_gist`) ngăn chặn hoàn toàn việc tồn tại hai chính sách chồng lấn thời gian trong cùng một phân khúc.
3. **Phát hiện Xung đột & Từ chối Thông minh (Conflict Detection & Safe Abstention):**  
   - Ma trận xung đột 3 cấp độ (Phương án, Nhóm chính sách, Cộng dồn).  
   - Khi phát hiện chính sách mập mờ, chồng chéo hoặc thiếu cơ sở dữ liệu, Agent chủ động dừng lại ở trạng thái `CONFLICT / NEEDS_INPUT` thay vì tự suy đoán bừa bãi.
4. **Cổng Phê duyệt Hai người Bắt buộc (HITL Gate & Digital Signing):**  
   - Tuân thủ nguyên tắc SoD (*Separation of Duties*: người tạo không thể tự duyệt). Báo giá chỉ được xuất PDF khi có chữ ký số xác thực của Sales Manager qua thuật toán Ed25519.

---

# 3. VAI TRÒ NGƯỜI DÙNG & TRẢI NGHIỆM TỔNG QUAN (PERSONAS & WORKFLOW)

| Vai trò Người dùng | Trách nhiệm Chính | Giá trị Nhận được |
| :--- | :--- | :--- |
| **Sales Executive** *(Nhân viên Kinh doanh)* | Nhập thông tin căn hộ, hồ sơ khách hàng, chọn tiêu chí tối ưu hóa; nhận tư vấn từ Agent và trình ký báo giá. | Giảm thời gian tính toán từ 90 phút xuống **dưới 10 giây**; có bảng so sánh trực quan 3 phương án và lý lẽ giải trình vững chắc cho khách hàng. |
| **Sales Manager** *(Quản lý Kinh doanh)* | Thẩm định các báo giá do Sales trình duyệt qua hệ thống cảnh báo cờ rủi ro; ký số phê duyệt hoặc từ chối yêu cầu sửa. | Duyệt hồ sơ trong **dưới 30 giây**; loại bỏ 100% rủi ro thất thoát chiết khấu và gian lận nội bộ. |
| **Policy Administrator** *(Quản trị viên Chính sách)* | Tải lên văn bản chính sách bán hàng mới, quản lý thời hạn hiệu lực, thiết lập ma trận xung đột và giám sát audit log. | Số hóa chính sách tức thì, kiểm soát phiên bản tập trung toàn hệ thống. |
| **Khách hàng Mua nhà** *(End Customer / Stakeholder)* | Nhận bản báo giá chính thức, quét mã QR để tra cứu tính pháp lý và toàn vẹn của báo giá. | Yên tâm tuyệt đối về tính minh bạch của giá bán, hiểu rõ lộ trình dòng tiền nộp từng đợt. |

---

# 4. CÁC TÍNH NĂNG CHỦ CHỐT CỦA SẢN PHẨM (CORE CAPABILITIES)

1. **So sánh Đối đầu 3 Kịch bản Chuẩn tắc (Canonical Scenarios):**
   - *Phương án 1 (Tiến độ chuẩn):* Chia 9 đợt giãn theo tiến độ xây dựng, cấn trừ cọc Đợt 1, thanh toán 20% + 100% KPBT khi nhận nhà.
   - *Phương án 2 (Thanh toán sớm 95%):* Chiết khấu tối đa khi thanh toán nhanh trong 15–30 ngày.
   - *Phương án 3 (Vay ngân hàng HTLS 0%):* Vốn tự có 30% + Ngân hàng giải ngân 70%, áp dụng thuật toán **Dual Reconciliation** triệt tiêu sai số 1 đồng ở từng cấu phần.
2. **Xếp hạng Theo 5 Tiêu chí Tối ưu hóa (Optimization Objectives):**
   - `MIN_NET_PRICE`: Giá mua Net trước thuế thấp nhất.
   - `MIN_CONTRACT_PRICE`: Tổng giá trị HĐMB cuối cùng thấp nhất.
   - `MIN_INITIAL_OUTFLOW`: Số tiền mặt nộp Đợt 1 ít nhất (sau khi đã trừ cọc).
   - `MIN_CASH_OUTFLOW_TO_HANDOVER`: Tổng dòng tiền tự chi trả đến khi nhận nhà ít nhất.
   - `MAX_BENEFIT_VALUE`: Tổng giá trị quà tặng và ưu đãi quy đổi lớn nhất.
3. **Cơ chế Minh bạch Giải trình ("Why & Why Not?"):**
   - Mọi khoản chiết khấu đều có trích đoạn điều khoản chính sách đính kèm.
   - Mọi khoản ưu đãi không được áp dụng đều được giải thích nguyên nhân rõ ràng (ví dụ: *Do xung đột với Điều khoản Vay HTLS tại Mục 3.2*).
4. **Hồ sơ Kiểm toán Bất biến (Immutable Evidence Snapshot & Audit Trail):**
   - Lưu trữ bản snapshot độc lập chứa toàn bộ điều khoản áp dụng và mã băm `source_pdf_sha256`.
   - Chuỗi băm Per-Quote Version Hash Chain ngăn chặn mọi hành vi chỉnh sửa cơ sở dữ liệu sau khi duyệt.
5. **Cổng Tra cứu Công khai (Public Verification Portal):**
   - Mỗi file PDF phát hành được gắn một mã QR dẫn tới trang kiểm thực công khai, bảo đảm tài liệu không bị chỉnh sửa photoshop.

---

# 5. NGĂN XẾP CÔNG NGHỆ & MÔ HÌNH TRIỂN KHAI (TECH STACK & DEPLOYMENT)

Thiết kế kiến trúc hệ thống được tinh chỉnh thực tế cho hạ tầng **VPS chuyên dụng (Dedicated VPS)** thông qua **Docker Compose đa container**, đáp ứng tiêu chí **MVP tinh gọn, chịu tải cao, không phụ thuộc dịch vụ đám mây đắt đỏ**:

| Thành phần | Công nghệ Lựa chọn | Vai trò Kỹ thuật |
| :--- | :--- | :--- |
| **Frontend / Web UI** | **Next.js 14 (App Router) + TailwindCSS** | Giao diện điều hành cho Sales & Manager; Streaming SSE thời gian thực. |
| **Ingress Proxy & SSL** | **Caddy 2 (Alpine)** | Tự động cấp phát HTTPS Let's Encrypt; Reverse proxy unbuffered streaming (`flush_interval -1`). |
| **API Backend Core** | **Python FastAPI (Async)** | API Gateway, điều phối luồng LangGraph StateGraph, quản lý xác thực JWT & SoD. |
| **Hardened Pricing Engine** | **Python Isolated Sidecar Container** | Container độc lập không có Internet (`network_mode: none`), giao tiếp qua Unix Domain Socket, tính toán số học 100% `Decimal`. |
| **Vector Engine / RAG** | **Qdrant Vector Database (Rust Core)** | Lưu trữ embeddings điều khoản chính sách; Hybrid search kết hợp Dense Vector và BM25 Payload filtering. |
| **Relational Database** | **PostgreSQL 16 (NVMe Volume)** | Quản lý 14 bảng quan hệ, `btree_gist` Exclusion Constraint, Audit hash chain trigger. |
| **Broker & Outbox Worker** | **Redis 7 + Python ARQ** | Quản lý cache idempotency và tác vụ nền xuất bản PDF không nghẽn luồng. |
| **Chữ ký số & An mật** | **Local Ed25519 Signer (RFC 8032)** | Ký số tài liệu dưới 1ms với khóa riêng tư nạp từ Docker Secret; sinh mã QR kiểm thực. |

---

# 6. KẾ HOẠCH NGIỆM THU & CHỈ SỐ CAM KẾT (BENCHMARKS & ACCEPTANCE)

- **Độ chính xác Số học (Financial Exactness):** Đạt **100% Exact Match** ($\Delta = 0$ VNĐ) trên bộ **15 Golden Test Vectors** đối soát theo tài liệu FCS v2.6.
- **Thời gian Xử lý Tính toán (End-to-End Latency):** Phân tích và tạo bảng so sánh 3 phương án trong thời gian **dưới 6 giây** (P95 $\le 8$ giây).
- **Độ tin cậy Phê duyệt (Approval Safety):** **100%** báo giá gửi ra thị trường phải có chữ ký số của Quản lý; database tự động chặn 100% trường hợp tự tạo tự duyệt.
- **Khả năng Bắt xung đột (Conflict Recall):** Đạt **100%** tỷ lệ nhận diện đối với các kịch bản chồng chéo chính sách trong bộ dữ liệu kiểm thử.

---
*Bản tóm tắt dự án phản ánh đầy đủ năng lực kỹ thuật và giải quyết trọn vẹn bài toán đặt ra theo chuẩn mực cao nhất của Đề thi BDSO2O-06.*
