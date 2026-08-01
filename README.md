# MyCodexAI

MyCodexAI is a local, Ollama-powered coding assistant built with FastAPI. It includes invite-only accounts, isolated workspaces, and an approval-aware coding-agent endpoint.

## Accounts and safe remote access

Every user must sign in before they can access the workspace, upload files, start an agent, or approve an action. The first administrator is created with a bootstrap token; administrators can create one-time, seven-day invite tokens from the Admin card in the workspace. Each account receives a separate workspace at `WORKSPACE_ROOT/users/<user-id>`, and agent runs are tied to their owner.

Before the first start, add a long random value to `.env`:

```env
AUTH_BOOTSTRAP_TOKEN=replace-with-a-long-random-secret
```

Open the app and choose **สร้าง Admin** to consume that token. Store the token safely; it is needed only for the first administrator. Use the Admin card to create invitation tokens for other users.

For public deployment, set `DEBUG=false` and keep `AUTH_COOKIE_SECURE=true`. Put the app behind an HTTPS reverse proxy or an authenticated tunnel; do not expose Uvicorn's port 8000 directly to the public internet.

### Keeping a small PC responsive

MyCodexAI defaults to one model request at a time, two Ollama inference threads per request, and a 90-second model keep-alive. These values preserve the model, context, and sampling quality while reserving CPU for Windows; a task may take longer but the desktop stays usable. Override only if needed in `.env`:

```env
OLLAMA_INFERENCE_THREADS=2
OLLAMA_MAX_CONCURRENT_REQUESTS=1
OLLAMA_KEEP_ALIVE_SECONDS=90
```

## What the agent can do

- Inspect workspace files and search code automatically
- Inspect Git status and uncommitted diffs
- Initialize a repository, create reviewed branches, create reviewed commits, and preview a one-file rollback
- Propose a complete file replacement with a unified diff preview
- Create a small, related group of files in one combined diff review (up to 20 files)
- Attach source files, folders, or ZIP archives and continue work from them
- Run `pytest` or `unittest` only after approval
- Run one approved, workspace-scoped project command with live terminal output and cancellation
- Render a trusted local HTML page in a headless browser and keep a project-scoped screenshot for visual review
- Continue a multi-step task until it completes, reaches its step limit, or needs approval
- Run a local-safe Team workflow that hands work from Research to Implement to Review

## Project Builder

Choose **Project Builder** in the web workspace (or use `"mode": "project"` in the API) when the request is to build a whole application. It gives the local Ollama agent up to 60 tool steps and asks it to:

1. Record a concise project plan.
2. Inspect the workspace and create the project in focused multi-file batches.
3. Pause for your approval before each file batch, install, build, or test command.
4. Continue after approval, then summarize the project and any manual setup that remains.

The agent may create up to 20 files in each reviewed batch. It can use reviewed, no-shell project commands such as `npm`, `pnpm`, `yarn`, `bun`, `pip`, `uv`, `poetry`, `pytest`, `go`, `cargo`, `dotnet`, `gradle`, and `mvn` for the project workflow.

## Expert workflow (Codex-style on Ollama)

Choose **Expert: workflow แบบ Codex** for a quality-focused project task. It uses the same local Ollama model and approval boundaries, but it directs the agent to work in layers: understand the project, plan, implement in reviewed batches, detect the relevant checks, run approved verification, review the changed files, and then report evidence and remaining risks. It also uses the active Code Index, Project Memory, and Project Guidance.

The **Guidance** controls provide repository-level instructions comparable to `AGENTS.md`: conventions, required tests, commands, and constraints. MyCodexAI reads both the project `AGENTS.md` and its saved `.mycodexai/instructions.md` for each new run. When the agent is working in a nested source folder, it can read inherited instructions from every parent `AGENTS.md`; a nearer `AGENTS.override.md` replaces the normal `AGENTS.md` at that folder only. Project guidance cannot override the current user request, safety rules, or approval requirements.

