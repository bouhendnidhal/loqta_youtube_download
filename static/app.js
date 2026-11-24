const $ = (id) => document.getElementById(id);
const token = document.querySelector('meta[name="app-token"]').content;
let inspection = null, currentJobs = [], lastJobs = '';
function showPreferences(show) {
  $('preferences-panel').classList.toggle('hidden', !show);
  $('settings-toggle').setAttribute('aria-expanded', String(show));
}
$('settings-toggle').addEventListener('click', () => showPreferences($('preferences-panel').classList.contains('hidden')));
$('settings-close').addEventListener('click', () => showPreferences(false));
async function loadPreferences() {
  try {
    const settings = await api('/api/settings');
    document.body.dataset.theme = settings.theme;
    $('theme-choice').value = settings.theme;
    $('folder-choice').value = settings.output_folder;
  } catch (error) { $('settings-message').textContent = error.message; }
}
$('theme-choice').addEventListener('change', async () => {
  try {
    const settings = await api('/api/settings', 'POST', {theme: $('theme-choice').value});
    document.body.dataset.theme = settings.theme;
    $('settings-message').textContent = 'تم حفظ المظهر.';
  } catch (error) { $('settings-message').textContent = error.message; }
});
$('folder-pick').addEventListener('click', async () => {
  $('settings-message').textContent = '';
  try {
    if (!window.pywebview?.api?.choose_folder) throw new Error('اختيار المجلد متاح داخل تطبيق Windows.');
    const folder = await window.pywebview.api.choose_folder();
    if (!folder) return;
    const settings = await api('/api/settings', 'POST', {output_folder: folder});
    $('folder-choice').value = settings.output_folder;
    $('settings-message').textContent = 'التحميلات الجديدة راح تتحفظ في المجلد المختار.';
  } catch (error) { $('settings-message').textContent = error.message; }
});
async function api(path, method = 'GET', body) {
  const response = await fetch(path, {method, headers: {'Content-Type': 'application/json', 'X-App-Token': token}, body: body ? JSON.stringify(body) : undefined});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'تعذّر إكمال الطلب.');
  return data;
}
function duration(seconds) {
  const value = Math.max(0, Math.floor(seconds));
  return [Math.floor(value / 3600), Math.floor(value / 60) % 60, value % 60].map(x => String(x).padStart(2, '0')).join(':');
}
function bytes(value) {
  if (!value) return '0 KB';
  if (value < 1024 ** 2) return (value / 1024).toFixed(1) + ' KB';
  return value >= 1024 ** 3 ? (value / 1024 ** 3).toFixed(2) + ' GB' : (value / 1024 ** 2).toFixed(1) + ' MB';
}
function node(tag, text, cls) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (cls) element.className = cls;
  return element;
}
$('url').addEventListener('input', () => { inspection = null; $('settings').disabled = true; $('video').classList.add('hidden'); });
$('inspect-form').addEventListener('submit', async event => {
  event.preventDefault();
  $('message').textContent = ''; $('inspect-btn').disabled = true; $('inspect-btn').textContent = 'جاري التحليل…';
  $('settings').disabled = true; inspection = null; $('video').classList.add('hidden');
  const url = $('url').value.trim();
  try {
    const data = await api('/api/inspect', 'POST', {url});
    if ($('url').value.trim() !== url) return;
    inspection = data;
    $('video-title').textContent = data.title;
    $('video-meta').textContent = `${data.channel} · ${duration(data.duration)} · ${data.heights.length ? 'حتى ' + Math.max(...data.heights) + 'p' : 'صوت فقط'}`;
    $('video').classList.remove('hidden'); $('settings').disabled = false;
    $('start').value = ''; $('end').value = '';
    for (const option of $('quality').options) option.disabled = data.heights.length > 0 && Number(option.value) < Math.min(...data.heights);
    if ($('quality').selectedOptions[0]?.disabled) $('quality').value = [...$('quality').options].find(o => !o.disabled)?.value || '1080';
  } catch (error) { $('message').textContent = error.message; }
  finally { $('inspect-btn').disabled = false; $('inspect-btn').textContent = 'تحليل الرابط'; }
});
document.querySelectorAll('input[name="kind"]').forEach(input => input.addEventListener('change', () => {
  const audio = document.querySelector('input[name="kind"]:checked').value === 'mp3';
  $('video-quality').classList.toggle('hidden', audio); $('audio-quality').classList.toggle('hidden', !audio);
}));
$('download-form').addEventListener('submit', async event => {
  event.preventDefault(); if (!inspection) return;
  $('download-btn').disabled = true; $('message').textContent = '';
  try {
    await api('/api/jobs', 'POST', {inspection_id: inspection.inspection_id, kind: document.querySelector('input[name="kind"]:checked').value, quality: $('quality').value, bitrate: $('bitrate').value, start: $('start').value.trim(), end: $('end').value.trim()});
    await refresh();
  } catch (error) { $('message').textContent = error.message; }
  finally { $('download-btn').disabled = false; }
});
function renderJobs(jobs) {
  $('jobs').replaceChildren(); $('empty').classList.toggle('hidden', jobs.length > 0); $('count').textContent = jobs.length + ' ملفات';
  for (const job of jobs) {
    const card = node('article', undefined, 'job'); card.append(node('h3', job.title));
    const s = job.settings;
    card.append(node('div', `${s.kind.toUpperCase()} · ${s.kind === 'mp4' ? 'حتى ' + s.quality + 'p' : s.bitrate + ' kbps'} · ${duration(s.start)} — ${s.end === null ? 'النهاية' : duration(s.end)}`, 'job-meta'));
    card.append(node('div', job.stage, 'job-stage' + (job.status === 'error' ? ' error' : '')));
    const progress = node('progress'); progress.max = 100; progress.value = job.progress; progress.setAttribute('aria-label', 'تقدم ' + job.title); card.append(progress);
    const stats = [`${Math.round(job.progress)}%`];
    if (job.speed) stats.push(bytes(job.speed) + '/s');
    if (job.eta != null) stats.push('متبقي للمسار: ' + duration(job.eta));
    if (job.size) stats.push(bytes(job.size));
    card.append(node('div', stats.join(' · '), 'job-stats'));
    if (job.saved_to) card.append(node('div', 'حُفظ في: ' + job.saved_to, 'job-stage'));
    const actions = node('div', undefined, 'job-actions');
    if (job.status === 'done') {
      const link = node('a', 'حفظ الملف', 'save'); link.href = `/api/jobs/${job.id}/file`; link.download = ''; actions.append(link);
      for (const [method, label, icon] of [
        ['show_in_folder', 'إظهار الملف في المجلد', '<path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v10H3V7Z"/><path d="M3 9h18"/>'],
        ['open_file', s.kind === 'mp3' ? 'تشغيل الصوت' : 'تشغيل الفيديو', '<path d="M8 5v14l11-7-11-7Z"/>']
      ]) {
        const button = node('button', undefined, 'file-action'); button.type = 'button';
        button.setAttribute('aria-label', label); button.title = label;
        button.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true">${icon}</svg>`;
        button.onclick = async () => {
          try {
            if (!window.pywebview?.api?.[method]) throw new Error('هذه الخاصية متاحة داخل تطبيق Windows.');
            const result = await window.pywebview.api[method](job.id);
            if (!result.ok) throw new Error(result.error);
          } catch (error) { $('message').textContent = error.message; }
        };
        actions.append(button);
      }
    }
    if (job.status === 'error') {
      const retry = node('button', 'إعادة المحاولة'); retry.onclick = async () => {
        retry.disabled = true;
        try { const info = await api('/api/inspect', 'POST', {url: job.url}); await api('/api/jobs', 'POST', {...s, inspection_id: info.inspection_id}); await refresh(); }
        catch (error) { $('message').textContent = error.message; } finally { retry.disabled = false; }
      }; actions.append(retry);
      const details = node('details'); details.append(node('summary', 'تفاصيل الخطأ'), node('pre', job.error || job.stage)); card.append(details);
    }
    if (['done', 'error'].includes(job.status)) {
      const remove = node('button', 'حذف من الجهاز', 'delete'); remove.onclick = async () => {
        if (!confirm('حذف هذا الملف وسجله من جهازك؟')) return;
        try { await api(`/api/jobs/${job.id}`, 'DELETE'); await refresh(); } catch (error) { $('message').textContent = error.message; }
      }; actions.append(remove);
    }
    card.append(actions); $('jobs').append(card);
  }
}
async function refresh() {
  try {
    currentJobs = await api('/api/jobs'); $('connection').textContent = '';
    const serialized = JSON.stringify(currentJobs);
    if (serialized !== lastJobs) { renderJobs(currentJobs); lastJobs = serialized; }
  } catch (error) { $('connection').textContent = 'انقطع الاتصال بالتطبيق. تأكد أن نافذة التشغيل مفتوحة.'; }
}
async function poll() { await refresh(); setTimeout(poll, 1200); }
api('/api/health').then(data => { $('health').textContent = data.ready ? 'الأدوات جاهزة · FFmpeg + yt-dlp + Node.js' : 'أدوات ناقصة: ' + Object.entries(data.tools).filter(([, ready]) => !ready).map(([name]) => name).join(', '); }).catch(() => { $('health').textContent = 'تعذّر فحص الأدوات.'; });
loadPreferences();
poll();
