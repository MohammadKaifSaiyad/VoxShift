#!/usr/bin/env python3
"""VoxShift spike S3b — S3 again with the spec's timing and identity mechanisms (Kaggle, T4).

Throwaway Phase 0 spike (docs/SPEC.md §17); not product code. Same inputs as S3 (private
dataset voxshift-s3-clips, docs/footage.md) and the decided models (D-62 Demucs, D-63
cfg_weight 0.5, D-64 separated mix). Adds, per docs/spikes.md S3 findings:

  fixed speaker count (cast-review stand-in) · speaker-flip smoothing · fragment merging ·
  confidence + singing filters (AST) · audition with distinct bank voices and voice_cps ·
  budgeted translation (TranslateGemma 4B vs Qwen3 4B) with validation + opus-mt fallback ·
  TTS silence trimming · up to 2 rewrite rounds · SPEC §9 fitting · kept-original spans ·
  English re-transcription check.

Outputs (private evaluation only): /kaggle/working/s3b/ (summary.md, results.json,
review_<clip>.md, audio/<clip>_dub.m4a, logs/).
"""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

WORK_OUT = Path(os.environ.get("S3B_WORK", "/kaggle/working")) / "s3b"
SCRATCH = Path(os.environ.get("S3B_SCRATCH", "/tmp/s3b"))
LOGS = WORK_OUT / "logs"
AUDIO_OUT = WORK_OUT / "audio"
CLIPS_DIR = SCRATCH / "clips"
VENVS = SCRATCH / "venvs"
BENCH = SCRATCH / "bench"
PY_VERSION = "3.11"
INPUT_GLOB = "/kaggle/input/**/*.m4a"

CLIP_IDS = ["QJH3CCrjda4", "aLvkEaaDte8", "cQ8J2vdB9VU"]  # ISLIK, Teneke, Hediye (docs/footage.md)
NUM_SPEAKERS = {"QJH3CCrjda4": 3, "aLvkEaaDte8": 2, "cQ8J2vdB9VU": 2}  # from the film credits
REQUIRE_HF_TOKEN = True
ASR_MODEL = "large-v3"
CFG_WEIGHT = 0.5  # D-63
TRANSLATORS = {"translategemma": ["translategemma:4b", "translategemma:4b-it-q4_K_M"],
               "qwen3": ["qwen3:4b", "qwen3:4b-q4_K_M"]}
REWRITER = "qwen3"
REWRITE_ROUNDS = 2
REF_SECONDS = 12.0
BUILD = {"flip_s": 0.5, "merge_gap_s": 0.35, "min_seg_s": 1.0, "fragment_gap_s": 1.0, "max_seg_s": 12.0,
         "min_mean_p": 0.45}
TAGGING = {"win_s": 3.0, "hop_s": 1.5, "singing_threshold": 0.3}
AUDITION_SENTENCES = [
    "I didn't expect to see you here so early this morning.",
    "We should talk about what happened yesterday, don't you think?",
    "Please close the door and sit down for a minute.",
]
BANK_TEXT = ("This is a reference recording for a fallback voice. It is spoken calmly and clearly, "
             "at an even pace, without any music in the background.")
S3_BASELINE = {"QJH3CCrjda4": {"speakers": 7, "over_1_10": 0.643, "truncated": 0.214},
               "aLvkEaaDte8": {"speakers": 4, "over_1_10": 0.933, "truncated": 0.467},
               "cQ8J2vdB9VU": {"speakers": 6, "over_1_10": 0.892, "truncated": 0.432}}

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
    "tag": {"pkgs": ["setuptools<81", "transformers", "torch", "soundfile", "numpy"]},
    "asr": {"pkgs": ["setuptools<81", "faster-whisper", "jiwer", "soundfile", "nvidia-cublas-cu12", "nvidia-cudnn-cu12==9.*"]},
    "diar": {"pkgs": ["setuptools<81", "pyannote.audio>=4.0", "soundfile"]},
    "dsp": {"pkgs": ["setuptools<81", "numpy", "soundfile"]},
    "tts": {"pkgs": ["setuptools<81", "chatterbox-tts", "soundfile", "resemble-perth"]},
    "opus": {"pkgs": ["setuptools<81", "transformers", "sentencepiece", "torch"]},
}

