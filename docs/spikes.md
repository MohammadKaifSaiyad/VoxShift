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

### Still to do

- **Listen** to `scripts/spikes/kaggle_s3/out/s3/audio/`:
  - `*_cfg05_separated` vs `*_ducked`;
  - `QJH3CCrjda4_cfg05_*` vs `QJH3CCrjda4_cfg00_*` (accent);
  - `QJH3CCrjda4_demucs_dialogue` vs `QJH3CCrjda4_tiger_dialogue` (separation).
- **S3b:** rerun with silence trimming, fragment merging, budgeted translation with validation, rewrite rounds and a fixed speaker count, to measure how far the spec's mechanisms close the gap.
- **S2 (voice cloning)** and **S3 (real clip)**: need consented Turkish voices and rights-cleared footage.
- **Listen** to `out/s1/audio_samples/`: `en_clone_cfg00` vs `en_clone_cfg05` (accent and pacing), and `tiger_dialogue_60s`.
