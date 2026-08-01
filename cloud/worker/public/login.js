"use strict";

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const form = $("#auth-form");
const errorBox = $("#auth-error");
const params = new URLSearchParams(location.search);
const invite = params.get("invite") || "";
const oauthMfaRequired = params.get("oauth_mfa") === "required";
let bootstrapRequired = false;

async function api(path, options = {}) {
  const response = await fetch(path, { credentials: "same-origin", ...options, headers: { "Content-Type": "application/json", ...(options.headers || {}) } });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.detail || "ไม่สามารถเชื่อมต่อระบบได้");
    error.status = response.status;
    error.data = data;
    throw error;
  }
  return data;
}

async function start() {
  try {
    const status = await api("/api/cloud/status");
    bootstrapRequired = Boolean(status.bootstrap_required);
    if (oauthMfaRequired) {
      $("#auth-title").textContent = "ยืนยัน Social Login";
      $("#auth-lead").textContent = "กรอกรหัส MFA หรือรหัสกู้คืนของบัญชี MyCodexAI";
      $("#username-wrap").classList.add("hidden");
      $("#password-wrap").classList.add("hidden");
      $("#username").required = false;
      $("#password").required = false;
      $("#mfa-wrap").classList.remove("hidden");
      $("#mfa-code").required = true;
      $("#auth-submit").textContent = "ยืนยันและเข้าสู่ระบบ";
      $("#mfa-code").focus();
    } else if (bootstrapRequired) {
      $("#auth-title").textContent = "สร้างผู้ดูแลระบบ";
      $("#auth-lead").textContent = "ตั้งค่าบัญชี Cloud ครั้งแรก โดยใช้โทเคนที่ใส่ผ่าน Wrangler secret";
      $("#bootstrap-wrap").classList.remove("hidden");
      $("#bootstrap-token").required = true;
      $("#password").autocomplete = "new-password";
      $("#auth-submit").textContent = "สร้างบัญชีและเข้าสู่ระบบ";
    } else if (invite) {
      $("#auth-title").textContent = "รับคำเชิญ";
      $("#auth-lead").textContent = "สร้างบัญชีใหม่ด้วยลิงก์เชิญแบบใช้ครั้งเดียว";
      $("#password").autocomplete = "new-password";
      $("#auth-submit").textContent = "สร้างบัญชี";
    } else {
      const oauth = await api("/api/auth/oauth/providers");
      for (const provider of ["google", "github"]) {
        const value = oauth.providers?.[provider];
        const configured = typeof value === "boolean" ? value : Boolean(value?.configured);
        if (configured) $("#oauth-" + provider).classList.remove("hidden");
      }
      if ($$("#oauth-login button:not(.hidden)").length) $("#oauth-login").classList.remove("hidden");
    }
    const oauthError = params.get("oauth_error");
    if (oauthError) {
      const messages = {
        cancelled: "ยกเลิกการเข้าสู่ระบบด้วย Social Login แล้ว",
        state: "คำขอ Social Login ไม่ถูกต้องหรือหมดอายุ กรุณาลองใหม่",
        not_linked: "บัญชี Social นี้ยังไม่ได้เชื่อมกับ MyCodexAI กรุณาเข้าสู่ระบบด้วยรหัสผ่านแล้วเชื่อมบัญชีก่อน",
        not_configured: "ผู้ให้บริการ Social Login นี้ยังไม่ได้ตั้งค่า",
        failed: "Social Login ไม่สำเร็จ กรุณาลองใหม่",
      };
      errorBox.textContent = messages[oauthError] || "Social Login ไม่สำเร็จ";
    }
  } catch (error) {
    errorBox.textContent = error.message;
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorBox.textContent = "";
  const button = $("#auth-submit");
  button.disabled = true;
  try {
    if (oauthMfaRequired) {
      await api("/api/auth/oauth/mfa/complete", { method: "POST", body: JSON.stringify({ code: $("#mfa-code").value }) });
      location.replace("/");
      return;
    }
    const body = { username: $("#username").value, password: $("#password").value };
    if (!$("#mfa-wrap").classList.contains("hidden")) body.mfa_code = $("#mfa-code").value;
    let endpoint = "/api/auth/login";
    if (bootstrapRequired) {
      endpoint = "/api/auth/bootstrap";
      body.bootstrap_token = $("#bootstrap-token").value;
    } else if (invite) {
      endpoint = "/api/auth/register";
      body.invite_token = invite;
    }
    await api(endpoint, { method: "POST", body: JSON.stringify(body) });
    location.replace("/");
  } catch (error) {
    if (error.data?.mfa_required && !bootstrapRequired && !invite) {
      $("#mfa-wrap").classList.remove("hidden");
      $("#mfa-code").required = true;
      $("#mfa-code").focus();
      $("#auth-submit").textContent = "ยืนยันและเข้าสู่ระบบ";
    }
    errorBox.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

for (const provider of ["google", "github"]) {
  $("#oauth-" + provider).addEventListener("click", () => {
    location.href = `/api/auth/oauth/${provider}/start`;
  });
}

start();
