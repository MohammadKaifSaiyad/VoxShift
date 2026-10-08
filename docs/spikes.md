# Spike results

Measured results from Phase 0 spikes. Desk research lives in `docs/feasibility.md`. Defaults are not chosen yet; that needs S2 and S3.

## Reference machine (2026-10-07)

The owner's Mac (SPEC §18.1), checked after `brew install ffmpeg`. FFmpeg checks cover SPEC §19 item 11 and Q-08. Test media were synthetic (`testsrc`) and lived in a `mktemp -d` dir that was deleted afterwards.

| Item | Value |
| --- | --- |
| Chip | Apple M1 Pro (8 performance + 2 efficiency cores), arm64 |
| RAM | 16 GB |
| macOS | 27.0.1 |
| Free disk (home volume) | 57 GiB of 460 GiB |
| Tools on PATH | `uv` 0.12.10; `ollama` 0.19.0 (server not running at check time); `ffmpeg`/`ffprobe` 9.0.2 (Homebrew). `deno` absent |

### FFmpeg

- **Version:** `ffmpeg version 9.0.2` and `ffprobe version 9.0.2`, Homebrew (`/opt/homebrew/bin`), built with Apple clang 21.0.0.
- **License flags:** `--enable-gpl` and `--enable-version3` are set, so this is a GPLv3 build. `--enable-nonfree` and any `libfdk` are absent. SPEC §4.4 allows a GPL build here because FFmpeg is installed by the user, run as an executable and not redistributed.
- **External libraries:** libsvtav1, libopus, libx264, libmp3lame, libdav1d, libvmaf, libvpx, libx265, openssl, videotoolbox, audiotoolbox.

| Filter | Present |
| --- | --- |
| `loudnorm` | yes |
| `sidechaincompress` | yes |
| `atempo` | yes |
| `ebur128` | yes |
| `alimiter` | yes |
| `pan` | yes |

`rubberband` (GPL-only; SPEC §4.4 forbids depending on it) is not in this build.

**Encoders:** native `aac` present (`aac_at`, AudioToolbox, also present; SPEC §11 uses native `aac`). `mov_text` present. `libfdk_aac` absent.

### MP4 stream copy (Q-08)

Method: a 3 s `testsrc` 320×240 clip encoded to MKV (WebM for VP9), then `ffmpeg -i in -i t.srt -map 0 -map 1 -c copy -c:s mov_text -movflags +faststart out.mp4` with a one-cue SRT, checked with `ffprobe`.

| Codec | Encoder used | MP4 stream copy (tag) | `mov_text` (tag) | Notes |
| --- | --- | --- | --- | --- |
| h264 | `libx264` | ok (`avc1`) | ok (`tx3g`) | — |
| hevc | `libx265` | ok (`hev1`) | ok (`tx3g`) | `-tag:v hvc1` not needed for the remux; with it the tag is `hvc1`. Playback in Apple players (often reported to need `hvc1`) not tested |
| vp9 | `libvpx-vp9` (WebM input) | ok (`vp09`) | ok (`tx3g`) | No `-strict experimental` needed |
| av1 | `libsvtav1` | ok (`av01`) | ok (`tx3g`) | `libaom-av1` and `librav1e` not in this build |

- Every output lasts 3.000 s and has `moov` before `mdat` (faststart applied).
- Every remux printed one harmless warning: the later `-c:s mov_text` overrides `-c copy` for the subtitle stream.
- Result: all four codecs in the default `MP4_COPY_CODECS` stream-copy into MP4 with `mov_text` subtitles on this build. Synthetic 8-bit clips only; real files (10-bit, HDR, unusual profiles) not tested.

**Deferred:** MPS availability needs torch → spike S4. (S4a shows MPS is available and works with torch 2.6.0.)

## S4a — Chatterbox TTS on the Mac (2026-10-07)

- **Scope:** only Chatterbox Multilingual (D-66). No other model was downloaded.
- **Code:** `scripts/spikes/mac_s4/run_s4a.py`. Results: `scripts/spikes/mac_s4/out/s4a/run1/results.json`. Logs hold indices and character counts only. Audio is git-ignored.
- **Setup:**
  - `chatterbox-tts` 0.1.7, torch 2.6.0, transformers 5.2.0, Python 3.11.16.
  - Model `ResembleAI/chatterbox` at revision `5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18`.
  - Settings as in S3d: `cfg_weight` 0.5, exaggeration 0.5, seed 1000 + line, one warm-up generation excluded.
- **Input:**
  - Reference: 11.8 s of ISLIK `SPEAKER_01` (165.4–177.2 s, one continuous stretch, original mix).
  - Text: the 16 English lines that S3d produced for ISLIK (6–78 characters each).
  - 3 Turkish sentences of our own, for the import check.
- **Process:** the subagent that ran S4a stalled while starting a repeat run. The main agent reviewed run 1 and wrote this section.

| | CPU | MPS |
| --- | --- | --- |
| Load + conditioning | 12.2 s + 12.3 s | 15.4 s + 10.6 s |
| Generation, 16 lines | 290 s for 40.1 s of audio | 276 s for 41.2 s of audio |
| **RTF** (generation ÷ audio) | **7.24** | **6.71** |
| Per-line RTF | 6.5–9.0 | 5.0–9.5 |
| Peak memory | RSS 5.3 GB | RSS 4.8 GB; MPS driver allocation grew from 3.7 to **13.1 GB**; peak process footprint 19.7 GB (on 16 GB, so swapping) |
| Turkish check, 3 sentences | RTF 6.3–6.9 | RTF 11.8–16.7 |
| Ops falling back to CPU | — | none logged |
| Offline (`HF_HUB_OFFLINE=1`, network blocked) | OK | OK |

