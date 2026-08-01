const remoteState = {
    workspaceId: 'main',
    projectId: 'workspace',
    runId: null,
    pollTimer: null,
    user: null,
    backups: [],
    github: null,
    canvaExport: null,
    voiceAutoplay: false,
    lastVoiceAnswer: '',
};

const remoteElements = {
    user: document.querySelector('#remote-user'),
    connection: document.querySelector('#remote-connection'),
    form: document.querySelector('#remote-form'),
    task: document.querySelector('#remote-task'),
    voiceInput: document.querySelector('#remote-voice-input'),
    voiceCommand: document.querySelector('#remote-voice-command'),
    voiceAutoRead: document.querySelector('#remote-voice-auto-read'),
    voiceStatus: document.querySelector('#remote-voice-status'),
    worktree: document.querySelector('#remote-worktree'),
    project: document.querySelector('#remote-project'),
    mode: document.querySelector('#remote-mode'),
    submit: document.querySelector('#remote-submit'),
    error: document.querySelector('#remote-error'),
    run: document.querySelector('#remote-run'),
    runTitle: document.querySelector('#remote-run-title'),
    status: document.querySelector('#remote-status'),
    progress: document.querySelector('#remote-progress'),
    trace: document.querySelector('#remote-trace'),
    approval: document.querySelector('#remote-approval'),
    approvalTitle: document.querySelector('#remote-approval-title'),
    approvalSummary: document.querySelector('#remote-approval-summary'),
    approvalPreview: document.querySelector('#remote-approval-preview'),
    approve: document.querySelector('#remote-approve'),
    reject: document.querySelector('#remote-reject'),
    answer: document.querySelector('#remote-answer'),
    answerSpeak: document.querySelector('#remote-answer-speak'),
    continue: document.querySelector('#remote-continue'),
    cancel: document.querySelector('#remote-cancel'),
    logout: document.querySelector('#remote-logout'),
    notifications: document.querySelector('#remote-notifications'),
    newTask: document.querySelector('#remote-new-task'),
    menuToggle: document.querySelector('#remote-menu-toggle'),
    menu: document.querySelector('#remote-menu'),
    menuClose: document.querySelector('#remote-menu-close'),
    menuBackdrop: document.querySelector('#remote-menu-backdrop'),
    adminNav: document.querySelector('#remote-admin-nav'),
    adminConsole: document.querySelector('#remote-admin-console'),
    hostStatus: document.querySelector('#remote-host-status'),
    imageStatus: document.querySelector('#remote-image-status'),
    imagePrompt: document.querySelector('#remote-image-prompt'),
    imageOverlayText: document.querySelector('#remote-image-overlay-text'),
    generateImage: document.querySelector('#remote-generate-image'),
    imageDownload: document.querySelector('#remote-image-download'),
    imageExportCanva: document.querySelector('#remote-image-export-canva'),
    imageResult: document.querySelector('#remote-image-result'),
    imageGallery: document.querySelector('#remote-image-gallery'),
    trainingStatus: document.querySelector('#remote-training-status'),
    learningInstruction: document.querySelector('#remote-learning-instruction'),
    learningResponse: document.querySelector('#remote-learning-response'),
    learningTags: document.querySelector('#remote-learning-tags'),
    saveLearningExample: document.querySelector('#remote-save-learning-example'),
    learningEvaluation: document.querySelector('#remote-learning-evaluation'),
    learningTerms: document.querySelector('#remote-learning-terms'),
    saveLearningEvaluation: document.querySelector('#remote-save-learning-evaluation'),
    runLearning: document.querySelector('#remote-run-learning'),
    exportLearning: document.querySelector('#remote-export-learning'),
    backupStatus: document.querySelector('#remote-backup-status'),
    backupPassphrase: document.querySelector('#remote-backup-passphrase'),
    backupConfirmation: document.querySelector('#remote-backup-confirmation'),
    createBackup: document.querySelector('#remote-create-backup'),
    restoreBackup: document.querySelector('#remote-restore-backup'),
    restorePassphrase: document.querySelector('#remote-restore-passphrase'),
    restorePhrase: document.querySelector('#remote-restore-phrase'),
    restoreConfirmation: document.querySelector('#remote-restore-confirmation'),
    restoreBackupButton: document.querySelector('#remote-restore-backup-button'),
    inviteRole: document.querySelector('#remote-invite-role'),
    createInvite: document.querySelector('#remote-create-invite'),
    inviteToken: document.querySelector('#remote-invite-token'),
    githubStatus: document.querySelector('#remote-github-status'),
    githubRefresh: document.querySelector('#remote-github-refresh'),
    githubConnect: document.querySelector('#remote-github-connect'),
    githubCi: document.querySelector('#remote-github-ci'),
    githubPush: document.querySelector('#remote-github-push'),
    githubPr: document.querySelector('#remote-github-pr'),
    githubOutput: document.querySelector('#remote-github-output'),
    adminNotice: document.querySelector('#remote-admin-notice'),
};

const RUN_STORAGE_KEY = 'mycodexai-remote-run';
const VOICE_AUTOPLAY_KEY = 'mycodexai-voice-autoplay';
const ACTIVE_STATUSES = new Set(['queued', 'running', 'cancelling']);
let lastRemoteNotification = '';

function headers(extra = {}) {
    return {
        'X-MyCodexAI-Worktree': remoteState.workspaceId,
        'X-MyCodexAI-Project': remoteState.projectId,
        ...extra,
    };
}

