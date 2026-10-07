# Phase 0 Completion Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish Phase 0 (SPEC §17): every §19 item is measured, decided or moved to `docs/OPEN_QUESTIONS.md`, and the exit files exist, so the owner can approve Phase 1.

**Architecture:** No application code. Measurements are throwaway spike scripts in `scripts/spikes/`: Kaggle T4 for heavy comparisons, the Mac for reference-machine numbers. Results go to `docs/spikes.md`; decisions go to `docs/DECISIONS.md` and `docs/SPEC.md`; licensing goes to `models.lock.json` and the license files.

**Tech Stack:** uv (Python 3.11 per provider venv), Kaggle CLI ≥ 1.8 via `uvx --python 3.12`, Ollama, Hugging Face Hub API, FFmpeg (Homebrew).

**Spec:** `docs/SPEC.md` §17 (Phase 0), §19 (verify list), §4 (licensing), §5 (stack), §6.5 (config). Open items: `docs/OPEN_QUESTIONS.md`.

## Execution (owner decision, 2026-10-07)

The plan runs subagent-driven, with review by the main agent:
1. Each task goes to a subagent with a bounded scope.
2. The subagent investigates, implements and tests only within that task. It does not commit.
3. The main agent reviews the diff and the results.
4. The main agent verifies them against `docs/SPEC.md` and `docs/DECISIONS.md`.
5. Only then does the main agent commit and move to the next task.

Subagents must not decide on their own:
- licensing exceptions;
- model substitutions;
- architecture changes;
- acceptance criteria;
- dependency exceptions.

They report these to the main agent, which takes them to the owner.

## Status (2026-10-07)

- **Done:** Task 1 (commit `6495eda`) and Task 2 (D-69 to D-80).
- **Decided:** Q-01 to Q-37 (D-66 to D-81). Kaggle terms are recorded in `docs/platform_terms.md`.
- **Open:** Q-17, Q-18, Q-19, Q-24, Q-43 and Q-45 to Q-47. Q-38 to Q-44 were decided as D-82 to D-88.
- **Effects of D-83 to D-85 on this plan:**
  - Task 6 runs on the Mac, not Kaggle, for CC film footage (D-85).
  - Golden-clip dubbing waits for Q-45 (actor consent, D-84).
  - The S4a rerun must not clone a film actor (D-84; Q-43).
  - Task 12's Kaggle clean-up waits for Q-46.
  - The "sanctioned routes only" line below is superseded by D-83.
- **Task 3:** S4a is done (commit `2ac1ed4`). Chatterbox on the Mac runs at RTF 6.7–7.2, so TTS alone projects to about 8 h for a 90-min film. Per D-66 the reference machine is revisited (Q-43). The rest of Task 3 and any further downloads wait for the owner's answer to Q-43.
- **Golden shortlist:** recorded in `docs/footage.md` (commit `084873b`) and waiting for owner approval.
- **Changes caused by Task 2:**
  - Task 4's QC-embedder row now checks that WeSpeaker ONNX (D-72) separates speakers; it no longer compares embedders.
  - Task 10, Step 2's blacklist rule is already in SPEC §8.5.
  - Task 5's outcome feeds §19 item 8 and D-71.
- **Footage (Q-39):** new golden clips come only through sanctioned routes (Commons, Vimeo downloads, creator-provided files) until the owner decides otherwise.

## Global Constraints

- Phase 0 must finish, and be approved by the owner, before any provider code (SPEC §0.1, `CLAUDE.md` rule 1). Spike scripts live in `scripts/spikes/` and are throwaway.
- Allowed model licenses: MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC, MPL-2.0, Unlicense, CC0-1.0, CC-BY-4.0 (attribution in `NOTICE`). Custom terms (for example the Gemma Terms of Use) are allowed only if listed in `config/license_allowlist.yaml` with a note. Blocked: non-commercial, research-only, NC share-alike, or unknown (§4.1).
- Lock fields per model: `id`, `role`, `source` (`hf | ollama | url | package`), `ref`, `revision`, `files` with `sha256` of the main weights, `license_spdx`, `commercial_ok`, `gated`, `attribution`, `notes` (§4.2).
- Runtime packages: permissive, MPL-2.0, or LGPL (unmodified, dynamically used). GPL only in dev-only tooling, never imported by the shipped runtime (§4.4).
- Never use copyrighted TV footage. Test clips are for private evaluation only. Media and dubbed outputs are never committed or published (`docs/footage.md`).
- Never commit or log tokens. The HF token lives only in the Kaggle secret `HF_TOKEN` or a local environment variable.
- Kaggle free tier only, no billing. Start gated runs from the editor (**Save & Run All**), then stop the interactive session. About 7 of the 30 weekly GPU hours have been used since 2026-10-05.
- One model process at a time; Ollama `keep_alive=0` (§5, §6.1).
- Installs and downloads on the Mac need the owner's go-ahead first.

## Review Focus

These are the failure modes most likely to bite that no task's "done when" check covers by default. Each one is pinned to a step in the owning task.

1. **Turkish casefolding.** Python's `"İ".lower()` returns `"i̇"` (two code points), so the S3d blacklist could never match "İzlediğiniz için teşekkür ederim", Whisper's most common Turkish phantom line. In S3d that line was removed only by the stricter pass-2 scores. Matching must map `İ→i` and `I→ı` first. Pinned in Task 10, Step 2.
2. **Lock drift.** Ollama tags (`translategemma:4b`) and Hugging Face `main` branches move, so a model benchmarked today may not be the one locked next week. Record the revision or digest at measurement time, and lock the same value. Pinned in Task 3, Step 1 and Task 7.
3. **Mac disk.** 52 GB is free, and S4 needs about 20–25 GB. Check free space before each download and clean up afterwards. Pinned in Task 3, Steps 2 and 6.
4. **Transitive GPL.** `chatterbox-tts` 0.1.7 requires `pykakasi==2.3.0` (GPL-3.0-or-later) and `gradio==6.8.0`. Pinned in Task 3 (import check) and Task 9, Step 3 (Q-33).
5. **Spike outputs on GitHub.** `origin/main` already holds the S3 `review_*.md` files, which contain the Turkish and English lines of the CC-BY films. Pinned in Task 12, Step 2 (Q-34).