For comparison, the Kaggle T4 ran the same model on the same film's lines at RTF 1.43–1.60 (S3d) and 1.22–1.30 (S1). The Mac is about 4.5× slower.

**Disk:** venv 1.16 GB (torch 358 MB is the largest package); model 3.2 GB (`t3_mtl23ls_v2.safetensors` 2.14 GB, `s3gen.pt` 1.06 GB); uv cache 1.19 GB (APFS clones shared with the venv). Free disk afterwards: 50 GB.

### Findings

1. **Chatterbox on the M1 Pro is about 7× slower than real time, and MPS barely helps** (RTF 6.7 vs 7.2). Generation is an autoregressive token loop at batch size 1, so the GPU adds little.
2. **90-minute projection (estimate):** 55 min of English speech × 1.3 × RTF 6.71 ≈ **480 min (8 h) for TTS alone**. The whole pipeline's 3× budget is 270 min. This is clearly over the target, which per D-66 means the reference machine must be revisited. Even if a clean rerun halved the RTF, TTS alone would take about 240 min.
3. **MPS memory grows without bound.** The driver allocation rose from 3.7 GB to 13.1 GB over 16 lines, and the process footprint peaked at 19.7 GB on a 16 GB machine. A real provider must free the MPS cache (for example `torch.mps.empty_cache()` per item) or cap it (`PYTORCH_MPS_HIGH_WATERMARK_RATIO`). The swapping may have slowed the MPS run, especially the Turkish check.
4. **Q-33: `pykakasi` and `gradio` are not needed for English or Turkish.**
   - Neither is imported at module import or after English and Turkish generation.
   - With both blocked (`sys.modules[...] = None`), loading the model and generating English and Turkish still work.
   - `pykakasi` is imported only on the Japanese path (`chatterbox/models/tokenizers/tokenizer.py:81`, guarded, with a warning if missing).
   - Not yet tested: installing without them (`--no-deps` with an explicit dependency list). That gets tested when the TTS provider venv is built.
5. **New: a hidden download on every model load.** Chatterbox's multilingual tokenizer imports `spacy_pkuseg` (`tokenizer.py:193`), which downloads `spacy_ontonotes.zip` from GitHub on every load, whatever the language. That bypasses the license gate and offline rule (SPEC §4.2). With `spacy_pkuseg` blocked, only Chinese segmentation is skipped. The TTS environment should exclude `spacy-pkuseg` as well (Q-44).
6. **Forced stops are normal for this model.** Chatterbox's "forced EOS" warning appeared on 10 of 16 lines on CPU and 14 of 16 on MPS, and on 61 of 68 lines on the T4 in S3d. No line had a suspicious duration.

### Caveats

- **Not a clean benchmark:**
  - the Mac ran on battery (90% → 81%);
  - load average was about 10 on 10 cores, from other apps and parallel research subagents;
  - the Mac slept twice during the MPS run (idle sleep 20:33–20:38, lid closed 20:38–20:40).
- **Sleep and timing:** the timer (`time.perf_counter`) does not advance during sleep, so per-line times exclude it, but memory pressure after waking may have slowed some lines.
- **Next step:** a clean rerun (AC power, lid open, `caffeinate`, nothing else running, MPS cache freed per line) would give fairer numbers. It needs no downloads, because the model and venv are kept.
- **Lines:** 16 short dub lines (median about 30 characters), not 20. Short lines carry fixed per-call overhead.

### Run 2 — clean rerun (2026-10-08)

- **Why:** D-87. Same script and venv, same model revision, no downloads. Results: `scripts/spikes/mac_s4/out/s4a/run2/results.json`. How to run: `scripts/spikes/mac_s4/README.md`.
- **Same as run 1:**
  - the 16 English lines and 3 Turkish sentences;
  - `cfg_weight` 0.5, exaggeration 0.5, seed 1000 + line;
  - one warm-up generation, excluded;
  - `HF_HUB_OFFLINE=1` with the socket guard allowing no hosts. No host was attempted.
- **Different from run 1:**
  - **Voice:** Chatterbox's built-in default voice (`model.conds` from the repo's `conds.pt`; `prepare_conditionals` not called), not a cloned film voice (D-84).
  - `pykakasi`, `gradio` and `spacy_pkuseg` are blocked in the model process (D-77, D-88).
  - Memory is freed after every generation, untimed. On MPS: `synchronize`, `gc.collect`, `empty_cache`. On CPU: `gc.collect`.
  - Each run is wrapped in `caffeinate -dimsu`.
- **Process:** a subagent ran run 2 and wrote this subsection. The main agent reviewed it and recomputed the RTFs, the MPS memory peak and the voice and blocking settings from `results.json`.

| Conditions | CPU (09:58–10:04) | MPS (10:06–10:14) |
| --- | --- | --- |
| Power | AC, charging (83% → 86%) | AC, charging (87% → 91%) |
| 1-min load, before → after | 3.12 → 9.66 | 3.42 → 11.16 |
| Lid | open before and after | open before and after |
| Sleep (`pmset -g log`) | No sleep. One 5 s clamshell DarkWake (10:02:08–10:02:13, lid closed briefly) during line 09 | none |
| Process clock lost to sleep | 0 s | 0 s |
| `caffeinate` assertions | held for the whole run (from `pmset -g log`) | held for the whole run |
| Top CPU before | Brave Browser Helper 23%, WindowServer 16%, iTerm2 10%, kernel_task 10%, top 9% | WindowServer 24%, loginwindow 19%, WallpaperAerials 10%, kernel_task 10%, claude.exe 7% |
| Voice | built-in | built-in |

