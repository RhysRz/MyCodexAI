const ui = {
    status: document.querySelector('#image-status'), prompt: document.querySelector('#image-prompt'),
    caption: document.querySelector('#image-caption'), generate: document.querySelector('#image-generate'),
    download: document.querySelector('#image-download'), canva: document.querySelector('#image-canva'),
    result: document.querySelector('#image-result'), gallery: document.querySelector('#image-gallery'),
};
let latest = null;

async function api(url, options = {}) {
    const response = await fetch(url, { cache: 'no-store', headers: { 'Content-Type': 'application/json' }, ...options });
    const payload = await response.json().catch(() => ({}));
    if (response.status === 401) { window.location.assign('/?next=/images'); throw new Error('ต้องเข้าสู่ระบบใหม่'); }
    if (!response.ok) throw new Error(payload.detail || 'ไม่สามารถดำเนินการได้');
    return payload;
}

function quota(status) { return status.quota_exempt ? 'ไม่จำกัดจำนวนภาพ' : `เหลือ ${status.remaining_today}/${status.daily_limit} ภาพวันนี้`; }

function renderGallery(images) {
    ui.gallery.replaceChildren();
    for (const image of images) {
        const link = document.createElement('a'); link.href = image.url; link.target = '_blank';
        const preview = document.createElement('img'); preview.src = image.url; preview.alt = 'ภาพที่สร้างโดย MyCodex'; preview.loading = 'lazy';
        link.append(preview); ui.gallery.append(link);
    }
    if (!latest && images.length) { latest = { image_id: images[0].image_id, caption: '' }; ui.canva.hidden = false; }
}

async function loadStudio() {
    const [status, list] = await Promise.all([api('/api/images/status'), api('/api/images')]);
    ui.status.textContent = `${status.detail} · ${status.model} · ${quota(status)}`;
    ui.generate.disabled = !status.configured;
    renderGallery(list.images || []);
}

function units(value) { return window.Intl?.Segmenter ? Array.from(new Intl.Segmenter('th', { granularity: 'grapheme' }).segment(value), item => item.segment) : Array.from(value); }
function lines(context, value, width) { const output = []; let line = ''; for (const unit of units(value)) { const next = line + unit; if (line && context.measureText(next).width > width) { output.push(line); line = unit; } else line = next; } if (line) output.push(line); return output; }
async function sourceImage(url) { return new Promise((resolve, reject) => { const image = new Image(); image.onload = () => resolve(image); image.onerror = () => reject(new Error('ไม่สามารถเตรียมภาพได้')); image.src = url; }); }
async function overlay(url, caption) {
    if (!caption.trim()) return url;
    const image = await sourceImage(url), canvas = document.createElement('canvas'); canvas.width = image.naturalWidth; canvas.height = image.naturalHeight;
    const context = canvas.getContext('2d'); context.drawImage(image, 0, 0);
    const size = Math.max(24, Math.min(72, Math.round(canvas.width * .055))), pad = Math.round(size * .58), height = Math.round(size * 1.34);
    context.font = `700 ${size}px "Leelawadee UI", Thonburi, Tahoma, sans-serif`;
    const wrapped = lines(context, caption.trim(), canvas.width - pad * 2), panel = wrapped.length * height + pad * 2, top = canvas.height - panel;
    context.fillStyle = 'rgba(8,12,20,.76)'; context.fillRect(0, top, canvas.width, panel); context.fillStyle = '#fff'; context.textAlign = 'center'; context.textBaseline = 'middle';
    wrapped.forEach((line, index) => context.fillText(line, canvas.width / 2, top + pad + height * index + height / 2));
    return canvas.toDataURL('image/png');
}

async function generate() {
    const prompt = ui.prompt.value.trim(), caption = ui.caption.value.trim();
    if (prompt.length < 2) { ui.status.textContent = 'กรุณาอธิบายภาพที่ต้องการก่อน'; return; }
    ui.generate.disabled = true; ui.status.textContent = 'MyCodex กำลังสร้างภาพ…';
    try {
        const image = await api('/api/images', { method: 'POST', body: JSON.stringify({ prompt, allow_text: false }) });
        const shown = await overlay(image.url, caption); ui.result.src = shown; ui.result.hidden = false;
        ui.download.href = shown; ui.download.download = caption ? 'mycodex-thai-caption.png' : ''; ui.download.hidden = false;
        latest = { image_id: image.image_id, caption }; ui.canva.hidden = false; ui.status.textContent = `สร้างภาพสำเร็จ · ${image.model}`;
        ui.prompt.value = ''; ui.caption.value = ''; await loadStudio();
    } catch (error) { ui.status.textContent = error.message; } finally { ui.generate.disabled = false; }
}

async function exportCanva() {
    if (!latest) return;
    ui.canva.disabled = true;
    try {
        const response = await fetch('/api/images/canva-export', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...latest, caption: ui.caption.value.trim() || latest.caption }) });
        if (!response.ok) { const error = await response.json().catch(() => ({})); throw new Error(error.detail || 'ส่งออก Canva ไม่สำเร็จ'); }
        const url = URL.createObjectURL(await response.blob()), link = document.createElement('a'); link.href = url; link.download = 'mycodex-canva-pack.zip'; link.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
        ui.status.textContent = 'ดาวน์โหลด Canva Pack แล้ว';
    } catch (error) { ui.status.textContent = error.message; } finally { ui.canva.disabled = false; }
}

ui.generate.addEventListener('click', generate); ui.canva.addEventListener('click', exportCanva); loadStudio().catch(error => { ui.status.textContent = error.message; });
