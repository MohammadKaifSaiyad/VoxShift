"""Spike S4a: Chatterbox Multilingual TTS on the reference Mac, CPU vs MPS.

Throwaway Phase 0 spike code (see README.md). Run with the spike venv:

    scripts/spikes/mac_s4/.venv/bin/python scripts/spikes/mac_s4/run_s4a.py all

Rules this script keeps:
- Film dialogue text is read from the S3d review file at run time and is never
  printed, logged or saved (only indices and character counts). Audio goes to
  out/s4a/audio/ (git-ignored *.wav).
- Every model-loading process blocks `spacy_pkuseg` (see README: Chatterbox's
  tokenizer otherwise downloads a Chinese segmentation model from GitHub on
  every load) and installs a socket guard that records and refuses any network
  host that is not allowed for that step.
- Timed passes run with HF_HUB_OFFLINE=1 and no network host allowed.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
OUT = HERE / "out" / "s4a"
AUDIO = OUT / "audio"
LOGS = OUT / "logs"
VENV_PY = HERE / ".venv" / "bin" / "python"

MEDIA = REPO / "media" / "QJH3CCrjda4.m4a"
REVIEW = REPO / "scripts" / "spikes" / "kaggle_s3d" / "out" / "s3d" / "review_QJH3CCrjda4.md"
S3D_TTS = REPO / "scripts" / "spikes" / "kaggle_s3d" / "out" / "s3d" / "stage_tts.json"

# Reference voice: SPEAKER_01 of S3d, review lines 1-4 (starts 165.5, 168.2, 170.9, 176.1 s).
# One continuous stretch, cut at silences found with ffmpeg silencedetect (-30 dB, 0.25 s):
# speech starts ~165.4 s, and a silence begins at 177.23 s.
REF_START_S = 165.40
REF_END_S = 177.20
REF_SR = 24000
REF_PATH = AUDIO / "ref_SPEAKER_01.wav"

MAX_LINES = 20
GEN = {"language_id": "en", "cfg_weight": 0.5, "exaggeration": 0.5}
SEED_BASE = 1000

# Our own neutral sentences (not film dialogue), for the warm-up and the Turkish import check.
WARMUP_EN = "This is a short warm-up sentence before the timed run."
TURKISH = [
    "Bugün hava çok güzel, güneş parlıyor.",
    "Yarın öğleden sonra yağmur yağması bekleniyor.",
    "Akşamları rüzgâr serin esiyor, yanına bir ceket al.",
]

HF_REPO_DIR = Path.home() / ".cache" / "huggingface" / "hub" / "models--ResembleAI--chatterbox"
HF_HOSTS = re.compile(r"(^|\.)(huggingface\.co|hf\.co)$")


# --------------------------------------------------------------------------------------
# helpers usable from any python (stdlib only)
# --------------------------------------------------------------------------------------

def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str) + "\n")


def load_json(path: Path):
    return json.loads(path.read_text())


def du_bytes(path: Path, follow_links: bool = False) -> int:
    """Allocated size like `du -sk` (`-L` follows symlinks, e.g. HF snapshot -> shared blob store)."""
    if not path.exists():
        return 0
    cmd = ["du", "-skL" if follow_links else "-sk", str(path)]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout.split()
    return int(out[0]) * 1024 if out else 0


def english_lines() -> list[str]:
    """First MAX_LINES non-empty cells of the 'English (final)' column, in order. Never print them."""
    rows = [ln for ln in REVIEW.read_text().splitlines() if ln.startswith("|")]
    header = [c.strip() for c in rows[0].strip().strip("|").split("|")]
    col = header.index("English (final)")
    lines = []
    for ln in rows[2:]:
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) > col and cells[col]:
            lines.append(cells[col])
        if len(lines) == MAX_LINES:
            break
    return lines


def review_meta() -> list[dict]:
    """Index, speaker and start time per review row (no text)."""
    rows = [ln for ln in REVIEW.read_text().splitlines() if ln.startswith("|")]
    out = []
    for ln in rows[2:]:
        c = [x.strip() for x in ln.strip().strip("|").split("|")]
        out.append({"idx": int(c[0]), "speaker": c[1], "start_s": float(c[2])})
    return out


def power_state() -> dict:
    def sh(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout
        except Exception as e:  # noqa: BLE001
            return f"error: {e}"
    batt = sh(["pmset", "-g", "batt"])
    therm = sh(["pmset", "-g", "therm"])
    lowpower = re.search(r"lowpowermode\s+(\d)", sh(["pmset", "-g"]))
    top = sh(["top", "-l", "2", "-n", "6", "-o", "cpu", "-stats", "command,cpu", "-s", "1"])
    # keep only the second sample (the first one has no CPU deltas)
    blocks = top.split("Processes:")
    last = blocks[-1] if blocks else top
    load = re.search(r"Load Avg: ([0-9., ]+)", last)
    procs = []
    m = re.search(r"COMMAND\s+%CPU\n(.*)", last, re.S)
    if m:
        for row in m.group(1).strip().splitlines()[:6]:
            parts = row.rsplit(None, 1)
            if len(parts) == 2:
                procs.append({"command": parts[0].strip(), "cpu_pct": parts[1]})
    return {
        "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "power_source": "AC" if "AC Power" in batt else ("battery" if "Battery Power" in batt else batt.strip()),
        "battery": (re.search(r"(\d+)%;\s*([a-z ]+);", batt).group(0) if re.search(r"(\d+)%;\s*([a-z ]+);", batt) else None),
        "low_power_mode": lowpower.group(1) if lowpower else None,
        "thermal": " | ".join(x.strip() for x in therm.strip().splitlines()),
        "load_avg": load.group(1).strip() if load else None,
        "top_cpu": procs,
    }


# --------------------------------------------------------------------------------------
# in-venv helpers (ML imports only inside functions)
# --------------------------------------------------------------------------------------

def install_guards(allow_hf: bool) -> dict:
    """Block spacy_pkuseg; record and refuse network hosts not allowed for this step."""
    import socket

    sys.modules["spacy_pkuseg"] = None  # Chinese segmenter: would download a model from GitHub on load
    record = {"allowed": [], "blocked": []}
    real_gai = socket.getaddrinfo
    real_connect = socket.socket.connect

    def is_local(host) -> bool:
        return host in (None, "localhost", "127.0.0.1", "::1", "0.0.0.0", "") or str(host).startswith("/")

    def gai(host, *a, **k):
        if is_local(host) or (allow_hf and HF_HOSTS.search(str(host) or "")):
            if not is_local(host) and host not in record["allowed"]:
                record["allowed"].append(host)
            return real_gai(host, *a, **k)
        if host not in record["blocked"]:
            record["blocked"].append(host)
        raise socket.gaierror(f"S4a guard: network host {host!r} not allowed in this step")

    def connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if is_local(host) or allow_hf:
            return real_connect(self, address)
        if str(host) not in record["blocked"]:
            record["blocked"].append(str(host))
        raise OSError(f"S4a guard: connect to {host!r} not allowed in this step")

    socket.getaddrinfo = gai
    socket.socket.connect = connect
    return record


class WarnCounter:
    """Counts Chatterbox repetition / forced-EOS warnings and torch MPS fallback warnings."""

    def __init__(self):
        import logging
        import warnings

        self.forced_eos = 0
        self.repetition = 0
        self.other_log_warnings: dict[str, int] = {}
        self.fallback_ops: dict[str, int] = {}
        self.py_warnings: dict[str, int] = {}
        outer = self

        class H(logging.Handler):
            def emit(self, record):
                msg = record.getMessage()
                if "forcing EOS" in msg:
                    outer.forced_eos += 1
                elif "repetition of token" in msg:
                    outer.repetition += 1
                elif record.levelno >= logging.WARNING:
                    key = re.sub(r"\d+(\.\d+)?", "N", msg)[:160]
                    outer.other_log_warnings[key] = outer.other_log_warnings.get(key, 0) + 1

        logging.getLogger().addHandler(H())
        logging.getLogger().setLevel(logging.WARNING)
        orig_show = warnings.showwarning

        def show(message, category, filename, lineno, file=None, line=None):
            msg = str(message)
            m = re.search(r"operator '([^']+)' is not currently (?:supported|implemented)", msg)
            if m:
                outer.fallback_ops[m.group(1)] = outer.fallback_ops.get(m.group(1), 0) + 1
            else:
                key = f"{category.__name__}: {msg.splitlines()[0][:160]}"
                outer.py_warnings[key] = outer.py_warnings.get(key, 0) + 1
            orig_show(message, category, filename, lineno, file, line)

        warnings.showwarning = show
        warnings.simplefilter("default")  # first occurrence per location (torch fallback warnings fire once anyway)

    def snapshot(self):
        return {"forced_eos": self.forced_eos, "repetition": self.repetition}


class RssSampler:
    def __init__(self, interval=0.2):
        import threading
        import psutil

        self.proc = psutil.Process()
        self.peak = self.proc.memory_info().rss
        self._stop = False
        self.t = threading.Thread(target=self._run, args=(interval,), daemon=True)
        self.t.start()

    def _run(self, interval):
        while not self._stop:
            self.peak = max(self.peak, self.proc.memory_info().rss)
            time.sleep(interval)

    def now(self):
        r = self.proc.memory_info().rss
        self.peak = max(self.peak, r)
        return r

    def stop(self):
        self._stop = True


def sync(device: str):
    import torch

    if device == "mps":
        torch.mps.synchronize()


def mps_mem(device: str) -> dict | None:
    if device != "mps":
        return None
    import torch

    return {"current_allocated": torch.mps.current_allocated_memory(),
            "driver_allocated": torch.mps.driver_allocated_memory()}


def versions() -> dict:
    from importlib.metadata import version

    out = {"python": platform.python_version(), "macos": platform.mac_ver()[0], "machine": platform.machine()}
    for p in ("chatterbox-tts", "torch", "torchaudio", "transformers", "huggingface-hub", "numpy",
              "resemble-perth", "s3tokenizer", "librosa"):
        try:
            out[p] = version(p)
        except Exception:  # noqa: BLE001
            out[p] = None
    return out


def write_wav(path: Path, wav, sr: int) -> float:
    import soundfile as sf

    data = wav.squeeze(0).numpy()
    sf.write(str(path), data, sr, subtype="PCM_16")
    return len(data) / sr


def babble_flag(chars: int, audio_s: float) -> str | None:
    """Crude sanity bounds for English speech: ~5-30 chars/s plus slack for short lines."""
    if audio_s > chars / 5.0 + 1.5:
        return "too_long"
    if audio_s < chars / 30.0:
        return "too_short"
    return None


# --------------------------------------------------------------------------------------
# steps
# --------------------------------------------------------------------------------------

def step_ref(_args) -> None:
    AUDIO.mkdir(parents=True, exist_ok=True)
    dur = REF_END_S - REF_START_S
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-y", "-ss", f"{REF_START_S:.2f}", "-to", f"{REF_END_S:.2f}",
           "-i", str(MEDIA), "-af",
           f"pan=mono|c0=0.5*c0+0.5*c1,aresample={REF_SR},"
           f"afade=t=in:d=0.02,afade=t=out:st={dur - 0.02:.2f}:d=0.02",
           "-c:a", "pcm_f32le", str(REF_PATH)]
    subprocess.run(cmd, check=True, capture_output=True)
    stats = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(REF_PATH), "-af", "astats=measure_overall=RMS_level+Peak_level:measure_perchannel=none",
                            "-f", "null", "-"], capture_output=True, text=True).stderr
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=sample_rate,channels:format=duration",
                                       "-of", "json", str(REF_PATH)], capture_output=True, text=True).stdout)
    rms = re.search(r"RMS level dB: (-?[0-9.]+)", stats)
    peak = re.search(r"Peak level dB: (-?[0-9.]+)", stats)
    meta = [m for m in review_meta() if m["speaker"] == "SPEAKER_01" and REF_START_S - 0.5 <= m["start_s"] < REF_END_S]
    save_json(OUT / "ref.json", {
        "source": "media/QJH3CCrjda4.m4a (ISLIK, CC-BY, private evaluation)",
        "speaker": "SPEAKER_01 (S3d labels)",
        "start_s": REF_START_S, "end_s": REF_END_S, "seconds": round(dur, 2),
        "review_rows_covered": [m["idx"] for m in meta],
        "clips_joined": 1,
        "processing": "ffmpeg: stereo->mono average, resample to 24 kHz, 20 ms fades, float32 WAV; no gain, no separation",
        "sample_rate": int(probe["streams"][0]["sample_rate"]), "channels": probe["streams"][0]["channels"],
        "duration_s": round(float(probe["format"]["duration"]), 3),
        "rms_db": float(rms.group(1)) if rms else None, "peak_db": float(peak.group(1)) if peak else None,
        "boundary_method": "S3d review start times + ffmpeg silencedetect (-30 dB, d=0.25 s) on the original mix; "
                           "S3d per-segment end times (segments.json) were not downloaded from Kaggle",
    })
    print(f"ref: {dur:.2f} s -> {REF_PATH.relative_to(REPO)}")


def step_fetch(_args) -> None:
    """First (online) load: lets Chatterbox download its own weights; only HF hosts allowed."""
    rec = install_guards(allow_hf=True)
    t0 = time.perf_counter()
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    t_import = time.perf_counter() - t0
    t0 = time.perf_counter()
    model = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
    t_load = time.perf_counter() - t0
    del model
    snaps = sorted((HF_REPO_DIR / "snapshots").iterdir()) if (HF_REPO_DIR / "snapshots").exists() else []
    files = []
    for snap in snaps:
        for p in sorted(snap.rglob("*")):
            if p.is_file():
                files.append({"path": str(p.relative_to(snap)), "bytes": p.resolve().stat().st_size})
    refs_main = (HF_REPO_DIR / "refs" / "main")
    save_json(OUT / "fetch.json", {
        "import_s": round(t_import, 2),
        "from_pretrained_s_including_download": round(t_load, 2),
        "repo_dir": str(HF_REPO_DIR).replace(str(Path.home()), "~"),
        "revision": refs_main.read_text().strip() if refs_main.exists() else None,
        "snapshots": [s.name for s in snaps],
        "files": files,
        "network_hosts_allowed": rec["allowed"],
        "network_hosts_blocked": rec["blocked"],
        "spacy_pkuseg_blocked": True,
        "versions": versions(),
    })
    print(f"fetch: from_pretrained {t_load:.1f} s, {len(files)} files, blocked hosts: {rec['blocked']}")


def step_bench(args) -> None:
    device = args.device
    rec = install_guards(allow_hf=False)
    warn = WarnCounter()
    rss = RssSampler()
    import torch

    t0 = time.perf_counter()
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    t_import = time.perf_counter() - t0

    t0 = time.perf_counter()
    model = ChatterboxMultilingualTTS.from_pretrained(device=device)
    sync(device)
    t_load = time.perf_counter() - t0
    mem_after_load = {"rss": rss.now(), "mps": mps_mem(device)}

    t0 = time.perf_counter()
    model.prepare_conditionals(str(REF_PATH), exaggeration=GEN["exaggeration"])
    sync(device)
    t_cond = time.perf_counter() - t0

    # Stage timers (behaviour unchanged): T3 = text -> speech tokens (autoregressive loop),
    # S3Gen = tokens -> waveform, wm = Perth watermark (CPU, numpy).
    stage_t = {"t3_s": 0.0, "s3gen_s": 0.0, "wm_s": 0.0, "speech_tokens": 0}

    def timed(obj, attr, key, count_tokens=False):
        fn = getattr(obj, attr)

        def wrapper(*a, **k):
            sync(device)
            t = time.perf_counter()
            out = fn(*a, **k)
            sync(device)
            stage_t[key] += time.perf_counter() - t
            if count_tokens:
                stage_t["speech_tokens"] += int(k["speech_tokens"].numel())
            return out
        setattr(obj, attr, wrapper)

    timed(model.t3, "inference", "t3_s")
    timed(model.s3gen, "inference", "s3gen_s", count_tokens=True)
    timed(model.watermarker, "apply_watermark", "wm_s")

    def gen(text, lang, seed):
        torch.manual_seed(seed)
        before = warn.snapshot()
        for k in stage_t:
            stage_t[k] = 0
        wall0 = time.time()
        t = time.perf_counter()
        wav = model.generate(text, language_id=lang, cfg_weight=GEN["cfg_weight"], exaggeration=GEN["exaggeration"])
        sync(device)
        dt = time.perf_counter() - t
        wall = time.time() - wall0
        after = warn.snapshot()
        extra = {k: after[k] - before[k] for k in after}
        extra.update({k: (round(v, 3) if isinstance(v, float) else v) for k, v in stage_t.items()})
        # perf_counter (mach_absolute_time) stops while the Mac sleeps; wall clock does not.
        extra["sleep_gap_s"] = round(wall - dt, 2) if wall - dt > 1.0 else 0.0
        return wav, dt, extra

    wav, dt, w = gen(WARMUP_EN, "en", SEED_BASE - 1)
    warm = {"gen_s": round(dt, 2), "audio_s": round(write_wav(AUDIO / f"{device}_warmup.wav", wav, model.sr), 2), **w}

    lines = english_lines()
    per_line = []
    mps_peak = {"current_allocated": 0, "driver_allocated": 0}
    for i, text in enumerate(lines):
        wav, dt, w = gen(text, "en", SEED_BASE + i)
        audio_s = write_wav(AUDIO / f"{device}_en_{i:02d}.wav", wav, model.sr)
        m = mps_mem(device)
        if m:
            for k in mps_peak:
                mps_peak[k] = max(mps_peak[k], m[k])
        per_line.append({"i": i, "chars": len(text), "gen_s": round(dt, 3), "audio_s": round(audio_s, 3),
                         "rtf": round(dt / audio_s, 3) if audio_s else None,
                         "chars_per_audio_s": round(len(text) / audio_s, 1) if audio_s else None,
                         "flag": babble_flag(len(text), audio_s), **w, "rss_after": rss.now(), "mps": m})
        print(f"{device} line {i:02d}: chars={len(text)} gen={dt:.2f}s audio={audio_s:.2f}s eos={w['forced_eos']}", flush=True)
    tot_gen = sum(x["gen_s"] for x in per_line)
    tot_audio = sum(x["audio_s"] for x in per_line)
    mods_after_en = {m: (m in sys.modules and sys.modules[m] is not None) for m in ("pykakasi", "gradio", "spacy_pkuseg")}

    tr = []
    for k, text in enumerate(TURKISH):
        wav, dt, w = gen(text, "tr", 2000 + k)
        audio_s = write_wav(AUDIO / f"{device}_tr_{k}.wav", wav, model.sr)
        tr.append({"k": k, "chars": len(text), "gen_s": round(dt, 2), "audio_s": round(audio_s, 2), **w})
    mods_after_tr = {m: (m in sys.modules and sys.modules[m] is not None) for m in ("pykakasi", "gradio", "spacy_pkuseg")}
    loaded_like = sorted({m.split(".")[0] for m, v in sys.modules.items() if v is not None
                          and re.match(r"(pykakasi|gradio|jaconv|fastapi|uvicorn|starlette|spacy_pkuseg)", m)})
    rss.stop()

    save_json(OUT / f"bench_{device}.json", {
        "device": device,
        "env": {k: os.environ.get(k) for k in ("HF_HUB_OFFLINE", "PYTORCH_ENABLE_MPS_FALLBACK", "TQDM_DISABLE")},
        "torch_threads": torch.get_num_threads(),
        "import_s": round(t_import, 2), "load_s": round(t_load, 2), "cond_s": round(t_cond, 2),
        "warmup": warm,
        "lines": len(per_line), "total_gen_s": round(tot_gen, 2), "total_audio_s": round(tot_audio, 2),
        "rtf": round(tot_gen / tot_audio, 3), "x_realtime": round(tot_audio / tot_gen, 3),
        "stage_totals_s": {k: round(sum(x[k] for x in per_line), 2) for k in ("t3_s", "s3gen_s", "wm_s")},
        "speech_tokens_total": sum(x["speech_tokens"] for x in per_line),
        "t3_tokens_per_s": round(sum(x["speech_tokens"] for x in per_line) / max(1e-9, sum(x["t3_s"] for x in per_line)), 1),
        "lines_with_sleep_gap": [x["i"] for x in per_line if x["sleep_gap_s"]],
        "per_line": per_line,
        "forced_eos_lines": sum(1 for x in per_line if x["forced_eos"]),
        "repetition_warning_lines": sum(1 for x in per_line if x["repetition"]),
        "flagged_lines": [x["i"] for x in per_line if x["flag"]],
        "turkish": tr,
        "modules_after_english": mods_after_en, "modules_after_turkish": mods_after_tr,
        "related_top_level_modules_loaded": loaded_like,
        "peak_rss_sampled": rss.peak, "mem_after_load": mem_after_load, "mps_peak_after_lines": mps_peak if device == "mps" else None,
        "mps_fallback_ops": warn.fallback_ops, "python_warnings": warn.py_warnings,
        "other_log_warnings": warn.other_log_warnings,
        "network_hosts_blocked": rec["blocked"],
        "versions": versions(),
    })
    print(f"{device}: load {t_load:.1f}s cond {t_cond:.2f}s RTF {tot_gen / tot_audio:.3f} ({tot_gen:.1f}s / {tot_audio:.1f}s)")


def step_blocked(args) -> None:
    """Fresh process with pykakasi and gradio blocked before chatterbox is imported."""
    sys.modules["pykakasi"] = None
    sys.modules["gradio"] = None
    device = args.device
    rec = install_guards(allow_hf=False)
    warn = WarnCounter()
    result = {"device": device, "blocked_modules": ["pykakasi", "gradio", "spacy_pkuseg"]}
    for m in ("pykakasi", "gradio"):
        try:
            __import__(m)
            result[f"import_{m}"] = "imported (block failed)"
        except ImportError:
            result[f"import_{m}"] = "ImportError (blocked)"
    try:
        import torch
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS

        t0 = time.perf_counter()
        model = ChatterboxMultilingualTTS.from_pretrained(device=device)
        result["load_s"] = round(time.perf_counter() - t0, 2)
        model.prepare_conditionals(str(REF_PATH), exaggeration=GEN["exaggeration"])
        out = []
        for lang, text, seed, name in (("en", english_lines()[0], SEED_BASE, "en_00"), ("tr", TURKISH[0], 2000, "tr_0")):
            torch.manual_seed(seed)
            t = time.perf_counter()
            wav = model.generate(text, language_id=lang, cfg_weight=GEN["cfg_weight"], exaggeration=GEN["exaggeration"])
            dt = time.perf_counter() - t
            audio_s = write_wav(AUDIO / f"blocked_{device}_{name}.wav", wav, model.sr)
            out.append({"lang": lang, "chars": len(text), "gen_s": round(dt, 2), "audio_s": round(audio_s, 2),
                        "flag": babble_flag(len(text), audio_s) if lang == "en" else None})
        result["generations"] = out
        result["ok"] = True
    except Exception as e:  # noqa: BLE001
        result["ok"] = False
        result["error"] = f"{type(e).__name__}: {e}"[:400]
    for m in ("pykakasi", "gradio"):
        state = "absent" if m not in sys.modules else ("blocked (None)" if sys.modules[m] is None else "loaded")
        result[f"{m}_sys_modules_at_end"] = state
    result["log_warnings"] = warn.other_log_warnings
    result["network_hosts_blocked"] = rec["blocked"]
    save_json(OUT / f"blocked_{device}.json", result)
    print(f"blocked ({device}): ok={result['ok']}")


# --------------------------------------------------------------------------------------
# orchestration (fresh process per step, wrapped in /usr/bin/time -l)
# --------------------------------------------------------------------------------------

def run_step(name: str, argv: list[str], env_extra: dict, log_name: str) -> dict:
    LOGS.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.pop("HF_TOKEN", None)
    env.update({"TQDM_DISABLE": "1", "PYTHONUNBUFFERED": "1", **env_extra})
    log = LOGS / log_name
    cmd = ["/usr/bin/time", "-l", str(VENV_PY), str(Path(__file__).resolve()), *argv]
    t0 = time.perf_counter()
    with log.open("w") as f:
        f.write(f"$ {' '.join(cmd[2:])}\n# env: {json.dumps(env_extra)}\n")
        f.flush()
        rc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, env=env, cwd=REPO).returncode
    wall = time.perf_counter() - t0
    text = log.read_text()
    maxrss = re.search(r"(\d+)\s+maximum resident set size", text)
    footprint = re.search(r"(\d+)\s+peak memory footprint", text)
    res = {"step": name, "rc": rc, "wall_s": round(wall, 1),
           "max_rss_bytes": int(maxrss.group(1)) if maxrss else None,
           "peak_footprint_bytes": int(footprint.group(1)) if footprint else None}
    print(json.dumps(res))
    return res


def step_importtime(_args) -> dict:
    log = LOGS / "importtime.log"
    env = os.environ.copy()
    env.update({"HF_HUB_OFFLINE": "1"})
    with log.open("w") as f:
        subprocess.run([str(VENV_PY), "-X", "importtime", "-c", "from chatterbox.mtl_tts import ChatterboxMultilingualTTS"],
                       stdout=f, stderr=subprocess.STDOUT, env=env, cwd=REPO)
    found = {}
    for mod in ("pykakasi", "gradio", "spacy_pkuseg", "jaconv"):
        hits = [ln for ln in log.read_text().splitlines() if re.search(rf"\|\s*{mod}(\.|$|\s)", ln)]
        found[mod] = len(hits)
    total = re.findall(r"\|\s+(\d+)\s+\|\s+chatterbox\.mtl_tts\s*$", log.read_text(), re.M)
    res = {"modules_imported_count": found, "chatterbox.mtl_tts_cumulative_us": int(total[-1]) if total else None}
    print("importtime:", json.dumps(res))
    return res


def chatterbox_source_refs() -> list[dict]:
    site = next((HERE / ".venv" / "lib").glob("python*/site-packages"))
    refs = []
    for p in sorted((site / "chatterbox").rglob("*.py")):
        for n, ln in enumerate(p.read_text().splitlines(), 1):
            if re.search(r"pykakasi|gradio|spacy_pkuseg|pkuseg\(|hf_hub_download\(|snapshot_download\(", ln):
                refs.append({"file": str(p.relative_to(site)), "line": n, "code": ln.strip()[:120]})
    return refs


def check_logs_for_text() -> dict:
    """Make sure no dialogue line leaked into logs or JSON outputs (reports counts only)."""
    lines = english_lines()
    leaks = 0
    scanned = 0
    for p in list(LOGS.glob("*.log")) + list(OUT.glob("*.json")):
        t = p.read_text(errors="ignore")
        scanned += 1
        leaks += sum(1 for ln in lines if len(ln) >= 8 and ln in t)
    return {"files_scanned": scanned, "dialogue_lines_found": leaks}


def step_all(args) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    AUDIO.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    steps = {}
    if not REF_PATH.exists():
        step_ref(args)
    steps["importtime"] = step_importtime(args)
    if not (HF_REPO_DIR / "snapshots").exists():
        free = shutil.disk_usage(Path.home()).free
        if free < 25 * 1024**3:
            sys.exit(f"stop: only {free / 1024**3:.1f} GB free (< 25 GB)")
        steps["fetch"] = run_step("fetch", ["fetch"], {}, "fetch.log")
    offline = {"HF_HUB_OFFLINE": "1"}
    for dev in args.devices:
        env = dict(offline)
        if dev == "mps":
            env["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
        steps[f"power_before_{dev}"] = power_state()
        steps[f"bench_{dev}"] = run_step(f"bench_{dev}", ["bench", "--device", dev], env, f"bench_{dev}.log")
        steps[f"power_after_{dev}"] = power_state()
    rtfs = {d: load_json(OUT / f"bench_{d}.json")["rtf"] for d in args.devices if (OUT / f"bench_{d}.json").exists()}
    blocked_dev = args.blocked_device or (min(rtfs, key=rtfs.get) if rtfs else "cpu")
    env = dict(offline)
    if blocked_dev == "mps":
        env["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
    steps[f"blocked_{blocked_dev}"] = run_step(f"blocked_{blocked_dev}", ["blocked", "--device", blocked_dev], env,
                                               f"blocked_{blocked_dev}.log")
    save_json(OUT / "steps.json", steps)
    step_collect(args)


def step_collect(_args) -> None:
    steps = load_json(OUT / "steps.json") if (OUT / "steps.json").exists() else {}
    res = {"spike": "S4a", "date": "2026-10-07", "machine": "Apple M1 Pro, 16 GB, macOS (see versions)",
           "settings": {**GEN, "seed": "1000 + line index", "warmup": "1 generation, excluded",
                        "conditioning": "prepare_conditionals once from the reference"}}
    for name in ("install", "ref", "fetch"):
        if (OUT / f"{name}.json").exists():
            res[name] = load_json(OUT / f"{name}.json")
    res["english_lines"] = {"source": "review_QJH3CCrjda4.md, 'English (final)' column, first non-empty rows",
                            "requested": MAX_LINES, "available": len(english_lines()),
                            "chars": [len(x) for x in english_lines()]}
    res["steps"] = steps
    for dev in ("cpu", "mps"):
        p = OUT / f"bench_{dev}.json"
        if p.exists():
            res[f"bench_{dev}"] = load_json(p)
    for p in sorted(OUT.glob("blocked_*.json")):
        res[p.stem] = load_json(p)
    run1 = OUT / "run1"
    if run1.exists():
        r1 = {"note": "first run; the Mac idle-slept 20:33:30-20:38:02 and clamshell-slept 20:38:34-20:40:34 "
                      "during the MPS pass (MPS English lines 6-15 and all Turkish lines affected); CPU pass unaffected"}
        for dev in ("cpu", "mps"):
            p = run1 / f"bench_{dev}.json"
            if p.exists():
                b = load_json(p)
                r1[dev] = {k: b.get(k) for k in ("load_s", "cond_s", "rtf", "total_gen_s", "total_audio_s",
                                                  "forced_eos_lines", "peak_rss_sampled", "mps_peak_after_lines")}
                r1[dev]["per_line_gen_s"] = [x["gen_s"] for x in b["per_line"]]
                r1[dev]["per_line_audio_s"] = [x["audio_s"] for x in b["per_line"]]
        if (run1 / "steps.json").exists():
            r1["steps"] = {k: v for k, v in load_json(run1 / "steps.json").items() if k.startswith(("bench", "blocked"))}
        res["run1"] = r1
    res["chatterbox_source_refs"] = chatterbox_source_refs()
    site = next((HERE / ".venv" / "lib").glob("python*/site-packages"))
    pk = sorted(((du_bytes(d), d.name) for d in site.iterdir() if d.is_dir() and not d.name.endswith(".dist-info")
                 and d.name != "__pycache__"), reverse=True)[:10]
    res["disk"] = {
        "venv_bytes": du_bytes(HERE / ".venv"),
        "largest_packages": [{"name": n, "bytes": b} for b, n in pk],
        "hf_repo_bytes_following_links": du_bytes(HF_REPO_DIR, follow_links=True),
        "hf_repo_dir_bytes_links_only": du_bytes(HF_REPO_DIR),
        "hf_hub_shared_blobs_bytes": du_bytes(HF_REPO_DIR.parent / "blobs"),
        "hf_hub_bytes_before_spike": 89488 * 1024,
        "hf_xet_dir_bytes": du_bytes(Path.home() / ".cache" / "huggingface" / "xet"),
        "uv_cache_bytes": du_bytes(Path.home() / ".cache" / "uv"),
        "pkuseg_home_exists": (Path.home() / ".pkuseg").exists(),
        "free_bytes_home": shutil.disk_usage(Path.home()).free,
    }
    if S3D_TTS.exists():
        s3d = load_json(S3D_TTS)
        res["s3d_t4_reference"] = {k: s3d.get(k) for k in ("versions", "QJH3CCrjda4", "aLvkEaaDte8", "cQ8J2vdB9VU",
                                                             "peak_rss_mb", "torch_peak_gpu_mb")}
    rtfs = {d: res[f"bench_{d}"]["rtf"] for d in ("cpu", "mps") if f"bench_{d}" in res}
    if rtfs:
        best = min(rtfs, key=rtfs.get)
        speech_min, factor = 55.0, 1.3
        res["projection_90min_estimate"] = {
            "assumption": "55 min English speech x 1.3 (audition, drift-gate regenerations, rewrites)",
            "best_device": best, "rtf": rtfs[best],
            "tts_minutes": round(speech_min * factor * rtfs[best], 1),
            "per_device_tts_minutes": {d: round(speech_min * factor * r, 1) for d, r in rtfs.items()},
            "pipeline_budget_minutes_3x": 270,
        }
    res["log_text_check"] = check_logs_for_text()
    save_json(OUT / "results.json", res)
    print("results:", OUT / "results.json")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ref")
    sub.add_parser("fetch")
    sub.add_parser("importtime")
    b = sub.add_parser("bench")
    b.add_argument("--device", choices=["cpu", "mps"], required=True)
    bl = sub.add_parser("blocked")
    bl.add_argument("--device", choices=["cpu", "mps"], required=True)
    a = sub.add_parser("all")
    a.add_argument("--devices", nargs="+", default=["cpu", "mps"])
    a.add_argument("--blocked-device", choices=["cpu", "mps"], default=None)
    sub.add_parser("collect")
    args = ap.parse_args()
    {"ref": step_ref, "fetch": step_fetch, "importtime": step_importtime, "bench": step_bench,
     "blocked": step_blocked, "all": step_all, "collect": step_collect}[args.cmd](args)


if __name__ == "__main__":
    main()
