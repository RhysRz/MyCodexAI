from typing import Literal

from pydantic import BaseModel, Field


class CredentialsRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=12, max_length=1_024)
    mfa_code: str | None = Field(default=None, max_length=64)


class BootstrapRequest(CredentialsRequest):
    bootstrap_token: str = Field(min_length=1, max_length=1_024)


class RegisterRequest(CredentialsRequest):
    invite_token: str = Field(min_length=1, max_length=1_024)


class InviteRequest(BaseModel):
    role: Literal["user", "admin"] = "user"


class AuthUserResponse(BaseModel):
    id: str
    username: str
    role: Literal["user", "admin"]


class InviteResponse(BaseModel):
    token: str
    role: Literal["user", "admin"]
    expires_at: str


class MfaConfirmRequest(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class MfaStatusResponse(BaseModel):
    enabled: bool
    required: bool


class MfaSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class MfaRecoveryCodesResponse(BaseModel):
    codes: list[str]


class SessionResponse(BaseModel):
    device_label: str
    created_at: str
    last_seen_at: str
    current: bool


class SessionsResponse(BaseModel):
    sessions: list[SessionResponse]


class OAuthProvidersResponse(BaseModel):
    providers: dict[str, bool]


class OAuthStartResponse(BaseModel):
    authorization_url: str
