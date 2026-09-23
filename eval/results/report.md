# Evaluation Report

> Báo cáo đánh giá chất lượng sản phẩm theo tiêu chí BTC.

---

## 1. RAG Core & Retrieval Metrics

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| **Time-Travel Leakage** | 0.0% | **0.00%** | ✅ Passed |
| **Clause-Level Recall@k** | 100.0% | **100.00%** | ✅ Passed |
| **Conflict Completeness** | 100.0% | **100.00%** | ✅ Passed |
| **Cryptographic Integrity** | 100.0% | **100.00%** | ✅ Passed |
| **Retrieval Latency (p95)** | < 300 ms | **5.76 ms** | ✅ Passed |
| **Retrieval Latency (Mean)** | < 100 ms | **4.78 ms** | ✅ Passed |

---

## 2. Test Results

### Automated Unit & Integration Tests (Pytest)
```
tests/test_agents/test_graph.py::test_agent_basic_flow PASSED
tests/test_agents/test_graph.py::test_agent_state_structure PASSED
tests/test_api/test_routes.py::test_health PASSED
tests/test_api/test_routes.py::test_chat_empty_message PASSED
tests/test_api/test_routes.py::test_agent_status PASSED
tests/test_rag/test_end_to_end_rag.py::test_end_to_end_rag_with_real_dataset PASSED
tests/test_rag/test_evidence_binder.py::test_evidence_binding_and_integrity_check PASSED
tests/test_rag/test_hierarchical_parser.py::test_parse_articles_and_clauses PASSED
tests/test_rag/test_hierarchical_parser.py::test_line_spans_and_sha256 PASSED
tests/test_rag/test_mutual_exclusion_pruner.py::test_hard_exclusion_pruning PASSED
tests/test_rag/test_mutual_exclusion_pruner.py::test_conditional_and_ambiguous_pruning PASSED
tests/test_rag/test_time_travel_retriever.py::test_time_travel_filters PASSED

============================== 12 passed in 0.91s ==============================
```

### RAG Evaluation Benchmark Scenarios
- **Golden Scenarios Tested:** 10 scenarios (Standard, VIP, Priority, Corporate, International transfer, Holiday promotions, Inactive/Expired policies, Ambiguous exclusions, Cross-channel mobile vs counter).
- **Time-Travel Verification:** 0% rò rỉ trên các ngày hiệu lực quá khứ/tương lai và chính sách đã hết hạn.
- **Mutual Exclusion Pruning:** Xử lý và loại trừ xung đột chính sách chính xác theo quy tắc ưu tiên nghiệp vụ.
- **Cryptographic Binding:** 100% chunks truy xuất được xác thực toàn vẹn bằng SHA-256 đối chiếu line spans gốc.

---

## 3. Action Items

- [x] Triển khai Hierarchical Ingestion Parser & Metadata Enrichment
- [x] Triển khai Time-Travel Retriever & Temporal Validation
- [x] Triển khai 3-tier Mutual Exclusion Pruning
- [x] Triển khai Cryptographic Evidence Binder (SHA-256 coordinate mapping)
- [x] Xây dựng bộ đo lường & Evaluation Suite cho RAG
- [ ] Tích hợp Deterministic Fee Calculator
- [ ] Hoàn thiện LangGraph Workflow State & Audit Node