async function legacyRemoteRequest(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: headers({ ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...(options.headers || {}) }),
    });
    const payload = await response.json().catch(() => ({}));
    if (response.status === 401) {
        window.location.assign('/');
        throw new Error('ต้องเข้าสู่ระบบใหม่');
    }
    if (!response.ok) throw new Error(payload.detail || 'ไม่สามารถเชื่อมต่อกับคอมได้');
    return payload;
}

async function request(url, options = {}) {
    const { timeoutMs = 20_000, ...fetchOptions } = options;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
    let response;
    try {
        response = await fetch(url, {
            ...fetchOptions,
            cache: url.startsWith('/api/') ? 'no-store' : fetchOptions.cache,
            signal: controller.signal,
            headers: headers({ ...(fetchOptions.body ? { 'Content-Type': 'application/json' } : {}), ...(fetchOptions.headers || {}) }),
        });
    } catch {
        if (controller.signal.aborted) throw new Error('การเชื่อมต่อหมดเวลา โปรดตรวจอินเทอร์เน็ตแล้วลองใหม่');
        throw new Error('เชื่อมต่อ MyCodexAI ไม่ได้ โปรดตรวจเครือข่ายแล้วลองใหม่');
    } finally {
        window.clearTimeout(timeout);
    }
    const payload = await response.json().catch(() => ({}));
    if (response.status === 401) {
        window.location.assign('/');
        throw new Error('ต้องเข้าสู่ระบบใหม่');
    }
    if (!response.ok) {
        const error = new Error(payload.detail || 'เชื่อมต่อกับคอมไม่ได้');
        error.status = response.status;
        throw error;
    }
    return payload;
}

function setError(message = '', isError = true) {
    remoteElements.error.textContent = message;
    remoteElements.error.hidden = !message;
    remoteElements.error.classList.toggle('remote-notice', Boolean(message) && !isError);
    if (!remoteElements.adminConsole.hidden) {
        remoteElements.adminNotice.textContent = message;
        remoteElements.adminNotice.hidden = !message;
        remoteElements.adminNotice.classList.toggle('is-error', Boolean(message) && isError);
    }
}

function setRemoteMenu(open) {
    const isOpen = Boolean(open);
    remoteElements.menu.classList.toggle('is-open', isOpen);
    remoteElements.menuBackdrop.classList.toggle('is-open', isOpen);
    remoteElements.menu.setAttribute('aria-hidden', String(!isOpen));
    remoteElements.menu.inert = !isOpen;
    remoteElements.menuToggle.setAttribute('aria-expanded', String(isOpen));
    document.body.classList.toggle('remote-menu-open', isOpen);
    if (isOpen) remoteElements.menuClose.focus();
}

function setRemoteVoiceStatus(message) {
    remoteElements.voiceStatus.textContent = message;
}

function syncRemoteVoiceControls() {
    const voice = window.MyCodexVoice;
    try { remoteState.voiceAutoplay = localStorage.getItem(VOICE_AUTOPLAY_KEY) === 'true'; } catch { remoteState.voiceAutoplay = false; }
    if (!voice?.inputSupported) {
        remoteElements.voiceInput.title = 'หากต้องการพูด ให้ใช้ปุ่มไมโครโฟนบนคีย์บอร์ดของอุปกรณ์';
        setRemoteVoiceStatus('ใช้ไมโครโฟนบนคีย์บอร์ดได้');
    }
    if (!voice?.outputSupported) remoteElements.voiceAutoRead.hidden = true;
    remoteElements.voiceAutoRead.classList.toggle('is-active', remoteState.voiceAutoplay);
    remoteElements.voiceAutoRead.setAttribute('aria-pressed', String(remoteState.voiceAutoplay));
}

function speakRemoteAnswer(text) {
    const voice = window.MyCodexVoice;
    if (!voice?.outputSupported) {
        setError('เบราว์เซอร์นี้ยังไม่รองรับการอ่านออกเสียง');
        return;
    }
    voice.speak(text, {
        onStart: () => setRemoteVoiceStatus('MyCodex กำลังอ่านคำตอบ…'),
        onEnd: () => setRemoteVoiceStatus('เสียงพร้อมใช้'),
        onError: (message) => setError(message),
    });
}

function listenForRemoteTask() {
    const voice = window.MyCodexVoice;
    if (!voice?.inputSupported) {
        setRemoteVoiceStatus('ให้ใช้ไมโครโฟนบนคีย์บอร์ดเพื่อพิมพ์เสียงแทน');
        remoteElements.task.focus();
        return;
    }
    if (voice.isListening()) {
        voice.stopListening();
        return;
    }
    const prefix = remoteElements.task.value.trim();
    voice.listen({
        onStart: () => {
            remoteElements.voiceInput.classList.add('is-listening');
            remoteElements.voiceInput.setAttribute('aria-pressed', 'true');
            setRemoteVoiceStatus('กำลังฟัง… พูดได้เลย');
        },
        onTranscript: (transcript, final) => {
            remoteElements.task.value = [prefix, transcript].filter(Boolean).join(prefix && transcript ? ' ' : '');
            remoteElements.task.focus();
            if (final) setRemoteVoiceStatus('ได้ข้อความแล้ว — ตรวจแล้วกดส่ง');
        },
        onEnd: () => {
            remoteElements.voiceInput.classList.remove('is-listening');
            remoteElements.voiceInput.setAttribute('aria-pressed', 'false');
        },
        onError: (message) => { setRemoteVoiceStatus(message); setError(message); },
    });
}

