"""Loudness measurement and peak limiting shared by make_sfx.py and make_music.py.

Loudness follows ITU-R BS.1770 closely enough for a bed under a video:
K-weighting applied in the frequency domain, 400 ms blocks, absolute and
relative gating. Peaks are held under a ceiling with a look-ahead limiter, so
nothing the scripts write can clip or jump out of the mix.
"""

import numpy as np

SR = 48_000
BLOCK = int(0.4 * SR)
HOP = int(0.1 * SR)


def k_weight(x):
    """High-pass near 38 Hz plus a +4 dB shelf above ~2 kHz (BS.1770 stage 1 and 2)."""
    spectrum = np.fft.rfft(x, axis=0)
    f = np.maximum(np.fft.rfftfreq(x.shape[0], 1 / SR), 1)
    highpass = 1 / np.sqrt(1 + (38 / f) ** 4)
    shelf = 1 + (10 ** (4 / 20) - 1) / (1 + (2000 / f) ** 4)
    return np.fft.irfft(spectrum * (highpass * shelf)[:, None], x.shape[0], axis=0)


def _block_power(x):
    w = k_weight(x if x.ndim == 2 else x[:, None])
    p = (w**2).sum(axis=1)
    if len(p) < BLOCK:
        return np.array([p.mean()])
    c = np.concatenate([[0], np.cumsum(p)])
    starts = np.arange(0, len(p) - BLOCK + 1, HOP)
    return (c[starts + BLOCK] - c[starts]) / BLOCK


def lufs(power):
    return -0.691 + 10 * np.log10(np.maximum(power, 1e-12))


def integrated(x):
    """Gated integrated loudness in LUFS."""
    p = _block_power(x)
    p = p[lufs(p) > -70]
    if not len(p):
        return -70.0
    p = p[lufs(p) > lufs(p.mean()) - 10]
    return float(lufs(p.mean()))


def momentary(x):
    """Momentary (400 ms) loudness every 100 ms, in LUFS."""
    return lufs(_block_power(x))


def short_term(x):
    """Short-term (3 s) loudness every 100 ms, in LUFS."""
    p = _block_power(x)
    if len(p) < 30:
        return lufs(np.array([p.mean()]))
    c = np.concatenate([[0], np.cumsum(p)])
    return lufs((c[30:] - c[:-30]) / 30)


def peak_db(x):
    return float(20 * np.log10(np.max(np.abs(x)) + 1e-12))


def limit(x, ceiling_db=-1.5, lookahead=0.005, release=0.15):
    """Look-ahead peak limiter: no sample ends up above ``ceiling_db``.

    Gain is computed per 5 ms block as the minimum needed by the block and its
    neighbours, recovers over ``release`` seconds, and is interpolated per
    sample. Every interpolated gain is at or below what each block needs, so
    the ceiling holds exactly while the gain changes smoothly.
    """
    x = x if x.ndim == 2 else x[:, None]
    ceiling = 10 ** (ceiling_db / 20)
    size = int(lookahead * SR)
    n_blocks = -(-len(x) // size)
    pad = np.zeros((n_blocks * size - len(x), x.shape[1]))
    peaks = np.abs(np.vstack([x, pad])).max(axis=1).reshape(n_blocks, size).max(axis=1)
    need = np.minimum(1, ceiling / np.maximum(peaks, 1e-12))
    need = np.minimum(need, np.minimum(np.roll(need, 1), np.roll(need, -1)))
    step = 1 - np.exp(-lookahead / release)
    gain = np.empty_like(need)
    g = 1.0
    for i, v in enumerate(need):
        g = v if v < g else g + (min(v, 1) - g) * step
        gain[i] = g
    centers = (np.arange(n_blocks) + 0.5) * size
    per_sample = np.interp(np.arange(len(x)), centers, gain)
    out = x * per_sample[:, None]
    return np.clip(out, -ceiling, ceiling)  # guard edges where interp extrapolates


def master(x, target_lufs, ceiling_db=-1.5):
    """Remove DC, set integrated loudness, then hold peaks under the ceiling."""
    x = x - x.mean(axis=0)
    x = x * 10 ** ((target_lufs - integrated(x)) / 20)
    return limit(x, ceiling_db)


def report(x):
    """Integrated loudness, loudest 400 ms, peak, and the largest 3 s rise.

    A rise is short-term loudness against the 3 s before it; a big one is what
    a viewer hears as the music suddenly getting loud.
    """
    st = short_term(x)
    rise = float(np.max(st[30:] - st[:-30])) if len(st) > 30 else 0.0
    return {
        "integrated_lufs": round(integrated(x), 1),
        "max_momentary_lufs": round(float(momentary(x).max()), 1),
        "peak_dbfs": round(peak_db(x), 1),
        "max_rise_lu": round(rise, 1),
    }
