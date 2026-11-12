"""Odszumianie nagrań z płyt szelakowych (78 obr./min) i winylowych.
Klasyczne przetwarzanie sygnału (FFmpeg) – działa bez AI i bez GPU, deterministycznie:
  1. dudnienie (rumble): filtr górnoprzepustowy,
  2. przydźwięk sieciowy 50 Hz i harmoniczne (opcjonalnie),
  3. trzaski i kliki: adeclick (detekcja impulsów + interpolacja autoregresyjna),
  4. szum ciągły (syk, szum przesuwu igły): afftdn z profilem szumu pobranym z najcichszego fragmentu,
  5. pasmo: dolnoprzepustowy tam, gdzie nośnik nie niesie muzyki (szelak ok. 8–10 kHz),
  6. normalizacja głośności (EBU R128).
"""
import json, subprocess, os
import numpy as np
import soundfile as sf

SR = 44100

PRESETS = {
    # nazwa: (mono, highpass Hz, lowpass Hz lub None, adeclick próg, redukcja szumu dB [łagodnie, średnio, mocno])
    "szelak": dict(label="Płyta szelakowa 78 obr./min", mono=True, hp=50, lp=9000, click_t=[3, 2, 1.5], nr=[8, 14, 20]),
    "winyl": dict(label="Płyta winylowa", mono=False, hp=25, lp=None, click_t=[4, 3, 2], nr=[4, 8, 12]),
    "lagodne": dict(label="Łagodne (nagrania mało zaszumione)", mono=False, hp=30, lp=None, click_t=[6, 4, 3], nr=[3, 5, 8]),
}


def _ff(args):
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args], check=True)


def _quietest(wav, sr, win=0.5, search=None):
    """Zwraca (start_s, rms_db) najcichszego okna – zwykle rowek wejściowy albo pauza."""
    x = wav.mean(1) if wav.ndim == 2 else wav
    if search:
        x = x[: int(search * sr)]
    n = int(win * sr)
    if len(x) < n * 2:
        return 0.0, -90.0
    hop = n // 2
    frames = np.lib.stride_tricks.sliding_window_view(x, n)[::hop]
    rms = np.sqrt((frames ** 2).mean(1) + 1e-12)
    # pomijamy ciszę cyfrową i okna przed opuszczeniem igły (ponad 40 dB poniżej średniej)
    overall = np.sqrt((x ** 2).mean() + 1e-12)
    rms[rms < overall * 10 ** (-40 / 20)] = np.inf
    i = int(np.argmin(rms))
    return i * hop / sr, float(20 * np.log10(rms[i])) if np.isfinite(rms[i]) else -90.0


def _noise_rel_db(path, at, win=0.5):
    """Poziom szumu w oknie [at, at+win] względem średniego poziomu całego nagrania (dB)."""
    w, sr = sf.read(path, dtype="float32", always_2d=True)
    x = w.mean(1)
    seg = x[int(at * sr): int((at + win) * sr)]
    if len(seg) < sr * 0.1:
        return None
    db = lambda v: 20 * np.log10(np.sqrt((v ** 2).mean()) + 1e-9)
    return float(db(seg) - db(x))


def _normalize(path, target_db=-18.0, peak_db=-1.0):
    """Stałe wzmocnienie (bez kompresji dynamiki): średni poziom -18 dBFS, szczyt maks. -1 dBFS."""
    w, sr = sf.read(path, dtype="float32", always_2d=True)
    rms = np.sqrt((w ** 2).mean() + 1e-12)
    g = 10 ** (target_db / 20) / rms
    peak = np.abs(w).max() * g
    if peak > 10 ** (peak_db / 20):
        g *= 10 ** (peak_db / 20) / peak
    sf.write(path, (w * g).squeeze(), sr, subtype="PCM_16")


def chain(preset="szelak", strength=2, hum=False, noise_at=None):
    p = PRESETS[preset]
    s = max(1, min(3, int(strength))) - 1
    f = [f"highpass=f={p['hp']}:poles=2"]
    if hum:
        f += [f"bandreject=f={h}:width_type=q:w=30" for h in (50, 100, 150, 200)]
    f.append(f"adeclick=t={p['click_t'][s]}:w=55:o=75:b=2")
    if noise_at is not None:
        a, b = noise_at, noise_at + 0.5
        f += [f"asendcmd=c='{a:.2f} afftdn@dn sn start; {b:.2f} afftdn@dn sn stop'"]
    f.append(f"afftdn@dn=nr={p['nr'][s]}:nf=-50:tn=1")
    if p["lp"]:
        f.append(f"lowpass=f={p['lp']}:poles=2")
    return ",".join(f)


def process(src, dst, preset="szelak", strength=2, hum=False, progress=lambda p, m: None):
    """Odszumia plik src do dst (WAV 44,1 kHz/16 bit). Zwraca metadane z pomiarami."""
    p = PRESETS[preset]
    tmp = dst + ".in.wav"
    progress(5, "Dekodowanie")
    _ff(["-i", src, "-ac", "1" if p["mono"] else "2", "-ar", str(SR), "-c:a", "pcm_s16le", tmp])
    w, sr = sf.read(tmp, dtype="float32", always_2d=True)
    start, q_db = _quietest(w, sr, search=20) if len(w) > sr * 25 else _quietest(w, sr)
    progress(15, "Usuwanie trzasków i szumu")
    flt = chain(preset, strength, hum, noise_at=start)
    _ff(["-i", tmp, "-af", flt, "-ar", str(SR), "-c:a", "pcm_s16le", dst])
    progress(85, "Normalizacja głośności")
    _normalize(dst)
    progress(90, "Pomiar")
    before, after = _noise_rel_db(tmp, start), _noise_rel_db(dst, start)
    os.remove(tmp)
    meta = {"preset": preset, "preset_label": p["label"], "strength": strength, "hum": hum,
            "noise_profile_at_s": round(start, 2), "filters": flt,
            "noise_before_db": before and round(before, 1), "noise_after_db": after and round(after, 1),
            "noise_reduction_db": (before is not None and after is not None) and round(before - after, 1) or None}
    progress(100, "Gotowe")
    return meta


def process_job(src, out_dir, preset="szelak", strength=2, hum=False, progress=lambda p, m: None):
    """Narzędzie „Odszumianie”: oryginał + wynik w MP3 (odsłuch A/B) oraz FLAC/WAV do pobrania."""
    os.makedirs(out_dir, exist_ok=True)
    clean = os.path.join(out_dir, "odszumione.wav")
    meta = process(src, clean, preset, strength, hum, lambda p_, m: progress(int(p_ * 0.85), m))
    progress(90, "Eksport")
    _ff(["-i", src, "-t", "600", "-ar", str(SR), "-c:a", "libmp3lame", "-b:a", "160k", os.path.join(out_dir, "przed.mp3")])
    _ff(["-i", clean, "-c:a", "libmp3lame", "-b:a", "160k", os.path.join(out_dir, "po.mp3")])
    _ff(["-i", clean, "-c:a", "flac", os.path.join(out_dir, "odszumione.flac")])
    _ff(["-i", clean, "-c:a", "libmp3lame", "-b:a", "320k", os.path.join(out_dir, "odszumione.mp3")])
    json.dump(meta, open(os.path.join(out_dir, "meta.json"), "w"), indent=1)
    progress(100, "Gotowe")
    return meta


if __name__ == "__main__":
    import sys, time
    t = time.time()
    m = process(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "szelak", 2)
    print(json.dumps(m, indent=1, ensure_ascii=False), round(time.time() - t, 1), "s")