function listenForRemoteCommand() {
    const voice = window.MyCodexVoice;
    if (!voice?.inputSupported) {
        setRemoteVoiceStatus('ให้ใช้ไมโครโฟนบนคีย์บอร์ดเพื่อพิมพ์คำสั่งแทน');
        remoteElements.task.focus();
        return;
    }
    if (voice.isListening()) {
        voice.stopListening();
        return;
    }
    let submitted = false;
    voice.listen({
        onStart: () => {
            remoteElements.voiceCommand.classList.add('is-listening');
            remoteElements.voiceCommand.setAttribute('aria-pressed', 'true');
            setRemoteVoiceStatus('กำลังฟังคำสั่งสำหรับคอม…');
        },
        onTranscript: async (transcript, final) => {
            if (!final || !transcript || submitted) return;
            submitted = true;
            remoteElements.task.value = transcript;
            remoteElements.mode.value = 'agent';
            setRemoteVoiceStatus('รับคำสั่งแล้ว · กำลังส่งเข้าคอม…');
            await submitTask();
        },
        onEnd: () => {
            remoteElements.voiceCommand.classList.remove('is-listening');
            remoteElements.voiceCommand.setAttribute('aria-pressed', 'false');
        },
        onError: (message) => { setRemoteVoiceStatus(message); setError(message); },
    });
}

function toggleRemoteVoiceAutoplay() {
    remoteState.voiceAutoplay = !remoteState.voiceAutoplay;
    try { localStorage.setItem(VOICE_AUTOPLAY_KEY, String(remoteState.voiceAutoplay)); } catch { /* Preference remains for this session. */ }
    syncRemoteVoiceControls();
    setRemoteVoiceStatus(remoteState.voiceAutoplay ? 'จะอ่านคำตอบของ MyCodex อัตโนมัติ' : 'ปิดการอ่านคำตอบอัตโนมัติ');
}

function setBusy(busy) {
    remoteElements.submit.disabled = busy;
    remoteElements.voiceCommand.disabled = busy;
    remoteElements.worktree.disabled = busy;
    remoteElements.project.disabled = busy;
    remoteElements.mode.disabled = busy;
}

function labelForStatus(status) {
    return {
        queued: 'รอคิวในคอม',
        running: 'กำลังทำงาน',
        awaiting_approval: 'รอการอนุมัติ',
        completed: 'เสร็จแล้ว',
        failed: 'ทำไม่สำเร็จ',
        cancelled: 'ยกเลิกแล้ว',
        cancelling: 'กำลังหยุด',
        needs_input: 'ต้องการคำสั่งใหม่',
    }[status] || status;
}

function saveRun() {
    if (!remoteState.runId) return;
    localStorage.setItem(RUN_STORAGE_KEY, JSON.stringify({
        runId: remoteState.runId,
        workspaceId: remoteState.workspaceId,
        projectId: remoteState.projectId,
    }));
}

function clearSavedRun() {
    localStorage.removeItem(RUN_STORAGE_KEY);
}

function replaceOptions(select, values, selectedId) {
    select.replaceChildren();
    for (const value of values) {
        const option = document.createElement('option');
        option.value = value.id;
        option.textContent = value.label;
        option.selected = value.id === selectedId;
        select.append(option);
    }
}

async function loadProjects() {
    const result = await request('/api/projects');
    const projects = result.projects || [];
    if (!projects.length) throw new Error('ไม่พบ project ใน worktree นี้');
    if (!projects.some((project) => project.id === remoteState.projectId)) {
        remoteState.projectId = projects[0].id;
    }
    replaceOptions(
        remoteElements.project,
        projects.map((project) => ({ id: project.id, label: `${project.id} · ${project.file_count} files` })),
        remoteState.projectId,
    );
}

async function loadAccountAndTargets() {
    const user = await request('/api/auth/me');
    remoteState.user = user;
    remoteElements.user.textContent = `@${user.username}`;
    remoteElements.adminConsole.hidden = user.role !== 'admin';
    remoteElements.adminNav.hidden = user.role !== 'admin';
    const result = await request('/api/worktrees');
    const worktrees = result.worktrees || [];
    if (!worktrees.length) throw new Error('ไม่พบ workspace สำหรับบัญชีนี้');
    if (!worktrees.some((worktree) => worktree.id === remoteState.workspaceId)) {
        remoteState.workspaceId = worktrees[0].id;
    }
    replaceOptions(
        remoteElements.worktree,
        worktrees.map((worktree) => ({ id: worktree.id, label: worktree.is_main ? `${worktree.id} · main` : worktree.id })),
        remoteState.workspaceId,
    );
    await loadProjects();
    remoteElements.connection.textContent = 'เชื่อมต่อกับคอมแล้ว';
    remoteElements.connection.classList.add('ready');
    if (user.role === 'admin') await loadRemoteAdmin();
}

function splitRemoteValues(value) {
    return value.split(',').map((item) => item.trim()).filter(Boolean);
}

function setRemoteButtonBusy(button, busy) {
    button.disabled = busy;
}

async function loadRemoteHostStatus() {
    const status = await request('/api/resilience/status');
    const resource = status.resource_guard || {};
    const memory = resource.measurement_available
        ? `RAM ว่าง ${resource.available_memory_mb} MB`
        : 'Resource guard พร้อม';
    const sandbox = status.sandbox?.ready ? 'sandbox พร้อม' : 'sandbox ต้องตรวจสอบ';
    remoteElements.hostStatus.textContent = `${memory} · ${sandbox} · งานที่กำลังทำ ${status.recovery?.active_runs || 0}`;
}

