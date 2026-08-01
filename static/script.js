const state = {
    runId: null,
    currentRun: null,
    busy: false,
    recent: [],
    attachments: [],
    user: null,
    workspaceId: 'main',
    worktrees: [],
    projectId: 'workspace',
    projects: [],
    terminalJob: null,
    terminalPollTimer: null,
    browserQa: null,
    sandbox: null,
    github: null,
    agentPollTimer: null,
    chatMessages: [],
    chatHistoryLoaded: false,
    canvaExport: null,
    voiceAutoplay: false,
    voiceConversationActive: false,
    voiceSpeechQueue: [],
    voiceSpeechActive: false,
    voiceSpeechToken: 0,
    voiceSpeechOnDrained: null,
    voiceStreamBuffer: '',
    voiceCommandRunId: null,
    voiceCommandSpeechKey: '',
};

const elements = {
    welcome: document.querySelector('#welcome'),
    runView: document.querySelector('#run-view'),
    runTitle: document.querySelector('#run-title'),
    runStatus: document.querySelector('#run-status'),
    continueRun: document.querySelector('#continue-run'),
    cancelRun: document.querySelector('#cancel-run'),
    timeline: document.querySelector('#timeline'),
    taskInput: document.querySelector('#task-input'),
    voiceInput: document.querySelector('#voice-input'),
    voiceConversation: document.querySelector('#voice-conversation'),
    voiceCommand: document.querySelector('#voice-command'),
    voiceAutoRead: document.querySelector('#voice-auto-read'),
    voiceStatus: document.querySelector('#voice-status'),
    openAdvancedControls: document.querySelector('#open-advanced-controls'),
    advancedComposer: document.querySelector('#advanced-composer'),
    startButton: document.querySelector('#start-agent'),
    startLabel: document.querySelector('#start-label'),
    approvalPanel: document.querySelector('#approval-panel'),
    approvalTitle: document.querySelector('#approval-title'),
    approvalSummary: document.querySelector('#approval-summary'),
    diffPreview: document.querySelector('#diff-preview'),
    approve: document.querySelector('#approve-action'),
    reject: document.querySelector('#reject-action'),
    recentRuns: document.querySelector('#recent-runs'),
    workspaceSidebar: document.querySelector('#workspace-sidebar'),
    sidebarBackdrop: document.querySelector('#sidebar-backdrop'),
    sidebarMenuToggle: document.querySelector('#sidebar-menu-toggle'),
    sidebarClose: document.querySelector('#sidebar-close'),
    sidebarAccountAnchor: document.querySelector('#sidebar-account-anchor'),
    topbarStatus: document.querySelector('.topbar-status'),
    factRun: document.querySelector('#fact-run'),
    factSteps: document.querySelector('#fact-steps'),
    factMode: document.querySelector('#fact-mode'),
    runMode: document.querySelector('#run-mode'),
    reviewControls: document.querySelector('#review-controls'),
    reviewScope: document.querySelector('#review-scope'),
    reviewTarget: document.querySelector('#review-target'),
    projectPlan: document.querySelector('#project-plan'),
    planName: document.querySelector('#plan-name'),
    planOverview: document.querySelector('#plan-overview'),
    planMilestones: document.querySelector('#plan-milestones'),
    teamPanel: document.querySelector('#team-panel'),
    teamMembers: document.querySelector('#team-members'),
    attachFiles: document.querySelector('#attach-files'),
    attachFolder: document.querySelector('#attach-folder'),
    filePicker: document.querySelector('#file-picker'),
    folderPicker: document.querySelector('#folder-picker'),
    uploadDestination: document.querySelector('#upload-destination'),
    uploadOverwrite: document.querySelector('#upload-overwrite'),
    attachmentList: document.querySelector('#attachment-list'),
    worktreeSelect: document.querySelector('#worktree-select'),
    worktreeBranch: document.querySelector('#worktree-branch'),
    createWorktree: document.querySelector('#create-worktree'),
    projectSelect: document.querySelector('#project-select'),
    projectName: document.querySelector('#project-name'),
    importProjectFolder: document.querySelector('#import-project-folder'),
    importProjectZip: document.querySelector('#import-project-zip'),
    rebuildProjectIndex: document.querySelector('#rebuild-project-index'),
    projectIndexStatus: document.querySelector('#project-index-status'),
    projectMemoryNote: document.querySelector('#project-memory-note'),
    saveProjectMemory: document.querySelector('#save-project-memory'),
    showProjectMemory: document.querySelector('#show-project-memory'),
    projectMemoryList: document.querySelector('#project-memory-list'),
    projectGuidance: document.querySelector('#project-guidance'),
    saveProjectGuidance: document.querySelector('#save-project-guidance'),
    loadProjectGuidance: document.querySelector('#load-project-guidance'),
    projectSkillId: document.querySelector('#project-skill-id'),
    projectSkillName: document.querySelector('#project-skill-name'),
    projectSkillDescription: document.querySelector('#project-skill-description'),
    projectSkillInstructions: document.querySelector('#project-skill-instructions'),
    saveProjectSkill: document.querySelector('#save-project-skill'),
    loadProjectSkills: document.querySelector('#load-project-skills'),
    projectSkillsList: document.querySelector('#project-skills-list'),
    browserQaFile: document.querySelector('#browser-qa-file'),
    captureBrowserQa: document.querySelector('#capture-browser-qa'),
    browserQaResult: document.querySelector('#browser-qa-result'),
    browserQaMeta: document.querySelector('#browser-qa-meta'),
    browserQaScreenshot: document.querySelector('#browser-qa-screenshot'),
    projectFolderPicker: document.querySelector('#project-folder-picker'),
    projectZipPicker: document.querySelector('#project-zip-picker'),
    terminalCommand: document.querySelector('#terminal-command'),
    terminalDirectory: document.querySelector('#terminal-directory'),
    startTerminal: document.querySelector('#start-terminal'),
    terminalStatus: document.querySelector('#terminal-status'),
    sandboxStatus: document.querySelector('#sandbox-status'),
    terminalApproval: document.querySelector('#terminal-approval'),
    terminalApprovalText: document.querySelector('#terminal-approval-text'),
    approveTerminal: document.querySelector('#approve-terminal'),
    rejectTerminal: document.querySelector('#reject-terminal'),
    terminalOutput: document.querySelector('#terminal-output'),
    cancelTerminal: document.querySelector('#cancel-terminal'),
    currentUser: document.querySelector('#current-user'),
    setupMfa: document.querySelector('#setup-mfa'),
    recoveryCodes: document.querySelector('#recovery-codes'),
    socialLinkActions: document.querySelector('#social-link-actions'),
    linkGoogle: document.querySelector('#link-google'),
    linkGithub: document.querySelector('#link-github'),
    logout: document.querySelector('#logout'),
    adminPanel: document.querySelector('#admin-panel'),
    inviteRole: document.querySelector('#invite-role'),
    createInvite: document.querySelector('#create-invite'),
    inviteToken: document.querySelector('#invite-token'),
    usageSummary: document.querySelector('#usage-summary'),
    activitySummary: document.querySelector('#activity-summary'),
    enableNotifications: document.querySelector('#enable-notifications'),
    resilienceStatus: document.querySelector('#resilience-status'),
    createBackup: document.querySelector('#create-backup'),
    restoreBackup: document.querySelector('#restore-backup'),
    deviceSessions: document.querySelector('#device-sessions'),
    revokeOtherSessions: document.querySelector('#revoke-other-sessions'),
    learningPanel: document.querySelector('#learning-panel'),
    learningStatus: document.querySelector('#learning-status'),
    learningInstruction: document.querySelector('#learning-instruction'),
    learningIdealResponse: document.querySelector('#learning-ideal-response'),
    learningTags: document.querySelector('#learning-tags'),
    saveLearningExample: document.querySelector('#save-learning-example'),
    learningEvalPrompt: document.querySelector('#learning-eval-prompt'),
    learningEvalTerms: document.querySelector('#learning-eval-terms'),
    saveLearningEval: document.querySelector('#save-learning-eval'),
    runLearningEvals: document.querySelector('#run-learning-evals'),
    exportLearningJsonl: document.querySelector('#export-learning-jsonl'),
    imageStudio: document.querySelector('#image-studio'),
    imageStatus: document.querySelector('#image-status'),
    imagePrompt: document.querySelector('#image-prompt'),
    imageOverlayText: document.querySelector('#image-overlay-text'),
    generateImage: document.querySelector('#generate-image'),
    imageResult: document.querySelector('#image-result'),
    imageDownload: document.querySelector('#image-download'),
    imageExportCanva: document.querySelector('#image-export-canva'),
    imageGallery: document.querySelector('#image-gallery'),
    githubStatus: document.querySelector('#github-status'),
    refreshGithub: document.querySelector('#refresh-github'),
    connectGithub: document.querySelector('#connect-github'),
    createGithubCi: document.querySelector('#create-github-ci'),
    pushGithub: document.querySelector('#push-github'),
    openGithubPr: document.querySelector('#open-github-pr'),
    githubOutput: document.querySelector('#github-output'),
    toast: document.querySelector('#toast'),
};

let lastRunNotification = '';

function escapeText(value) {
    return String(value ?? '');
}

function shortId(runId) {
    return runId ? `${runId.slice(0, 8)}…` : '—';
}

function formatStatus(status) {
    const labels = {
        idle: 'พร้อมเริ่ม',
        queued: 'รอคิว Ollama',
        running: 'กำลังทำงาน',
        awaiting_approval: 'รออนุมัติ',
        completed: 'เสร็จแล้ว',
        failed: 'ทำงานไม่สำเร็จ',
        cancelled: 'ยกเลิกแล้ว',
        cancelling: 'กำลังหยุด',
        needs_input: 'ต้องการข้อมูลงานเพิ่ม',
    };
    return labels[status] || status;
}

function formatToolName(tool) {
    const labels = {
        list_files: 'ดูรายการไฟล์',
        inspect_project: 'สำรวจโปรเจกต์',
        find_code: 'ค้นหาโค้ดที่เกี่ยวข้อง',
        search_code: 'ค้นหาโค้ด',
        read_file: 'อ่านไฟล์',
        read_project_guidance: 'อ่านคำแนะนำโปรเจกต์',
        list_project_skills: 'ดู Project Skills',
        read_project_skill: 'อ่าน Project Skill',
        set_project_plan: 'บันทึกแผนงาน',
        write_file: 'เขียนไฟล์',
        write_files: 'เขียนชุดไฟล์',
        run_project_command: 'รันคำสั่งโปรเจกต์',
        run_tests: 'รันทดสอบ',
        git_status: 'ตรวจสอบ Git',
        git_diff: 'ตรวจสอบ Git diff',
        git_initialize: 'เริ่มต้น Git',
        git_commit: 'สร้าง Git commit',
        capture_browser_qa: 'ตรวจหน้าเว็บ',
        final: 'สรุปผล',
    };
    return labels[tool] || tool || 'agent';
}

function toast(message, isError = false) {
    elements.toast.textContent = message;
    elements.toast.classList.toggle('error', isError);
    elements.toast.classList.add('show');
    window.clearTimeout(toast.timer);
    toast.timer = window.setTimeout(() => elements.toast.classList.remove('show'), 3600);
}

const VOICE_AUTOPLAY_KEY = 'mycodexai-voice-autoplay';

function setVoiceStatus(message) {
    if (elements.voiceStatus) elements.voiceStatus.textContent = message;
}

function syncVoiceControls() {
    const voice = window.MyCodexVoice;
    try { state.voiceAutoplay = localStorage.getItem(VOICE_AUTOPLAY_KEY) === 'true'; } catch { state.voiceAutoplay = false; }
    if (!voice?.inputSupported) {
        elements.voiceInput.title = 'หากต้องการพูด ให้ใช้ปุ่มไมโครโฟนบนคีย์บอร์ดของอุปกรณ์';
        setVoiceStatus('ใช้ไมโครโฟนบนคีย์บอร์ดได้');
    }
    if (!voice?.outputSupported) elements.voiceAutoRead.hidden = true;
    elements.voiceAutoRead.classList.toggle('is-active', state.voiceAutoplay);
    elements.voiceAutoRead.setAttribute('aria-pressed', String(state.voiceAutoplay));
    syncVoiceConversation();
}

function syncVoiceConversation() {
    const isChat = elements.runMode.value === 'chat';
    if (!isChat && state.voiceConversationActive) stopVoiceConversation();
    elements.voiceConversation.hidden = !isChat;
    elements.voiceConversation.classList.toggle('is-active', state.voiceConversationActive);
    elements.voiceConversation.setAttribute('aria-pressed', String(state.voiceConversationActive));
    elements.voiceConversation.textContent = state.voiceConversationActive ? '■ หยุดคุยเสียง' : '◉ คุยด้วยเสียง';
}

function clearVoiceSpeech() {
    state.voiceSpeechToken += 1;
    state.voiceSpeechQueue = [];
    state.voiceSpeechActive = false;
    state.voiceSpeechOnDrained = null;
    state.voiceStreamBuffer = '';
    window.MyCodexVoice?.stopSpeaking();
}

function finishVoiceSpeechQueue() {
    if (state.voiceSpeechActive || state.voiceSpeechQueue.length) return;
    const onDrained = state.voiceSpeechOnDrained;
    state.voiceSpeechOnDrained = null;
    setVoiceStatus('เสียงพร้อมใช้');
    onDrained?.();
}