No load wait was needed (load was below 4 at both starts). The "after" loads include the benchmark's own threads.

| | CPU | MPS |
| --- | --- | --- |
| Load | 13.9 s | 15.3 s |
| Warm-up (excluded) | 16.7 s for 3.0 s of audio | 34.7 s for 6.4 s of audio |
| Generation, 16 lines | 238 s for 43.6 s of audio | 322 s for 49.8 s of audio |
| **RTF** (generation ÷ audio) | **5.45** | **6.47** (5.64 without line 03) |
| Per-line RTF | 4.98–8.08 (median 5.46) | 4.12–12.33 (median 5.74) |
| T3 speed (speech tokens per second) | 6.0 overall (5.7–6.2 per line) | 5.4 overall (6.8–9.2 per line, except 3.3 and 3.7 on lines 03–04) |
| Time in T3 / S3Gen | 183 s / 55 s | 233 s / 88 s |
| Peak RSS (`/usr/bin/time -l`) | 5.9 GB | 4.8 GB |
| Peak process footprint | 5.0 GB | **27.3 GB** (on 16 GB) |
| MPS driver allocation | — | 3.7 GB after load. Peak 19.4 GB right after a generation. After cleanup: about 4.9 GB through line 02, then 15.6–16.4 GB from line 03 on |
| Turkish check, 3 sentences | RTF 4.99 (5.00, 4.98, 5.00) | RTF 7.86 (5.45, 4.68, 13.13) |
| Forced-EOS / repetition warnings | 15 / 4 of 16 lines | 12 / 3 of 16 lines |
| Cleanup time (not in RTF) | 1.6 s | 4.0 s |
| Ops falling back to CPU | — | none logged |

| Run 1 vs run 2 | Run 1 | Run 2 |
| --- | --- | --- |
| CPU RTF | 7.24 | **5.45** (−25%) |
| CPU per-line RTF | 6.5–9.0 | 5.0–8.1 |
| MPS RTF | 6.71 | 6.47 (−4%); 5.64 without line 03 |
| MPS per-line RTF | 5.0–9.5 | 4.1–12.3 |
| Turkish RTF, CPU / MPS | 6.6 / 13.6 | 5.0 / 7.9 |
| MPS peak driver allocation | 13.1 GB | 19.4 GB |
| MPS peak process footprint | 19.7 GB | 27.3 GB |
| Load (CPU / MPS) | 12.2 s / 15.4 s | 13.9 s / 15.3 s |

**90-minute projection (estimate):**

- 55 min of English speech × 1.3 = 71.5 min of audio to generate.
- On CPU (the faster device): 71.5 × RTF 5.45 ≈ **390 min (6.5 h) for TTS alone**.
- On MPS: 463 min, or 403 min without the run-on line.
- The whole pipeline's 3× budget is 270 min, so TTS alone takes 1.44× the whole budget (run 1's estimate was 480 min).
- To fit TTS alone into 270 min would need an RTF of 3.78 or less. The rest of the pipeline would then have no time left.

#### Findings

1. **Clean conditions made CPU 25% faster (RTF 7.24 → 5.45), but it is still about 5.5× slower than real time.** CPU is the faster device on this Mac. The 90-minute target is still missed by a wide margin (projection above).
2. **MPS is not faster than CPU overall.**
   - On most lines its T3 loop is faster per token (6.8–9.2 vs 5.7–6.2 tokens/s).
   - Its S3Gen stage took longer per audio second (1.76 s vs 1.26 s).
   - One run-on line and memory pressure dominated its total.
3. **Freeing the MPS cache after every line did not keep memory bounded.**
   - Live tensors stayed at 3.25 GB throughout.
   - After the warm-up and lines 00–02, `empty_cache` brought the driver allocation back to about 4.9 GB.
   - After the 378-token line 03 it stayed at 15.6–16.4 GB to the end of the run, and the process footprint peaked at 27.3 GB on a 16 GB machine. A manual `sysctl vm.swapusage` right after the run showed 2.4 GB of swap in use.
   - Cause not investigated. `PYTORCH_MPS_HIGH_WATERMARK_RATIO` was not tested.
4. **MPS line 03 ran on.**
   - It produced 15.1 s of audio (13.2 s non-silent) for a 78-character line. The same line gave 5.7 s on CPU.
   - T3 generated 378 tokens at 3.3 tokens/s, so the line took 127 s, which is 39% of the MPS generation time.
   - The crude length check (characters ÷ 5 + 1.5 s = 17.1 s) did not flag it. Nobody has listened to it. The third MPS Turkish sentence (RTF 13.1) ran later, under the same memory pressure.
5. **The built-in voice works offline, and English and Turkish generate with `pykakasi`, `gradio` and `spacy_pkuseg` blocked** (none were loaded after the Turkish pass).
6. **Forced stops remain the norm** (15 of 16 lines on CPU, 12 of 16 on MPS), as in run 1.

#### Caveats

- **Voice differs from run 1** (built-in vs cloned).
  - Assumption: speed per audio second does not depend on the voice.
  - Chatterbox emits 25 speech tokens per second of audio, so RTF is set by the time per token.
  - Both voices give T3 a 150-token speech prompt.
  - This is not tested beyond that.
  - The voice does change the speech rate, so audio lengths differ between runs.
- **Single run per device.** Sampling differs between devices, so the same lines gave 43.6 s of audio on CPU and 49.8 s on MPS.
- **Lid closed for about 5 s during the CPU run (line 09):**
  - the Mac went to DarkWake, not sleep, and the process clock lost no time;
  - line 09's RTF (5.50) and token rate (5.7/s) match its neighbours.