async function loadRemoteTraining() {
    const overview = await request('/api/learning/overview');
    const latest = overview.latest_evaluation;
    const score = latest ? ` · ล่าสุด ${latest.score_percent}%` : '';
    remoteElements.trainingStatus.textContent = `${overview.example_count} ตัวอย่าง · ${overview.evaluation_count} benchmarks${score}`;
}

function renderRemoteImageGallery(images) {
    remoteElements.imageGallery.replaceChildren();
    for (const image of images) {
        const link = document.createElement('a');
        link.href = image.url;
        link.target = '_blank';
        link.rel = 'noopener';
        const preview = document.createElement('img');
        preview.src = image.url;
        preview.alt = 'รูปที่ MyCodex สร้าง';
        preview.loading = 'lazy';
        link.append(preview);
        remoteElements.imageGallery.append(link);
    }
}

function syncRemoteCanvaExport(images) {
    if (!remoteState.canvaExport && images.length) {
        remoteState.canvaExport = { image_id: images[0].image_id, caption: '' };
    }
    const available = Boolean(remoteState.canvaExport);
    remoteElements.imageExportCanva.hidden = !available;
    remoteElements.imageExportCanva.disabled = !available;
}

function remoteThaiGraphemes(value) {
    if (window.Intl?.Segmenter) {
        return Array.from(new Intl.Segmenter('th', { granularity: 'grapheme' }).segment(value), ({ segment }) => segment);
    }
    return Array.from(value);
}

function wrapRemoteThaiCanvasText(context, value, maxWidth) {
    const lines = [];
    for (const paragraph of value.replace(/\r/g, '').split('\n')) {
        let line = '';
        for (const grapheme of remoteThaiGraphemes(paragraph)) {
            const candidate = line + grapheme;
            if (line && context.measureText(candidate).width > maxWidth) {
                lines.push(line);
                line = grapheme;
            } else {
                line = candidate;
            }
        }
        if (line || !lines.length) lines.push(line);
    }
    return lines.filter(Boolean);
}

function loadRemoteImageForCanvas(url) {
    return new Promise((resolve, reject) => {
        const source = new Image();
        source.onload = () => resolve(source);
        source.onerror = () => reject(new Error('ไม่สามารถเตรียมภาพสำหรับวางข้อความได้'));
        source.src = url;
    });
}

async function composeRemoteThaiOverlay(url, caption) {
    const cleanCaption = caption.trim();
    if (!cleanCaption) return { url, composed: false };
    const source = await loadRemoteImageForCanvas(url);
    const canvas = document.createElement('canvas');
    canvas.width = source.naturalWidth;
    canvas.height = source.naturalHeight;
    const context = canvas.getContext('2d');
    context.drawImage(source, 0, 0);
    const fontSize = Math.max(24, Math.min(72, Math.round(canvas.width * 0.055)));
    const lineHeight = Math.round(fontSize * 1.34);
    const padding = Math.round(fontSize * 0.58);
    context.font = `700 ${fontSize}px "Leelawadee UI", Thonburi, Tahoma, sans-serif`;
    const lines = wrapRemoteThaiCanvasText(context, cleanCaption, canvas.width - (padding * 2));
    const panelHeight = (lines.length * lineHeight) + (padding * 2);
    const top = canvas.height - panelHeight;
    context.fillStyle = 'rgba(8, 12, 20, 0.76)';
    context.fillRect(0, top, canvas.width, panelHeight);
    context.fillStyle = '#ffffff';
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    lines.forEach((line, index) => context.fillText(line, canvas.width / 2, top + padding + (lineHeight * index) + (lineHeight / 2)));
    return { url: canvas.toDataURL('image/png'), composed: true };
}

async function exportRemoteImageForCanva() {
    if (!remoteState.canvaExport) return;
    remoteElements.imageExportCanva.disabled = true;
    try {
        const exportRequest = {
            ...remoteState.canvaExport,
            caption: remoteElements.imageOverlayText.value.trim() || remoteState.canvaExport.caption || '',
        };
        const response = await fetch('/api/images/canva-export', {
            method: 'POST',
            cache: 'no-store',
            headers: headers({ 'Content-Type': 'application/json' }),
            body: JSON.stringify(exportRequest),
        });
        if (!response.ok) {
            const payload = await response.json().catch(() => ({}));
            throw new Error(payload.detail || 'ไม่สามารถส่งออกไฟล์สำหรับ Canva ได้');
        }
        const file = await response.blob();
        const url = URL.createObjectURL(file);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'mycodex-canva-pack.zip';
        link.click();
        window.setTimeout(() => URL.revokeObjectURL(url), 1_000);
        setError('ดาวน์โหลด Canva Pack แล้ว', false);
    } catch (error) {
        setError(error.message);
    } finally {
        remoteElements.imageExportCanva.disabled = false;
    }
}

async function loadRemoteImages() {
    try {
        const [status, gallery] = await Promise.all([
            request('/api/images/status'),
            request('/api/images'),
        ]);
        const quota = status.quota_exempt ? 'ไม่จำกัดจำนวนภาพ' : `เหลือ ${status.remaining_today}/${status.daily_limit} ภาพวันนี้`;
        remoteElements.imageStatus.textContent = `${status.detail} · ${status.model} · ${quota}`;
        remoteElements.generateImage.disabled = !status.configured;
        renderRemoteImageGallery(gallery.images || []);
        syncRemoteCanvaExport(gallery.images || []);
    } catch (error) {
        remoteElements.imageStatus.textContent = `ใช้งานไม่ได้: ${error.message}`;
        remoteElements.generateImage.disabled = true;
    }
}

