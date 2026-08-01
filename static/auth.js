const form = document.querySelector('#auth-form');
const title = document.querySelector('#auth-title');
const description = document.querySelector('#auth-description');
const username = document.querySelector('#auth-username');
const password = document.querySelector('#auth-password');
const mfaLabel = document.querySelector('#auth-mfa-label');
const mfa = document.querySelector('#auth-mfa');
const secretLabel = document.querySelector('#auth-secret-label');
const secret = document.querySelector('#auth-secret');
const help = document.querySelector('#auth-help');
const error = document.querySelector('#auth-error');
const submit = document.querySelector('#auth-submit');
const socialLogin = document.querySelector('#social-login');
const loginGoogle = document.querySelector('#login-google');
const loginGithub = document.querySelector('#login-github');
const oauthMfaForm = document.querySelector('#oauth-mfa-form');
const oauthMfaCode = document.querySelector('#oauth-mfa-code');
const oauthMfaError = document.querySelector('#oauth-mfa-error');
const oauthMfaSubmit = document.querySelector('#oauth-mfa-submit');
const oauthMfaRequired = new URLSearchParams(window.location.search).get('oauth_mfa') === 'required';
const requestedDestination = new URLSearchParams(window.location.search).get('next') === '/remote' ? '/remote' : '/';
let mode = 'login';

const modes = {
    login: {
        title: 'เข้าสู่ระบบ',
        description: 'ใช้บัญชีที่ได้รับเชิญเพื่อเข้าถึง workspace ของคุณ',
        endpoint: '/api/auth/login',
        submit: 'เข้าสู่ระบบ',
        help: 'บัญชีถูกสร้างผ่านคำเชิญจากผู้ดูแลระบบ',
        secretLabel: '',
        secretField: '',
        mfa: true,
        minimumPasswordLength: 12,
        autocomplete: 'current-password',
    },
    register: {
        title: 'ใช้คำเชิญ',
        description: 'สร้างบัญชีใหม่ด้วยคำเชิญแบบใช้ได้ครั้งเดียว',
        endpoint: '/api/auth/register',
        submit: 'สร้างบัญชี',
        help: 'รหัสผ่านต้องมีอย่างน้อย 15 ตัวอักษร',
        secretLabel: 'รหัสคำเชิญ',
        secretField: 'invite_token',
        mfa: false,
        minimumPasswordLength: 15,
        autocomplete: 'new-password',
    },
};

function renderMode() {
    const config = modes[mode];
    title.textContent = config.title;
    description.textContent = config.description;
    help.textContent = config.help;
    submit.textContent = config.submit;
    secretLabel.hidden = !config.secretField;
    secret.required = Boolean(config.secretField);
    mfaLabel.hidden = !config.mfa;
    mfa.value = '';
    password.minLength = config.minimumPasswordLength;
    secret.value = '';
    password.autocomplete = config.autocomplete;
    error.hidden = true;
    document.querySelectorAll('.auth-tab').forEach((tab) => {
        tab.classList.toggle('active', tab.dataset.mode === mode);
    });
}

document.querySelectorAll('.auth-tab').forEach((tab) => {
    tab.addEventListener('click', () => {
        mode = tab.dataset.mode;
        renderMode();
    });
});

function showOAuthMessage() {
    const query = new URLSearchParams(window.location.search);
    const messages = {
        not_linked: 'บัญชีโซเชียลนี้ยังไม่ได้เชื่อมกับ MyCodexAI กรุณาเข้าสู่ระบบด้วยรหัสผ่านก่อน',
        already_linked: 'บัญชีโซเชียลนี้เชื่อมกับผู้ใช้อื่นอยู่แล้ว',
        provider_already_linked: 'บัญชีนี้เชื่อมผู้ให้บริการนี้ไว้แล้ว',
        not_configured: 'ยังไม่ได้ตั้งค่าผู้ให้บริการโซเชียล',
        cancelled: 'คุณยกเลิกการเข้าสู่ระบบผ่านโซเชียล',
        mfa_expired: 'ขั้นตอนยืนยัน MFA หมดอายุแล้ว กรุณาเริ่มเข้าสู่ระบบผ่านโซเชียลใหม่',
        mfa_invalid: 'รหัสยืนยัน MFA ไม่ถูกต้อง',
        failed: 'ยืนยันตัวตนผ่านโซเชียลไม่สำเร็จ กรุณาลองใหม่',
    };
    const message = messages[query.get('oauth_error')];
    if (message) {
        error.textContent = message;
        error.hidden = false;
    }
}

async function loadSocialProviders() {
    if (oauthMfaRequired) {
        socialLogin.hidden = true;
        return;
    }
    try {
        const response = await fetch('/api/auth/oauth/providers');
        const result = await response.json().catch(() => ({}));
        if (!response.ok) return;
        const providers = result.providers || {};
        const googleEnabled = Boolean(providers.google);
        const githubEnabled = Boolean(providers.github);
        socialLogin.hidden = !googleEnabled && !githubEnabled;
        loginGoogle.disabled = !googleEnabled;
        loginGithub.disabled = !githubEnabled;
    } catch {
        socialLogin.hidden = true;
    }
}

function beginSocialLogin(provider) {
    window.location.assign(`/api/auth/oauth/${provider}/start`);
}

loginGoogle.addEventListener('click', () => beginSocialLogin('google'));
loginGithub.addEventListener('click', () => beginSocialLogin('github'));

oauthMfaForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    oauthMfaSubmit.disabled = true;
    oauthMfaError.hidden = true;
    try {
        const response = await fetch('/api/auth/oauth/mfa/complete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: oauthMfaCode.value.trim() }),
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(result.detail || 'ยืนยัน MFA ไม่สำเร็จ');
        window.location.assign(requestedDestination);
    } catch (requestError) {
        oauthMfaError.textContent = requestError.message;
        oauthMfaError.hidden = false;
    } finally {
        oauthMfaSubmit.disabled = false;
    }
});

form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const config = modes[mode];
    const payload = { username: username.value.trim(), password: password.value };
    if (config.secretField) payload[config.secretField] = secret.value;
    if (config.mfa && mfa.value.trim()) payload.mfa_code = mfa.value.trim();

    submit.disabled = true;
    error.hidden = true;
    try {
        const response = await fetch(config.endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(result.detail || 'ไม่สามารถเข้าสู่ระบบได้');
        window.location.assign('/');
    } catch (requestError) {
        error.textContent = requestError.message;
        error.hidden = false;
    } finally {
        submit.disabled = false;
    }
});

renderMode();
if (oauthMfaRequired) {
    title.textContent = 'ยืนยัน MFA';
    description.textContent = 'กรอกรหัสจาก Authenticator เพื่อเข้าสู่ระบบด้วยบัญชีโซเชียล';
    document.querySelector('.auth-tabs').hidden = true;
    form.hidden = true;
    oauthMfaForm.hidden = false;
    oauthMfaCode.focus();
} else {
    showOAuthMessage();
    loadSocialProviders();
}
