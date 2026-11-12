"""Pipeline: rekonstrukcja (ffmpeg) -> separacja (Demucs htdemucs) -> eksport (FLAC, MP3, stemy, ZIP)."""
import os, subprocess, zipfile, json, time
import numpy as np
import soundfile as sf

SR = 44100
_model = None

def _ff(*args):
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args], check=True)

def _model_get():
    global _model
    if _model is None:
        from demucs.pretrained import get_model
        _model = get_model("htdemucs")
        _model.eval()
    return _model

def _device():
    import torch
    return "mps" if torch.backends.mps.is_available() else "cpu"

def separate(src, out_dir, restore="szelak", strength=2, hum=False, progress=lambda p, m: None):
    """src: dowolny plik audio; restore: preset odszumiania (szelak / winyl / lagodne) albo None."""
    import denoise
    import torch
    from demucs.apply import apply_model
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    progress(5, "Dekodowanie i rekonstrukcja")
    restored = os.path.join(out_dir, "rekonstrukcja.wav")
    dn = None
    if restore:
        dn = denoise.process(src, restored, restore, strength, hum, lambda p, m: progress(5 + int(p * 0.15), m))
        _ff("-i", restored, "-ac", "2", restored + ".st.wav")  # model oczekuje stereo
        os.replace(restored + ".st.wav", restored)
    else:
        _ff("-i", src, "-ac", "2", "-ar", str(SR), "-c:a", "pcm_s16le", restored)

    progress(20, "Separacja AI (Demucs)")
    wav, sr = sf.read(restored, dtype="float32", always_2d=True)
    x = torch.from_numpy(wav.T.copy())
    ref = x.mean(0)
    mean, std = ref.mean(), ref.std() + 1e-8
    x = (x - mean) / std
    model = _model_get()
    with torch.no_grad():
        dev = _device()
        try:
            est = apply_model(model, x[None], device=dev, shifts=1, split=True, overlap=0.25, progress=False)[0]
        except Exception:
            est = apply_model(model, x[None], device="cpu", shifts=1, split=True, overlap=0.25, progress=False)[0]
    est = est * std + mean
    stems = {name: est[i].cpu().numpy().T for i, name in enumerate(model.sources)}  # drums, bass, other, vocals

    progress(80, "Eksport plików")
    mix = {
        "wokal": stems["vocals"],
        "podklad": stems["drums"] + stems["bass"] + stems["other"],
        "rytm": stems["drums"] + stems["bass"],
        "melodia": stems["other"],
    }
    files = {}
    for name, data in mix.items():
        p = os.path.join(out_dir, f"{name}.flac")
        sf.write(p, np.clip(data, -1, 1), SR, format="FLAC", subtype="PCM_16")
        files[name] = p
    files["flac"] = os.path.join(out_dir, "nagranie.flac")
    _ff("-i", restored, "-c:a", "flac", files["flac"])
    files["mp3"] = os.path.join(out_dir, "nagranie.mp3")
    _ff("-i", restored, "-c:a", "libmp3lame", "-b:a", "320k", files["mp3"])
    files["preview"] = os.path.join(out_dir, "podglad.mp3")
    _ff("-i", restored, "-c:a", "libmp3lame", "-b:a", "128k", files["preview"])
    for name in mix:  # lekkie podglądy stemów do odtwarzacza w przeglądarce
        _ff("-i", files[name], "-c:a", "libmp3lame", "-b:a", "128k", os.path.join(out_dir, f"{name}.mp3"))
    files["zip"] = os.path.join(out_dir, "stemy.zip")
    with zipfile.ZipFile(files["zip"], "w", zipfile.ZIP_STORED) as z:
        for name in mix:
            z.write(files[name], f"{name}.flac")
    # prosta ocena jakości separacji: udział energii wokalu
    e = {k: float(np.mean(v ** 2)) for k, v in mix.items()}
    meta = {"model": "htdemucs (Demucs v4, MIT)", "denoise": dn,
            "seconds": round(time.time() - t0, 1), "energy": e,
            "vocal_ratio": round(e["wokal"] / (e["wokal"] + e["podklad"] + 1e-12), 3)}
    json.dump(meta, open(os.path.join(out_dir, "meta.json"), "w"), indent=1)
    os.remove(restored)
    progress(100, "Gotowe")
    return files, meta

if __name__ == "__main__":
    import sys
    f, m = separate(sys.argv[1], sys.argv[2], progress=lambda p, msg: print(p, msg, flush=True))
    print(json.dumps(m, indent=1))