async function generateRemoteImage() {
    const prompt = remoteElements.imagePrompt.value.trim();
    const overlayText = remoteElements.imageOverlayText.value.trim();
    if (prompt.length < 2) {
        setError('กรุณาอธิบายภาพที่ต้องการก่อน');
        remoteElements.imagePrompt.focus();
        return;
    }
    setRemoteButtonBusy(remoteElements.generateImage, true);
    remoteElements.imageStatus.textContent = 'MyCodex กำลังสร้างภาพ… อาจใช้เวลาประมาณ 10–90 วินาที';
    try {
        const image = await request('/api/images', {
            method: 'POST',
            body: JSON.stringify({ prompt, allow_text: false }),
            timeoutMs: 180_000,
        });
        remoteElements.imagePrompt.value = '';
        remoteElements.imageOverlayText.value = '';
        const display = await composeRemoteThaiOverlay(image.url, overlayText);
        remoteElements.imageResult.src = display.url;
        remoteElements.imageResult.hidden = false;
        remoteElements.imageDownload.href = display.url;
        remoteElements.imageDownload.download = display.composed ? 'mycodex-thai-caption.png' : '';
        remoteElements.imageDownload.hidden = false;
        remoteState.canvaExport = { image_id: image.image_id, caption: overlayText };
        syncRemoteCanvaExport([image]);
        remoteElements.imageStatus.textContent = `สร้างภาพสำเร็จ · ${image.model}`;
        setError('สร้างภาพสำเร็จแล้ว', false);
    } catch (error) {
        remoteElements.imageStatus.textContent = `สร้างภาพไม่สำเร็จ: ${error.message}`;
        setError(error.message);
    } finally {
        await loadRemoteImages();
    }
}

async function saveRemoteLearningExample() {
    const instruction = remoteElements.learningInstruction.value.trim();
    const idealResponse = remoteElements.learningResponse.value.trim();
    if (!instruction || !idealResponse) {
        setError('กรอกคำสั่งตัวอย่างและคำตอบมาตรฐานก่อนบันทึก');
        return;
    }
    setRemoteButtonBusy(remoteElements.saveLearningExample, true);
    try {
        const result = await request('/api/learning/examples', {
            method: 'POST',
            body: JSON.stringify({ instruction, ideal_response: idealResponse, tags: splitRemoteValues(remoteElements.learningTags.value) }),
        });
        remoteElements.learningInstruction.value = '';
        remoteElements.learningResponse.value = '';
        remoteElements.learningTags.value = '';
        setError(`บันทึก Training Example แล้ว · รวม ${result.example_count} ตัวอย่าง`, false);
        await loadRemoteTraining();
    } catch (error) {
        setError(error.message);
    } finally {
        setRemoteButtonBusy(remoteElements.saveLearningExample, false);
    }
}

async function saveRemoteLearningEvaluation() {
    const prompt = remoteElements.learningEvaluation.value.trim();
    const requiredTerms = splitRemoteValues(remoteElements.learningTerms.value);
    if (!prompt || !requiredTerms.length) {
        setError('กรอกโจทย์ Benchmark และคำสำคัญอย่างน้อยหนึ่งคำ');
        return;
    }
    setRemoteButtonBusy(remoteElements.saveLearningEvaluation, true);
    try {
        const result = await request('/api/learning/evaluations', {
            method: 'POST', body: JSON.stringify({ prompt, required_terms: requiredTerms }),
        });
        remoteElements.learningEvaluation.value = '';
        remoteElements.learningTerms.value = '';
        setError(`เพิ่ม Benchmark แล้ว · รวม ${result.evaluation_count} ข้อ`, false);
        await loadRemoteTraining();
    } catch (error) {
        setError(error.message);
    } finally {
        setRemoteButtonBusy(remoteElements.saveLearningEvaluation, false);
    }
}

async function runRemoteLearning() {
    if (!window.confirm('Benchmark จะเรียก Ollama เพื่อวัดผลแบบอ่านอย่างเดียว ต้องการเริ่มหรือไม่?')) return;
    setRemoteButtonBusy(remoteElements.runLearning, true);
    try {
        const report = await request('/api/learning/evaluations/run', { method: 'POST' });
        setError(`Benchmark เสร็จแล้ว · ${report.score_percent}% (${report.passed}/${report.total})`, false);
        await loadRemoteTraining();
    } catch (error) {
        setError(error.message);
    } finally {
        setRemoteButtonBusy(remoteElements.runLearning, false);
    }
}

async function exportRemoteLearning() {
    setRemoteButtonBusy(remoteElements.exportLearning, true);
    try {
        const exported = await request('/api/learning/exports', { method: 'POST' });
        window.location.assign(`/api/learning/exports/${encodeURIComponent(exported.file_name)}`);
    } catch (error) {
        setError(error.message);
    } finally {
        setRemoteButtonBusy(remoteElements.exportLearning, false);
    }
}

function updateRestorePhrase() {
    const backupId = remoteElements.restoreBackup.value;
    remoteElements.restorePhrase.textContent = backupId ? `RESTORE ${backupId}` : 'RESTORE backup-id';
}