This improves the workflow but does not make an Ollama model identical to OpenAI's `gpt-5.6-sol`. The active `qwen2.5-coder:3b` configuration is a small local model; use a stronger coding/reasoning model that your machine can run through Ollama for materially better planning and tool use. Do not change `OLLAMA_MODEL` until that model is installed locally.

## Delivery workflow (durable goal)

Choose **Delivery: Plan → Build → Verify → Review** when a task should be carried through to a reviewable handoff. The agent first plans and makes only approved changes. When it returns a final answer after an approved write, MyCodexAI automatically detects one supported project test or build command and asks for approval to run it in the Docker sandbox. A passing check is followed by a read-only Git status and diff capture in the timeline. A failing check changes the run to **needs input**; inspect the evidence, then click **ทำต่อจากสถานะเดิม** to let the same goal continue from its saved context.

Delivery mode never auto-commits, never bypasses an approval, and records no prompt or file content in its operational log.

## Per-user safety budget and activity

Every signed-in user has a daily agent-run and model-step allowance. Defaults are `12` runs and `240` model decisions per UTC day. This prevents a shared local Ollama machine from being monopolized by an accidental loop while preserving the configured model and its quality. Change these values in `.env` only when the machine capacity and user trust level justify it:

```env
AGENT_DAILY_RUN_LIMIT=12
AGENT_DAILY_STEP_LIMIT=240
AGENT_AUDIT_RETENTION=400
```

Set a limit to `0` only to disable that one limit. The **OPERATIONS** card shows the current user's allowance and latest event. The audit stores metadata such as start, approval, verification, cancellation, and completion; it deliberately excludes task text, files, command arguments, model responses, credentials, and tokens. Browser notifications are opt-in and only requested when the user clicks the button.

Administrators are explicitly quota-exempt, so their account has an unlimited recovery and maintenance path. The displayed limits still apply to ordinary user accounts only.

## GitHub handoff and real CI

The **GITHUB & CI** card reads the active project's Git branch and `origin` safely, can generate `.github/workflows/mycodexai-ci.yml`, push the current committed branch, and open a pull request. Creating the CI file, pushing, and opening a pull request each use a single-use confirmation that is bound to the signed-in user, selected worktree, and selected project and expires after 10 minutes.

MyCodexAI never asks for, receives, stores, or writes a GitHub personal access token. Use the operating system's Git Credential Manager for push authentication. To open pull requests from the card, install [GitHub CLI](https://cli.github.com/) and run `gh auth login` in PowerShell once; its sign-in remains managed by GitHub CLI, not MyCodexAI. After the CI workflow is committed and pushed, GitHub Actions runs the detected Python, Node, Go, or Rust checks on GitHub's runners.

For a new repository, click **เชื่อม Repository** and enter a plain `https://github.com/owner/repository.git` or `git@github.com:owner/repository.git` URL. It configures only the local `origin`; click **Push branch** separately after reviewing the confirmation. URLs containing embedded credentials are rejected.

## Team workflow (local multi-agent)

Choose **Team: Research → Implement → Review** for work that benefits from an explicit second pass. MyCodexAI runs three specialized roles in sequence: Research first explores the codebase and hands off a small plan; Implement makes the approved changes; Review inspects the resulting diff and requests the most relevant verification. Each role and its handoff appear in the run timeline.

The roles deliberately run **one at a time**, rather than running several Ollama requests in parallel. On this computer's 8 GB RAM and CPU-only Ollama setup, parallel model calls would compete for RAM and CPU and make the system less responsive. It still provides the useful Codex-style separation of context and review without that performance penalty. Research and Review are technically restricted to read-only tools (apart from approved tests/browser checks for Review); only Implement can propose code or Git changes. Every write and command retains the normal approval screen.

## Background agent queue and cancellation

The web workspace now starts agent work in the background and polls its live status, so the page remains usable while Ollama is thinking. MyCodexAI runs at most one background agent at a time (`AGENT_MAX_CONCURRENT_RUNS=1` by default); later tasks enter a first-in, first-out queue until the current task reaches approval, completion, or failure. A queued task displays only its own queue position and the total number of active/queued tasks; it never reveals another user's task, name, files, or workspace. This deliberately avoids competing Ollama processes on a CPU-only 8 GB machine.

