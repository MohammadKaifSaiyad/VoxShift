#!/usr/bin/env python3
"""VoxShift spike S1 — runs inside one Kaggle GPU session (Linux + CUDA).

Throwaway Phase 0 spike (docs/SPEC.md §17, docs/feasibility.md §10); not product code.
Installs each model family in its own uv venv (one model family per process, SPEC §6),
synthesizes all test audio inside the session (no user data is uploaded), and measures
load time, speed and peak GPU memory, plus a few quality signals against known ground
truth. Results go to /kaggle/working/s1/ (results.json, summary.md, logs/, audio_samples/).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

WORK = Path(os.environ.get("S1_WORK", "/kaggle/working")) / "s1"
SCRATCH = Path(os.environ.get("S1_SCRATCH", "/tmp/s1"))
LOGS = WORK / "logs"
SAMPLES = WORK / "audio_samples"
AUDIO = SCRATCH / "audio"
VENVS = SCRATCH / "venvs"
BENCH = SCRATCH / "bench"
PY_VERSION = "3.11"
REQUIRE_HF_TOKEN = False  # True: stop within a minute if the HF_TOKEN secret is missing (only diarization needs it)
ONLY: list[str] = []  # e.g. ["diar"] to rerun selected benches; TTS and test audio always run

ENV = dict(os.environ)
ENV.update({
    "HF_HOME": str(SCRATCH / "hf"),
    "TORCH_HOME": str(SCRATCH / "torch"),
    "UV_CACHE_DIR": str(SCRATCH / "uv-cache"),
    "UV_LINK_MODE": "hardlink",
    "PYTHONUNBUFFERED": "1",
    "TOKENIZERS_PARALLELISM": "false",
    "CUDA_VISIBLE_DEVICES": "0",  # benchmark on one GPU; the second T4 is recorded but unused
})

RESULTS: dict = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "env": {}, "install": {}, "bench": {}}

# Synthetic test script: original sentences with names and digits (alignment edge cases).
TR = [
    "Merhaba, benim adım Ayşe ve bugün size kısa bir hikâye anlatacağım.",
    "Bu hikâye, 1990 yılında İstanbul'da küçük bir mahallede geçiyor.",
    "O yıllarda herkes birbirini tanır, akşamları kapı önünde sohbet ederdi.",
    "Mehmet amca her sabah fırından taze ekmek alır, komşulara dağıtırdı.",
    "Bir gün mahalleye yeni bir aile taşındı ve herkes çok meraklandı.",
    "Ailenin en küçük kızı Zeynep, ilk gün kimseyle konuşmak istemedi.",
    "Ama ertesi gün parkta diğer çocuklarla birlikte oyun oynamaya başladı.",
    "Akşam olunca annesi onu eve çağırdı: Zeynep, yemek hazır, hadi gel!",
    "Zeynep koşarak geldi ve masada 3 tabak dolusu börek olduğunu gördü.",
    "O akşam bütün komşular toplandı ve geç saatlere kadar sohbet ettiler.",
    "Yıllar geçti, mahalle değişti, ama o günlerin sıcaklığı hiç unutulmadı.",
    "Şimdi bu hikâyeyi size anlatırken, o günleri özlemle hatırlıyorum.",
]
EN = [
    "Hello, my name is Ayşe and today I will tell you a short story.",
    "This story takes place in a small neighborhood in Istanbul in 1990.",
    "In those years everyone knew each other and chatted at their doorsteps in the evenings.",
    "Every morning Uncle Mehmet bought fresh bread from the bakery and handed it out to the neighbors.",
    "One day a new family moved into the neighborhood and everyone became very curious.",
    "The family's youngest daughter, Zeynep, did not want to talk to anyone on the first day.",
    "But the next day she started playing with the other children in the park.",
    "When evening came, her mother called her home: Zeynep, dinner is ready, come on!",
    "Zeynep came running and saw that there were 3 plates full of börek on the table.",
    "That evening all the neighbors gathered and talked until late.",
    "Years passed and the neighborhood changed, but the warmth of those days was never forgotten.",
    "Now, as I tell you this story, I remember those days with longing.",
]
TRANSLATE_PROMPT = (
    "You are a professional Turkish (tr) to English (en) translator. Your goal is to accurately "
    "convey the meaning and nuances of the original Turkish text while adhering to English grammar, "
    "vocabulary, and cultural sensitivities. Produce only the English translation, without any "
    "additional explanations or commentary. Please translate the following Turkish text into "
    "English:\n\n{text}"
)
OLLAMA_MODELS = [["translategemma:4b", "translategemma:4b-it-q4_K_M"],
                 ["translategemma:12b", "translategemma:12b-it-q4_K_M"]]
ASR_MODELS = ["large-v3-turbo", "large-v3"]

FAMILIES = {
    "tts": {"pkgs": ["setuptools<81", "chatterbox-tts", "soundfile", "resemble-perth"]},
    "vad": {"pkgs": ["setuptools<81", "silero-vad", "soundfile", "torch"]},
    "asr": {"pkgs": ["setuptools<81", "faster-whisper", "jiwer", "soundfile", "nvidia-cublas-cu12", "nvidia-cudnn-cu12==9.*"]},
    "align": {"pkgs": ["setuptools<81", "whisperx", "soundfile"]},
    "diar": {"pkgs": ["setuptools<81", "pyannote.audio>=4.0", "soundfile"]},
    "tiger": {"pkgs": ["setuptools<81", "torch", "torchaudio", "soundfile", "huggingface_hub", "pyyaml", "numpy"],
              "repo": "https://github.com/JusperLee/TIGER"},
    "demucs": {"pkgs": ["setuptools<81", "demucs @ git+https://github.com/adefossez/demucs", "soundfile"],
               "fallback_pkgs": ["setuptools<81", "demucs", "soundfile"]},
    "tagger": {"pkgs": ["setuptools<81", "transformers", "torch", "soundfile", "numpy"]},
    "opusmt": {"pkgs": ["setuptools<81", "transformers", "sentencepiece", "torch"]},
}

# ---------------------------------------------------------------- bench programs
# Each bench runs in its family's venv as: <venv>/bin/python <bench>.py '<json cfg>'.

HEAD = r'''
import json, os, sys, time, resource, traceback
CFG = json.loads(sys.argv[1])
AD = CFG["audio_dir"]
RESULT = {"bench": CFG["bench"], "ok": False}

def rss_mb():
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)

def torch_peak_mb():
    try:
        import torch
        if torch.cuda.is_available():
            return round(torch.cuda.max_memory_allocated() / 2**20, 1)
    except Exception:
        pass
    return None

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

def truth():
    with open(os.path.join(AD, "truth.json")) as f:
        return json.load(f)

def si_sdr(est, ref):
    import numpy as np
    n = min(len(est), len(ref))
    est = est[:n] - est[:n].mean()
    ref = ref[:n] - ref[:n].mean()
    a = float(np.dot(est, ref) / (np.dot(ref, ref) + 1e-9))
    target = a * ref
    noise = est - target
    return round(10 * float(np.log10((np.dot(target, target) + 1e-9) / (np.dot(noise, noise) + 1e-9))), 2)
'''

# Corpus-level chrF approximation (character n-grams 1–6, beta 2); shared by benches and the orchestrator.
CHRF = r'''
def chrf(hyps, refs, n=6, beta=2.0):
    from collections import Counter
    def grams(s, k):
        s = s.replace(" ", "")
        return Counter(s[i:i + k] for i in range(len(s) - k + 1))
    precs, recs = [], []
    for k in range(1, n + 1):
        match = hyp_n = ref_n = 0
        for h, r in zip(hyps, refs):
            gh, gr = grams(h, k), grams(r, k)
            match += sum((gh & gr).values())
            hyp_n += sum(gh.values())
            ref_n += sum(gr.values())
        precs.append(match / hyp_n if hyp_n else 0.0)
        recs.append(match / ref_n if ref_n else 0.0)
    p, r = sum(precs) / n, sum(recs) / n
    return 0.0 if p + r == 0 else round(100 * (1 + beta ** 2) * p * r / (beta ** 2 * p + r), 1)
'''

TAIL = r'''
try:
    main()
    RESULT["ok"] = True
except BaseException as e:  # record everything, including CUDA OOM
    RESULT["error"] = f"{type(e).__name__}: {e}"[:2000]
    RESULT["traceback"] = traceback.format_exc()[-4000:]
finally:
    RESULT["peak_rss_mb"] = rss_mb()
    RESULT["torch_peak_gpu_mb"] = torch_peak_mb()
    with open(CFG["result_path"], "w") as f:
        json.dump(RESULT, f, indent=2, default=str)
'''

SOURCES: dict[str, str] = {}

SOURCES["tts"] = r'''
def main():
    import subprocess
    import numpy as np, soundfile as sf, torch
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    RESULT["versions"] = versions("chatterbox-tts", "torch", "transformers", "resemble-perth")
    RESULT["device"] = torch.cuda.get_device_name(0)
    tr, en, ff = CFG["tr_sentences"], CFG["en_sentences"], CFG["ffmpeg"]

    t = time.time()
    model = ChatterboxMultilingualTTS.from_pretrained(device="cuda")
    RESULT["mtl_load_s"] = round(time.time() - t, 1)
    sr = model.sr
    RESULT["mtl_sample_rate"] = sr

    def run(name, texts, lang, prefix, **kw):
        gen = dur = 0.0
        for i, text in enumerate(texts):
            torch.manual_seed(1000 + i)
            t0 = time.time()
            wav = model.generate(text, language_id=lang, **kw)
            torch.cuda.synchronize()
            gen += time.time() - t0
            a = wav.squeeze().detach().float().cpu().numpy()
            sf.write(os.path.join(AD, f"{prefix}_{i:02d}.wav"), a, sr)
            dur += len(a) / sr
        RESULT[name] = speed(dur, gen)

    torch.cuda.reset_peak_memory_stats()
    run("mtl_tr_default_voice", tr, "tr", "tr_A")
    run("mtl_en_default_voice", en, "en", "en_default")

    # Cross-lingual cloning: synthetic Turkish voice A as reference, English text.
    ref = os.path.join(AD, "ref_tr_A.wav")
    clips = [sf.read(os.path.join(AD, f"tr_A_{i:02d}.wav"), dtype="float32")[0] for i in range(3)]
    sf.write(ref, np.concatenate(clips), sr)
    RESULT["clone_reference_s"] = round(sum(len(c) for c in clips) / sr, 2)
    run("mtl_en_clone_cfg05", en, "en", "en_clone_cfg05", audio_prompt_path=ref, cfg_weight=0.5)
    run("mtl_en_clone_cfg00", en, "en", "en_clone_cfg00", audio_prompt_path=ref, cfg_weight=0.0)
    d05 = RESULT["mtl_en_clone_cfg05"]["audio_s"]
    d00 = RESULT["mtl_en_clone_cfg00"]["audio_s"]
    RESULT["cfg_weight_0_vs_05_duration_ratio"] = round(d00 / d05, 3) if d05 else None
    RESULT["mtl_peak_gpu_mb"] = torch_peak_mb()

    # Watermark survival (SPEC §19.7).
    try:
        import perth
        det = perth.PerthImplicitWatermarker()
        src = os.path.join(AD, "en_default_00.wav")
        a, s = sf.read(src, dtype="float32")
        wm = {"raw": float(det.get_watermark(a, sample_rate=s))}
        def via(name, args, ext):
            out = os.path.join(AD, f"wm_{name}.{ext}")
            subprocess.run([ff, "-v", "error", "-y", "-i", src, *args, out], check=True)
            dec = subprocess.run([ff, "-v", "error", "-i", out, "-ac", "1", "-ar", str(s), "-f", "f32le", "-"],
                                 check=True, capture_output=True).stdout
            return float(det.get_watermark(np.frombuffer(dec, dtype=np.float32).copy(), sample_rate=s))
        wm["atempo_1.2"] = via("atempo", ["-af", "atempo=1.2"], "wav")
        wm["aac_128k"] = via("aac", ["-c:a", "aac", "-b:a", "128k"], "m4a")
        wm["atempo_1.2+aac"] = via("atempo_aac", ["-af", "atempo=1.2", "-c:a", "aac", "-b:a", "128k"], "m4a")
        RESULT["watermark_detect"] = wm
    except Exception as e:
        RESULT["watermark_detect"] = {"error": f"{type(e).__name__}: {e}"[:500]}

    del model
    torch.cuda.empty_cache()

    # Chatterbox Turbo (English), cloned from the synthetic English default voice.
    try:
        from chatterbox.tts_turbo import ChatterboxTurboTTS
        torch.cuda.reset_peak_memory_stats()
        t = time.time()
        turbo = ChatterboxTurboTTS.from_pretrained(device="cuda")
        RESULT["turbo_load_s"] = round(time.time() - t, 1)
        ref_en = os.path.join(AD, "ref_en_default.wav")
        clips = [sf.read(os.path.join(AD, f"en_default_{i:02d}.wav"), dtype="float32")[0] for i in range(2)]
        sf.write(ref_en, np.concatenate(clips), sr)
        gen = dur = 0.0
        for i, text in enumerate(en):
            torch.manual_seed(2000 + i)
            t0 = time.time()
            wav = turbo.generate(text, audio_prompt_path=ref_en)
            torch.cuda.synchronize()
            gen += time.time() - t0
            dur += wav.shape[-1] / turbo.sr
        RESULT["turbo_en_clone"] = speed(dur, gen)
        RESULT["turbo_peak_gpu_mb"] = torch_peak_mb()
    except Exception as e:
        RESULT["turbo_en_clone"] = {"error": f"{type(e).__name__}: {e}"[:500]}
'''

SOURCES["make_audio"] = r'''
def main():
    import glob, subprocess
    import numpy as np, soundfile as sf
    ff, SR = CFG["ffmpeg"], 48000
    rng = np.random.default_rng(7)

    def load(path, extra=None):
        args = [ff, "-v", "error", "-i", path]
        if extra:
            args += ["-af", extra]
        args += ["-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
        raw = subprocess.run(args, check=True, capture_output=True).stdout
        return np.frombuffer(raw, dtype=np.float32).copy()

    def resample(src, dst, rate, channels):
        subprocess.run([ff, "-v", "error", "-y", "-i", src, "-ac", str(channels), "-ar", str(rate), dst], check=True)

    def concat(prefix):
        files = sorted(glob.glob(os.path.join(AD, f"{prefix}_[0-9][0-9].wav")))
        if not files:
            return None
        parts = []
        for p in files:
            parts += [load(p), np.zeros(int(0.5 * SR), np.float32)]
        out48 = os.path.join(AD, f"{prefix}_concat_48k.wav")
        sf.write(out48, np.concatenate(parts), SR)
        resample(out48, os.path.join(AD, f"{prefix}_concat_16k.wav"), 16000, 1)
        return len(files)

    clips = sorted(glob.glob(os.path.join(AD, "tr_A_[0-9][0-9].wav")))
    if not clips:
        raise RuntimeError("no Turkish clips to build test audio from")
    # Speaker B = speaker A with lower pitch and formants, same duration.
    shift = f"aresample={SR},asetrate={int(SR * 0.84)},aresample={SR},atempo={1 / 0.84:.4f}"
    voices = [load(p) if i % 2 == 0 else load(p, shift) for i, p in enumerate(clips)]

    def music(seconds):
        t = np.arange(int(seconds * SR)) / SR
        env = 0.6 + 0.4 * np.sin(2 * np.pi * 0.25 * t)
        tone = sum(a * np.sin(2 * np.pi * f * t) for f, a in ((220.0, 0.5), (277.18, 0.35), (329.63, 0.3), (110.0, 0.4)))
        noise = rng.standard_normal(len(t)) * 0.05
        left = env * tone + noise
        right = env * np.roll(tone, 120) + noise
        return np.stack([left, right], axis=1).astype(np.float32)

    def build(repeats, tag):
        segs, parts, pos = [], [np.zeros(SR, np.float32)], float(SR)
        for r in range(repeats):
            for i, v in enumerate(voices):
                segs.append({"start": pos / SR, "end": (pos + len(v)) / SR, "speaker": "A" if i % 2 == 0 else "B",
                             "idx": i})
                parts.append(v)
                pos += len(v)
                gap = int(rng.uniform(0.4, 0.9) * SR)
                parts.append(np.zeros(gap, np.float32))
                pos += gap
        dialogue = np.concatenate(parts)
        mus = music(len(dialogue) / SR)
        d_rms = np.sqrt(np.mean(dialogue[dialogue != 0] ** 2))
        m_rms = np.sqrt(np.mean(mus ** 2))
        mus *= (d_rms / m_rms) * 10 ** (-12 / 20)
        mix = mus + dialogue[:, None]
        peak = np.abs(mix).max()
        scale = 0.9 / peak if peak > 0.9 else 1.0
        dialogue, mus, mix = dialogue * scale, mus * scale, mix * scale
        files = {
            f"dialogue_{tag}_48k.wav": (dialogue, 1),
            f"background_{tag}_48k.wav": (mus.mean(axis=1), 1),
            f"mix_{tag}_48k.wav": (mix, 2),
        }
        for name, (data, _) in files.items():
            sf.write(os.path.join(AD, name), data, SR)
        resample(os.path.join(AD, f"mix_{tag}_48k.wav"), os.path.join(AD, f"mix_{tag}_16k.wav"), 16000, 1)
        resample(os.path.join(AD, f"dialogue_{tag}_48k.wav"), os.path.join(AD, f"dialogue_{tag}_16k.wav"), 16000, 1)
        resample(os.path.join(AD, f"mix_{tag}_48k.wav"), os.path.join(AD, f"mix_{tag}_44k.wav"), 44100, 2)
        resample(os.path.join(AD, f"mix_{tag}_48k.wav"), os.path.join(AD, f"mix_{tag}_44k_mono.wav"), 44100, 1)
        resample(os.path.join(AD, f"dialogue_{tag}_48k.wav"), os.path.join(AD, f"dialogue_{tag}_44k.wav"), 44100, 1)
        resample(os.path.join(AD, f"background_{tag}_48k.wav"), os.path.join(AD, f"background_{tag}_44k.wav"), 44100, 1)
        return {"segments": segs, "texts": CFG["tr_sentences"][:len(voices)] * repeats,
                "duration_s": round(len(dialogue) / SR, 2)}

    data = {"60s": build(1, "60s"), "300s": build(5, "300s")}
    with open(os.path.join(AD, "truth.json"), "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    RESULT["durations"] = {k: v["duration_s"] for k, v in data.items()}
    RESULT["concat"] = {p: concat(p) for p in ("en_default", "en_clone_cfg05", "en_clone_cfg00")}
'''

SOURCES["vad"] = r'''
def main():
    import numpy as np, soundfile as sf, torch
    from silero_vad import load_silero_vad, get_speech_timestamps
    RESULT["versions"] = versions("silero-vad", "torch")
    t = time.time()
    model = load_silero_vad()
    RESULT["load_s"] = round(time.time() - t, 2)
    tr = truth()
    for tag in ("60s", "300s"):
        wav, sr = sf.read(os.path.join(AD, f"mix_{tag}_16k.wav"), dtype="float32")
        t = time.time()
        ts = get_speech_timestamps(torch.from_numpy(wav), model, sampling_rate=sr, return_seconds=True)
        el = time.time() - t
        segs = tr[tag]["segments"]
        truth_s = sum(s["end"] - s["start"] for s in segs)
        hit = sum(max(0.0, min(a["end"], s["end"]) - max(a["start"], s["start"])) for a in ts for s in segs)
        r = speed(len(wav) / sr, el)
        r.update({"regions": len(ts), "speech_recall": round(hit / truth_s, 3),
                  "detected_speech_s": round(sum(a["end"] - a["start"] for a in ts), 1),
                  "true_speech_s": round(truth_s, 1), "device": "cpu"})
        RESULT[tag] = r
'''

SOURCES["asr"] = r'''
def main():
    import re
    import soundfile as sf, jiwer, ctranslate2
    from faster_whisper import WhisperModel
    RESULT["versions"] = versions("faster-whisper", "ctranslate2")
    RESULT["cuda_devices"] = ctranslate2.get_cuda_device_count()
    tr = truth()

    def norm(s):
        s = re.sub(r"[^\w\s]", " ", s.lower())
        return " ".join(s.split())

    def text_of(model, path, lang):
        segs, info = model.transcribe(path, language=lang, beam_size=5, condition_on_previous_text=False,
                                      vad_filter=True)
        segs = list(segs)
        return segs, info, " ".join(s.text for s in segs)

    for name in CFG["asr_models"]:
        r = {}
        try:
            t = time.time()
            model = WhisperModel(name, device="cuda", compute_type="float16")
            r["load_s"] = round(time.time() - t, 1)
            for tag in ("60s", "300s"):
                path = os.path.join(AD, f"mix_{tag}_16k.wav")
                t = time.time()
                segs, info, hyp = text_of(model, path, "tr")
                el = time.time() - t
                r[tag] = speed(sf.info(path).duration, el)
                r[tag]["segments"] = len(segs)
                r[tag]["wer_tr_vs_truth"] = round(jiwer.wer(norm(" ".join(tr[tag]["texts"])), norm(hyp)), 3)
                if tag == "60s" and segs:
                    r["segment_fields"] = {k: hasattr(segs[0], k)
                                           for k in ("avg_logprob", "no_speech_prob", "compression_ratio", "words")}
            # Intelligibility of synthesized English (SPEC §12.2 SC2 analogue).
            for prefix in ("en_default", "en_clone_cfg05", "en_clone_cfg00"):
                path = os.path.join(AD, f"{prefix}_concat_16k.wav")
                if os.path.exists(path):
                    _, _, hyp = text_of(model, path, "en")
                    r[f"wer_{prefix}"] = round(jiwer.wer(norm(" ".join(CFG["en_sentences"])), norm(hyp)), 3)
            segs, info = model.transcribe(os.path.join(AD, "tr_A_00.wav"))
            list(segs)
            r["language_detect"] = {"language": info.language, "probability": round(info.language_probability, 3)}
            del model
        except Exception as e:
            r["error"] = f"{type(e).__name__}: {e}"[:800]
        RESULT[name] = r
'''

SOURCES["align"] = r'''
def main():
    import soundfile as sf, torch, whisperx
    from whisperx import alignment
    RESULT["versions"] = versions("whisperx", "torch", "transformers")
    RESULT["default_align_model_tr"] = getattr(alignment, "DEFAULT_ALIGN_MODELS_HF", {}).get("tr")
    tr = truth()
    audio, sr = sf.read(os.path.join(AD, "dialogue_60s_16k.wav"), dtype="float32")
    segments = [{"start": s["start"], "end": s["end"], "text": tr["60s"]["texts"][s["idx"]]}
                for s in tr["60s"]["segments"]]
    t = time.time()
    model_a, meta = whisperx.load_align_model(language_code="tr", device="cuda")
    RESULT["load_s"] = round(time.time() - t, 1)
    t = time.time()
    out = whisperx.align(segments, model_a, meta, audio, "cuda", return_char_alignments=False)
    el = time.time() - t
    words = [w for s in out["segments"] for w in s.get("words", [])]
    speech_s = sum(s["end"] - s["start"] for s in segments)
    RESULT["speed_on_speech"] = speed(speech_s, el)
    RESULT["words_total"] = len(words)
    RESULT["words_without_timestamps"] = sum(1 for w in words if "start" not in w)
    RESULT["untimed_words"] = [w.get("word") for w in words if "start" not in w][:10]
'''

SOURCES["diar"] = r'''
def main():
    from collections import Counter
    import soundfile as sf, torch
    from pyannote.audio import Pipeline
    RESULT["versions"] = versions("pyannote.audio", "torch")
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN missing (attach the Kaggle secret and accept the model conditions on Hugging Face)")
    t = time.time()
    pipe = Pipeline.from_pretrained("pyannote/speaker-diarization-community-1", token=token)
    pipe.to(torch.device("cuda"))
    RESULT["load_s"] = round(time.time() - t, 1)
    tr = truth()
    for tag in ("60s", "300s"):
        wav, sr = sf.read(os.path.join(AD, f"mix_{tag}_16k.wav"), dtype="float32")
        torch.cuda.reset_peak_memory_stats()
        t = time.time()
        out = pipe({"waveform": torch.from_numpy(wav)[None], "sample_rate": sr})
        el = time.time() - t
        try:
            turns = [(seg.start, seg.end, spk) for seg, spk in out.speaker_diarization]
        except (TypeError, ValueError):
            turns = [(seg.start, seg.end, spk) for seg, _, spk in out.speaker_diarization.itertracks(yield_label=True)]

        def dominant(s):
            best, best_o = None, 0.0
            for a, b, label in turns:
                o = max(0.0, min(b, s["end"]) - max(a, s["start"]))
                if o > best_o:
                    best, best_o = label, o
            return best

        dom = [(s["speaker"], dominant(s)) for s in tr[tag]["segments"]]
        majority = {spk: Counter(d for s, d in dom if s == spk).most_common(1)[0][0] for spk in {s for s, _ in dom}}
        r = speed(len(wav) / sr, el)
        r.update({"speakers_found": len({t_[2] for t_ in turns}), "speakers_true": len(majority),
                  "labels_distinct": len(set(majority.values())) == len(majority),
                  "segment_speaker_accuracy": round(sum(1 for s, d in dom if d == majority[s]) / len(dom), 3),
                  "peak_gpu_mb": torch_peak_mb()})
        if tag == "60s":
            r["output_fields"] = [a for a in dir(out) if not a.startswith("_")]
            emb = getattr(out, "speaker_embeddings", None)
            r["speaker_embeddings_shape"] = list(getattr(emb, "shape", [])) if emb is not None else None
            r["has_exclusive_diarization"] = hasattr(out, "exclusive_speaker_diarization")
        RESULT[tag] = r
'''

SOURCES["tiger"] = r'''
def main():
    import numpy as np, soundfile as sf, torch
    sys.path.insert(0, CFG["tiger_repo"])
    import look2hear.models
    RESULT["versions"] = versions("torch", "torchaudio")
    t = time.time()
    model = look2hear.models.TIGERDNR.from_pretrained("JusperLee/TIGER-DnR",
                                                      cache_dir=os.path.join(os.environ["HF_HOME"], "tiger"))
    model = model.to("cuda").eval()
    RESULT["load_s"] = round(time.time() - t, 1)

    def separate(x):
        with torch.no_grad():
            d, e, m = model(x)
        return d, e + m

    for tag in ("60s", "300s"):
        mix, sr = sf.read(os.path.join(AD, f"mix_{tag}_44k_mono.wav"), dtype="float32")
        x = torch.from_numpy(mix)[None, None].to("cuda")
        torch.cuda.reset_peak_memory_stats()
        t = time.time()
        chunked = False
        try:
            dialog, bg = separate(x)
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            chunked, step, outs = True, 30 * sr, []
            for i in range(0, x.shape[-1], step):
                outs.append([o.cpu() for o in separate(x[..., i:i + step])])
            dialog = torch.cat([o[0] for o in outs], dim=-1)
            bg = torch.cat([o[1] for o in outs], dim=-1)
        torch.cuda.synchronize()
        el = time.time() - t
        ref_d = sf.read(os.path.join(AD, f"dialogue_{tag}_44k.wav"), dtype="float32")[0]
        ref_b = sf.read(os.path.join(AD, f"background_{tag}_44k.wav"), dtype="float32")[0]
        d = dialog.squeeze().float().cpu().numpy()
        b = bg.squeeze().float().cpu().numpy()
        r = speed(len(mix) / sr, el)
        r.update({"chunked": chunked, "peak_gpu_mb": torch_peak_mb(),
                  "si_sdr_dialogue_db": si_sdr(d, ref_d), "si_sdr_background_db": si_sdr(b, ref_b),
                  "si_sdr_mix_vs_dialogue_db": si_sdr(mix, ref_d)})
        if tag == "60s":
            sf.write(os.path.join(AD, "tiger_dialogue_60s.wav"), d, sr)
        RESULT[tag] = r
'''

SOURCES["demucs"] = r'''
def main():
    import soundfile as sf, torch
    from demucs.pretrained import get_model
    from demucs.apply import apply_model
    RESULT["versions"] = versions("demucs", "torch", "torchaudio")
    t = time.time()
    model = get_model("htdemucs")
    model.to("cuda").eval()
    RESULT["load_s"] = round(time.time() - t, 1)
    RESULT["sources"] = list(model.sources)
    vi = model.sources.index("vocals")
    for tag in ("60s", "300s"):
        mix, sr = sf.read(os.path.join(AD, f"mix_{tag}_44k.wav"), dtype="float32")
        x = torch.from_numpy(mix.T.copy())
        ref = x.mean(0)
        xn = (x - ref.mean()) / (ref.std() + 1e-8)
        torch.cuda.reset_peak_memory_stats()
        t = time.time()
        with torch.no_grad():
            out = apply_model(model, xn[None], device="cuda", split=True, overlap=0.25, progress=False)[0]
        torch.cuda.synchronize()
        el = time.time() - t
        out = out * ref.std() + ref.mean()
        voc = out[vi].mean(0).cpu().numpy()
        bg = (out.sum(0) - out[vi]).mean(0).cpu().numpy()
        ref_d = sf.read(os.path.join(AD, f"dialogue_{tag}_44k.wav"), dtype="float32")[0]
        ref_b = sf.read(os.path.join(AD, f"background_{tag}_44k.wav"), dtype="float32")[0]
        r = speed(len(mix) / sr, el)
        r.update({"peak_gpu_mb": torch_peak_mb(), "si_sdr_dialogue_db": si_sdr(voc, ref_d),
                  "si_sdr_background_db": si_sdr(bg, ref_b)})
        RESULT[tag] = r
'''

SOURCES["tagger"] = r'''
def main():
    import soundfile as sf, torch
    from transformers import ASTFeatureExtractor, ASTForAudioClassification
    RESULT["versions"] = versions("transformers", "torch")
    name = "MIT/ast-finetuned-audioset-10-10-0.4593"
    t = time.time()
    fe = ASTFeatureExtractor.from_pretrained(name)
    model = ASTForAudioClassification.from_pretrained(name).to("cuda").eval()
    RESULT["load_s"] = round(time.time() - t, 1)
    wav, sr = sf.read(os.path.join(AD, "mix_60s_16k.wav"), dtype="float32")
    windows, t = [], time.time()
    for i in range(0, len(wav), 10 * sr):
        chunk = wav[i:i + 10 * sr]
        if len(chunk) < sr:
            break
        inp = fe(chunk, sampling_rate=sr, return_tensors="pt").to("cuda")
        with torch.no_grad():
            probs = torch.sigmoid(model(**inp).logits[0])
        top = probs.topk(3)
        windows.append([[model.config.id2label[int(j)], round(float(p), 3)] for p, j in zip(top.values, top.indices)])
    RESULT.update(speed(len(wav) / sr, time.time() - t))
    RESULT["top_labels_per_10s"] = windows
'''

SOURCES["opusmt"] = r'''
def main():
    import torch
    from transformers import MarianMTModel, MarianTokenizer
    RESULT["versions"] = versions("transformers", "torch", "sentencepiece")
    name = "Helsinki-NLP/opus-mt-tr-en"
    t = time.time()
    tok = MarianTokenizer.from_pretrained(name)
    model = MarianMTModel.from_pretrained(name).to("cuda").eval()
    RESULT["load_s"] = round(time.time() - t, 1)
    t = time.time()
    batch = tok(CFG["tr_sentences"], return_tensors="pt", padding=True).to("cuda")
    with torch.no_grad():
        gen = model.generate(**batch, max_new_tokens=128)
    hyp = tok.batch_decode(gen, skip_special_tokens=True)
    RESULT["run_s"] = round(time.time() - t, 2)
    RESULT["sentences"] = len(hyp)
    RESULT["chrf_vs_reference"] = chrf(hyp, CFG["en_sentences"])
'''

# ---------------------------------------------------------------- orchestration


def save() -> None:
    (WORK / "results.json").write_text(json.dumps(RESULTS, indent=2, ensure_ascii=False, default=str))


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


def gpu_used_mb() -> list[int]:
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True)
    return [int(x) for x in out.stdout.split()] if out.returncode == 0 else []


class GpuSampler:
    """Samples GPU 0 (the one every bench is pinned to) every 250 ms and keeps the peak memory in MB."""

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


def ensure_uv() -> None:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "uv"], check=True)


def ensure_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if path:
        return path
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "imageio-ffmpeg"], check=True)
    import imageio_ffmpeg  # type: ignore
    return imageio_ffmpeg.get_ffmpeg_exe()


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


def env_info(ffmpeg: str) -> None:
    info = RESULTS["env"]
    info["python"] = sys.version.split()[0]
    info["gpus"] = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True).stdout.strip().splitlines()
    info["driver"] = subprocess.run(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                                    capture_output=True, text=True).stdout.strip()
    info["scratch_free_gb"] = round(shutil.disk_usage(SCRATCH).free / 1e9, 1)
    info["working_free_gb"] = round(shutil.disk_usage(WORK).free / 1e9, 1)
    try:
        mem = Path("/proc/meminfo").read_text().splitlines()[0].split()[1]
        info["ram_gb"] = round(int(mem) / 1e6, 1)
    except Exception:
        pass
    info["ffmpeg"] = subprocess.run([ffmpeg, "-version"], capture_output=True, text=True).stdout.splitlines()[0]


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
        repo_dir = SCRATCH / name / "repo"
        ok = run(["git", "clone", "--depth", "1", spec["repo"], str(repo_dir)], log) == 0
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


def bench(name: str, family: str, cfg: dict, ffmpeg: str, extra_env: dict | None = None, timeout: int = 2700) -> dict:
    path = BENCH / f"bench_{name}.py"
    path.write_text(HEAD + CHRF + SOURCES[name] + TAIL)
    result_path = WORK / f"result_{name}.json"
    full = {**cfg, "bench": name, "result_path": str(result_path), "audio_dir": str(AUDIO), "ffmpeg": ffmpeg,
            "tr_sentences": TR, "en_sentences": EN}
    env = dict(ENV)
    env.update(extra_env or {})
    sampler = GpuSampler()
    sampler.start()
    t = time.time()
    rc = run([str(VENVS / family / "bin" / "python"), str(path), json.dumps(full, ensure_ascii=False)],
             LOGS / f"bench_{name}.log", env=env, timeout=timeout)
    wall = round(time.time() - t, 1)
    peak = sampler.stop()
    res = json.loads(result_path.read_text()) if result_path.exists() else {"ok": False, "error": f"no result (rc={rc})"}
    res.update({"wall_s": wall, "nvidia_smi_peak_mb": peak, "returncode": rc})
    RESULTS["bench"][name] = res
    save()
    print(f"[s1] {name}: ok={res.get('ok')} wall={wall}s peak={peak}MB {str(res.get('error') or '')[:200]}", flush=True)
    return res


def espeak_fallback() -> None:
    """Only if Chatterbox failed: synthesize the Turkish lines with espeak-ng (dev-only tool)."""
    log = LOGS / "espeak.log"
    if not shutil.which("espeak-ng"):
        run(["bash", "-lc", "apt-get update -qq && apt-get install -y -qq espeak-ng"], log, timeout=900)
    for i, text in enumerate(TR):
        run(["espeak-ng", "-v", "tr", "-s", "150", "-w", str(AUDIO / f"tr_A_{i:02d}.wav"), text], log)
    RESULTS["env"]["test_audio_source"] = "espeak-ng fallback (Chatterbox unavailable)"


def ollama_bench() -> None:
    log, r = LOGS / "ollama.log", {"prompt": TRANSLATE_PROMPT}
    env = dict(ENV, OLLAMA_MODELS=str(SCRATCH / "ollama"), OLLAMA_HOST="127.0.0.1:11434")
    t = time.time()
    if not shutil.which("ollama"):
        if not shutil.which("zstd"):
            run(["bash", "-lc", "apt-get update -qq && apt-get install -y -qq zstd"], log, timeout=900)
        run(["bash", "-lc", "curl -fsSL https://ollama.com/install.sh | sh"], log, timeout=1200)
    r["install_s"] = round(time.time() - t, 1)
    if not shutil.which("ollama"):
        RESULTS["bench"]["ollama"] = {**r, "ok": False, "error": "ollama install failed (see logs/ollama.log)"}
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

    try:
        for _ in range(60):
            try:
                call("/api/tags")
                break
            except Exception:
                time.sleep(1)
        r["gpu_mb_idle"] = gpu_used_mb()
        for candidates in OLLAMA_MODELS:
            tag, entry = None, {}
            t = time.time()
            for c in candidates:
                if run(["ollama", "pull", c], log, env=env, timeout=1800) == 0:
                    tag = c
                    break
            entry["pull_s"] = round(time.time() - t, 1)
            if tag is None:
                r[candidates[0]] = {**entry, "error": "pull failed"}
                continue
            sampler = GpuSampler()
            sampler.start()
            hyps, tokens, eval_ns, t = [], 0, 0, time.time()
            for i, text in enumerate(TR):
                out = call("/api/generate", {"model": tag, "prompt": TRANSLATE_PROMPT.format(text=text),
                                             "stream": False, "keep_alive": "5m", "options": {"temperature": 0}})
                if i == 0:
                    entry["first_call_s"] = round(time.time() - t, 1)  # includes model load
                hyps.append(out.get("response", "").strip())
                tokens += out.get("eval_count", 0)
                eval_ns += out.get("eval_duration", 0)
            entry["total_s"] = round(time.time() - t, 1)
            entry["peak_gpu_mb"] = sampler.stop()
            entry["decode_tok_per_s"] = round(tokens / (eval_ns / 1e9), 1) if eval_ns else None
            entry["sec_per_sentence_after_load"] = round((entry["total_s"] - entry.get("first_call_s", 0)) / max(len(TR) - 1, 1), 2)
            entry["chrf_vs_reference"] = _chrf(hyps, EN)
            entry["gpu_mb_loaded"] = gpu_used_mb()
            call("/api/generate", {"model": tag, "prompt": "", "keep_alive": 0})
            time.sleep(5)
            entry["gpu_mb_after_keep_alive_0"] = gpu_used_mb()
            entry["loaded_after_unload"] = [m.get("name") for m in call("/api/ps").get("models", [])]
            r[tag] = entry
            save()
        r["ok"] = True
    except Exception as e:
        r["ok"] = False
        r["error"] = f"{type(e).__name__}: {e}"[:800]
    finally:
        server.terminate()
    RESULTS["bench"]["ollama"] = r
    save()


def _chrf(hyps: list[str], refs: list[str]) -> float:
    scope: dict = {}
    exec(CHRF, scope)
    return scope["chrf"](hyps, refs)


def write_summary() -> None:
    b = RESULTS["bench"]
    video_s, speech_en_s = 5400.0, 55 * 60 * 1.3  # SPEC assumption: 90-min video, ~55 min English speech x1.3

    def get(*keys):
        cur = b
        for k in keys:
            if not isinstance(cur, dict) or k not in cur:
                return None
            cur = cur[k]
        return cur

    proj = {}
    for label, xr in (("ASR large-v3-turbo", get("asr", "large-v3-turbo", "300s", "x_realtime")),
                      ("ASR large-v3", get("asr", "large-v3", "300s", "x_realtime")),
                      ("VAD", get("vad", "300s", "x_realtime")),
                      ("Diarization", get("diar", "300s", "x_realtime")),
                      ("Separation TIGER-DnR", get("tiger", "300s", "x_realtime")),
                      ("Separation Demucs", get("demucs", "300s", "x_realtime"))):
        if xr:
            proj[label] = round(video_s / xr / 60, 1)
    align_xr = get("align", "speed_on_speech", "x_realtime")
    if align_xr:
        proj["Alignment (on ~55 min speech)"] = round(3300 / align_xr / 60, 1)
    for label, key in (("TTS multilingual clone (1 GPU)", "mtl_en_clone_cfg00"), ("TTS Turbo (1 GPU)", "turbo_en_clone")):
        rtf = get("tts", key, "rtf")
        if rtf:
            proj[label] = round(speech_en_s * rtf / 60, 1)
    for tag in ("translategemma:4b", "translategemma:4b-it-q4_K_M"):
        sps = get("ollama", tag, "sec_per_sentence_after_load")
        if sps:
            proj["Translation TranslateGemma 4B (~1,200 segments)"] = round(sps * 1200 / 60, 1)
    RESULTS["projection_90min_minutes"] = proj
    save()

    lines = ["# Spike S1 results", "", f"Started {RESULTS['started']}; GPUs: {RESULTS['env'].get('gpus')}", "",
             "| Bench | OK | Wall s | nvidia-smi peak MB | Key numbers | Error |", "| --- | --- | --- | --- | --- | --- |"]
    for name, res in b.items():
        key = {k: v for k, v in res.items() if k in ("60s", "300s", "load_s", "speed_on_speech", "chrf_vs_reference",
                                                     "mtl_en_clone_cfg00", "turbo_en_clone",
                                                     "cfg_weight_0_vs_05_duration_ratio", "watermark_detect",
                                                     "large-v3-turbo", "large-v3")}
        lines.append(f"| {name} | {res.get('ok')} | {res.get('wall_s', '')} | {res.get('nvidia_smi_peak_mb', '')} | "
                     f"{json.dumps(key, ensure_ascii=False)[:400]} | {str(res.get('error', ''))[:120]} |")
    lines += ["", "## Projection for a 90-minute video (minutes, single T4)", ""]
    lines += [f"- {k}: {v}" for k, v in proj.items()]
    lines += ["", "Install times and venv sizes: see results.json → install."]
    (WORK / "summary.md").write_text("\n".join(lines))


def copy_samples() -> None:
    SAMPLES.mkdir(parents=True, exist_ok=True)
    for name in ("mix_60s_48k.wav", "tiger_dialogue_60s.wav", "en_default_concat_48k.wav",
                 "en_clone_cfg05_concat_48k.wav", "en_clone_cfg00_concat_48k.wav", "ref_tr_A.wav"):
        src = AUDIO / name
        if src.exists():
            shutil.copy2(src, SAMPLES / name)


def main() -> None:
    for d in (WORK, LOGS, SCRATCH, AUDIO, VENVS, BENCH):
        d.mkdir(parents=True, exist_ok=True)
    ffmpeg = ensure_ffmpeg()
    env_info(ffmpeg)
    token = hf_token()
    RESULTS["env"]["hf_token_present"] = bool(token)
    RESULTS["env"]["internet"] = internet_ok()
    save()
    if not RESULTS["env"]["internet"]:
        print("[s1] No internet in this session (phone verification / internet setting): stopping.", flush=True)
        return
    if REQUIRE_HF_TOKEN and not token:
        print("[s1] HF_TOKEN secret not attached: stopping before any heavy work. Attach it and run again.", flush=True)
        return
    ensure_uv()

    # 1. TTS first: it also produces the synthetic Turkish test speech.
    RESULTS["env"]["test_audio_source"] = "Chatterbox Multilingual default voice (synthetic)"
    if install("tts"):
        bench("tts", "tts", {}, ffmpeg)
    if not list(AUDIO.glob("tr_A_*.wav")):
        espeak_fallback()
    audio_family = "tts" if INSTALLED.get("tts") else ("vad" if install("vad") else None)
    if audio_family is None or not bench("make_audio", audio_family, {}, ffmpeg).get("ok"):
        print("[s1] could not build test audio; stopping", flush=True)
        write_summary()
        return

    # 2. Every other family, one process at a time.
    asr_env = {}
    plan = [
        ("vad", "vad", {}, None),
        ("asr", "asr", {"asr_models": ASR_MODELS}, "asr"),
        ("align", "align", {}, None),
        ("diar", "diar", {}, "diar"),
        ("tiger", "tiger", {"tiger_repo": str(SCRATCH / "tiger" / "repo")}, None),
        ("demucs", "demucs", {}, None),
        ("tagger", "tagger", {}, None),
        ("opusmt", "opusmt", {}, None),
    ]
    for family, name, cfg, special in plan:
        if ONLY and name not in ONLY:
            continue
        if not install(family):
            RESULTS["bench"][name] = {"ok": False, "error": f"install failed (logs/install_{family}.log)"}
            save()
            continue
        extra = {}
        if special == "asr":
            code = ("import os, nvidia.cublas.lib, nvidia.cudnn.lib; print(os.path.dirname(nvidia.cublas.lib.__file__)"
                    " + ':' + os.path.dirname(nvidia.cudnn.lib.__file__))")
            out = subprocess.run([str(VENVS / "asr" / "bin" / "python"), "-c", code], capture_output=True, text=True,
                                 env=ENV)
            libs = out.stdout.strip()
            asr_env = {"LD_LIBRARY_PATH": f"{libs}:{os.environ.get('LD_LIBRARY_PATH', '')}"} if libs else {}
            extra = asr_env
        if special == "diar" and token:
            extra = {"HF_TOKEN": token}
        bench(name, family, cfg, ffmpeg, extra_env=extra)

    # 3. Translation LLMs via Ollama (outside the venvs).
    if not ONLY or "ollama" in ONLY:
        ollama_bench()

    RESULTS["disk"] = {"scratch_used_gb": du_gb(SCRATCH), "hf_cache_gb": du_gb(SCRATCH / "hf"),
                       "uv_cache_gb": du_gb(SCRATCH / "uv-cache"), "ollama_models_gb": du_gb(SCRATCH / "ollama")}
    RESULTS["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    copy_samples()
    write_summary()
    print((WORK / "summary.md").read_text(), flush=True)


if __name__ == "__main__":
    main()