- **CPU caffeinate check:** the script's live caffeinate check recorded nothing on the CPU run (it matched the wrong PID). It was fixed before the MPS run, and `pmset -g log` confirms the CPU run's assertions were held from 09:58:53 to 10:04:32.

## S1 — model families on Kaggle (run v4, 2026-10-05)

- **Setup:** Kaggle, 2× Tesla T4 (16 GB each; benchmarks used GPU 0 only), 33 GB RAM. Every model family ran in its own uv venv (Python 3.11).
- **Code:** `scripts/spikes/kaggle_s1/run_s1.py`. Raw output: `scripts/spikes/kaggle_s1/out/s1/` (`results.json`, `logs/`, `audio_samples/`).
- **Run time:** 27 minutes, including all installs and downloads.
- **Test audio:** fully synthetic, so no personal data was used:
  - Chatterbox's built-in voice reading 12 Turkish sentences, plus a pitch-shifted copy as a second speaker;
  - sine-tone "music" mixed 12 dB below the dialogue;
  - one 86 s clip and one 426 s clip.

### Results

| Family | Load s | Speed on T4 | 90-min projection (1× T4) | Peak GPU | Quality signal |
| --- | --- | --- | --- | --- | --- |
| Silero VAD (CPU) | <0.1 | 58–63× real time | 1.4 min | — | Recall metric not usable (see caveats) |
| faster-whisper large-v3-turbo (fp16) | 19 | 16–37× | 2.4 min | 4.1 GB | Turkish WER 20–26% (TTS + ASR combined, see caveats); language ID `tr` p = 0.999 |
| faster-whisper large-v3 (fp16) | 21 | 12–13× | 7.1 min | 4.1 GB | Turkish WER 16–31% |
| WhisperX alignment (Turkish) | 5.6 | 4.9× on speech | 11 min | 1.9 GB | Default model is `mpoyraz/wav2vec2-xls-r-300m-cv7-turkish`; 123 of 123 words timed, digits included |
| pyannote community-1 (4.0.7, run v5) | 4.8 | 19–24× | 3.7 min | 1.6 GB | Found **1 speaker instead of 2**: the synthetic speaker B is only a pitch-shifted copy of A (see caveats). Output exposes `speaker_embeddings` (per speaker, 256-d) and `exclusive_speaker_diarization` |
| TIGER-DnR | 1.7 | **1.2×** (slow) | **73 min** | 2.0 GB | Synthetic mix not informative (see caveats) |
| Demucs htdemucs | 2.8 | 13–20× | 4.5 min | 0.6 GB | Synthetic mix not informative |
| AST tagger | 3.9 | 38–62× | — | 0.6 GB | Labels Speech, Music (4 of 9 windows), and "Speech synthesizer" |
| opus-mt tr→en | 8.9 | 12 sentences in 0.9 s | <1 min | 0.7 GB | chrF 73.3 vs reference |
| TranslateGemma 4B (Ollama) | 88 (first call) | 56 tok/s; 0.46 s per sentence | 9 min | 3.7 GB | chrF 74.7 |
| TranslateGemma 12B (Ollama) | — | 18 tok/s; 1.42 s per sentence | ~28 min | 8.8 GB | chrF 74.6 (no better than 4B here) |
| Chatterbox Multilingual (0.1.7), Turkish | 39 | RTF 1.18 (0.85× real time) | — | 3.7 GB | — |
| Chatterbox Multilingual, English, cloned | — | RTF 1.22–1.30 | **87 min** (≈ 44 min on 2 GPUs) | 3.7 GB | English WER 1.2–2.3% (very intelligible) |
| Chatterbox Turbo, English, cloned | 39 | RTF 0.49 (2× real time) | 35 min | 3.3 GB | Not measured |

The TTS projection assumes ~55 min of English speech × 1.3 for audition, drift-gate regenerations and rewrites.

**90-minute estimate on Kaggle T4** (all stages measured, plus ~15 min for mix, render and validation and ~10 min session setup):
- With Demucs and the Multilingual TTS on one GPU: **≈ 2.4 h (1.6× video length)**; ≈ 1.7 h if TTS uses both T4s. This is within the ≤ 3× target (SPEC §2).
- With TIGER-DnR instead of Demucs: ≈ 3.5 h (2.4×).
- These are Kaggle T4 numbers. **The Mac has not been measured.**

### Findings

1. **Q1, the models work together:** all 9 families install and run side by side in separate venvs (1–43 s each from a warm cache; 2.7–8.8 GB per venv with CUDA torch). Fixes needed along the way:
   - every venv needs `setuptools<81`, because Perth and Lightning import `pkg_resources`;
   - benchmark files must not shadow library names;
   - Ollama's installer needs `zstd`.
2. **`cfg_weight=0` makes cloned English clips 28% longer** than `cfg_weight=0.5` (69.7 s vs 54.3 s for the same 12 sentences). The hypothesis in D-32 holds on this voice. It matters for fitting (SPEC §9): `cfg_weight=0` would push many more segments into rewrites or `atempo`. S2 must weigh accent against length.
3. **The Perth watermark survives:** detected (1.0) on the raw clip, after `atempo=1.2`, after AAC 128k, and after both. SPEC §19.7 is answered for these transforms; mixing is not yet tested.
4. **TranslateGemma 4B matches 12B** on these sentences (chrF 74.7 vs 74.6) at 3× the speed and less than half the memory. opus-mt is close behind (73.3) and much faster.
5. **`keep_alive=0` works:** Ollama's GPU memory went from 3.7 GB / 8.8 GB to 0 after unload (SPEC §19.10).
6. **TIGER-DnR is slow:** 1.2× real time on a T4, about 15× slower than Demucs, despite its tiny parameter count.
7. **Chatterbox Turbo is 2.5× faster** than Multilingual. Its cross-lingual accent from a Turkish reference is unknown (S2).
8. **ASR exposes `avg_logprob`, `no_speech_prob` and `compression_ratio`** (SPEC §19.4, faster-whisper path).
9. **Kaggle secrets are unavailable in CLI-started runs** (`ConnectionError` from the secrets service). Gated models need a run started from the Kaggle editor (**Save & Run All**), which worked in run v5.
10. **The pyannote pipeline returns per-speaker embeddings** (256-d) and exclusive diarization (SPEC §19.3). Per-segment embeddings for the identity second pass (SPEC §3.1) still need the embedding model, which can run in the same venv.
11. **Similar voices can merge:** a pitch-shifted copy of the same synthetic voice was not separated from the original. This is not a fair test of distinct real speakers, but it supports the mandatory cast review (split action, edge case 12).