Use **หยุด agent** to cancel a queued job immediately or request cancellation for a running job. Ollama cannot safely be interrupted mid-response, so a running job stops after its current response returns and does not execute another action. Approved writes and commands keep their existing approval boundary. If the API process restarts while a background run is active, MyCodexAI marks it as needing input rather than resuming it without review.

## Recovery, encrypted backups, and resource guard

The **RECOVERY & HOST** card reports whether the Docker sandbox is ready, how many of *your* jobs are active, and available RAM when `psutil` is installed. `RESOURCE_GUARD_ENABLED=true` delays a new Ollama response while the host has less than `RESOURCE_GUARD_MIN_AVAILABLE_MB` free memory. It never changes the Ollama model, prompt, token limit, or sampling settings; it only waits, then uses the existing inference settings.

Click **สร้าง Backup เข้ารหัส** to create an owner-scoped workspace recovery point. You must choose a separate passphrase of at least 16 characters; it is used locally to encrypt the archive and is never saved by MyCodexAI. The archive excludes `.env` files, dependency caches, virtual environments, and Git metadata. Keep the passphrase in a password manager and keep the local backup directory protected. A restore requires the passphrase plus typing the exact `RESTORE backup-...` confirmation, cannot run while your agent has an active job, and preserves the current workspace as a local restore point before replacement.

Use **รหัสกู้คืน MFA** after MFA is enabled to generate one-time recovery codes. Confirm it with the current Authenticator code, copy the displayed codes directly to a password manager, and never share them. Generating new codes invalidates all old recovery codes. The **DEVICES** card stores only a coarse device label (for example `iPhone / iPad`), not IP addresses or full browser fingerprints; **ออกจากอุปกรณ์อื่นทั้งหมด** revokes every other session while retaining the current device.

## Installable mobile client

`/remote` is an installable Progressive Web App when opened over HTTPS. On iPhone Safari use **Share → Add to Home Screen**; on Android use the browser's **Install app** or **Add to Home screen** command. The service worker caches only static UI files. It never caches HTML, API responses, workspace files, sessions, or agent output. The Remote page can request a browser notification permission while it is open in the background; it does not use push notifications or a third-party notification service.

## Training Lab: curate first, train later

The **TRAINING LAB** card is a private data-curation and evaluation pipeline. It does **not** silently train Ollama, collect chat history, send data to a third party, or change the active model. Add only examples you have reviewed: an instruction, an ideal answer, and optional tags. Text that looks like a credential is rejected before it can be stored.

Add benchmark prompts with one or more required terms, then choose **Run Benchmark** to measure the current Ollama model. The saved report contains scores and matched-term counts, not raw model responses. This provides a before/after score when you later evaluate an adapter.

Choose **Export JSONL** to download your manual examples in chat-JSONL format. Keep that export private. It is the input for a later, separate QLoRA/LoRA job on a compatible GPU; importing an adapter into Ollama must use the same base model family as the adapter. Training data stays local to the signed-in user unless that user downloads it.

## Code Review mode

Choose **Code Review: ตรวจ Git diff แบบอ่านอย่างเดียว** to start a dedicated, read-only reviewer. Its scope selector supports **Uncommitted changes** (tracked staged and unstaged changes against `HEAD`), **Staged changes**, **One commit**, or **Branch against HEAD**. The reviewer checks Git status and the selected diff, then reads only the relevant changed files. It reports prioritized, actionable findings with evidence and does not edit files, stage, commit, create branches, or restore code. It may request approval for a focused test or Browser QA screenshot when verification is necessary.

Use a concrete review prompt such as: `Review this branch for security, regressions, and test gaps. Report only actionable findings with file references.` For **One commit** or **Branch against HEAD**, fill in a commit hash or base branch name. The active project must be a Git repository; otherwise the reviewer reports that review scope is unavailable.