---

## Where Phase 0 stands

### SPEC §17, Phase 0 items

| # | Item | Status | Evidence / gap |
| --- | --- | --- | --- |
| 1 | Hardware recorded | Partial | M1 Pro, 16 GB, macOS 27.0.1, 52 GB free (read 2026-10-07). MPS not checked. Not yet in `spikes.md`. |
| 2 | Benchmarks | Partial | All 9 model families on Kaggle T4 (S1). Nothing on the Mac. Not run: mlx-whisper, CPU vs MPS, Bandit v2, Chatterbox English / Nano, Qwen3-TTS, hybrid-MLX. |
| 3 | TTS bake-off | Partial | `cfg_weight` decided (D-63). Consistency measured on the CC-BY actors (S3–S3d). Not run: seed variance, exaggeration band, reference length 5–15 s vs 10–30 s, VC lock, consented voices. |
| 4 | Threshold calibration | Not started | No golden set. Only spike values exist (hallucination filters, short lines, pass-2 filters). |
| 5 | Footage | Partial | 3 CC-BY shorts (`docs/footage.md`), each with only 31–55 s of speech. The golden set needs ≥ 5 clips of 1–5 min, one clip ≥ 60 min, and `golden/manifest.json`. |
| 6 | License files | Not started | `models.lock.json`, `MODEL_LICENSES.md`, `NOTICE`, `THIRD_PARTY_LICENSES.md` |
| 7 | Output | Partial | `spikes.md` has the T4 numbers and a 1.6× projection for 90 min. Missing: chosen defaults, a Mac projection, `config/defaults.yaml`. |

### SPEC §19, verify list

| # | Item | Status | Evidence / gap |
| --- | --- | --- | --- |
| 1 | Licenses | Partial | Turkish aligner confirmed as WhisperX's default (`mpoyraz/wav2vec2-xls-r-300m-cv7-turkish`, CC-BY-4.0 reported). AST tagger BSD-3 reported. TIGER-DnR: Apache-2.0, with a non-commercial training-data caveat. Bandit v2 weights: unknown. Not chosen yet: QC embedder, `chatterbox-mlx`, fixture voices, voice bank. Every model card must be re-read at lock time. |
| 2 | Model names | Partial | TranslateGemma 4B and 12B pulled from Ollama; Turbo loaded. Multilingual V3 unconfirmed (Q-18). Nano is gated and was not loaded. Qwen3-TTS not tried. |
| 3 | pyannote | Partial | Exposes per-speaker 256-d embeddings and exclusive diarization. MPS and CPU-vs-MPS parity untested (Mac only). |
| 4 | ASR fields | Partial | faster-whisper exposes all of them. mlx-whisper untested (Mac only). |
| 5 | WhisperX on mlx-whisper | Not started | Works on faster-whisper output (S1). |
| 6 | Chatterbox | Partial | CUDA memory 3.7 GB; effect of `cfg_weight` measured (D-63). Not measured: CPU / MPS / MLX memory, maximum reference length, `TTS_MAX_CHARS`, saving and loading conditioning, voice-state carry-over, VC. |
| 7 | Perth watermark | Partial | Survives `atempo` and AAC. Mixing and `loudnorm` untested. |
| 8 | TranslateGemma | Partial | The Ollama pull needs no HF gate (the Gemma terms still apply). 4B matches 12B on T4. The budget was met 52% of the time. Translates meaning better than Qwen3 (S3d). Untested: context, glossary and keyed JSON, because the spikes used its own one-line prompt (Q-12, Q-27); Mac memory. Done: rewrite LLM with thinking off (Qwen3-4B-Instruct-2507). |
| 9 | transformers v5 / opus-mt | **Done** | `MarianMTModel` loads directly under transformers 5.18.0 (S1, chrF 73.3). `pipeline("translation")` is not needed. |
| 10 | `keep_alive=0` | Partial | Frees GPU memory on CUDA (S1). Mac unified memory untested. |
| 11 | FFmpeg | Not started | FFmpeg is not installed on the Mac. |
| 12 | Thresholds | Partial | Spike values only; most need golden clips. |
| 13 | `ASR_INPUT` / `DIARIZATION_INPUT` | Open | The dialogue stem yields 11–75% more ASR words, but these are unverified. Diarization over-splits on both inputs. Needs human transcripts. |
| 14 | Reference denoise | Not started | The D-58 default (none) stands. |
| 15 | Speed | Partial | T4: ≈ 2.4 h for a 90-min video (1.6×). Mac: not measured (Q-19). |

## Decisions needed from the owner

The full wording is in `docs/OPEN_QUESTIONS.md`. Rows are ordered by how much work each decision blocks.