### Caveats

- **Synthetic audio.** The quality columns say little about real Turkish drama; S2 and S3 answer that.
- **Turkish WER (16–31%) mixes TTS errors with ASR errors.** Chatterbox may skip or misread words, and the reference text has digits ("1990", "3"). A clean ASR measure needs real speech with human transcripts (S3).
- **VAD recall (71%) is a measurement artifact.** The ground truth treats each whole generated clip, including its leading and trailing silence, as speech. The same metric was 95% on tighter espeak clips in run v3.
- **Separation SI-SDR is uninformative.** Dialogue scored 16.5 dB for both separators, the same as the unprocessed mix (16.8 dB); background scored −1 to −2 dB. Sine tones and white noise are not film music. Only the speed numbers are usable.
- **Diarization accuracy is untested.** The two test "speakers" are one synthetic voice and its pitch-shifted copy, so finding one speaker says nothing about real actors. Speed and output format are the usable results. A fair test needs genuinely different voices: S3 (real clip), or an optional extra run with several distinct synthetic voices.
- **One run per stage, one GPU type.** Not the reference Mac (open question Q-23).
- **Chatterbox version.** `chatterbox-tts` 0.1.7 loaded the multilingual model from `ResembleAI/chatterbox`; whether those weights are the V3 release is not confirmed (Q-18 stays open).

## S3 — rough end-to-end dub of three CC-BY Turkish short films (run v3, 2026-10-06)

- **Setup:** Kaggle T4. Clips: ISLIK (7:18, 3 credited actors), Teneke (8:36, 2 main characters + street music), Hediye (8:25, 2 main characters + sound effects). Sources and use limits: `docs/footage.md`.
- **Code:** `scripts/spikes/kaggle_s3/run_s3.py`. Output: `scripts/spikes/kaggle_s3/out/s3/`:
  - `review_<clip>.md`: Turkish, English and fit for each segment;
  - `audio/`: dubbed mixes and stems (git-ignored);
  - `results.json`.
- **Run time:** about 40 min of GPU time for all three films.
- **Not a real dub:** the pipeline was naive on purpose. It had no translation budget, no rewrite rounds, no TTS silence trimming, no cast review and no bank voices, so it shows the raw behaviour that SPEC §3, §8 and §9 are meant to correct.
- **Bug:** the final English re-transcription stage did not run (a stage-name bug in the spike, now fixed).

### Results

| | ISLIK | Teneke | Hediye |
| --- | --- | --- | --- |
| Speech in the film (after segmenting) | 31 s | 31 s | 55 s |
| Diarization speakers (dialogue stem / original) vs real | **7 / 7 vs 3** | **4 / 3 vs 2** | **6 / 5 vs 2** |
| ASR words (dialogue stem / original) | 69 / 62 | 88 / 55 | 146 / 84 |
| Segments; speakers with < 2 s of clean speech (default voice) | 15; 2 of 6 | 33; 1 of 3 | 38; 1 of 6 |
| Reference length per cloned speaker | 3.4–6.2 s | 2.8–4.9 s | 2.2–10.5 s |
| TTS RTF (cfg 0.5) | 1.27 | 1.39 | 1.49 |
| Median TTS length ÷ available slot | 1.17 (cfg 0: **1.64**) | **2.07** | **1.79** |
| Segments needing tempo > 1.10× (SPEC target ≤ 15%) | **64%** (cfg 0: 79%) | **93%** | **89%** |
| Segments truncated | 21% (cfg 0: 43%) | 47% | 43% |
| Voice consistency within a speaker (cosine to own centroid; mean, speakers with ≥ 4 clips) | 0.81–0.84 | 0.68 | 0.73–0.85 |
| Similarity between different speakers' voices | 0.02–0.46 | −0.09–0.19 | −0.03–0.50 |
| Similarity of the English output to the Turkish reference | 0.47–0.69 | 0.41–0.52 | 0.39–0.63 |

**Speed:** Demucs ran at 21× real time and TIGER-DnR at 1.3×. ASR ran at 49–114× real time (Silero gating skips non-speech), diarization at 20–23×, and translation took 6–10 s per film once loaded.

### Findings

1. **Speaker identity is not stable without review.** Diarization found 2–3.5× more speakers than the films have, in both the dialogue stem and the original, and some sentences flip speaker mid-way. Splitting one actor into several labels is the dominant error. The mandatory cast review (SPEC §3.1) is essential. A "set number of speakers" action that reruns diarization with `num_speakers` would fix most of it.
2. **Fitting fails without the spec's timing machinery.** 64–93% of segments needed tempo > 1.10× (target ≤ 15%), and 21–47% were truncated. Causes:
   - segments of one or two words ("Aç", "Bak", "canım");
   - leading and trailing silence in TTS clips (not trimmed);
   - verbose translations;
   - no rewrite rounds.
   The translation budget and rewrite rounds (SPEC §8.14, §9) are required, not optional. TTS silence trimming and merging of very short fragments must be added.