## Project Skills (`SKILL.md` workflows)

The **PROJECT SKILLS** controls let you store a reusable workflow inside the active project's `.mycodexai/skills/<skill-id>/SKILL.md`. Give it a lowercase id such as `frontend-qa`, a short name, a description that says when it applies, and the complete instructions for the workflow. Click a saved Skill to load it back into the editor.

On a new task, MyCodexAI gives Ollama only the Skill ids, names, and descriptions. If the user explicitly names a Skill or the task clearly matches its description, the agent can read that one Skill's complete instructions through `read_project_skill`. This keeps detailed workflows out of unrelated tasks and avoids increasing model context or CPU load. Skill instructions are project context only: they cannot bypass approvals, Docker policy, or the current user request.

## Attach existing files

Use **แนบไฟล์** to add one or more files, or **แนบโฟลเดอร์** to copy a folder while preserving its structure. The default destination is `uploads`; change the destination field to choose another workspace-relative folder. ZIP files are extracted beneath a folder named after the archive, so attaching `starter.zip` to `imports` produces `imports/starter/...`.

The upload endpoint validates every path, blocks path traversal and symbolic links in ZIP archives, and rejects existing files unless **แทนที่ไฟล์เดิม** is selected. A task receives the uploaded paths as attachments, so Project Builder knows what to inspect first. The limit is 100 files, 25 MB per file, and 100 MB per upload batch.

The agent is intentionally limited to the configured workspace. It has no arbitrary shell command tool. Git initialization, branch creation, commits, and rollback are explicit approval-required actions. A reviewed package command may use the network when the selected runtime requires it.
The legacy `/api/chat` endpoint is read-only; use the agent endpoint for any file modification.

## Import a complete source project

Use **นำเข้าโฟลเดอร์** or **นำเข้า ZIP** in the **Active project** card to import a codebase as one project. This is different from attachments: the agent receives a project root and can inspect the tree on demand, so a project is not limited by the 100 attachment paths used by a single task.

The import accepts up to 2,000 files, 25 MB per file, and 100 MB after extraction. It automatically excludes `.git`, `.mycodexai`, virtual environments, `node_modules`, `__pycache__`, logs, compiled Python files, and likely secrets such as `.env`, `.key`, `.pem`, SSH keys, and `credentials.json`. ZIP imports reject unsafe paths and symbolic links. Source is placed at `projects/<project-name>` in the current workspace/worktree.

Choose the imported project from **Active project** before starting an agent task, adding attachments, or using Safe Terminal. The API then scopes all those operations to that project. A run or terminal job cannot be resumed through a different project header.

Use **สร้าง Code Index** after importing a project or making substantial external changes. The index records the project tree, language totals, top-level folders, likely entry points, Python symbols/imports, and JavaScript/TypeScript symbols/imports. During Project Builder work the agent can use `inspect_project` and `find_code` to locate relevant files before opening them. Index data stays in the active project's `.mycodexai/codebase-index.json` cache and is invalidated automatically after agent writes or uploads.

## Project Memory and task history

The **บันทึก Memory** field stores architecture decisions, conventions, or known constraints for the active project. When a signed-in agent run reaches a final status, MyCodexAI also saves a compact task record: task, status, plan name, tools used, and final summary. Use **ดู History** to inspect those records.

At the next run, the project notes and a small set of recent task outcomes are provided to the agent as *untrusted historical context*. The system prompt tells it to verify that context against current source files before acting. Memory is scoped to the active project at `.mycodexai/project-memory.json`; it is not shared with other projects or users.

## Safe Terminal

The **SAFE TERMINAL** card lets a signed-in user review a command before it starts, follow output while it runs, and request cancellation. It executes a direct argument list with `shell=False` in the selected workspace or a selected subdirectory. There is at most one active command per user and worktree, and switching worktrees is locked while it runs.