PROMPT_TRANSLATEGEMMA = (
    "You are a professional Turkish (tr) to English (en) translator. Your goal is to accurately "
    "convey the meaning and nuances of the original Turkish text while adhering to English grammar, "
    "vocabulary, and cultural sensitivities. Produce only the English translation, without any "
    "additional explanations or commentary. Keep the translation under {budget} characters. "
    "Please translate the following Turkish text into English:\n\n{text}"
)
PROMPT_QWEN_TRANSLATE = (
    "Translate the Turkish line into natural spoken English for a film dub.\n"
    "Rules: at most {budget} characters; keep names and numbers; same tone and register; "
    "output only the English line, no quotes, no notes.\n"
    "Earlier lines (context only, do not translate): {context}\n"
    "Turkish line: {text}"
)
PROMPT_QWEN_REWRITE = (
    "Shorten this English film-dub line to at most {budget} characters while keeping the meaning of the "
    "Turkish original, names and numbers. Output only the new English line, no quotes, no notes.\n"
    "Turkish original: {src}\n"
    "Current English: {en}"
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

def ffmpeg_mono(path, sr, af=None):
    import subprocess
    import numpy as np
    args = [CFG["ffmpeg"], "-v", "error", "-i", path]
    if af:
        args += ["-af", af]
    args += ["-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    raw = subprocess.run(args, check=True, capture_output=True).stdout
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
    model = get_model("htdemucs")
    model.to("cuda").eval()
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

SOURCES["tag"] = r'''
def main():
    import numpy as np, soundfile as sf, torch
    from transformers import ASTFeatureExtractor, ASTForAudioClassification
    name = "MIT/ast-finetuned-audioset-10-10-0.4593"
    fe = ASTFeatureExtractor.from_pretrained(name)
    model = ASTForAudioClassification.from_pretrained(name).to("cuda").eval()
    want = ["Singing", "Music", "Speech", "Laughter", "Crying, sobbing", "Screaming", "Sigh"]
    ids = {w: model.config.label2id[w] for w in want if w in model.config.label2id}
    RESULT["labels"] = list(ids)
    win, hop, thr = CFG["win_s"], CFG["hop_s"], CFG["singing_threshold"]
    for cid in CFG["clips"]:
        wav, sr = sf.read(os.path.join(clip_dir(cid), "dialogue_16k.wav"), dtype="float32")
        w = int(win * sr)
        starts = list(range(0, max(1, len(wav) - w + 1), int(hop * sr)))
        frames, t = [], time.time()
        for b in range(0, len(starts), 16):
            batch = [wav[s:s + w] for s in starts[b:b + 16]]
            inp = fe(batch, sampling_rate=sr, return_tensors="pt").to("cuda")
            with torch.no_grad():
                probs = torch.sigmoid(model(**inp).logits).cpu().numpy()
            for s, p in zip(starts[b:b + 16], probs):
                frames.append({"start": round(s / sr, 2), "end": round(s / sr + win, 2),
                               **{k: round(float(p[i]), 3) for k, i in ids.items()}})
        with open(os.path.join(clip_dir(cid), "events.json"), "w") as f:
            json.dump(frames, f)
        r = speed(len(wav) / sr, time.time() - t)
        r.update({"windows": len(frames),
                  "singing_windows": sum(1 for f in frames if f.get("Singing", 0) >= thr),
                  "max_singing": max((f.get("Singing", 0) for f in frames), default=0),
                  "music_windows": sum(1 for f in frames if f.get("Music", 0) >= 0.3)})
        RESULT[cid] = r
'''

SOURCES["asr"] = r'''
def main():
    import re
    import soundfile as sf
    from faster_whisper import WhisperModel
    RESULT["versions"] = versions("faster-whisper", "ctranslate2")
    model = WhisperModel(CFG["asr_model"], device="cuda", compute_type="float16")
    if CFG["mode"] == "source":
        for cid in CFG["clips"]:
            path = os.path.join(clip_dir(cid), "dialogue_16k.wav")
            t = time.time()
            segs, info = model.transcribe(path, language="tr", beam_size=5, condition_on_previous_text=False,
                                          vad_filter=True, word_timestamps=True)
            segs = list(segs)
            el = time.time() - t
            data = [{"start": s.start, "end": s.end, "text": s.text.strip(), "avg_logprob": s.avg_logprob,
                     "no_speech_prob": s.no_speech_prob, "compression_ratio": s.compression_ratio,
                     "words": [{"start": w.start, "end": w.end, "word": w.word, "p": w.probability}
                               for w in (s.words or [])]} for s in segs]
            save_json(os.path.join(clip_dir(cid), "asr_dialogue.json"), data)
            r = speed(sf.info(path).duration, el)
            r.update({"segments": len(data), "words": sum(len(s["words"]) for s in data)})
            RESULT[cid] = r
    else:
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
    pipe = Pipeline.from_pretrained("pyannote/speaker-diarization-community-1", token=token)
    pipe.to(torch.device("cuda"))

    def tracks(ann):
        try:
            return [(seg.start, seg.end, spk) for seg, spk in ann]
        except (TypeError, ValueError):
            return [(seg.start, seg.end, spk) for seg, _, spk in ann.itertracks(yield_label=True)]

    for cid in CFG["clips"]:
        wav, sr = sf.read(os.path.join(clip_dir(cid), "dialogue_16k.wav"), dtype="float32")
        k = CFG["num_speakers"].get(cid)
        for mode, kw in (("auto", {}), ("fixed", {"num_speakers": k} if k else {})):
            t = time.time()
            out = pipe({"waveform": torch.from_numpy(wav)[None], "sample_rate": sr}, **kw)
            el = time.time() - t
            excl = tracks(out.exclusive_speaker_diarization)
            save_json(os.path.join(clip_dir(cid), f"diar_{mode}.json"),
                      {"regular": tracks(out.speaker_diarization), "exclusive": excl})
            per = {}
            for a, b, s in excl:
                per[s] = per.get(s, 0.0) + (b - a)
            r = speed(len(wav) / sr, el)
            r.update({"speakers": len(per), "speech_s_per_speaker": {x: round(v, 1) for x, v in sorted(per.items())}})
            RESULT[f"{cid}_{mode}"] = r
'''

SOURCES["build"] = r'''
def main():
    import soundfile as sf
    P = CFG["build"]
    sing_thr = CFG["singing_threshold"]
    for cid in CFG["clips"]:
        d = clip_dir(cid)
        asr = load_json(os.path.join(d, "asr_dialogue.json"))
        diar = load_json(os.path.join(d, "diar_fixed.json"))
        events = load_json(os.path.join(d, "events.json"))
        excl, reg = diar["exclusive"], diar["regular"]
        media_end = sf.info(os.path.join(d, "original_16k.wav")).duration

        def whisper_flag(s):
            return (s["no_speech_prob"] > 0.6 and s["avg_logprob"] < -1.0) or s["compression_ratio"] > 2.4

        words = [dict(w) for s in asr if not whisper_flag(s) for w in s["words"] if w["start"] is not None]

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

        for w in words:
            w["spk"] = speaker_of(w["start"], w["end"])

        # Smooth speaker flips: a short run between two runs of the same other speaker takes that speaker.
        runs, i = [], 0
        while i < len(words):
            j = i
            while j + 1 < len(words) and words[j + 1]["spk"] == words[i]["spk"]:
                j += 1
            runs.append([i, j, words[i]["spk"]])
            i = j + 1
        flips = 0
        for k in range(1, len(runs) - 1):
            i0, i1, spk = runs[k]
            if runs[k - 1][2] == runs[k + 1][2] != spk and words[i1]["end"] - words[i0]["start"] < P["flip_s"]:
                for t in range(i0, i1 + 1):
                    words[t]["spk"] = runs[k - 1][2]
                runs[k][2] = runs[k - 1][2]
                flips += 1

        segs, cur = [], None
        for w in words:
            sentence_end = cur is not None and cur["text"].rstrip().endswith((".", "?", "!", "…"))
            short = cur is not None and cur["end"] - cur["start"] < P["min_seg_s"]
            if (cur and w["spk"] == cur["speaker"] and w["start"] - cur["end"] < P["merge_gap_s"]
                    and (not sentence_end or short) and w["end"] - cur["start"] <= P["max_seg_s"]):
                cur["end"] = w["end"]
                cur["text"] += w["word"]
                cur["ps"].append(w["p"])
            else:
                if cur:
                    segs.append(cur)
                cur = {"speaker": w["spk"], "start": w["start"], "end": w["end"], "text": w["word"], "ps": [w["p"]]}
        if cur:
            segs.append(cur)

        # Merge remaining fragments into a same-speaker neighbour within fragment_gap_s.
        merged_fragments, changed = 0, True
        while changed:
            changed = False
            for i, s in enumerate(segs):
                if s["end"] - s["start"] >= P["min_seg_s"]:
                    continue
                prev = segs[i - 1] if i > 0 else None
                nxt = segs[i + 1] if i + 1 < len(segs) else None
                if (prev and prev["speaker"] == s["speaker"] and s["start"] - prev["end"] < P["fragment_gap_s"]
                        and s["end"] - prev["start"] <= P["max_seg_s"]):
                    prev["end"], prev["text"], prev["ps"] = s["end"], prev["text"] + " " + s["text"], prev["ps"] + s["ps"]
                elif (nxt and nxt["speaker"] == s["speaker"] and nxt["start"] - s["end"] < P["fragment_gap_s"]
                      and nxt["end"] - s["start"] <= P["max_seg_s"]):
                    nxt["start"], nxt["text"], nxt["ps"] = s["start"], s["text"] + " " + nxt["text"], s["ps"] + nxt["ps"]
                else:
                    continue
                del segs[i]
                merged_fragments += 1
                changed = True
                break

        skipped = {}
        for idx, s in enumerate(segs):
            s["idx"] = idx
            s["text"] = " ".join(s["text"].split())
            ps = s.pop("ps")
            s["mean_p"] = round(sum(ps) / max(1, len(ps)), 3)
            dur = max(1e-6, s["end"] - s["start"])
            other = sum(max(0.0, min(s["end"], b) - max(s["start"], a)) for a, b, spk in reg if spk != s["speaker"])
            s["is_overlap"] = other / dur > 0.2
            sung = sum(max(0.0, min(s["end"], f["end"]) - max(s["start"], f["start"]))
                       for f in events if f.get("Singing", 0) >= sing_thr)
            s["singing_cover"] = round(min(1.0, sung / dur), 2)
            reason = None
            if s["singing_cover"] > 0.5:
                reason = "singing"
            elif s["mean_p"] < P["min_mean_p"]:
                reason = "low_confidence"
            s["skip_reason"] = reason
            if reason:
                skipped[reason] = skipped.get(reason, 0) + 1
        for s in segs:
            later = [o["start"] for o in segs if o["start"] >= s["end"] and o is not s]
            nxt = min(later) if later else media_end
            s["hard_limit"] = round(nxt - 0.12 - s["start"], 3)
            s["available"] = round(min(s["hard_limit"], 1.25 * (s["end"] - s["start"])), 3)
        speakers = {}
        for s in segs:
            speakers[s["speaker"]] = speakers.get(s["speaker"], 0.0) + s["end"] - s["start"]
        save_json(os.path.join(d, "segments.json"), {"segments": segs, "speakers": speakers})
        durs = sorted(s["end"] - s["start"] for s in segs)
        RESULT[cid] = {"segments": len(segs), "dubbable": len(segs) - sum(skipped.values()), "skipped": skipped,
                       "speaker_flips_smoothed": flips, "fragments_merged": merged_fragments,
                       "segments_under_1s": sum(1 for x in durs if x < 1.0),
                       "median_segment_s": round(durs[len(durs) // 2], 2) if durs else None,
                       "speech_s_per_speaker": {k: round(v, 1) for k, v in sorted(speakers.items())}}
'''

SOURCES["refs"] = r'''
def main():
    import numpy as np, soundfile as sf
    for cid in CFG["clips"]:
        d = clip_dir(cid)
        segs = load_json(os.path.join(d, "segments.json"))["segments"]
        dia, sr = sf.read(os.path.join(d, "dialogue_48k.wav"), dtype="float32")
        refs = {}
        for spk in sorted({s["speaker"] for s in segs if not s["skip_reason"]}):
            cands = [s for s in segs if s["speaker"] == spk and not s["skip_reason"] and not s["is_overlap"]
                     and 1.5 <= s["end"] - s["start"] <= 12.0]
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
                refs[spk] = {"path": None, "seconds": round(total, 1)}
                continue
            ref = np.concatenate(parts)
            ref = np.clip(ref * (0.1 / (np.sqrt(np.mean(ref ** 2)) + 1e-9)), -0.99, 0.99)
            path = os.path.join(d, f"ref_{spk}.wav")
            sf.write(path, ref, sr)
            refs[spk] = {"path": path, "seconds": round(total, 1), "segments": used}
        save_json(os.path.join(d, "references.json"), refs)
        RESULT[cid] = {k: v["seconds"] for k, v in refs.items()}
'''

SOURCES["tts"] = r'''
def main():
    import subprocess
    import numpy as np, soundfile as sf, torch
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    RESULT["versions"] = versions("chatterbox-tts", "torch")
    model = ChatterboxMultilingualTTS.from_pretrained(device="cuda")
    sr, ff, cw = model.sr, CFG["ffmpeg"], CFG["cfg_weight"]
    default_conds = model.conds

    def trim(a):
        frame = int(0.01 * sr)
        n = len(a) // frame
        if n == 0:
            return a
        env = np.abs(a[:n * frame]).reshape(n, frame).max(axis=1)
        idx = np.where(env > (float(np.abs(a).max()) + 1e-9) * 10 ** (-35 / 20))[0]
        if len(idx) == 0:
            return a
        pad = int(0.04 * sr)
        return a[max(0, idx[0] * frame - pad):min(len(a), (idx[-1] + 1) * frame + pad)]

    def synth(text, seed):
        torch.manual_seed(seed)
        t = time.time()
        wav = model.generate(text, language_id="en", cfg_weight=cw, exaggeration=0.5)
        torch.cuda.synchronize()
        a = wav.squeeze().float().cpu().numpy()
        return a, trim(a), time.time() - t

    def use_voice(v):
        if v.get("path"):
            model.prepare_conditionals(v["path"], exaggeration=0.5)  # once per actor; re-prepared on every switch
        else:
            model.conds = default_conds

    if CFG["mode"] == "audition":
        os.makedirs(CFG["bank_dir"], exist_ok=True)
        model.conds = default_conds
        _, at, _ = synth(CFG["bank_text"], 1)
        base = os.path.join(CFG["bank_dir"], "bank_a.wav")
        sf.write(base, at, sr)
        bank = {"bank_a": base}
        for name, factor in (("bank_b", 0.86), ("bank_c", 1.14)):  # distinct timbres from the synthetic default voice
            out = os.path.join(CFG["bank_dir"], f"{name}.wav")
            subprocess.run([ff, "-v", "error", "-y", "-i", base, "-af",
                            f"aresample=48000,asetrate={int(48000 * factor)},aresample={sr},atempo={1 / factor:.4f}", out],
                           check=True)
            bank[name] = out
        for cid in CFG["clips"]:
            d = clip_dir(cid)
            refs = load_json(os.path.join(d, "references.json"))
            free, voices = list(bank), {}
            for spk, r in sorted(refs.items()):
                if r.get("path"):
                    voices[spk] = {"path": r["path"], "source": "cloned"}
                else:
                    name = free.pop(0) if free else "bank_a"
                    voices[spk] = {"path": bank[name], "source": f"fallback_{name}"}
            for spk, v in voices.items():
                use_voice(v)
                chars = dur = 0.0
                for i, text in enumerate(CFG["audition_sentences"]):
                    _, at, _ = synth(text, 500 + i)
                    chars += len(text)
                    dur += len(at) / sr
                v["cps"] = round(chars / max(dur, 1e-3), 2)
            save_json(os.path.join(d, "voices.json"), voices)
            RESULT[cid] = {k: {"source": v["source"], "cps": v["cps"]} for k, v in voices.items()}
        return

    rnd = CFG.get("round", 0)
    for cid in CFG["clips"]:
        d = clip_dir(cid)
        segs = load_json(os.path.join(d, "segments.json"))["segments"]
        tr = load_json(os.path.join(d, "translations.json"))
        voices = load_json(os.path.join(d, "voices.json"))
        only = set(map(str, CFG["only"].get(cid, []))) if CFG["mode"] == "round" else None
        outdir = os.path.join(d, "tts")
        os.makedirs(outdir, exist_ok=True)
        res_path = os.path.join(d, "tts.json")
        res = load_json(res_path) if os.path.exists(res_path) else {}
        by_spk = {}
        for s in segs:
            if s["skip_reason"] or (only is not None and str(s["idx"]) not in only):
                continue
            by_spk.setdefault(s["speaker"], []).append(s)
        gen = dur = raw = 0.0
        n = errors = 0
        for spk, items in by_spk.items():
            use_voice(voices[spk])
            for s in items:
                text = (tr.get(str(s["idx"])) or "").strip()
                if not text:
                    continue
                try:
                    a, at, el = synth(text, 10000 + s["idx"] + 1000 * rnd)
                except Exception:
                    errors += 1
                    continue
                path = os.path.join(outdir, f"seg_{s['idx']:04d}_r{rnd}.wav")
                sf.write(path, at, sr)
                res[str(s["idx"])] = {"path": path, "dur": round(len(at) / sr, 3), "raw_dur": round(len(a) / sr, 3),
                                      "gen_s": round(el, 3), "text": text, "round": rnd}
                gen += el
                dur += len(at) / sr
                raw += len(a) / sr
                n += 1
        save_json(res_path, res)
        r = speed(dur, gen)
        r.update({"segments": n, "errors": errors, "silence_trimmed_s": round(raw - dur, 2)})
        RESULT[cid] = r
'''

SOURCES["opus"] = r'''
def main():
    import torch
    from transformers import MarianMTModel, MarianTokenizer
    name = "Helsinki-NLP/opus-mt-tr-en"
    tok = MarianTokenizer.from_pretrained(name)
    model = MarianMTModel.from_pretrained(name).to("cuda").eval()
    for cid in CFG["clips"]:
        d = clip_dir(cid)
        tr = load_json(os.path.join(d, "translations.json"))
        segs = {str(s["idx"]): s for s in load_json(os.path.join(d, "segments.json"))["segments"]}
        missing = [k for k, v in tr.items() if not v]
        if missing:
            batch = tok([segs[k]["text"] for k in missing], return_tensors="pt", padding=True).to("cuda")
            with torch.no_grad():
                out = model.generate(**batch, max_new_tokens=128)
            for k, text in zip(missing, tok.batch_decode(out, skip_special_tokens=True)):
                tr[k] = " ".join(text.split())
            save_json(os.path.join(d, "translations.json"), tr)
        RESULT[cid] = {"filled_by_opus_mt": len(missing)}
'''

SOURCES["qc"] = r'''
def main():
    import numpy as np, torch
    from pyannote.audio import Model, Inference
    model = Model.from_pretrained("pyannote/wespeaker-voxceleb-resnet34-LM", token=os.environ.get("HF_TOKEN"))
    inf = Inference(model, window="whole", device=torch.device("cuda"))

    def emb(path):
        wav = ffmpeg_mono(path, 16000)
        v = np.asarray(inf({"waveform": torch.from_numpy(wav)[None], "sample_rate": 16000})).reshape(-1)
        return v / (np.linalg.norm(v) + 1e-9)

    for cid in CFG["clips"]:
        d = clip_dir(cid)
        segs = load_json(os.path.join(d, "segments.json"))["segments"]
        tts = load_json(os.path.join(d, "tts.json"))
        per = {}
        for s in segs:
            item = tts.get(str(s["idx"]))
            if item and item["dur"] >= 1.0:
                per.setdefault(s["speaker"], []).append(emb(item["path"]))
        r, cents = {}, {}
        for spk, es in per.items():
            E = np.stack(es)
            c = E.mean(0)
            c = c / (np.linalg.norm(c) + 1e-9)
            cents[spk] = c
            to_c = E @ c
            r[spk] = {"n": len(es), "cos_to_own_centroid_mean": round(float(to_c.mean()), 3),
                      "cos_to_own_centroid_p10": round(float(np.percentile(to_c, 10)), 3),
                      "below_0_6": int((to_c < 0.6).sum())}
        names = sorted(cents)
        r["between_speakers"] = {f"{a}~{b}": round(float(cents[a] @ cents[b]), 3)
                                 for i, a in enumerate(names) for b in names[i + 1:]}
        RESULT[cid] = r
'''

SOURCES["mix"] = r'''
def main():
    import subprocess
    import numpy as np, soundfile as sf
    ff, SR = CFG["ffmpeg"], 48000
    os.makedirs(CFG["audio_out"], exist_ok=True)
    check = []

    def load_clip(path, tempo=None):
        return ffmpeg_mono(path, SR, af=f"atempo={tempo:.4f}" if tempo else None)

    def fade(a, ms_in=15, ms_out=15):
        n_in, n_out = min(len(a) // 2, int(SR * ms_in / 1000)), min(len(a) // 2, int(SR * ms_out / 1000))
        if n_in > 0:
            a[:n_in] *= np.linspace(0, 1, n_in, dtype=np.float32)
        if n_out > 0:
            a[-n_out:] *= np.linspace(1, 0, n_out, dtype=np.float32)
        return a

    def smooth(x, ms=50):
        k = max(1, int(SR * ms / 1000))
        c = np.cumsum(np.concatenate([[0.0], x.astype(np.float64)]))
        idx = np.arange(len(x))
        lo, hi = np.clip(idx - k // 2, 0, len(x)), np.clip(idx + k // 2 + 1, 0, len(x))
        return ((c[hi] - c[lo]) / (hi - lo)).astype(np.float32)

    for cid in CFG["clips"]:
        d = clip_dir(cid)
        segs = load_json(os.path.join(d, "segments.json"))["segments"]
        tts = load_json(os.path.join(d, "tts.json"))
        meta = load_json(os.path.join(d, "translate_meta.json"))
        bg, _ = sf.read(os.path.join(d, "background_48k.wav"), dtype="float32")
        dia, _ = sf.read(os.path.join(d, "dialogue_48k.wav"), dtype="float32")
        n = min(len(bg), len(dia))
        bg, dia = bg[:n], dia[:n]
        track = np.zeros(n, np.float32)
        dub_mask, keep_mask = np.zeros(n, np.float32), np.zeros(n, np.float32)
        fit = {"none": 0, "tempo_le_1_10": 0, "tempo_gt_1_10": 0, "overflow": 0, "truncated": 0}
        rows, placed_text, ratios = [], [], []
        for s in segs:
            m = meta.get(str(s["idx"]), {})
            item = tts.get(str(s["idx"]))
            if s["skip_reason"] or not item:
                keep_mask[max(0, int((s["start"] - 0.05) * SR)):min(n, int((s["end"] + 0.05) * SR))] = 1.0
                rows.append((s, m, None, s["skip_reason"] or "no_audio", None))
                continue
            avail, hard = max(0.2, s["available"]), max(0.2, s["hard_limit"])
            r = item["dur"] / avail
            ratios.append(r)
            if r <= 1.0:
                tempo, method = None, "none"
            elif r <= 1.25:
                tempo, method = r, ("tempo_le_1_10" if r <= 1.10 else "tempo_gt_1_10")
            else:
                tempo = 1.25
                method = "overflow" if item["dur"] / 1.25 <= hard else "truncated"
            a = load_clip(item["path"], tempo)
            if method == "truncated":
                a = fade(a[:int(hard * SR)], ms_out=150)
            fit[method] += 1
            i0 = int(s["start"] * SR)
            i1 = min(n, i0 + len(a))
            src = dia[i0:max(i0 + 1, int(s["end"] * SR))]
            gain = (np.sqrt(np.mean(src ** 2)) + 1e-6) / (np.sqrt(np.mean(a ** 2)) + 1e-6)
            a = fade(a * float(np.clip(gain, 10 ** (-12 / 20), 10 ** (12 / 20))))
            track[i0:i1] += a[:i1 - i0]
            dub_mask[max(0, int((s["start"] - 0.1) * SR)):min(n, i1 + int(0.1 * SR))] = 1.0
            placed_text.append(item["text"])
            rows.append((s, m, item, method, round(r, 2)))
        dub_mask, keep_mask = smooth(dub_mask), smooth(keep_mask)
        dia_gain = keep_mask + (1.0 - keep_mask) * (1.0 - dub_mask) * 10 ** (-6 / 20)  # kept spans 0 dB, lay-back -6 dB
        mix = bg + (track + dia * dia_gain)[:, None]
        raw = os.path.join(d, "dub_separated.wav")
        sf.write(raw, mix, SR)
        subprocess.run([ff, "-v", "error", "-y", "-i", raw, "-af", "loudnorm=I=-16:TP=-2:LRA=11", "-c:a", "aac",
                        "-b:a", "192k", os.path.join(CFG["audio_out"], f"{cid}_dub.m4a")], check=True)
        check.append({"name": cid, "path": raw, "ref_text": " ".join(placed_text)})
        dubbed = max(1, len(ratios))
        RESULT[cid] = {"dubbed": len(ratios), "kept_original": sum(1 for r in rows if r[2] is None), "fit": fit,
                       "ratio_median": round(float(np.median(ratios)), 2) if ratios else None,
                       "share_over_1_10": round((fit["tempo_gt_1_10"] + fit["overflow"] + fit["truncated"]) / dubbed, 3),
                       "share_truncated": round(fit["truncated"] / dubbed, 3),
                       "share_overflow": round(fit["overflow"] / dubbed, 3)}
        clean = lambda x: str(x).replace("|", "/").replace("\n", " ")
        lines = [f"# Review — {cid} (S3b)", "",
                 "| # | Speaker | Start s | Turkish | English | Budget | Chars | Translator | Rewrites | gen/avail | Fit / skip |",
                 "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for s, m, item, method, ratio in rows:
            en = item["text"] if item else m.get("final", "")
            lines.append(f"| {s['idx']} | {s['speaker']} | {s['start']:.1f} | {clean(s['text'])} | {clean(en)} | "
                         f"{m.get('budget', '')} | {len(en)} | {m.get('chosen', '')} | {m.get('rewrites', 0)} | "
                         f"{ratio if ratio is not None else ''} | {method} |")
        with open(os.path.join(CFG["out_dir"], f"review_{cid}.md"), "w") as f:
            f.write("\n".join(lines))
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
CLIPS_READY: list[str] = []
FFMPEG = "ffmpeg"


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
    if ok:
        ok = run([*uv, "pip", "install", "--python", py, *spec["pkgs"]], log, timeout=2400) == 0
        if not ok and spec.get("fallback_pkgs"):
            note = "used fallback packages"
            ok = run([*uv, "pip", "install", "--python", py, *spec["fallback_pkgs"]], log, timeout=2400) == 0
    RESULTS["install"][name] = {"ok": ok, "seconds": round(time.time() - t, 1), "venv_gb": du_gb(venv), "note": note}
    INSTALLED[name] = ok
    save()
    return ok


def stage(name: str, family: str, cfg: dict, extra_env: dict | None = None, timeout: int = 5400,
          program: str | None = None) -> dict:
    if not install(family):
        res = {"ok": False, "error": f"install failed (logs/install_{family}.log)"}
        RESULTS["stages"][name] = res
        save()
        return res
    path = BENCH / f"stage_{name}.py"
    path.write_text(HEAD + SOURCES[program or name] + TAIL)
    result_path = WORK_OUT / f"stage_{name}.json"
    full = {**cfg, "stage": name, "result_path": str(result_path), "clips_dir": str(CLIPS_DIR), "ffmpeg": FFMPEG,
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
    print(f"[s3b] {name}: ok={res.get('ok')} wall={wall}s peak={peak}MB {str(res.get('error') or '')[:200]}", flush=True)
    return res


def ffmpeg_convert(src: Path, dst: Path, rate: int, channels: int) -> None:
    subprocess.run([FFMPEG, "-v", "error", "-y", "-i", str(src), "-ac", str(channels), "-ar", str(rate), str(dst)],
                   check=True)


# ---------------------------------------------------------------- LLM steps (Ollama on the host GPU)

class Ollama:
    def __init__(self) -> None:
        self.log = LOGS / "ollama.log"
        self.env = dict(ENV, OLLAMA_MODELS=str(SCRATCH / "ollama"), OLLAMA_HOST="127.0.0.1:11434")
        self.server: subprocess.Popen | None = None
        self.tags: dict[str, str] = {}

    def start(self) -> None:
        if not shutil.which("ollama"):
            if not shutil.which("zstd"):
                run(["bash", "-lc", "apt-get update -qq && apt-get install -y -qq zstd"], self.log, timeout=900)
            run(["bash", "-lc", "curl -fsSL https://ollama.com/install.sh | sh"], self.log, timeout=1200)
        if not shutil.which("ollama"):
            raise RuntimeError("ollama install failed")
        self.server = subprocess.Popen(["ollama", "serve"], stdout=open(LOGS / "ollama_serve.log", "a"),
                                       stderr=subprocess.STDOUT, env=self.env)
        for _ in range(60):
            try:
                self.call("/api/tags")
                return
            except Exception:
                time.sleep(1)

    def stop(self) -> None:
        for tag in self.tags.values():
            try:
                self.call("/api/generate", {"model": tag, "prompt": "", "keep_alive": 0})
            except Exception:
                pass
        if self.server:
            self.server.terminate()
            self.server = None

    def call(self, path: str, payload: dict | None = None, timeout: int = 600) -> dict:
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(f"http://127.0.0.1:11434{path}", data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())

    def pull(self, key: str) -> str:
        for tag in TRANSLATORS[key]:
            if run(["ollama", "pull", tag], self.log, env=self.env, timeout=1800) == 0:
                self.tags[key] = tag
                return tag
        raise RuntimeError(f"pull failed for {key}")

    def generate(self, key: str, prompt: str) -> str:
        payload = {"model": self.tags[key], "prompt": prompt, "stream": False, "keep_alive": "5m",
                   "options": {"temperature": 0.2}}
        if key == "qwen3":
            payload["think"] = False
        try:
            out = self.call("/api/generate", payload).get("response", "")
        except urllib.error.HTTPError:
            payload.pop("think", None)
            payload["prompt"] = prompt + " /no_think"
            out = self.call("/api/generate", payload).get("response", "")
        return re.sub(r"<think>.*?</think>", "", out, flags=re.S)


def clean_line(text: str) -> str:
    text = text.strip()
    if text.lower().startswith("english:"):
        text = text[8:].strip()
    text = text.strip().strip('"“”\'‘’').strip()
    return text


def problem(src: str, en: str) -> str | None:
    """Translation validation (SPEC §8.14): reject empty output and commentary instead of a line."""
    if not en:
        return "empty"
    if "\n" in en:
        return "multiline"
    low = en.lower()
    if re.search(r"(^|\s)[*•]\s", en) or re.search(r"(^|\n)\s*-\s", en):
        return "bullets"
    if any(p in low for p in ("translat", "could mean", "context", "literally", "this phrase", "the phrase")):
        return "commentary"
    if len(en) > 2.0 * len(src) + 15:
        return "too_long_vs_source"
    return None


def translate_all() -> None:
    llm, r = Ollama(), {}
    t0 = time.time()
    try:
        llm.start()
        for key in TRANSLATORS:
            llm.pull(key)
        r["models"] = dict(llm.tags)
        outputs: dict = {key: {} for key in TRANSLATORS}
        budgets: dict = {}
        for cid in CLIPS_READY:
            d = CLIPS_DIR / cid
            segs = [s for s in json.loads((d / "segments.json").read_text())["segments"] if not s["skip_reason"]]
            voices = json.loads((d / "voices.json").read_text())
            all_segs = json.loads((d / "segments.json").read_text())["segments"]
            for s in segs:
                cps = voices[s["speaker"]]["cps"]
                budgets[(cid, s["idx"])] = max(8, int(s["available"] * cps * 0.95))
            for key in TRANSLATORS:
                for s in segs:
                    budget = budgets[(cid, s["idx"])]
                    if key == "translategemma":
                        prompt = PROMPT_TRANSLATEGEMMA.format(budget=budget, text=s["text"])
                    else:
                        prev = [o["text"] for o in all_segs if o["idx"] < s["idx"]][-2:]
                        prompt = PROMPT_QWEN_TRANSLATE.format(budget=budget, context=" / ".join(prev) or "(none)",
                                                              text=s["text"])
                    raw = llm.generate(key, prompt)
                    en = clean_line(" ".join(raw.split()) if "\n" not in raw.strip() else raw.strip())
                    outputs[key][(cid, s["idx"])] = (en, problem(s["text"], en))
        stats = {}
        for key, outs in outputs.items():
            total = max(1, len(outs))
            within = sum(1 for (cid, idx), (en, p) in outs.items() if not p and len(en) <= budgets[(cid, idx)])
            rejects: dict = {}
            for en, p in outs.values():
                if p:
                    rejects[p] = rejects.get(p, 0) + 1
            stats[key] = {"segments": len(outs), "within_budget": round(within / total, 3), "rejected": rejects,
                          "mean_chars_over_budget": round(sum(max(0, len(en) - budgets[k]) for k, (en, p) in outs.items())
                                                          / total, 1)}
        r["translator_stats"] = stats
        primary = max(stats, key=lambda k: stats[k]["within_budget"] - sum(stats[k]["rejected"].values()) / max(1, stats[k]["segments"]))
        other = [k for k in TRANSLATORS if k != primary][0]
        r["primary"] = primary
        for cid in CLIPS_READY:
            d = CLIPS_DIR / cid
            segs = [s for s in json.loads((d / "segments.json").read_text())["segments"] if not s["skip_reason"]]
            final, meta = {}, {}
            for s in segs:
                k = (cid, s["idx"])
                en_p, prob_p = outputs[primary][k]
                en_o, prob_o = outputs[other][k]
                if not prob_p:
                    final[str(s["idx"])], chosen = en_p, primary
                elif not prob_o:
                    final[str(s["idx"])], chosen = en_o, other
                else:
                    final[str(s["idx"])], chosen = "", "opus-mt"
                meta[str(s["idx"])] = {"budget": budgets[k], "chosen": chosen, "rewrites": 0,
                                       "rejected": {primary: prob_p, other: prob_o}}
            (d / "translations.json").write_text(json.dumps(final, ensure_ascii=False, indent=1))
            (d / "translate_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
            r[cid] = {"segments": len(segs), "chosen": {c: sum(1 for m in meta.values() if m["chosen"] == c)
                                                        for c in (primary, other, "opus-mt")}}
        r["ok"] = True
    except Exception as e:
        r["ok"] = False
        r["error"] = f"{type(e).__name__}: {e}"[:800]
    finally:
        llm.stop()
    r["wall_s"] = round(time.time() - t0, 1)
    RESULTS["stages"]["translate"] = r
    save()
    print(f"[s3b] translate: ok={r.get('ok')} primary={r.get('primary')} {r.get('error', '')}", flush=True)


def rewrite_round(rnd: int) -> dict[str, list[int]]:
    """SPEC §9 rule 3: one batched LLM pass over segments with gen/available > 1.10."""
    llm, r, changed = Ollama(), {}, {}
    t0 = time.time()
    try:
        llm.start()
        llm.pull(REWRITER)
        for cid in CLIPS_READY:
            d = CLIPS_DIR / cid
            segs = {str(s["idx"]): s for s in json.loads((d / "segments.json").read_text())["segments"]}
            tts = json.loads((d / "tts.json").read_text())
            tr = json.loads((d / "translations.json").read_text())
            meta = json.loads((d / "translate_meta.json").read_text())
            voices = json.loads((d / "voices.json").read_text())
            need = [k for k, item in tts.items() if item["dur"] / max(0.2, segs[k]["available"]) > 1.10]
            done = []
            for k in need:
                s = segs[k]
                budget = max(8, int(s["available"] * voices[s["speaker"]]["cps"] * 0.9))
                en = clean_line(llm.generate(REWRITER, PROMPT_QWEN_REWRITE.format(budget=budget, src=s["text"], en=tr[k])))
                if not problem(s["text"], en) and len(en) < len(tr[k]):
                    tr[k] = en
                    meta[k]["rewrites"] = meta[k].get("rewrites", 0) + 1
                    meta[k]["budget"] = budget
                    done.append(int(k))
            (d / "translations.json").write_text(json.dumps(tr, ensure_ascii=False, indent=1))
            (d / "translate_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
            changed[cid] = done
            r[cid] = {"over_1_10": len(need), "rewritten": len(done)}
        r["ok"] = True
    except Exception as e:
        r["ok"] = False
        r["error"] = f"{type(e).__name__}: {e}"[:800]
    finally:
        llm.stop()
    r["wall_s"] = round(time.time() - t0, 1)
    RESULTS["stages"][f"rewrite_{rnd}"] = r
    save()
    print(f"[s3b] rewrite_{rnd}: {json.dumps({k: v for k, v in r.items() if k in CLIPS_READY})}", flush=True)
    return changed


def write_summary() -> None:
    st = RESULTS["stages"]
    lines = ["# Spike S3b results", "", f"Started {RESULTS['started']}; finished {RESULTS.get('finished')}", "",
             "| Stage | OK | Wall s | Peak GPU MB | Error |", "| --- | --- | --- | --- | --- |"]
    for name, res in st.items():
        lines.append(f"| {name} | {res.get('ok')} | {res.get('wall_s', '')} | {res.get('nvidia_smi_peak_mb', '')} | "
                     f"{str(res.get('error') or '')[:120]} |")
    lines += ["", "## S3 → S3b", "",
              "| Clip | Speakers auto → fixed (S3) | > 1.10× S3 → S3b | Truncated S3 → S3b | Overflow S3b | Kept original |",
              "| --- | --- | --- | --- | --- | --- |"]
    for cid in CLIPS_READY:
        base, mix = S3_BASELINE[cid], st.get("mix", {}).get(cid, {})
        auto = st.get("diar", {}).get(f"{cid}_auto", {}).get("speakers")
        fixed = st.get("diar", {}).get(f"{cid}_fixed", {}).get("speakers")
        lines.append(f"| {cid} | {auto} → {fixed} ({base['speakers']}) | {base['over_1_10']:.0%} → "
                     f"{mix.get('share_over_1_10', float('nan')):.0%} | {base['truncated']:.0%} → "
                     f"{mix.get('share_truncated', float('nan')):.0%} | {mix.get('share_overflow', float('nan')):.0%} | "
                     f"{mix.get('kept_original')} |")
    lines += ["", "## Per clip", ""]
    for cid in CLIPS_READY:
        lines.append(f"### {cid}")
        for name, res in st.items():
            for k in [k for k in res if k == cid or k.startswith(cid + "_")]:
                lines.append(f"- {name} `{k}`: {json.dumps(res[k], ensure_ascii=False)[:500]}")
        lines.append("")
    lines += [f"Translators: {json.dumps(st.get('translate', {}).get('translator_stats'), ensure_ascii=False)}",
              f"Primary translator: {st.get('translate', {}).get('primary')}", "",
              "Listen: audio/<clip>_dub.m4a. Read: review_<clip>.md. Private evaluation only (docs/footage.md)."]
    (WORK_OUT / "summary.md").write_text("\n".join(lines))


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
        print("[s3b] No internet in this session: stopping.", flush=True)
        return
    if REQUIRE_HF_TOKEN and not token:
        print("[s3b] HF_TOKEN secret not available (start this run from the Kaggle editor): stopping.", flush=True)
        return
    missing = [c for c in CLIP_IDS if c not in found]
    if missing:
        print(f"[s3b] Missing inputs {missing}; attach the voxshift-s3-clips dataset: stopping.", flush=True)
        return
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "uv"], check=True)

    for cid in CLIP_IDS:
        d = CLIPS_DIR / cid
        d.mkdir(parents=True, exist_ok=True)
        src = Path(found[cid])
        ffmpeg_convert(src, d / "original_44k.wav", 44100, 2)
        ffmpeg_convert(src, d / "original_16k.wav", 16000, 1)
        CLIPS_READY.append(cid)

    stage("sep", "sep", {})
    for cid in CLIPS_READY:
        d = CLIPS_DIR / cid
        ffmpeg_convert(d / "dialogue_44k.wav", d / "dialogue_16k.wav", 16000, 1)
        ffmpeg_convert(d / "dialogue_44k.wav", d / "dialogue_48k.wav", 48000, 1)
        ffmpeg_convert(d / "background_44k.wav", d / "background_48k.wav", 48000, 2)
    stage("tag", "tag", TAGGING)

    code = ("import os, nvidia.cublas.lib, nvidia.cudnn.lib; print(os.path.dirname(nvidia.cublas.lib.__file__)"
            " + ':' + os.path.dirname(nvidia.cudnn.lib.__file__))")
    asr_env: dict = {}
    if install("asr"):
        out = subprocess.run([str(VENVS / "asr" / "bin" / "python"), "-c", code], capture_output=True, text=True, env=ENV)
        if out.stdout.strip():
            asr_env = {"LD_LIBRARY_PATH": f"{out.stdout.strip()}:{os.environ.get('LD_LIBRARY_PATH', '')}"}
    stage("asr", "asr", {"mode": "source", "asr_model": ASR_MODEL}, extra_env=asr_env)
    stage("diar", "diar", {"num_speakers": NUM_SPEAKERS}, extra_env={"HF_TOKEN": token or ""})
    stage("build", "dsp", {"build": BUILD, "singing_threshold": TAGGING["singing_threshold"]})
    stage("refs", "dsp", {"ref_seconds": REF_SECONDS})
    stage("audition", "tts", {"mode": "audition", "cfg_weight": CFG_WEIGHT, "bank_dir": str(SCRATCH / "bank"),
                              "bank_text": BANK_TEXT, "audition_sentences": AUDITION_SENTENCES}, program="tts")
    translate_all()
    stage("opus", "opus", {})
    stage("tts", "tts", {"mode": "main", "cfg_weight": CFG_WEIGHT}, timeout=7200)
    for rnd in range(1, REWRITE_ROUNDS + 1):
        changed = rewrite_round(rnd)
        if not any(changed.values()):
            break
        stage(f"tts_round{rnd}", "tts", {"mode": "round", "round": rnd, "only": changed, "cfg_weight": CFG_WEIGHT},
              program="tts")
    stage("qc", "diar", {}, extra_env={"HF_TOKEN": token or ""})
    check_list = str(SCRATCH / "check_list.json")
    stage("mix", "dsp", {"audio_out": str(AUDIO_OUT), "out_dir": str(WORK_OUT), "check_list": check_list})
    if Path(check_list).exists():
        stage("check", "asr", {"mode": "check", "asr_model": ASR_MODEL, "check_list": check_list},
              extra_env=asr_env, program="asr")

    RESULTS["disk"] = {"scratch_used_gb": du_gb(SCRATCH), "output_gb": du_gb(WORK_OUT)}
    RESULTS["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save()
    write_summary()
    print((WORK_OUT / "summary.md").read_text(), flush=True)


if __name__ == "__main__":
    main()
