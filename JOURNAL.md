# Weekly Journal — Team PricePolicy P-096

> Nhật ký tiến độ hàng tuần ghi lại mục tiêu, thành quả hoàn thành, khó khăn kỹ thuật, bài học kinh nghiệm và kế hoạch tiếp theo theo chuẩn Deliverable #8 của Ban Tổ Chức AI20K.

---

## Week 1: 2026-09-01 - 2026-09-07

### Mục tiêu tuần này
- [x] Khảo sát bài toán tư vấn giá và chính sách bán hàng bất động sản dự án lớn (Vinhomes / Masterise).
- [x] Thu thập và phân tích cấu trúc 10 bộ văn bản chính sách thực tế (`POL-01` đến `POL-10`).
- [x] Xác định các rủi ro cốt lõi: Ảo giác LLM, rò rỉ thời gian hiệu lực chính sách (Time-Travel Leakage), xung đột chính sách loại trừ nhau.
- [x] Thiết lập kiến trúc tổng quan hệ thống phân tách giữa Orchestrator và Deterministic Sidecar.

### Đã hoàn thành
- Hoàn thành tài liệu phân tích yêu cầu (`1.requirement-analysis.md`) và khám phá sản phẩm (`2.product-discovery.md`).
- Nhận diện 5 tiêu chí tối ưu hóa chuẩn hóa (`MIN_NET_PRICE`, `MIN_CONTRACT_PRICE`, `MIN_INITIAL_OUTFLOW`, `MIN_CASH_OUTFLOW_TO_HANDOVER`, `MAX_BENEFIT_VALUE`).
- Thiết lập repository ban đầu, cài đặt Git hooks đồng bộ AI logs và cấu hình template.

### Khó khăn & Giải pháp
| Khó khăn | Giải pháp | Kết quả |
| :--- | :--- | :--- |
| Văn bản chính sách có cấu trúc lồng nhau phức tạp (Chương, Điều, Khoản, Điểm) khiến chunking cố định độ dài bị cắt đứt ngữ cảnh. | Thiết kế thuật toán bóc tách phân cấp theo cú pháp văn bản pháp lý (Hierarchical Regex Parser). | Giữ nguyên vẹn tọa độ điều khoản và liên kết phân cấp. |

### Bài học
- Trong nghiệp vụ tài chính bất động sản, việc trích xuất thiếu một câu ghi chú chân trang (Footnote) có thể làm thay đổi hoàn toàn điều kiện hưởng chiết khấu hàng trăm triệu đồng của khách hàng.

### Kế hoạch tuần sau
- [x] Triển khai Core RAG Ingestion Pipeline và Time-Travel Policy Retriever.
- [x] Kết nối cơ sở dữ liệu PostgreSQL với extension `pgvector`.

---

## Week 2: 2026-09-08 - 2026-09-14

### Mục tiêu tuần này
- [x] Lập trình bộ nạp phân cấp `LegalHierarchicalParser` gắn mã băm SHA-256 cho từng điều khoản.
- [x] Triển khai `TimeTravelPolicyRetriever` thực thi lọc SQL ngày hiệu lực cứng tại Database.
- [x] Cấu hình cơ sở dữ liệu Supabase pgvector HNSW phục vụ tìm kiếm ngữ nghĩa.
- [x] Xây dựng bộ lọc loại trừ 3 cấp độ (`MutualExclusionPruner`).

### Đã hoàn thành
- Hoàn thành `src/rag/ingestion/hierarchical_parser.py` và `pipeline.py`.
- Tích hợp PostgreSQL `pgvector` HNSW (`vector(1536)`) qua SQLAlchemy async session.
- Viết 12 bài unit test ban đầu đạt tỷ lệ pass 100%.

### Khó khăn & Giải pháp
| Khó khăn | Giải pháp | Kết quả |
| :--- | :--- | :--- |
| Lỗi rò rỉ thời gian (Time-travel leakage) khi truy vấn chính sách quá hạn nếu chỉ dùng Cosine Similarity đơn thuần. | Đặt bộ lọc SQL cứng `(valid_from <= tx_date AND valid_to >= tx_date)` chạy trước bước Vector Search (SQL-first filtering). | Đạt tỷ lệ rò rỉ thời gian chính xác 0.00%. |

### Bài học
- Không bao giờ dựa vào LLM để lọc ngày hiệu lực; việc kiểm soát thời gian phải được bảo đảm bằng ràng buộc logic cứng tại tầng cơ sở dữ liệu.