3. **The translation model sometimes explains instead of translating.** On one garbled line, TranslateGemma returned a paragraph of alternatives ("This phrase is difficult to translate directly… It could mean: …"). Validation must reject commentary (multiple lines, bullets, length > ~2× the source) and fall back. Ordinary lines translated well, idioms and profanity included.
4. **The hallucination filters missed a garbled opening.** Hediye's first 20 s (probably a background announcer or music) was transcribed as nonsense with good confidence, and 0 segments were flagged. Per-segment checks (audio-event tagging, word probability, language ID) are needed on top of Whisper's scores.
5. **Voices stay distinct and fairly consistent once cloned.** Within a speaker, voices score 0.68–0.93; between speakers, mostly < 0.35. But the 10th-percentile score within a speaker is 0.57–0.69, so some segments drift; the drift gate (SPEC §3.2.7) is justified. Two speakers who both fell back to the single default voice scored 0.86 against each other, i.e. sounded the same, which confirms the need for **distinct** bank voices per actor (SPEC §3.3).
6. **The Turkish reference is a poor yardstick for the English output** (cosine 0.39–0.69). This confirms D-08: gate drift against the TTS centroid, not the reference.
7. **`cfg_weight=0` vs 0.5 (ISLIK):** cfg 0 scored slightly higher against the reference (+0.04 to +0.11 for 3 of 4 speakers) and on consistency (+0.02), but produced 9% more audio and twice as many truncations. Listening must decide whether the accent gain is worth it.
8. **References are short in short films:** 2–6 s for most speakers, against the 10–15 s target (SPEC §3.2.2). Features will have more speech per actor, and merging over-split speakers adds more.
9. **ASR on the dialogue stem finds 11–75% more words** than on the original, but whether those words are real or hallucinated needs a human check of `review_*.md`. `ASR_INPUT` is still open (SPEC §19.13).
10. **Chatterbox warnings:** 17 forced stops for token repetition and 5 failed generations, mostly on very short texts. More evidence that tiny segments should be merged before TTS.

### Caveats

- Short films with little dialogue (31–55 s per film), so speaker statistics rest on few segments.
- No ground-truth transcript or speaker labels. Speaker counts are compared with the film credits, which may omit minor voices.
- Naive pipeline: these numbers are the baseline the spec's mechanisms must improve. They are not the expected final quality.

## S3b — S3 with the spec's mechanisms (run v2, 2026-10-06)

- **Code:** `scripts/spikes/kaggle_s3b/run_s3b.py`. Output: `scripts/spikes/kaggle_s3b/out/s3b/` (`summary.md`, `review_<clip>.md`, `audio/<clip>_dub.m4a`).
- **Same films and decided models** (D-62, D-63, D-64), plus every mechanism listed in `scripts/spikes/kaggle_s3b/README.md`.
- **Run time:** 2 h 52 min, of which 2 h 32 min was the Qwen3 bug (finding 1). The rest of the pipeline took about 20 min for all three films.

| | ISLIK | Teneke | Hediye |
| --- | --- | --- | --- |
| Speakers: auto → fixed count | 7 → 3 | 4 → 2 | 5 → 2 |
| Segments; under 1 s; median length | 9; 0; 2.1 s | 26; 11; 1.2 s | 29; 2; 1.9 s |
| Lines needing tempo > 1.10×, S3 → S3b | 64% → **67%** | 93% → **54%** | 89% → **50%** |
| Lines truncated, S3 → S3b | 21% → 22% | 47% → **17%** | 43% → **19%** |
| Lines overflowing into following silence | 33% | 29% | 15% |
| Voice chars/s from audition (per speaker) | 14.3, 15.3 | 18.0, 9.4 | 17.5, 19.4 |
| Voice consistency within a speaker (mean; p10) | 0.78–0.82; 0.69–0.80 | 0.70–0.74; 0.65–0.71 | 0.71–0.78; 0.65–0.72 |
| Similarity between speakers' voices | 0.34 | 0.13 | 0.22 |
| English re-transcription of the dub | **detected Turkish** (p 0.62) | English 0.91, WER 27% | English 0.84, WER 13% |
| Diarized speech vs speech inside dubbed segments | 49.8 s vs 30.0 s | 84.0 s vs 34.2 s | 85.4 s vs 58.0 s |

### Findings

1. **Qwen3 failed completely, through a bug in the spike.** Every reply was a long reasoning trace (~15,000 characters, ~1.5 min per call), so all 61 translations were rejected as multi-line and all 32 rewrites failed. The `think: false` switch did not take effect; the `qwen3:4b` tag probably points at a thinking-only release. As a result the **rewrite rounds were never actually tested**, and that model step cost 2.5 h of GPU. Fix: use an explicit non-thinking instruct tag and strip everything up to `</think>`; also cap `num_predict`.
2. **The mechanisms that did work halved the timing misses** on Teneke and Hediye (93% → 54%, 89% → 50%) and cut truncation by more than half. Contributing changes:
   - the fixed speaker count;
   - flip smoothing;
   - fragment merging;
   - TTS silence trimming (0.1 s per line);
   - TranslateGemma's budget (57% of lines within budget, 4.6 characters over on average, no commentary).
   ISLIK did not improve (9 lines only). This is still far from the ≤ 15% target. The missing pieces are working rewrite rounds and better budget compliance.
