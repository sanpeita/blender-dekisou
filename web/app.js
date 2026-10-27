const state = { index: [], run: null, activeStep: null };

const el = (id) => document.getElementById(id);
const video = el('video');

const fmt = (t) => {
  if (t == null || Number.isNaN(t)) return '—';
  const m = Math.floor(t / 60);
  const s = (t % 60).toFixed(1).padStart(4, '0');
  return m > 0 ? `${m}:${s}` : `${(t).toFixed(1)}s`;
};

async function boot() {
  const res = await fetch('data/index.json', { cache: 'no-cache' });
  state.index = await res.json();
  const nav = el('runs');
  nav.innerHTML = '';
  state.index.forEach((run, i) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.dataset.slug = run.slug;
    b.setAttribute('aria-pressed', i === 0 ? 'true' : 'false');
    b.innerHTML = `<span class="rt">${run.theme}</span>${run.title.replace('Blenderって無理そう？', '')} · ${run.duration}s`;
    b.addEventListener('click', () => select(run.slug, nav, true));
    nav.appendChild(b);
  });
  await select(state.index[0].slug, nav, false);
}

async function select(slug, nav, scroll) {
  [...nav.children].forEach((b) => {
    b.setAttribute('aria-pressed', b.dataset.slug === slug ? 'true' : 'false');
  });

  const res = await fetch(`data/${slug}.json`, { cache: 'no-cache' });
  const run = await res.json();
  state.run = run;

  video.poster = `media/poster_${slug}.jpg`;
  video.src = `media/${slug}.mp4`;
  video.load();

  el('runTitle').textContent = run.title;
  el('runPromise').textContent = run.promise || '';
  el('metaStyle').textContent = '9:16 / テロップ18字 / 1操作';
  const setLen = () => {
    const d = Number.isFinite(video.duration) ? video.duration : run.duration_sec;
    el('metaLen').textContent = `${d ? d.toFixed(1) : '—'}s / ${run.steps.length}工程`;
  };
  setLen();
  el('metaModel').textContent = (run.model || '').replace('nvidia/', '');
  el('metaValid').textContent = (run.validation_errors && run.validation_errors.length === 0)
    ? 'バリデータ通過（0件）' : `${(run.validation_errors || []).length} 件`;
  el('metaValid').className = (run.validation_errors || []).length === 0 ? 'ok' : '';

  const list = el('steps');
  list.innerHTML = '';
  run.steps.forEach((s) => {
    const li = document.createElement('li');
    li.dataset.id = s.id;
    li.innerHTML = `
      <div class="row"><span class="idx">${String(s.id).padStart(2, '0')}</span>
        <span class="cap">${s.caption}</span>
        <span class="time">${fmt(s.t_start)} – ${fmt(s.t_end)}</span></div>
      <p class="narr">${s.narration || ''}</p>
      <div class="code">${escapeHtml((s.code || '').split('\n').slice(0, 3).join('\n'))}</div>
      ${s.error ? `<p class="err">実行エラー: ${escapeHtml(s.error)}</p>` : ''}`;
    li.addEventListener('click', () => {
      if (s.t_start == null) return;
      video.currentTime = Math.max(0, s.t_start + 0.05);
      video.play().catch(() => {});
    });
    list.appendChild(li);
  });

  highlight(null);
  if (scroll) window.scrollTo({ top: nav.offsetTop - 12, behavior: 'smooth' });
}

function highlight(id) {
  if (state.activeStep === id) return;
  state.activeStep = id;
  document.querySelectorAll('.steps li').forEach((li) => {
    li.classList.toggle('active', String(li.dataset.id) === String(id));
  });
}

el('playbtn').addEventListener('click', () => { video.play().catch(() => {}); });
video.addEventListener('play', () => { el('playbtn').hidden = true; });
video.addEventListener('pause', () => { el('playbtn').hidden = false; });
video.addEventListener('ended', () => { el('playbtn').hidden = false; });

video.addEventListener('loadedmetadata', () => {
  const run = state.run;
  if (!run) return;
  el('metaLen').textContent = `${video.duration.toFixed(1)}s / ${run.steps.length}工程`;
  el('lenbadge').textContent = `${video.duration.toFixed(1)}s`;
  // 1フレーム目は黒いので、中盤の工程が見える位置で止めておく（ポスター代わり）
  if (!video.dataset.seeked) {
    const pick = run.steps[Math.min(3, run.steps.length - 1)];
    video.currentTime = pick && pick.t_start != null ? pick.t_start + 1.0 : 2.0;
    video.dataset.seeked = '1';
  }
});

video.addEventListener('timeupdate', () => {
  const run = state.run;
  if (!run) return;
  const t = video.currentTime;
  const current = run.steps.find((s) => s.t_start != null && t >= s.t_start && t < s.t_end);
  highlight(current ? current.id : null);
});

function escapeHtml(s) {
  return s.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
}

boot();
