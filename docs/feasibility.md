# Feasibility investigation (desk research, before Phase 0)

Date: 2026-10-05. Method: web research of primary and secondary sources plus read-only checks of the reference machine. Nothing was installed, downloaded or run. Tags: **V** = seen in a primary source (vendor page, model card, paper); **R** = reported by a secondary source (blog, aggregator, issue); **?** = not found. Everything here must be confirmed by the hands-on spikes in §10 before it becomes a default in `docs/spikes.md`.

## 0. Verdicts

| # | Question | Verdict | Deciding evidence | Still needs |
| --- | --- | --- | --- | --- |
| 1 | Can the chosen local models work together? | **GO**, only with per-family environments | Chatterbox pins torch 2.6; pyannote.audio 4 needs torch ≥ 2.8, so they cannot share an environment (§1) | Spike S1 install and smoke run |
| 2 | Can we legally use them? | **GO** for the core stack; 3 items open | Core models are MIT / Apache-2.0 / CC-BY-4.0 / Gemma terms (§2) | Licenses of Bandit v2 weights and PANNs; training data of TIGER-DnR and Demucs |
| 3 | Can the M1 Pro run them in reasonable time and memory? | Memory **GO**; time **BORDERLINE**; disk **RED** | Estimated 2.1–6.3 h for 90 min vs 4.5 h target; TTS dominates; 51 GB disk free (§3) | Spike S1 real-time factors |
| 4 | Can we get stable speaker identity? | **GO with cast review**; uncertain without it | community-1 is the best open diarizer, but no drama or Turkish benchmark exists (§4) | Spike S3 on a real clip |
| 5 | Can we clone Turkish → English voices consistently? | **UNPROVEN** (top product risk) | Vendor claims and README guidance only; no published consistency metric (§5) | Spike S2 bake-off |
| 6 | Can we preserve background audio acceptably? | **UNPROVEN**; ducked-original fallback is the guaranteed floor | License-clean separators (trained only on DnR) generalize poorly to real films (§6) | Spike S3 listening test |
| 7 | Can we process a realistic multi-speaker clip? | **BLOCKED** on footage | Prior art shows the pipeline shape works, but none of it is license-clean or Turkish (§7) | Rights-cleared Turkish footage |

## 1. Working together