3. **A fixed speaker count fixes over-splitting** (7 → 3, 4 → 2, 5 → 2), and voices stay distinct (between-speaker 0.13–0.34) and consistent (within-speaker 0.70–0.82; at most one line per speaker below 0.6). This supports cast review with a "number of speakers" action.
4. **New risk: untranscribed Turkish leaks into the dub.** Diarization hears much more speech than ends up in dubbed segments (for example ISLIK 49.8 s vs 30.0 s). SPEC §10.2's non-verbal lay-back puts everything outside dubbed spans back at −6 dB, including Turkish speech that ASR missed. On ISLIK, Whisper then identified the whole dub as Turkish. Required changes:
   - lay back only non-speech (VAD- and tagger-aware);
   - add a **speech coverage** metric (dubbed ÷ detected speech) with `needs_review`;
   - add a second ASR pass on detected speech that no segment covers.
5. **ASR is not stable on hard audio:** ISLIK gave 44 words this run vs 69 in S3, with the same model and input. faster-whisper's temperature fallback samples randomly. Make decoding deterministic (temperature 0 only, or a seeded fallback) and rely on the coverage pass.
6. **No singing in these films** (maximum AST singing probability 0.03–0.09 on the dialogue stems), so Q-24 is still untested on real singing.
7. **Voice speaking rates differ by 2×** (9.4–19.4 chars/s). Budgets must be per voice, as SPEC §8.14 says; one global rate would be wrong.

## S3c — S3b with its failures fixed (run v2, 2026-10-06)

- **Code:** `scripts/spikes/kaggle_s3c/run_s3c.py`. Output: `scripts/spikes/kaggle_s3c/out/s3c/`.
- **Run time:** 33 min including installs; about 25 min of processing for 22 min of film audio.
- **Fixes:**
  - Qwen3-4B-Instruct-2507 (no thinking mode);
  - speech-aware lay-back with a coverage metric;
  - deterministic ASR plus a second pass on missed speech.

| | ISLIK | Teneke | Hediye |
| --- | --- | --- | --- |
| Lines needing tempo > 1.10×, S3 → S3b → S3c | 64% → 67% → **42%** | 93% → 54% → **54%** | 89% → 50% → **39%** |
| Truncated, S3 → S3b → S3c | 21% → 22% → **5%** | 47% → 17% → **21%** | 43% → 19% → **14%** |
| Of which overflow into silence (no speed-up beyond 1.25×) | 37% | 17% | 22% |
| Median TTS length ÷ slot | 1.00 | 1.15 | 0.92 |
| Segments; under 1 s | 19; 2 | 25; 9 | 40; 7 |
| Speech coverage (dubbed + kept + non-verbal ÷ VAD speech) | 77% | 86% | 79% |
| Untranscribed speech muted | 8.8 s | 3.7 s | 11.4 s |
| English re-transcription of the dub (language; WER) | **en**; 12% | **en**; 43% | **en**; 21% |
| ASR second pass: missed VAD regions → words added | 5 → 13 | 1 → 2 | 9 → 14 |
| Rewrite rounds 1 / 2: rewritten of those over 1.10× | 6/11, 0/8 | 6/14, 0/13 | 12/21, 3/14 |
| Voice consistency within main speakers (mean; lines < 0.6) | 0.72–0.74; 0 | 0.67–0.69; 5 | 0.66–0.74; 5 |

### Findings

1. **The spec's mechanisms stack.** From the naive S3 to S3c:
   - lines needing > 1.10× fell from 64–93% to 39–54%;
   - truncation fell from 21–47% to 5–21%;
   - the median line now fits its slot;
   - every dub is recognized as English.
   The target of ≤ 15% (SPEC §2) is **not reached** on these clips.
2. **What's left is mostly very short lines in rapid exchanges.** "bak." gave 4.5× its slot, "Oğlum" 1.6×, "Darbuka." 2.5×: English TTS needs ~0.6–1 s, and these sources give 0.3–0.5 s with no silence to overflow into. Teneke has 9 of 25 segments under 1 s. Needs a short-utterance policy (an owner decision):
   - a higher tempo cap for clips under 1 s;
   - pre-roll into preceding silence;
   - or keeping the original for one-word interjections.
   Feature films with longer speeches may behave better; unmeasured.
3. **Qwen3-4B-Instruct: fast and budget-compliant, but weaker on meaning.**
   - **Speed and compliance:** 0.67 s per call, 78% of lines within budget (TranslateGemma: 57% in S3b), no commentary.
   - **Meaning errors on idioms and slang**, for example "Adam mı yiyorsun sen?" → "Are you eating a man?" (TranslateGemma in S3: "Are you out of your mind?"), "Aç mısın oğlum?" → "Open up, buddy?".
   - **Turkish left in output:** "Aç siktir lan." returned unchanged; one rewrite gave "Son, buraya yaklaş.".
   This favours the spec's split: TranslateGemma translates, an instruct model only shortens. Validation must also reject output that equals the source or contains Turkish-only letters (ç ğ ı ö ş ü).
4. **TranslateGemma was not fairly tested in S3c** (spike bug). The latency guard averaged in a ~90 s model reload on its first call and dropped it after 4 lines. The guard must exclude the first call after a load.
5. **Whisper's classic Turkish phantom lines appeared:** "İzlediğiniz için teşekkür ederim" and "Altyazı M.K.", most likely from the second pass, which runs without VAD gating. This validates SPEC §8.5's blacklist file, which S3c did not implement. The second pass needs the same filters plus the blacklist.
6. **Speech-aware lay-back stopped the Turkish leak** (all dubs detected as English). Coverage is 77–86%. Whether the muted 3.7–11.4 s is missed dialogue or vocal noise needs listening.
7. **Rewrite round 2 adds little** (0–3 lines): once a line is near its budget, the 4B model cannot shorten it further without losing meaning. A larger rewrite model, or the short-utterance policy, is the next lever, not more rounds.
8. **Voices are distinct and fairly consistent.** Between speakers 0.07–0.41. Within a speaker, up to 4–5 of 14–22 lines fall below 0.6 cosine, so the drift gate (SPEC §3.2.7) would regenerate about 10–25% of a main actor's lines. That cost belongs in the speed estimate.

