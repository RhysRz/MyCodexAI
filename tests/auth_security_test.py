from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from cryptography.fernet import Fernet

from app.core.settings import settings
from app.services.auth_service import AuthError, AuthService
from app.services.mfa_service import MfaService


temporary_root = TemporaryDirectory()
original_database_path = AuthService._database_path
original_bootstrap_token = settings.auth_bootstrap_token
original_mfa_key = settings.auth_mfa_encryption_key
original_max_sessions = settings.auth_max_active_sessions
original_attempts = settings.auth_login_max_attempts
AuthService._database_path = Path(temporary_root.name) / "auth.db"
settings.auth_bootstrap_token = "test-bootstrap-token"
settings.auth_mfa_encryption_key = Fernet.generate_key().decode("ascii")
settings.auth_max_active_sessions = 2
settings.auth_login_max_attempts = 3
AuthService._login_attempts.clear()

try:
    admin = AuthService.bootstrap_admin("security-admin", "a secure passphrase for testing", "test-bootstrap-token")
    setup = AuthService.begin_mfa_setup(admin)
    assert setup["secret"] and setup["provisioning_uri"].startswith("otpauth://totp/")
    assert AuthService.confirm_mfa_setup(admin, MfaService._totp(setup["secret"], 0))["enabled"] is True

    try:
        AuthService.login("security-admin", "a secure passphrase for testing", "test-client")
        raise AssertionError("MFA-enabled login must require a verification code")
    except AuthError as error:
        assert error.status_code == 401

    user, token = AuthService.login(
        "security-admin",
        "a secure passphrase for testing",
        "test-client",
        MfaService._totp(setup["secret"], 0),
    )
    assert user.id == admin.id
    assert AuthService.mfa_status(user)["enabled"] is True

    recovery_codes = AuthService.generate_mfa_recovery_codes(user, MfaService._totp(setup["secret"], 0))
    assert len(recovery_codes) == settings.auth_recovery_code_count
    recovery_user, _ = AuthService.login(
        "security-admin", "a secure passphrase for testing", "recovery-client", recovery_codes[0], "iPhone"
    )
    assert recovery_user.id == admin.id

    desktop_token = AuthService.create_session(admin, "Windows browser")
    phone_token = AuthService.create_session(admin, "iPhone")
    sessions = AuthService.sessions(admin, phone_token)
    assert any(item["current"] and item["device_label"] == "iPhone / iPad" for item in sessions)
    assert AuthService.revoke_other_sessions(admin, phone_token) >= 1
    assert len(AuthService.sessions(admin, phone_token)) == 1

    for _ in range(3):
        try:
            AuthService.login("security-admin", "wrong password", "different-client")
        except AuthError as error:
            last_error = error
    assert last_error.status_code == 429

    with AuthService._connection() as connection:
        connection.execute(
            "UPDATE users SET lockout_until = NULL, failed_login_count = 0 WHERE id = ?", (admin.id,)
        )
    token = AuthService.create_session(admin)
    with AuthService._connection() as connection:
        connection.execute(
            "UPDATE sessions SET last_seen_at = ? WHERE token_hash = ?",
            (AuthService._timestamp(AuthService._now() - timedelta(hours=9)), AuthService._hash_token(token)),
        )
    assert AuthService.user_from_session(token) is None
finally:
    AuthService._database_path = original_database_path
    AuthService._login_attempts.clear()
    settings.auth_bootstrap_token = original_bootstrap_token
    settings.auth_mfa_encryption_key = original_mfa_key
    settings.auth_max_active_sessions = original_max_sessions
    settings.auth_login_max_attempts = original_attempts
    temporary_root.cleanup()

print("auth_security=ok")
