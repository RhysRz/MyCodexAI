const ui = {
    status: document.querySelector('#music-status'), file: document.querySelector('#music-file'), upload: document.querySelector('#music-upload'),
    analyze: document.querySelector('#music-analyze'), player: document.querySelector('#music-player'), library: document.querySelector('#music-library'),
    source: document.querySelector('#music-source'), instrument: document.querySelector('#music-instrument'), play: document.querySelector('#music-play'), stop: document.querySelector('#music-stop'), playbackNote: document.querySelector('#music-playback-note'),
    results: document.querySelector('#music-results'), title: document.querySelector('#music-title'), facts: document.querySelector('#music-facts'),
    chords: document.querySelector('#music-chord-list'), notes: document.querySelector('#music-note-list'), tabPanel: document.querySelector('#music-tab-panel'), tabSummary: document.querySelector('#music-tab-summary'), tabDetails: document.querySelector('#music-tab-details'), parts: document.querySelector('#music-parts'), stems: document.querySelector('#music-stems'),
    midi: document.querySelector('#music-midi'), chordFile: document.querySelector('#music-chords'), tab: document.querySelector('#music-tab'), json: document.querySelector('#music-json'),
    musicxml: document.querySelector('#music-musicxml'), stemMidi: document.querySelector('#music-stem-midi'), stemMixer: document.querySelector('#music-stem-mixer'), stemRows: document.querySelector('#music-stem-rows'), stemPlay: document.querySelector('#music-stem-play'), stemStop: document.querySelector('#music-stem-stop'),
};

const state = { tracks: [], current: null, playbackNotes: [], audioContext: null, playbackNodes: [], playbackTimer: null, sampledAudio: null, stemAudios: [] };

