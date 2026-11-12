// Mikser stemów: Web Audio, wspólny zegar dla wszystkich ścieżek, wycisz/solo/głośność.
document.querySelectorAll('.mixer').forEach(async (el) => {
  const stems = JSON.parse(el.dataset.stems);
  const playBtn = el.querySelector('.mx-play'), seek = el.querySelector('.mx-seek'), time = el.querySelector('.mx-time');
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  const tracks = {};
  let duration = 0, startAt = 0, offset = 0, playing = false, sources = [];
  const fmt = s => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
  try {
    await Promise.all(stems.map(async ([key, label, url]) => {
      const buf = await ctx.decodeAudioData(await (await fetch(url)).arrayBuffer());
      const gain = ctx.createGain(); gain.connect(ctx.destination);
      tracks[key] = { buf, gain, row: el.querySelector(`tr[data-key="${key}"]`) };
      duration = Math.max(duration, buf.duration);
    }));
  } catch (e) { playBtn.textContent = 'Błąd wczytywania'; return; }
  playBtn.disabled = false; seek.disabled = false; playBtn.textContent = el.dataset.lPlay;
  const levels = () => {
    const anySolo = Object.values(tracks).some(t => t.row.querySelector('.mx-solo').checked);
    for (const t of Object.values(tracks)) {
      const mute = t.row.querySelector('.mx-mute').checked, solo = t.row.querySelector('.mx-solo').checked;
      const vol = t.row.querySelector('.mx-vol').value / 100;
      t.gain.gain.value = (mute || (anySolo && !solo)) ? 0 : vol;
    }
  };
  el.querySelectorAll('input').forEach(i => i.addEventListener('input', levels));
  const stop = () => { sources.forEach(s => { try { s.stop(); } catch (e) {} }); sources = []; };
  const play = () => {
    stop(); ctx.resume();
    sources = Object.values(tracks).map(t => { const s = ctx.createBufferSource(); s.buffer = t.buf; s.connect(t.gain); s.start(0, offset); return s; });
    startAt = ctx.currentTime - offset; playing = true; playBtn.textContent = el.dataset.lPause; levels();
  };
  const pause = () => { offset = ctx.currentTime - startAt; stop(); playing = false; playBtn.textContent = el.dataset.lPlay; };
  playBtn.addEventListener('click', () => playing ? pause() : play());
  seek.addEventListener('input', () => { offset = seek.value / 1000 * duration; if (playing) play(); time.textContent = fmt(offset); });
  (function tick() {
    if (playing) {
      const pos = ctx.currentTime - startAt;
      if (pos >= duration) { pause(); offset = 0; }
      else { seek.value = pos / duration * 1000; time.textContent = `${fmt(pos)} / ${fmt(duration)}`; }
    }
    requestAnimationFrame(tick);
  })();
});