| Finding | Tag | Source |
| --- | --- | --- |
| `chatterbox-tts` pins `torch==2.6.0`, `torchaudio==2.6.0`, `diffusers==0.29.0` and others; pyannote.audio ≥ 4.0 requires torch ≥ 2.8, so "the two cannot coexist" in one environment | R | [PyPI videopython-chatterbox](https://pypi.org/project/videopython-chatterbox/), [chatterbox issue #243](https://github.com/resemble-ai/chatterbox/issues/243) |
| Chatterbox recommends Python 3.10/3.11 (3.12 untested) | R | same |
| pyannote.audio works on the PyTorch MPS backend | R | [Mac build notes](https://git.azcomputerguru.com/azcomputerguru/claudetools/src/branch/ad2/projects/radio-show/audio-processor/MAC_BUILD_TASK.md) |
| Community MLX / CoreML ports exist: Chatterbox Multilingual MLX fp16 (1.3 GB), pyannote community-1 CoreML, Chatterbox Nano MLX/ONNX/CoreML | V | [Chatterbox-Multilingual-MLX-fp16](https://huggingface.co/aufklarer/Chatterbox-Multilingual-MLX-fp16), [Pyannote-Community-1-CoreML](https://huggingface.co/aufklarer/Pyannote-Community-1-CoreML), [chatterbox-nano-fp16-mlx](https://huggingface.co/Rybib/chatterbox-nano-fp16-mlx) |

Implications:
- SPEC §6 (one venv per model family, subprocess per call, files between stages) is required, not optional.
- The QC embedder that SPEC §3.2 loads inside the TTS worker must run under the TTS environment's torch 2.6. Options: a WeSpeaker model through ONNX Runtime (no torch dependency), or Chatterbox's own voice encoder (provider-specific).
- Risks: macOS 27.0.1 is very new, so PyTorch-MPS and MLX support on it is unverified. MLX and CoreML ports are community-maintained, so check their licenses and how actively they are maintained.

## 2. Legal

| Model | Role | License | Commercial | Tag | Notes |
| --- | --- | --- | --- | --- | --- |
| Chatterbox Multilingual **V3** (0.5B, released 2026-06-10) | TTS default | MIT | Yes | V | 23 languages incl. Turkish (some pages say 25 incl. dialects); PerTh watermark on by default. [Resemble](https://resemble.ai/learn/models/chatterbox-multilingual), [V3 post](https://www.resemble.ai/resources/chatterbox-multilingual-v3-tts-with-embedded-watermarking-for-25-languages) |
| Chatterbox Turbo (350M) | TTS candidate | MIT | Yes | R | English; [tts.ai](https://tts.ai/voices/chatterbox-turbo-default/) |
| Chatterbox **Nano** (110M) | TTS candidate (CPU) | MIT | Yes | R | Exists; HF repo gated (share contact info); ~3× real time on 8 CPU threads; same data as Turbo (English). [Resemble](https://www.resemble.ai/learn/models/chatterbox-nano), [HF](https://huggingface.co/ResembleAI/chatterbox-nano) |
| Chatterbox **Flash** | TTS candidate (new; not in SPEC) | ? | ? | V (exists) | MLX RTF 0.78 on M4. [HF](https://huggingface.co/ResembleAI/chatterbox-flash) |
| Qwen3-TTS 0.6B / 1.7B | TTS candidate | Apache-2.0 | Yes | R | 10 languages, no Turkish; cloning from ~3 s. [Gigazine](https://gigazine.net/gsc_news/en/20260123-qwen3-tts-family-opensource) |
| TranslateGemma 4B / 12B / 27B | Translation | Gemma Terms of Use | Yes, with conditions | V | In the Ollama library (`translategemma:4b-it-q8_0` etc.). Must pass use restrictions on to users and ship a Gemma NOTICE. [Ollama](https://ollama.com/library/translategemma:4b-it-q8_0/blobs/3e2c24001f9e) |
| pyannote speaker-diarization-community-1 | Diarization | CC-BY-4.0 | Yes ("no commercial restrictions") | R | Gated (accept terms + HF token); exclusive diarization included. [HF](https://huggingface.co/pyannote/speaker-diarization-community-1) |
| WeSpeaker ResNet34-LM (pyannote) | Embeddings | CC-BY-4.0 (VoxCeleb license) | Yes, attribution | R | [HF](https://huggingface.co/pyannote/wespeaker-voxceleb-resnet34-LM) |
| mpoyraz/wav2vec2-xls-r-300m-cv7-turkish | Turkish alignment | CC-BY-4.0 | Yes, attribution | R | Trained on Common Voice 7. Whether it is WhisperX's default for `tr` is not yet confirmed. [PromptLayer](https://www.promptlayer.com/models/wav2vec2-xls-r-300m-cv7-turkish) |
| TIGER-DnR (~1.4M params per stem) | Separation default | Apache-2.0 | Yes | R | **Training-data caveat:** trained on the original DnR, whose FMA music includes CC BY-NC / NC-SA tracks (DnR v3 paper). [Mixpeek](https://mixpeek.com/model/JusperLee/TIGER-DnR), [LiteRT port](https://huggingface.co/litert-community/TIGER-DnR-LiteRT), [DnR v3](https://arxiv.org/pdf/2407.07275) |
| Bandit v2 | Separation candidate | **?** | ? | V (data) | Trained on DnR v3, built "exclusively from sources with explicit and permissive licenses, permitting commercial and derivative use". Weights license not found. [DnR v3](https://arxiv.org/pdf/2407.07275) |
| AST (MIT/ast-finetuned-audioset) | Audio events (singing, laughter) | BSD-3-Clause | Yes | R | AudioSet classes cover singing, laughter, crying, screaming, sigh. [HF](https://huggingface.co/MIT/ast-finetuned-audioset-14-14-0.443) |
| PANNs CNN14 | Audio events | **?** | ? | — | License not found |
| Demucs htdemucs | Separation fallback | MIT (code) | ? | — | Training-data terms (MUSDB18) not verified in this pass |

Open legal items: Bandit v2 weights license; PANNs license; TIGER-DnR training-data position; Demucs training-data terms; licenses of the MLX/CoreML ports; whether WhisperX's default Turkish aligner is the mpoyraz model.

## 3. M1 Pro time, memory, disk

Machine (read-only check, 2026-10-03): M1 Pro, 10 CPU cores (8P + 2E), 16-core GPU, 16 GB unified memory, macOS 27.0.1, **51 GB free disk**, 3.5 GB swap already in use.

Rough 90-minute estimate. Assumes ~55 min of English speech to synthesize and ×1.3 for audition, drift-gate regenerations and rewrites. All inputs are secondary numbers, not measurements.

| Stage | Basis | Estimate |
| --- | --- | --- |
| ASR (mlx-whisper large-v3-turbo) | 14–18× real time on Apple Silicon, R ([PromptQuorum](https://www.promptquorum.com/local-llms/apple-silicon-whisper-metal-benchmark)) | 5–10 min |
| Word alignment | no number found | 5–15 min |
| Diarization (pyannote, MPS) | MPS works; CoreML port reported ~10–20× faster, R | 10–40 min |
| Separation (TIGER-DnR) | very small model; no M1 number | 10–45 min |
| Translation (TranslateGemma 4B) | Gemma 3 4B Q4 ≈ 56 tok/s, ~7.4 GB on M1 Pro 16 GB, R ([willitrunai](https://willitrunai.com/can-run/gemma-3-4b-on-m1-pro-16gb)) | 10–20 min |
| TTS (Chatterbox Multilingual) | MPS ≈ 2.5× CPU on M1, R ([HF space](https://huggingface.co/spaces/Jimmi42/chatterbox-tts-apple-silicon/blob/main/APPLE_SILICON_ADAPTATION_SUMMARY.md)); Flash MLX RTF 0.78 on M4; assumed RTF 1–3 on M1 Pro | 70–215 min |
| Mix, render, validate | FFmpeg and numpy | 15–30 min |
| **Total** | | **≈ 2.1–6.3 h** vs target ≤ 4.5 h (3×) |

- **Memory:** every model fits on its own when run one at a time. The largest is TranslateGemma 4B with context (~7 GB). The 12B variant is reported to need more than 16 GB at Q4 with context, so the default should be 4B.
- **Time:** borderline; TTS decides it. An MLX port, Turbo or Flash could bring it under target; that needs measuring.
- **Disk — the real constraint.** Bake-off models ≈ 20–35 GB, Python environments ≈ 5–10 GB, one 90-minute job ≈ 15 GB (several full-length 48 kHz float WAVs plus the source). That does not fit comfortably in 51 GB. Recommend ≥ 100 GB free, or putting `DATA_DIR` and the model caches on an external SSD.

## 4. Speaker identity

- community-1 improves speaker counting and assignment over 3.1 and outputs exclusive diarization. DER is around 11% on VoxConverse (R; [pyannote benchmark](https://www.pyannote.ai/benchmark)). VoxConverse (debates, news) is the closest public proxy; no drama or Turkish benchmark was found.
- Drama adds overlap, music under speech, shouting and whispering, many one-line speakers and the same actor across scenes. Expect more speaker confusion than in benchmarks.
- Verdict: the main cast's identity is realistic with whole-file diarization **plus** the mandatory cast review (merge/split/ignore) that SPEC §3.1 already requires. Without review it is uncertain. Minor and crowd speakers will stay noisy; they are handled by `minor` / `ignore`.

## 5. Turkish → English cloning consistency

- Chatterbox Multilingual V3 (vendor claim, V): better speaker similarity and fewer hallucinations than v2, and "voice identity and accent hold more consistently across language switches".
- README guidance (V): if the reference language differs from the target, outputs "may inherit the accent of the reference clip's language. To mitigate this, set cfg_weight to 0." Defaults are exaggeration 0.5, cfg_weight 0.5.
- Fixed seeds give reproducible output for the same input. Drift across separate generations is reported in long-form use, and practitioners batch by character to catch it (R; [Chatterbox-TTS-Server](https://github.com/BrunBrand/Chatterbox-TTS-Server-mt), [HackerNoon](https://hackernoon.com/how-to-keep-an-ai-voice-consistent-across-every-video-clip)).
- No published metric covers consistency across hundreds of segments, or Turkish-reference → English quality.
- Backup: Qwen3-TTS (Apache-2.0). It does not speak Turkish, but here it only needs to *hear* a Turkish reference and *speak* English, so it may still work. It may need a reference transcript in a supported language, which must be tested.
- Verdict: unproven, and the highest product risk. The Phase 0 TTS bake-off (SPEC §17) is the deciding experiment.

## 6. Background preservation

- Sound Demixing Challenge 2023, cinematic track, on real movies (CDXDB23): the best system trained **only on DnR** gained just 1.8 dB SDR over the baseline, while the best unrestricted-data system gained 5.7 dB. "A major source of this improvement was making the simulated data better match real cinematic audio." (V; [SDX23 CDX](https://arxiv.org/pdf/2308.06981))
- The license-clean models (TIGER-DnR, Bandit v2) are DnR-trained, so expect audible Turkish residue in the background or lost effects in some scenes.
- Verdict: unproven. "Acceptable" needs listening tests on real clips. SPEC §10's `speech_mask_ducked_original` mode (voice-over style) is the guaranteed floor.

## 7. Realistic multi-speaker clip

- Prior art with the same shape exists: Python-Autodub (Demucs + pyannote + F5-TTS, [Pinokio](https://pinokio.co/apps/github-com-daniel-mclarty-python-autodub)), ViDubb ([GitHub](https://github.com/medahmedkrichen/ViDubb)), pyVideoTrans, YouDub. None is license-clean end to end (for example, F5-TTS weights are non-commercial). None reports Turkish → English quality.
- Verdict: cannot be answered without rights-cleared multi-speaker Turkish footage, which does not exist in the repo yet.

## 8. Proposed spec changes (not applied; need approval)

1. Q-18 resolved: Chatterbox Multilingual V3 and Nano exist. Add Chatterbox Flash to the bake-off.
2. TranslateGemma default 4B; 12B only if Phase 0 shows it fits.
3. Prefer Bandit v2 if its weights license is permissive (cleanest training data). Record TIGER-DnR's training-data caveat in `models.lock.json` notes.
4. Audio-event tagger candidate: AST (BSD-3-Clause).
5. Diarization speed option: the CoreML port of community-1 (license check first).
6. QC embedder must run in the TTS environment (torch 2.6), via ONNX Runtime or Chatterbox's encoder.
7. SPEC §18: disk requirement (≥ 100 GB free recommended; external SSD allowed for data and caches).

## 9. Free remote GPU options (owner asked, 2026-10-05)

| Option | Free allowance | Hardware | Can a run be started programmatically? | Terms / catches | Tag |
| --- | --- | --- | --- | --- | --- |
| **Kaggle Notebooks** | 30 GPU-h per week, fixed | 2× T4 (16 GB each) or 1× P100 16 GB | **Yes**: `kaggle kernels push` with an accelerator (T4/P100) runs a script on Kaggle; poll the status; `kaggle kernels output` downloads results. Inputs go up as private Kaggle Datasets. | 12 h per session; 20 GB saved output (`/kaggle/working`) plus scratch disk; internet needs phone verification. Terms reportedly limit use to "internal, personal, non-commercial use, and not on behalf of or for the benefit of any third party"; **not verified** (page is JS-rendered); read [kaggle.com/terms](https://kaggle.com/terms) yourself. | R |
| **Lightning AI** | 15 credits per month (≈ 80 GPU-h on spot) | T4 / A10, up to 2 GPUs | Studio-based; SDK exists | Phone verification, no card | R ([gmicloud](https://www.gmicloud.ai/en/blog/best-free-gpu-cloud-options-for-ai-startups-and-researchers)) |
| **Modal** | $30 per month in credits (≈ 50 T4-h or 37 L4-h) | T4 $0.59/h, L4 $0.80/h, larger GPUs | **Yes**: serverless Python functions on GPU, best fit for automation | Only $1 credit until a payment method is added (then $30/month); commercial cloud | R ([modal.com/pricing](https://modal.com/pricing), [costbench](https://www.costbench.com/software/ai-gpu-cloud/modal/free-plan/)) |
| Google Colab (free) | Variable, not guaranteed | Usually T4 | No official batch API | Idle disconnects; dynamic limits; unsuitable for unattended runs | R ([hivenet](https://www.hivenet.com/post/google-colaboratory-gpu-complete-guide-to-free-cloud-gpu-access-and-limitations)) |
| Hugging Face ZeroGPU | 5 GPU-min per day (free) | Shared large GPU | Via Spaces | Far too small for batch dubbing | V ([HF docs](https://huggingface.co/docs/hub/spaces-zerogpu)) |
| SageMaker Studio Lab | 4 GPU-h per day | T4 | — | Closed to new customers since 2026-07-30 | R ([gpuperhour](https://gpuperhour.com/blog/free-cloud-gpus-and-credits)) |

Kaggle API accelerator IDs include `NvidiaTeslaT4` and `NvidiaTeslaP100`; free accounts get T4/P100 (R, [Kaggle MCP docs](https://jupyter-mcp-server.datalayer.tech/providers/kaggle)).

**Rough throughput on Kaggle 2× T4** (estimate, not measured). Per 90-minute video: ASR 5–10 min (faster-whisper fp16); diarization 9–18 min (pyannote ≈ 5–10× real time on T4, R ([vexascribe](https://vexascribe.com/pyannote-audio))); separation 5–15; alignment 3–8; translation 10–20; TTS 15–45 (≈ 72 min of audio split across 2 GPUs, assumed RTF 0.4–1.2 per T4); mix, render and validate 10–20; per-session setup 10–20. Total ≈ **1.1–2.6 h per 90-minute video**, i.e. ≈ 0.75–1.75 GPU-h per hour of video.

| Goal | GPU-h needed | Kaggle alone |
| --- | --- | --- |
| 3 h of video in one session | 2.3–5.3 | Fits in one 12 h session |
| 5 h of video in one session | 3.8–8.8 | Fits in one 12 h session |
| 3 h of video every day | 16–37 per week | Borderline against 30 GPU-h/week |
| 5 h of video every day | 26–61 per week | Exceeds the quota at the high end; would need Lightning and/or Modal on top |

Implications:
- **Legal:** if Kaggle's non-commercial / no-third-party wording is confirmed, Kaggle suits personal R&D and the feasibility spikes, but not a commercial product or work done for an employer. Modal and Lightning are commercial clouds whose credits are not restricted that way (their terms still need checking).
- **Privacy:** voices and videos would leave the machine. Use private datasets, delete them after each run, and make sure consent covers third-party processing (SPEC §1.5).
- **Spec impact:** SPEC D-04 / D-56 chose the Mac as the reference machine and dropped Kaggle. Using a free remote GPU means a new decision: the pipeline would run headless (CLI) in a Kaggle or Modal job on Linux + CUDA, which the architecture supports because providers are separate processes.

## 10. Hands-on spikes that would close the gaps

| Spike | Answers | Needs | Effort |
| --- | --- | --- | --- |
| S1 Environments and speed | Q1, Q3 | Permission to create venvs and download ~25–35 GB of models; enough disk | 0.5–1 day |
| S2 TTS bake-off | Q5 | 2–3 consenting Turkish speakers (≥ 2 min each) as references | 1–2 days |
| S3 Real clip | Q4, Q6, Q7 | 1–3 rights-cleared multi-speaker Turkish clips (3–5 min), hand-labelled speaker turns | 1 day |
