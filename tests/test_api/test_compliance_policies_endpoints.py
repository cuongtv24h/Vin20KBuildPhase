"""Tests for Compliance Gate and Policy Management Endpoints."""

from fastapi.testclient import TestClient

from src.api.deps import create_access_token
from src.main import app

client = TestClient(app)

# Cổng kiểm thử/ban hành chính sách là nghiệp vụ POLICY_ADMIN (đồng bộ với mock server).
POLICY_ADMIN_HEADERS = {
    "Authorization": f"Bearer {create_access_token('minh.tuan@vlandfuture.vn', 'POLICY_ADMIN')}",
}


def test_compliance_check_message_supported():
    payload = {
        "message": "Căn hộ được áp dụng chiết khấu 8% theo chính sách đã ban hành.",
        "mode": "ON_DRAFT",
        "policy_version_refs": ["POL-002:v1"],
    }
    response = client.post("/api/v1/compliance/check-message", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["overall_status"] == "SUPPORTED"
    assert "message_hash" in data
    assert data["message_hash"].startswith("sha256:")


def test_compliance_check_message_prohibited():
    payload = {
        "message": "Dự án này cam kết chắc chắn sinh lời 15% mỗi năm không rủi ro!",
        "mode": "FINAL_SEND",
    }
    response = client.post("/api/v1/compliance/check-message", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["overall_status"] == "PROHIBITED"
    assert data["required_action"] == "BLOCK_MESSAGE_COMPLIANCE_VIOLATION"


def test_messages_send_blocked_when_prohibited():
    payload = {
        "message": "Cam kết chắc chắn sinh lời 20% trong 2 năm!",
        "recipient": "0901234567",
    }
    response = client.post("/api/v1/messages/send", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert data["detail"]["error"] == "COMPLIANCE_GATE_BLOCKED"
    assert data["detail"]["overall_status"] == "PROHIBITED"


def test_messages_send_success():
    payload = {
        "message": "Kính gửi quý khách thông tin chính sách bán hàng của dự án.",
        "recipient": "0901234567",
        "policy_version_refs": ["POL-001:v1"],
    }
    response = client.post("/api/v1/messages/send", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SENT"
    assert data["message_id"].startswith("MSG-")
    assert "sent_at" in data


def test_extract_rules_endpoint():
    md = """# Chính sách POL-01
## Điều 1. Phạm vi áp dụng
Chính sách này áp dụng cho toàn bộ phân khu Ruby.

## Điều 2. Chiết khấu thanh toán
Khách hàng thanh toán sớm được hưởng chiết khấu 7% trên giá bán chưa VAT.
"""
    payload = {
        "policy_id": "POL-01",
        "policy_name": "Chính sách Ruby",
        "markdown_content": md,
        "valid_from": "2026-01-01",
        "valid_to": "2026-12-31",
    }
    response = client.post("/api/v1/policies/extract-rules", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["policy_id"] == "POL-01"
    assert data["total_atoms"] >= 2
    assert data["status"] == "EXTRACTED_PENDING_REVIEW"


def test_policy_rules_test_endpoint():
    payload = {
        "policy_id": "POL-01",
        "test_queries": ["Chiết khấu thanh toán sớm"],
    }
    response = client.post("/api/v1/policies/rules/test", json=payload, headers=POLICY_ADMIN_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["passed"] is True
    assert data["recommendation"] == "READY_TO_PUBLISH"


def test_policy_publish_endpoint():
    payload = {
        "policy_id": "POL-01",
        "version": "v1.2",
        "published_by": "tranchivi@vlandfuture.vn",
    }
    response = client.post("/api/v1/policies/publish", json=payload, headers=POLICY_ADMIN_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "APPROVED_FOR_USE"
    assert data["snapshot_hash"].startswith("sha256:")


def test_rules_test_runs_real_formula_regression_gate():
    """Cổng kiểm thử phải chạy 17 ca golden thật và trả đủ contract của frontend."""
    payload = {"policy_id": "POL-GATE-01", "version": "v1.0", "test_queries": ["Chiết khấu thanh toán sớm 8%"]}
    response = client.post("/api/v1/policies/rules/test", json=payload, headers=POLICY_ADMIN_HEADERS)
    assert response.status_code == 200
    data = response.json()

    # Contract RulesTestReport mà PolicyDetailPage đọc
    assert data["checked_at"]
    assert data["regression"] == {"passed": 17, "total": 17}
    assert data["can_publish"] is True
    assert data["policy_alignment"] == "DRIFT"  # văn bản mới chưa có bộ ca vàng riêng
    assert data["benchmark_run_id"].startswith("BENCH-RUN-")

    codes = {c["code"]: c for c in data["checks"]}
    assert codes["FORMULA_REGRESSION"]["status"] == "PASS"
    assert "17/17" in codes["FORMULA_REGRESSION"]["detail"]
    assert codes["GOLDEN_ALIGNMENT"]["status"] == "WARN"
    assert data["conflicts_detected"] == []


def test_publish_gate_blocks_unknown_policy_when_already_published():
    """Ban hành lần hai cùng phiên bản bị cổng kiểm thử chặn (tránh ghi đè bản đang hiệu lực)."""
    payload = {"policy_id": "POL-01", "version": "v1.2", "published_by": "tranchivi@vlandfuture.vn"}
    response = client.post("/api/v1/policies/publish", json=payload, headers=POLICY_ADMIN_HEADERS)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "POLICY_TEST_GATE_FAILED"
    assert any("ALREADY_PUBLISHED" in c for c in response.json()["detail"]["conflicts"])


def test_publish_requires_policy_admin_role():
    payload = {"policy_id": "POL-ROLE-01", "version": "v1.0", "published_by": "someone@vlandfuture.vn"}
    response = client.post("/api/v1/policies/publish", json=payload)
    assert response.status_code == 403