async function api(url, options = {}) {
    const headers = new Headers(options.headers || {});
    if (!(options.body instanceof FormData) && options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
    const response = await fetch(url, { cache: 'no-store', ...options, headers });
    const payload = await response.json().catch(() => ({}));
    if (response.status === 401) { window.location.assign('/?next=/music'); throw new Error('ต้องเข้าสู่ระบบใหม่'); }
    if (!response.ok) throw new Error(payload.detail || 'ไม่สามารถดำเนินการได้');
    return payload;
}

function duration(seconds) {
    if (!Number.isFinite(Number(seconds))) return 'ไม่ทราบความยาว';
    const value = Math.max(0, Math.round(Number(seconds))), minutes = Math.floor(value / 60);
    return `${minutes}:${String(value % 60).padStart(2, '0')}`;
}

function bytes(value) {
    const amount = Number(value) || 0;
    return amount < 1024 * 1024 ? `${Math.round(amount / 1024)} KB` : `${(amount / 1024 / 1024).toFixed(1)} MB`;
}

function make(tag, text = '', className = '') {
    const node = document.createElement(tag); if (text) node.textContent = text; if (className) node.className = className; return node;
}

function renderTracks() {
    ui.library.replaceChildren();
    if (!state.tracks.length) { ui.library.append(make('p', 'ยังไม่มีเพลงที่อัปโหลด', 'muted')); return; }
    for (const track of state.tracks) {
        const button = make('button', '', 'track'); button.type = 'button';
        button.classList.toggle('is-active', track.music_id === state.current?.music_id);
        const type = track.kind === 'sheet' ? 'PDF โน้ต' : duration(track.duration_seconds);
        button.append(make('strong', track.file_name), make('small', `${type} · ${bytes(track.bytes)}${track.analyzed ? ' · วิเคราะห์แล้ว' : ''}`));
        button.addEventListener('click', () => selectTrack(track)); ui.library.append(button);
    }
}

async function selectTrack(track) {
    stopPlayback(); state.current = track; ui.analyze.disabled = false;
    ui.source.href = track.source_url; ui.source.hidden = !track.source_url;
    if (track.audio_url) { ui.player.src = track.audio_url; ui.player.hidden = false; } else { ui.player.pause(); ui.player.removeAttribute('src'); ui.player.hidden = true; }
    ui.results.hidden = true; renderTracks(); ui.status.textContent = `เลือก ${track.file_name} แล้ว`;
    if (track.analyzed) {
        try { renderAnalysis((await api(`/api/music/${track.music_id}/analysis`)).analysis); } catch { /* The user can run analysis again. */ }
    }
}

function fact(label, value) { const box = make('div', '', 'fact'); box.append(make('span', label), make('strong', value)); return box; }

function renderAnalysis(analysis) {
    if (!state.current) return;
    ui.results.hidden = false; ui.title.textContent = `ผลการวิเคราะห์ · ${state.current.file_name}`;
    ui.facts.replaceChildren(
        fact('Tempo', `${analysis.tempo?.bpm ?? '—'} BPM`), fact('Key', analysis.key?.name || 'Unknown'),
        fact('จังหวะ', analysis.rhythm?.meter || '—'), fact('Groove', analysis.rhythm?.groove || '—'),
    );
    ui.chords.replaceChildren();
    for (const chord of analysis.chords || []) {
        const item = make('div', '', 'timeline-item'); item.append(make('strong', chord.name || 'N.C.'), make('span', `${duration(chord.start)}–${duration(chord.end)} · ${Math.round((Number(chord.confidence) || 0) * 100)}%`)); ui.chords.append(item);
    }
    if (!ui.chords.childElementCount) ui.chords.append(make('p', 'ไม่พบคอร์ดที่เชื่อถือได้', 'muted'));
    ui.notes.replaceChildren();
    for (const note of (analysis.notes || []).slice(0, 96)) {
        const item = make('div', '', 'note'); item.append(make('strong', note.name || `MIDI ${note.midi}`), make('small', `${duration(note.start)} · ${Math.round((Number(note.confidence) || 0) * 100)}%`)); ui.notes.append(item);
    }
    if (!ui.notes.childElementCount) ui.notes.append(make('p', 'ไม่พบแนวโน้ตหลักที่เชื่อถือได้', 'muted'));
    const sourceTab = analysis.tablature;
    ui.tabPanel.hidden = !sourceTab;
    ui.tabDetails.replaceChildren();
    if (sourceTab) {
        ui.tabSummary.textContent = `${sourceTab.instrument} · ${sourceTab.string_count} สาย · จูนจากบนลงล่าง: ${(sourceTab.tuning || []).join(', ')}`;
        for (const event of (sourceTab.events || []).slice(0, 120)) {
            const item = make('div', '', 'timeline-item'); item.append(make('strong', event.muted ? 'x muted' : `สาย ${event.string} · fret ${event.fret}`), make('span', duration(event.start))); ui.tabDetails.append(item);
        }
    }
    ui.parts.replaceChildren();
    for (const part of analysis.detected_parts || []) {
        const item = make('div', '', 'part'); const left = make('div'); left.append(make('strong', part.name), make('p', part.detail)); item.append(left, make('span', part.confidence || 'estimated')); ui.parts.append(item);
    }
    ui.stems.textContent = analysis.stem_separation?.detail || 'ไม่พบข้อมูลการแยก stem';
    const artifacts = analysis.artifacts || {};
    for (const [element, href] of [[ui.midi, artifacts.midi], [ui.chordFile, artifacts.chords], [ui.tab, artifacts.tab], [ui.json, artifacts.analysis], [ui.musicxml, artifacts.musicxml], [ui.stemMidi, artifacts.stem_midi]]) { element.hidden = !href; element.href = href || '#'; }
    renderStemMixer(artifacts);
    state.playbackNotes = Array.isArray(analysis.notes) ? analysis.notes : [];
    ui.play.disabled = !state.playbackNotes.length;
    ui.playbackNote.textContent = state.playbackNotes.length ? 'เลือกเครื่องดนตรีแล้วกดเล่น ระบบจะสร้างเสียง sampled จริงในเครื่อง' : 'ไม่พบร่างโน้ตที่นำมาเล่นได้';
    if (Array.isArray(analysis.limitations) && analysis.limitations.length) ui.status.textContent = `วิเคราะห์เสร็จแล้ว · ${analysis.limitations[0]}`;
}

function stopStems() {
    for (const audio of state.stemAudios) { audio.pause(); audio.currentTime = 0; }
}

function renderStemMixer(artifacts) {
    stopStems(); state.stemAudios = []; ui.stemRows.replaceChildren();
    const labels = { vocals: 'เสียงร้อง', drums: 'กลอง', bass: 'เบส', guitar: 'กีตาร์', piano: 'เปียโน', other: 'เสียงอื่น' };
    for (const [stem, label] of Object.entries(labels)) {
        const url = artifacts[`stem_${stem}`]; if (!url) continue;
        const audio = new Audio(url); audio.preload = 'none'; state.stemAudios.push(audio);
        const row = make('div', '', 'stem-row'), slider = document.createElement('input'), mute = make('button', 'ปิดเสียง');
        slider.type = 'range'; slider.min = '0'; slider.max = '1'; slider.step = '0.05'; slider.value = '1'; slider.setAttribute('aria-label', `ระดับเสียง ${label}`);
        slider.addEventListener('input', () => { audio.volume = Number(slider.value); });
        mute.type = 'button'; mute.addEventListener('click', () => { audio.muted = !audio.muted; mute.textContent = audio.muted ? 'เปิดเสียง' : 'ปิดเสียง'; });
        row.append(make('span', label), slider, mute); ui.stemRows.append(row);
    }
    ui.stemMixer.hidden = !state.stemAudios.length;
}

async function playStems() {
    stopStems();
    try { await Promise.all(state.stemAudios.map((audio) => audio.play())); }
    catch { ui.status.textContent = 'เบราว์เซอร์ยังไม่อนุญาตให้เล่นเสียง โปรดลองกดอีกครั้ง'; }
}

async function upload() {
    const file = ui.file.files?.[0];
    if (!file) { ui.status.textContent = 'กรุณาเลือก PDF หรือไฟล์เสียงก่อน'; return; }
    ui.upload.disabled = true; ui.status.textContent = 'กำลังอัปโหลดเพลงแบบส่วนตัว…';
    try {
        const form = new FormData(); form.append('file', file, file.name);
        const track = await api('/api/music/tracks', { method: 'POST', body: form });
        state.tracks = [track, ...state.tracks.filter((item) => item.music_id !== track.music_id)]; ui.file.value = ''; await selectTrack(track);
    } catch (error) { ui.status.textContent = error.message; } finally { ui.upload.disabled = false; }
}

async function analyze() {
    if (!state.current) return;
    ui.analyze.disabled = true; ui.status.textContent = state.current.kind === 'sheet' ? 'กำลังอ่านคอร์ดและ tempo จาก PDF…' : 'กำลังวิเคราะห์ BPM คีย์ คอร์ด และโน้ตในเครื่อง… อาจใช้เวลาสักครู่';
    try {
        const result = await api(`/api/music/${state.current.music_id}/analyze`, { method: 'POST' });
        state.current.analyzed = true; state.tracks = state.tracks.map((track) => track.music_id === state.current.music_id ? { ...track, analyzed: true } : track);
        renderTracks(); renderAnalysis(result.analysis);
    } catch (error) { ui.status.textContent = error.message; } finally { ui.analyze.disabled = false; }
}

function midiFrequency(note) { return 440 * (2 ** ((Number(note) - 69) / 12)); }

function stopPlayback() {
    if (state.playbackTimer) window.clearTimeout(state.playbackTimer);
    state.playbackTimer = null;
    if (state.sampledAudio) {
        state.sampledAudio.pause();
        state.sampledAudio.removeAttribute('src');
        state.sampledAudio = null;
    }
    for (const node of state.playbackNodes) { try { node.stop(); } catch { /* already ended */ } try { node.disconnect(); } catch { /* already disconnected */ } }
    state.playbackNodes = [];
    ui.stop.disabled = true;
    ui.play.disabled = !state.playbackNotes.length;
}

function trackPlaybackSource(source) { state.playbackNodes.push(source); }

function voiceOutput(context, start, length, cutoff, level, attack, release) {
    const filter = context.createBiquadFilter(), gain = context.createGain(), stopAt = start + length + release;
    filter.type = 'lowpass'; filter.frequency.setValueAtTime(cutoff, start); filter.Q.value = 0.75;
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(level, start + attack);
    gain.gain.exponentialRampToValueAtTime(Math.max(0.0001, level * 0.32), start + Math.min(length * 0.32, attack + 0.16));
    gain.gain.exponentialRampToValueAtTime(0.0001, stopAt);
    filter.connect(gain); gain.connect(context.destination);
    return { input: filter, stopAt };
}

function scheduleOscillator(context, frequency, start, stopAt, input, type, level, detune = 0) {
    const oscillator = context.createOscillator(), gain = context.createGain();
    oscillator.type = type; oscillator.frequency.setValueAtTime(frequency, start); oscillator.detune.setValueAtTime(detune, start);
    gain.gain.setValueAtTime(level, start); oscillator.connect(gain); gain.connect(input);
    oscillator.start(start); oscillator.stop(stopAt); trackPlaybackSource(oscillator);
}

function schedulePiano(context, note, start, length) {
    const voice = voiceOutput(context, start, length, 4200, 0.22, 0.008, 1.8), frequency = midiFrequency(note.midi);
    [[1, 0.72], [2, 0.26], [3, 0.14], [4, 0.08], [5, 0.035]].forEach(([partial, level], index) => {
        scheduleOscillator(context, frequency * partial, start, voice.stopAt, voice.input, 'sine', level, index * 1.7 - 3.4);
    });
}

function scheduleGuitar(context, note, start, length) {
    const frequency = midiFrequency(note.midi), period = Math.max(12, Math.min(4096, Math.round(context.sampleRate / frequency)));
    const buffer = context.createBuffer(1, period, context.sampleRate), data = buffer.getChannelData(0);
    for (let index = 0; index < data.length; index += 1) data[index] = (Math.random() * 2 - 1) * (1 - index / data.length * 0.35);
    const source = context.createBufferSource(), voice = voiceOutput(context, start, Math.min(1.15, length + 0.32), Math.min(5200, frequency * 8), 0.3, 0.004, 0.85);
    source.buffer = buffer; source.loop = true; source.loopStart = 0; source.loopEnd = buffer.duration;
    source.connect(voice.input); source.start(start); source.stop(voice.stopAt); trackPlaybackSource(source);
}

function scheduleBass(context, note, start, length) {
    const voice = voiceOutput(context, start, length, 920, 0.18, 0.012, 0.48), frequency = midiFrequency(note.midi);
    scheduleOscillator(context, frequency, start, voice.stopAt, voice.input, 'sine', 0.72);
    scheduleOscillator(context, frequency, start, voice.stopAt, voice.input, 'sawtooth', 0.11, -5);
    scheduleOscillator(context, frequency * 2, start, voice.stopAt, voice.input, 'sine', 0.08, 3);
}

function scheduleStrings(context, note, start, length) {
    const voice = voiceOutput(context, start, Math.max(0.55, length), 2400, 0.09, 0.13, 0.78), frequency = midiFrequency(note.midi);
    [-9, -3, 4, 10].forEach((detune, index) => scheduleOscillator(context, frequency, start, voice.stopAt, voice.input, index % 2 ? 'sawtooth' : 'triangle', 0.19, detune));
}

function scheduleFlute(context, note, start, length) {
    const voice = voiceOutput(context, start, length, 5600, 0.2, 0.08, 0.45), frequency = midiFrequency(note.midi);
    scheduleOscillator(context, frequency, start, voice.stopAt, voice.input, 'sine', 0.78);
    scheduleOscillator(context, frequency * 2, start, voice.stopAt, voice.input, 'sine', 0.11, 4);
    scheduleOscillator(context, frequency * 3, start, voice.stopAt, voice.input, 'sine', 0.035, -3);
}

function scheduleTone(context, note, start, length, instrument) {
    if (instrument === 'guitar') return scheduleGuitar(context, note, start, length);
    if (instrument === 'bass') return scheduleBass(context, note, start, length);
    if (instrument === 'strings') return scheduleStrings(context, note, start, length);
    if (instrument === 'flute') return scheduleFlute(context, note, start, length);
    return schedulePiano(context, note, start, length);
}

async function playSynthNotes() {
    if (!state.playbackNotes.length) return;
    stopPlayback();
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) { ui.playbackNote.textContent = 'เบราว์เซอร์นี้ยังไม่รองรับเสียงสังเคราะห์'; return; }
    state.audioContext ||= new AudioContextClass();
    await state.audioContext.resume();
    const context = state.audioContext, origin = context.currentTime + 0.08, instrument = ui.instrument.value;
    let latest = 0;
    for (const note of state.playbackNotes.slice(0, 192)) {
        const start = origin + Math.max(0, Number(note.start) || 0), length = Math.max(0.08, Math.min(4, Number(note.duration) || 0.4));
        scheduleTone(context, note, start, length, instrument); latest = Math.max(latest, (Number(note.start) || 0) + length + 1.1);
    }
    ui.play.disabled = true; ui.stop.disabled = false; ui.playbackNote.textContent = `กำลังเล่นร่างโน้ตด้วย ${ui.instrument.options[ui.instrument.selectedIndex].text}`;
    state.playbackTimer = window.setTimeout(() => { stopPlayback(); ui.playbackNote.textContent = 'เล่นร่างโน้ตเสร็จแล้ว'; }, Math.ceil(latest * 1000));
}

