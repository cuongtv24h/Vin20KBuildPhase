# PricePolicy Architecture Diagram (P-096)

Tài liệu sơ đồ kiến trúc hệ thống phục vụ đánh giá Deliverable #3 của Ban Tổ Chức AI20K.

---

## 1. Sơ Đồ Kiến Trúc Tổng Thể (System Architecture)

```mermaid
graph TB
    subgraph Client["Lớp Giao Diện Người Dùng"]
        User([Khách Hàng / Sale]) --> WebUI[Web Interface<br/>React / Next.js]
    end

    subgraph API_Gateway["Lớp API Gateway"]
        WebUI -->|HTTP / REST| API[FastAPI Backend<br/>/api/v1/chat, /messages/send]
    end

    subgraph Agent_Layer["Lớp Điều Phối Tác Tử (LangGraph)"]
        API --> Orchestrator[Orchestrator StateGraph<br/>C-01: Pre-Sales & Official Quote]
        Orchestrator --> LLM[LLM Service<br/>OpenAI GPT-4o / Fallback Chain]
        Orchestrator --> Tool[Agent Tools<br/>policy_search.py]
    end

    subgraph RAG_Engine["Lớp PEC-RAG & Evidence Engine"]
        Tool --> RAGFacade[PolicyRAGService Facade<br/>src/services/rag/]
        RAGFacade --> Temporal[Time-Travel SQL Filter<br/>C-02: 0% Time Leakage]
        Temporal --> DualPol[Dual-Polarity Retrieval<br/>Why vs Why-Not]
        DualPol --> TDEC[1-Hop TDEC Closure<br/>C-04: Footnotes & Exclusions]
        TDEC --> Verifier[Evidence Verifier & Linker<br/>C-04: 5 Invariant Checks N-14B]
    end

    subgraph Sidecar["Lớp Tính Toán Tài Chính Tất Định"]
        Verifier -->|Verified EvidenceBundle| PricingSidecar[Pricing Engine Sidecar<br/>C-06: 6 Sanity Checks & Optimization]
        PricingSidecar --> Gate[Compliance Gate C-11<br/>POL-08 Speech Standards]
    end

    subgraph Storage["Lớp Lưu Trữ Bền Vững"]
        Temporal <--> DB[(PostgreSQL + pgvector<br/>Supabase HNSW dims=1536)]
        Gate --> Audit[(Append-Only Audit Trail<br/>C-07: Hash Chain)]
    end

    Gate -->|Certified Response + Anchors| API
```

---

## 2. Sơ Đồ Luồng Tác Tử LangGraph (Agent StateGraph Flow)

```mermaid
graph LR
    START((Khởi Đầu)) --> Ingest[Nhận Yêu Cầu & Bóc Tách Thực Thể]
    Ingest --> CheckIntent{Mục Đích Yêu Cầu?}
    
    CheckIntent -->|Tra Cứu Chính Sách| SearchTool[Gọi Tool search_policy]
    SearchTool --> RAG_Eval[PEC-RAG + 1-Hop TDEC]
    RAG_Eval --> VerifyDecision{Xác Thực Bằng Chứng?}
    
    VerifyDecision -->|Có footnote chưa rõ / Hết hạn| AbstainNode[Sinh AbstentionCertificate<br/>Từ Chối An Toàn]
    VerifyDecision -->|Hợp lệ toàn vẹn| BundleNode[Phát Hành EvidenceBundle<br/>Mỏ Neo SHA-256]
    
    BundleNode --> PricingNode[Tính Toán Bảng Giá & Chiết Khấu Tất Định]
    PricingNode --> ComplianceNode[Kiểm Soát Phát Ngôn POL-08]
    
    ComplianceNode --> FinalResponse[Tạo Phản Hồi Minh Bạch Kèm Mỏ Neo]
    AbstainNode --> FinalResponse
    FinalResponse --> END((Kết Thúc))
```

---

## 3. Bảng Thành Phần Công Nghệ & Vai Trò (Component Tech Stack)

| Thành phần | Công nghệ | Vai trò & Mục đích | Trạng thái |
| :--- | :--- | :--- | :---: |
| **Frontend** | React / Next.js / TailwindCSS | Giao diện tư vấn khách hàng và bảng điều khiển sale | ✅ Hoàn thiện |
| **Backend** | FastAPI / Pydantic v2 | API Gateway và xử lý luồng dữ liệu thời gian thực | ✅ Hoàn thiện |
| **Orchestrator** | LangGraph / StateGraph | Điều phối trạng thái tác tử Pre-Sales & Official Quote | ✅ Hoàn thiện |
| **RAG Core** | PEC-RAG / Dual-Polarity | Tìm kiếm ngữ nghĩa kết hợp lọc ngày hiệu lực cứng | ✅ Hoàn thiện |
| **Evidence Engine** | 1-Hop TDEC / SHA-256 Linker | Đóng gói chứng cứ và kiểm chứng 5 bất biến N-14B | ✅ Hoàn thiện |
| **Compliance Gate** | 3-Checkpoint $\times$ 4-Tier | Giám sát phát ngôn tuân thủ quy chuẩn POL-08 | ✅ Hoàn thiện |
| **Vector Database** | PostgreSQL + pgvector HNSW | Lưu trữ nhúng 1536 chiều, độ trễ truy xuất < 2.5ms | ✅ Hoàn thiện |
