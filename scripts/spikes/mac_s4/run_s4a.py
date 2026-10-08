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

Run 2 (clean rerun, D-87) uses the `device` step once per device, then `collect`, all with
`--run-dir run2`: built-in voice (`--voice default`, no film audio, D-84), pykakasi/gradio blocked
(`--block-optional`), MPS cache freed after every line (`--empty-cache`), caffeinate, and power/load/
sleep checks. Without these options the script behaves as in run 1.
"""

from __future__ import annotations

import argparse
import datetime as dt_mod
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
# Where a run writes bench/steps/results JSON and generated audio. Run 1 used OUT/AUDIO directly
# (moved to out/s4a/run1/ by hand afterwards); --run-dir NAME redirects to out/s4a/NAME/.
RUN = OUT
AUDIO_OUT = AUDIO
VENV_PY = HERE / ".venv" / "bin" / "python"
OPTIONAL_BLOCKED = ("pykakasi", "gradio")  # D-77/D-88: not installed in the target TTS environment

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

def configure_run(run_dir: str | None) -> None:
    """--run-dir NAME: JSON, logs and audio go under out/s4a/NAME/ (run 1's files are never touched)."""
    global RUN, AUDIO_OUT, LOGS
    if run_dir:
        if run_dir == "run1":
            sys.exit("stop: run1 is the archived first run; pick another --run-dir")
        RUN = OUT / run_dir
        AUDIO_OUT = RUN / "audio"
        LOGS = RUN / "logs"


def sh(cmd, timeout=60) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception as e:  # noqa: BLE001
        return f"error: {e}"


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


def load_1min() -> float | None:
    vals = sh(["sysctl", "-n", "vm.loadavg"]).strip(" {}\n").split()
    try:
        return float(vals[0])
    except (IndexError, ValueError):
        return None


def conditions() -> dict:
    """power_state() plus sysctl load averages, lid state and free-memory percentage (run 2)."""
    st = power_state()
    vals = sh(["sysctl", "-n", "vm.loadavg"]).strip(" {}\n").split()
    st["sysctl_loadavg"] = [float(v) for v in vals[:3]] if len(vals) >= 3 else None
    clam = re.search(r'"AppleClamshellState" = (Yes|No)', sh(["ioreg", "-r", "-k", "AppleClamshellState", "-d", "4"]))
    st["lid"] = {"No": "open", "Yes": "closed"}.get(clam.group(1)) if clam else None
    free = re.search(r"free percentage: (\d+)%", sh(["memory_pressure"]))
    st["memory_free_pct"] = int(free.group(1)) if free else None
    return st


def pmset_sleep_wake(start: dt_mod.datetime, end: dt_mod.datetime) -> dict:
    """Sleep/Wake/DarkWake events from `pmset -g log` between start and end (local time)."""
    events, assertion_lines = [], 0
    # type column is padded and ends at a tab ("Wake Requests" is scheduling bookkeeping, not a wake)
    pat = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) [+-]\d{4} ([^\t]+?)\s*\t")
    for ln in sh(["pmset", "-g", "log"], timeout=180).splitlines():
        if not re.search(r"Sleep|Wake", ln):
            continue
        m = pat.match(ln)
        if not m:
            continue
        t = dt_mod.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
        if not (start <= t <= end):
            continue
        if m.group(2) in ("Sleep", "Wake", "DarkWake"):
            events.append(ln[:100].rstrip())
        elif "caffeinate" in ln:
            assertion_lines += 1
    return {"window": [start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")],
            "events": events, "sleep_events": sum(1 for e in events if pat.match(e).group(2) == "Sleep"),
            "caffeinate_assertion_log_lines": assertion_lines}


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


def block_optional() -> None:
    """Make `import pykakasi` / `import gradio` raise ImportError (must run before chatterbox is imported)."""
    for m in OPTIONAL_BLOCKED:
        sys.modules[m] = None


def free_memory(device: str) -> dict:
    """Run 2 per-line cleanup. MPS: synchronize, gc.collect, empty_cache. CPU: gc.collect."""
    import gc

    import torch

    t = time.perf_counter()
    before = mps_mem(device)
    if device == "mps":
        torch.mps.synchronize()
    gc.collect()
    if device == "mps":
        torch.mps.empty_cache()
    return {"cleanup_s": round(time.perf_counter() - t, 3), "mps_before_cleanup": before,
            "mps_after_cleanup": mps_mem(device)}


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
    voice = getattr(args, "voice", "ref")
    empty_cache = getattr(args, "empty_cache", False)
    if getattr(args, "block_optional", False):
        block_optional()
    rec = install_guards(allow_hf=False)
    warn = WarnCounter()
    rss = RssSampler()
    import torch

    AUDIO_OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    t_import = time.perf_counter() - t0

    t0 = time.perf_counter()
    model = ChatterboxMultilingualTTS.from_pretrained(device=device)
    sync(device)
    t_load = time.perf_counter() - t0
    mem_after_load = {"rss": rss.now(), "mps": mps_mem(device)}

    if voice == "default":
        # D-84: no cloning. Use the built-in voice that from_pretrained loads from the repo's conds.pt.
        if model.conds is None:
            save_json(RUN / f"bench_{device}_error.json", {"device": device, "error": "model.conds is None: no built-in voice"})
            sys.exit("stop: model.conds is None (no built-in voice); prepare_conditionals is not allowed in this run")
        rev = (HF_REPO_DIR / "refs" / "main").read_text().strip()
        conds_file = HF_REPO_DIR / "snapshots" / rev / "conds.pt"
        c = model.conds.t3
        voice_info = {
            "voice": "built-in default (model.conds from conds.pt; prepare_conditionals not called)",
            "conds_blob": conds_file.resolve().name if conds_file.exists() else None,
            "conds_bytes": conds_file.resolve().stat().st_size if conds_file.exists() else None,
            "builtin_emotion_adv": float(c.emotion_adv.flatten()[0]) if c.emotion_adv is not None else None,
            "speaker_emb_shape": list(c.speaker_emb.shape) if c.speaker_emb is not None else None,
            "cond_prompt_speech_tokens": int(c.cond_prompt_speech_tokens.numel()) if c.cond_prompt_speech_tokens is not None else None,
        }
        t_cond = None
    else:
        voice_info = {"voice": "cloned from reference", "ref": str(REF_PATH.relative_to(REPO))}
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

    def cleanup() -> dict:
        return free_memory(device) if empty_cache else {}

    wav, dt, w = gen(WARMUP_EN, "en", SEED_BASE - 1)
    warm = {"gen_s": round(dt, 2), "audio_s": round(write_wav(AUDIO_OUT / f"{device}_warmup.wav", wav, model.sr), 2), **w}
    warm.update(cleanup())

    lines = english_lines()
    per_line = []
    mps_peak = {"current_allocated": 0, "driver_allocated": 0}
    mps_peak_after_cleanup = {"current_allocated": 0, "driver_allocated": 0}
    for i, text in enumerate(lines):
        wav, dt, w = gen(text, "en", SEED_BASE + i)
        audio_s = write_wav(AUDIO_OUT / f"{device}_en_{i:02d}.wav", wav, model.sr)
        m = mps_mem(device)  # after generation, before any cleanup (as in run 1)
        if m:
            for k in mps_peak:
                mps_peak[k] = max(mps_peak[k], m[k])
        cl = cleanup()
        if cl.get("mps_after_cleanup"):
            for k in mps_peak_after_cleanup:
                mps_peak_after_cleanup[k] = max(mps_peak_after_cleanup[k], cl["mps_after_cleanup"][k])
        cl.pop("mps_before_cleanup", None)  # same moment as "mps"
        per_line.append({"i": i, "chars": len(text), "gen_s": round(dt, 3), "audio_s": round(audio_s, 3),
                         "rtf": round(dt / audio_s, 3) if audio_s else None,
                         "chars_per_audio_s": round(len(text) / audio_s, 1) if audio_s else None,
                         "flag": babble_flag(len(text), audio_s), **w, "rss_after": rss.now(), "mps": m, **cl})
        drv = f" drv={m['driver_allocated'] / 1e9:.2f}GB" if m else ""
        drv += f"->{cl['mps_after_cleanup']['driver_allocated'] / 1e9:.2f}GB" if cl.get("mps_after_cleanup") else ""
        print(f"{device} line {i:02d}: chars={len(text)} gen={dt:.2f}s audio={audio_s:.2f}s eos={w['forced_eos']}{drv}", flush=True)
    tot_gen = sum(x["gen_s"] for x in per_line)
    tot_audio = sum(x["audio_s"] for x in per_line)
    mods_after_en = {m: (m in sys.modules and sys.modules[m] is not None) for m in ("pykakasi", "gradio", "spacy_pkuseg")}

    tr = []
    for k, text in enumerate(TURKISH):
        wav, dt, w = gen(text, "tr", 2000 + k)
        audio_s = write_wav(AUDIO_OUT / f"{device}_tr_{k}.wav", wav, model.sr)
        m = mps_mem(device)
        tr.append({"k": k, "chars": len(text), "gen_s": round(dt, 2), "audio_s": round(audio_s, 2), **w,
                   "mps": m, **{a: b for a, b in cleanup().items() if a != "mps_before_cleanup"}})
        print(f"{device} tr {k}: chars={len(text)} gen={dt:.2f}s audio={audio_s:.2f}s", flush=True)
    mods_after_tr = {m: (m in sys.modules and sys.modules[m] is not None) for m in ("pykakasi", "gradio", "spacy_pkuseg")}
    loaded_like = sorted({m.split(".")[0] for m, v in sys.modules.items() if v is not None
                          and re.match(r"(pykakasi|gradio|jaconv|fastapi|uvicorn|starlette|spacy_pkuseg)", m)})
    rss.stop()

    save_json(RUN / f"bench_{device}.json", {
        "device": device,
        "voice": voice_info,
        "empty_cache_per_line": empty_cache,
        "blocked_modules": [m for m in (*OPTIONAL_BLOCKED, "spacy_pkuseg") if m in sys.modules and sys.modules[m] is None],
        "env": {k: os.environ.get(k) for k in ("HF_HUB_OFFLINE", "PYTORCH_ENABLE_MPS_FALLBACK", "TQDM_DISABLE")},
        "torch_threads": torch.get_num_threads(),
        "import_s": round(t_import, 2), "load_s": round(t_load, 2),
        "cond_s": round(t_cond, 2) if t_cond is not None else None,
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
        "mps_peak_after_cleanup": mps_peak_after_cleanup if device == "mps" and empty_cache else None,
        "cleanup_total_s": round(sum(x.get("cleanup_s", 0) for x in per_line), 2) if empty_cache else None,
        "mps_fallback_ops": warn.fallback_ops, "python_warnings": warn.py_warnings,
        "other_log_warnings": warn.other_log_warnings,
        "network_hosts_blocked": rec["blocked"],
        "versions": versions(),
    })
    cond = f"cond {t_cond:.2f}s" if t_cond is not None else "built-in voice"
    print(f"{device}: load {t_load:.1f}s {cond} RTF {tot_gen / tot_audio:.3f} ({tot_gen:.1f}s / {tot_audio:.1f}s)")


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
            audio_s = write_wav(AUDIO_OUT / f"blocked_{device}_{name}.wav", wav, model.sr)
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
    save_json(RUN / f"blocked_{device}.json", result)
    print(f"blocked ({device}): ok={result['ok']}")


# --------------------------------------------------------------------------------------
# orchestration (fresh process per step, wrapped in /usr/bin/time -l)
# --------------------------------------------------------------------------------------

CAFFEINATE = ["caffeinate", "-dimsu"]


def run_step(name: str, argv: list[str], env_extra: dict, log_name: str, caffeinate: bool = False) -> dict:
    LOGS.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.pop("HF_TOKEN", None)
    env.update({"TQDM_DISABLE": "1", "PYTHONUNBUFFERED": "1", **env_extra})
    log = LOGS / log_name
    prefix = CAFFEINATE if caffeinate else []
    cmd = [*prefix, "/usr/bin/time", "-l", str(VENV_PY), str(Path(__file__).resolve()), *argv]
    t0 = time.perf_counter()
    wall0 = time.time()
    assertions = None
    with log.open("w") as f:
        f.write(f"$ {' '.join(prefix + cmd[len(prefix) + 2:])}\n# env: {json.dumps(env_extra)}\n")
        f.flush()
        p = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, env=env, cwd=REPO)
        if caffeinate:
            try:
                p.wait(timeout=20)
            except subprocess.TimeoutExpired:
                # proof that caffeinate holds its assertions while the step runs
                # caffeinate forks: the asserting child's "Details" line names our pid ("on behalf of ... (pid N)")
                rows = sh(["pmset", "-g", "assertions"]).splitlines()
                types = {m.group(1) for ln, nxt in zip(rows, rows[1:] + [""])
                         if "(caffeinate)" in ln and f"(pid {p.pid})" in nxt
                         and (m := re.search(r"\]\s+\S+\s+(\w+)\s+named:", ln))}
                assertions = {"checked_after_s": 20, "types": sorted(types)}
        rc = p.wait()
    wall = time.perf_counter() - t0
    text = log.read_text()
    maxrss = re.search(r"(\d+)\s+maximum resident set size", text)
    footprint = re.search(r"(\d+)\s+peak memory footprint", text)
    res = {"step": name, "rc": rc, "wall_s": round(wall, 1),
           "max_rss_bytes": int(maxrss.group(1)) if maxrss else None,
           "peak_footprint_bytes": int(footprint.group(1)) if footprint else None}
    if caffeinate:
        res["caffeinate"] = " ".join(CAFFEINATE)
        res["caffeinate_assertions"] = assertions
        # perf_counter stops during sleep; wall clock does not
        res["wall_clock_minus_monotonic_s"] = round((time.time() - wall0) - wall, 1)
    print(json.dumps(res), flush=True)
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
    for p in list(LOGS.glob("*.log")) + list(RUN.glob("*.json")):
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
    rtfs = {d: load_json(RUN / f"bench_{d}.json")["rtf"] for d in args.devices if (RUN / f"bench_{d}.json").exists()}
    blocked_dev = args.blocked_device or (min(rtfs, key=rtfs.get) if rtfs else "cpu")
    env = dict(offline)
    if blocked_dev == "mps":
        env["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
    steps[f"blocked_{blocked_dev}"] = run_step(f"blocked_{blocked_dev}", ["blocked", "--device", blocked_dev], env,
                                               f"blocked_{blocked_dev}.log")
    save_json(RUN / "steps.json", steps)
    step_collect(args)


def step_device(args) -> None:
    """Run 2: one clean device run. AC power required; waits for 1-min load < max; caffeinate; pmset log."""
    dev = args.device
    RUN.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    steps = load_json(RUN / "steps.json") if (RUN / "steps.json").exists() else {}
    before = conditions()
    print(f"before {dev}: power={before['power_source']} load={before['sysctl_loadavg']} lid={before['lid']}", flush=True)
    if before["power_source"] != "AC":
        steps[f"power_before_{dev}"] = before
        save_json(RUN / "steps.json", steps)
        sys.exit(f"stop: not on AC power ({before['power_source']})")
    checks = [{"t": before["time"], "load_1m": before["sysctl_loadavg"][0] if before["sysctl_loadavg"] else None}]
    t_wait = time.time()
    while (checks[-1]["load_1m"] or 0) >= args.max_load and time.time() - t_wait < args.max_wait_s:
        time.sleep(20)
        checks.append({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "load_1m": load_1min()})
        print(f"load wait: {checks[-1]}", flush=True)
    if len(checks) > 1:
        before = conditions()  # re-record right before the run
    steps[f"load_wait_{dev}"] = {"max_load_1m": args.max_load, "max_wait_s": args.max_wait_s,
                                 "waited_s": round(time.time() - t_wait), "checks": checks,
                                 "proceeded_above_max": (checks[-1]["load_1m"] or 0) >= args.max_load}
    steps[f"power_before_{dev}"] = before
    save_json(RUN / "steps.json", steps)

    env = {"HF_HUB_OFFLINE": "1"}
    if dev == "mps":
        env["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
    argv = ["bench", "--device", dev, "--run-dir", args.run_dir, "--voice", args.voice, "--block-optional"]
    if not args.no_empty_cache:
        argv.append("--empty-cache")
    start = dt_mod.datetime.now().replace(microsecond=0)
    steps[f"bench_{dev}"] = run_step(f"bench_{dev}", argv, env, f"bench_{dev}.log", caffeinate=True)
    end = dt_mod.datetime.now().replace(microsecond=0)
    steps[f"power_after_{dev}"] = conditions()
    sw = pmset_sleep_wake(start, end)
    (LOGS / f"pmset_sleep_wake_{dev}.log").write_text("\n".join(sw["events"]) + ("\n" if sw["events"] else ""))
    steps[f"sleep_wake_{dev}"] = sw
    save_json(RUN / "steps.json", steps)
    print(f"after {dev}: rc={steps[f'bench_{dev}']['rc']} sleep_events={sw['sleep_events']} "
          f"load={steps[f'power_after_{dev}']['sysctl_loadavg']}", flush=True)


def _median(xs: list[float]) -> float | None:
    s = sorted(xs)
    n = len(s)
    return None if not n else round(s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2, 3)


def device_summary(b: dict, st: dict) -> dict:
    rtfs = [x["rtf"] for x in b["per_line"]]
    tr_gen = sum(x["gen_s"] for x in b["turkish"])
    tr_audio = sum(x["audio_s"] for x in b["turkish"])
    drv = [x["mps"]["driver_allocated"] for x in b["per_line"] if x.get("mps")]
    drv_clean = [x["mps_after_cleanup"]["driver_allocated"] for x in b["per_line"] if x.get("mps_after_cleanup")]
    tr_drv = [x["mps"]["driver_allocated"] for x in b["turkish"] if x.get("mps")]
    load_mps = (b.get("mem_after_load") or {}).get("mps")
    slowest = max(b["per_line"], key=lambda x: x["gen_s"])
    rest = [x for x in b["per_line"] if x is not slowest]
    return {
        "rtf_without_slowest_line": {"i": slowest["i"], "rtf": round(sum(x["gen_s"] for x in rest) /
                                                                     sum(x["audio_s"] for x in rest), 3)},
        "import_s": b["import_s"], "load_s": b["load_s"], "cond_s": b.get("cond_s"),
        "warmup_gen_s": b["warmup"]["gen_s"], "warmup_audio_s": b["warmup"]["audio_s"],
        "lines": b["lines"], "total_gen_s": b["total_gen_s"], "total_audio_s": b["total_audio_s"],
        "rtf": b["rtf"], "x_realtime": b["x_realtime"],
        "per_line_rtf_min": min(rtfs), "per_line_rtf_max": max(rtfs), "per_line_rtf_median": _median(rtfs),
        "stage_totals_s": b.get("stage_totals_s"), "t3_tokens_per_s": b.get("t3_tokens_per_s"),
        "forced_eos_lines": b["forced_eos_lines"], "repetition_warning_lines": b["repetition_warning_lines"],
        "flagged_lines": b["flagged_lines"], "lines_with_sleep_gap": b.get("lines_with_sleep_gap"),
        "cleanup_total_s": b.get("cleanup_total_s"),
        "peak_rss_bytes_time_l": st.get("max_rss_bytes"), "peak_footprint_bytes_time_l": st.get("peak_footprint_bytes"),
        "peak_rss_sampled_bytes": b["peak_rss_sampled"], "step_wall_s": st.get("wall_s"),
        "mps_driver_after_load": load_mps["driver_allocated"] if load_mps else None,
        "mps_driver_per_line_after_gen": drv or None,
        "mps_driver_per_line_after_cleanup": drv_clean or None,
        "mps_driver_peak_after_gen": max(drv) if drv else None,
        "mps_driver_peak_after_cleanup": max(drv_clean) if drv_clean else None,
        "turkish_rtf": round(tr_gen / tr_audio, 3) if tr_audio else None,
        "turkish_per_sentence_rtf": [round(x["gen_s"] / x["audio_s"], 2) for x in b["turkish"] if x["audio_s"]],
        "turkish_mps_driver_after_gen": tr_drv or None,
        "mps_fallback_ops": b.get("mps_fallback_ops"), "network_hosts_blocked": b.get("network_hosts_blocked"),
        "modules_after_turkish": b.get("modules_after_turkish"),
    }


def caffeinate_created(window: list[str]) -> dict:
    """Assertion types a caffeinate created within 2 s of the window start, read back from `pmset -g log`."""
    start = dt_mod.datetime.fromisoformat(window[0])
    end = dt_mod.datetime.fromisoformat(window[1])
    by_pid: dict[str, list] = {}
    for ln in sh(["pmset", "-g", "log"], timeout=180).splitlines():
        m = re.match(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) [+-]\d{4} Assertions\s+PID (\d+)\(caffeinate\) (\w+) (\w+)", ln)
        if not m:
            continue
        t = dt_mod.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
        if start <= t <= end:
            by_pid.setdefault(m.group(2), []).append((t, m.group(3), m.group(4)))
    for pid, ev in by_pid.items():
        created = [e for e in ev if e[1] == "Created"]
        if created and abs((created[0][0] - start).total_seconds()) <= 2:
            released = [e for e in ev if e[1] in ("ClientDied", "Released", "TimedOut")]
            return {"created": sorted({e[2] for e in created}), "created_at": created[0][0].isoformat(),
                    "ended": sorted({f"{e[2]} {e[1]} {e[0].time()}" for e in released})}
    return {"created": None}


def silent_seconds(path: Path) -> float | None:
    """Total silence (ffmpeg silencedetect, -35 dB, >= 0.3 s) in a generated file."""
    if not path.exists():
        return None
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(path), "-af", "silencedetect=n=-35dB:d=0.3",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    return round(sum(float(x) for x in re.findall(r"silence_duration: ([0-9.]+)", err)), 2)


def collect_clean_run(args) -> None:
    """results.json for a --run-dir run (run 2): numbers and settings only, no text."""
    steps = load_json(RUN / "steps.json") if (RUN / "steps.json").exists() else {}
    chars = [len(x) for x in english_lines()]
    res = {"spike": "S4a", "run": args.run_dir, "date": time.strftime("%Y-%m-%d"),
           "machine": "Apple M1 Pro, 16 GB (see versions in bench_*)",
           "settings": {**GEN, "seed": "1000 + line index (warm-up 999, Turkish 2000 + k)",
                        "warmup": "1 generation, excluded",
                        "voice": "built-in default: model.conds from the repo's conds.pt; prepare_conditionals not "
                                 "called; no cloning, no film audio (D-84)",
                        "per_line_cleanup": "MPS: synchronize, gc.collect, empty_cache; CPU: gc.collect "
                                            "(after warm-up, every English line and every Turkish sentence; not timed)",
                        "blocked_modules": [*OPTIONAL_BLOCKED, "spacy_pkuseg"],
                        "caffeinate": " ".join(CAFFEINATE), "HF_HUB_OFFLINE": "1",
                        "network": "socket guard, no hosts allowed"},
           "english_lines": {"count": len(chars), "chars": chars, "total_chars": sum(chars)}}
    summary, benches = {}, {}
    for dev in ("cpu", "mps"):
        p = RUN / f"bench_{dev}.json"
        if p.exists():
            benches[dev] = load_json(p)
            summary[dev] = device_summary(benches[dev], steps.get(f"bench_{dev}", {}))
            sil = [silent_seconds(AUDIO_OUT / f"{dev}_en_{x['i']:02d}.wav") for x in benches[dev]["per_line"]]
            summary[dev]["per_line_silent_s"] = sil
            summary[dev]["per_line_non_silent_s"] = [round(x["audio_s"] - s, 2) if s is not None else None
                                                     for x, s in zip(benches[dev]["per_line"], sil)]
    res["summary"] = summary
    res["conditions"] = {}
    for dev in summary:
        b_step = steps.get(f"bench_{dev}", {})
        res["conditions"][dev] = {
            "power_before": steps.get(f"power_before_{dev}"), "load_wait": steps.get(f"load_wait_{dev}"),
            "power_after": steps.get(f"power_after_{dev}"), "sleep_wake": steps.get(f"sleep_wake_{dev}"),
            "caffeinate_assertions": b_step.get("caffeinate_assertions"),
            "caffeinate_from_pmset_log": (caffeinate_created(steps[f"sleep_wake_{dev}"]["window"])
                                          if steps.get(f"sleep_wake_{dev}") else None),
            "wall_clock_minus_monotonic_s": b_step.get("wall_clock_minus_monotonic_s"),
        }
    comp = {"note": "run 1: cloned ISLIK SPEAKER_01 voice (11.8 s), battery, load ~10, Mac slept during the MPS "
                    "pass, no cache freeing, pykakasi/gradio not blocked; run 2: built-in voice, see settings"}
    for dev in summary:
        p = OUT / "run1" / f"bench_{dev}.json"
        if not p.exists():
            continue
        s1 = device_summary(load_json(p), (load_json(OUT / "run1" / "steps.json") if (OUT / "run1" / "steps.json").exists()
                                           else {}).get(f"bench_{dev}", {}))
        s2 = summary[dev]
        comp[dev] = {k: {"run1": s1[k], "run2": s2[k]} for k in
                     ("load_s", "rtf", "per_line_rtf_min", "per_line_rtf_max", "per_line_rtf_median", "total_gen_s",
                      "total_audio_s", "forced_eos_lines", "turkish_rtf", "peak_rss_bytes_time_l",
                      "peak_footprint_bytes_time_l", "mps_driver_peak_after_gen", "t3_tokens_per_s")}
        comp[dev]["rtf_run2_over_run1"] = round(s2["rtf"] / s1["rtf"], 3)
    res["run1_comparison"] = comp
    if summary:
        best = min(summary, key=lambda d: summary[d]["rtf"])
        speech_min, factor, budget = 55.0, 1.3, 270
        tts = speech_min * factor * summary[best]["rtf"]
        res["projection_90min_estimate"] = {
            "assumption": "55 min English speech x 1.3 (audition, drift-gate regenerations, rewrites) x best RTF; "
                          "voice-independent speed is an assumption",
            "best_device": best, "rtf": summary[best]["rtf"], "tts_minutes": round(tts, 1),
            "per_device_tts_minutes": {d: round(speech_min * factor * s["rtf"], 1) for d, s in summary.items()},
            "pipeline_budget_minutes_3x": budget, "tts_over_budget_ratio": round(tts / budget, 2),
        }
    res["steps"] = {k: v for k, v in steps.items() if k.startswith("bench")}
    for dev, b in benches.items():
        res[f"bench_{dev}"] = b
    res["log_text_check"] = check_logs_for_text()
    save_json(RUN / "results.json", res)
    print("results:", RUN / "results.json")


def step_collect(_args) -> None:
    if getattr(_args, "run_dir", None):
        collect_clean_run(_args)
        return
    steps = load_json(RUN / "steps.json") if (RUN / "steps.json").exists() else {}
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
        p = RUN / f"bench_{dev}.json"
        if p.exists():
            res[f"bench_{dev}"] = load_json(p)
    for p in sorted(RUN.glob("blocked_*.json")):
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
    save_json(RUN / "results.json", res)
    print("results:", RUN / "results.json")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ref")
    sub.add_parser("fetch")
    sub.add_parser("importtime")
    b = sub.add_parser("bench")
    b.add_argument("--device", choices=["cpu", "mps"], required=True)
    b.add_argument("--voice", choices=["ref", "default"], default="ref",
                   help="ref: clone the ISLIK reference (run 1); default: built-in voice from conds.pt (run 2)")
    b.add_argument("--empty-cache", action="store_true", help="free memory after every generation (run 2)")
    b.add_argument("--block-optional", action="store_true", help="block pykakasi and gradio before import (run 2)")
    b.add_argument("--run-dir", default=None)
    bl = sub.add_parser("blocked")
    bl.add_argument("--device", choices=["cpu", "mps"], required=True)
    a = sub.add_parser("all")
    a.add_argument("--devices", nargs="+", default=["cpu", "mps"])
    a.add_argument("--blocked-device", choices=["cpu", "mps"], default=None)
    d = sub.add_parser("device", help="run 2: one clean device run with power/load/sleep checks")
    d.add_argument("--device", choices=["cpu", "mps"], required=True)
    d.add_argument("--run-dir", required=True)
    d.add_argument("--voice", choices=["ref", "default"], default="default")
    d.add_argument("--no-empty-cache", action="store_true")
    d.add_argument("--max-load", type=float, default=4.0)
    d.add_argument("--max-wait-s", type=int, default=300)
    c = sub.add_parser("collect")
    c.add_argument("--run-dir", default=None)
    args = ap.parse_args()
    configure_run(getattr(args, "run_dir", None))
    {"ref": step_ref, "fetch": step_fetch, "importtime": step_importtime, "bench": step_bench,
     "blocked": step_blocked, "all": step_all, "device": step_device, "collect": step_collect}[args.cmd](args)


if __name__ == "__main__":
    main()
