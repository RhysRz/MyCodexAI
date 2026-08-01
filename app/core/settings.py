from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str
    debug: bool = False
    environment: Literal["development", "production"] = "development"

    ollama_url: str
    ollama_model: str
    # Normal conversation can use a chat-focused model while Agent mode keeps a
    # coding-focused model. An empty value preserves the legacy single-model setup.
    ollama_chat_model: str = ""
    ollama_api_key: str

    ollama_timeout_seconds: float = 90
    ollama_max_tokens: int = 512
    ollama_chat_temperature: float = Field(default=0.45, ge=0, le=1.5)
    # Keep normal chat responsive on small local machines. Agent mode is
    # unchanged; this only controls models that expose a separate think trace.
    ollama_chat_thinking: bool = False
    # Hugging Face is optional and used by the private, per-account Image Studio.
    # The token is read from the local environment and is never returned by an API.
    hf_token: str = ""
    hf_image_provider: str = "fal-ai"
    hf_image_model: str = "krea/Krea-2-Turbo"
    image_generation_timeout_seconds: float = Field(default=150, ge=20, le=600)
    image_max_output_bytes: int = Field(default=12 * 1024 * 1024, ge=512 * 1024, le=30 * 1024 * 1024)
    image_retention_per_user: int = Field(default=30, ge=1, le=200)
    image_daily_user_limit: int = Field(default=8, ge=0, le=100)
    # Optional local Optical Music Recognition (OMR).  It is intentionally
    # disabled by default: the external score reader is invoked only for a
    # scanned notation PDF and never for normal audio or vector TAB files.
    music_omr_executable: str = ""
    music_omr_timeout_seconds: int = Field(default=300, ge=30, le=900)
    # Optional trusted OCR executable for image-only guitar/bass TAB.  The
    # score controls only image input; it never controls the executable path.
    music_tab_ocr_executable: str = ""
    music_tab_ocr_timeout_seconds: int = Field(default=60, ge=10, le=300)
    # Sample-based playback is rendered only on a user click.  The SoundFont
    # remains local, so remote/mobile clients do not depend on a third party.
    music_fluidsynth_executable: str = "tools/fluidsynth-2.5.7/fluidsynth-v2.5.7-win10-x64-cpp11/bin/fluidsynth.exe"
    music_soundfont_path: str = "assets/soundfonts/GeneralUser-GS.sf2"
    music_render_timeout_seconds: int = Field(default=180, ge=20, le=900)
    # Render only when this much memory is free.  Unlike chat backpressure, an
    # audio render fails safely rather than competing with a resident LLM.
    music_render_min_available_mb: int = Field(default=2048, ge=512, le=65_536)
    # Advanced analysis is opt-in because Demucs and Basic Pitch are sizeable.
    # Cloud runners enable it explicitly; ordinary local startup stays light.
    music_advanced_enabled: bool = False
    music_ffmpeg_executable: str = "ffmpeg"
    music_demucs_model: str = "htdemucs_6s"
    music_demucs_timeout_seconds: int = Field(default=1800, ge=120, le=3600)
    music_basic_pitch_executable: str = ""
    music_basic_pitch_timeout_seconds: int = Field(default=900, ge=60, le=1800)
    music_stem_preview_seconds: int = Field(default=20, ge=5, le=45)
    # These controls change scheduling and resource use only; they do not change
    # the model, sampling parameters, prompt context, or answer quality.
    ollama_inference_threads: int = Field(default=2, ge=1, le=64)
    ollama_max_concurrent_requests: int = Field(default=1, ge=1, le=4)
    # On an 8 GB machine, holding the chat and coding models at the same time
    # causes paging and makes even short replies feel stalled. This only affects
    # how long a completed model stays resident; it never changes model quality.
    ollama_keep_alive_seconds: int = Field(default=20, ge=0, le=3_600)
    # Backpressure only delays a request when the host is already under pressure;
    # it never changes the selected model or generation parameters.
    resource_guard_enabled: bool = True
    # Leave enough memory for one local model and the browser before admitting
    # another inference. The request waits instead of degrading its model.
    resource_guard_min_available_mb: int = Field(default=1536, ge=128, le=65_536)
    resource_guard_max_wait_seconds: int = Field(default=180, ge=0, le=3_600)
    resource_guard_poll_seconds: float = Field(default=3, ge=0.5, le=30)
    workspace_root: str = "workspace"
    agent_state_root: str = ".mycodexai/runs"
    agent_max_concurrent_runs: int = 1
    agent_daily_run_limit: int = Field(default=12, ge=0, le=500)
    agent_daily_step_limit: int = Field(default=240, ge=0, le=20_000)
    agent_audit_retention: int = Field(default=400, ge=50, le=10_000)
    auth_database_path: str = ".mycodexai/auth.db"
    auth_bootstrap_token: str = ""
    auth_cookie_name: str = "mycodexai_session"
    auth_session_days: int = Field(default=1, ge=1, le=30)
    auth_session_idle_minutes: int = Field(default=480, ge=15, le=1_440)
    auth_max_active_sessions: int = Field(default=2, ge=1, le=10)
    auth_login_max_attempts: int = Field(default=5, ge=3, le=20)
    auth_login_window_minutes: int = Field(default=15, ge=1, le=120)
    auth_login_lockout_minutes: int = Field(default=15, ge=1, le=1_440)
    auth_recovery_code_count: int = Field(default=10, ge=5, le=20)
    auth_mfa_encryption_key: str = ""
    auth_require_mfa_for_admin: bool = False
    auth_cookie_secure: bool = True
    oauth_state_ttl_seconds: int = Field(default=600, ge=120, le=3_600)
    oauth_request_timeout_seconds: float = Field(default=10, ge=3, le=30)
    oauth_google_client_id: str = ""
    oauth_google_client_secret: str = ""
    oauth_github_client_id: str = ""
    oauth_github_client_secret: str = ""
    allowed_hosts: str = "localhost,127.0.0.1,testserver"
    public_origin: str = ""
    force_https: bool = False
    hsts_max_age_seconds: int = Field(default=63_072_000, ge=31_536_000)
    max_request_bytes: int = Field(default=110 * 1024 * 1024, ge=1_024 * 1_024, le=500 * 1024 * 1024)
    browser_qa_enabled: bool = True
    browser_qa_executable: str = ""
    browser_qa_timeout_seconds: float = 45
    sandbox_mode: str = "host"
    sandbox_docker_executable: str = ""
    sandbox_docker_image: str = "mycodexai-sandbox:latest"
    sandbox_container_user: str = "sandbox"
    sandbox_allow_network: bool = False
    sandbox_memory_mb: int = 2048
    sandbox_cpus: float = 2
    sandbox_pids_limit: int = 256
    sandbox_browser_executable: str = "/usr/bin/chromium"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def allowed_host_list(self) -> list[str]:
        return [host.strip().casefold() for host in self.allowed_hosts.split(",") if host.strip()]

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if not self.is_production:
            return self

        errors: list[str] = []
        if self.debug:
            errors.append("DEBUG must be false")
        if not self.auth_cookie_secure:
            errors.append("AUTH_COOKIE_SECURE must be true")
        if not self.auth_cookie_name.startswith("__Host-"):
            errors.append("AUTH_COOKIE_NAME must use the __Host- prefix")
        if not self.force_https:
            errors.append("FORCE_HTTPS must be true")
        if self.auth_bootstrap_token:
            errors.append("AUTH_BOOTSTRAP_TOKEN must be empty after the first admin exists")
        if not self.auth_mfa_encryption_key:
            errors.append("AUTH_MFA_ENCRYPTION_KEY must be set")
        if not self.auth_require_mfa_for_admin:
            errors.append("AUTH_REQUIRE_MFA_FOR_ADMIN must be true")
        if bool(self.oauth_google_client_id) != bool(self.oauth_google_client_secret):
            errors.append("OAuth Google client ID and secret must be configured together")
        if bool(self.oauth_github_client_id) != bool(self.oauth_github_client_secret):
            errors.append("OAuth GitHub client ID and secret must be configured together")
        if self.sandbox_mode.casefold() != "docker":
            errors.append("SANDBOX_MODE must be docker")
        if self.sandbox_allow_network:
            errors.append("SANDBOX_ALLOW_NETWORK must be false")
        if self.browser_qa_enabled:
            errors.append("BROWSER_QA_ENABLED must be false for public deployment")
        if not self.allowed_host_list or "*" in self.allowed_host_list:
            errors.append("ALLOWED_HOSTS must contain explicit host names")
        parsed_origin = urlparse(self.public_origin)
        if parsed_origin.scheme != "https" or not parsed_origin.hostname:
            errors.append("PUBLIC_ORIGIN must be one HTTPS origin")
        elif parsed_origin.hostname.casefold() not in self.allowed_host_list:
            errors.append("PUBLIC_ORIGIN host must appear in ALLOWED_HOSTS")
        if errors:
            raise ValueError("Production configuration rejected: " + "; ".join(errors))
        return self


settings = Settings()
