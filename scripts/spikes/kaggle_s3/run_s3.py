#!/usr/bin/env python3
"""VoxShift spike S3 — rough end-to-end dub of real CC-BY Turkish short films on Kaggle.

Throwaway Phase 0 spike (docs/SPEC.md §17); not product code. Inputs: the private Kaggle
dataset voxshift-s3-clips (sources and licenses in docs/footage.md). Every model family runs
in its own uv venv, one process at a time (SPEC §6). Outputs, private evaluation only:
/kaggle/working/s3/ (results.json, summary.md, review_<clip>.md, audio/*.m4a, logs/).

Stages: prepare → separate (Demucs; TIGER on the first clip) → ASR (faster-whisper, word
timestamps) → diarize (pyannote) → build segments → translate (TranslateGemma 4B, Ollama)
→ references → TTS (Chatterbox Multilingual, per-speaker cached conditioning) → voice QC
(speaker embeddings) → fit + mix (separated and ducked-original) → English re-transcription.
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

WORK_OUT = Path(os.environ.get("S3_WORK", "/kaggle/working")) / "s3"
SCRATCH = Path(os.environ.get("S3_SCRATCH", "/tmp/s3"))
LOGS = WORK_OUT / "logs"
AUDIO_OUT = WORK_OUT / "audio"
CLIPS_DIR = SCRATCH / "clips"
VENVS = SCRATCH / "venvs"
BENCH = SCRATCH / "bench"
PY_VERSION = "3.11"
INPUT_GLOB = "/kaggle/input/**/*.m4a"

CLIP_IDS = ["QJH3CCrjda4", "aLvkEaaDte8", "cQ8J2vdB9VU"]  # ISLIK, Teneke, Hediye (docs/footage.md)
REQUIRE_HF_TOKEN = True  # diarization and voice QC need it; start this run from the Kaggle editor
RUN_TIGER_ON_FIRST = True
ASR_MODEL = "large-v3"
TRANSLATION_MODEL = ["translategemma:4b", "translategemma:4b-it-q4_K_M"]
TTS_VARIANTS_FIRST = {"cfg05": 0.5, "cfg00": 0.0}  # first clip: compare cfg_weight (accent vs length)
TTS_VARIANTS = {"cfg05": 0.5}
REF_SECONDS = 12.0

ENV = dict(os.environ)
ENV.update({
    "HF_HOME": str(SCRATCH / "hf"),
    "TORCH_HOME": str(SCRATCH / "torch"),
    "UV_CACHE_DIR": str(SCRATCH / "uv-cache"),
    "UV_LINK_MODE": "hardlink",
    "PYTHONUNBUFFERED": "1",
    "TOKENIZERS_PARALLELISM": "false",
    "CUDA_VISIBLE_DEVICES": "0",
})

RESULTS: dict = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "env": {}, "install": {}, "stages": {}}

FAMILIES = {
    "sep": {"pkgs": ["setuptools<81", "demucs @ git+https://github.com/adefossez/demucs", "soundfile"],
            "fallback_pkgs": ["setuptools<81", "demucs", "soundfile"]},
    "tiger": {"pkgs": ["setuptools<81", "torch", "torchaudio", "soundfile", "huggingface_hub", "pyyaml", "numpy"],
              "repo": "https://github.com/JusperLee/TIGER"},
    "asr": {"pkgs": ["setuptools<81", "faster-whisper", "jiwer", "soundfile", "nvidia-cublas-cu12", "nvidia-cudnn-cu12==9.*"]},
    "diar": {"pkgs": ["setuptools<81", "pyannote.audio>=4.0", "soundfile"]},
    "dsp": {"pkgs": ["setuptools<81", "numpy", "soundfile"]},
    "tts": {"pkgs": ["setuptools<81", "chatterbox-tts", "soundfile", "resemble-perth"]},
}

TRANSLATE_PROMPT = (
    "You are a professional Turkish (tr) to English (en) translator. Your goal is to accurately "
    "convey the meaning and nuances of the original Turkish text while adhering to English grammar, "
    "vocabulary, and cultural sensitivities. Produce only the English translation, without any "
    "additional explanations or commentary. Please translate the following Turkish text into "
    "English:\n\n{text}"
)

# ---------------------------------------------------------------- stage programs
# Each runs in its family's venv as: <venv>/bin/python <file>.py '<json cfg>'.

HEAD = r'''
import json, os, sys, time, resource, traceback
CFG = json.loads(sys.argv[1])
RESULT = {"stage": CFG["stage"], "ok": False}

def clip_dir(cid):
    return os.path.join(CFG["clips_dir"], cid)

def load_json(path):
    with open(path) as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

def versions(*names):
    from importlib.metadata import version
    out = {}
    for n in names:
        try:
            out[n] = version(n)
        except Exception:
            out[n] = None
    return out

def speed(audio_s, run_s):
    return {"audio_s": round(audio_s, 2), "run_s": round(run_s, 2),
            "x_realtime": round(audio_s / run_s, 2) if run_s > 0 else None,
            "rtf": round(run_s / audio_s, 3) if audio_s > 0 else None}

def ffmpeg_mono(path, sr):
    import subprocess
    import numpy as np
    raw = subprocess.run([CFG["ffmpeg"], "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()
'''

TAIL = r'''
try:
    main()
    RESULT["ok"] = True
except BaseException as e:
    RESULT["error"] = f"{type(e).__name__}: {e}"[:2000]
    RESULT["traceback"] = traceback.format_exc()[-4000:]
finally:
    RESULT["peak_rss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    try:
        import torch
        if torch.cuda.is_available():
            RESULT["torch_peak_gpu_mb"] = round(torch.cuda.max_memory_allocated() / 2**20, 1)
    except Exception:
        pass
    with open(CFG["result_path"], "w") as f:
        json.dump(RESULT, f, indent=2, default=str)
'''

SOURCES: dict[str, str] = {}

SOURCES["sep"] = r'''
def main():
    import soundfile as sf, torch
    from demucs.pretrained import get_model
    from demucs.apply import apply_model
    RESULT["versions"] = versions("demucs", "torch")
    t = time.time()
    model = get_model("htdemucs")
    model.to("cuda").eval()
    RESULT["load_s"] = round(time.time() - t, 1)
    vi = model.sources.index("vocals")
    for cid in CFG["clips"]:
        d = clip_dir(cid)
        mix, sr = sf.read(os.path.join(d, "original_44k.wav"), dtype="float32")
        x = torch.from_numpy(mix.T.copy())
        ref = x.mean(0)
        xn = (x - ref.mean()) / (ref.std() + 1e-8)
        t = time.time()
        with torch.no_grad():
            out = apply_model(model, xn[None], device="cuda", split=True, overlap=0.25, progress=False)[0]
        torch.cuda.synchronize()
        el = time.time() - t
        out = out * ref.std() + ref.mean()
        sf.write(os.path.join(d, "dialogue_44k.wav"), out[vi].mean(0).cpu().numpy(), sr)
        sf.write(os.path.join(d, "background_44k.wav"), (out.sum(0) - out[vi]).cpu().numpy().T, sr)
        RESULT[cid] = speed(len(mix) / sr, el)
'''

SOURCES["tiger"] = r'''
def main():
    import soundfile as sf, torch
    sys.path.insert(0, CFG["tiger_repo"])
    import look2hear.models
    t = time.time()
    model = look2hear.models.TIGERDNR.from_pretrained("JusperLee/TIGER-DnR",
                                                      cache_dir=os.path.join(os.environ["HF_HOME"], "tiger"))
    model = model.to("cuda").eval()
    RESULT["load_s"] = round(time.time() - t, 1)
    cid = CFG["clips"][0]
    d = clip_dir(cid)
    mix = ffmpeg_mono(os.path.join(d, "original_44k.wav"), 44100)
    x = torch.from_numpy(mix)[None, None].to("cuda")
    t = time.time()
    with torch.no_grad():
        try:
            dia, eff, mus = model(x)
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            step, parts = 30 * 44100, []
            for i in range(0, x.shape[-1], step):
                parts.append([o.cpu() for o in model(x[..., i:i + step])])
            dia = torch.cat([p[0] for p in parts], -1)
            eff = torch.cat([p[1] for p in parts], -1)
            mus = torch.cat([p[2] for p in parts], -1)
    torch.cuda.synchronize()
    RESULT[cid] = speed(len(mix) / 44100, time.time() - t)
    sf.write(os.path.join(d, "tiger_dialogue_44k.wav"), dia.squeeze().float().cpu().numpy(), 44100)
    sf.write(os.path.join(d, "tiger_background_44k.wav"), (eff + mus).squeeze().float().cpu().numpy(), 44100)
'''

SOURCES["asr"] = r'''
def main():
    import re
    import soundfile as sf
    from faster_whisper import WhisperModel
    RESULT["versions"] = versions("faster-whisper", "ctranslate2")
    t = time.time()
    model = WhisperModel(CFG["asr_model"], device="cuda", compute_type="float16")
    RESULT["load_s"] = round(time.time() - t, 1)

    if CFG["mode"] == "source":
        for cid in CFG["clips"]:
            d = clip_dir(cid)
            for inp in ("dialogue", "original"):
                path = os.path.join(d, f"{inp}_16k.wav")
                t = time.time()
                segs, info = model.transcribe(path, language="tr", beam_size=5, condition_on_previous_text=False,
                                              vad_filter=True, word_timestamps=True)
                segs = list(segs)
                el = time.time() - t
                data = [{"start": s.start, "end": s.end, "text": s.text.strip(), "avg_logprob": s.avg_logprob,
                         "no_speech_prob": s.no_speech_prob, "compression_ratio": s.compression_ratio,
                         "words": [{"start": w.start, "end": w.end, "word": w.word, "p": w.probability}
                                   for w in (s.words or [])]} for s in segs]
                save_json(os.path.join(d, f"asr_{inp}.json"), data)
                flagged = sum(1 for s in data
                              if (s["no_speech_prob"] > 0.6 and s["avg_logprob"] < -1.0) or s["compression_ratio"] > 2.4)
                r = speed(sf.info(path).duration, el)
                r.update({"segments": len(data), "words": sum(len(s["words"]) for s in data), "flagged": flagged,
                          "mean_avg_logprob": round(sum(s["avg_logprob"] for s in data) / max(len(data), 1), 3)})
                RESULT[f"{cid}_{inp}"] = r
    else:  # "check": re-transcribe the dubbed English mixes
        import jiwer

        def norm(s):
            s = re.sub(r"[^\w\s]", " ", s.lower())
            return " ".join(s.split())

        for item in load_json(CFG["check_list"]):
            segs, info = model.transcribe(item["path"], beam_size=5, condition_on_previous_text=False, vad_filter=True)
            hyp = " ".join(s.text for s in segs)
            RESULT[item["name"]] = {"detected_language": info.language,
                                    "language_probability": round(info.language_probability, 3),
                                    "wer_vs_translation": round(jiwer.wer(norm(item["ref_text"]), norm(hyp)), 3)}
'''

SOURCES["diar"] = r'''
def main():
    import soundfile as sf, torch
    from pyannote.audio import Pipeline
    RESULT["versions"] = versions("pyannote.audio", "torch")
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN missing")
    t = time.time()
    pipe = Pipeline.from_pretrained("pyannote/speaker-diarization-community-1", token=token)
    pipe.to(torch.device("cuda"))
    RESULT["load_s"] = round(time.time() - t, 1)

    def tracks(ann):
        try:
            return [(seg.start, seg.end, spk) for seg, spk in ann]
        except (TypeError, ValueError):
            return [(seg.start, seg.end, spk) for seg, _, spk in ann.itertracks(yield_label=True)]

    for cid in CFG["clips"]:
        d = clip_dir(cid)
        for inp in ("dialogue", "original"):
            wav, sr = sf.read(os.path.join(d, f"{inp}_16k.wav"), dtype="float32")
            t = time.time()
            out = pipe({"waveform": torch.from_numpy(wav)[None], "sample_rate": sr})
            el = time.time() - t
            regular, exclusive = tracks(out.speaker_diarization), tracks(out.exclusive_speaker_diarization)
            save_json(os.path.join(d, f"diar_{inp}.json"), {"regular": regular, "exclusive": exclusive})
            per = {}
            for a, b, s in exclusive:
                per[s] = per.get(s, 0.0) + (b - a)
            r = speed(len(wav) / sr, el)
            r.update({"speakers": len(per), "speech_s_per_speaker": {k: round(v, 1) for k, v in sorted(per.items())}})
            RESULT[f"{cid}_{inp}"] = r
'''

SOURCES["build"] = r'''
def main():
    import soundfile as sf
    for cid in CFG["clips"]:
        d = clip_dir(cid)
        asr = load_json(os.path.join(d, "asr_dialogue.json"))
        diar = load_json(os.path.join(d, "diar_dialogue.json"))
        excl, reg = diar["exclusive"], diar["regular"]
        media_end = sf.info(os.path.join(d, "original_16k.wav")).duration

        def flagged(s):
            return (s["no_speech_prob"] > 0.6 and s["avg_logprob"] < -1.0) or s["compression_ratio"] > 2.4

        words = [w for s in asr if not flagged(s) for w in s["words"] if w["start"] is not None]
        dropped = sum(1 for s in asr if flagged(s))

        def speaker_of(a, b):
            best, best_o = None, 0.0
            for x, y, spk in excl:
                o = min(b, y) - max(a, x)
                if o > best_o:
                    best, best_o = spk, o
            if best is None and excl:
                near = min(excl, key=lambda t: min(abs(t[0] - b), abs(t[1] - a)))
                if min(abs(near[0] - b), abs(near[1] - a)) <= 0.5:
                    best = near[2]
            return best or "UNKNOWN"

        segs, cur = [], None
        for w in words:
            spk = speaker_of(w["start"], w["end"])
            sentence_end = cur is not None and cur["text"].rstrip().endswith((".", "?", "!", "…"))
            if (cur and spk == cur["speaker"] and w["start"] - cur["end"] < 0.35 and not sentence_end
                    and w["end"] - cur["start"] <= 12.0):
                cur["end"] = w["end"]
                cur["text"] += w["word"]
                cur["ps"].append(w["p"])
            else:
                if cur:
                    segs.append(cur)
                cur = {"speaker": spk, "start": w["start"], "end": w["end"], "text": w["word"], "ps": [w["p"]]}
        if cur:
            segs.append(cur)
        segs = [s for s in segs if s["text"].strip()]

        for i, s in enumerate(segs):
            s["idx"] = i
            s["text"] = s["text"].strip()
            ps = s.pop("ps")
            s["mean_p"] = round(sum(ps) / max(1, len(ps)), 3)
            dur = s["end"] - s["start"]
            other = sum(max(0.0, min(s["end"], b) - max(s["start"], a)) for a, b, spk in reg if spk != s["speaker"])
            s["is_overlap"] = dur > 0 and other / dur > 0.2
        for s in segs:
            later = [o["start"] for o in segs if o["start"] >= s["end"] and o is not s]
            nxt = min(later) if later else media_end
            s["hard_limit"] = round(nxt - 0.12 - s["start"], 3)
            s["available"] = round(min(s["hard_limit"], 1.25 * (s["end"] - s["start"])), 3)
        speakers = {}
        for s in segs:
            speakers[s["speaker"]] = speakers.get(s["speaker"], 0.0) + s["end"] - s["start"]
        save_json(os.path.join(d, "segments.json"), {"segments": segs, "speakers": speakers})
        RESULT[cid] = {"segments": len(segs), "asr_segments_dropped_by_filters": dropped,
                       "speech_s_per_speaker": {k: round(v, 1) for k, v in sorted(speakers.items())},
                       "overlap_segments": sum(1 for s in segs if s["is_overlap"]),
                       "unknown_speaker_segments": sum(1 for s in segs if s["speaker"] == "UNKNOWN")}
'''

SOURCES["refs"] = r'''
def main():
    import numpy as np, soundfile as sf
    for cid in CFG["clips"]:
        d = clip_dir(cid)
        segs = load_json(os.path.join(d, "segments.json"))["segments"]
        dia, sr = sf.read(os.path.join(d, "dialogue_48k.wav"), dtype="float32")
        refs = {}
        for spk in sorted({s["speaker"] for s in segs}):
            cands = [s for s in segs if s["speaker"] == spk and not s["is_overlap"] and 2.0 <= s["end"] - s["start"] <= 12.0]
            cands.sort(key=lambda s: -s["mean_p"])
            parts, total, used = [], 0.0, []
            for s in cands:
                a = dia[int(s["start"] * sr):int(s["end"] * sr)]
                parts += [a, np.zeros(int(0.15 * sr), np.float32)]
                total += len(a) / sr
                used.append(s["idx"])
                if total >= CFG["ref_seconds"]:
                    break
            if total < 2.0 or spk == "UNKNOWN":
                refs[spk] = {"path": None, "seconds": round(total, 1), "source": "default_voice"}
                continue
            ref = np.concatenate(parts)
            ref = np.clip(ref * (0.1 / (np.sqrt(np.mean(ref ** 2)) + 1e-9)), -0.99, 0.99)
            path = os.path.join(d, f"ref_{spk}.wav")
            sf.write(path, ref, sr)
            refs[spk] = {"path": path, "seconds": round(total, 1), "segments": used, "source": "cloned"}
        save_json(os.path.join(d, "references.json"), refs)
        RESULT[cid] = {k: {"seconds": v["seconds"], "source": v["source"]} for k, v in refs.items()}
'''

SOURCES["tts"] = r'''
def main():
    import soundfile as sf, torch
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    RESULT["versions"] = versions("chatterbox-tts", "torch")
    t = time.time()
    model = ChatterboxMultilingualTTS.from_pretrained(device="cuda")
    RESULT["load_s"] = round(time.time() - t, 1)
    sr = model.sr
    default_conds = model.conds
    for ci, cid in enumerate(CFG["clips"]):
        d = clip_dir(cid)
        segs = load_json(os.path.join(d, "segments.json"))["segments"]
        tr = load_json(os.path.join(d, "translations.json"))
        refs = load_json(os.path.join(d, "references.json"))
        variants = CFG["variants_first"] if ci == 0 else CFG["variants"]
        by_spk = {}
        for s in segs:
            by_spk.setdefault(s["speaker"], []).append(s)
        for vname, cw in variants.items():
            outdir = os.path.join(d, f"tts_{vname}")
            os.makedirs(outdir, exist_ok=True)
            res, gen, dur, errors = {}, 0.0, 0.0, 0
            for spk, items in by_spk.items():
                ref = (refs.get(spk) or {}).get("path")
                if ref:
                    model.prepare_conditionals(ref, exaggeration=0.5)  # once per actor, re-prepared on every switch
                else:
                    model.conds = default_conds
                for s in items:
                    text = (tr.get(str(s["idx"])) or "").strip()
                    if not text:
                        continue
                    torch.manual_seed(10000 + s["idx"])
                    t = time.time()
                    try:
                        wav = model.generate(text, language_id="en", cfg_weight=cw, exaggeration=0.5)
                    except Exception:
                        errors += 1
                        continue
                    torch.cuda.synchronize()
                    el = time.time() - t
                    a = wav.squeeze().float().cpu().numpy()
                    path = os.path.join(outdir, f"seg_{s['idx']:04d}.wav")
                    sf.write(path, a, sr)
                    res[str(s["idx"])] = {"path": path, "dur": round(len(a) / sr, 3), "gen_s": round(el, 3)}
                    gen += el
                    dur += len(a) / sr
            save_json(os.path.join(d, f"tts_{vname}.json"), res)
            r = speed(dur, gen)
            r.update({"segments": len(res), "errors": errors})
            RESULT[f"{cid}_{vname}"] = r
'''

SOURCES["qc"] = r'''
def main():
    import numpy as np, torch
    from pyannote.audio import Model, Inference
    token = os.environ.get("HF_TOKEN")
    model = Model.from_pretrained("pyannote/wespeaker-voxceleb-resnet34-LM", token=token)
    inf = Inference(model, window="whole", device=torch.device("cuda"))

    def emb(path):
        wav = ffmpeg_mono(path, 16000)
        v = np.asarray(inf({"waveform": torch.from_numpy(wav)[None], "sample_rate": 16000})).reshape(-1)
        return v / (np.linalg.norm(v) + 1e-9)

    def unit(v):
        return v / (np.linalg.norm(v) + 1e-9)

    for ci, cid in enumerate(CFG["clips"]):
        d = clip_dir(cid)
        segs = load_json(os.path.join(d, "segments.json"))["segments"]
        refs = {k: emb(v["path"]) for k, v in load_json(os.path.join(d, "references.json")).items() if v.get("path")}
        variants = CFG["variants_first"] if ci == 0 else CFG["variants"]
        for vname in variants:
            tts = load_json(os.path.join(d, f"tts_{vname}.json"))
            per = {}
            for s in segs:
                item = tts.get(str(s["idx"]))
                if item and item["dur"] >= 1.0:
                    per.setdefault(s["speaker"], []).append(emb(item["path"]))
            r, cents = {}, {}
            for spk, es in per.items():
                E = np.stack(es)
                c = unit(E.mean(0))
                cents[spk] = c
                to_c = E @ c
                r[spk] = {"n": len(es), "cos_to_own_centroid_mean": round(float(to_c.mean()), 3),
                          "cos_to_own_centroid_p10": round(float(np.percentile(to_c, 10)), 3),
                          "cos_to_reference_mean": round(float((E @ refs[spk]).mean()), 3) if spk in refs else None}
            names = sorted(cents)
            r["between_speakers"] = {f"{a}~{b}": round(float(cents[a] @ cents[b]), 3)
                                     for i, a in enumerate(names) for b in names[i + 1:]}
            RESULT[f"{cid}_{vname}"] = r
'''

SOURCES["mix"] = r'''
def main():
    import subprocess
    import numpy as np, soundfile as sf
    ff, SR = CFG["ffmpeg"], 48000
    os.makedirs(CFG["audio_out"], exist_ok=True)
    check = []

    def load_clip(path, tempo=None):
        args = [ff, "-v", "error", "-i", path]
        if tempo:
            args += ["-af", f"atempo={tempo:.4f}"]
        args += ["-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
        return np.frombuffer(subprocess.run(args, check=True, capture_output=True).stdout, np.float32).copy()

    def fade(a, ms=15):
        n = min(len(a) // 2, int(SR * ms / 1000))
        if n > 0:
            ramp = np.linspace(0, 1, n, dtype=np.float32)
            a[:n] *= ramp
            a[-n:] *= ramp[::-1]
        return a

    def smooth(x, ms=50):
        k = max(1, int(SR * ms / 1000))
        c = np.cumsum(np.concatenate([[0.0], x.astype(np.float64)]))
        out = np.empty_like(x)
        half = k // 2
        idx = np.arange(len(x))
        lo, hi = np.clip(idx - half, 0, len(x)), np.clip(idx + half + 1, 0, len(x))
        out[:] = (c[hi] - c[lo]) / (hi - lo)
        return out

    for ci, cid in enumerate(CFG["clips"]):
        d = clip_dir(cid)
        segs = load_json(os.path.join(d, "segments.json"))["segments"]
        tr = load_json(os.path.join(d, "translations.json"))
        orig, _ = sf.read(os.path.join(d, "original_48k.wav"), dtype="float32")
        bg, _ = sf.read(os.path.join(d, "background_48k.wav"), dtype="float32")
        dia, _ = sf.read(os.path.join(d, "dialogue_48k.wav"), dtype="float32")
        n = min(len(orig), len(bg), len(dia))
        orig, bg, dia = orig[:n], bg[:n], dia[:n]
        variants = CFG["variants_first"] if ci == 0 else CFG["variants"]
        for vname in variants:
            tts = load_json(os.path.join(d, f"tts_{vname}.json"))
            track = np.zeros(n, np.float32)
            spans, rows, fit = [], [], {"none": 0, "tempo": 0, "truncated": 0}
            ratios, placed_text = [], []
            for s in segs:
                item = tts.get(str(s["idx"]))
                if not item:
                    continue
                avail, hard = max(0.2, s["available"]), max(0.2, s["hard_limit"])
                r = item["dur"] / avail
                ratios.append(r)
                if r <= 1.0:
                    a, method = load_clip(item["path"]), "none"
                else:
                    a, method = load_clip(item["path"], tempo=min(r, 1.25)), "tempo"
                    if len(a) / SR > hard:
                        a, method = a[:int(hard * SR)], "truncated"
                fit[method] += 1
                i0 = int(s["start"] * SR)
                i1 = min(n, i0 + len(a))
                src = dia[i0:max(i0 + 1, int(s["end"] * SR))]
                gain = (np.sqrt(np.mean(src ** 2)) + 1e-6) / (np.sqrt(np.mean(a ** 2)) + 1e-6)
                a = fade(a * float(np.clip(gain, 10 ** (-12 / 20), 10 ** (12 / 20))))
                track[i0:i1] += a[:i1 - i0]
                spans.append((s["start"], s["start"] + len(a) / SR))
                placed_text.append(tr.get(str(s["idx"]), ""))
                rows.append((s["idx"], s["speaker"], s["start"], s["text"], tr.get(str(s["idx"]), ""), round(r, 2), method))
            mask = np.zeros(n, np.float32)
            for a0, a1 in spans:
                mask[max(0, int((a0 - 0.1) * SR)):min(n, int((a1 + 0.1) * SR))] = 1.0
            mask = smooth(mask)
            layback = dia * (1.0 - mask) * 10 ** (-6 / 20)       # SPEC §10.2 non-verbal lay-back
            mix_sep = bg + (track + layback)[:, None]
            duck = 1.0 - mask * (1.0 - 10 ** (-15 / 20))           # SPEC §10.1 speech-mask ducked original
            mix_duck = orig * duck[:, None] + track[:, None]
            for mode, m in (("separated", mix_sep), ("ducked", mix_duck)):
                raw = os.path.join(d, f"dub_{vname}_{mode}.wav")
                sf.write(raw, m, SR)
                out = os.path.join(CFG["audio_out"], f"{cid}_{vname}_{mode}.m4a")
                subprocess.run([ff, "-v", "error", "-y", "-i", raw, "-af", "loudnorm=I=-16:TP=-2:LRA=11",
                                "-c:a", "aac", "-b:a", "192k", out], check=True)
                if mode == "separated":
                    check.append({"name": f"{cid}_{vname}", "path": raw, "ref_text": " ".join(placed_text)})
            total = max(1, len(ratios))
            RESULT[f"{cid}_{vname}"] = {
                "segments_placed": len(spans), "fit": fit,
                "ratio_median": round(float(np.median(ratios)), 2) if ratios else None,
                "share_tempo_over_1_10": round(sum(1 for x in ratios if x > 1.10) / total, 3),
                "share_truncated": round(fit["truncated"] / total, 3)}
            if vname == list(variants)[0]:
                lines = [f"# Review — {cid} ({vname})", "",
                         "| # | Speaker | Start s | Turkish | English | gen/available | Fit |", "| --- | --- | --- | --- | --- | --- | --- |"]
                for i, spk, st, src_text, tgt, ratio, method in rows:
                    clean = lambda x: x.replace("|", "/").replace("\n", " ")
                    lines.append(f"| {i} | {spk} | {st:.1f} | {clean(src_text)} | {clean(tgt)} | {ratio} | {method} |")
                with open(os.path.join(CFG["out_dir"], f"review_{cid}.md"), "w") as f:
                    f.write("\n".join(lines))
        for stem, label in (("dialogue_48k.wav", "demucs_dialogue"), ("background_48k.wav", "demucs_background")):
            subprocess.run([ff, "-v", "error", "-y", "-i", os.path.join(d, stem), "-c:a", "aac", "-b:a", "160k",
                            os.path.join(CFG["audio_out"], f"{cid}_{label}.m4a")], check=True)
        for stem, label in (("tiger_dialogue_44k.wav", "tiger_dialogue"), ("tiger_background_44k.wav", "tiger_background")):
            if os.path.exists(os.path.join(d, stem)):
                subprocess.run([ff, "-v", "error", "-y", "-i", os.path.join(d, stem), "-c:a", "aac", "-b:a", "160k",
                                os.path.join(CFG["audio_out"], f"{cid}_{label}.m4a")], check=True)
    save_json(CFG["check_list"], check)
'''

# ---------------------------------------------------------------- orchestration


def save() -> None:
    (WORK_OUT / "results.json").write_text(json.dumps(RESULTS, indent=2, ensure_ascii=False, default=str))


def run(cmd: list[str], log: Path, env: dict | None = None, timeout: int = 3600) -> int:
    with open(log, "a") as f:
        f.write(f"\n$ {' '.join(cmd)[:500]}\n")
        f.flush()
        try:
            return subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, env=env or ENV, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            f.write(f"TIMEOUT after {timeout}s\n")
            return 124


def du_gb(path: Path) -> float | None:
    out = subprocess.run(["du", "-sb", str(path)], capture_output=True, text=True)
    return round(int(out.stdout.split()[0]) / 1e9, 2) if out.returncode == 0 and out.stdout else None


class GpuSampler:
    """Samples GPU 0 every 250 ms and keeps the peak memory in MB."""

    def __init__(self) -> None:
        self.peak = 0
        self.proc: subprocess.Popen | None = None
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        self.proc = subprocess.Popen(["nvidia-smi", "-i", "0", "--query-gpu=memory.used",
                                      "--format=csv,noheader,nounits", "-lms", "250"],
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _read(self) -> None:
        assert self.proc and self.proc.stdout
        for line in self.proc.stdout:
            line = line.strip()
            if line.isdigit():
                self.peak = max(self.peak, int(line))

    def stop(self) -> int:
        if self.proc:
            self.proc.terminate()
        if self.thread:
            self.thread.join(timeout=2)
        return self.peak


def hf_token() -> str | None:
    if os.environ.get("HF_TOKEN"):
        return os.environ["HF_TOKEN"]
    try:
        from kaggle_secrets import UserSecretsClient  # type: ignore
        return UserSecretsClient().get_secret("HF_TOKEN")
    except Exception as e:  # record why, never the value
        RESULTS["env"]["hf_token_error"] = f"{type(e).__name__}: {e}"[:300]
        return None


def internet_ok() -> bool:
    try:
        urllib.request.urlopen("https://pypi.org/simple/uv/", timeout=15).read(100)
        return True
    except Exception:
        return False


INSTALLED: dict[str, bool] = {}


def install(name: str) -> bool:
    if name in INSTALLED:
        return INSTALLED[name]
    spec = FAMILIES[name]
    venv, log = VENVS / name, LOGS / f"install_{name}.log"
    py = str(venv / "bin" / "python")
    uv = [sys.executable, "-m", "uv"]
    t = time.time()
    ok = run([*uv, "venv", str(venv), "--python", PY_VERSION], log) == 0
    note = None
    if ok and spec.get("repo"):
        ok = run(["git", "clone", "--depth", "1", spec["repo"], str(SCRATCH / name / "repo")], log) == 0
    if ok:
        ok = run([*uv, "pip", "install", "--python", py, *spec["pkgs"]], log, timeout=2400) == 0
        if not ok and spec.get("fallback_pkgs"):
            note = "used fallback packages"
            ok = run([*uv, "pip", "install", "--python", py, *spec["fallback_pkgs"]], log, timeout=2400) == 0
    if ok and spec.get("repo"):
        req = SCRATCH / name / "repo" / "requirements.txt"
        if req.exists() and run([*uv, "pip", "install", "--python", py, "-r", str(req)], log, timeout=2400) != 0:
            note = "repo requirements.txt failed; base packages kept"
    RESULTS["install"][name] = {"ok": ok, "seconds": round(time.time() - t, 1), "venv_gb": du_gb(venv), "note": note}
    INSTALLED[name] = ok
    save()
    return ok


def stage(name: str, family: str, cfg: dict, ffmpeg: str, extra_env: dict | None = None, timeout: int = 5400,
          program: str | None = None) -> dict:
    if not install(family):
        res = {"ok": False, "error": f"install failed (logs/install_{family}.log)"}
        RESULTS["stages"][name] = res
        save()
        return res
    path = BENCH / f"stage_{name}.py"
    path.write_text(HEAD + SOURCES[program or name] + TAIL)
    result_path = WORK_OUT / f"stage_{name}.json"
    full = {**cfg, "stage": name, "result_path": str(result_path), "clips_dir": str(CLIPS_DIR), "ffmpeg": ffmpeg,
            "clips": CLIPS_READY}
    env = dict(ENV)
    env.update(extra_env or {})
    sampler = GpuSampler()
    sampler.start()
    t = time.time()
    rc = run([str(VENVS / family / "bin" / "python"), str(path), json.dumps(full, ensure_ascii=False)],
             LOGS / f"stage_{name}.log", env=env, timeout=timeout)
    wall = round(time.time() - t, 1)
    peak = sampler.stop()
    res = json.loads(result_path.read_text()) if result_path.exists() else {"ok": False, "error": f"no result (rc={rc})"}
    res.update({"wall_s": wall, "nvidia_smi_peak_mb": peak, "returncode": rc})
    RESULTS["stages"][name] = res
    save()
    print(f"[s3] {name}: ok={res.get('ok')} wall={wall}s peak={peak}MB {str(res.get('error') or '')[:200]}", flush=True)
    return res


def ffmpeg_convert(src: Path, dst: Path, rate: int, channels: int) -> None:
    subprocess.run([FFMPEG, "-v", "error", "-y", "-i", str(src), "-ac", str(channels), "-ar", str(rate), str(dst)],
                   check=True)


def translate_all() -> None:
    """TranslateGemma 4B via Ollama, one request per segment, then unload (keep_alive 0)."""
    log, r = LOGS / "ollama.log", {"model": None}
    env = dict(ENV, OLLAMA_MODELS=str(SCRATCH / "ollama"), OLLAMA_HOST="127.0.0.1:11434")
    if not shutil.which("ollama"):
        if not shutil.which("zstd"):
            run(["bash", "-lc", "apt-get update -qq && apt-get install -y -qq zstd"], log, timeout=900)
        run(["bash", "-lc", "curl -fsSL https://ollama.com/install.sh | sh"], log, timeout=1200)
    if not shutil.which("ollama"):
        RESULTS["stages"]["translate"] = {"ok": False, "error": "ollama install failed (logs/ollama.log)"}
        save()
        return
    server = subprocess.Popen(["ollama", "serve"], stdout=open(LOGS / "ollama_serve.log", "w"),
                              stderr=subprocess.STDOUT, env=env)

    def call(path: str, payload: dict | None = None, timeout: int = 600) -> dict:
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(f"http://127.0.0.1:11434{path}", data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())

    t0 = time.time()
    try:
        for _ in range(60):
            try:
                call("/api/tags")
                break
            except Exception:
                time.sleep(1)
        for tag in TRANSLATION_MODEL:
            if run(["ollama", "pull", tag], log, env=env, timeout=1800) == 0:
                r["model"] = tag
                break
        if not r["model"]:
            raise RuntimeError("pull failed")
        for cid in CLIPS_READY:
            segs = json.loads((CLIPS_DIR / cid / "segments.json").read_text())["segments"]
            out, src_chars, tgt_chars, t = {}, 0, 0, time.time()
            for s in segs:
                resp = call("/api/generate", {"model": r["model"], "prompt": TRANSLATE_PROMPT.format(text=s["text"]),
                                              "stream": False, "keep_alive": "5m", "options": {"temperature": 0}})
                text = " ".join(resp.get("response", "").strip().split())
                out[str(s["idx"])] = text
                src_chars += len(s["text"])
                tgt_chars += len(text)
            (CLIPS_DIR / cid / "translations.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
            r[cid] = {"segments": len(segs), "seconds": round(time.time() - t, 1),
                      "empty": sum(1 for v in out.values() if not v),
                      "en_to_tr_char_ratio": round(tgt_chars / max(src_chars, 1), 3)}
        call("/api/generate", {"model": r["model"], "prompt": "", "keep_alive": 0})
        r["ok"] = True
    except Exception as e:
        r["ok"] = False
        r["error"] = f"{type(e).__name__}: {e}"[:800]
    finally:
        server.terminate()
    r["wall_s"] = round(time.time() - t0, 1)
    RESULTS["stages"]["translate"] = r
    save()
    print(f"[s3] translate: ok={r.get('ok')} {r.get('error', '')}", flush=True)


def write_summary() -> None:
    st = RESULTS["stages"]
    lines = ["# Spike S3 results", "", f"Started {RESULTS['started']}; finished {RESULTS.get('finished')}", "",
             "| Stage | OK | Wall s | Peak GPU MB | Error |", "| --- | --- | --- | --- | --- |"]
    for name, res in st.items():
        lines.append(f"| {name} | {res.get('ok')} | {res.get('wall_s', '')} | {res.get('nvidia_smi_peak_mb', '')} | "
                     f"{str(res.get('error') or '')[:120]} |")
    lines += ["", "## Per clip", ""]
    for cid in CLIPS_READY:
        lines.append(f"### {cid}")
        for name in ("sep", "asr", "diar", "build", "refs", "translate", "tts", "qc", "mix", "check"):
            res = st.get(name, {})
            keys = [k for k in res if k == cid or k.startswith(cid + "_")]
            for k in keys:
                lines.append(f"- {name} `{k}`: {json.dumps(res[k], ensure_ascii=False)[:600]}")
        lines.append("")
    lines += ["Listen: audio/<clip>_<variant>_separated.m4a and _ducked.m4a; stems: <clip>_demucs_*.m4a, <clip>_tiger_*.m4a.",
              "Read: review_<clip>.md (Turkish, English, fit per segment). Private evaluation only (docs/footage.md)."]
    (WORK_OUT / "summary.md").write_text("\n".join(lines))


CLIPS_READY: list[str] = []
FFMPEG = "ffmpeg"


def main() -> None:
    global FFMPEG
    for d in (WORK_OUT, LOGS, AUDIO_OUT, SCRATCH, CLIPS_DIR, VENVS, BENCH):
        d.mkdir(parents=True, exist_ok=True)
    FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
    RESULTS["env"]["gpus"] = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True).stdout.strip().splitlines()
    token = hf_token()
    RESULTS["env"]["hf_token_present"] = bool(token)
    RESULTS["env"]["internet"] = internet_ok()
    found = {Path(p).stem: p for p in glob.glob(INPUT_GLOB, recursive=True)}
    RESULTS["env"]["inputs_found"] = sorted(found)
    save()
    if not RESULTS["env"]["internet"]:
        print("[s3] No internet in this session: stopping.", flush=True)
        return
    if REQUIRE_HF_TOKEN and not token:
        print("[s3] HF_TOKEN secret not available (start this run from the Kaggle editor): stopping.", flush=True)
        return
    missing = [c for c in CLIP_IDS if c not in found]
    if missing:
        print(f"[s3] Missing inputs {missing}; attach the voxshift-s3-clips dataset: stopping.", flush=True)
        return
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "uv"], check=True)

    # Prepare: decode each clip once into the rates the models need.
    for cid in CLIP_IDS:
        d = CLIPS_DIR / cid
        d.mkdir(parents=True, exist_ok=True)
        src = Path(found[cid])
        ffmpeg_convert(src, d / "original_48k.wav", 48000, 2)
        ffmpeg_convert(src, d / "original_44k.wav", 44100, 2)
        ffmpeg_convert(src, d / "original_16k.wav", 16000, 1)
        CLIPS_READY.append(cid)

    stage("sep", "sep", {}, FFMPEG)
    for cid in CLIPS_READY:
        d = CLIPS_DIR / cid
        ffmpeg_convert(d / "dialogue_44k.wav", d / "dialogue_16k.wav", 16000, 1)
        ffmpeg_convert(d / "dialogue_44k.wav", d / "dialogue_48k.wav", 48000, 1)
        ffmpeg_convert(d / "background_44k.wav", d / "background_48k.wav", 48000, 2)
    if RUN_TIGER_ON_FIRST:
        stage("tiger", "tiger", {"tiger_repo": str(SCRATCH / "tiger" / "repo")}, FFMPEG)

    code = ("import os, nvidia.cublas.lib, nvidia.cudnn.lib; print(os.path.dirname(nvidia.cublas.lib.__file__)"
            " + ':' + os.path.dirname(nvidia.cudnn.lib.__file__))")
    asr_env: dict = {}
    if install("asr"):
        out = subprocess.run([str(VENVS / "asr" / "bin" / "python"), "-c", code], capture_output=True, text=True, env=ENV)
        if out.stdout.strip():
            asr_env = {"LD_LIBRARY_PATH": f"{out.stdout.strip()}:{os.environ.get('LD_LIBRARY_PATH', '')}"}
    stage("asr", "asr", {"mode": "source", "asr_model": ASR_MODEL}, FFMPEG, extra_env=asr_env)
    stage("diar", "diar", {}, FFMPEG, extra_env={"HF_TOKEN": token or ""})
    stage("build", "dsp", {}, FFMPEG)
    translate_all()
    stage("refs", "dsp", {"ref_seconds": REF_SECONDS}, FFMPEG)
    variants = {"variants_first": TTS_VARIANTS_FIRST, "variants": TTS_VARIANTS}
    stage("tts", "tts", variants, FFMPEG, timeout=7200)
    stage("qc", "diar", variants, FFMPEG, extra_env={"HF_TOKEN": token or ""})
    check_list = str(SCRATCH / "check_list.json")
    stage("mix", "dsp", {**variants, "audio_out": str(AUDIO_OUT), "out_dir": str(WORK_OUT), "check_list": check_list},
          FFMPEG)
    if Path(check_list).exists():
        stage("check", "asr", {"mode": "check", "asr_model": ASR_MODEL, "check_list": check_list}, FFMPEG,
              extra_env=asr_env, program="asr")

    RESULTS["disk"] = {"scratch_used_gb": du_gb(SCRATCH), "output_gb": du_gb(WORK_OUT)}
    RESULTS["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save()
    write_summary()
    print((WORK_OUT / "summary.md").read_text(), flush=True)


if __name__ == "__main__":
    main()