| Q | Decision | Recommendation | Blocks |
| --- | --- | --- | --- |
| Q-23 | Which machine is the §2 reference: the Mac or Kaggle? | The Mac, because it runs the local app. Measure only the chosen defaults on it (S4, ≈ 20–25 GB download). Keep Kaggle for the heavy comparisons. | Task 3 |
| Q-30 | Who provides consented Turkish voices for S2? | The owner records their own voice, plus 1–2 consenting people if possible, 2–3 min each. Without them, S2 reuses the CC-BY actors privately, which gives weaker evidence. | Task 4 |
| Q-20 | Golden set: where does more footage come from, and who labels it? | Find 2 or more owner-uploaded CC-BY shorts with dense dialogue. The owner corrects the transcripts and speaker labels (about 30–60 min per clip). Build the long clip by concatenation (Q-15). | Task 6 |
| Q-29 | Adopt the S3–S3d mechanisms into the spec (11 items, Task 2)? | Approve them as one batch. | Task 2 |
| Q-25 | Timing gap: add a "ripple" rule to §9? | Yes. A line that still does not fit may push the next line up to 0.25 s later, only when that line has slack. Build and test it in Phase 6. Keep the SC4 target (15%) until Phase 11. | Task 2 |
| Q-27 / Q-12 | TranslateGemma prompt: its native one-line format, or §8.14's context + glossary + keyed JSON? | Run Task 5. Keep the native format unless keyed JSON gives ≥ 95% valid output. | Task 5 |
| Q-28 | Which QC embedder runs inside the TTS venv? | Chatterbox's own voice encoder, if S2 shows it separates speakers as well as WeSpeaker. Otherwise WeSpeaker via ONNX Runtime. | Task 4 |
| Q-26 | Which rewrite model? | Qwen3-4B-Instruct-2507 (Apache-2.0, already measured). Try a larger instruct model only if S4 shows it fits in 16 GB. | Task 7 |
| Q-33 | `chatterbox-tts` pulls in `pykakasi` (GPL-3.0) and `gradio` | Install without them if the tr/en path never imports them (checked in S4). Otherwise the owner decides. | Task 9 |
| Q-31 | Lock the fallback separators (TIGER-DnR, Bandit v2)? | No. Lock only Demucs; the ducked original is the fallback. | Task 7 |
| Q-32 | Sources for bank voices and fixture voices | Bank: synthetic English voices from Kokoro-82M (Apache-2.0; voice license to verify). Fixture: Chatterbox Turkish. Generate them in Phases 1 and 3. | Task 7 |
| Q-16 | Loudness target | Match the original track's loudness, clamped to −24…−14 LUFS, so switching tracks is not jarring. | Task 10 |
| Q-34 | The S3 transcripts are already on GitHub | Confirm the repository is private, and stop committing `review_*.md`. | Task 12 |
| Q-01–Q-15 | Provisional choices | Confirm as written, except Q-08 (checked in Task 1) and Q-12 (decided by Task 5). | Task 2 |

---

## Tasks

**Order:**
- Task 1 can start now.
- Task 2 needs the owner's answers.
- Tasks 3–6 are measurements: 3 and 5 run on the Mac, 4 and 6 on Kaggle.
- Tasks 7–10 write the exit files from the measured defaults.
- Tasks 11–12 close Phase 0.

Each task ends with a commit. Nothing is pushed without the owner's OK.

### Task 1: Record the Mac and check FFmpeg (§17.1, §19.11, Q-08)

**Files:**
- Modify: `docs/spikes.md` (new section "Reference machine")

- [ ] **Step 1:** Record the values read on 2026-10-07:
  - Apple M1 Pro, 16 GB, macOS 27.0.1, 52 GB free of 460 GB;
  - uv and Ollama installed; FFmpeg and Deno not installed.
