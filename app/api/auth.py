from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse

from app.api.dependencies import require_user
from app.core.settings import settings
from app.schemas.auth import (
    AuthUserResponse,
    BootstrapRequest,
    CredentialsRequest,
    InviteRequest,
    InviteResponse,
    MfaConfirmRequest,
    MfaSetupResponse,
    MfaRecoveryCodesResponse,
    MfaStatusResponse,
    OAuthProvidersResponse,
    OAuthStartResponse,
    RegisterRequest,
    SessionsResponse,
)
from app.services.auth_service import AuthError, AuthenticatedUser, AuthService
from app.services.social_auth_service import SocialAuthError, SocialAuthService


router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _to_response(user: AuthenticatedUser) -> AuthUserResponse:
    return AuthUserResponse(id=user.id, username=user.username, role=user.role)


def _set_session(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=settings.auth_session_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
        path="/",
    )


def _raise_auth_error(error: AuthError) -> None:
    raise HTTPException(status_code=error.status_code, detail=error.detail) from error


def _oauth_state_cookie_name() -> str:
    return f"{settings.auth_cookie_name}_oauth_state"


def _oauth_mfa_cookie_name() -> str:
    return f"{settings.auth_cookie_name}_oauth_mfa"


def _set_oauth_state(response: Response, state: str) -> None:
    response.set_cookie(
        key=_oauth_state_cookie_name(),
        value=state,
        max_age=settings.oauth_state_ttl_seconds,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )


def _clear_oauth_state(response: Response) -> None:
    response.delete_cookie(
        _oauth_state_cookie_name(),
        path="/",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
    )


def _set_oauth_mfa_challenge(response: Response, challenge: str) -> None:
    response.set_cookie(
        key=_oauth_mfa_cookie_name(),
        value=challenge,
        max_age=settings.oauth_state_ttl_seconds,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
        path="/",
    )


def _clear_oauth_mfa_challenge(response: Response) -> None:
    response.delete_cookie(
        _oauth_mfa_cookie_name(),
        path="/",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
    )


@router.post("/bootstrap", response_model=AuthUserResponse)
def bootstrap(request: BootstrapRequest, response: Response):
    try:
        user = AuthService.bootstrap_admin(request.username, request.password, request.bootstrap_token)
        _set_session(response, AuthService.create_session(user))
        return _to_response(user)
    except AuthError as error:
        _raise_auth_error(error)


@router.post("/register", response_model=AuthUserResponse)
def register(request: RegisterRequest, response: Response):
    try:
        user = AuthService.register_with_invite(request.username, request.password, request.invite_token)
        _set_session(response, AuthService.create_session(user))
        return _to_response(user)
    except AuthError as error:
        _raise_auth_error(error)


@router.post("/login", response_model=AuthUserResponse)
def login(request: CredentialsRequest, response: Response, raw_request: Request):
    client_key = raw_request.client.host if raw_request.client else "unknown"
    try:
        user, token = AuthService.login(
            request.username, request.password, client_key, request.mfa_code, raw_request.headers.get("user-agent", "")
        )
        _set_session(response, token)
        return _to_response(user)
    except AuthError as error:
        _raise_auth_error(error)


@router.get("/oauth/providers", response_model=OAuthProvidersResponse)
def oauth_providers():
    return OAuthProvidersResponse(providers=SocialAuthService.provider_status())


