# Secure public deployment

Deploy MyCodexAI only on a dedicated Linux VM. This application can accept source code and start isolated Docker jobs, so the VM must not hold unrelated secrets, personal files, SSH agent sockets, cloud credentials, or other workloads. Do **not** expose the development Windows machine directly to the internet.

## 1. Enroll MFA before public deployment

1. Use the current local-only instance and sign in as the administrator.
2. Click **ตั้งค่า MFA** in the top-right area.
3. Add the shown secret to an authenticator app, enter its six-digit code, then sign out and sign in once with the code to verify it.
4. Back up the encrypted local auth database securely. Losing both the database and the MFA encryption key makes MFA recovery impossible.

The public configuration rejects startup unless administrator MFA is required. Standard user accounts can additionally enroll MFA from the same control.

## 2. Prepare a dedicated VM

Use a supported Linux VM with a static public IP and enough memory for Ollama. Create a non-root `mycodexai` account, install Docker and Caddy from their official packages, and keep SSH key-only. The `mycodexai` account needs controlled access to Docker for the sandbox; Docker control is powerful, which is why this must be an isolated VM.

Create writable data directories and restrict them to the service account:

```bash
sudo install -d -o mycodexai -g mycodexai -m 0700 /srv/mycodexai/state /srv/mycodexai/workspace
sudo install -d -o root -g mycodexai -m 0750 /etc/mycodexai
sudo install -d -o caddy -g caddy -m 0750 /var/log/caddy
```

Build the existing sandbox image on that VM before starting the service:

```bash
cd /opt/mycodexai
sudo docker build -t mycodexai-sandbox:latest -f sandbox/Dockerfile sandbox
```

## 3. Configure the app

Copy `deploy/.env.production.example` to `/etc/mycodexai/mycodexai.env`, replace the domain placeholders, and generate a unique Fernet key:

```bash
/opt/mycodexai/venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
sudo chown root:mycodexai /etc/mycodexai/mycodexai.env
sudo chmod 0640 /etc/mycodexai/mycodexai.env
```

### Optional: Google and GitHub sign-in

Social sign-in is deliberately **not** a public registration path. A user first signs in with their MyCodexAI password, clicks **เชื่อม Google** or **เชื่อม GitHub**, and approves the provider. Only that already-linked provider account can subsequently use the social button on the login page. Provider access tokens are not saved by MyCodexAI.

If that MyCodexAI account has MFA enabled, the Authenticator code is still required after the provider returns. Social sign-in never bypasses MFA.

Create an OAuth web application in Google Cloud and/or a GitHub OAuth App. Put each provider's client ID and secret in the matching `OAUTH_*` variables, then register its exact HTTPS callback URL:

```text
https://YOUR_DOMAIN/api/auth/oauth/google/callback
https://YOUR_DOMAIN/api/auth/oauth/github/callback
```

Leave both variables for a provider empty to keep its button disabled. Never place either secret in source code, a browser, Git, or a chat message.

Copy the already-enrolled `auth.db` only through a secure administrator channel, or create and enroll a new administrator while the new VM is private. Never copy a production `.env`, database, workspace, or run state to GitHub.

Install `deploy/mycodexai.service` as `/etc/systemd/system/mycodexai.service`, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mycodexai
sudo systemctl status mycodexai
```

The application binds only to `127.0.0.1:8000`; do not open that port publicly. Ollama must likewise remain private on `127.0.0.1:11434`.

## 4. DNS, HTTPS, and firewall

Before starting Caddy, point the domain's A/AAAA record to the VM. Copy `deploy/Caddyfile` to `/etc/caddy/Caddyfile`, set `MYCODEXAI_DOMAIN` and `ACME_EMAIL` in Caddy's service environment, and restart Caddy.

Only allow public TCP ports `80` and `443`, plus SSH restricted to your own IP/VPN. Do not expose `8000`, `11434`, Docker's API, the database, or the workspace. Caddy obtains and renews the certificate and redirects HTTP to HTTPS once DNS and ports 80/443 are correct.

## 5. Verify before inviting anyone

```bash
curl -I https://ai.example.com/
curl -I http://ai.example.com/
curl -fsS https://ai.example.com/healthz
sudo ss -lntp | grep -E ':(80|443|8000|11434)'
```

Verify that the public response has `Strict-Transport-Security`, `Content-Security-Policy`, `X-Frame-Options: DENY`, and no `Server` header. Confirm that port 8000 and 11434 listen only on loopback. Test admin sign-in with MFA, create one low-privilege invite, and delete it after verification.

Keep Docker, Caddy, the OS, Ollama, Python dependencies, and this application patched. Review Caddy access logs and system logs, back up `/srv/mycodexai/state/auth.db` encrypted, and test restore on a separate private machine.

## 6. Migration and recovery kit

Before moving the live instance, run the included preflight script on the destination VM. It checks the production controls without printing values from the environment file:

```bash
cd /opt/mycodexai
sudo bash deploy/oracle-preflight.sh /opt/mycodexai /etc/mycodexai/mycodexai.env
```

Create a server-side state backup before every upgrade or migration. Keep the generated archive and checksum in encrypted storage outside the VM; it can contain user workspaces and the encrypted MFA database.

```bash
sudo bash /opt/mycodexai/deploy/oracle-backup.sh /srv/mycodexai /var/backups/mycodexai
```

On the current Windows machine, `deploy/windows/Start-MyCodexAI.ps1` is the single safe launcher. To start it automatically after your Windows sign-in, run this once in an ordinary PowerShell window:

```powershell
cd C:\MyCodexAI
.\deploy\windows\Install-MyCodexAIRecoveryTask.ps1
```

The task starts only after this Windows user signs in. It launches a small local watchdog that checks port 8000 every 30 seconds, starts MyCodexAI again if it is missing, and waits briefly for Docker Desktop before restarting an existing Quick Tunnel. It does not expose port 8000 and it does not create a new public Quick Tunnel. Remove it at any time with `Remove-MyCodexAIRecoveryTask.ps1`.

If Windows policy rejects Scheduled Tasks, use the per-user Startup fallback instead (no administrator permission required):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\MyCodexAI\deploy\windows\Install-MyCodexAIStartupFallback.ps1
```

## Remote control from a phone

After HTTPS, DNS, authentication, and MFA verification are complete, open this exact URL in Safari or another mobile browser:

```text
https://YOUR_DOMAIN/remote
```

The Remote page is a compact client for sending an agent task, selecting the permitted worktree/project, tracking progress, and approving or rejecting the same guarded actions shown on desktop. It does not expose a raw shell, Docker, Ollama, or a new unauthenticated control API. Add the page to the phone home screen only after confirming the HTTPS certificate and login work correctly. Do not bookmark or expose a direct IP address or port 8000.