- [ ] **Step 2 (needs the owner's OK):** `brew install ffmpeg`
- [ ] **Step 3: License flags.** Run `ffmpeg -hide_banner -buildconf | grep -E "enable-(gpl|nonfree|libfdk)"`. Expected: `--enable-gpl`, which is acceptable because FFmpeg is not redistributed (§4.4), and no `--enable-nonfree`.
- [ ] **Step 4: Filters and encoder.**
  - Run `ffmpeg -hide_banner -filters | grep -wE "loudnorm|sidechaincompress|atempo|ebur128|alimiter|pan"`. Expected: 6 lines.
  - Run `ffmpeg -hide_banner -encoders | grep -w aac`. Expected: the native encoder.
- [ ] **Step 5: MP4 stream copy of VP9 and AV1, with `mov_text` subtitles** (Q-08, §11):

```bash
cd "$(mktemp -d)"
ffmpeg -y -f lavfi -i testsrc=d=3:s=320x240 -c:v libvpx-vp9 vp9.webm
ffmpeg -y -f lavfi -i testsrc=d=3:s=320x240 -c:v libsvtav1 av1.mkv
printf '1\n00:00:00,000 --> 00:00:02,000\nHello\n' > t.srt
for f in vp9.webm av1.mkv; do
  ffmpeg -y -i "$f" -i t.srt -map 0 -map 1 -c copy -c:s mov_text -movflags +faststart "${f%.*}.mp4"
done
for f in vp9.mp4 av1.mp4; do ffprobe -v error -show_entries stream=codec_name -of csv=p=0 "$f" | paste -sd, -; done
```

  Expected output: `vp9,mov_text` and `av1,mov_text`.
- [ ] **Step 6:** Write the results under "Reference machine" in `docs/spikes.md`. Mark §19.11 as done and record the answer to Q-08.
- [ ] **Step 7:** Commit:

```bash
git add docs/spikes.md
git commit -m "Phase 0: reference machine and FFmpeg checks"
```

**Done when:** `docs/spikes.md` lists the hardware, the FFmpeg version and license flags, the 6 filters, and the VP9/AV1 MP4 result.

### Task 2: Apply the owner's decisions to the spec

**Files:**
- Modify: `docs/DECISIONS.md` (D-66 onward, plus a changelog line)
- Modify: `docs/SPEC.md` (the sections named below)
- Modify: `docs/OPEN_QUESTIONS.md` (delete the answered items)

Q-29's batch, with the values measured in S3–S3d (`scripts/spikes/kaggle_s3d/run_s3d.py`):

| # | Change | SPEC section | Spike evidence |
| --- | --- | --- | --- |
| a | Cast-review action `set_speaker_count`: reruns `DIARIZING` with `num_speakers` | §3.1.4, §8.7 | Speaker counts went 7 → 3, 4 → 2 and 5 → 2 with a fixed count (S3b) |
| b | Flip smoothing: a run of another speaker's words shorter than 0.5 s, lying between two runs of one speaker, takes that speaker | §8.8 | `flip_s = 0.5` |
| c | Fragment merge: a segment under 1.0 s merges into a same-speaker neighbour within 1.0 s | §8.8 | `min_seg_s = 1.0`, `fragment_gap_s = 1.0` |
| d | Deterministic ASR: temperature 0 only, with no fallback sampling | §8.5 | ISLIK gave 44 vs 69 words between runs when fallback sampling was on (S3b) |
| e | Second ASR pass on VAD speech ≥ 0.6 s that segments cover < 30%. Stricter filters: `avg_logprob ≥ −0.8`, `no_speech_prob ≤ 0.5`, plus the blacklist | §8.5 | S3c, S3d |
| f | Turkish blacklist file (Task 10), matched after Turkish-aware casefolding | §8.5 | 7 phrases |
| g | Translation validation also rejects: multi-line output, bullets, commentary phrases, length > 2 × source + 15, output that is ≥ 50% source words ("untranslated"), and lowercase words containing ç ğ ı ö ş ü | §8.14.4 | S3c, S3d |
| h | TTS silence trim before fitting: cut leading and trailing audio below −35 dB of the clip's peak, keeping 40 ms | §8.16 | ≈ 0.1 s saved per line |
| i | Speech-aware lay-back: lay back only non-speech; mute VAD speech that no dubbed or kept segment covers | §10.2 | Stopped the Turkish leak (S3c) |
| j | Speech coverage metric `(dubbed + kept + non-verbal) ÷ VAD speech`, with soft check SC7 (provisional threshold 75%) | §12.2 | 67–86% across the clips |
| k | LLM calls: thinking off; `num_predict` caps (translate 160, rewrite 100); strip text up to `</think>`; latency counted without model load | §5, §8.14 | S3c, S3d |

- [ ] **Step 1:** For each approved item, add a D-entry with the decision, the reason (spike evidence), what it overrides, and its status.
- [ ] **Step 2:** Edit the named SPEC section so it reads correctly on its own, without referring to the spikes.
- [ ] **Step 3:** Apply the answers to Q-25 (§9), Q-26 (§5) and Q-31 (§5) the same way.
- [ ] **Step 4:** For each confirmed item in Q-01–Q-15, change its status from "provisional" to "final" in `docs/DECISIONS.md` and delete its row from `docs/OPEN_QUESTIONS.md`.
- [ ] **Step 5:** Run `grep -n "provisional" docs/DECISIONS.md` and check that every remaining hit is still open in `docs/OPEN_QUESTIONS.md`.
- [ ] **Step 6:** Commit:

```bash
git add docs/DECISIONS.md docs/SPEC.md docs/OPEN_QUESTIONS.md
git commit -m "Phase 0: owner decisions after S3d"
```

**Done when:** no answered question is left in `docs/OPEN_QUESTIONS.md`, and each answered one has a D-entry and matching spec text.

### Task 3: Spike S4, benchmarks on the Mac (§17.2, §19.3–6, §19.8, §19.10, §19.15; Q-19, Q-23, Q-26, Q-33)

**Depends on:**
- Q-23 answered "the Mac";
- the owner's OK for ≈ 20–25 GB of downloads;
- Task 1.

**Files:**
- Create: `scripts/spikes/mac_s4/run_s4.py` and `scripts/spikes/mac_s4/README.md`. Same pattern as `kaggle_s1/run_s1.py`: one uv venv per family, one process at a time, results written to JSON.
- Output: `scripts/spikes/mac_s4/out/` with `results.json` and `summary.md`. Audio is git-ignored.

**Input:** ISLIK (`media/QJH3CCrjda4.m4a`, CC-BY, private), cut to 60 s and 5 min.

**Staging (D-66):**
1. **S4a** runs first: only the TTS row below (Chatterbox Multilingual, CPU vs MPS), about 3–4 GB of downloads, after the owner's OK.
2. The other rows run only after S4a's result, and only if the owner agrees.
3. If S4a projects the Mac pipeline to be clearly over 3×, the reference machine is revisited before anything else is downloaded.

| Family | Variants | Measures | Answers |
| --- | --- | --- | --- |
| ASR | mlx-whisper large-v3-turbo vs large-v3; faster-whisper large-v3 CPU int8 | RTF, peak memory, and whether `avg_logprob`, `no_speech_prob`, `compression_ratio`, word timestamps and the language probability are exposed | §19.4, ASR size |
| Alignment | WhisperX `align()` on mlx-whisper output, CPU vs MPS | RTF, share of words timed | §19.5 |
| Diarization | community-1 with `num_speakers=3`, CPU vs MPS | RTF, memory, parity (same speaker count and ≥ 95% frame agreement after label mapping) | §19.3 |
| Separation | Demucs htdemucs, CPU vs MPS | RTF on 5 min | 90-min projection |
| VAD, tagger | Silero (CPU); AST, CPU vs MPS | RTF | 90-min projection |
| TTS | Chatterbox Multilingual 0.1.7, CPU vs MPS (`PYTORCH_ENABLE_MPS_FALLBACK=1`, log the ops that fall back), 20 English lines cloned from a 12 s ISLIK reference | RTF, peak memory, and whether `pykakasi` or `gradio` gets imported (`python -X importtime -c "from chatterbox.mtl_tts import ChatterboxMultilingualTTS" 2>&1 \| grep -E "pykakasi\|gradio"`) | §19.6 memory, Q-19, Q-33 |
| LLM | Ollama `translategemma:4b` and `qwen3:4b-instruct-2507-q4_K_M` on the 68 S3d lines; optionally a larger instruct model for rewrites | Tokens/s, seconds per line, memory while loaded and after `keep_alive=0` (`ollama ps`, `memory_pressure`) | §19.8, §19.10, Q-26 |
| Perth | Run the detector after TTS → `atempo` 1.2 → mix with background → two-pass `loudnorm` → AAC | Watermark detected or not | §19.7, SC6 |

**Not planned unless S4 misses the 3× target:**
- benchmarks of the alternatives: Chatterbox English, Turbo, Nano and Flash, Qwen3-TTS, the hybrid-MLX `chatterbox-mlx` backend, Bandit v2, and TranslateGemma 12B on the Mac;
- §19.2 asks only whether these exist under their names, and Task 7, Step 1 checks that with `model_info`.

If S4 misses the target, Turbo and `chatterbox-mlx` are the first alternatives to try.

- [ ] **Step 1:** Write `run_s4.py` (throwaway). Record each model's revision or Ollama digest in `results.json` (Review Focus 2).
- [ ] **Step 2:** Before every download, run `df -h ~` and stop if less than 25 GB is free (Review Focus 3).
- [ ] **Step 3:** Run the families one at a time. Take peak memory from `/usr/bin/time -l`, plus `torch.mps.driver_allocated_memory()` on MPS.
- [ ] **Step 4:** Project the 90-minute wall-clock time from the per-stage RTFs, using S1's assumptions (55 min of English speech × 1.3).
- [ ] **Step 5:** Add an "S4" section to `docs/spikes.md` with:
  - the CPU vs MPS table;
  - the chosen backend per role;
  - the projection against §2 criterion 7 (≤ 3×);
  - the parity result and the Perth result.
- [ ] **Step 6:** Delete the venvs and model caches, unless the owner wants to keep them for Phase 1.
- [ ] **Step 7:** Commit:

```bash
git add scripts/spikes/mac_s4 docs/spikes.md
git commit -m "Phase 0: S4 Mac benchmarks"
```

**Done when:** every role has a measured backend on the Mac, and Q-19 has a number.

### Task 4: Spike S2, Chatterbox voice settings (§17.3, §19.6; Q-18, Q-28, Q-30)

**Depends on:** Q-30 (the voices). Runs on a Kaggle T4, started from the editor.

**Files:**
- Create: `scripts/spikes/kaggle_s2/` with `run_s2.py`, `push.sh`, `fetch.sh`, `kernel-metadata.template.json` and `README.md`, following the pattern of `kaggle_s3d/`.
- The voices go into a private Kaggle dataset, `voxshift-s2-voices`, deleted after the run. Consent notes stay outside git.

| Test | Design | Decides |
| --- | --- | --- |
| Reference length | 5–15 s vs 10–30 s, plus 2–6 s (the short-film case) | Default length (§3.2.2, D-09) |
| Seed variance | 5 seeds × 20 sentences per voice | Within-voice mean and p10 cosine; spread of durations |
| Exaggeration | 0.3 / 0.5 / 0.7 | Band and default (§3.2.6) |
| VC lock | Chatterbox VC on vs off | `TTS_VC_LOCK` (§3.2.8) |
| Text length | 50 / 100 / 200 / 300 / 400 characters | `TTS_MAX_CHARS` (rate of babble or cut-off output) |
| Conditioning cache | `prepare_conditionals` → save → load in a fresh process. Does the same seed give the same audio? | §19.6, save and load |
| Voice carry-over | Synthesize A, B, then A again without resetting the conditioning | The §3.2.6 rule |
| QC embedder | Chatterbox's voice encoder vs WeSpeaker on the same clips, comparing how well each separates speakers (between- vs within-speaker cosine) | Q-28 |
| Drift threshold | Regeneration rate at `DRIFT_MIN_COS` = 0.55 / 0.60 / 0.65 | Initial `DRIFT_MIN_COS` and its speed cost |
| Model identity | Record the `ResembleAI/chatterbox` revision and whether the multilingual weights are V3 | Q-18 |
| Reference denoise | No denoise vs DeepFilterNet (MIT/Apache-2.0) on the 2–6 s short-film references | §19.14, D-58 |

- [ ] **Step 1:** Write the scripts and push them. Then **Save & Run All** from the editor and stop the interactive session.
- [ ] **Step 2:** The owner listens to the exaggeration and VC samples.
- [ ] **Step 3:** Add an "S2" section with the chosen values to `docs/spikes.md`.
- [ ] **Step 4:** Delete the Kaggle dataset and the run's audio output.
- [ ] **Step 5:** Commit:

```bash
git add scripts/spikes/kaggle_s2 docs/spikes.md
git commit -m "Phase 0: S2 voice settings"
```

**Done when:**
- the reference length, exaggeration, `TTS_VC_LOCK`, `TTS_MAX_CHARS`, initial `DRIFT_MIN_COS` and reference-denoise setting are chosen;
- Q-18 and Q-28 are answered.

### Task 5: TranslateGemma prompt format (§19.8; Q-12, Q-27)

**Depends on:** S4's Ollama models (on the Mac), or a small Kaggle run.

**Files:**
- Create: `scripts/spikes/mac_s4/translate_format.py`.
- Output: `out/translate_format.json`. The side-by-side `.md` stays git-ignored because it contains lines from the films.

**Input:** the 68 Turkish lines from S3d.

| Variant | Prompt |
| --- | --- |
| a | TranslateGemma's native one-line prompt with a budget (the S3d baseline) |
| b | (a) plus the previous 3 and next 1 source lines, marked as context |
| c | Keyed JSON for each utterance group (≤ 6 segments) |
| d | (b) plus a glossary of 2–3 names per film |

- [ ] **Step 1:** For each variant, measure:
  - the JSON parse rate and whether all ids are present;
  - budget compliance and whether glossary names are kept;
  - rejects under Task 2's item g;
  - seconds per line.
- [ ] **Step 2:** The owner reads 20 lines side by side and judges the meaning.
- [ ] **Step 3:** Keep (a) unless (c) or (d) is ≥ 95% valid and reads at least as well. Record the result in `docs/spikes.md` and the answer to Q-12 and Q-27.
- [ ] **Step 4:** Commit:

```bash
git add scripts/spikes/mac_s4/translate_format.py scripts/spikes/mac_s4/out/translate_format.json docs/spikes.md
git commit -m "Phase 0: translation prompt format"
```

### Task 6: Calibration set and initial thresholds (§17.4–5, §19.12–13; Q-15, Q-20, Q-24)

**Depends on:** Q-20.

**Files:**
- Modify: `docs/footage.md` (new clips)
- Create: `golden/manifest.json` (name, sha256, source)
- Create: `scripts/spikes/kaggle_cal/` (calibration notebook; use CPU where possible, which costs no GPU quota)

- [ ] **Step 1:** Find 2 or more owner-uploaded CC-BY Turkish shorts with dense multi-speaker dialogue. As before, reject re-uploads and TV footage.
- [ ] **Step 2:** Cut 5 or more excerpts of 1–5 min into `golden/<clip_id>/clip.<ext>`, and write `golden/manifest.json`. Files and fields are listed in SPEC §16.4 (D-67).
- [ ] **Step 3:** Prepare the draft `reference_turns.rttm` and `reference_transcript.json` from ASR and diarization output (on Kaggle, if Q-35 allows it). A human then corrects every speaker label by listening to and watching the clip. Freeze the files by recording their sha256 in the manifest.
- [ ] **Step 4:** Compare `ASR_INPUT` and `DIARIZATION_INPUT` (dialogue stem vs original) by WER and by error in speaker count (§19.13).
- [ ] **Step 5:** Compute the calibration statistics:
  - Source-side embedding statistics (within vs between speakers, outliers). These set `MERGE_COS`, `SPLIT_COS`, `OUTLIER_COS`, `OUTLIER_MARGIN` and the `speaker_confidence` formula.
  - Separation metrics on the clips where the owner judged separation good. These set `SEP_MAX_SPEECH_IN_BG` and `SEP_MIN_DIALOGUE_COVERAGE`.
- [ ] **Step 6:** Fill the threshold table in `docs/spikes.md` with value, source and the label "provisional". Phase 11 retunes them, because three short films are easy to over-fit.
- [ ] **Step 7:** Commit:

```bash
git add docs/footage.md golden/manifest.json scripts/spikes/kaggle_cal docs/spikes.md
git commit -m "Phase 0: calibration set and initial thresholds"
```

| Threshold | Source of the initial value |
| --- | --- |
| Hallucination 0.6 / −1.0 / 2.4; pass 2 −0.8 / 0.5 | Whisper defaults (D-49); S3d |
| Fit: guard 0.12; tempo 1.10 / 1.25; short line 1.0 s / 1.5 / 0.3 s; budgets 0.95 / 0.9 | SPEC §9, D-65 |
| `DRIFT_MIN_COS`, `AUDITION_MIN_COS` | S2 (Task 4) |
| `MERGE_COS`, `SPLIT_COS`, `OUTLIER_COS`, `OUTLIER_MARGIN`, `speaker_confidence` | Step 5 |
| Separation thresholds | Step 5 |
| `REF_MIN_CONF`, `REF_MIN_ASR`, `REF_MIN_SNR_DB` | Step 5 distributions; provisional |
| Gender F0 bands 155 / 185 Hz | SPEC §3.4 defaults, checked against the credited cast |
| `LID_MIN_CONF` | Whisper's language probabilities on the golden clips |
| Singing threshold | Provisional. The current clips have no singing (Q-24). |
| SC7 coverage | 75%, provisional (S3c/S3d range: 67–86%) |

### Task 7: `models.lock.json` (§4.2)

**Depends on:** Tasks 3–5 (final defaults), Q-31, Q-32.

**Files:**
- Create: `models.lock.json` (repository root)

These are the models that ship enabled. The list is final after S4 and S2.

| id | role | source | ref | License to verify on the card | Gated |
| --- | --- | --- | --- | --- | --- |
| `silero_vad` | vad | package | `silero-vad` (pinned version; weights inside the package) | MIT | no |
| `ast_audioset` | audio_events | hf | `MIT/ast-finetuned-audioset-10-10-0.4593` | BSD-3-Clause | no |
| `whisper_mlx` | asr | hf | `mlx-community/whisper-large-v3[-turbo]` (size from S4) | MIT | no |
| `whisper_ct2` | asr (CPU fallback) | hf | faster-whisper conversion of the same size | MIT | no |
| `align_tr` | alignment | hf | `mpoyraz/wav2vec2-xls-r-300m-cv7-turkish` | CC-BY-4.0 | no |
| `diar_community1` | diarization | hf | `pyannote/speaker-diarization-community-1` | CC-BY-4.0 | yes |
| `embed_wespeaker` | identity embeddings | hf | `pyannote/wespeaker-voxceleb-resnet34-LM` | CC-BY-4.0 (VoxCeleb data note) | check |
| `demucs_htdemucs` | separation | url | the htdemucs checkpoint listed in Demucs' remote files | MIT code; weights and MUSDB training data to verify | no |
| `translategemma_4b` | translation | ollama | `translategemma:4b` (digest) | Gemma Terms of Use (allowlisted) | no |
| `qwen3_4b_instruct` | rewrite | ollama | `qwen3:4b-instruct-2507-q4_K_M` (digest) | Apache-2.0 | no |
| `opus_mt_tr_en` | translation fallback | hf | `Helsinki-NLP/opus-mt-tr-en` | The SPEC says Apache-2.0. Check the card, because OPUS-MT also publishes under CC-BY-4.0. | no |
| `chatterbox_mtl` | tts, vc | hf | `ResembleAI/chatterbox` (revision) | MIT | no |
| `perth` | watermark | package | `resemble-perth` (pinned) | MIT | no |
| QC embedder | qc | per Q-28 | — | — | — |

- [ ] **Step 1:** Get Hugging Face revisions and weight hashes. Gated repositories need `HF_TOKEN` in the environment. If metadata is refused, run this step in a Kaggle CPU session with the secret.

```bash
uv run --no-project --with huggingface_hub python - <<'EOF'
import os
from huggingface_hub import HfApi
api = HfApi(token=os.environ.get("HF_TOKEN"))
REPOS = [
    "MIT/ast-finetuned-audioset-10-10-0.4593",
    "mpoyraz/wav2vec2-xls-r-300m-cv7-turkish",
    "pyannote/speaker-diarization-community-1",
    "pyannote/wespeaker-voxceleb-resnet34-LM",
    "Helsinki-NLP/opus-mt-tr-en",
    "ResembleAI/chatterbox",
    # plus the Whisper repos chosen in S4
    # §19.2 existence check only (not locked): "ResembleAI/chatterbox-nano", "ResembleAI/chatterbox-flash"
]
for repo in REPOS:
    info = api.model_info(repo, files_metadata=True)
    print(repo, info.sha, (info.card_data or {}).get("license"), "gated:", info.gated)
    for s in info.siblings:
        if s.lfs:
            print("   ", s.rfilename, s.lfs.sha256, s.size)
EOF
```

- [ ] **Step 2:** Get the Ollama digests: after the S4 pull, run `ollama show <tag> --modelfile`; the `FROM` line holds the blob's sha256.
- [ ] **Step 3:** For weights that come from a package or URL, pin the version and record the sha256 of the weight file.
- [ ] **Step 4:** Re-read every model card at the pinned revision. Fill `license_spdx`, `commercial_ok`, `gated`, `attribution` and `notes` (training-data caveats).
- [ ] **Step 5:** Write the file. Each entry has this shape:

```json
{
  "schema_version": 1,
  "models": [
    {
      "id": "diar_community1",
      "role": "diarization",
      "source": "hf",
      "ref": "pyannote/speaker-diarization-community-1",
      "revision": "<commit sha printed by Step 1>",
      "files": [{"path": "<file printed by Step 1>", "sha256": "<sha256 printed by Step 1>"}],
      "license_spdx": "CC-BY-4.0",
      "commercial_ok": true,
      "gated": true,
      "attribution": "pyannote/speaker-diarization-community-1 by pyannote, CC-BY-4.0",
      "notes": ""
    }
  ]
}
```

- [ ] **Step 6:** Validate:

```bash
python3 - <<'EOF'
import json, re
lock = json.load(open("models.lock.json"))
ids = [m["id"] for m in lock["models"]]
assert len(ids) == len(set(ids)), "duplicate ids"
for m in lock["models"]:
    assert re.fullmatch(r"[0-9a-f]{40}|sha256:[0-9a-f]{64}|[0-9.]+", m["revision"]), m["id"]
    assert all(re.fullmatch(r"[0-9a-f]{64}", f["sha256"]) for f in m["files"]), m["id"]
print("ok", len(ids), "models")
EOF
```

- [ ] **Step 7:** Commit:

```bash
git add models.lock.json
git commit -m "Phase 0: models.lock.json"
```

### Task 8: `MODEL_LICENSES.md`, `NOTICE` and `config/license_allowlist.yaml`

**Files:**
- Create: `MODEL_LICENSES.md`, `NOTICE`, `config/license_allowlist.yaml` (paths per SPEC §18.3)

- [ ] **Step 1:** In `MODEL_LICENSES.md`, write one row per lock entry: id, role, ref@revision, license, `commercial_ok`, gated, attribution, notes.
- [ ] **Step 2:** In `NOTICE`, write:
  - the CC-BY-4.0 attributions (community-1, WeSpeaker, the Turkish aligner, and opus-mt if it is CC-BY);
  - the Gemma notice: "Gemma is provided under and subject to the Gemma Terms of Use found at ai.google.dev/gemma/terms", with the use restrictions passed on.
- [ ] **Step 3:** Write `config/license_allowlist.yaml`:

```yaml
# Custom model licenses allowed by SPEC §4.1. Each entry needs a note.
- license: gemma-terms-of-use
  models: [translategemma_4b]
  url: https://ai.google.dev/gemma/terms
  note: Commercial use allowed. Pass the use restrictions on to users and ship the Gemma notice in NOTICE.
```

- [ ] **Step 4:** These files are hand-written for now. `scripts/license_report.py` (§4.2) is built test-first in Phase 1, next to the license gate, and must regenerate them byte for byte.
- [ ] **Step 5:** Commit:

```bash
git add MODEL_LICENSES.md NOTICE config/license_allowlist.yaml
git commit -m "Phase 0: model licenses and NOTICE"
```

### Task 9: `THIRD_PARTY_LICENSES.md`, first version (§4.4; Q-33)

**Files:**
- Create: `THIRD_PARTY_LICENSES.md`

- [ ] **Step 1:** List the direct dependencies the spec names, with licenses taken from PyPI metadata:
  - **Core:** FastAPI, pydantic-settings, numpy, soundfile (bundles libsndfile, LGPL), librosa, inflect, yt-dlp.
  - **Providers:** torch, torchaudio, transformers, mlx, mlx-whisper, faster-whisper, ctranslate2, whisperx, pyannote.audio, silero-vad, demucs, chatterbox-tts, resemble-perth, sentencepiece.
  - **Frontend:** react, vite, typescript.
- [ ] **Step 2:** Audit the transitive dependencies of the S4 venvs. For each venv, run `uv pip list --format json` and read each package's license metadata. Flag GPL, AGPL and unknown licenses.
- [ ] **Step 3:** Record the known flags and Q-33's outcome:
  - `pykakasi` (GPL-3.0-or-later), required by chatterbox-tts 0.1.7;
  - `gradio` (heavy and unused).
- [ ] **Step 4:** Commit:

```bash
git add THIRD_PARTY_LICENSES.md
git commit -m "Phase 0: first third-party license audit"
```

### Task 10: `config/defaults.yaml` and the Turkish blacklist

**Depends on:** Tasks 3–6, Q-16.

**Files:**
- Create: `config/defaults.yaml`, `config/hallucination_blacklist.tr.txt`

- [ ] **Step 1:** Write the blacklist file, one phrase per line:

```
izlediğiniz için teşekkür
altyazı
abone olmayı unutmayın
abone olun
beğenmeyi unutmayın
bir sonraki videoda
m.k.
```

- [ ] **Step 2:** Write the matching rule into SPEC §8.5 for Phase 2 (Review Focus 1):
  - Normalize both the text and the phrases: map `İ→i` and `I→ı`, then apply `str.lower()`, then strip punctuation.
  - Match a phrase as a whole word sequence.
  - Bare "altyazı" ("subtitle") matches only in segments of ≤ 4 words, so real dialogue about subtitles survives.
  - Phase 2 tests: "İzlediğiniz için teşekkür ederim." is flagged; "Altyazıyı aç." is not.
- [ ] **Step 3:** Write `config/defaults.yaml`. List every §6.5 key with its value and a comment naming its source (`# D-63`, `# S4`, `# provisional: Task 6`).
  - **Already decided:**
    - separation `demucs_htdemucs`;
    - `cfg_weight` 0.5, with 0.3 as the per-voice fallback;
    - short lines 1.0 s / 1.5 / 0.3 s; guard 0.12; tempo 1.10 / 1.25;
    - budgets 0.95 / 0.9; rewrite rounds 2; `FIT_TERMINAL_POLICY=truncate`;
    - hallucination 0.6 / −1.0 / 2.4; pass 2 −0.8 / 0.5;
    - `keep_alive` 0; `num_predict` 160 / 100;
    - `MAX_VIDEO_MINUTES` 120; `TRUE_PEAK_TARGET_DBTP` −2.0.
  - **From S4, S2 and Task 6:**
    - ASR size and backend; TTS backend;
    - `ASR_INPUT`, `DIARIZATION_INPUT`;
    - `TTS_MAX_CHARS`, exaggeration, `TTS_VC_LOCK`, reference length;
    - all identity, drift and separation thresholds;
    - the loudness target (Q-16).
- [ ] **Step 4:** Validate: `uv run --no-project --with pyyaml python -c "import yaml; yaml.safe_load(open('config/defaults.yaml'))"`
- [ ] **Step 5:** Commit:

```bash
git add config/defaults.yaml config/hallucination_blacklist.tr.txt docs/SPEC.md
git commit -m "Phase 0: defaults and Turkish blacklist"
```

### Task 11: Phase 0 report

**Files:**
- Modify: `docs/spikes.md`, `docs/feasibility.md`, `docs/OPEN_QUESTIONS.md`

- [ ] **Step 1:** Add a "Phase 0 summary" at the top of `docs/spikes.md`:
  - the chosen default per role (model, size, backend);
  - the 90-minute projection on the Mac and on the T4, against §2 criterion 7;
  - each §19 item with its outcome.
- [ ] **Step 2:** Mark the verdicts in §0 of `docs/feasibility.md` as superseded by `docs/spikes.md`.
- [ ] **Step 3:** Each item left in `docs/OPEN_QUESTIONS.md` names the phase that will answer it, with the owner's sign-off.
- [ ] **Step 4:** Commit:

```bash
git add docs/spikes.md docs/feasibility.md docs/OPEN_QUESTIONS.md
git commit -m "Phase 0: summary"
```

### Task 12: Cleanup and approval

- [ ] **Step 1:** On Kaggle, delete the `voxshift-s3-clips` dataset and the notebook outputs that contain cloned voices, once calibration no longer needs them (use limits in `docs/footage.md`).
- [ ] **Step 2:** For GitHub (Q-34):
  - add `scripts/spikes/**/review_*.md` to `.gitignore`;
  - untrack the existing files with `git rm --cached`;
  - rewrite history only if the repository is public and the owner asks for it.
- [ ] **Step 3:** Commit with `git commit -m "Phase 0 complete"`. Push only with the owner's OK.
- [ ] **Step 4:** The owner approves Phase 1; then the Phase 1 plan is written.
