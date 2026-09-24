from fastapi import APIRouter, HTTPException
from src.models.pec_contracts import PricingRequest

router = APIRouter()

@router.post("/calculate")
async def calculate_pricing(request: PricingRequest):
    """
    Mock Pricing API.
    Nhiệm vụ: Chặn đứng bất kỳ payload nào không phải là Verified EvidenceBundle.
    """
    bundle_ref = request.evidence_bundle_ref
    
    # 1. Reject if bundle is NOT verified
    if bundle_ref.decision_status != "VERIFIED":
        raise HTTPException(
            status_code=400, 
            detail="Pricing Engine rejected: Evidence Bundle is not VERIFIED. Refusing to calculate."
        )
    
    # 2. Reject if hash is invalid or missing
    if not bundle_ref.bundle_hash.startswith("sha256:"):
        raise HTTPException(
            status_code=400,
            detail="Pricing Engine rejected: Invalid or missing bundle hash format."
        )
        
    # Trong môi trường thực tế, Pricing sẽ:
    # 1. Gọi Redis/S3 lấy EvidenceBundle gốc bằng bundle_hash
    # 2. Check policy_snapshot_hash
    # 3. Chạy deterministic engine.
    
    return {
        "status": "success",
        "message": "Pricing calculated successfully based on VERIFIED policy evidence.",
        "used_snapshot": bundle_ref.resolved_policy_snapshot_hash
    }