Allowed commands are the same project runtimes available to the agent (`npm`, `pnpm`, `yarn`, `bun`, `pip`, `uv`, `poetry`, `pytest`, `go`, `cargo`, `dotnet`, `gradle`, and `mvn`), plus read-only Git operations (`status`, `diff`, `log`, `branch`, `show`, and `rev-parse`). It intentionally rejects PowerShell, `cmd`, command chaining, arbitrary executables, and Git write operations. Commands stop after 15 minutes unless they finish or the user requests cancellation.

The default `SANDBOX_MODE=host` is a workspace-scoped command policy, not an operating-system container. Package scripts can still execute code, so a public deployment should use the Docker sandbox below or run MyCodexAI under a dedicated non-administrator OS account/VM.

## Docker execution sandbox

MyCodexAI includes a fail-closed Docker execution mode for Safe Terminal, approved agent project commands, tests, and Browser QA. In this mode each run gets a fresh container with a read-only container filesystem, dropped Linux capabilities, `no-new-privileges`, CPU/memory/PID limits, an isolated `/tmp`, and no network by default. Only the active project is bind-mounted at `/workspace`; it stays writable so builds and tests can create their expected project files.

Docker mode never falls back to the host. If Docker Desktop is stopped or the sandbox image is missing, the command fails with that explicit reason. The workspace displays the current `Host policy` or `Docker sandbox` status before a command is approved.

On a machine with Docker Desktop installed and running, build the included image once:

```bash
docker build -t mycodexai-sandbox:latest -f sandbox/Dockerfile sandbox
```

If Docker Desktop was installed only for the current Windows user and a terminal still says that `docker` is not recognized, open a new PowerShell window first. As an immediate alternative, call the installed CLI directly:

```powershell
& "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe" build -t mycodexai-sandbox:latest -f sandbox/Dockerfile sandbox
```

MyCodexAI detects this per-user Docker Desktop CLI automatically; an explicit `SANDBOX_DOCKER_EXECUTABLE` setting is only needed for a non-standard installation path.

Then set these values in `.env` and restart MyCodexAI:

```env
SANDBOX_MODE=docker
SANDBOX_DOCKER_IMAGE=mycodexai-sandbox:latest
SANDBOX_ALLOW_NETWORK=false
```

Keep network disabled for normal testing. Turn it on only temporarily for a reviewed dependency installation, then turn it off and restart the app. Docker isolation is a substantial safety improvement, but it does not replace keeping Docker Desktop and the host OS patched or treating projects from unknown users as untrusted.

## Browser QA screenshots

The **BROWSER QA** card renders one selected `.html`/`.htm` file inside the active project using a local headless Chromium browser and displays the resulting screenshot. It is useful after creating a static landing page or other browser UI: select `index.html` (or enter another project-relative HTML path), click **สร้าง Screenshot**, and inspect the image before accepting the result.

An Expert run can also request `capture_browser_qa`; like writes and tests, it pauses for approval first. Its screenshot appears in the run timeline. Every screenshot is stored only in that active project's `.mycodexai/browser-qa` directory and its image endpoint remains session-protected.

In host mode Browser QA deliberately runs the page's JavaScript on the API host. Do not render untrusted projects there. In Docker mode it instead uses Chromium inside the execution sandbox with network disabled; its screenshot is written back only to the active project's Browser QA cache. You can disable Browser QA (`BROWSER_QA_ENABLED=false`) or configure `BROWSER_QA_EXECUTABLE` for host mode.

## Isolate parallel work with Git worktrees

Each user starts on a private **main workspace**. When that workspace is a Git repository with at least one commit, the **Workspace / branch** control above the task box can create a branch workspace such as `feature/login-page`. MyCodexAI creates it as a Git worktree outside the repository and switches uploads, file tools, and agent runs to that selected branch.

Use this sequence for a new project:

1. Ask the agent to initialize Git and approve the action.
2. Create and approve the first coherent file batch, then ask the agent to commit it.
3. Enter a branch name in **Workspace / branch** and choose **สร้าง branch workspace**.
4. Select that workspace before starting the task. Attachments and approved writes stay on that branch; the main workspace is unchanged.