@router.get("/oauth/{provider}/start", include_in_schema=False)
def start_oauth_login(provider: str, request: Request):
    try:
        authorization_url, oauth_state = SocialAuthService.begin_login(
            provider,
            SocialAuthService.callback_origin(str(request.base_url)),
        )
    except AuthError as error:
        _raise_auth_error(error)
    response = RedirectResponse(authorization_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    _set_oauth_state(response, oauth_state)
    return response


@router.post("/oauth/{provider}/link/start", response_model=OAuthStartResponse)
def start_oauth_link(
    provider: str,
    request: Request,
    response: Response,
    user: AuthenticatedUser = Depends(require_user),
):
    try:
        authorization_url, oauth_state = SocialAuthService.begin_link(
            provider,
            user,
            SocialAuthService.callback_origin(str(request.base_url)),
        )
    except AuthError as error:
        _raise_auth_error(error)
    _set_oauth_state(response, oauth_state)
    return OAuthStartResponse(authorization_url=authorization_url)


@router.get("/oauth/{provider}/callback", include_in_schema=False)
def complete_oauth_callback(
    provider: str,
    request: Request,
    code: str | None = Query(default=None, min_length=1, max_length=4_096),
    state: str | None = Query(default=None, min_length=20, max_length=1_024),
    provider_error: str | None = Query(default=None, alias="error", max_length=128),
):
    response = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    try:
        if provider_error:
            response.headers["Location"] = "/?oauth_error=cancelled"
            return response
        if not code or not state:
            response.headers["Location"] = "/?oauth_error=failed"
            return response
        outcome, user, token = SocialAuthService.complete_callback(
            provider,
            state,
            request.cookies.get(_oauth_state_cookie_name()),
            code,
        )
        if outcome == "linked":
            response.headers["Location"] = "/?oauth_success=linked"
        elif outcome == "mfa_required" and token is not None:
            _set_oauth_mfa_challenge(response, token)
            response.headers["Location"] = "/?oauth_mfa=required"
        elif user is not None and token is not None:
            _set_session(response, token)
    except SocialAuthError as error:
        response.headers["Location"] = f"/?oauth_error={error.code}"
    except AuthError:
        response.headers["Location"] = "/?oauth_error=failed"
    finally:
        _clear_oauth_state(response)
    return response


@router.post("/oauth/mfa/complete", response_model=AuthUserResponse)
def complete_oauth_mfa(
    request: MfaConfirmRequest,
    response: Response,
    raw_request: Request,
):
    try:
        user, token = SocialAuthService.complete_mfa_challenge(
            raw_request.cookies.get(_oauth_mfa_cookie_name()),
            request.code,
        )
        _set_session(response, token)
        _clear_oauth_mfa_challenge(response)
        return _to_response(user)
    except AuthError as error:
        _raise_auth_error(error)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response):
    AuthService.logout(request.cookies.get(settings.auth_cookie_name))
    response.delete_cookie(
        settings.auth_cookie_name,
        path="/",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
    )


@router.get("/me", response_model=AuthUserResponse)
def current_user(user: AuthenticatedUser = Depends(require_user)):
    return _to_response(user)


@router.get("/mfa", response_model=MfaStatusResponse)
def mfa_status(user: AuthenticatedUser = Depends(require_user)):
    try:
        return MfaStatusResponse(**AuthService.mfa_status(user))
    except AuthError as error:
        _raise_auth_error(error)


@router.post("/mfa/setup", response_model=MfaSetupResponse)
def setup_mfa(user: AuthenticatedUser = Depends(require_user)):
    try:
        return MfaSetupResponse(**AuthService.begin_mfa_setup(user))
    except AuthError as error:
        _raise_auth_error(error)


@router.post("/mfa/confirm", response_model=MfaStatusResponse)
def confirm_mfa(request: MfaConfirmRequest, user: AuthenticatedUser = Depends(require_user)):
    try:
        return MfaStatusResponse(**AuthService.confirm_mfa_setup(user, request.code))
    except AuthError as error:
        _raise_auth_error(error)


@router.post("/mfa/recovery-codes", response_model=MfaRecoveryCodesResponse)
def regenerate_mfa_recovery_codes(request: MfaConfirmRequest, user: AuthenticatedUser = Depends(require_user)):
    try:
        return MfaRecoveryCodesResponse(codes=AuthService.generate_mfa_recovery_codes(user, request.code))
    except AuthError as error:
        _raise_auth_error(error)


@router.get("/sessions", response_model=SessionsResponse)
def list_sessions(raw_request: Request, user: AuthenticatedUser = Depends(require_user)):
    return SessionsResponse(sessions=AuthService.sessions(user, raw_request.cookies.get(settings.auth_cookie_name)))


@router.post("/sessions/revoke-others")
def revoke_other_sessions(raw_request: Request, user: AuthenticatedUser = Depends(require_user)):
    try:
        count = AuthService.revoke_other_sessions(user, raw_request.cookies.get(settings.auth_cookie_name))
        return {"revoked": count}
    except AuthError as error:
        _raise_auth_error(error)


@router.post("/invites", response_model=InviteResponse)
def create_invite(
    request: InviteRequest,
    user: AuthenticatedUser = Depends(require_user),
):
    try:
        return AuthService.create_invite(user, request.role)
    except AuthError as error:
        _raise_auth_error(error)
