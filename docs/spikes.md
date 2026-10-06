# Spike results

Measured results from Phase 0 spikes. Desk research lives in `docs/feasibility.md`. Defaults are not chosen yet; that needs S2 and S3.

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

### Still to do

- **S2 (voice cloning)** and **S3 (real clip)**: need consented Turkish voices and rights-cleared footage.
- **Listen** to `out/s1/audio_samples/`: `en_clone_cfg00` vs `en_clone_cfg05` (accent and pacing), and `tiger_dialogue_60s`.
