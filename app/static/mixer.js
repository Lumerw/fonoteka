// Mikser stemów: Web Audio, wspólny zegar dla wszystkich ścieżek; wycisz / solo / głośność.
document.querySelectorAll('.mixer').forEach(async (el) => {
  const stems = JSON.parse(el.dataset.stems);
  const playBtn = el.querySelector('.mx-play'), seek = el.querySelector('.mx-seek'), time = el.querySelector('.mx-time');
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  const tracks = {};
  let duration = 0, startAt = 0, offset = 0, playing = false, sources = [];
  const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
  const setBtn = () => { playBtn.textContent = playing ? '❚❚' : '▶'; playBtn.setAttribute('aria-label', playing ? el.dataset.lPause : el.dataset.lPlay); };
  try {
    await Promise.all(stems.map(async ([key, label, desc, url]) => {
      const buf = await ctx.decodeAudioData(await (await fetch(url)).arrayBuffer());
      const gain = ctx.createGain(); gain.connect(ctx.destination);
      tracks[key] = { buf, gain, row: el.querySelector(`[data-key="${key}"]`) };
      duration = Math.max(duration, buf.duration);
    }));
  } catch (e) { playBtn.textContent = '!'; playBtn.setAttribute('aria-label', 'Błąd wczytywania'); return; }
  playBtn.disabled = false; seek.disabled = false; setBtn(); time.textContent = `0:00 / ${fmt(duration)}`;
  const pressed = (b) => b.getAttribute('aria-pressed') === 'true';
  const levels = () => {
    const anySolo = Object.values(tracks).some((t) => pressed(t.row.querySelector('.mx-solo')));
    for (const t of Object.values(tracks)) {
      const mute = pressed(t.row.querySelector('.mx-mute')), solo = pressed(t.row.querySelector('.mx-solo'));
      t.gain.gain.value = (mute || (anySolo && !solo)) ? 0 : t.row.querySelector('.mx-vol').value / 100;
    }
  };
  el.querySelectorAll('.toggle').forEach((b) => b.addEventListener('click', () => { b.setAttribute('aria-pressed', !pressed(b)); levels(); }));
  el.querySelectorAll('.mx-vol').forEach((i) => i.addEventListener('input', levels));
  const stop = () => { sources.forEach((s) => { try { s.stop(); } catch (e) {} }); sources = []; };
  const play = () => {
    stop(); ctx.resume();
    sources = Object.values(tracks).map((t) => { const s = ctx.createBufferSource(); s.buffer = t.buf; s.connect(t.gain); s.start(0, offset); return s; });
    startAt = ctx.currentTime - offset; playing = true; setBtn(); levels();
  };
  const pause = () => { offset = ctx.currentTime - startAt; stop(); playing = false; setBtn(); };
  playBtn.addEventListener('click', () => (playing ? pause() : play()));
  seek.addEventListener('input', () => { offset = (seek.value / 1000) * duration; if (playing) play(); time.textContent = `${fmt(offset)} / ${fmt(duration)}`; });
  (function tick() {
    if (playing) {
      const pos = ctx.currentTime - startAt;
      if (pos >= duration) { pause(); offset = 0; }
      else { seek.value = (pos / duration) * 1000; time.textContent = `${fmt(pos)} / ${fmt(duration)}`; }
    }
    requestAnimationFrame(tick);
  })();
});