async function playNotes() {
    if (!state.current || !state.playbackNotes.length) return;
    stopPlayback();
    ui.play.disabled = true;
    ui.playbackNote.textContent = 'กำลังสร้างเสียง sampled จากชุดเสียงในเครื่อง…';
    try {
        const rendered = await api(`/api/music/${state.current.music_id}/sampled-audio`, {
            method: 'POST', body: JSON.stringify({ instrument: ui.instrument.value }),
        });
        const player = new Audio(`${rendered.audio_url}?v=${Date.now()}`);
        state.sampledAudio = player;
        player.addEventListener('ended', () => {
            if (state.sampledAudio === player) {
                state.sampledAudio = null; ui.stop.disabled = true; ui.play.disabled = false;
                ui.playbackNote.textContent = 'เล่นเสียง sampled เสร็จแล้ว';
            }
        }, { once: true });
        await player.play();
        ui.stop.disabled = false;
        ui.playbackNote.textContent = `กำลังเล่นเสียง sampled: ${rendered.label}`;
    } catch (error) {
        if (state.sampledAudio) { state.sampledAudio.pause(); state.sampledAudio = null; }
        ui.playbackNote.textContent = `เสียง sampled ไม่พร้อม (${error.message}) จึงใช้เสียงจำลองชั่วคราว`;
        await playSynthNotes();
    }
}

async function load() {
    const [status, tracks] = await Promise.all([api('/api/music/status'), api('/api/music/tracks')]);
    ui.status.textContent = `${status.detail} · รองรับ ${status.supported_formats.join(', ')}`;
    state.tracks = tracks.tracks || []; renderTracks();
    if (state.tracks.length) await selectTrack(state.tracks[0]);
}

ui.upload.addEventListener('click', upload); ui.analyze.addEventListener('click', analyze); ui.play.addEventListener('click', playNotes); ui.stop.addEventListener('click', stopPlayback); ui.stemPlay.addEventListener('click', playStems); ui.stemStop.addEventListener('click', stopStems); window.addEventListener('pagehide', () => { stopPlayback(); stopStems(); }); load().catch((error) => { ui.status.textContent = error.message; });