## S3d — translation split and short-line rule (run v2, 2026-10-07)

- **Code:** `scripts/spikes/kaggle_s3d/run_s3d.py`. Output: `scripts/spikes/kaggle_s3d/out/s3d/`. `review_<clip>.md` shows TranslateGemma and Qwen3 side by side.
- **Run time:** 34 min.
- **Changes from S3c:**
  - TranslateGemma translates; Qwen3-4B-Instruct only shortens (and is the fallback);
  - validation rejects untranslated and half-Turkish output;
  - phantom-line blacklist;
  - D-65 short-line rule.

| | ISLIK | Teneke | Hediye |
| --- | --- | --- | --- |
| Lines needing tempo > 1.10×, S3 → S3b → S3c → S3d | 64 → 67 → 42 → **38%** | 93 → 54 → 54 → **32%** | 89 → 50 → 39 → **45%** |
| Truncated, S3 → S3b → S3c → S3d | 21 → 22 → 5 → **19%** | 47 → 17 → 21 → **9%** | 43 → 19 → 14 → **28%** |
| Short lines (< 1 s): count; pre-roll used; tempo > 1.25 | 1; 1; 1 | 5; 2; 2 | 4; 2; 1 |
| English re-transcription (language; WER) | en; **7%** | en; 43% | en; **16%** |
| Speech coverage; untranscribed muted | 67%; 12.5 s | 83%; 4.6 s | 80%; 11.0 s |
| ASR segments dropped: blacklist; strict pass 2 | 1; 1 | 0; 0 | 0; 5 |

**Translators on the same 68 lines:**

| | Within budget | Mean chars over budget | Generation time per line | Rejected |
| --- | --- | --- | --- | --- |
| TranslateGemma 4B | 52% | 5.3 | 0.81 s | 1 commentary |
| Qwen3-4B-Instruct | 66% | 1.7 | 0.47 s | 1 commentary |

### Findings

1. **TranslateGemma is clearly the better translator; Qwen3 is the better shortener.** Side by side on idioms and slang:

   | Turkish | TranslateGemma | Qwen3 |
   | --- | --- | --- |
   | "Adam mı yiyorsun sen?" | "Are you serious?" | "Are you eating a man?" |
   | "Aç mısın oğlum?" | "Hungry, son?" | "Ach, son?" |
   | "Bak" | "Look." | "Bak" (untranslated) |

   This confirms the spec's split: TranslateGemma translates, an instruct model rewrites. Qwen3's rewrites save time but can turn telegraphic ("History vis. below", "Yes, different game."). A larger rewrite model is the obvious next lever.
2. **The split costs timing on two films.** TranslateGemma's longer lines raised truncation on ISLIK (5 → 19%) and Hediye (14 → 28%), even though rewrite round 1 now shortens 64–82% of the over-long lines. Teneke improved (truncation 21 → 9%, over 1.10× 54 → 32%), helped by the short-line rule and better translations.
3. **The short-line rule works where it applies.** 10 short lines; pre-roll used on 5, tempo above 1.25 on 4. The worst S3c case, "bak." (4.5× its slot), now overflows briefly into silence instead of being truncated.
4. **Intelligibility of the final dub improved** (WER 7% ISLIK, 16% Hediye; 43% Teneke, which has rapid slang exchanges). All dubs are detected as English with p 0.80–0.97.
5. **The blacklist and strict second pass removed phantom lines** (7 ASR segments dropped), at a cost in coverage on ISLIK (77 → 67%). Hediye's opening announcer lines (garbled ASR) still get dubbed and truncated, inflating its numbers. Cast review's "ignore" action is the remedy.
6. **The target (SPEC §2: ≤ 15% of lines over 1.10×) is still not met** on these short films (32–45%; truncation 9–28%). The per-line greedy fitting of SPEC §9 has reached its limits on rapid exchanges. Remaining levers:
   - a **timeline solver** that may delay the next line by a fraction of a second when it has slack ("ripple"), instead of truncating the current one;
   - a larger rewrite model;
   - reconsidering whether SC2–SC4 thresholds suit drama dialogue (owner decision after golden clips, Phase 11).
7. **The blacklist cannot match a capital "İ" (spike bug, found afterwards).** Python's `"İ".lower()` returns `"i̇"` (two code points), so "İzlediğiniz için teşekkür ederim" never matches "izlediğiniz için teşekkür". The phantom line did not appear in S3d only because the stricter pass-2 scores removed it. The real implementation must casefold Turkish first (`İ→i`, `I→ı`).

### Still to do

- **Listen** to `scripts/spikes/kaggle_s3/out/s3/audio/`:
  - `*_cfg05_separated` vs `*_ducked`;
  - `QJH3CCrjda4_cfg05_*` vs `QJH3CCrjda4_cfg00_*` (accent);
  - `QJH3CCrjda4_demucs_dialogue` vs `QJH3CCrjda4_tiger_dialogue` (separation).
- **S3b:** rerun with silence trimming, fragment merging, budgeted translation with validation, rewrite rounds and a fixed speaker count, to measure how far the spec's mechanisms close the gap.
- **S2 (voice cloning)** and **S3 (real clip)**: need consented Turkish voices and rights-cleared footage.
- **Listen** to `out/s1/audio_samples/`: `en_clone_cfg00` vs `en_clone_cfg05` (accent and pacing), and `tiger_dialogue_60s`.
