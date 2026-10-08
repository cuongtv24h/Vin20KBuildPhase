from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "AI20K Agent"
    app_env: Literal["development", "production", "test"] = "development"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_host: str = "0.0.0.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    cors_origins: str = "http://localhost:3000,http://localhost:5173,http://localhost:5174"

    #: Khoá mã hoá API key của nhà cung cấp LLM (`src/services/llm_secrets.py`).
    #: Nhận cả `LLM_SECRET_KEY` và `SECRET_KEY`. Đặt trong `.env` là đủ — không cần export ra shell,
    #: vì giá trị trong `.env` chỉ được pydantic-settings nạp vào Settings, KHÔNG tự vào `os.environ`.
    llm_secret_key: str = Field(
        default="",
        validation_alias=AliasChoices("llm_secret_key", "LLM_SECRET_KEY", "SECRET_KEY"),
    )

    #: Chế độ header HTTP khi gọi nhà cung cấp LLM (xem `src/services/llm_http.py`):
    #: `app` = khai báo tên ứng dụng; `browser` = thêm bộ header kiểu trình duyệt, dùng khi nhà cung
    #: cấp đứng sau Cloudflare chặn challenge. Có thể đặt bằng biến môi trường `LLM_HTTP_HEADERS`.
    llm_http_headers: Literal["app", "browser"] = "app"

    # Primary LLM
    openai_api_key: str = ""
    openai_base_url: str | None = None
    model_name: str = "gpt-4o-mini"
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    llm_max_retries: int = Field(default=1, ge=0, le=10)

    # Text-to-Speech (đọc câu trả lời Copilot) — giá trị khởi tạo từ ENV,
    # thiết lập trong DB/UI sẽ đè lên khi có.
    tts_provider: str = ""
    tts_model: str = ""
    tts_voice: str = ""
    tts_speed: float = 1.0
    tts_enabled: bool = True
    tts_auto_speak: bool = False
    tts_max_chars_per_turn: int = 600
    #: Hạn mức ký tự gửi đi đọc **mỗi ngày** cho đường trả phí (0 = không giới hạn).
    #: Mặc định 300.000 ký tự/ngày ≈ 9.000 ký tự/ngày/nhân viên với ~30 người — đủ dùng thật, vẫn chặn
    #: được trường hợp một phiên bị lặp đọc cả câu trả lời dài hàng nghìn lần.
    tts_daily_char_budget: int = 300_000
    #: Cache audio trên đĩa: TTL (ngày) và trần dung lượng (MB).
    tts_cache_ttl_days: int = 7
    tts_cache_max_mb: int = 200
    #: Khoá của các nhà cung cấp TTS không dùng chung OPENAI_API_KEY.
    google_application_credentials: str = ""
    azure_speech_key: str = ""
    azure_speech_region: str = "southeastasia"
    viettel_tts_token: str = ""
    vbee_token: str = ""
    fpt_tts_api_key: str = ""

    # ---- Speech-to-Text (Sale NÓI -> chữ cho Copilot) — DB đè ENV, cùng cơ chế với TTS ----
    #: `groq` (Whisper trên LPU, có gói free không cần thẻ) | `openai` (whisper-1) | `browser` (Web Speech API).
    stt_provider: str = "groq"
    stt_enabled: bool = True
    #: Khoá Groq RIÊNG cho nghe-nói — tách khỏi `OPENAI_API_KEY` đang chạy LLM: hết hạn mức STT thì
    #: Copilot vẫn sống, và ngược lại (người dùng chốt 2026-10-08: "khai báo riêng 1 key Groq").
    stt_groq_api_key: str = ""
    stt_groq_base_url: str = "https://api.groq.com/openai/v1"
    #: `whisper-large-v3-turbo` (nhanh, 0,04 USD/giờ) hoặc `whisper-large-v3` (tiếng Việt chính xác hơn, 0,111 USD/giờ).
    stt_model: str = "whisper-large-v3-turbo"
    #: Nhà cung cấp `openai` dùng lại khoá LLM sẵn có, chỉ model khai báo riêng.
    stt_openai_model: str = "whisper-1"
    stt_language: str = "vi"
    #: Từ vựng MỒI cho Whisper (không phải lệnh hệ thống, không chứa dữ liệu khách): tên dự án, mã căn,
    #: thuật ngữ chính sách — thiếu nó thì "ZEN-A-1205" hay ra "ZEN A 1205" và Copilot tra sai căn.
    stt_prompt: str = (
        "The Zen Park, VLand Future Riverside, VLand Future Sapphire, ZEN-A-1205, ZEN-A-0803, "
        "KPBT, VAT, GPMB, ân hạn, chiết khấu, vốn tự có, báo giá, hồ sơ đề xuất, quản lý kinh doanh"
    )
    #: Hạn mức số PHÚT audio/ngày cho đường trả phí (0 = không giới hạn). Groq free: 2.000 request/ngày,
    #: 8 giờ audio/ngày — đặt thấp hơn trần để không ăn 429 giữa demo.
    stt_daily_minutes_budget: int = 60
    #: Trần phía frontend (máy chủ không giải mã audio nên chặn theo dung lượng là chính).
    stt_max_duration_seconds: int = 120
    stt_max_bytes: int = 10_000_000
    stt_request_timeout_seconds: float = 30.0
    #: CAM KẾT VẬN HÀNH, không phải công tắc kỹ thuật: Groq không có tham số ZDR theo request — ADMIN bật
    #: Zero Data Retention trong Groq Console -> Data Controls rồi khai báo lại ở đây để `/stt/health` hết cảnh báo.
    stt_zero_data_retention: bool = False

    # Fallback LLM 1
    fallback_openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("fallback_openai_api_key", "fallback1_openai_api_key"),
    )
    fallback_openai_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("fallback_openai_base_url", "fallback1_openai_base_url"),
    )
    fallback_model_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("fallback_model_name", "fallback1_model_name"),
    )

    # Fallback LLM 2
    fallback2_openai_api_key: str | None = None
    fallback2_openai_base_url: str | None = None
    fallback2_model_name: str | None = None

    # Database
    database_url: str = "sqlite:///./data/app.db"

    #: Fallback DNS cho Supabase pooler khi mạng nội bộ chặn phân giải (`src/db/dns_patch.py`).
    #: Mặc định BẬT để không đổi hành vi deploy hiện tại; đặt `DB_DNS_FALLBACK=false` khi DNS thông suốt.
    #: Patch chỉ thực sự kích hoạt nếu `DATABASE_URL` trỏ tới Supabase.
    db_dns_fallback: bool = True

    # LangGraph persistent checkpointing (INV-RT-04 — Spike 2)
    checkpoint_db_uri: str | None = None
    use_postgres_checkpointer: bool = False

    # Vector Store & Local Embeddings
    chroma_persist_dir: str = "./data/chroma"
    pg_table_name: str = "policy_atoms"
    embedding_model_id: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384
    reranker_model_id: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    reranker_enabled: bool = True
    reranker_top_k: int = 5
    hybrid_search_enabled: bool = True
    coarse_top_k: int = 30

    # Pricing Sidecar (Component C-06)
    pricing_sidecar_socket: str = "./data/pricing.sock"
    pricing_sidecar_host: str = "127.0.0.1"
    pricing_sidecar_port: int = 28001
    pricing_use_mock: bool = False
    pricing_fallback_to_direct: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
