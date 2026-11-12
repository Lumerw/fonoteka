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