async function loadRemoteBackups() {
    const result = await request('/api/resilience/backups');
    remoteState.backups = result.backups || [];
    remoteElements.restoreBackup.replaceChildren();
    if (!remoteState.backups.length) {
        const empty = document.createElement('option');
        empty.textContent = 'ยังไม่มี Backup';
        empty.value = '';
        remoteElements.restoreBackup.append(empty);
        remoteElements.restoreBackup.disabled = true;
        remoteElements.restoreBackupButton.disabled = true;
        remoteElements.backupStatus.textContent = 'ยังไม่มี Backup';
    } else {
        for (const backup of remoteState.backups) {
            const option = document.createElement('option');
            option.value = backup.backup_id;
            option.textContent = `${backup.backup_id} · ${backup.file_count} ไฟล์`;
            remoteElements.restoreBackup.append(option);
        }
        remoteElements.restoreBackup.disabled = false;
        remoteElements.restoreBackupButton.disabled = false;
        remoteElements.backupStatus.textContent = `${remoteState.backups.length} Backup`;
    }
    updateRestorePhrase();
}

async function createRemoteBackup() {
    const passphrase = remoteElements.backupPassphrase.value;
    if (passphrase.length < 16 || passphrase !== remoteElements.backupConfirmation.value) {
        setError('Backup passphrase ต้องยาวอย่างน้อย 16 ตัวอักษรและตรงกันทั้งสองช่อง');
        return;
    }
    setRemoteButtonBusy(remoteElements.createBackup, true);
    try {
        const backup = await request('/api/resilience/backups', { method: 'POST', body: JSON.stringify({ passphrase }) });
        remoteElements.backupPassphrase.value = '';
        remoteElements.backupConfirmation.value = '';
        setError(`สร้าง Backup เข้ารหัสแล้ว · ${backup.file_count} ไฟล์`, false);
        await loadRemoteBackups();
    } catch (error) {
        setError(error.message);
    } finally {
        setRemoteButtonBusy(remoteElements.createBackup, false);
    }
}

async function restoreRemoteBackup() {
    const backupId = remoteElements.restoreBackup.value;
    const confirmation = remoteElements.restoreConfirmation.value.trim();
    if (!backupId || !remoteElements.restorePassphrase.value || confirmation !== `RESTORE ${backupId}`) {
        setError(`กรอก passphrase และพิมพ์ RESTORE ${backupId} ให้ตรงก่อนคืนค่า`);
        return;
    }
    if (!window.confirm('การคืนค่าจะแทน Workspace ปัจจุบันและเก็บจุดคืนค่าก่อนหน้า ต้องการทำต่อหรือไม่?')) return;
    setRemoteButtonBusy(remoteElements.restoreBackupButton, true);
    try {
        await request(`/api/resilience/backups/${encodeURIComponent(backupId)}/restore`, {
            method: 'POST', body: JSON.stringify({ passphrase: remoteElements.restorePassphrase.value, confirmation }),
        });
        window.location.reload();
    } catch (error) {
        setError(error.message);
    } finally {
        setRemoteButtonBusy(remoteElements.restoreBackupButton, false);
    }
}

async function createRemoteInvite() {
    setRemoteButtonBusy(remoteElements.createInvite, true);
    try {
        const invite = await request('/api/auth/invites', { method: 'POST', body: JSON.stringify({ role: remoteElements.inviteRole.value }) });
        remoteElements.inviteToken.textContent = invite.token;
        remoteElements.inviteToken.hidden = false;
        setError('สร้างคำเชิญแล้ว คัดลอกรหัสและส่งผ่านช่องทางที่ปลอดภัย', false);
    } catch (error) {
        setError(error.message);
    } finally {
        setRemoteButtonBusy(remoteElements.createInvite, false);
    }
}

function renderRemoteGitHubStatus(github) {
    remoteState.github = github;
    if (!github.is_git_repository) {
        remoteElements.githubStatus.textContent = 'ยังไม่ใช่ Git repository';
        return;
    }
    const remote = github.is_github_remote ? 'เชื่อม GitHub แล้ว' : 'ยังไม่มี GitHub remote';
    const dirty = github.dirty ? 'มีไฟล์รอ commit' : 'working tree สะอาด';
    remoteElements.githubStatus.textContent = `${remote} · ${github.branch || 'detached'} · ${dirty}`;
}

async function loadRemoteGitHub() {
    try {
        renderRemoteGitHubStatus(await request('/api/integrations/github/status'));
    } catch (error) {
        remoteElements.githubStatus.textContent = `ตรวจ GitHub ไม่สำเร็จ: ${error.message}`;
    }
}

async function executeRemoteGitHubPrepared(prepared) {
    const preview = prepared.preview ? `\n\nPreview:\n${prepared.preview.slice(0, 2000)}` : '';
    if (!window.confirm(`${prepared.summary}${preview}\n\nยืนยันทำรายการนี้หรือไม่?`)) return;
    const result = await request('/api/integrations/github/execute', {
        method: 'POST', body: JSON.stringify({ approval_token: prepared.approval_token }),
    });
    remoteElements.githubOutput.textContent = `${result.summary}${result.output ? `\n\n${result.output}` : ''}`;
    remoteElements.githubOutput.hidden = false;
    setError(result.summary, result.status !== 'ok');
    await loadRemoteGitHub();
}

async function connectRemoteGitHub() {
    const url = window.prompt('GitHub repository URL เช่น https://github.com/owner/repository.git');
    if (!url) return;
    try {
        await executeRemoteGitHubPrepared(await request('/api/integrations/github/remote/prepare', {
            method: 'POST', body: JSON.stringify({ remote: 'origin', url }),
        }));
    } catch (error) {
        setError(error.message);
    }
}

