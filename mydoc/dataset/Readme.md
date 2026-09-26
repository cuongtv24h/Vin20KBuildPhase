mydoc/dataset/
├── canonical/                         # [Dữ liệu Nguồn Chuẩn hóa - JSON Ground Truth]
│   ├── projects.json                  # Thông tin dự án mẫu VLand Future Riverside (40 căn, 3 phân khu)
│   ├── units.json                     # Bảng hàng 40 căn hộ chuẩn (1BR, 2BR, 3BR, Shophouse kèm diện tích & giá)
│   ├── policies.json                  # Metadata 10 chính sách (ID, version, ngày hiệu lực, trạng thái)
│   └── mutual_exclusions.json         # Ma trận loại trừ xung đột 3 cấp độ (Hard, Conditional, Ambiguous)
│
├── policies_md/                       # [Văn bản Chính sách Sạch cho Chunking & Vector Search]
│   ├── POL-01_bang_gia_chuan.md       # Bảng giá niêm yết, VAT 10%, KPBT 2%, quy định đặt cọc
│   ├── POL-02_chiet_khau_thanh_toan_som.md # Chiết khấu 8% thanh toán sớm 95%
│   ├── POL-03_ho_tro_lai_suat_ngan_hang.md # HTLS 0% trong 24 tháng, ân hạn nợ gốc, vốn tự có 30%
│   ├── POL-04_thanh_toan_gian_tien_do.md   # Tiến độ chuẩn 9 đợt, chiết khấu 2%
│   ├── POL-05_qua_tang_noi_that.md    # Gói quà nội thất 200tr cho căn 3BR (quy đổi 100tr nếu trả sớm)
│   ├── POL-06_tri_an_khach_hang_cu.md # Chiết khấu 1% cho khách hàng cũ / người thân
│   ├── POL-07_chinh_sach_ngoai_le_vip.md   # Quy chế phê duyệt ngoại lệ VIP (Dùng cho Safe Abstention)
│   ├── POL-08_huong_dan_phat_ngon_sale.md  # Quy chuẩn phát ngôn, danh mục cấm cho F8 Compliance Gate
│   ├── POL-09_thay_the_chinh_sach_cu.md    # Chính sách 2025 hết hạn (Dùng để test Time-Travel RAG)
│   └── POL-10_phu_luc_dieu_kien_phap_ly.md # Bảng điều kiện hưởng ưu đãi dạng Markdown Table
│
├── fixtures/                          # [Fixtures Kiểm thử Tự động & Demo Kịch bản Agent]
│   ├── pre_sales_personas.json        # 4 chân dung khách hàng (Gia đình trẻ, Nhà đầu tư, Đa thế hệ, Thiếu ngân sách)
│   ├── golden_scenarios.json          # Test cases chuẩn kế toán đối soát sai số Δ = 0 VNĐ (Exact Match)
│   └── compliance_messages.json       # 4 mẫu tin nhắn kiểm thử F8 (SUPPORTED, CONDITIONAL, UNSUPPORTED, PROHIBITED)
│
└── showcase_documents/                # [Tài liệu Mô phỏng phục vụ Demo thao tác Upload trên Web UI]
    ├── BangGia_VLand_Riverside_2026.csv   # File bảng giá để demo chức năng Import Inventory
    └── ThongBao_ChinhSach_Moi_P09.txt     # Văn bản có mộc để demo nạp chính sách mới & phát hiện xung đột