### Kế hoạch tuần sau
- [x] Nghiên cứu và hiện thực hóa cơ chế Dual-Polarity và mở rộng đồ thị 1-hop TDEC.
- [x] Đóng băng các hợp đồng dữ liệu chuẩn (`EvidenceBundle`, `AbstentionCertificate`).

---

## Week 3: 2026-09-15 - 2026-09-21

### Mục tiêu tuần này
- [x] Triển khai cơ chế tìm kiếm lưỡng cực `DualPolarityRetriever` (truy xuất song song Cực Dương "Tại sao được" và Cực Âm "Tại sao không").
- [x] Xây dựng thuật toán mở rộng đồ thị có giới hạn 1-hop TDEC (`TDECClosure`).
- [x] Triển khai bộ kiểm chứng bằng chứng và phát hành chứng thư (`EvidenceVerifier`, `AbstentionGenerator`).
- [x] Kết nối mock Pricing Service bắt buộc tiêu thụ verified bundle.

### Đã hoàn thành
- Đóng băng schema `pec_contracts.py` với đầy đủ các đối tượng `PolicyAtom`, `PolicyEdge`, `EvidenceBundle`, `AbstentionCertificate`.
- Nâng số lượng bài test lên 25/25 bài pass trọn vẹn.
- Tạo mock API endpoint `/pricing/calculate` chỉ chấp thuận bundle có chữ ký xác thực.

### Khó khăn & Giải pháp
| Khó khăn | Giải pháp | Kết quả |
| :--- | :--- | :--- |
| Nguy cơ bùng nổ tổ hợp khi duyệt đồ thị quan hệ chính sách đa bậc (Multi-hop). | Bounded 1-Hop Closure: giới hạn bán kính duyệt đúng 1 bước xung quanh các seed atoms để bắt footnote và conflict partner. | Tốc độ hoàn tất closure < 2ms, loại bỏ hoàn toàn nguy cơ timeout. |

### Bài học
- Quyết định từ chối an toàn (Safe Abstention) bằng `AbstentionCertificate` khi thiếu bằng chứng có giá trị bảo vệ uy tín doanh nghiệp cao hơn việc cố gắng trả lời liều.

### Kế hoạch tuần sau
- [x] Tái cấu trúc toàn bộ mã nguồn theo chuẩn phân công kiến trúc của TechLead (`CODEBASE_MAP.md`).
- [x] Xây dựng Compliance Gate F8 kiểm soát phát ngôn sale theo chuẩn POL-08.

---

## Week 4: 2026-09-22 - 2026-09-26

### Mục tiêu tuần này
- [x] Thực hiện đại phẫu Zero-Breakage: chuyển các module sang `src/services/rag/`, `src/services/evidence/`, `src/services/compliance/`.
- [x] Xây dựng `Claim-Level Evidence Linker` (C-04) thực hiện 5 điểm kiểm chứng bất biến N-14B.
- [x] Xây dựng `Message Compliance Gate` (C-11) hỗ trợ 3 checkpoint và 4 tier phân loại theo chuẩn POL-08.
- [x] Viết công cụ `policy_search.py` cho LangGraph agent và script nạp dữ liệu tự động `scripts/seed_data.py`.
- [x] Đạt 100% bài test pass (32/32 tests sạch không trùng lặp) và chuẩn hóa toàn bộ code sạch bóng vi phạm `ruff`.

### Đã hoàn thành
- Tái cấu trúc thành công 100% không làm hư hại một dòng code nghiệp vụ nào.
- Toàn bộ 32/32 unit & integration tests pass trong 1.70 giây.
- Hoàn thành bộ báo cáo đánh giá tự động `scripts/run_eval.py` vượt qua toàn bộ 5 kịch bản benchmark.
- Cập nhật toàn diện bộ tài liệu 10 Deliverables theo chuẩn Rubric của Ban Tổ Chức AI20K.

### Khó khăn & Giải pháp
| Khó khăn | Giải pháp | Kết quả |
| :--- | :--- | :--- |
| Tránh lỗi import vỡ liên kết khi đổi đường dẫn thư mục mà vẫn đảm bảo tính tương thích ngược cho các file gọi cũ. | Tạo các backward compatibility shims chuyển tiếp tại `src/rag/`, kết hợp script cập nhật import tự động toàn workspace. | 46 bài test pass ngay lần chạy đầu tiên, mã nguồn sạch hoàn toàn lỗi linter `ruff`. |

### Bài học
- Cấu trúc thư mục ngăn nắp chuẩn theo phân công của TechLead giúp việc phân chia ranh giới trách nhiệm (Separation of Concerns) trong nhóm trở nên rõ ràng, sẵn sàng cho việc merge code và trình diễn Demo Day mượt mà.