async function createRemoteGitHubCi() {
    try {
        await executeRemoteGitHubPrepared(await request('/api/integrations/github/ci/prepare', { method: 'POST' }));
    } catch (error) {
        setError(error.message);
    }
}

async function pushRemoteGitHub() {
    try {
        await executeRemoteGitHubPrepared(await request('/api/integrations/github/push/prepare', {
            method: 'POST', body: JSON.stringify({ branch: remoteState.github?.branch || '' }),
        }));
    } catch (error) {
        setError(error.message);
    }
}

async function openRemoteGitHubPr() {
    const base = window.prompt('Base branch สำหรับ Pull Request', 'main');
    if (!base) return;
    const title = window.prompt('ชื่อ Pull Request');
    if (!title) return;
    const body = window.prompt('รายละเอียด Pull Request (ไม่บังคับ)', '') || '';
    try {
        await executeRemoteGitHubPrepared(await request('/api/integrations/github/pull-requests/prepare', {
            method: 'POST', body: JSON.stringify({ base, title, body }),
        }));
    } catch (error) {
        setError(error.message);
    }
}

async function loadRemoteAdmin() {
    try {
        await Promise.all([loadRemoteHostStatus(), loadRemoteImages(), loadRemoteTraining(), loadRemoteBackups(), loadRemoteGitHub()]);
    } catch (error) {
        setError(error.message);
    }
}

function previewText(preview) {
    if (!preview) return 'ไม่มีรายละเอียดเพิ่มเติม';
    const text = typeof preview === 'string' ? preview : JSON.stringify(preview, null, 2);
    return text.length > 8_000 ? `${text.slice(0, 8_000)}\n… (ตัดข้อความสำหรับมือถือ)` : text;
}

function renderTrace(trace) {
    remoteElements.trace.replaceChildren();
    for (const item of (trace || []).slice(-6).reverse()) {
        const row = document.createElement('div');
        row.className = 'remote-trace-item';
        const text = document.createElement('strong');
        text.textContent = item.summary || item.tool || 'agent step';
        const status = document.createElement('span');
        status.textContent = item.status || 'ok';
        row.append(text, status);
        remoteElements.trace.append(row);
    }
}

function renderRun(run) {
    remoteElements.run.hidden = false;
    remoteElements.runTitle.textContent = run.task;
    remoteElements.status.dataset.status = run.status;
    remoteElements.status.textContent = labelForStatus(run.status);
    remoteElements.progress.textContent = `ขั้นตอน ${run.progress.completed_steps} จาก ${run.progress.max_steps} · ${labelForStatus(run.status)}`;
    renderTrace(run.trace);

    const pending = run.pending_action;
    remoteElements.approval.hidden = !pending;
    if (pending) {
        remoteElements.approvalTitle.textContent = `${pending.tool} ต้องการการอนุมัติ`;
        remoteElements.approvalSummary.textContent = pending.summary || 'ตรวจสอบรายละเอียดก่อนอนุมัติ';
        remoteElements.approvalPreview.textContent = previewText(pending.preview);
    }

    const answer = run.answer || '';
    remoteElements.answer.hidden = !answer;
    remoteElements.answer.textContent = answer;
    remoteElements.answerSpeak.hidden = !answer;
    if (answer && run.status === 'completed' && remoteState.voiceAutoplay && remoteState.lastVoiceAnswer !== answer) {
        remoteState.lastVoiceAnswer = answer;
        speakRemoteAnswer(answer);
    }
    remoteElements.continue.hidden = run.status !== 'needs_input';
    remoteElements.cancel.hidden = !ACTIVE_STATUSES.has(run.status);
    notifyRemoteRun(run);
}

function notifyRemoteRun(run) {
    const key = `${run.run_id}:${run.status}`;
    if (key === lastRemoteNotification || ACTIVE_STATUSES.has(run.status) || document.visibilityState === 'visible') return;
    lastRemoteNotification = key;
    if (!('Notification' in window) || Notification.permission !== 'granted') return;
    new Notification(
        run.status === 'completed' ? 'MyCodexAI ทำงานเสร็จแล้ว' : 'MyCodexAI ต้องการการตรวจสอบ',
        { body: run.task || 'Agent run updated', icon: '/static/app-icon.svg' },
    );
}

async function enableRemoteNotifications() {
    if (!('Notification' in window)) {
        setError('เบราว์เซอร์นี้ไม่รองรับการแจ้งเตือน');
        return;
    }
    const permission = await Notification.requestPermission();
    remoteElements.notifications.textContent = permission === 'granted' ? 'แจ้งเตือนพร้อม' : 'แจ้งเตือนถูกปิด';
}

function schedulePoll() {
    window.clearTimeout(remoteState.pollTimer);
    if (!remoteState.runId) return;
    remoteState.pollTimer = window.setTimeout(refreshRun, 1_100);
}

async function refreshRun() {
    if (!remoteState.runId) return;
    try {
        const run = await request(`/api/agent/runs/${remoteState.runId}`);
        renderRun(run);
        if (ACTIVE_STATUSES.has(run.status)) schedulePoll();
    } catch (error) {
        clearSavedRun();
        remoteState.runId = null;
        remoteElements.run.hidden = true;
        setError(error.message);
    }
}

