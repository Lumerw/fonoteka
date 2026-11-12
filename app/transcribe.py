"""Automatyczny SZKIC zapisu nutowego: melodia z wokalu (pYIN) + akordy z podkładu (chroma).
To punkt wyjścia dla muzyka-transkryptora, nie gotowa transkrypcja."""
import numpy as np, librosa

NOTES_SHARP = ['C', '^C', 'D', '^D', 'E', 'F', '^F', 'G', '^G', 'A', '^A', 'B']
NOTES_FLAT = ['C', '_D', 'D', '_E', 'E', 'F', '_G', 'G', '_A', 'A', '_B', 'B']
NAMES_SHARP = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
NAMES_FLAT = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']
MAJ = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MIN = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
FLAT_KEYS = {'F', 'Bb', 'Eb', 'Ab', 'Db', 'Gb', 'Dm', 'Gm', 'Cm', 'Fm', 'Bbm', 'Ebm'}

def _key(chroma_sum):
    best = None
    for t in range(12):
        for prof, suf in ((MAJ, ''), (MIN, 'm')):
            r = np.corrcoef(np.roll(prof, t), chroma_sum)[0, 1]
            if best is None or r > best[0]:
                best = (r, t, suf)
    _, t, suf = best
    name = NAMES_SHARP[t] + suf
    if (NAMES_FLAT[t] + suf) in FLAT_KEYS:
        name = NAMES_FLAT[t] + suf
    return name, name in FLAT_KEYS

def _abc_note(midi, flat):
    pc, octv = midi % 12, midi // 12 - 1
    n = (NOTES_FLAT if flat else NOTES_SHARP)[pc]
    acc, letter = (n[0], n[1]) if len(n) == 2 else ('', n)
    if octv >= 5:
        s = acc + letter.lower() + "'" * (octv - 5)
    else:
        s = acc + letter + "," * (4 - octv)
    return s

def _dur(n):  # n w ósemkach (L:1/8)
    return '' if n == 1 else str(n)

def draft(vocal_path, accomp_path, title='', composer='', max_bars=32):
    y_acc, sr = librosa.load(accomp_path, sr=22050, mono=True)
    tempo, beats = librosa.beat.beat_track(y=y_acc, sr=sr, units='time')
    tempo = float(np.atleast_1d(tempo)[0])
    if len(beats) < 8:
        return None
    y_voc, _ = librosa.load(vocal_path, sr=sr, mono=True)
    f0, voiced, _ = librosa.pyin(y_voc, fmin=80, fmax=900, sr=sr, frame_length=2048, hop_length=256)
    times = librosa.times_like(f0, sr=sr, hop_length=256)
    chroma = librosa.feature.chroma_cqt(y=y_acc, sr=sr, hop_length=512)
    ctimes = librosa.times_like(chroma, sr=sr, hop_length=512)
    key, flat = _key(chroma.sum(1))
    # siatka ósemek: każdy beat dzielimy na 2
    grid = []
    for a, b in zip(beats[:-1], beats[1:]):
        m = (a + b) / 2
        grid += [(a, m), (m, b)]
    cells = []
    for a, b in grid:
        sel = (times >= a) & (times < b)
        v = voiced[sel]
        if sel.sum() == 0 or v.mean() < 0.5:
            cells.append(None)
        else:
            cells.append(int(round(np.median(librosa.hz_to_midi(f0[sel][v[:len(f0[sel])]])))))
    # błędy oktawowe pYIN: sprowadzamy nuty do ±oktawy od mediany melodii
    vals = [c for c in cells if c is not None]
    if vals:
        med = int(np.median(vals))
        for i, c in enumerate(cells):
            if c is None:
                continue
            while c < med - 9:
                c += 12
            while c > med + 9:
                c -= 12
            cells[i] = c
    # akordy na takt (8 ósemek)
    names = NAMES_FLAT if flat else NAMES_SHARP
    templ = []
    for r in range(12):
        for q, suf in ((4, ''), (3, 'm')):
            t = np.zeros(12); t[[r, (r + q) % 12, (r + 7) % 12]] = 1
            templ.append((names[r] + suf, t / np.linalg.norm(t)))
    bars = []
    for i in range(0, min(len(cells), max_bars * 8) - 7, 8):
        a, b = grid[i][0], grid[i + 7][1]
        c = chroma[:, (ctimes >= a) & (ctimes < b)].mean(1)
        c = c / (np.linalg.norm(c) + 1e-9)
        chord = max(templ, key=lambda t: float(c @ t[1]))[0]
        seg, out, j = cells[i:i + 8], [], 0
        while j < 8:
            k = j
            while k + 1 < 8 and seg[k + 1] == seg[j]:
                k += 1
            n = k - j + 1
            out.append(('z' if seg[j] is None else _abc_note(seg[j], flat)) + _dur(n))
            j = k + 1
        bars.append(f'"{chord}"' + ''.join(out))
    lines = [' | '.join(bars[i:i + 4]) + ' |' for i in range(0, len(bars), 4)]
    abc = '\n'.join([
        'X:1', f'T:{title}', 'T:(szkic automatyczny – do korekty)', f'C:{composer}',
        'M:4/4', 'L:1/8', f'Q:1/4={int(round(tempo))}', f'N:Szacowana tonacja: {key}. Znaki chromatyczne zapisane przy nutach.', 'K:C', *lines])
    return {'abc': abc, 'key': key, 'tempo': round(tempo), 'bars': len(bars)}

if __name__ == '__main__':
    import sys
    r = draft(sys.argv[1], sys.argv[2], 'Test')
    print(r['abc'] if r else 'brak')