function pumpVoiceSpeechQueue() {
    if (state.voiceSpeechActive) return;
    const voice = window.MyCodexVoice;
    if (!voice?.outputSupported) {
        state.voiceSpeechQueue = [];
        finishVoiceSpeechQueue();
        return;
    }
    const next = state.voiceSpeechQueue.shift();
    if (!next) {
        finishVoiceSpeechQueue();
        return;
    }
    state.voiceSpeechActive = true;
    const token = ++state.voiceSpeechToken;
    const started = voice.speak(next, {
        onStart: () => setVoiceStatus('MyCodex กำลังตอบด้วยเสียง…'),
        onEnd: () => {
            if (token !== state.voiceSpeechToken) return;
            state.voiceSpeechActive = false;
            pumpVoiceSpeechQueue();
        },
        onError: (message) => {
            if (token !== state.voiceSpeechToken) return;
            state.voiceSpeechActive = false;
            state.voiceSpeechQueue = [];
            setVoiceStatus(message);
            toast(message, true);
            finishVoiceSpeechQueue();
        },
    });
    if (!started) {
        state.voiceSpeechActive = false;
        pumpVoiceSpeechQueue();
    }
}

function queueVoiceSpeech(text, { onDrained } = {}) {
    const content = String(text || '').trim();
    if (content) state.voiceSpeechQueue.push(content);
    if (onDrained) state.voiceSpeechOnDrained = onDrained;
    pumpVoiceSpeechQueue();
}

function takeVoiceStreamPhrases(final = false) {
    const phrases = [];
    while (state.voiceStreamBuffer) {
        const punctuation = state.voiceStreamBuffer.search(/[.!?…\n]/);
        if (punctuation >= 0) {
            phrases.push(state.voiceStreamBuffer.slice(0, punctuation + 1));
            state.voiceStreamBuffer = state.voiceStreamBuffer.slice(punctuation + 1);
            continue;
        }
        if (!final && state.voiceStreamBuffer.length < 72) break;
        if (final) {
            phrases.push(state.voiceStreamBuffer);
            state.voiceStreamBuffer = '';
            break;
        }
        const windowText = state.voiceStreamBuffer.slice(0, 92);
        const boundary = Math.max(windowText.lastIndexOf(' '), windowText.lastIndexOf('،'));
        const cut = boundary >= 32 ? boundary + 1 : 72;
        phrases.push(state.voiceStreamBuffer.slice(0, cut));
        state.voiceStreamBuffer = state.voiceStreamBuffer.slice(cut);
    }
    return phrases.map((phrase) => phrase.trim()).filter(Boolean);
}

function queueVoiceStreamDelta(delta) {
    state.voiceStreamBuffer += delta;
    takeVoiceStreamPhrases().forEach((phrase) => queueVoiceSpeech(phrase));
}

function finishVoiceStream({ resumeVoice = false } = {}) {
    takeVoiceStreamPhrases(true).forEach((phrase) => queueVoiceSpeech(phrase));
    if (resumeVoice && state.voiceConversationActive) {
        state.voiceSpeechOnDrained = () => window.setTimeout(listenForVoiceConversation, 350);
        finishVoiceSpeechQueue();
    }
}

function speakChat(text, { onEnd } = {}) {
    const voice = window.MyCodexVoice;
    if (!voice?.outputSupported) {
        toast('เบราว์เซอร์นี้ยังไม่รองรับการอ่านออกเสียง', true);
        return;
    }
    clearVoiceSpeech();
    queueVoiceSpeech(text, { onDrained: onEnd });
}

function announceVoiceCommandUpdate(run) {
    if (!run || state.voiceCommandRunId !== run.run_id) return;

    const pending = run.pending_action;
    let speechKey = '';
    let message = '';
    if (pending) {
        speechKey = `approval:${pending.action_id || pending.id || pending.tool}:${pending.summary || ''}`;
        message = `ผมต้องขออนุมัติก่อนทำต่อครับ ${pending.summary || `รายการ ${pending.tool}`}`;
    } else if (['completed', 'failed', 'cancelled', 'needs_input'].includes(run.status)) {
        speechKey = `final:${run.status}:${run.answer || ''}`;
        message = run.answer || `งานนี้อยู่ในสถานะ ${formatStatus(run.status)} ครับ`;
    }
    if (!message || speechKey === state.voiceCommandSpeechKey) return;
    state.voiceCommandSpeechKey = speechKey;
    speakChat(message);
}

function stopVoiceConversation() {
    state.voiceConversationActive = false;
    window.MyCodexVoice?.stopListening();
    clearVoiceSpeech();
    elements.voiceConversation.classList.remove('is-listening', 'is-active');
    elements.voiceConversation.setAttribute('aria-pressed', 'false');
    elements.voiceConversation.textContent = '◉ คุยด้วยเสียง';
    setVoiceStatus('ปิดโหมดคุยด้วยเสียงแล้ว');
}

function listenForVoiceConversation() {
    const voice = window.MyCodexVoice;
    if (!state.voiceConversationActive || state.busy) return;
    if (!voice?.inputSupported) {
        stopVoiceConversation();
        toast('เบราว์เซอร์นี้ไม่รองรับการฟังเสียงต่อเนื่อง ใช้ไมโครโฟนบนคีย์บอร์ดแทนได้', true);
        return;
    }
    let submitted = false;
    voice.listen({
        onStart: () => {
            elements.voiceConversation.classList.add('is-listening');
            setVoiceStatus('กำลังฟัง… พูดกับ MyCodex ได้เลย');
        },
        onTranscript: async (transcript, final) => {
            if (!final || !transcript || submitted || !state.voiceConversationActive) return;
            submitted = true;
            elements.taskInput.value = transcript;
            setVoiceStatus('รับข้อความแล้ว · MyCodex กำลังตอบ…');
            await startChat(transcript, { resumeVoice: true });
        },
        onEnd: () => elements.voiceConversation.classList.remove('is-listening'),
        onError: (message) => {
            if (!state.voiceConversationActive) return;
            setVoiceStatus(message);
            toast(message, true);
        },
    });
}

function toggleVoiceConversation() {
    if (state.voiceConversationActive) {
        stopVoiceConversation();
        return;
    }
    if (elements.runMode.value !== 'chat') {
        elements.runMode.value = 'chat';
        syncReviewControls();
    }
    state.voiceConversationActive = true;
    elements.voiceConversation.classList.add('is-active');
    elements.voiceConversation.setAttribute('aria-pressed', 'true');
    elements.voiceConversation.textContent = '■ หยุดคุยเสียง';
    window.speechSynthesis?.getVoices();
    listenForVoiceConversation();
}

function listenForTask() {
    const voice = window.MyCodexVoice;
    if (!voice?.inputSupported) {
        toast('อุปกรณ์นี้ให้ใช้ปุ่มไมโครโฟนบนคีย์บอร์ด เพื่อพิมพ์ข้อความด้วยเสียงแทน', true);
        elements.taskInput.focus();
        return;
    }
    if (voice.isListening()) {
        voice.stopListening();
        return;
    }
    const prefix = elements.taskInput.value.trim();
    const putTranscript = (transcript) => {
        elements.taskInput.value = [prefix, transcript].filter(Boolean).join(prefix && transcript ? ' ' : '');
        elements.taskInput.focus();
    };
    voice.listen({
        onStart: () => {
            elements.voiceInput.classList.add('is-listening');
            elements.voiceInput.setAttribute('aria-pressed', 'true');
            setVoiceStatus('กำลังฟัง… พูดได้เลย');
        },
        onTranscript: (transcript, final) => {
            putTranscript(transcript);
            if (final) setVoiceStatus('ได้ข้อความแล้ว — ตรวจแล้วกดส่ง');
        },
        onEnd: () => {
            elements.voiceInput.classList.remove('is-listening');
            elements.voiceInput.setAttribute('aria-pressed', 'false');
        },
        onError: (message) => {
            setVoiceStatus(message);
            toast(message, true);
        },
    });
}

function listenForComputerCommand() {
    const voice = window.MyCodexVoice;
    if (!voice?.inputSupported) {
        toast('อุปกรณ์นี้ให้ใช้ปุ่มไมโครโฟนบนคีย์บอร์ดเพื่อพิมพ์คำสั่งแทน', true);
        elements.taskInput.focus();
        return;
    }
    if (voice.isListening()) {
        voice.stopListening();
        return;
    }
    let submitted = false;
    voice.listen({
        onStart: () => {
            elements.voiceCommand.classList.add('is-listening');
            elements.voiceCommand.setAttribute('aria-pressed', 'true');
            setVoiceStatus('กำลังฟังคำสั่งสำหรับคอม…');
        },
        onTranscript: async (transcript, final) => {
            if (!final || !transcript || submitted) return;
            submitted = true;
            elements.taskInput.value = transcript;
            elements.runMode.value = 'agent';
            syncReviewControls();
            setVoiceStatus('รับคำสั่งแล้ว · กำลังส่งให้ Agent…');
            const run = await startRun();
            if (run?.run_id) {
                state.voiceCommandRunId = run.run_id;
                state.voiceCommandSpeechKey = '';
                speakChat('รับคำสั่งแล้วครับ กำลังเริ่มทำงานบนคอม');
                announceVoiceCommandUpdate(run);
            }
        },
        onEnd: () => {
            elements.voiceCommand.classList.remove('is-listening');
            elements.voiceCommand.setAttribute('aria-pressed', 'false');
        },
        onError: (message) => { setVoiceStatus(message); toast(message, true); },
    });
}

function toggleVoiceAutoplay() {
    state.voiceAutoplay = !state.voiceAutoplay;
    try { localStorage.setItem(VOICE_AUTOPLAY_KEY, String(state.voiceAutoplay)); } catch { /* Preference remains for this session. */ }
    syncVoiceControls();
    setVoiceStatus(state.voiceAutoplay ? 'จะอ่านคำตอบของ MyCodex อัตโนมัติ' : 'ปิดการอ่านคำตอบอัตโนมัติ');
}

function compactSidebarActive() {
    return window.matchMedia('(max-width: 720px)').matches;
}

function setWorkspaceSidebar(open) {
    const enabled = compactSidebarActive();
    const isOpen = enabled && Boolean(open);
    elements.workspaceSidebar.classList.toggle('is-open', isOpen);
    elements.sidebarBackdrop.classList.toggle('is-open', isOpen);
    elements.workspaceSidebar.inert = enabled && !isOpen;
    elements.sidebarMenuToggle.setAttribute('aria-expanded', String(isOpen));
    document.body.classList.toggle('sidebar-open', isOpen);
    if (isOpen) elements.sidebarClose.focus();
}

function initializeSidebarLayout() {
    if (elements.topbarStatus.parentElement !== elements.sidebarAccountAnchor) {
        elements.sidebarAccountAnchor.append(elements.topbarStatus);
    }
    setWorkspaceSidebar(false);
}

function notifyRunCompletion(run) {
    const key = `${run.run_id}:${run.status}`;
    if (key === lastRunNotification || document.visibilityState === 'visible') return;
    lastRunNotification = key;
    if (!('Notification' in window) || Notification.permission !== 'granted') return;
    const title = run.status === 'completed' ? 'MyCodexAI ทำงานเสร็จแล้ว' : 'MyCodexAI ต้องการการตรวจสอบ';
    new Notification(title, { body: run.task || 'Agent run updated' });
}

async function loadOperations() {
    const [usage, activity] = await Promise.all([
        request('/api/agent/usage'),
        request('/api/agent/activity?limit=1'),
    ]);
    if (usage.quota_exempt) {
        elements.usageSummary.textContent = 'บัญชี Admin: ไม่จำกัดโควตา Agent';
    } else {
        const runLimit = usage.runs_limited ? usage.run_limit : '∞';
        const stepLimit = usage.steps_limited ? usage.step_limit : '∞';
        elements.usageSummary.textContent = `วันนี้: ${usage.runs}/${runLimit} งาน · ${usage.steps}/${stepLimit} ขั้นตอน`;
    }
    const latest = (activity.events || [])[0];
    elements.activitySummary.textContent = latest
        ? `ล่าสุด: ${latest.event}${latest.outcome ? ` · ${latest.outcome}` : ''}`
        : 'ยังไม่มีเหตุการณ์ล่าสุด';
}

function renderGitHubStatus(github) {
    state.github = github;
    elements.githubOutput.hidden = true;
    elements.githubOutput.textContent = '';
    elements.createGithubCi.disabled = state.busy;
    elements.connectGithub.disabled = state.busy || !github.is_git_repository;
    elements.pushGithub.disabled = state.busy || !github.is_github_remote || !github.branch;
    elements.openGithubPr.disabled = state.busy || !github.is_github_remote || !github.branch || !github.github_cli_authenticated;
    if (!github.is_git_repository) {
        elements.githubStatus.textContent = 'ยังไม่ใช่ Git repository — ให้ Agent Initialize Git และ commit baseline ก่อน';
        return;
    }
    const repository = github.repository ? ` · ${github.repository}` : '';
    const remote = github.is_github_remote ? 'เชื่อม GitHub แล้ว' : 'ยังไม่มี GitHub remote';
    const dirty = github.dirty ? 'มีไฟล์ที่ยังไม่ commit' : 'working tree สะอาด';
    const ci = github.ci_workflow_present ? 'CI workflow พร้อม' : `ยังไม่มี CI (${github.ci_kind})`;
    const gh = github.github_cli_available
        ? (github.github_cli_authenticated ? 'gh พร้อมเปิด PR' : 'ติดตั้ง gh แล้ว แต่ยังไม่ได้ sign in')
        : 'ยังไม่ได้ติดตั้ง GitHub CLI';
    elements.githubStatus.textContent = `${remote}${repository} · ${github.branch || 'detached HEAD'} · ${dirty} · ${ci} · ${gh}`;
}