async function submitTask(event) {
    event?.preventDefault();
    setError();
    remoteState.lastVoiceAnswer = '';
    setBusy(true);
    try {
        const run = await request('/api/agent/runs', {
            method: 'POST',
            body: JSON.stringify({
                task: remoteElements.task.value.trim(),
                mode: remoteElements.mode.value,
                background: true,
            }),
        });
        remoteState.runId = run.run_id;
        saveRun();
        renderRun(run);
        schedulePoll();
        remoteElements.run.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (error) {
        setError(error.message);
    } finally {
        setBusy(false);
    }
}

async function resumeRun(approve) {
    if (!remoteState.runId) return;
    remoteElements.approve.disabled = true;
    remoteElements.reject.disabled = true;
    try {
        const run = await request(`/api/agent/runs/${remoteState.runId}/resume`, {
            method: 'POST',
            body: JSON.stringify({ approve }),
        });
        renderRun(run);
        schedulePoll();
    } catch (error) {
        setError(error.message);
    } finally {
        remoteElements.approve.disabled = false;
        remoteElements.reject.disabled = false;
    }
}

async function cancelRun() {
    if (!remoteState.runId || !window.confirm('หยุดงานนี้บนคอม? งานที่กำลังคิดอยู่จะจบก่อนแล้วจึงหยุด')) return;
    try {
        const run = await request(`/api/agent/runs/${remoteState.runId}/cancel`, { method: 'POST' });
        renderRun(run);
        schedulePoll();
    } catch (error) {
        setError(error.message);
    }
}

async function continueRun() {
    if (!remoteState.runId) return;
    remoteElements.continue.disabled = true;
    try {
        const run = await request(`/api/agent/runs/${remoteState.runId}/continue`, { method: 'POST' });
        renderRun(run);
        schedulePoll();
    } catch (error) {
        setError(error.message);
    } finally {
        remoteElements.continue.disabled = false;
    }
}

async function logout() {
    try {
        await fetch('/api/auth/logout', { method: 'POST' });
    } finally {
        window.location.assign('/');
    }
}

function restoreRun() {
    try {
        const saved = JSON.parse(localStorage.getItem(RUN_STORAGE_KEY) || 'null');
        if (!saved || !saved.runId) return;
        remoteState.runId = saved.runId;
        remoteState.workspaceId = saved.workspaceId || remoteState.workspaceId;
        remoteState.projectId = saved.projectId || remoteState.projectId;
    } catch {
        clearSavedRun();
    }
}

remoteElements.form.addEventListener('submit', submitTask);
remoteElements.voiceInput.addEventListener('click', listenForRemoteTask);
remoteElements.voiceCommand.addEventListener('click', listenForRemoteCommand);
remoteElements.voiceAutoRead.addEventListener('click', toggleRemoteVoiceAutoplay);
remoteElements.answerSpeak.addEventListener('click', () => speakRemoteAnswer(remoteElements.answer.textContent));
remoteElements.worktree.addEventListener('change', async () => {
    remoteState.workspaceId = remoteElements.worktree.value;
    remoteState.projectId = 'workspace';
    try {
        await loadProjects();
    } catch (error) {
        setError(error.message);
    }
});
remoteElements.project.addEventListener('change', () => { remoteState.projectId = remoteElements.project.value; });
remoteElements.approve.addEventListener('click', () => resumeRun(true));
remoteElements.reject.addEventListener('click', () => resumeRun(false));
remoteElements.continue.addEventListener('click', continueRun);
remoteElements.cancel.addEventListener('click', cancelRun);
remoteElements.logout.addEventListener('click', logout);
remoteElements.notifications.addEventListener('click', enableRemoteNotifications);
remoteElements.newTask.addEventListener('click', () => remoteElements.task.focus());
remoteElements.menuToggle.addEventListener('click', () => setRemoteMenu(true));
remoteElements.menuClose.addEventListener('click', () => setRemoteMenu(false));
remoteElements.menuBackdrop.addEventListener('click', () => setRemoteMenu(false));
remoteElements.menu.addEventListener('click', (event) => {
    if (event.target.closest('a')) setRemoteMenu(false);
});
document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && remoteElements.menu.classList.contains('is-open')) setRemoteMenu(false);
});
remoteElements.saveLearningExample.addEventListener('click', saveRemoteLearningExample);
remoteElements.generateImage.addEventListener('click', generateRemoteImage);
remoteElements.imageExportCanva.addEventListener('click', exportRemoteImageForCanva);
remoteElements.saveLearningEvaluation.addEventListener('click', saveRemoteLearningEvaluation);
remoteElements.runLearning.addEventListener('click', runRemoteLearning);
remoteElements.exportLearning.addEventListener('click', exportRemoteLearning);
remoteElements.createBackup.addEventListener('click', createRemoteBackup);
remoteElements.restoreBackup.addEventListener('change', updateRestorePhrase);
remoteElements.restoreBackupButton.addEventListener('click', restoreRemoteBackup);
remoteElements.createInvite.addEventListener('click', createRemoteInvite);
remoteElements.githubRefresh.addEventListener('click', loadRemoteGitHub);
remoteElements.githubConnect.addEventListener('click', connectRemoteGitHub);
remoteElements.githubCi.addEventListener('click', createRemoteGitHubCi);
remoteElements.githubPush.addEventListener('click', pushRemoteGitHub);
remoteElements.githubPr.addEventListener('click', openRemoteGitHubPr);

(async () => {
    syncRemoteVoiceControls();
    restoreRun();
    try {
        await loadAccountAndTargets();
        if (remoteState.runId) await refreshRun();
    } catch (error) {
        setError(error.message);
        remoteElements.connection.textContent = 'เชื่อมต่อไม่สำเร็จ';
    }
})();