An agent run is bound to the worktree in which it was started. The API rejects a read or approval request sent with a different `X-MyCodexAI-Worktree` header, preventing an approval from being applied to the wrong branch.

## Configure

Set these values in `.env`:

```env
APP_NAME=MyCodexAI
DEBUG=true
OLLAMA_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen2.5-coder:3b
OLLAMA_API_KEY=ollama
OLLAMA_TIMEOUT_SECONDS=90
OLLAMA_MAX_TOKENS=512
AGENT_MAX_CONCURRENT_RUNS=1
WORKSPACE_ROOT=workspace
AGENT_STATE_ROOT=.mycodexai/runs
AUTH_DATABASE_PATH=.mycodexai/auth.db
AUTH_BOOTSTRAP_TOKEN=replace-with-a-long-random-secret
AUTH_COOKIE_NAME=mycodexai_session
AUTH_SESSION_DAYS=7
AUTH_COOKIE_SECURE=true
BROWSER_QA_ENABLED=true
# Optional: BROWSER_QA_EXECUTABLE=C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe
BROWSER_QA_TIMEOUT_SECONDS=45
# Optional scanned-score OMR. Leave empty to keep the OMR process disabled.
# Example after installing the local Audiveris app:
# MUSIC_OMR_EXECUTABLE=C:\\Program Files\\Audiveris\\bin\\Audiveris.exe
# MUSIC_OMR_TIMEOUT_SECONDS=300
SANDBOX_MODE=host
SANDBOX_DOCKER_IMAGE=mycodexai-sandbox:latest
SANDBOX_ALLOW_NETWORK=false
SANDBOX_MEMORY_MB=2048
SANDBOX_CPUS=2
SANDBOX_PIDS_LIMIT=256
```

`WORKSPACE_ROOT` is the parent directory for user workspaces. Each signed-in user can only inspect or edit their own `WORKSPACE_ROOT/users/<user-id>` directory. Use an absolute path if the coding storage should be outside this project. `AGENT_STATE_ROOT` stores resumable agent runs, and `AUTH_DATABASE_PATH` stores users, sessions, and invite hashes; both locations must be writable by the API process.

During local HTTP development (`DEBUG=true`), secure cookies are automatically relaxed so login works on `http://127.0.0.1`. Do not use that mode for remote deployment.

### Music Lab: score OMR and guitar TAB

Music Lab reads selectable-text chord sheets and vector guitar/bass TAB directly.
For a scanned PDF or a five-line staff image, install a local OMR application such
as Audiveris, set `MUSIC_OMR_EXECUTABLE` to its executable, and restart MyCodexAI.
The OMR process is called only when a score PDF has no readable chord text or
vector TAB; uploaded files can never choose the executable or command.  The result
is converted from MusicXML to editable MIDI, analysis JSON, and a note preview.