async function loadGitHubStatus() {
    try {
        renderGitHubStatus(await request('/api/integrations/github/status'));
    } catch (error) {
        elements.githubStatus.textContent = `ตรวจ GitHub ไม่สำเร็จ: ${error.message}`;
        elements.pushGithub.disabled = true;
        elements.openGithubPr.disabled = true;
    }
}

async function executeGitHubPrepared(prepared) {
    const preview = prepared.preview ? `\n\nPreview:\n${prepared.preview.slice(0, 2000)}` : '';
    if (!window.confirm(`${prepared.summary}${preview}\n\nยืนยันทำรายการนี้หรือไม่?`)) return null;
    const result = await request('/api/integrations/github/execute', {
        method: 'POST',
        body: JSON.stringify({ approval_token: prepared.approval_token }),
    });
    elements.githubOutput.textContent = `${result.summary}${result.output ? `\n\n${result.output}` : ''}`;
    elements.githubOutput.hidden = false;
    await loadGitHubStatus();
    toast(result.summary, result.status !== 'ok');
    return result;
}

async function createGitHubCi() {
    elements.createGithubCi.disabled = true;
    try {
        const prepared = await request('/api/integrations/github/ci/prepare', { method: 'POST' });
        await executeGitHubPrepared(prepared);
    } catch (error) {
        toast(error.message, true);
    } finally {
        await loadGitHubStatus();
    }
}

async function connectGitHub() {
    const url = window.prompt('GitHub repository URL เช่น https://github.com/owner/repository.git');
    if (!url) return;
    elements.connectGithub.disabled = true;
    try {
        const prepared = await request('/api/integrations/github/remote/prepare', {
            method: 'POST',
            body: JSON.stringify({ remote: 'origin', url }),
        });
        await executeGitHubPrepared(prepared);
    } catch (error) {
        toast(error.message, true);
    } finally {
        await loadGitHubStatus();
    }
}

async function pushGitHub() {
    elements.pushGithub.disabled = true;
    try {
        const prepared = await request('/api/integrations/github/push/prepare', {
            method: 'POST',
            body: JSON.stringify({ branch: state.github?.branch || '' }),
        });
        await executeGitHubPrepared(prepared);
    } catch (error) {
        toast(error.message, true);
    } finally {
        await loadGitHubStatus();
    }
}

async function openGitHubPr() {
    const base = window.prompt('Base branch สำหรับ Pull Request', 'main');
    if (!base) return;
    const title = window.prompt('ชื่อ Pull Request');
    if (!title) return;
    const body = window.prompt('รายละเอียด Pull Request (ไม่บังคับ)', '') || '';
    elements.openGithubPr.disabled = true;
    try {
        const prepared = await request('/api/integrations/github/pull-requests/prepare', {
            method: 'POST',
            body: JSON.stringify({ base, title, body }),
        });
        await executeGitHubPrepared(prepared);
    } catch (error) {
        toast(error.message, true);
    } finally {
        await loadGitHubStatus();
    }
}

async function enableNotifications() {
    if (!('Notification' in window)) {
        toast('เบราว์เซอร์นี้ไม่รองรับการแจ้งเตือน', true);
        return;
    }
    const result = await Notification.requestPermission();
    toast(result === 'granted' ? 'เปิดแจ้งเตือนแล้ว' : 'ยังไม่ได้อนุญาตการแจ้งเตือน', result !== 'granted');
}

async function loadResilience() {
    try {
        const status = await request('/api/resilience/status');
        const resource = status.resource_guard || {};
        const memory = resource.measurement_available
            ? `RAM ว่าง ${resource.available_memory_mb} MB${resource.constrained ? ' · รอทรัพยากรก่อนเริ่มงานหนัก' : ''}`
            : 'กำลังใช้ resource guard แบบตั้งค่า';
        const sandbox = status.sandbox?.ready ? 'sandbox พร้อม' : 'sandbox ต้องตรวจสอบ';
        elements.resilienceStatus.textContent = `${memory} · ${sandbox} · งานที่กำลังทำ ${status.recovery?.active_runs || 0}`;
    } catch (error) {
        elements.resilienceStatus.textContent = `ตรวจสถานะไม่สำเร็จ: ${error.message}`;
    }
}

async function createEncryptedBackup() {
    const passphrase = window.prompt('ตั้ง Backup passphrase ใหม่อย่างน้อย 16 ตัวอักษร (ระบบจะไม่เก็บหรือกู้คืนให้):');
    if (!passphrase) return;
    const confirmation = window.prompt('พิมพ์ passphrase เดิมอีกครั้งเพื่อยืนยัน:');
    if (passphrase !== confirmation) {
        toast('Backup passphrase ไม่ตรงกัน', true);
        return;
    }
    elements.createBackup.disabled = true;
    try {
        const backup = await request('/api/resilience/backups', { method: 'POST', body: JSON.stringify({ passphrase }) });
        toast(`สร้าง Backup เข้ารหัสแล้ว · ${backup.file_count} ไฟล์`);
    } catch (error) {
        toast(error.message, true);
    } finally {
        elements.createBackup.disabled = false;
    }
}

async function restoreLatestBackup() {
    try {
        const result = await request('/api/resilience/backups');
        const latest = (result.backups || [])[0];
        if (!latest) {
            toast('ยังไม่มี Backup สำหรับบัญชีนี้', true);
            return;
        }
        const backupId = window.prompt('ระบุ Backup ที่ต้องการคืนค่า:', latest.backup_id);
        if (!backupId) return;
        const passphrase = window.prompt('กรอก Backup passphrase:');
        if (!passphrase) return;
        const confirmation = window.prompt(`การคืนค่าจะแทน workspace ปัจจุบัน\nพิมพ์ RESTORE ${backupId} เพื่อยืนยัน:`);
        if (!confirmation) return;
        elements.restoreBackup.disabled = true;
        const restored = await request(`/api/resilience/backups/${encodeURIComponent(backupId)}/restore`, {
            method: 'POST',
            body: JSON.stringify({ passphrase, confirmation }),
        });
        toast(`คืนค่า workspace แล้ว · เก็บจุดคืนค่าก่อนหน้า ${restored.restore_point}`);
        window.location.reload();
    } catch (error) {
        toast(error.message, true);
    } finally {
        elements.restoreBackup.disabled = false;
    }
}

function renderSessions(sessions) {
    elements.deviceSessions.replaceChildren();
    for (const session of sessions || []) {
        const row = document.createElement('div');
        row.className = 'device-session';
        const label = document.createElement('span');
        label.textContent = `${session.device_label}${session.current ? ' · อุปกรณ์นี้' : ''}`;
        const seen = document.createElement('small');
        seen.textContent = `ใช้งานล่าสุด ${new Date(session.last_seen_at).toLocaleString()}`;
        row.append(label, seen);
        elements.deviceSessions.append(row);
    }
    if (!sessions?.length) elements.deviceSessions.textContent = 'ไม่พบ session ที่ใช้งานอยู่';
}

async function loadSessions() {
    try {
        renderSessions((await request('/api/auth/sessions')).sessions);
    } catch (error) {
        elements.deviceSessions.textContent = `โหลดอุปกรณ์ไม่สำเร็จ: ${error.message}`;
    }
}

async function revokeOtherSessions() {
    if (!window.confirm('จะออกจากระบบ MyCodexAI บนอุปกรณ์อื่นทั้งหมด โดยคงอุปกรณ์นี้ไว้ ต้องการทำต่อหรือไม่?')) return;
    try {
        const result = await request('/api/auth/sessions/revoke-others', { method: 'POST' });
        toast(`ออกจากอุปกรณ์อื่นแล้ว ${result.revoked} รายการ`);
        await loadSessions();
    } catch (error) {
        toast(error.message, true);
    }
}

async function showRecoveryCodes() {
    const code = window.prompt('กรอกรหัส 6 หลักจาก Authenticator เพื่อสร้าง Recovery Codes ใหม่:');
    if (!code) return;
    try {
        const result = await request('/api/auth/mfa/recovery-codes', { method: 'POST', body: JSON.stringify({ code }) });
        window.prompt('คัดลอกรหัสต่อไปนี้เก็บไว้ใน password manager (รหัสเก่าจะใช้ไม่ได้):', result.codes.join('\n'));
        toast('สร้าง Recovery Codes ใหม่แล้ว');
    } catch (error) {
        toast(error.message, true);
    }
}

async function loadLearning() {
    try {
        const overview = await request('/api/learning/overview');
        const latest = overview.latest_evaluation;
        const score = latest ? ` · ล่าสุด ${latest.score_percent}% (${latest.passed}/${latest.total})` : '';
        elements.learningStatus.textContent = `${overview.example_count} ตัวอย่าง · ${overview.evaluation_count} benchmarks${score}`;
    } catch (error) {
        elements.learningStatus.textContent = `โหลด Training Pipeline ไม่สำเร็จ: ${error.message}`;
    }
}

function renderImageGallery(images) {
    elements.imageGallery.replaceChildren();
    for (const image of images) {
        const link = document.createElement('a');
        link.href = image.url;
        link.target = '_blank';
        link.rel = 'noopener';
        link.title = 'เปิดภาพที่สร้าง';
        const preview = document.createElement('img');
        preview.src = image.url;
        preview.alt = 'รูปที่ MyCodex สร้าง';
        preview.loading = 'lazy';
        link.append(preview);
        elements.imageGallery.append(link);
    }
}

function syncCanvaExport(images) {
    if (!state.canvaExport && images.length) {
        state.canvaExport = { image_id: images[0].image_id, caption: '' };
    }
    const available = Boolean(state.canvaExport);
    elements.imageExportCanva.hidden = !available;
    elements.imageExportCanva.disabled = !available;
}

function thaiGraphemes(value) {
    if (window.Intl?.Segmenter) {
        return Array.from(new Intl.Segmenter('th', { granularity: 'grapheme' }).segment(value), ({ segment }) => segment);
    }
    return Array.from(value);
}

