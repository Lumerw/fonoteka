// Wspólne zachowania interfejsu: zakładki (ARIA tabs) i krótki odsłuch na listach.
(function () {
  // --- zakładki: <div data-tabs> z [role=tablist] i panelami [role=tabpanel]; bez JS wszystkie panele są widoczne
  document.querySelectorAll('[data-tabs]').forEach((root) => {
    const tabs = [...root.querySelectorAll('[role=tab]')];
    const panels = tabs.map((t) => document.getElementById(t.getAttribute('aria-controls')));
    const select = (i, focus, push) => {
      tabs.forEach((t, j) => {
        const on = i === j;
        t.setAttribute('aria-selected', on); t.tabIndex = on ? 0 : -1;
        panels[j].hidden = !on;
      });
      if (focus) tabs[i].focus();
      if (push) history.replaceState(null, '', '#' + panels[i].id);
    };
    tabs.forEach((t, i) => {
      t.addEventListener('click', () => select(i, false, true));
      t.addEventListener('keydown', (e) => {
        const k = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
        if (k) { e.preventDefault(); select((i + k + tabs.length) % tabs.length, true, true); }
        if (e.key === 'Home') { e.preventDefault(); select(0, true, true); }
        if (e.key === 'End') { e.preventDefault(); select(tabs.length - 1, true, true); }
      });
    });
    const fromHash = () => { const i = panels.findIndex((p) => '#' + p.id === location.hash); return i < 0 ? 0 : i; };
    select(fromHash(), false, false);
    window.addEventListener('hashchange', () => select(fromHash(), false, false));
    // linki do zakładek z innych miejsc strony (np. panel boczny)
    document.querySelectorAll('a[data-tab]').forEach((a) => a.addEventListener('click', (e) => {
      const i = panels.findIndex((p) => p.id === a.dataset.tab);
      if (i >= 0) { e.preventDefault(); select(i, true, true); root.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
    }));
  });

  // --- krótki odsłuch na listach: jeden wspólny odtwarzacz
  const btns = document.querySelectorAll('.play-mini');
  if (btns.length) {
    const audio = new Audio(); let current = null;
    const reset = () => { if (current) { current.setAttribute('aria-pressed', 'false'); current.textContent = '▶'; } };
    btns.forEach((b) => b.addEventListener('click', () => {
      if (current === b && !audio.paused) { audio.pause(); reset(); current = null; return; }
      reset(); current = b; audio.src = b.dataset.src; audio.play();
      b.setAttribute('aria-pressed', 'true'); b.textContent = '❚❚';
    }));
    audio.addEventListener('ended', () => { reset(); current = null; });
  }
})();

// ================= własne kontrolki =================
(function () {
  const L = window.FONO || { play: 'Odtwórz', pause: 'Pauza', choose: 'Wybierz plik', drop: 'lub przeciągnij go tutaj', position: 'Pozycja odtwarzania' };
  const fmt = (s) => (isFinite(s) ? `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}` : '–:––');

  // --- suwaki: wypełnienie do pozycji kciuka (zmienna --p)
  const paint = (r) => { const min = +r.min || 0, max = +r.max || 100; r.style.setProperty('--p', ((r.value - min) / (max - min)) * 100 + '%'); };
  window.fonoPaintRange = paint;
  document.querySelectorAll('input[type=range]').forEach((r) => { paint(r); r.addEventListener('input', () => paint(r)); });

  // --- rozwijane menu (details): zamykanie kliknięciem obok i klawiszem Esc
  document.addEventListener('click', (e) => document.querySelectorAll('details.dropdown[open], details.mobile-menu[open]').forEach((d) => { if (!d.contains(e.target)) d.open = false; }));
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') document.querySelectorAll('details.dropdown[open], details.mobile-menu[open]').forEach((d) => { d.open = false; d.querySelector('summary').focus(); }); });

  // --- lista wyboru: przycisk + lista opcji (wzorzec ARIA „select-only combobox”); natywny <select> zostaje w formularzu
  let uid = 0;
  document.querySelectorAll('select:not([multiple]):not([data-native])').forEach((sel) => {
    const id = 'sel' + (++uid);
    const wrap = document.createElement('div'); wrap.className = 'select';
    sel.parentNode.insertBefore(wrap, sel); wrap.appendChild(sel);
    sel.tabIndex = -1; sel.setAttribute('aria-hidden', 'true');
    const btn = document.createElement('button'); btn.type = 'button'; btn.className = 'select-btn';
    btn.setAttribute('role', 'combobox'); btn.setAttribute('aria-haspopup', 'listbox'); btn.setAttribute('aria-expanded', 'false'); btn.setAttribute('aria-controls', id + '-list');
    const label = sel.id && document.querySelector(`label[for="${sel.id}"]`);
    if (label) { label.id = label.id || id + '-lbl'; label.setAttribute('for', ''); label.addEventListener('click', () => btn.focus()); btn.setAttribute('aria-labelledby', label.id + ' ' + id + '-btn'); }
    btn.id = id + '-btn';
    const txt = document.createElement('span'); btn.appendChild(txt);
    const list = document.createElement('ul'); list.className = 'select-list'; list.id = id + '-list'; list.setAttribute('role', 'listbox'); list.hidden = true; list.tabIndex = -1;
    if (label) list.setAttribute('aria-labelledby', label.id);
    const opts = [...sel.options].map((o, i) => {
      const li = document.createElement('li'); li.setAttribute('role', 'option'); li.id = `${id}-o${i}`; li.textContent = o.textContent; li.dataset.i = i; list.appendChild(li); return li;
    });
    wrap.append(btn, list);
    let active = sel.selectedIndex;
    const render = () => {
      const o = sel.options[sel.selectedIndex];
      txt.textContent = o ? o.textContent : ''; txt.className = !o || o.value === '' ? 'ph' : '';
      opts.forEach((li, i) => li.setAttribute('aria-selected', i === sel.selectedIndex));
    };
    const setActive = (i) => { active = Math.max(0, Math.min(opts.length - 1, i)); opts.forEach((li, j) => li.classList.toggle('active', j === active)); btn.setAttribute('aria-activedescendant', opts[active].id); opts[active].scrollIntoView({ block: 'nearest' }); };
    const open = () => { list.hidden = false; btn.setAttribute('aria-expanded', 'true'); setActive(sel.selectedIndex < 0 ? 0 : sel.selectedIndex); };
    const close = () => { list.hidden = true; btn.setAttribute('aria-expanded', 'false'); btn.removeAttribute('aria-activedescendant'); };
    const choose = (i) => { if (sel.selectedIndex !== i) { sel.selectedIndex = i; sel.dispatchEvent(new Event('change', { bubbles: true })); } render(); close(); btn.focus(); };
    btn.addEventListener('click', () => (list.hidden ? open() : close()));
    list.addEventListener('mousedown', (e) => e.preventDefault());
    list.addEventListener('click', (e) => { const li = e.target.closest('[role=option]'); if (li) choose(+li.dataset.i); });
    list.addEventListener('mousemove', (e) => { const li = e.target.closest('[role=option]'); if (li) setActive(+li.dataset.i); });
    let typed = '', typedAt = 0;
    btn.addEventListener('keydown', (e) => {
      const isOpen = !list.hidden;
      if (['ArrowDown', 'ArrowUp'].includes(e.key)) { e.preventDefault(); if (!isOpen) open(); else setActive(active + (e.key === 'ArrowDown' ? 1 : -1)); }
      else if (e.key === 'Home' && isOpen) { e.preventDefault(); setActive(0); }
      else if (e.key === 'End' && isOpen) { e.preventDefault(); setActive(opts.length - 1); }
      else if ((e.key === 'Enter' || e.key === ' ') ) { e.preventDefault(); isOpen ? choose(active) : open(); }
      else if (e.key === 'Escape' && isOpen) { e.preventDefault(); close(); }
      else if (e.key === 'Tab' && isOpen) { choose(active); }
      else if (e.key.length === 1 && /\S/.test(e.key)) {
        const now = Date.now(); typed = (now - typedAt < 600 ? typed : '') + e.key.toLowerCase(); typedAt = now;
        const i = opts.findIndex((li) => li.textContent.toLowerCase().startsWith(typed));
        if (i >= 0) { if (!isOpen) open(); setActive(i); }
      }
    });
    btn.addEventListener('blur', () => setTimeout(() => { if (!wrap.contains(document.activeElement)) close(); }, 0));
    sel.addEventListener('change', render);
    if (sel.disabled || sel.closest('fieldset[disabled]')) btn.disabled = true;
    render();
  });

  // --- plik: własny przycisk, nazwa pliku i przeciąganie na pole
  document.querySelectorAll('.dropzone').forEach((dz) => {
    const input = dz.querySelector('input[type=file]'); if (!input) return;
    const box = document.createElement('span'); box.className = 'file';
    const btn = document.createElement('span'); btn.className = 'btn secondary small'; btn.textContent = L.choose;
    const name = document.createElement('span'); name.className = 'file-name'; name.textContent = L.drop; name.setAttribute('aria-live', 'polite');
    input.parentNode.insertBefore(box, input); box.append(input, btn, name);
    const show = () => { const f = input.files[0]; name.textContent = f ? `${f.name} · ${(f.size / 1048576).toFixed(1)} MB` : L.drop; name.classList.toggle('set', !!f); };
    input.addEventListener('change', show);
    ['dragenter', 'dragover'].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add('drag'); }));
    ['dragleave', 'drop'].forEach((ev) => dz.addEventListener(ev, () => dz.classList.remove('drag')));
    dz.addEventListener('drop', (e) => { e.preventDefault(); if (e.dataTransfer.files.length && !input.disabled) { input.files = e.dataTransfer.files; show(); } });
  });

  // --- odtwarzacz: zamiast systemowych kontrolek <audio>
  document.querySelectorAll('audio[controls]').forEach((au) => {
    au.controls = false;
    const box = document.createElement('div'); box.className = 'player';
    const play = document.createElement('button'); play.type = 'button'; play.className = 'btn pl-play'; play.textContent = '▶'; play.setAttribute('aria-label', L.play);
    const seek = document.createElement('input'); seek.type = 'range'; seek.min = 0; seek.max = 1000; seek.value = 0; seek.setAttribute('aria-label', au.getAttribute('aria-label') ? L.position + ': ' + au.getAttribute('aria-label') : L.position);
    const time = document.createElement('span'); time.className = 'pl-time'; time.textContent = '0:00 / –:––';
    au.parentNode.insertBefore(box, au); box.append(play, seek, time, au);
    if (au.style.marginBottom) { box.style.marginBottom = au.style.marginBottom; }
    const upd = () => { const d = au.duration; if (!seeking) seek.value = d ? (au.currentTime / d) * 1000 : 0; paint(seek); time.textContent = `${fmt(au.currentTime)} / ${fmt(d)}`; };
    let seeking = false;
    play.addEventListener('click', () => {
      if (au.paused) { document.querySelectorAll('.player audio').forEach((o) => o !== au && o.pause()); au.play(); } else au.pause();
    });
    au.addEventListener('play', () => { play.textContent = '❚❚'; play.setAttribute('aria-label', L.pause); });
    au.addEventListener('pause', () => { play.textContent = '▶'; play.setAttribute('aria-label', L.play); });
    ['timeupdate', 'loadedmetadata', 'durationchange', 'ended'].forEach((ev) => au.addEventListener(ev, upd));
    seek.addEventListener('input', () => { seeking = true; paint(seek); if (au.duration) time.textContent = `${fmt((seek.value / 1000) * au.duration)} / ${fmt(au.duration)}`; });
    seek.addEventListener('change', () => { if (au.duration) au.currentTime = (seek.value / 1000) * au.duration; seeking = false; });
    upd();
  });
})();