Music Lab also includes a local sample-playback engine (FluidSynth plus GeneralUser
GS) for the selectable Piano, Guitar, Bass, Strings, and Flute preview. It renders
only after an authenticated user clicks play and saves the private WAV beside that
user's music item; subsequent plays of the same instrument use the cached render.
The configurable locations are `MUSIC_FLUIDSYNTH_EXECUTABLE` and
`MUSIC_SOUNDFONT_PATH`. Keep the SoundFont local—never expose it as a public static
download. See the upstream [FluidSynth](https://github.com/FluidSynth/fluidsynth)
and [GeneralUser GS](https://github.com/mrbumpy409/GeneralUser-GS) projects for
their licenses and attribution.

## Run

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000/` for the agent workspace, or `http://127.0.0.1:8000/docs` for the API reference.

## Public HTTPS deployment

Do not expose the development Windows machine or port `8000` directly. The production-ready Caddy, systemd, firewall, MFA-enrollment, backup, and verification procedure is in [deploy/README.md](deploy/README.md). It keeps FastAPI and Ollama on loopback and exposes only Caddy on ports 80/443 with the existing invite-only login plus TOTP MFA for administrators.

All coding and upload endpoints require the session cookie. Authentication endpoints are available at `/api/auth/bootstrap`, `/api/auth/register`, `/api/auth/login`, `/api/auth/logout`, `/api/auth/me`, and `/api/auth/invites`.

## Agent API

Start a task:

```http
POST /api/agent/runs
Content-Type: application/json

{
  "task": "Create a Vite React task tracker with local storage and tests",
  "mode": "project",
  "max_steps": 60
}
```

For the sequential team workflow, use `"mode": "team"`. It defaults to 24 total tool steps across all three roles; the API permits up to 36 for an unusually large investigation.

For read-only review, use `"mode": "review"`. The optional `review_scope` is `uncommitted` (default), `staged`, `commit`, or `branch`; `review_target` is required only for `commit` and `branch`:

```json
{
  "task": "Review for security and regressions; report actionable findings only.",
  "mode": "review",
  "review_scope": "branch",
  "review_target": "main"
}
```

Read-only actions run immediately. A file write, related multi-file build, or project command returns `status: "awaiting_approval"` with a preview in `pending_action.preview`. A multi-file build uses `write_files`, validates every workspace path before writing, and presents one combined diff. Approve or reject exactly that pending action:

```http
POST /api/agent/runs/{run_id}/resume
Content-Type: application/json

{
  "approve": true
}
```

Use `GET /api/agent/runs/{run_id}` to retrieve the trace, project plan, and progress. Runs are saved under `AGENT_STATE_ROOT` and can be resumed after an API restart when that directory is writable.

To use a non-main worktree through the API, include its branch identifier in every workspace, agent, and upload request:

```http
X-MyCodexAI-Worktree: feature/login-page
```

`GET /api/worktrees` lists the current user's worktrees, and `POST /api/worktrees` with `{ "branch": "feature/login-page" }` creates one after the main workspace has an initial commit.

## Terminal API

Create a command review:

```http
POST /api/terminal/jobs
X-MyCodexAI-Worktree: feature/login-page
Content-Type: application/json

{
  "command": ["npm", "test"],
  "working_directory": "apps/web"
}
```

The job starts as `awaiting_approval`. Send `POST /api/terminal/jobs/{job_id}/resume` with `{ "approve": true }`, then poll `GET /api/terminal/jobs/{job_id}` to receive current output. Send `POST /api/terminal/jobs/{job_id}/cancel` to request cancellation. Each request must use the same worktree header as the job.

## Project API

`GET /api/projects` lists the available projects in the selected worktree. `POST /api/projects/import` accepts multipart `project_name` and `files`; pass either every file from a selected folder (with relative paths) or one ZIP archive. To scope uploads, agent runs, and terminal jobs to an imported project, send its identifier as:

```http
X-MyCodexAI-Project: MyCodexAI
```

`GET /api/projects/index` returns the active project's existing index or creates it when absent. `POST /api/projects/index/rebuild` forces a rebuild. Both use the same project header.

`GET /api/projects/memory` returns the active project's notes and task history. `POST /api/projects/memory/notes` accepts `{ "note": "..." }` to add an architecture note. Both use the same project header.

`GET /api/projects/guidance?directory=apps/web` returns the effective ordered guidance for an existing workspace folder, including its source paths. Omit `directory` for project-root guidance.

For example, ask: `Create a simple landing page with index.html, style.css, and app.js, then wait for my review.` For a full project, select Project Builder and be explicit about the stack, features, and target folder. The agent will pause before it creates files or executes project commands.

## Upload API

`POST /api/workspace/uploads` accepts multipart `files`, plus optional `destination` (defaults to `uploads`) and `overwrite` (defaults to `false`). Its response contains the workspace-relative paths to include in the `attachments` array when starting an agent run.

## Project structure

```
app/        FastAPI app, Ollama adapter, tools, agent loop
workspace/  Default coding workspace for the agent
tests/      Script-based regression checks
```