function wrapThaiCanvasText(context, value, maxWidth) {
    const lines = [];
    for (const paragraph of value.replace(/\r/g, '').split('\n')) {
        let line = '';
        for (const grapheme of thaiGraphemes(paragraph)) {
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

function loadImageForCanvas(url) {
    return new Promise((resolve, reject) => {
        const source = new Image();
        source.onload = () => resolve(source);
        source.onerror = () => reject(new Error('ไม่สามารถเตรียมภาพสำหรับวางข้อความได้'));
        source.src = url;
    });
}

async function composeThaiOverlay(url, caption) {
    const cleanCaption = caption.trim();
    if (!cleanCaption) return { url, composed: false };
    const source = await loadImageForCanvas(url);
    const canvas = document.createElement('canvas');
    canvas.width = source.naturalWidth;
    canvas.height = source.naturalHeight;
    const context = canvas.getContext('2d');
    context.drawImage(source, 0, 0);
    const fontSize = Math.max(24, Math.min(72, Math.round(canvas.width * 0.055)));
    const lineHeight = Math.round(fontSize * 1.34);
    const padding = Math.round(fontSize * 0.58);
    context.font = `700 ${fontSize}px "Leelawadee UI", Thonburi, Tahoma, sans-serif`;
    const lines = wrapThaiCanvasText(context, cleanCaption, canvas.width - (padding * 2));
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

async function exportImageForCanva() {
    if (!state.canvaExport) return;
    elements.imageExportCanva.disabled = true;
    try {
        const exportRequest = {
            ...state.canvaExport,
            caption: elements.imageOverlayText.value.trim() || state.canvaExport.caption || '',
        };
        const response = await fetch('/api/images/canva-export', {
            method: 'POST',
            cache: 'no-store',
            headers: {
                'Content-Type': 'application/json',
                'X-MyCodexAI-Worktree': state.workspaceId,
                'X-MyCodexAI-Project': state.projectId,
            },
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
        toast('ดาวน์โหลด Canva Pack แล้ว');
    } catch (error) {
        toast(error.message, true);
    } finally {
        elements.imageExportCanva.disabled = false;
    }
}

async function loadImageStudio() {
    try {
        const [status, gallery] = await Promise.all([
            request('/api/images/status'),
            request('/api/images'),
        ]);
        const quota = status.quota_exempt ? 'ไม่จำกัดจำนวนภาพ' : `เหลือ ${status.remaining_today}/${status.daily_limit} ภาพวันนี้`;
        elements.imageStatus.textContent = `${status.detail} · ${status.model} · ${quota}`;
        elements.generateImage.disabled = !status.configured;
        renderImageGallery(gallery.images || []);
        syncCanvaExport(gallery.images || []);
    } catch (error) {
        elements.imageStatus.textContent = `ไม่สามารถใช้งาน Image Studio ได้: ${error.message}`;
        elements.generateImage.disabled = true;
    }
}

async function generateImage() {
    const prompt = elements.imagePrompt.value.trim();
    const overlayText = elements.imageOverlayText.value.trim();
    if (prompt.length < 2) {
        toast('กรุณาอธิบายภาพที่ต้องการก่อน', true);
        elements.imagePrompt.focus();
        return;
    }
    elements.generateImage.disabled = true;
    elements.imageStatus.textContent = 'MyCodex กำลังสร้างภาพ… อาจใช้เวลาประมาณ 10–90 วินาที';
    try {
        const image = await request('/api/images', {
            method: 'POST',
            body: JSON.stringify({ prompt, allow_text: false }),
            timeoutMs: 180_000,
        });
        elements.imagePrompt.value = '';
        elements.imageOverlayText.value = '';
        const display = await composeThaiOverlay(image.url, overlayText);
        elements.imageResult.src = display.url;
        elements.imageResult.hidden = false;
        elements.imageDownload.href = display.url;
        elements.imageDownload.download = display.composed ? 'mycodex-thai-caption.png' : '';
        elements.imageDownload.hidden = false;
        state.canvaExport = { image_id: image.image_id, caption: overlayText };
        syncCanvaExport([image]);
        elements.imageStatus.textContent = `สร้างภาพสำเร็จ · ${image.model}`;
        toast('สร้างภาพสำเร็จแล้ว');
        const gallery = await request('/api/images');
        renderImageGallery(gallery.images || []);
    } catch (error) {
        elements.imageStatus.textContent = `สร้างภาพไม่สำเร็จ: ${error.message}`;
        toast(error.message, true);
    } finally {
        if (state.user?.role === 'admin') await loadImageStudio();
    }
}

function splitLearningValues(value) {
    return value.split(',').map((item) => item.trim()).filter(Boolean);
}

async function saveLearningExample() {
    const instruction = elements.learningInstruction.value.trim();
    const idealResponse = elements.learningIdealResponse.value.trim();
    if (!instruction || !idealResponse) {
        toast('กรอกทั้งคำสั่งตัวอย่างและคำตอบที่ผ่านการตรวจแล้วก่อน', true);
        return;
    }
    elements.saveLearningExample.disabled = true;
    try {
        const result = await request('/api/learning/examples', {
            method: 'POST', body: JSON.stringify({ instruction, ideal_response: idealResponse, tags: splitLearningValues(elements.learningTags.value) }),
        });
        elements.learningInstruction.value = '';
        elements.learningIdealResponse.value = '';
        elements.learningTags.value = '';
        toast(`บันทึก Training Example แล้ว · รวม ${result.example_count} ตัวอย่าง`);
        await loadLearning();
    } catch (error) {
        toast(error.message, true);
    } finally {
        elements.saveLearningExample.disabled = false;
    }
}

async function saveLearningEvaluation() {
    const prompt = elements.learningEvalPrompt.value.trim();
    const requiredTerms = splitLearningValues(elements.learningEvalTerms.value);
    if (!prompt || !requiredTerms.length) {
        toast('กรอกโจทย์ Benchmark และคำสำคัญอย่างน้อยหนึ่งคำ', true);
        return;
    }
    elements.saveLearningEval.disabled = true;
    try {
        const result = await request('/api/learning/evaluations', { method: 'POST', body: JSON.stringify({ prompt, required_terms: requiredTerms }) });
        elements.learningEvalPrompt.value = '';
        elements.learningEvalTerms.value = '';
        toast(`เพิ่ม Benchmark แล้ว · รวม ${result.evaluation_count} ข้อ`);
        await loadLearning();
    } catch (error) {
        toast(error.message, true);
    } finally {
        elements.saveLearningEval.disabled = false;
    }
}

async function runLearningEvaluations() {
    if (!window.confirm('Benchmark จะเรียก Ollama แบบอ่านอย่างเดียวเพื่อวัดผล ต้องการเริ่มหรือไม่?')) return;
    elements.runLearningEvals.disabled = true;
    try {
        const report = await request('/api/learning/evaluations/run', { method: 'POST' });
        toast(`Benchmark เสร็จแล้ว · ${report.score_percent}% (${report.passed}/${report.total})`, report.score_percent < 100);
        await loadLearning();
    } catch (error) {
        toast(error.message, true);
    } finally {
        elements.runLearningEvals.disabled = false;
    }
}

async function exportLearningJsonl() {
    elements.exportLearningJsonl.disabled = true;
    try {
        const exported = await request('/api/learning/exports', { method: 'POST' });
        toast(`Export ${exported.example_count} ตัวอย่างแล้ว กำลังดาวน์โหลด JSONL`);
        window.location.assign(`/api/learning/exports/${encodeURIComponent(exported.file_name)}`);
    } catch (error) {
        toast(error.message, true);
    } finally {
        elements.exportLearningJsonl.disabled = false;
    }
}

function setBusy(busy, label = 'กำลังเริ่ม agent…') {
    state.busy = busy;
    elements.startButton.disabled = busy;
    elements.approve.disabled = busy;
    elements.reject.disabled = busy;
    elements.continueRun.disabled = busy;
    elements.cancelRun.disabled = busy;
    elements.runMode.disabled = busy;
    elements.reviewScope.disabled = busy;
    elements.reviewTarget.disabled = busy;
    elements.attachFiles.disabled = busy;
    elements.attachFolder.disabled = busy;
    elements.worktreeSelect.disabled = busy;
    elements.worktreeBranch.disabled = busy;
    elements.createWorktree.disabled = busy;
    elements.projectSelect.disabled = busy;
    elements.projectName.disabled = busy;
    elements.importProjectFolder.disabled = busy;
    elements.importProjectZip.disabled = busy;
    elements.rebuildProjectIndex.disabled = busy;
    elements.projectMemoryNote.disabled = busy;
    elements.saveProjectMemory.disabled = busy;
    elements.showProjectMemory.disabled = busy;
    elements.projectGuidance.disabled = busy;
    elements.saveProjectGuidance.disabled = busy;
    elements.loadProjectGuidance.disabled = busy;
    elements.projectSkillId.disabled = busy;
    elements.projectSkillName.disabled = busy;
    elements.projectSkillDescription.disabled = busy;
    elements.projectSkillInstructions.disabled = busy;
    elements.saveProjectSkill.disabled = busy;
    elements.loadProjectSkills.disabled = busy;
    elements.browserQaFile.disabled = busy;
    elements.captureBrowserQa.disabled = busy;
    elements.setupMfa.disabled = busy;
    elements.openAdvancedControls.disabled = busy;
    elements.refreshGithub.disabled = busy;
    elements.connectGithub.disabled = busy;
    elements.createGithubCi.disabled = busy;
    elements.pushGithub.disabled = busy;
    elements.openGithubPr.disabled = busy;
    if (elements.generateImage) elements.generateImage.disabled = busy || elements.generateImage.disabled;
    elements.startLabel.textContent = busy ? label : 'ส่ง';
    syncTerminalControls();
}

function syncReviewControls() {
    const isChat = elements.runMode.value === 'chat';
    const isReview = elements.runMode.value === 'review';
    const needsTarget = ['commit', 'branch'].includes(elements.reviewScope.value);
    elements.reviewControls.hidden = !isReview;
    elements.reviewTarget.hidden = !isReview || !needsTarget;
    elements.reviewTarget.required = isReview && needsTarget;
    elements.openAdvancedControls.hidden = isChat;
    elements.advancedComposer.hidden = isChat;
    if (isChat) {
        setAdvancedComposer(false);
        elements.taskInput.placeholder = 'คุยกับ MyCodex…';
        if (!state.chatHistoryLoaded) loadChatHistory().catch((error) => toast(error.message, true));
    } else {
        elements.taskInput.placeholder = 'ถาม วางแผน แก้โค้ด หรือสร้างโปรเจกต์…';
    }
    syncVoiceConversation();
}

async function legacyRequest(url, options = {}) {
    const workspaceHeaders = url.startsWith('/api/auth/')
        ? {}
        : {
            'X-MyCodexAI-Worktree': state.workspaceId,
            'X-MyCodexAI-Project': state.projectId,
        };
    const response = await fetch(url, {
        headers: { 'Content-Type': 'application/json', ...workspaceHeaders, ...(options.headers || {}) },
        ...options,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(payload.detail || 'ไม่สามารถเชื่อมต่อกับ agent ได้');
    }
    return payload;
}

async function legacyLoadAccount() {
    try {
        const user = await request('/api/auth/me');
        state.user = user;
        elements.currentUser.textContent = `@${user.username}`;
        elements.adminPanel.hidden = user.role !== 'admin';
        elements.learningPanel.hidden = user.role !== 'admin';
        const mfa = await request('/api/auth/mfa');
        elements.setupMfa.textContent = mfa.enabled ? 'MFA เปิดแล้ว' : 'ตั้งค่า MFA';
        if (mfa.required && !mfa.enabled) {
            toast('ต้องตั้งค่า MFA ก่อนเปิดใช้งานผ่านโดเมนสาธารณะ', true);
        }
        await loadSocialLinkActions();
        await loadWorktrees();
        await loadProjects();
        await loadProjectSkills();
        await loadSandboxStatus();
        await loadGitHubStatus();
        if (user.role === 'admin') {
            await loadLearning();
        }
    } catch {
        window.location.assign('/');
    }
}

async function request(url, options = {}) {
    const workspaceHeaders = url.startsWith('/api/auth/')
        ? {}
        : {
            'X-MyCodexAI-Worktree': state.workspaceId,
            'X-MyCodexAI-Project': state.projectId,
        };
    const controller = new AbortController();
    const { timeoutMs = 20_000, ...fetchOptions } = options;
    const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
    let response;
    try {
        response = await fetch(url, {
            ...fetchOptions,
            cache: url.startsWith('/api/') ? 'no-store' : fetchOptions.cache,
            signal: controller.signal,
            headers: { 'Content-Type': 'application/json', ...workspaceHeaders, ...(fetchOptions.headers || {}) },
        });
    } catch {
        if (controller.signal.aborted) throw new Error('การเชื่อมต่อหมดเวลา โปรดตรวจอินเทอร์เน็ตแล้วลองใหม่');
        throw new Error('เชื่อมต่อ MyCodexAI ไม่ได้ โปรดตรวจเครือข่ายแล้วลองใหม่');
    } finally {
        window.clearTimeout(timeout);
    }
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        const error = new Error(payload.detail || 'เชื่อมต่อกับ agent ไม่ได้');
        error.status = response.status;
        throw error;
    }
    return payload;
}

async function loadAccount() {
    let user;
    try {
        user = await request('/api/auth/me');
    } catch (error) {
        if (error.status === 401) window.location.assign('/');
        else toast(error.message, true);
        return;
    }

    state.user = user;
    elements.currentUser.textContent = `@${user.username}`;
    elements.adminPanel.hidden = user.role !== 'admin';
    elements.learningPanel.hidden = user.role !== 'admin';
    elements.imageStudio.hidden = false;

    try {
        const mfa = await request('/api/auth/mfa');
        elements.setupMfa.textContent = mfa.enabled ? 'MFA เปิดแล้ว' : 'ตั้งค่า MFA';
        if (mfa.required && !mfa.enabled) toast('ต้องตั้งค่า MFA ก่อนเปิดใช้งานผ่านโดเมนสาธารณะ', true);
    } catch (error) {
        toast(`โหลดสถานะ MFA ไม่สำเร็จ: ${error.message}`, true);
    }

    await loadSocialLinkActions();
    try {
        await loadWorktrees();
        await loadProjects();
        await loadProjectSkills();
    } catch (error) {
        toast(`โหลด Workspace ไม่สำเร็จ: ${error.message}`, true);
    }

    await Promise.allSettled([
        loadSandboxStatus(),
        loadGitHubStatus(),
        ...(user.role === 'admin' ? [loadLearning(), loadImageStudio()] : []),
    ]);
}

async function loadSocialLinkActions() {
    try {
        const result = await request('/api/auth/oauth/providers');
        const providers = result.providers || {};
        const googleEnabled = Boolean(providers.google);
        const githubEnabled = Boolean(providers.github);
        elements.socialLinkActions.hidden = !googleEnabled && !githubEnabled;
        elements.linkGoogle.disabled = !googleEnabled;
        elements.linkGithub.disabled = !githubEnabled;
    } catch {
        elements.socialLinkActions.hidden = true;
    }
}

async function beginSocialLink(provider) {
    try {
        const result = await request(`/api/auth/oauth/${provider}/link/start`, { method: 'POST' });
        window.location.assign(result.authorization_url);
    } catch (error) {
        toast(error.message, true);
    }
}

function renderSandboxStatus(sandbox) {
    state.sandbox = sandbox;
    elements.sandboxStatus.dataset.mode = sandbox.mode;
    if (sandbox.isolated && sandbox.ready) {
        elements.sandboxStatus.textContent = 'Docker sandbox พร้อม: แยก container, ปิด network เป็นค่าเริ่มต้น';
    } else if (sandbox.isolated) {
        elements.sandboxStatus.textContent = `Docker sandbox ยังไม่พร้อม: ${sandbox.reason}`;
    } else {
        elements.sandboxStatus.textContent = 'Host policy: ยังไม่ใช่ OS sandbox — ดูคู่มือติดตั้ง Docker เพื่อแยกการรันจริง';
    }
}

async function loadSandboxStatus() {
    try {
        renderSandboxStatus(await request('/api/sandbox/status'));
    } catch (error) {
        elements.sandboxStatus.dataset.mode = 'error';
        elements.sandboxStatus.textContent = `ตรวจ sandbox ไม่สำเร็จ: ${error.message}`;
    }
}

function resetTaskView() {
    if (state.agentPollTimer) {
        window.clearTimeout(state.agentPollTimer);
        state.agentPollTimer = null;
    }
    state.runId = null;
    state.currentRun = null;
    elements.welcome.hidden = false;
    elements.runView.hidden = true;
    elements.projectPlan.hidden = true;
    elements.teamPanel.hidden = true;
    elements.approvalPanel.hidden = true;
}

function setAdvancedComposer(open) {
    elements.advancedComposer.open = open;
    elements.openAdvancedControls.setAttribute('aria-expanded', String(open));
    elements.openAdvancedControls.textContent = open ? 'ซ่อนการตั้งค่า' : 'การตั้งค่าและเครื่องมือ';
}

function applyComposerShortcut(button) {
    const templates = {
        fix: 'ช่วยตรวจหาสาเหตุของปัญหา แก้โค้ดเฉพาะที่จำเป็น และรอให้ฉันอนุมัติก่อนแก้ไฟล์',
        build: 'สร้างโปรเจกต์ให้ครบตามที่ระบุ วางแผนก่อน ทำเป็นชุดเล็ก ๆ และรออนุมัติก่อนเขียนไฟล์',
        review: 'ตรวจ Git diff สำหรับ bug, security, regression และ test gap พร้อมรายงานเฉพาะประเด็นที่แก้ได้',
    };
    const mode = button.dataset.mode;
    if (mode) {
        elements.runMode.value = mode;
        syncReviewControls();
    }
    if (!elements.taskInput.value.trim() && templates[button.dataset.composerShortcut]) {
        elements.taskInput.value = templates[button.dataset.composerShortcut];
    }
    elements.taskInput.focus();
}

function renderWorktrees() {
    elements.worktreeSelect.replaceChildren();
    state.worktrees.forEach((worktree) => {
        const option = document.createElement('option');
        option.value = worktree.id;
        option.textContent = worktree.is_main ? 'main workspace' : worktree.id;
        elements.worktreeSelect.append(option);
    });

    if (!state.worktrees.some((worktree) => worktree.id === state.workspaceId)) {
        state.workspaceId = 'main';
    }
    elements.worktreeSelect.value = state.workspaceId;
}

async function loadWorktrees() {
    const payload = await request('/api/worktrees');
    state.worktrees = payload.worktrees || [{ id: 'main', is_main: true }];
    renderWorktrees();
}

function renderProjects() {
    elements.projectSelect.replaceChildren();
    state.projects.forEach((project) => {
        const option = document.createElement('option');
        option.value = project.id;
        option.textContent = project.is_workspace ? 'workspace root' : `${project.id} · ${project.file_count} files`;
        elements.projectSelect.append(option);
    });
    if (!state.projects.some((project) => project.id === state.projectId)) {
        state.projectId = 'workspace';
    }
    elements.projectSelect.value = state.projectId;
}

async function loadProjects() {
    const payload = await request('/api/projects');
    state.projects = payload.projects || [{ id: 'workspace', is_workspace: true, file_count: 0 }];
    renderProjects();
}

function renderProjectIndex(index) {
    if (!index) {
        elements.projectIndexStatus.hidden = true;
        return;
    }
    const languages = Object.entries(index.languages || {})
        .slice(0, 4)
        .map(([name, count]) => `${name} ${count}`)
        .join(' · ');
    elements.projectIndexStatus.textContent = `Code Index: ${index.file_count} ไฟล์${index.truncated ? '+' : ''}${languages ? ` · ${languages}` : ''}`;
    elements.projectIndexStatus.hidden = false;
}

async function rebuildProjectIndex() {
    setBusy(true, 'กำลังสร้าง Code Index…');
    try {
        const index = await request('/api/projects/index/rebuild', { method: 'POST' });
        renderProjectIndex(index);
        toast(`สร้าง Code Index แล้ว: ${index.file_count} ไฟล์`);
    } catch (error) {
        toast(error.message, true);
    } finally {
        setBusy(false);
    }
}

function renderProjectMemory(memory) {
    elements.projectMemoryList.replaceChildren();
    const notes = memory?.notes || [];
    const history = memory?.history || [];
    if (!notes.length && !history.length) {
        elements.projectMemoryList.hidden = true;
        return;
    }
    notes.forEach((note) => {
        const item = document.createElement('article');
        item.className = 'project-memory-item';
        const title = document.createElement('strong');
        title.textContent = 'Project note';
        const content = document.createElement('div');
        content.textContent = note.note;
        item.append(title, content);
        elements.projectMemoryList.append(item);
    });
    history.forEach((entry) => {
        const item = document.createElement('article');
        item.className = 'project-memory-item';
        const title = document.createElement('strong');
        title.textContent = `${formatStatus(entry.status)} · ${entry.task}`;
        const content = document.createElement('div');
        content.textContent = entry.answer || entry.tools?.join(' → ') || 'No summary';
        item.append(title, content);
        elements.projectMemoryList.append(item);
    });
    elements.projectMemoryList.hidden = false;
}

async function loadProjectMemory() {
    const memory = await request('/api/projects/memory');
    renderProjectMemory(memory);
}

async function saveProjectMemory() {
    const note = elements.projectMemoryNote.value.trim();
    if (!note) {
        elements.projectMemoryNote.focus();
        toast('กรุณาระบุสิ่งที่ต้องการให้ project จำ', true);
        return;
    }
    elements.saveProjectMemory.disabled = true;
    try {
        await request('/api/projects/memory/notes', {
            method: 'POST',
            body: JSON.stringify({ note }),
        });
        elements.projectMemoryNote.value = '';
        await loadProjectMemory();
        toast('บันทึก Project Memory แล้ว');
    } catch (error) {
        toast(error.message, true);
    } finally {
        syncTerminalControls();
    }
}

async function loadProjectGuidance() {
    const guidance = await request('/api/projects/guidance');
    elements.projectGuidance.value = guidance.custom_content || '';
    return guidance;
}

async function saveProjectGuidance() {
    elements.saveProjectGuidance.disabled = true;
    try {
        await request('/api/projects/guidance', {
            method: 'PUT',
            body: JSON.stringify({ content: elements.projectGuidance.value }),
        });
        toast('บันทึก Project Guidance แล้ว — agent จะใช้กับงานถัดไป');
    } catch (error) {
        toast(error.message, true);
    } finally {
        syncTerminalControls();
    }
}

function clearProjectSkillEditor() {
    elements.projectSkillId.value = '';
    elements.projectSkillName.value = '';
    elements.projectSkillDescription.value = '';
    elements.projectSkillInstructions.value = '';
}

function renderProjectSkills(skills) {
    elements.projectSkillsList.replaceChildren();
    if (!skills?.length) {
        elements.projectSkillsList.hidden = true;
        return;
    }
    skills.forEach((skill) => {
        const item = document.createElement('button');
        item.type = 'button';
        item.className = 'project-skill-item';
        item.textContent = `${skill.id} · ${skill.name} — ${skill.description}`;
        item.addEventListener('click', async () => {
            try {
                const detail = await request(`/api/projects/skills/${encodeURIComponent(skill.id)}`);
                elements.projectSkillId.value = detail.id;
                elements.projectSkillName.value = detail.name;
                elements.projectSkillDescription.value = detail.description;
                elements.projectSkillInstructions.value = detail.instructions || '';
                toast(`โหลด Skill ${detail.name} แล้ว`);
            } catch (error) {
                toast(error.message, true);
            }
        });
        elements.projectSkillsList.append(item);
    });
    elements.projectSkillsList.hidden = false;
}

async function loadProjectSkills() {
    const payload = await request('/api/projects/skills');
    renderProjectSkills(payload.skills || []);
    return payload.skills || [];
}

async function saveProjectSkill() {
    const id = elements.projectSkillId.value.trim();
    const name = elements.projectSkillName.value.trim();
    const description = elements.projectSkillDescription.value.trim();
    const instructions = elements.projectSkillInstructions.value.trim();
    if (!id || !name || !description || !instructions) {
        toast('กรอก id, ชื่อ, คำอธิบาย และขั้นตอนของ Skill ให้ครบ', true);
        return;
    }
    elements.saveProjectSkill.disabled = true;
    try {
        const skill = await request(`/api/projects/skills/${encodeURIComponent(id)}`, {
            method: 'PUT',
            body: JSON.stringify({ name, description, instructions }),
        });
        await loadProjectSkills();
        toast(`บันทึก Skill ${skill.name} แล้ว — agent จะใช้กับงานถัดไปเมื่อ task ตรงกัน`);
    } catch (error) {
        toast(error.message, true);
    } finally {
        syncTerminalControls();
    }
}

function renderBrowserQa(result) {
    state.browserQa = result || null;
    elements.browserQaResult.hidden = !result;
    if (!result) {
        elements.browserQaMeta.textContent = '';
        elements.browserQaScreenshot.removeAttribute('src');
        return;
    }
    const title = result.document_title ? ` · ${result.document_title}` : '';
    elements.browserQaMeta.textContent = `${result.filename} · ${result.viewport_width}×${result.viewport_height}${title}`;
    elements.browserQaScreenshot.src = `${result.screenshot_url}${result.screenshot_url.includes('?') ? '&' : '?'}captured=${encodeURIComponent(result.captured_at)}`;
}

function browserQaScreenshotUrl(captureId) {
    return `/api/projects/browser-qa/${encodeURIComponent(captureId)}/screenshot?worktree=${encodeURIComponent(state.workspaceId)}&project=${encodeURIComponent(state.projectId)}`;
}

async function captureBrowserQa() {
    const filename = elements.browserQaFile.value.trim();
    if (!filename) {
        elements.browserQaFile.focus();
        toast('ระบุไฟล์ HTML ที่ต้องการตรวจ', true);
        return;
    }
    elements.captureBrowserQa.disabled = true;
    try {
        const result = await request('/api/projects/browser-qa/capture', {
            method: 'POST',
            body: JSON.stringify({ filename }),
        });
        renderBrowserQa(result);
        toast('สร้าง Browser QA screenshot แล้ว');
    } catch (error) {
        toast(error.message, true);
    } finally {
        syncTerminalControls();
    }
}

function importNameFromFiles(files) {
    const first = files[0];
    if (!first) return '';
    const path = first.webkitRelativePath || first.name;
    const topLevel = path.split('/')[0] || '';
    return topLevel.replace(/\.zip$/i, '').replace(/[^A-Za-z0-9._-]/g, '-').slice(0, 80);
}

function excludedImportFile(file) {
    const path = (file.webkitRelativePath || file.name).replace(/\\/g, '/');
    const parts = path.split('/').map((part) => part.toLowerCase());
    const filename = parts.at(-1) || '';
    const ignoredDirectories = new Set(['.git', '.mycodexai', '.venv', 'venv', 'node_modules', '__pycache__', 'logs']);
    const ignoredFiles = new Set(['.env', '.env.local', '.env.production', '.env.development', 'id_rsa', 'id_dsa', 'credentials.json']);
    return parts.slice(0, -1).some((part) => ignoredDirectories.has(part))
        || ignoredFiles.has(filename)
        || filename.endsWith('.key')
        || filename.endsWith('.pem')
        || filename.endsWith('.pyc');
}

async function importProject(fileList) {
    const files = [...fileList];
    if (!files.length) return;
    const name = (elements.projectName.value.trim() || importNameFromFiles(files)).replace(/[^A-Za-z0-9._-]/g, '-');
    if (!name || name === 'workspace') {
        toast('กรุณาระบุชื่อ project ที่ปลอดภัย เช่น MyCodexAI', true);
        return;
    }

    const filteredFiles = files.filter((file) => !excludedImportFile(file));
    const clientIgnored = files.length - filteredFiles.length;
    if (!filteredFiles.length) {
        toast('ไม่พบ source file ที่นำเข้าได้หลังตัดไฟล์ที่ถูกละเว้น', true);
        return;
    }

    const form = new FormData();
    form.append('project_name', name);
    filteredFiles.forEach((file) => form.append('files', file, file.webkitRelativePath || file.name));
    setBusy(true, 'กำลังนำเข้า project…');
    try {
        const response = await fetch('/api/projects/import', {
            method: 'POST',
            headers: {
                'X-MyCodexAI-Worktree': state.workspaceId,
                'X-MyCodexAI-Project': 'workspace',
            },
            body: form,
        });
        const project = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(project.detail || 'ไม่สามารถนำเข้า project ได้');
        state.projectId = project.id;
        state.attachments = [];
        renderAttachments();
        renderProjectMemory(null);
        renderBrowserQa(null);
        elements.projectGuidance.value = '';
        clearProjectSkillEditor();
        renderProjectSkills(null);
        elements.projectName.value = '';
        await loadProjects();
        await loadProjectSkills();
        resetTaskView();
        const ignored = clientIgnored + project.ignored_file_count;
        toast(`นำเข้า ${project.id} แล้ว ${project.file_count} ไฟล์${ignored ? ` · ตัด ${ignored} ไฟล์ที่ไม่ปลอดภัย/ไม่จำเป็น` : ''}`);
    } catch (error) {
        toast(error.message, true);
    } finally {
        setBusy(false);
    }
}

async function selectProject() {
    const nextProjectId = elements.projectSelect.value || 'workspace';
    if (nextProjectId === state.projectId) return;
    if (terminalIsActive()) {
        elements.projectSelect.value = state.projectId;
        toast('หยุดหรือรอ Terminal ให้เสร็จก่อนสลับ project', true);
        return;
    }
    state.projectId = nextProjectId;
    state.attachments = [];
    renderAttachments();
    renderProjectMemory(null);
    renderBrowserQa(null);
    elements.projectGuidance.value = '';
    clearProjectSkillEditor();
    renderProjectSkills(null);
    resetTaskView();
    try {
        await loadProjectSkills();
        await loadGitHubStatus();
    } catch (error) {
        toast(error.message, true);
    }
    toast(`สลับไปที่ project ${nextProjectId}`);
}

async function createWorktree() {
    const branch = elements.worktreeBranch.value.trim();
    if (!branch) {
        elements.worktreeBranch.focus();
        toast('กรุณาระบุชื่อ branch เช่น feature/login-page', true);
        return;
    }

    setBusy(true, 'กำลังสร้าง branch workspace…');
    try {
        const worktree = await request('/api/worktrees', {
            method: 'POST',
            body: JSON.stringify({ branch }),
        });
        state.workspaceId = worktree.id;
        state.projectId = 'workspace';
        state.attachments = [];
        renderAttachments();
        renderProjectMemory(null);
        clearProjectSkillEditor();
        renderProjectSkills(null);
        elements.worktreeBranch.value = '';
        await loadWorktrees();
        await loadProjects();
        await loadProjectSkills();
        await loadGitHubStatus();
        resetTaskView();
        toast(`สร้าง ${worktree.id} แล้ว — งานถัดไปจะแยกไฟล์จาก main`);
    } catch (error) {
        toast(error.message, true);
    } finally {
        setBusy(false);
    }
}

async function selectWorktree() {
    const nextWorkspaceId = elements.worktreeSelect.value || 'main';
    if (nextWorkspaceId === state.workspaceId) return;
    if (terminalIsActive()) {
        elements.worktreeSelect.value = state.workspaceId;
        toast('หยุดหรือรอ Terminal ให้เสร็จก่อนสลับ workspace', true);
        return;
    }
    state.workspaceId = nextWorkspaceId;
    state.projectId = 'workspace';
    state.attachments = [];
    renderAttachments();
    renderProjectMemory(null);
    renderBrowserQa(null);
    elements.projectGuidance.value = '';
    clearProjectSkillEditor();
    renderProjectSkills(null);
    resetTaskView();
    try {
        await loadProjects();
        await loadProjectSkills();
        await loadGitHubStatus();
        toast(`สลับไปที่ ${nextWorkspaceId}`);
    } catch (error) {
        toast(error.message, true);
    }
}

function terminalIsActive() {
    return ['awaiting_approval', 'running', 'cancelling'].includes(state.terminalJob?.status);
}

function syncTerminalControls() {
    const active = terminalIsActive();
    const waiting = state.terminalJob?.status === 'awaiting_approval';
    const running = ['running', 'cancelling'].includes(state.terminalJob?.status);
    elements.terminalCommand.disabled = state.busy || active;
    elements.terminalDirectory.disabled = state.busy || active;
    elements.startTerminal.disabled = state.busy || active;
    elements.approveTerminal.disabled = state.busy || !waiting;
    elements.rejectTerminal.disabled = state.busy || !waiting;
    elements.cancelTerminal.disabled = state.busy || !running;
    elements.startButton.disabled = state.busy || active;
    elements.runMode.disabled = state.busy || active;
    elements.attachFiles.disabled = state.busy || active;
    elements.attachFolder.disabled = state.busy || active;
    elements.worktreeSelect.disabled = state.busy || active;
    elements.worktreeBranch.disabled = state.busy || active;
    elements.createWorktree.disabled = state.busy || active;
    elements.projectSelect.disabled = state.busy || active;
    elements.projectName.disabled = state.busy || active;
    elements.importProjectFolder.disabled = state.busy || active;
    elements.importProjectZip.disabled = state.busy || active;
    elements.rebuildProjectIndex.disabled = state.busy || active;
    elements.projectMemoryNote.disabled = state.busy || active;
    elements.saveProjectMemory.disabled = state.busy || active;
    elements.showProjectMemory.disabled = state.busy || active;
    elements.projectGuidance.disabled = state.busy || active;
    elements.saveProjectGuidance.disabled = state.busy || active;
    elements.loadProjectGuidance.disabled = state.busy || active;
    elements.projectSkillId.disabled = state.busy || active;
    elements.projectSkillName.disabled = state.busy || active;
    elements.projectSkillDescription.disabled = state.busy || active;
    elements.projectSkillInstructions.disabled = state.busy || active;
    elements.saveProjectSkill.disabled = state.busy || active;
    elements.loadProjectSkills.disabled = state.busy || active;
    elements.browserQaFile.disabled = state.busy || active;
    elements.captureBrowserQa.disabled = state.busy || active;
    elements.refreshGithub.disabled = state.busy || active;
    elements.connectGithub.disabled = state.busy || active || !state.github?.is_git_repository;
    elements.createGithubCi.disabled = state.busy || active;
    elements.pushGithub.disabled = state.busy || active || !state.github?.is_github_remote;
    elements.openGithubPr.disabled = state.busy || active || !state.github?.is_github_remote || !state.github?.github_cli_authenticated;
}

function parseTerminalCommand(input) {
    const command = input.trim();
    if (!command) throw new Error('กรุณาระบุคำสั่ง เช่น npm test');

    const argumentsList = [];
    let token = '';
    let quote = null;
    for (let index = 0; index < command.length; index += 1) {
        const character = command[index];
        if ((character === '"' || character === "'") && (!quote || quote === character)) {
            quote = quote ? null : character;
            continue;
        }
        if (/\s/.test(character) && !quote) {
            if (token) argumentsList.push(token);
            token = '';
            continue;
        }
        token += character;
    }
    if (quote) throw new Error('คำสั่งมีเครื่องหมาย quote ที่ปิดไม่ครบ');
    if (token) argumentsList.push(token);
    if (!argumentsList.length) throw new Error('กรุณาระบุคำสั่ง');
    return argumentsList;
}

function renderTerminalJob(job) {
    state.terminalJob = job;
    const status = job?.status || 'idle';
    elements.terminalStatus.dataset.status = status;
    const environment = job?.execution_environment;
    elements.terminalStatus.textContent = job ? `${formatStatus(status)}${environment ? ` · ${environment}` : ''}` : 'พร้อมใช้งาน';
    elements.terminalApproval.hidden = status !== 'awaiting_approval';
    elements.cancelTerminal.hidden = !['running', 'cancelling'].includes(status);

    if (job?.status === 'awaiting_approval') {
        elements.terminalApprovalText.textContent = `$ ${job.command.join(' ')}  (ใน ${job.working_directory})`;
    }
    const output = job?.output || job?.reason || '';
    elements.terminalOutput.hidden = !output;
    if (output) {
        elements.terminalOutput.textContent = output;
        elements.terminalOutput.scrollTop = elements.terminalOutput.scrollHeight;
    }

    syncTerminalControls();
    if (['running', 'cancelling'].includes(status)) {
        pollTerminalJob();
    } else {
        window.clearTimeout(state.terminalPollTimer);
        state.terminalPollTimer = null;
    }
}

async function createTerminalJob() {
    let command;
    try {
        command = parseTerminalCommand(elements.terminalCommand.value);
    } catch (error) {
        toast(error.message, true);
        return;
    }

    elements.startTerminal.disabled = true;
    try {
        const job = await request('/api/terminal/jobs', {
            method: 'POST',
            body: JSON.stringify({
                command,
                working_directory: elements.terminalDirectory.value.trim() || '.',
            }),
        });
        renderTerminalJob(job);
        toast('ตรวจคำสั่งแล้ว — กดอนุมัติก่อนเริ่มรัน');
    } catch (error) {
        toast(error.message, true);
        syncTerminalControls();
    }
}

async function resumeTerminalJob(approve) {
    const job = state.terminalJob;
    if (!job) return;
    try {
        const updated = await request(`/api/terminal/jobs/${job.job_id}/resume`, {
            method: 'POST',
            body: JSON.stringify({ approve }),
        });
        renderTerminalJob(updated);
        toast(approve ? 'เริ่มรันคำสั่งแล้ว' : 'ไม่รันคำสั่งนี้');
    } catch (error) {
        toast(error.message, true);
        syncTerminalControls();
    }
}

async function cancelTerminalJob() {
    const job = state.terminalJob;
    if (!job) return;
    try {
        renderTerminalJob({ ...job, status: 'cancelling' });
        const updated = await request(`/api/terminal/jobs/${job.job_id}/cancel`, { method: 'POST' });
        renderTerminalJob(updated);
    } catch (error) {
        toast(error.message, true);
    }
}

async function pollTerminalJob() {
    if (state.terminalPollTimer || !state.terminalJob) return;
    state.terminalPollTimer = window.setTimeout(async () => {
        state.terminalPollTimer = null;
        try {
            const job = await request(`/api/terminal/jobs/${state.terminalJob.job_id}`);
            renderTerminalJob(job);
        } catch (error) {
            toast(`ไม่สามารถอ่าน Terminal: ${error.message}`, true);
        }
    }, 650);
}

async function logout() {
    try {
        await fetch('/api/auth/logout', { method: 'POST' });
    } finally {
        window.location.assign('/');
    }
}

async function setupMfa() {
    setBusy(true, 'กำลังสร้าง MFA secret…');
    try {
        const setup = await request('/api/auth/mfa/setup', { method: 'POST' });
        window.prompt('เพิ่ม secret นี้ในแอป Authenticator แล้วคัดลอกเก็บไว้จนยืนยันเสร็จ:', setup.secret);
        const code = window.prompt('กรอกรหัส 6 หลักจาก Authenticator เพื่อยืนยัน MFA:', '');
        if (code === null) {
            toast('ยกเลิกการยืนยัน MFA แล้ว');
            return;
        }
        const status = await request('/api/auth/mfa/confirm', {
            method: 'POST',
            body: JSON.stringify({ code: code.trim() }),
        });
        elements.setupMfa.textContent = status.enabled ? 'MFA เปิดแล้ว' : 'ตั้งค่า MFA';
        toast('เปิด MFA แล้ว — ครั้งต่อไปให้กรอกรหัส 6 หลักตอนเข้าสู่ระบบ');
    } catch (error) {
        toast(error.message, true);
    } finally {
        setBusy(false);
    }
}

async function createInvite() {
    elements.createInvite.disabled = true;
    try {
        const invite = await request('/api/auth/invites', {
            method: 'POST',
            body: JSON.stringify({ role: elements.inviteRole.value }),
        });
        elements.inviteToken.value = invite.token;
        elements.inviteToken.hidden = false;
        toast('สร้างคำเชิญแล้ว — คัดลอกรหัสและส่งให้ผู้ใช้');
    } catch (error) {
        toast(error.message, true);
    } finally {
        elements.createInvite.disabled = false;
    }
}

function addRecent(run) {
    const item = {
        runId: run.run_id,
        task: run.task,
        status: run.status,
        workspaceId: run.workspace_id || 'main',
        projectId: run.project_id || 'workspace',
        savedAt: Date.now(),
    };
    state.recent = [item, ...state.recent.filter((entry) => entry.runId !== item.runId)].slice(0, 8);
    localStorage.setItem('mycodexai-recent-runs', JSON.stringify(state.recent));
    renderRecent();
}

function loadRecent() {
    try {
        state.recent = JSON.parse(localStorage.getItem('mycodexai-recent-runs') || '[]');
    } catch {
        state.recent = [];
    }
    renderRecent();
}

function renderRecent() {
    elements.recentRuns.replaceChildren();
    if (!state.recent.length) {
        const empty = document.createElement('p');
        empty.className = 'empty-recent';
        empty.textContent = 'ยังไม่มีงานในเบราว์เซอร์นี้';
        elements.recentRuns.append(empty);
        return;
    }

    state.recent.forEach((run) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'recent-run';
        button.title = run.task;
        button.textContent = run.task;
        button.addEventListener('click', () => {
            setWorkspaceSidebar(false);
            loadRun(run.runId, run.workspaceId || 'main', run.projectId || 'workspace');
        });
        elements.recentRuns.append(button);
    });
}

function renderChatConversation() {
    state.runId = null;
    state.currentRun = null;
    if (state.agentPollTimer) {
        window.clearTimeout(state.agentPollTimer);
        state.agentPollTimer = null;
    }

    elements.welcome.hidden = true;
    elements.runView.hidden = false;
    elements.runTitle.textContent = 'คุยกับ MyCodex';
    elements.runStatus.dataset.status = 'completed';
    elements.runStatus.textContent = 'Chat';
    elements.factRun.textContent = 'Chat';
    elements.factSteps.textContent = `${state.chatMessages.length} ข้อความ`;
    elements.factMode.textContent = 'Normal chat · ไม่เข้าถึงไฟล์หรือเครื่องมือ';
    elements.continueRun.hidden = true;
    elements.cancelRun.hidden = true;
    elements.approvalPanel.hidden = true;
    elements.projectPlan.hidden = true;
    elements.teamPanel.hidden = true;
    elements.timeline.replaceChildren();

    if (!state.chatMessages.length) {
        const empty = document.createElement('article');
        empty.className = 'timeline-item chat-message assistant';
        empty.textContent = 'เริ่มคุยได้เลย — โหมดนี้จะไม่เปิดไฟล์ รันคำสั่ง หรือแก้โปรเจกต์';
        elements.timeline.append(empty);
        return;
    }

    state.chatMessages.forEach((message) => {
        const item = document.createElement('article');
        item.className = `timeline-item chat-message ${message.role === 'user' ? 'user' : 'assistant'}${message.pending ? ' pending' : ''}`;
        const title = document.createElement('div');
        title.className = 'timeline-title';
        title.textContent = message.role === 'user' ? 'คุณ' : message.pending ? 'MyCodex · กำลังพิมพ์คำตอบ…' : 'MyCodex';
        const content = document.createElement('p');
        content.className = 'timeline-result';
        content.textContent = message.content;
        item.append(title, content);
        if (message.role === 'assistant' && !message.pending && message.content) {
            const speak = document.createElement('button');
            speak.type = 'button';
            speak.className = 'chat-speak';
            speak.textContent = '🔊 ฟัง';
            speak.setAttribute('aria-label', 'ฟังคำตอบของ MyCodex');
            speak.addEventListener('click', () => speakChat(message.content));
            item.append(speak);
        }
        elements.timeline.append(item);
    });
    elements.timeline.lastElementChild?.scrollIntoView({ block: 'end', behavior: 'smooth' });
}

async function loadChatHistory() {
    const payload = await request('/api/chat/history');
    state.chatMessages = Array.isArray(payload.messages) ? payload.messages : [];
    state.chatHistoryLoaded = true;
    if (elements.runMode.value === 'chat') renderChatConversation();
}

async function streamChatAnswer(message, onDelta) {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 210_000);
    try {
        const response = await fetch('/api/chat/stream', {
            method: 'POST',
            cache: 'no-store',
            signal: controller.signal,
            headers: {
                'Content-Type': 'application/json',
                'X-MyCodexAI-Worktree': state.workspaceId,
                'X-MyCodexAI-Project': state.projectId,
            },
            body: JSON.stringify({ message }),
        });
        if (response.status === 401) {
            window.location.assign('/');
            throw new Error('ต้องเข้าสู่ระบบใหม่');
        }
        if (!response.ok) {
            const payload = await response.json().catch(() => ({}));
            throw new Error(payload.detail || 'เชื่อมต่อกับ MyCodex ไม่ได้');
        }
        if (!response.body) throw new Error('เบราว์เซอร์นี้ไม่รองรับคำตอบแบบสตรีม');

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let answer = '';
        let streamError = '';
        const consume = (frame) => {
            const dataLine = frame.split('\n').find((line) => line.startsWith('data:'));
            if (!dataLine) return;
            const payload = JSON.parse(dataLine.slice(5).trim());
            if (payload.type === 'delta') {
                const delta = String(payload.delta || '');
                answer += delta;
                onDelta(delta, answer);
            } else if (payload.type === 'error') {
                streamError = payload.detail || 'MyCodex ไม่สามารถตอบได้';
            }
        };
        while (true) {
            const { value, done } = await reader.read();
            buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
            const frames = buffer.split('\n\n');
            buffer = frames.pop() || '';
            frames.forEach(consume);
            if (streamError) throw new Error(streamError);
            if (done) break;
        }
        if (buffer.trim()) consume(buffer);
        if (streamError) throw new Error(streamError);
        return answer.trim();
    } catch (error) {
        if (controller.signal.aborted) throw new Error('MyCodex ใช้เวลาตอบนานเกินไป ลองใหม่อีกครั้ง');
        throw error;
    } finally {
        window.clearTimeout(timeout);
    }
}

async function startChat(message, { resumeVoice = false } = {}) {
    setBusy(true, 'Ollama กำลังตอบ…');
    state.chatMessages.push({ role: 'user', content: message });
    const pendingMessage = { role: 'assistant', content: 'Ollama กำลังคิดและเรียบเรียงคำตอบ…', pending: true };
    state.chatMessages.push(pendingMessage);
    renderChatConversation();
    elements.taskInput.value = '';
    if (resumeVoice) {
        clearVoiceSpeech();
        state.voiceStreamBuffer = '';
    }
    try {
        const answer = await streamChatAnswer(message, (delta, partial) => {
            pendingMessage.content = partial || 'MyCodex กำลังคิดและเรียบเรียงคำตอบ…';
            renderChatConversation();
            if (resumeVoice && state.voiceConversationActive) queueVoiceStreamDelta(delta);
        });
        if (!answer) throw new Error('MyCodex ยังไม่ส่งคำตอบกลับมา');
        const pendingIndex = state.chatMessages.indexOf(pendingMessage);
        if (pendingIndex >= 0) state.chatMessages.splice(pendingIndex, 1, { role: 'assistant', content: answer });
        else state.chatMessages.push({ role: 'assistant', content: answer });
        state.chatHistoryLoaded = true;
        renderChatConversation();
        if (resumeVoice && state.voiceConversationActive) {
            finishVoiceStream({ resumeVoice: true });
        } else if (state.voiceAutoplay) speakChat(answer);
    } catch (error) {
        const pendingIndex = state.chatMessages.indexOf(pendingMessage);
        const failure = { role: 'assistant', content: `ไม่สามารถตอบได้: ${error.message}` };
        if (pendingIndex >= 0) state.chatMessages.splice(pendingIndex, 1, failure);
        else state.chatMessages.push(failure);
        renderChatConversation();
        toast(error.message, true);
    } finally {
        setBusy(false);
        if (!resumeVoice) elements.taskInput.focus();
    }
}

function renderRun(run) {
    state.runId = run.run_id;
    state.currentRun = run;
    if (run.workspace_id && run.workspace_id !== state.workspaceId) {
        state.workspaceId = run.workspace_id;
        renderWorktrees();
    }
    if (run.project_id && run.project_id !== state.projectId) {
        state.projectId = run.project_id;
        renderProjects();
    }
    if (Array.isArray(run.attachments)) {
        state.attachments = run.attachments;
        renderAttachments();
    }
    elements.welcome.hidden = true;
    elements.runView.hidden = false;
    elements.runTitle.textContent = run.task;
    elements.runStatus.dataset.status = run.status;
    elements.factRun.textContent = shortId(run.run_id);
    const progress = run.progress || {};
    const activity = run.activity || null;
    const queuePosition = progress.queue_position;
    const queueTotal = progress.queue_total;
    elements.runStatus.textContent = run.status === 'running' && activity?.state === 'waiting_for_memory'
        ? 'รอ RAM ให้พร้อม'
        : run.status === 'running' && activity?.state === 'thinking'
            ? 'Ollama กำลังคิด'
        : run.status === 'running' && activity?.state === 'executing'
            ? 'กำลังทำขั้นตอน'
        : run.status === 'queued' && Number.isInteger(queuePosition) && queuePosition > 0
        ? `รอคิว Ollama · ลำดับ ${queuePosition}${queueTotal ? ` จาก ${queueTotal}` : ''}`
        : formatStatus(run.status);
    const completedSteps = progress.completed_steps ?? run.trace.length;
    elements.factSteps.textContent = run.status === 'queued' && Number.isInteger(queuePosition) && queuePosition > 0
        ? `คิว ${queuePosition}${queueTotal ? `/${queueTotal}` : ''} · ${completedSteps}/${progress.max_steps || '?'} steps`
        : `${completedSteps}/${progress.max_steps || '?'} steps`;
    const reviewLabel = run.review_target ? `${run.review_scope} · ${run.review_target}` : (run.review_scope || 'uncommitted');
    elements.factMode.textContent = run.mode === 'review' ? `Read-only Code Review · ${reviewLabel}` : run.mode === 'team' ? 'Local Team (sequential)' : run.mode === 'delivery' ? 'Delivery · Plan → Verify → Review' : run.mode === 'expert' ? 'Codex-style Expert' : run.mode === 'project' ? 'Project Builder' : 'Ollama local';
    const canCancel = run.background && ['queued', 'running', 'cancelling'].includes(run.status);
    const canContinue = run.status === 'needs_input';
    elements.continueRun.hidden = !canContinue;
    elements.continueRun.disabled = state.busy;
    elements.cancelRun.hidden = !canCancel;
    elements.cancelRun.disabled = state.busy || run.status === 'cancelling';

    elements.timeline.replaceChildren();
    if (activity?.message) {
        const item = document.createElement('article');
        item.className = 'timeline-item timeline-activity';
        const icon = document.createElement('span');
        icon.className = 'timeline-icon';
        icon.textContent = activity.state === 'waiting_for_memory' ? '…' : activity.state === 'executing' ? '›' : '◌';
        const content = document.createElement('div');
        const title = document.createElement('div');
        title.className = 'timeline-title';
        title.textContent = activity.message;
        content.append(title);
        if (activity.state === 'waiting_for_memory' && Number.isFinite(activity.available_memory_mb) && Number.isFinite(activity.min_available_mb)) {
            const detail = document.createElement('p');
            detail.className = 'timeline-summary';
            detail.textContent = `RAM ว่าง ${activity.available_memory_mb} MB จากเกณฑ์ ${activity.min_available_mb} MB`;
            content.append(detail);
        }
        if (activity.detail) {
            const detail = document.createElement('p');
            detail.className = 'timeline-summary';
            detail.textContent = activity.detail;
            content.append(detail);
        }
        item.append(icon, content);
        elements.timeline.append(item);
    }
    run.trace.forEach((entry) => {
        const item = document.createElement('article');
        item.className = 'timeline-item';

        const icon = document.createElement('span');
        icon.className = 'timeline-icon';
        icon.textContent = entry.tool === 'final' ? '✓' : entry.status === 'awaiting_approval' ? '!' : '›';

        const title = document.createElement('div');
        title.className = 'timeline-title';
        const label = document.createElement('span');
        const toolLabel = formatToolName(entry.tool);
        label.textContent = entry.team_member_name ? `${entry.team_member_name} · ${toolLabel}` : toolLabel;
        const stateLabel = document.createElement('span');
        stateLabel.className = 'timeline-state';
        stateLabel.textContent = formatStatus(entry.status);
        title.append(label, stateLabel);
        item.append(icon, title);

        if (entry.summary) {
            const summary = document.createElement('p');
            summary.className = 'timeline-summary';
            summary.textContent = escapeText(entry.summary);
            item.append(summary);
        }

        if (entry.result) {
            const result = document.createElement('p');
            result.className = 'timeline-result';
            const output = entry.result.output || entry.result.reason || entry.result.content;
            result.textContent = output ? escapeText(output) : `status: ${entry.result.status || 'ok'}`;
            item.append(result);
            if (entry.tool === 'capture_browser_qa' && entry.result.status === 'captured' && entry.result.capture_id) {
                const screenshot = document.createElement('img');
                screenshot.className = 'timeline-browser-qa';
                screenshot.alt = `Browser QA screenshot for ${entry.result.filename || 'HTML page'}`;
                screenshot.loading = 'lazy';
                screenshot.src = browserQaScreenshotUrl(entry.result.capture_id);
                item.append(screenshot);
            }
        }
        elements.timeline.append(item);
    });

    if (run.answer) {
        const answer = document.createElement('article');
        answer.className = 'timeline-item';
        const icon = document.createElement('span');
        icon.className = 'timeline-icon';
        icon.textContent = '✦';
        const title = document.createElement('div');
        title.className = 'timeline-title';
        title.textContent = 'สรุปจาก agent';
        const content = document.createElement('p');
        content.className = 'timeline-result';
        content.textContent = run.answer;
        answer.append(icon, title, content);
        elements.timeline.append(answer);
    }

    renderProjectPlan(run);
    renderTeam(run);
    renderApproval(run);
    announceVoiceCommandUpdate(run);
    addRecent(run);
    if (['completed', 'failed', 'cancelled', 'needs_input'].includes(run.status)) {
        loadProjectMemory().catch(() => {});
        loadOperations().catch(() => {});
        notifyRunCompletion(run);
    }
    if (canCancel) {
        pollRun();
    } else if (state.agentPollTimer) {
        window.clearTimeout(state.agentPollTimer);
        state.agentPollTimer = null;
    }
}

function renderTeam(run) {
    const members = run.team_members || [];
    elements.teamPanel.hidden = !members.length;
    if (!members.length) return;

    elements.teamMembers.replaceChildren();
    members.forEach((member) => {
        const item = document.createElement('article');
        item.className = 'team-member';
        item.dataset.status = member.status || 'pending';
        const title = document.createElement('div');
        const name = document.createElement('strong');
        name.textContent = member.name || member.id;
        const status = document.createElement('span');
        status.textContent = formatStatus(member.status || 'pending');
        title.append(name, status);
        item.append(title);
        if (member.summary) {
            const summary = document.createElement('p');
            summary.textContent = member.summary;
            item.append(summary);
        }
        elements.teamMembers.append(item);
    });
}

function renderProjectPlan(run) {
    const plan = run.project_plan;
    elements.projectPlan.hidden = !plan;
    if (!plan) return;

    elements.planName.textContent = plan.name || 'Project plan';
    elements.planOverview.textContent = plan.overview || 'The agent will build this project in reviewed batches.';
    elements.planMilestones.replaceChildren();
    (plan.milestones || []).forEach((milestone) => {
        const item = document.createElement('li');
        item.textContent = milestone;
        elements.planMilestones.append(item);
    });
}

function renderAttachments() {
    elements.attachmentList.replaceChildren();
    elements.attachmentList.hidden = !state.attachments.length;

    state.attachments.forEach((path) => {
        const item = document.createElement('span');
        item.className = 'attachment-chip';
        const label = document.createElement('span');
        label.textContent = path;
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'attachment-remove';
        remove.setAttribute('aria-label', `Remove ${path} from this task`);
        remove.textContent = '×';
        remove.addEventListener('click', () => {
            state.attachments = state.attachments.filter((itemPath) => itemPath !== path);
            renderAttachments();
        });
        item.append(label, remove);
        elements.attachmentList.append(item);
    });
}

async function uploadFiles(fileList) {
    const files = [...fileList];
    if (!files.length) return;

    const form = new FormData();
    form.append('destination', elements.uploadDestination.value.trim() || 'uploads');
    form.append('overwrite', String(elements.uploadOverwrite.checked));
    files.forEach((file) => {
        form.append('files', file, file.webkitRelativePath || file.name);
    });

    setBusy(true, 'กำลังแนบไฟล์…');
    try {
        const response = await fetch('/api/workspace/uploads', {
            method: 'POST',
            body: form,
            headers: { 'X-MyCodexAI-Worktree': state.workspaceId },
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(payload.detail || 'ไม่สามารถแนบไฟล์เข้า workspace ได้');
        }

        const uploadedPaths = payload.files.map((file) => file.path);
        state.attachments = [...new Set([...state.attachments, ...uploadedPaths])];
        renderAttachments();
        toast(`แนบ ${uploadedPaths.length} ไฟล์แล้ว — agent จะได้รับรายการนี้พร้อมงาน`);
    } catch (error) {
        toast(error.message, true);
    } finally {
        setBusy(false);
    }
}

function renderApproval(run) {
    const pending = run.pending_action;
    elements.approvalPanel.hidden = !pending;
    if (!pending) return;

    elements.approvalTitle.textContent = `${pending.tool} ต้องการการอนุมัติ`;
    elements.approvalSummary.textContent = pending.summary || 'ตรวจผลของ action นี้ก่อนทำต่อ';
    const preview = pending.preview || {};
    if (preview.file_count) {
        elements.approvalTitle.textContent = `${pending.tool} · ${preview.file_count} ไฟล์รออนุมัติ`;
    }
    elements.diffPreview.textContent = preview.diff || preview.reason || 'ไม่มี diff สำหรับ action นี้';
}

async function startRun() {
    const task = elements.taskInput.value.trim();
    const mode = elements.runMode.value;
    const reviewScope = elements.reviewScope.value;
    const reviewTarget = elements.reviewTarget.value.trim();
    if (!task) {
        elements.taskInput.focus();
        toast('กรุณาระบุงานที่ต้องการให้ agent ทำ', true);
        return;
    }
    if (mode === 'chat') {
        await startChat(task);
        return;
    }
    if (mode === 'review' && ['commit', 'branch'].includes(reviewScope) && !reviewTarget) {
        elements.reviewTarget.focus();
        toast('กรุณาระบุ commit หรือ base branch ที่จะตรวจ', true);
        return;
    }

    setBusy(true);
    try {
        const run = await request('/api/agent/runs', {
            method: 'POST',
            body: JSON.stringify({
                task,
                mode,
                max_steps: ['project', 'expert'].includes(mode) ? 60 : mode === 'delivery' ? 48 : mode === 'team' ? 24 : mode === 'review' ? 16 : 8,
                attachments: state.attachments,
                background: true,
                review_scope: mode === 'review' ? reviewScope : 'uncommitted',
                review_target: mode === 'review' ? reviewTarget : '',
            }),
        });
        renderRun(run);
        if (['queued', 'running'].includes(run.status)) {
            toast('agent เริ่มงานเบื้องหลังแล้ว — ใช้งานหน้าจอต่อได้');
        } else if (run.status === 'awaiting_approval') {
            toast('agent รอให้คุณอนุมัติ action ถัดไป');
        } else if (run.status === 'completed') {
            toast('agent ทำงานเสร็จแล้ว');
        } else {
            toast(`agent หยุดทำงาน: ${formatStatus(run.status)}`, true);
        }
        return run;
    } catch (error) {
        toast(error.message, true);
    } finally {
        setBusy(false);
    }
}

async function resumeRun(approve) {
    if (!state.runId) return;
    setBusy(true, approve ? 'กำลังทำ action ที่อนุมัติ…' : 'กำลังยกเลิก action…');
    try {
        const run = await request(`/api/agent/runs/${state.runId}/resume`, {
            method: 'POST',
            body: JSON.stringify({ approve }),
        });
        renderRun(run);
        toast(approve ? 'ส่ง action เข้าคิวให้ agent ทำต่อแล้ว' : 'ปฏิเสธ action แล้ว');
    } catch (error) {
        toast(error.message, true);
    } finally {
        setBusy(false);
    }
}

async function continueRun() {
    if (!state.runId) return;
    setBusy(true, 'กำลังทำต่อจากสถานะเดิม…');
    try {
        const run = await request(`/api/agent/runs/${state.runId}/continue`, { method: 'POST' });
        renderRun(run);
        toast('ส่ง goal กลับเข้าคิวแล้ว');
    } catch (error) {
        toast(error.message, true);
    } finally {
        setBusy(false);
    }
}

function pollRun() {
    if (state.agentPollTimer || !state.runId) return;
    state.agentPollTimer = window.setTimeout(async () => {
        state.agentPollTimer = null;
        try {
            const run = await request(`/api/agent/runs/${state.runId}`);
            renderRun(run);
        } catch (error) {
            toast(`ติดตาม agent ไม่สำเร็จ: ${error.message}`, true);
        }
    }, 800);
}

async function cancelRun() {
    if (!state.runId) return;
    setBusy(true, 'กำลังขอหยุด agent…');
    try {
        const run = await request(`/api/agent/runs/${state.runId}/cancel`, { method: 'POST' });
        renderRun(run);
        toast(run.status === 'cancelled' ? 'หยุด agent แล้ว' : 'กำลังรอให้ Ollama จบรอบปัจจุบันก่อนหยุด');
    } catch (error) {
        toast(error.message, true);
    } finally {
        setBusy(false);
    }
}

async function loadRun(runId, workspaceId = state.workspaceId, projectId = state.projectId) {
    setBusy(true, 'กำลังโหลดงาน…');
    try {
        if (workspaceId !== state.workspaceId) {
            state.workspaceId = workspaceId;
            renderWorktrees();
            await loadProjects();
        }
        if (projectId !== state.projectId) {
            state.projectId = projectId;
            renderProjects();
        }
        const run = await request(`/api/agent/runs/${runId}`);
        renderRun(run);
    } catch (error) {
        toast('ไม่พบ run นี้แล้ว อาจเกิดจาก server ถูก restart', true);
    } finally {
        setBusy(false);
    }
}

document.querySelectorAll('.suggestion').forEach((button) => {
    button.addEventListener('click', () => {
        elements.taskInput.value = button.dataset.task;
        elements.taskInput.focus();
    });
});

document.querySelector('#new-task').addEventListener('click', () => {
    resetTaskView();
    setAdvancedComposer(false);
    elements.taskInput.value = '';
    state.attachments = [];
    renderAttachments();
    elements.taskInput.focus();
    setWorkspaceSidebar(false);
});
document.querySelector('#focus-task').addEventListener('click', () => {
    elements.taskInput.focus();
    setWorkspaceSidebar(false);
});
elements.sidebarMenuToggle.addEventListener('click', () => setWorkspaceSidebar(true));
elements.sidebarClose.addEventListener('click', () => setWorkspaceSidebar(false));
elements.sidebarBackdrop.addEventListener('click', () => setWorkspaceSidebar(false));
document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && elements.workspaceSidebar.classList.contains('is-open')) setWorkspaceSidebar(false);
});
window.matchMedia('(max-width: 720px)').addEventListener('change', () => setWorkspaceSidebar(false));
elements.openAdvancedControls.addEventListener('click', () => setAdvancedComposer(!elements.advancedComposer.open));
elements.advancedComposer.addEventListener('toggle', () => {
    elements.openAdvancedControls.setAttribute('aria-expanded', String(elements.advancedComposer.open));
    elements.openAdvancedControls.textContent = elements.advancedComposer.open ? 'ซ่อนการตั้งค่า' : 'การตั้งค่าและเครื่องมือ';
});
document.querySelectorAll('[data-composer-shortcut]').forEach((button) => {
    button.addEventListener('click', () => applyComposerShortcut(button));
});
elements.attachFiles.addEventListener('click', () => elements.filePicker.click());
elements.attachFolder.addEventListener('click', () => elements.folderPicker.click());
elements.filePicker.addEventListener('change', async () => {
    await uploadFiles(elements.filePicker.files);
    elements.filePicker.value = '';
});
elements.folderPicker.addEventListener('change', async () => {
    await uploadFiles(elements.folderPicker.files);
    elements.folderPicker.value = '';
});
elements.startButton.addEventListener('click', startRun);
elements.voiceInput.addEventListener('click', listenForTask);
elements.voiceConversation.addEventListener('click', toggleVoiceConversation);
elements.voiceCommand.addEventListener('click', listenForComputerCommand);
elements.voiceAutoRead.addEventListener('click', toggleVoiceAutoplay);
elements.continueRun.addEventListener('click', continueRun);
elements.cancelRun.addEventListener('click', cancelRun);
elements.runMode.addEventListener('change', syncReviewControls);
elements.reviewScope.addEventListener('change', syncReviewControls);
elements.logout.addEventListener('click', logout);
elements.setupMfa.addEventListener('click', setupMfa);
elements.recoveryCodes.addEventListener('click', showRecoveryCodes);
elements.linkGoogle.addEventListener('click', () => beginSocialLink('google'));
elements.linkGithub.addEventListener('click', () => beginSocialLink('github'));
elements.createInvite.addEventListener('click', createInvite);
elements.enableNotifications.addEventListener('click', enableNotifications);
elements.createBackup.addEventListener('click', createEncryptedBackup);
elements.restoreBackup.addEventListener('click', restoreLatestBackup);
elements.revokeOtherSessions.addEventListener('click', revokeOtherSessions);
elements.saveLearningExample.addEventListener('click', saveLearningExample);
elements.saveLearningEval.addEventListener('click', saveLearningEvaluation);
elements.runLearningEvals.addEventListener('click', runLearningEvaluations);
elements.exportLearningJsonl.addEventListener('click', exportLearningJsonl);
elements.generateImage.addEventListener('click', generateImage);
elements.imageExportCanva.addEventListener('click', exportImageForCanva);
elements.refreshGithub.addEventListener('click', loadGitHubStatus);
elements.connectGithub.addEventListener('click', connectGitHub);
elements.createGithubCi.addEventListener('click', createGitHubCi);
elements.pushGithub.addEventListener('click', pushGitHub);
elements.openGithubPr.addEventListener('click', openGitHubPr);
elements.createWorktree.addEventListener('click', createWorktree);
elements.worktreeSelect.addEventListener('change', selectWorktree);
elements.importProjectFolder.addEventListener('click', () => elements.projectFolderPicker.click());
elements.importProjectZip.addEventListener('click', () => elements.projectZipPicker.click());
elements.projectSelect.addEventListener('change', selectProject);
elements.rebuildProjectIndex.addEventListener('click', rebuildProjectIndex);
elements.saveProjectMemory.addEventListener('click', saveProjectMemory);
elements.showProjectMemory.addEventListener('click', async () => {
    try {
        await loadProjectMemory();
    } catch (error) {
        toast(error.message, true);
    }
});
elements.saveProjectGuidance.addEventListener('click', saveProjectGuidance);
elements.loadProjectGuidance.addEventListener('click', async () => {
    try {
        const guidance = await loadProjectGuidance();
        toast(guidance.content ? 'โหลด Project Guidance แล้ว' : 'project นี้ยังไม่มี Guidance');
    } catch (error) {
        toast(error.message, true);
    }
});
elements.saveProjectSkill.addEventListener('click', saveProjectSkill);
elements.loadProjectSkills.addEventListener('click', async () => {
    try {
        const skills = await loadProjectSkills();
        toast(skills.length ? `โหลด ${skills.length} Project Skills แล้ว` : 'project นี้ยังไม่มี Skill');
    } catch (error) {
        toast(error.message, true);
    }
});
elements.captureBrowserQa.addEventListener('click', captureBrowserQa);
elements.projectFolderPicker.addEventListener('change', async () => {
    await importProject(elements.projectFolderPicker.files);
    elements.projectFolderPicker.value = '';
});
elements.projectZipPicker.addEventListener('change', async () => {
    await importProject(elements.projectZipPicker.files);
    elements.projectZipPicker.value = '';
});
elements.startTerminal.addEventListener('click', createTerminalJob);
elements.approveTerminal.addEventListener('click', () => resumeTerminalJob(true));
elements.rejectTerminal.addEventListener('click', () => resumeTerminalJob(false));
elements.cancelTerminal.addEventListener('click', cancelTerminalJob);
elements.approve.addEventListener('click', () => resumeRun(true));
elements.reject.addEventListener('click', () => resumeRun(false));
elements.taskInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        startRun();
    }
});

initializeSidebarLayout();
syncVoiceControls();
loadRecent();
renderAttachments();
syncReviewControls();
setAdvancedComposer(false);
syncTerminalControls();
loadAccount().finally(() => {
    window.setTimeout(() => {
        loadOperations().catch(() => {});
        loadResilience();
        loadSessions();
    }, 250);
});
