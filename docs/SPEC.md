# AI Video Dubber — Specification v3

Single source of truth. Prepared 3 October 2026.
Decision history: `docs/DECISIONS.md`. Unresolved items: `docs/OPEN_QUESTIONS.md`.
Files in `docs/archive/` are historical and must never be used as instructions.

| § | Section | § | Section |
| --- | --- | --- | --- |
| 0 | Working rules | 10 | Mixing |
| 1 | Product | 11 | Render |
| 2 | Definition of Done | 12 | Validation |
| 3 | Voice consistency | 13 | API |
| 4 | Licensing and license gate | 14 | UI |
| 5 | Stack | 15 | Edge cases (1–51) |
| 6 | Architecture | 16 | Testing |
| 7 | Data model | 17 | Phases (0–12) |
| 8 | Pipeline stages | 18 | Environment and guides |
| 9 | Timing and fitting | 19 | Verify in Phase 0 |

---

## 0. Working rules

1. Work one phase at a time (§17). Start a phase only when the previous one has passing automated tests and a runnable app.
2. Write the failing test first, then the code.
3. Mocks live only under `tests/`. The shipped pipeline always uses real providers.
4. No model without entries in `models.lock.json` and `MODEL_LICENSES.md`; no package without passing the package license audit (§4.4). Model names appear only in their provider package and the lock file.
5. The API and worker processes never import torch, MLX or any ML library (numpy and soundfile are allowed). ML runs only in provider subprocesses (§6).
6. Before each commit: `uv run pytest -m "not models and not long"`, lint and type-check. Commit at least once per phase.
7. If this spec proves wrong or unverifiable, stop and record it in `docs/OPEN_QUESTIONS.md`. Record benchmarks and surprises in `docs/spikes.md`. Never silently work around the spec.
8. Spec changes: add a numbered entry to `docs/DECISIONS.md`, then update this file.
9. Never log transcript or translation text, and never log secrets.

---

## 1. Product

### 1.1 Goal

A local-first application that dubs a video from a source language into a target language. It keeps the original video and background audio, and gives every actor a distinct voice that stays consistent for the whole video. Default pair: Turkish (`tr`) → English (`en`). Other pairs are configurable; only `tr → en` is acceptance-tested in this release.

### 1.2 Inputs

| Input | Rule |
| --- | --- |
| File upload (any container FFmpeg reads) | Primary input |
| URL (via yt-dlp) | Best-effort; not required by §2 |
| `source_language`, `target_language` | Defaults `tr`, `en` |
| `consent_confirmed` | Must be `true`: the user has rights to the video and to the voices |
| Options | `pause_after_translation` (default false), `audio_stream_index` (override, §8.1), `glossary` (names and terms) |

### 1.3 Outputs

- Dubbed video `output/dubbed.<h>.mp4` (`.mkv` when the video codec cannot be stream-copied into MP4, §11). Video stream-copied. Audio track 0 = dubbed mix (default track); track 1 = original audio. Target-language subtitles embedded.
- SRT file, validation report, and all intermediates (database rows plus artifact files, §6.6). The final video is never the only source of truth.

### 1.4 Scope limits

- Typical input 60–90 minutes. `MAX_VIDEO_MINUTES = 120` (default); longer inputs are rejected before any compute (§8.1).
- Not in this release: lip sync; changing video timing (video is never sped up or slowed); authentication or multiple users; cloud storage; server-sent events (polling only); background mode chosen per region.
- Voice expectation: each actor gets a consistent timbre and gender in the target language. The output does not reproduce the original actor's accent or emotional performance exactly.

### 1.5 Legal and consent

- Process only content the user has the right to dub. Use voice references only with consent. Test only with rights-cleared footage (`docs/footage.md`); never copyrighted TV footage.
- Keep the TTS watermark. Label outputs as AI-dubbed (§11).
- Speaker embeddings and reference clips are biometric data: scoped to one job, never reused across jobs, deleted by `DELETE /api/jobs/{id}`.
- Non-commercial models are disabled by default (§4.3).

---

## 2. Definition of Done

The release is done when every row holds on the reference machine (§18.1). "Golden clips" are the rights-cleared clips in `golden/` (§16.4).

| # | Criterion | Measure |
| --- | --- | --- |
| 1 | Input-agnostic | Every golden clip runs from an uploaded file. URL ingest is optional. |
| 2 | Hard checks | No hard-check failure (§12.1) on any golden clip. |
| 3 | Intelligibility | Re-transcription WER ≤ 25% (§12.2) on each golden clip. |
| 4 | Timing | ≤ 15% of dubbed segments use tempo > 1.10×. |
| 5 | Voice consistency | ≥ 95% of gate-eligible segments pass the drift gate (§3.2.7) within the allowed regenerations. |
| 6 | Cast review | Completed by a human on every golden clip (`cast_review_mode = human` in the report). |
| 7 | Speed | A 90-minute video completes in ≤ 3× its duration wall-clock, excluding time in `PAUSED` (stretch goal 2×; > 5× is a defect). Provisional until Phase 0; real numbers recorded in `docs/spikes.md`. |
| 8 | Resilience | After `kill -9` of the worker or a provider process at any stage, restarting the worker resumes the job, reuses verified outputs and completes. |
| 9 | Behaviour | Different actors get different voices; the same actor keeps the same voice throughout; overlapping speech is mixed at its timestamps; background audio is kept where separation allows; every stage can be retried on its own. |
| 10 | Cost | The default pipeline needs no paid API, license or SaaS. |

---

## 3. Voice consistency (central requirement)

Two separate layers: **identity** (who is who across the whole video) and **voice** (each actor sounds the same every time).

### 3.1 Identity layer

1. **Whole-file diarization** with `pyannote/speaker-diarization-community-1` for any input up to `MAX_VIDEO_MINUTES`. Chunked diarization with embedding reconciliation is a fallback, used only if whole-file diarization fails or runs out of memory (edge case 31).
2. **Second pass** (stage `BUILDING_SPEAKER_PROFILES`). Embed every clean segment (not overlapped, ≥ 1.0 s of speech) and compute per-speaker centroids. Per segment:
   - `speaker_cos` = cosine to its own speaker centroid;
   - `speaker_margin` = `speaker_cos` − highest cosine to any other centroid;
   - `speaker_confidence` = our own score computed from `speaker_cos` and `speaker_margin` (formula and thresholds calibrated in Phase 0; the diarization model provides no confidence);
   - outlier when `speaker_cos < OUTLIER_COS` or `speaker_margin < OUTLIER_MARGIN` → flag `speaker_outlier`.
   Segments too short to embed keep their diarization speaker and get `speaker_confidence = null`.
3. **Proposals** from the speaker similarity matrix (cosine between centroids):
   - merge proposal: cosine ≥ `MERGE_COS`;
   - "similar voices" warning: `SPLIT_COS` ≤ cosine < `MERGE_COS` (edge case 12);
   - split proposal: a speaker whose segment embeddings form two clusters (agglomerative; cosine between cluster centroids < `SPLIT_COS`; each cluster ≥ 5 segments and ≥ 5 s).
4. **Cast review** (stage `CAST_REVIEW`, mandatory). Job status `PAUSED`. Shown per speaker: 3 audio clips (highest confidence, spread across the timeline), segment count, speech seconds, estimated gender with confidence, the similarity matrix and the proposals. Actions: `merge`, `split` (accept a proposal or list segment ids), `rename` (display name), `ignore` (reason `crowd | tv | song | other`; that speaker's segments are not dubbed and keep original audio), `set_gender` (`female | male | unknown`), `set_voice` (§3.2.9). Actions are stored as `SpeakerOverride` rows. The effective cast (diarization + overrides) feeds the input hash of every later stage. Leave the pause with `POST /api/jobs/{id}/resume`.
5. **`--auto-cast`** (CLI) / `auto_cast=true` (API) resumes `CAST_REVIEW` with no overrides. Accepted only when `DUBBER_TEST_MODE=true`. The report records `cast_review_mode = auto | human`; only `human` counts for §2.
6. Overrides may change after later stages ran. The changed hash invalidates the affected downstream stages and segments.

### 3.2 Voice layer

1. **One canonical reference per actor**, immutable once registered.
2. **Candidates** (stage `EXTRACTING_REFERENCES`): top-3 candidate references per actor, cut from the dialogue stem. Source segments: not overlapped, `speaker_confidence ≥ REF_MIN_CONF`, ASR confidence ≥ `REF_MIN_ASR`, estimated SNR ≥ `REF_MIN_SNR_DB`, 2–12 s each. Prefer one continuous clip; otherwise join ≤ 3 clips with 150 ms silence. Clean each candidate: denoise (method chosen in Phase 0; default none), trim silence, loudness-normalize to `REF_LUFS`. Length 10–15 s by default; Phase 0 compares 5–15 s and 10–30 s and may change the default.
3. **Audition** (stage `AUDITIONING_VOICES`): each candidate synthesizes the same fixed test sentences (`config/audition_sentences.<lang>.txt`) with the first `AUDITION_SEEDS` seeds of the actor's seed list. The QC embedder (§5) embeds every output and the actor's clean source segments (same embedding space). Score = mean cosine to the actor's source centroid − `AUDITION_LAMBDA` × standard deviation across seeds. The best candidate wins if its mean cosine ≥ `AUDITION_MIN_COS`. The winner also provides `voice_cps` (target-language characters per second, used for translation budgets, §8.14) and the initial drift centroid (§3.2.7).
4. **Fallback is per actor.** If no candidate passes, or the actor is minor (< 2 s of clean speech), the whole actor uses a fixed bank voice (§3.3). This is decided in `AUDITIONING_VOICES`, before bulk TTS.
5. **Registry** (stage `REGISTERING_VOICES`): one immutable `Voice` row per actor holding the canonical reference (path, sha256), the prepared voice conditioning (prepared once, cached as a file), the seed list, the exaggeration value, the `cfg_weight` value, `voice_cps` and `source` (`cloned | fallback_bank`).
6. **Generation rules** (stage `GENERATING_TTS`):
   - Group segments by actor; within an actor, process in timeline order.
   - Before each actor's first segment, explicitly set that actor's conditioning: load the cached file, or re-prepare from the canonical reference if the cache is missing or its hash differs. Never rely on the model's current voice state; some TTS models keep the previous voice.
   - No per-segment or per-emotion references.
   - Exaggeration: one value per actor, inside a narrow band (band and default from Phase 0).
   - Seeds: a fixed per-actor seed list derived from `job_id` and `speaker_id`, logged. Attempt *k* uses seed *k*.
7. **Drift gate** on every segment with `gen_dur ≥ DRIFT_MIN_DUR_S` (default 1.0 s). Compute the cosine between the segment's QC embedding and the running centroid of that actor's accepted TTS outputs. The centroid starts from the winning audition outputs and is never compared against the source-language reference, because cross-language similarity is lower. Below `DRIFT_MIN_COS` → regenerate with the next seed, up to `DRIFT_MAX_REGENERATIONS = 3` (4 attempts in total). If no attempt passes, keep the attempt with the highest cosine and set `needs_review`. Only passing outputs update the centroid. On resume the centroid is rebuilt from stored per-segment embeddings. Shorter segments are not gated and are excluded from the §2 ratio.
8. **Optional timbre lock**: voice conversion of each generated segment to the canonical reference (Chatterbox VC). `TTS_VC_LOCK=false` unless Phase 0 shows it reduces drift.
9. **Changing an actor's voice** (`set_voice`) creates a new `Voice` and points the actor at it. `voice_id` is part of every segment hash, so all of that actor's segments regenerate. A voice never changes in the middle of a video.

### 3.3 Fallback voice bank

- `assets/voice_bank/`: 4–6 clips (≥ 2 female, ≥ 2 male, 1–2 neutral), each with `LICENSE` and `PROVENANCE` files. Allowed sources: synthetic voices from a permissively licensed TTS, or recordings of people who consented to voice cloning. The license must allow redistribution. Target-language clips are preferred, because a same-language reference avoids accent transfer.
- Assignment per actor: by effective gender (`unknown` → neutral), in a fixed order, and avoiding reuse while unused bank voices of that gender remain. Reuse produces a warning.

### 3.4 Gender

- F0 heuristic (librosa pYIN) on clean voiced frames: median F0 < `GENDER_MALE_MAX_HZ` (≈ 155) → `male`; > `GENDER_FEMALE_MIN_HZ` (≈ 185) → `female`; otherwise `unknown`. Confidence comes from the margin to the band and the amount of voiced audio. Whispered or barely voiced speech → `unknown`. Bands are calibrated in Phase 0.
- Gender is an estimate of voice pitch. It is used only to choose bank voices and is shown (editable) in cast review. It never decides speaker identity, and unknown gender never fails a job.
- The audeering age/gender model exists only as an optional non-commercial plugin (§4.3).

---

## 4. Licensing and license gate

### 4.1 Policy

- Intended use: license-safe by default, meaning the default configuration must permit commercial use. "Zero cost" means no paid API, license or SaaS; the only resource spent is local compute.
- Allowed model licenses: MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC, MPL-2.0, Unlicense, CC0-1.0, CC-BY-4.0 (attribution in `NOTICE`). Custom terms (for example the Gemma Terms of Use) only if listed in `config/license_allowlist.yaml` with a note.
- Blocked: non-commercial, research-only, NC share-alike, or unknown.

### 4.2 `models.lock.json` and the gate

- Fields per model: `id`, `role`, `source` (`hf | ollama | url | package`), `ref` (repo, registry name or URL), `revision` (commit sha or registry digest), `files` with `sha256` of the main weights, `license_spdx`, `commercial_ok`, `gated`, `attribution`, `notes` (training-data caveats).
- A provider refuses to load a model whose revision or hash differs from the lock (edge case 41), or whose `commercial_ok` is false while `ALLOW_NONCOMMERCIAL_MODELS=false` (raises `LicenseBlockedError`; unit-tested).
- Providers load models from explicit local paths and run with `HF_HUB_OFFLINE=1` (and equivalent switches) after preflight, so libraries cannot download sub-models that are not in the lock.
- `scripts/license_report.py` generates `MODEL_LICENSES.md` and `NOTICE` from the lock file. Re-read each model card when locking; licenses change.
- Hugging Face token: read from an env var or Docker secret, never logged; needed only to download gated models. `python -m dubber doctor` lists gates not yet accepted. Gated models work offline once downloaded.

### 4.3 Non-commercial plugins

Optional. Never defaults. Loadable only when `ALLOW_NONCOMMERCIAL_MODELS=true`:

| Plugin | Role | License |
| --- | --- | --- |
| XTTS-v2 | TTS | Coqui Public Model License (non-commercial; vendor defunct) |
| NLLB-200 | Translation | CC-BY-NC-4.0 |
| audeering wav2vec2 age/gender | Gender | CC-BY-NC-SA-4.0 |

Keep them disabled for any commercial use, including internal use within a company.

### 4.4 Packages and tools

- Python and npm package licenses are audited by `scripts/license_report.py` into `THIRD_PARTY_LICENSES.md`. Runtime packages: permissive, MPL-2.0, or LGPL (unmodified, dynamically used). GPL packages only in dev-only tooling (for example fixture generation), never imported by the shipped runtime.
- FFmpeg is installed by the user and run as an executable; it is not redistributed in this release. Use the native `aac` encoder (never `libfdk_aac`). Never depend on GPL-only filters such as `rubberband`. A future image that bundles FFmpeg must use an LGPL build.

---

## 5. Stack

"Default" means the candidate that Phase 0 must confirm; Phase 0 results go to `docs/spikes.md` and `config/defaults.yaml`.

| Role | Default | Fallback / optional | Notes |
| --- | --- | --- | --- |
| Ingest | File upload; yt-dlp (Unlicense) for URLs | — | URL path needs Deno and `yt-dlp-ejs`; best-effort |
| VAD | Silero VAD (MIT) | — | No token needed |
| Audio events | Tagger chosen in Phase 0 (license-checked) | — | Singing, laughter, crying, screams, sighs (edge cases 46, 47) |
| ASR | mlx-whisper (MIT), Whisper large-v3 or large-v3-turbo, Metal | faster-whisper (MIT), CPU int8; CUDA on the Linux profile | Size from Phase 0 |
| Language ID | Whisper language detection per segment | — | Edge case 48 |
| Word alignment | WhisperX `align()` (BSD-2-Clause) with the per-language wav2vec2 model | Whisper word timestamps | Turkish alignment model license audited in Phase 0 |
| Separation | Demucs v4 `htdemucs` from the maintained `adefossez/demucs` fork (MIT code; training-data terms to verify) | TIGER-DnR (cinematic 3-stem; ~1.3× real time on a T4, too slow as default); Bandit v2 (weights license to confirm) | Demucs is a music separator: singing goes to the dialogue stem, so singing detection (edge case 46) must keep songs from the original |
| Diarization | `pyannote/speaker-diarization-community-1` (CC-BY-4.0, gated, free), MPS | CPU | MPS is not officially supported: parity test required (§16) |
| Identity embeddings | From the pyannote pipeline, if exposed | WeSpeaker or SpeechBrain ECAPA (Apache-2.0; check training-data terms) | |
| QC embedder | Chosen in Phase 0 | — | Used for audition and the drift gate; must load inside the TTS worker without dependency conflicts |
| Gender | F0 heuristic (librosa pYIN, ISC) | audeering model (non-commercial plugin) | |
| Translation | TranslateGemma 4B or 12B (Gemma Terms of Use, allowlisted) via Ollama on the host | `Helsinki-NLP/opus-mt-tr-en` (Apache-2.0); MADLAD-400 3B (Apache-2.0) for other pairs; NLLB-200 (non-commercial plugin) | Size from Phase 0 by memory |
| Rewrite (shorten) | Apache-2.0 instruct LLM (for example Qwen3) via Ollama, thinking disabled | — | |
| TTS | Chatterbox Multilingual V3 (MIT; 23 languages incl. Turkish and English) | Chatterbox English, Turbo, Nano; Qwen3-TTS 0.6B/1.7B (Apache-2.0, no Turkish); `chatterbox-mlx` fork (candidate only); XTTS-v2 (non-commercial plugin) | Backend CPU, MPS or hybrid-MLX from Phase 0 |
| Voice conversion | Chatterbox VC (MIT), optional | — | §3.2.8 |
| TTS text normalization | Permissively licensed number-to-words library (for example `inflect`, MIT) | — | §8.14 |
| Reference denoise | None | DeepFilterNet (MIT/Apache-2.0) if Phase 0 shows a benefit | §3.2.2 |
| Mix and render | FFmpeg and ffprobe | — | Native `aac` encoder |

Notes:

- Chatterbox embeds the Perth watermark in all output. Keep it; never strip it.
- Provider environments pin Python 3.11.
- `transformers` v5 is reported to have removed `pipeline("translation")`; load `AutoModelForSeq2SeqLM` directly (verify in Phase 0).
- `cfg_weight` default is **0.5**, stored per voice. Try 0.3 for a voice whose Turkish accent is too strong. `0` is not used: although the Chatterbox README advises it for cross-language references, it makes clips longer and doubles truncations.
- Ollama runs on the host. Every request sets `keep_alive=0` (or the model is unloaded at the end of the stage) so memory is free for the next model process.

---

## 6. Architecture

### 6.1 Processes

| Process | What | Rules |
| --- | --- | --- |
| api | FastAPI on `127.0.0.1:8000` | Never runs stages. No auth in this release; do not expose the port. No ML imports. |
| worker | `python -m dubber worker` | Stage engine and DB-backed queue; one job at a time; no ML imports. |
| provider | `providers/<name>/`, own `pyproject.toml` and `uv.lock`, run as a subprocess | One model family per process; the process exits after each call, which frees memory. |
| ollama | Host service | Translation and rewrite LLMs. |
| frontend | React + Vite + TypeScript | Talks only to the api. |
| CLI | `python -m dubber run --input file.mp4 --src tr --tgt en`, plus `doctor`, `worker`, `cast` | Same engine; no Docker needed. |

- api and worker share one SQLite database in WAL mode. Queue is DB-backed; no Redis.
- Docker Compose covers api and frontend only. ML workers run natively with uv, because Docker on macOS has no GPU access. An optional later profile, `linux-nvidia`, targets a CUDA host.
- Exactly one model process runs at a time (a global lock in the worker). Peak memory = the largest single model process, plus Ollama only while it is loaded (`keep_alive=0` keeps that at zero between calls).

### 6.2 Provider protocol

- The worker writes `request.json` (`schema_version`, input paths, config, model lock ids, device) and starts the provider. The provider appends NDJSON events (progress, heartbeat, per-item results) to `events.ndjson` and writes `result.json`. stdout and stderr go to `stderr.log`. All under `runs/<stage>/<attempt>/` (§6.6). Files pass by path; tensors never cross the boundary.
- Interfaces are batch-shaped (§6.3). Per-item results are checkpointed as they complete, so a restart redoes only unfinished items.
- A stage may call several provider processes, strictly one after another (for example `FIT_AND_PLACE` calls translation, then TTS).
- Typed errors: `Retryable`, `NeedsSmallerConfig`, `Fatal`, `LicenseBlockedError`. Out-of-memory (CUDA or MPS allocation errors, or the process killed with SIGKILL by macOS memory pressure while no cancel was requested) maps to `NeedsSmallerConfig`.
- The worker records the provider's PID and process group on the `StageRun`. On startup it kills orphaned provider processes before reclaiming leases.
- Cancel: SIGTERM to the process group, SIGKILL after 10 s.

### 6.3 Provider interfaces (Protocols)

```python
class VADProvider(Protocol):
    def speech_regions(self, wavs: list[Path]) -> list[list[Region]]: ...
class AudioEventProvider(Protocol):
    def tag(self, wav: Path, labels: list[str]) -> list[EventRegion]: ...
class TranscriptionProvider(Protocol):
    def transcribe(self, wav: Path, regions: list[Region], language: str, cfg: AsrConfig) -> Transcript: ...
    def detect_language(self, clips: list[Clip]) -> list[LanguageGuess]: ...
class AlignmentProvider(Protocol):
    def align(self, wav: Path, transcript: Transcript, language: str) -> AlignedTranscript: ...
class SeparationProvider(Protocol):
    def separate(self, wav: Path, out_dir: Path) -> SeparationResult: ...  # dialogue, background
class DiarizationProvider(Protocol):
    def diarize(self, wav: Path, cfg: DiarCfg) -> Diarization: ...  # turns, exclusive turns, embeddings if exposed
class EmbeddingProvider(Protocol):
    def embed(self, clips: list[Clip]) -> list[Embedding]: ...
class GenderProvider(Protocol):
    def classify(self, clips_by_speaker: dict[str, list[Clip]]) -> dict[str, GenderResult]: ...
class TranslationProvider(Protocol):
    def translate(self, groups: list[SegmentGroup], ctx: TranslationContext) -> list[Translation]: ...
    def rewrite_shorter(self, items: list[RewriteRequest]) -> list[Translation]: ...
class TTSProvider(Protocol):
    def prepare_voice(self, reference: Path, meta: VoiceMeta) -> VoiceConditioning: ...
    def synthesize(self, items: list[TtsItem], voice: VoiceConditioning, gate: DriftGate) -> list[TtsResult]: ...
```

- All inputs and outputs are Pydantic models with `schema_version`. Providers are registered by name from config.
- `synthesize` takes items for one actor. The drift gate (§3.2.7) runs inside the TTS worker with the QC embedder loaded in the same process; `TtsResult` returns the chosen attempt, its seed, its embedding and all attempt scores.

### 6.4 Stage engine

- Each stage declares `inputs`, `outputs`, `version`, `config_keys`.
- `input_hash = sha256(input artifact sha256s + stage version + relevant config + model lock revisions + hash of the DB state the stage reads)`. DB state includes the effective cast, segment texts and overrides, and voice ids.
- A completed `StageRun` with the same `input_hash` and verified outputs is not rerun; the new run is recorded as `REUSED`.
- Segment-level key: `seg_hash = sha256(tts_text + voice_id + conditioning sha256 + TTS params + seed + model lock revision)`. It is part of the segment's file names, so changed text, voice or params can never reuse stale audio.
- Manifest: every output is an `Artifact` row (kind, path, size, sha256), also exported to `manifest.json`. Verify before reuse; a mismatch means corruption, so invalidate that stage and everything downstream (edge case 43).
- Atomic writes: outputs are written to `runs/<stage>/<attempt>/tmp/` (same filesystem), then renamed into place. Never overwrite a file recorded by a completed `StageRun`.
- Leases: a running `StageRun` holds `worker_id` and `heartbeat_at` (refreshed from provider events). On startup, stale leases are reclaimed (after killing orphans) and rerun.
- Retry: per-stage `max_attempts` with exponential backoff for `Retryable`. `NeedsSmallerConfig` steps down `OOM_BACKOFF` (§6.5). `Fatal` fails the job. stderr of FFmpeg and provider failures is stored.
- Cancel: cooperative, checked between items; the provider subprocess is terminated.
- Progress = completed stages weighted by typical cost, plus completed items in the current stage (from provider events). No timers.
- Disk guard: before each stage, estimate the space it needs; if free space < estimate + `DISK_RESERVE_GB`, fail early with a readable message (edge case 37).
- `KEEP_INTERMEDIATES=true` by default. When false, intermediates are deleted only after `VALIDATING` succeeds.
- The effective config, including any out-of-memory downgrade, is stored on the `StageRun` and in the report.

### 6.5 Config (pydantic-settings, env-overridable)

| Group | Keys |
| --- | --- |
| Providers and models | `PROVIDER_<ROLE>`, model sizes and variants, compute dtype, batch sizes, chunk seconds |
| Devices | `DEVICE_<ROLE>` = `auto | mps | cpu | cuda` (`auto` prefers MPS on Apple Silicon, then CPU) |
| Inputs | `ASR_INPUT`, `DIARIZATION_INPUT` = `dialogue | original` (default from Phase 0) |
| Policy | `ALLOW_NONCOMMERCIAL_MODELS=false`, `ALLOW_SINGLE_SPEAKER_FALLBACK=false`, `FOREIGN_SPEECH_POLICY=keep_original`, `FIT_TERMINAL_POLICY=truncate`, `BACKGROUND_MODE=auto`, `TTS_VC_LOCK=false`, `DUBBER_TEST_MODE=false` |
| Limits | `MAX_VIDEO_MINUTES=120`, `MAX_UPLOAD_GB`, `DISK_RESERVE_GB`, `OOM_BACKOFF` (ordered list: smaller batch → shorter chunk → quantized or smaller model → CPU) |
| Thresholds | Voice (§3), segments (§8.8), fitting (§9), mixing (§10), validation (§12) |
| Storage | `DATA_DIR` (default `./data`), `KEEP_INTERMEDIATES=true` |

Memory-dependent defaults (Whisper size, TranslateGemma size, Chatterbox variant and backend) are set by Phase 0 in `config/defaults.yaml`.

### 6.6 Job directory layout

Root: `<DATA_DIR>/jobs/<job_id>/`. `<h>` = first 12 hex characters of the producing `input_hash` (or `seg_hash` for per-segment files). Storage is the local filesystem behind a thin interface.

```
source/source.<ext>                           original upload or download; extension from the container
source/probe.json                             ffprobe output
audio/source_48k.<h>.wav                      selected track, offset-corrected, stereo float32
audio/source_16k_mono.<h>.wav                 model input
audio/source_16k_mono_asr.<h>.wav             loudness-normalized ASR copy (quiet audio only)
separation/dialogue.<h>.wav
separation/background.<h>.wav
analysis/vad.<h>.json                         speech regions: original, dialogue, background
analysis/events.<h>.json                      audio-event regions
analysis/separation_metrics.<h>.json
transcription/transcription.<h>.json          incl. per-segment language ID
transcription/aligned.<h>.json
diarization/diarization.<h>.rttm
diarization/exclusive.<h>.rttm
diarization/speakers.<h>.json
segments/segments.<h>.json                    DB export
speakers/embeddings.<h>.npy                   + embeddings.<h>.index.json
speakers/profiles.<h>.json                    centroids, confidence, similarity matrix, proposals (DB export)
speakers/review/<speaker>_<n>.<h>.wav         cast-review clips
voices/<speaker>/candidates/cand_<n>.<h>.wav
voices/<speaker>/audition/<cand>_<seed>_<k>.<h>.wav
voices/<speaker>/reference.<h>.wav            canonical reference (immutable)
voices/<speaker>/conditioning.<h>.<ext>       cached voice conditioning
translation/translations.<h>.json             DB export
tts/segment_<idx6>.<h>.wav                    accepted TTS attempt
tts/attempts/segment_<idx6>.<seed>.<h>.wav    rejected attempts (kept while KEEP_INTERMEDIATES)
tts/embeddings/segment_<idx6>.<h>.npy         QC embedding of the accepted attempt
fit/segment_<idx6>.<h>.wav                    tempo-adjusted or trimmed clip
mix/blocks/dialogue_<blk3>.<h>.wav            5-minute dialogue blocks with overlap
mix/dialogue.<h>.wav
mix/mixed.<h>.wav                             pre-encode master
output/dubbed.<h>.mp4 | output/dubbed.<h>.mkv
output/subtitles.<lang>.<h>.srt
output/report.<h>.json
manifest.json                                 export of the Artifact rows
runs/<stage>/<attempt>/request.json | result.json | events.ndjson | stderr.log | tmp/
```

Shared, outside jobs: `assets/voice_bank/`, the Hugging Face cache, the Ollama model store.

---

## 7. Data model

SQLite via SQLAlchemy, WAL mode, schema migrations (tool chosen in Phase 1). **The database is the authority for everything editable** (segments, translations, speakers, voices, overrides). JSON files in §6.6 are exports for debugging and reuse checks. Every edit writes the DB row plus an override row, and the affected stages' `input_hash` includes that DB state, so "regenerate" can never reuse stale audio.

### 7.1 Status values

| Field | Values |
| --- | --- |
| `Job.status` | `QUEUED`, `RUNNING`, `PAUSED`, `COMPLETED`, `FAILED`, `CANCELLED` |
| `Job.current_stage` | One of the 20 stage names in §8.0; null while `QUEUED` before the first stage |
| `StageRun.status` | `PENDING`, `RUNNING`, `SUCCEEDED`, `REUSED`, `SKIPPED`, `FAILED`, `CANCELLED` |
| `Segment.dub_status` | `PENDING`, `TRANSLATED`, `SYNTHESIZED`, `PLACED`, `KEPT_ORIGINAL` |
| `Segment.skip_reason` (when `KEPT_ORIGINAL`) | `hallucination`, `low_confidence`, `ignored_speaker`, `singing`, `foreign_language`, `translation_failed`, `tts_failed`, `fit_terminal`, `user_skip` |

- `PAUSED` occurs only with `current_stage` = `CAST_REVIEW` or `TRANSLATION_REVIEW`.
- `COMPLETED` only if every hard check passes (§12.1); soft-check failures add warnings and `needs_review` flags.
- `SKIPPED` marks an optional stage that is switched off (`TRANSLATION_REVIEW` when `pause_after_translation=false`).

### 7.2 Tables

| Table | Fields |
| --- | --- |
| `Job` | id, status, current_stage, progress, source_type (`upload | url`), source_url (nullable), original_filename, source_sha256, source_language, target_language, consent_confirmed, idempotency_key, config_snapshot JSON, background_mode, audio_stream_index, audio_offset_s, pause_after_translation, cast_review_mode (`human | auto`), error_type, error_message, warnings JSON, metadata JSON, created_at, updated_at |
| `StageRun` | id, job_id, stage, attempt, status, input_hash, effective_config JSON, worker_id, heartbeat_at, provider_pid, started_at, finished_at, error_type, error_message, stderr_path, metrics JSON |
| `Artifact` | id, job_id, stage_run_id, kind (`source`, `audio`, `stem`, `analysis`, `transcript`, `diarization`, `segments`, `embeddings`, `review_clip`, `reference`, `conditioning`, `translations`, `tts_segment`, `fit_segment`, `mix`, `video_mp4`, `video_mkv`, `srt`, `report`, `manifest`), name (unique per job), path, sha256, size, downloadable, created_at |
| `Segment` | id, job_id, idx, speaker_id, src_start, src_end, src_text, src_words JSON, language, language_confidence, asr_confidence, avg_logprob, no_speech_prob, is_overlap, assignment_overlap, speaker_cos, speaker_margin, speaker_confidence, flags JSON, available_s, hard_limit_s, tgt_text, tts_text, tgt_budget_chars, rewrite_count, dub_status, skip_reason, voice_id, seed, tts_attempts, drift_cos, seg_hash, tts_path, gen_dur, final_dur, fit_method, placement_start, needs_review, warnings JSON |
| `SpeakerProfile` | id, job_id, speaker_label, display_name, status (`active | minor | ignored | merged`), merged_into, speech_seconds, segment_count, gender, gender_confidence, voice_id, reference_segment_ids JSON, reference_quality, similar_to JSON |
| `SpeakerOverride` | id, job_id, seq, action (`merge | split | rename | ignore | set_gender | set_voice`), payload JSON, created_at |
| `SegmentOverride` | id, job_id, segment_id, seq, field (`tgt_text | skip | regenerate`), value JSON, created_at |
| `Voice` | voice_id, job_id, speaker_id, source (`cloned | fallback_bank`), provider, model_lock_id, reference_path, reference_sha256, conditioning_path, conditioning_sha256, seed_list JSON, exaggeration, cfg_weight, voice_cps, audition_score, fallback_reason, created_at. Immutable. |
| `Metric` | id, job_id, stage, name, value, unit, created_at (processing time, CPU time, accelerator time, peak memory, model ids, WER, drift, LUFS) |

---

## 8. Pipeline stages

### 8.0 Canonical stage list

`Job.current_stage`, `StageRun.stage`, the API and the UI use exactly these names, in this order.

| # | Stage | Does | Provider processes | Main outputs |
| --- | --- | --- | --- | --- |
| 1 | `INGESTING` | Upload or URL, probe, limits, track choice | — (yt-dlp, ffprobe) | `source/` |
| 2 | `EXTRACTING_AUDIO` | Track, offset, downmix, resample | — (ffmpeg) | `audio/` |
| 3 | `SEPARATING_AUDIO` | Dialogue and background stems | separation | `separation/` |
| 4 | `DETECTING_SPEECH` | VAD on original and stems, audio events, separation metrics | vad, audio_events | `analysis/` |
| 5 | `TRANSCRIBING` | VAD-gated ASR, hallucination filters, language ID | asr | `transcription.json` |
| 6 | `ALIGNING_WORDS` | Word timestamps | alignment | `aligned.json` |
| 7 | `DIARIZING` | Whole-file diarization | diarization | `diarization/` |
| 8 | `BUILDING_SEGMENTS` | Words → speakers → segments, flags, timing slots | — | Segment rows |
| 9 | `BUILDING_SPEAKER_PROFILES` | Embeddings, confidence, proposals, gender, review clips | embedding, gender | `speakers/` |
| 10 | `CAST_REVIEW` | Pause for human cast review | — | SpeakerOverride rows |
| 11 | `EXTRACTING_REFERENCES` | Top-3 candidate references per actor | — (optional denoise provider) | `voices/*/candidates/` |
| 12 | `AUDITIONING_VOICES` | Audition; canonical reference or bank voice | tts (+ QC embedder) | `voices/*/audition/` |
| 13 | `REGISTERING_VOICES` | Immutable Voice rows, cached conditioning | tts | `voices/*/reference`, `conditioning` |
| 14 | `TRANSLATING` | Context-aware, budgeted translation | translation; opus-mt fallback | Segment rows |
| 15 | `TRANSLATION_REVIEW` | Optional pause | — | SegmentOverride rows |
| 16 | `GENERATING_TTS` | Synthesis with drift gate | tts (+ QC embedder) | `tts/` |
| 17 | `FIT_AND_PLACE` | Timing (§9), batched rewrite rounds | translation, tts | `fit/` |
| 18 | `MIXING_AUDIO` | Background mode, assembly, loudness, ducking | — (numpy, ffmpeg) | `mix/` |
| 19 | `RENDERING_VIDEO` | Mux, metadata, subtitles | — (ffmpeg) | `output/` |
| 20 | `VALIDATING` | Hard and soft checks, report | asr (WER sample) | `output/report` |

### 8.1 INGESTING

1. Upload: stream to `source/source.<ext>` (extension from the probed container, never from the user's filename); compute sha256 while streaming; enforce `MAX_UPLOAD_GB`.
2. URL: `http(s)` only. Resolve DNS and block private, loopback, link-local, CGNAT and unique-local ranges. Run yt-dlp as a subprocess with timeout, `--no-playlist`, an extractor allowlist (`URL_EXTRACTORS`); fetch metadata first (duration check), then download; prefer `avc1` + `mp4a` formats. Log the yt-dlp version at startup; warn if it is older than 60 days. Known limitation: pre-resolution checks do not cover redirects or DNS rebinding; acceptable while the API binds to localhost.
3. Probe with ffprobe. Duration > `MAX_VIDEO_MINUTES` → `Fatal` with a readable error, before any other compute (edge case 51). No audio stream → `Fatal` (edge case 5).
4. Audio track (edge case 50): `audio_stream_index` if given; else the stream whose language tag matches the source language (`tr`/`tur`); else the default-disposition stream; else the first. Record the choice and the reason on the job.
5. `consent_confirmed` must be true. Idempotency key = sha256(source sha256 or normalized URL + languages + config snapshot hash). A duplicate returns the existing job (edge case 35).

### 8.2 EXTRACTING_AUDIO

1. Start offset (edge case 49): read `start_time` of the selected audio and video streams; pad or trim the start so that t = 0 equals the first video presentation time; store `audio_offset_s`.
2. Downmix (edge case 50): more than 2 channels → stereo using explicit ITU-R BS.775 coefficients (center −3 dB into both channels, surrounds −3 dB, LFE dropped). Record the source layout.
3. Write `source_48k` (stereo float32) and `source_16k_mono`. Integrated loudness < `QUIET_LUFS` (default −40 LUFS) → warning plus a normalized copy used only for ASR (edge case 6).

### 8.3 SEPARATING_AUDIO

1. Provider's chunked inference with overlap for long audio. Outputs `dialogue` and `background` (music + effects) at 48 kHz.
2. Separation failure → warning; the job continues and `MIXING_AUDIO` uses a mode without stems (edge case 28).

### 8.4 DETECTING_SPEECH

1. Silero VAD on the original, dialogue and background (16 kHz mono).
2. Audio-event tagging: singing, music, laughter, crying, screaming, sighs.
3. Separation metrics: `speech_in_background` (VAD speech seconds on the background stem ÷ on the original), `background_in_dialogue` (dialogue-stem energy where the original has no speech), `dialogue_coverage` (share of original speech present in the dialogue stem).

### 8.5 TRANSCRIBING

1. Input per `ASR_INPUT`. Transcribe only VAD speech regions (merged, padded 0.2 s, windows ≤ 30 s), `condition_on_previous_text=False`, fixed source language. Checkpoint per window.
2. Hallucination filters (edge case 18); flagged segments are never dubbed: `no_speech_prob > 0.6` together with `avg_logprob < −1.0`; `compression_ratio > 2.4`; repeated n-grams; phrases in `config/hallucination_blacklist.<lang>.txt` (for Turkish, subtitle-credit phrases Whisper emits on silence); < 50% overlap with VAD speech. All thresholds are configurable.
3. Language ID (edge case 48): for segments ≥ 1.0 s, detect the language. If the top language is not the source language and its probability ≥ `LID_MIN_CONF`, flag `foreign_language` and re-transcribe that segment in the detected language for the record. Never force-transcribe it as the source language. With `FOREIGN_SPEECH_POLICY=keep_original` (default) the segment is not dubbed. Shorter segments inherit the language of their neighbours.
4. Persist all confidences.

### 8.6 ALIGNING_WORDS

1. WhisperX `align()` with the source-language alignment model if its license passes the gate; otherwise use Whisper word timestamps.
2. Words the aligner cannot time (digits, symbols) take Whisper timestamps, or are interpolated between neighbours.
3. Timestamp sanity (edge case 19): start < end, monotonic, within media duration; clamp and flag violations.

### 8.7 DIARIZING

1. Whole-file community-1 on `DIARIZATION_INPUT`; regular and exclusive diarization; RTTM; per-speaker embeddings if the pipeline exposes them. Device MPS with CPU fallback.
2. Failure: retry. Out of memory → chunked diarization with embedding reconciliation (edge case 31). Still failing: single speaker with a warning only if `ALLOW_SINGLE_SPEAKER_FALLBACK=true`; otherwise the job fails.

### 8.8 BUILDING_SEGMENTS

1. Assign each word to the exclusive-diarization speaker with maximum overlap. Words with no overlap → nearest turn within 0.5 s; otherwise speaker `unknown` and flagged.
2. Split at speaker changes. Merge same-speaker fragments when the gap is < 0.35 s and no sentence end intervenes. Cap at 12 s (split at punctuation, else at the largest word gap).
3. Minimum 0.3 s, except complete short utterances ("Evet", "Ne?"), kept when separated from the same speaker's other speech by ≥ 0.25 s on both sides (edge case 23). Other fragments under 0.3 s merge into the adjacent same-speaker segment, otherwise they are dropped and flagged.
4. `assignment_overlap` = share of the segment covered by the assigned speaker's exclusive turns. `is_overlap` = another speaker's regular turn covers > 20% of the segment (edge case 15).
5. Not dubbed (`KEPT_ORIGINAL`): hallucination flags; singing (singing events cover > 50% of the segment; edge case 46); `foreign_language` under the default policy; speaker `unknown` with low ASR confidence; background, TV and crowd voices (low `assignment_overlap` and speech also present on the background stem → `low_confidence`; edge cases 16, 17).
6. Compute each segment's `next_speech`, `hard_limit_s` and `available_s` (§9); translation budgets use them.

### 8.9 BUILDING_SPEAKER_PROFILES

§3.1 items 2–3, gender (§3.4), cast-review clips. Speakers with < 2 s of clean speech get `status = minor`.

### 8.10 CAST_REVIEW

§3.1 items 4–6.

### 8.11 EXTRACTING_REFERENCES

§3.2 item 2. Actors with `status = ignored` get no references.

### 8.12 AUDITIONING_VOICES

§3.2 items 3–4.

### 8.13 REGISTERING_VOICES

§3.2 item 5.

### 8.14 TRANSLATING

1. Dubbable segments only. Group consecutive segments of one speaker with gaps < 1 s into utterances (≤ 6 segments each).
2. Prompt: the utterance; the previous 3 and next 1 source sentences; the glossary (job glossary plus detected names and numbers); a character budget per segment. Output: JSON keyed by segment id.
3. Budget: `tgt_budget_chars = floor(available_s × voice_cps × 0.95)`, with `voice_cps` from the actor's `Voice`.
4. Validate: the JSON parses, every id is present, no text is empty, digits are preserved, glossary names are present. Characters outside the TTS character set are normalized or stripped (edge case 25). On failure: retry once → translate per segment with context → opus-mt → `KEPT_ORIGINAL` with `translation_failed`, keeping the source text (edge case 24).
5. `tgt_text` = display and subtitle text (numbers as digits). `tts_text` = text for speech (numbers as words, abbreviations expanded).

### 8.15 TRANSLATION_REVIEW

If `pause_after_translation`: job `PAUSED`; the user edits `tgt_text` or skips segments (SegmentOverride rows) and resumes. Otherwise the stage is `SKIPPED`.

### 8.16 GENERATING_TTS

1. §3.2 items 6–8.
2. `tts_text` longer than `TTS_MAX_CHARS` (from Phase 0) is split at sentence boundaries and joined with 80 ms gaps.
3. Duration sanity: `gen_dur` outside [0.4, 2.0] × expected duration (`len(tts_text) / voice_cps`) counts as a failed attempt (babble or truncation) and moves to the next seed.
4. No usable attempt after all seeds → `KEPT_ORIGINAL` with `tts_failed` and `needs_review` (edge case 26).
5. Results are checkpointed per segment.

### 8.17 FIT_AND_PLACE

§9.

### 8.18 MIXING_AUDIO

§10.

### 8.19 RENDERING_VIDEO

§11.

### 8.20 VALIDATING

§12.

---

## 9. Timing and fitting

Per segment:

| Term | Definition |
| --- | --- |
| `src_dur` | `src_end − src_start` |
| `next_speech` | Start of the earliest speech after `src_end`, from any other segment (dubbed or kept original) or any VAD speech region on the original. Segments that overlap this one in the source are excluded: source overlaps are reproduced, not avoided. Last segment: media end. |
| `guard` | 0.12 s |
| `hard_limit_s` | `next_speech − guard − src_start`; never crossed |
| `available_s` | `min(hard_limit_s, 1.25 × src_dur)` |
| `r` | `gen_dur / available_s` |

Rules:

1. `r ≤ 1.0`: accept. Place at `src_start`; pad with silence; never slow speech down. `fit_method = none`.
2. `1.0 < r ≤ 1.10`: FFmpeg `atempo = r`. `fit_method = tempo`.
3. `r > 1.10`: rewrite rounds. All such segments go in one batch to `rewrite_shorter` with budget `floor(available_s × voice_cps × 0.9)`, then one TTS batch regenerates them (drift gate applies); recompute `r`. At most 2 rounds. Then apply rule 1 or 2, or `atempo` up to 1.25 if `r ≤ 1.25`. `fit_method = rewrite` or `rewrite+tempo`.
4. Still `r > 1.25` after the rounds: `atempo = 1.25`. If the result ends before `hard_limit_s`, it overflows into the following silence with a 150 ms fade-out: `fit_method = overflow`, `needs_review = true`. Otherwise apply `FIT_TERMINAL_POLICY`: `truncate` (default) cuts at `hard_limit_s` with a 150 ms fade-out (`fit_method = truncated`, `needs_review = true`); `keep_original` sets `KEPT_ORIGINAL` with `fit_terminal`.
5. `gen_dur < 0.5 × src_dur`: keep as is, placed at `src_start` (edge case 22).
6. Never overwrite later dialogue. Never use the `rubberband` filter. Never change video timing.

Each rewrite round is one translation process call plus one TTS process call; the round number is part of the stage input hash. Persist `gen_dur`, `final_dur`, `fit_method`, `rewrite_count`, `tts_attempts`, `placement_start`. All thresholds live in config: initial values from Phase 0, checked on fixtures in Phase 6, tuned on golden clips in Phase 11.

---

## 10. Mixing

1. **Background mode**, chosen in this stage because it needs the final segment spans. `BACKGROUND_MODE=auto` picks the least destructive mode that passes; the choice is stored on the job. One mode per job.

   | Mode | Background | Chosen when |
   | --- | --- | --- |
   | `separated` | Background stem | Separation succeeded, `speech_in_background ≤ SEP_MAX_SPEECH_IN_BG` and `dialogue_coverage ≥ SEP_MIN_DIALOGUE_COVERAGE` |
   | `speech_mask_ducked_original` | Original mix, attenuated by `MASK_DUCK_DB` (12–20 dB, default 15) under a smoothed mask of the dubbed spans | `separated` fails its thresholds, or separation failed |
   | `attenuated_original` | Original mix at −`ATTEN_DB` (default 12 dB), except kept-original spans | Only when forced by config |

2. **Original dialogue restore** (`separated` mode only):
   - Kept-original segments (any `skip_reason`) and ignored speakers: dialogue stem at 0 dB over the segment span, 50 ms fades.
   - Non-verbal lay-back (edge case 47): dialogue stem at `NONVERBAL_GAIN_DB` (default −6 dB) everywhere outside dubbed spans, excluding `DUB_SPAN_MARGIN` (default 100 ms) around each dubbed span, with 20 ms fades.
   - Inside dubbed spans the dialogue stem is fully removed (tested for Turkish leakage).
   - In the two original-mix modes the original dialogue is already present; ducking applies only to dubbed spans, so kept-original regions stay at their original level.
3. **Dialogue assembly** in blocks of `BLOCK_SECONDS` (default 300) with 2 s crossfaded overlap; within a block, per-speaker tracks are summed (overlaps are mixed, never serialized; edge case 15); every clip gets 10–20 ms fades (edge case 30). Blocks are concatenated, or memory-mapped. Full-length multi-track audio is never held in RAM; a 90-minute stereo 48 kHz float32 track is about 2 GB.
4. **Loudness match**: each clip is gain-matched to the original dialogue loudness over the same span (short-term LUFS; spans < 400 ms use RMS), clamped to ±12 dB. Whispers stay quiet, shouts stay loud.
5. **Ducking**: background ducked under dubbed dialogue with FFmpeg `sidechaincompress`, in `separated` mode only (the other modes are already attenuated; no double ducking).
6. **Master**: two-pass `loudnorm` with `linear=true` to `LOUDNESS_TARGET_LUFS` (default −16) and `TRUE_PEAK_TARGET_DBTP` (default −2.0). If the second pass reports `normalization_type` other than `linear`, apply a static gain plus a true-peak limiter instead. Verify no clipping (edge case 29).
7. Background stereo is preserved; dialogue sits near the center.

---

## 11. Render

1. Video stream-copied; never re-encoded by default. MP4 when the video codec is in `MP4_COPY_CODECS` (default `h264, hevc, av1, vp9`; confirmed in Phase 0); otherwise MKV. An explicit, logged H.264 transcode is the only permitted video re-encode.
2. Audio track 0: dubbed mix, native AAC 192 kb/s, default disposition, language = target (`eng`), title "English (AI-dubbed)".
3. Audio track 1: the original selected audio stream, stream-copied (AAC if copying fails), language = source (`tur`), title "Original".
4. Subtitles: target language, `mov_text` in MP4, SRT in MKV; also written as a separate SRT file.
5. Global metadata: `comment` = "AI-dubbed; synthetic voices", plus the TTS model id.
6. Audio track 0 starts at the same presentation time as the video (edge case 49).
7. `-movflags +faststart` for MP4. FFmpeg stderr is captured on failure; the job fails with a readable message and is never `COMPLETED`.
8. Outputs are registered as `Artifact` rows (`video_mp4 | video_mkv`, `srt`, `report`).

---

## 12. Validation

### 12.1 Hard checks (any failure → job `FAILED`)

| # | Check | Edge case |
| --- | --- | --- |
| H1 | ffprobe: valid container, ≥ 1 video and ≥ 1 audio stream | 44 |
| H2 | Track 0 not silent: mean volume > −50 dB | 44 |
| H3 | Track 0 true peak ≤ −1.0 dBTP, measured on the decoded track | 29 |
| H4 | Audio and video durations within 0.5 s | 45 |
| H5 | Every segment not `KEPT_ORIGINAL` has placed audio | 26 |
| H6 | End-of-video sync: cross-correlate the background component of track 0 with track 1 over the last 60 s with enough energy; lag ≤ 45 ms | 49 |

### 12.2 Soft checks (warning + `needs_review`)

| # | Check |
| --- | --- |
| SC1 | Integrated loudness within 1.5 LU of target |
| SC2 | WER ≤ 25%: re-transcribe a random 10% sample (≥ 20 segments) of placed clips and compare with `tts_text`, both through Whisper's English text normalizer |
| SC3 | Drift gate pass rate ≥ 95% of gate-eligible segments; per-speaker standard deviation of `drift_cos` |
| SC4 | Share of segments with tempo > 1.10× ≤ 15% |
| SC5 | Similar-voice warnings, bank-voice reuse, actors on bank voices |
| SC6 | Watermark detectable in track 0 (only if Phase 0 shows the detector survives processing) |

§2 uses SC2–SC4 as pass criteria on golden clips.

### 12.3 Report

`output/report.<h>.json`, also served by `GET /api/jobs/{id}/report`: every check result, metrics, `background_mode`, `cast_review_mode`, model ids and lock revisions, effective configs, per-stage processing time, CPU time, accelerator time where measurable, peak memory, warnings. Cost metrics are also stored in `Metric`.

---

## 13. API

Binds to `127.0.0.1` by default. No authentication in this release; do not expose the port. Clients poll status every 2 s.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/jobs` | Create: multipart file **or** `source_url`; `source_language`, `target_language`, `consent_confirmed=true` (required), `pause_after_translation`, `audio_stream_index`, `glossary`. A duplicate returns the existing job. |
| GET | `/api/jobs` | List jobs (status, current_stage, progress) |
| GET | `/api/jobs/{id}` | Job detail |
| DELETE | `/api/jobs/{id}` | Cancel if running, then purge files, embeddings, references and DB rows |
| POST | `/api/jobs/{id}/retry` | Optional `from_stage`; default = first stage without verified outputs |
| POST | `/api/jobs/{id}/cancel` | Cancel |
| POST | `/api/jobs/{id}/resume` | Leave `PAUSED` (`CAST_REVIEW` or `TRANSLATION_REVIEW`) |
| GET | `/api/jobs/{id}/stages` | StageRun list |
| GET | `/api/jobs/{id}/cast` | Cast-review data: speakers, clips, similarity matrix, proposals, overrides |
| PUT | `/api/jobs/{id}/cast` | Replace the override list (`merge`, `split`, `rename`, `ignore`, `set_gender`, `set_voice`) |
| GET | `/api/jobs/{id}/speakers` | Speaker profiles and voices |
| GET | `/api/jobs/{id}/segments` | Segments (paged) |
| PATCH | `/api/jobs/{id}/segments/{sid}` | Edit `tgt_text` or skip. Voice cannot be changed per segment (use `set_voice` per actor). |
| POST | `/api/jobs/{id}/segments/{sid}/regenerate` | Record a regenerate override (next seed), then run from `GENERATING_TTS`; unchanged segments are reused by `seg_hash` |
| GET | `/api/jobs/{id}/artifacts` | Downloadable `Artifact` rows |
| GET | `/api/jobs/{id}/download` | Primary dubbed video |
| GET | `/api/jobs/{id}/download/{artifact_name}` | Download by name, looked up in the `Artifact` table; paths are never accepted |
| GET | `/api/jobs/{id}/report` | Validation report |

Segment edits are applied by a run starting at the earliest affected stage (`retry` with `from_stage`, or automatically by `regenerate`). Mixing, render and validation rerun afterwards.

---

## 14. UI

- Job form: file upload (primary) or URL, consent checkbox, language selectors, "pause after translation" toggle.
- Job list (reachable again after closing the browser).
- Job page: `status`, `current_stage`, progress per stage using the §8.0 names, errors and warnings.
- Cast review screen (job `PAUSED` at `CAST_REVIEW`): per speaker 3 clips, segment count, speech seconds, gender with confidence (editable), similarity-matrix heatmap, proposals; merge, split, rename, ignore, set gender; "Confirm cast" resumes.
- Speakers table: display name, gender with confidence, voice source (`cloned | fallback_bank`), audition score, segment count, reference preview, similar-voice warning; change voice per actor.
- Segment table: source text, translation, `dub_status` and `skip_reason`, `fit_method`, `drift_cos`, `needs_review`, audio preview; edit text, skip, regenerate. In edit mode it serves the `TRANSLATION_REVIEW` pause.
- Player: original vs dubbed (track switch).
- Downloads: video, SRT, report.

---

## 15. Edge cases

Every case maps to at least one test in `tests/edge_cases/`.

| # | Case | Handling | Test |
| --- | --- | --- | --- |
| 1 | Invalid URL | 422 with readable error (§8.1) | `test_input.py::test_ec01_invalid_url` |
| 2 | Unsupported URL | Scheme, extractor and IP-range checks; readable error | `test_input.py::test_ec02_unsupported_url` |
| 3 | Private or unavailable video | yt-dlp error mapped to a readable `Fatal` | `test_input.py::test_ec03_unavailable_video` |
| 4 | Download failure | `Retryable` with backoff, then readable error | `test_input.py::test_ec04_download_failure` |
| 5 | No audio | `Fatal` at `INGESTING` | `test_audio_quality.py::test_ec05_no_audio_stream` |
| 6 | Very quiet audio | Warning; normalized ASR copy | `test_audio_quality.py::test_ec06_quiet_audio` |
| 7 | Mostly music | VAD gating; few segments; background kept | `test_audio_quality.py::test_ec07_mostly_music` |
| 8 | One speaker | Works without forced splits | `test_speakers.py::test_ec08_single_speaker` |
| 9 | Many speakers | Registry scales; bank reuse warning | `test_speakers.py::test_ec09_many_speakers` |
| 10 | Same speaker throughout | One `voice_id` on every segment of the actor | `test_speakers.py::test_ec10_voice_consistent_across_video` |
| 11 | Speaker appears once | `minor` → per-actor bank voice | `test_speakers.py::test_ec11_one_time_speaker` |
| 12 | Similar voices | Similarity warning and merge proposal in cast review | `test_speakers.py::test_ec12_similar_voices_flagged` |
| 13 | Gender uncertain | `unknown` → neutral bank voice if needed; never fails | `test_speakers.py::test_ec13_gender_unknown` |
| 14 | Insufficient clean reference | Best shorter candidate; audition fail → per-actor bank voice | `test_speakers.py::test_ec14_insufficient_reference` |
| 15 | Simultaneous speech | `is_overlap`; separate tracks mixed at timestamps | `test_speakers.py::test_ec15_overlap_mixed_not_serialized` |
| 16 | Background TV or radio voices | `low_confidence` or ignored in cast review → kept original | `test_audio_quality.py::test_ec16_background_tv_voices` |
| 17 | Crowd speech | As 16 | `test_audio_quality.py::test_ec17_crowd_speech` |
| 18 | Whisper hallucination | Filters (§8.5); never dubbed | `test_audio_quality.py::test_ec18_hallucination_filtered` |
| 19 | Incorrect timestamps | Sanity checks, clamping, interpolation (§8.6) | `test_text.py::test_ec19_timestamp_sanity` |
| 20 | Translation much longer | Budgeted prompt and rewrite rounds (§8.14, §9) | `test_text.py::test_ec20_translation_too_long` |
| 21 | TTS longer than slot | §9 rules 2–4 | `test_tts_timing.py::test_ec21_tts_longer_than_slot` |
| 22 | TTS much shorter | §9 rule 5 | `test_tts_timing.py::test_ec22_tts_much_shorter` |
| 23 | Very short utterances | §8.8 rule 3 | `test_text.py::test_ec23_short_utterances_kept` |
| 24 | Empty translation | Retry → per segment → opus-mt → kept original | `test_text.py::test_ec24_empty_translation` |
| 25 | Unsupported characters | Normalized to the TTS character set | `test_text.py::test_ec25_unsupported_characters` |
| 26 | TTS failure | Seed attempts → `KEPT_ORIGINAL` + `needs_review` | `test_tts_timing.py::test_ec26_tts_failure` |
| 27 | Voice cloning fails for one actor | Whole actor uses a bank voice, decided before bulk TTS | `test_tts_timing.py::test_ec27_cloning_fails_actor_fallback` |
| 28 | Separation fails | Background-mode ladder (§10) | `test_mix_render.py::test_ec28_separation_failure_fallback` |
| 29 | Clipping | True-peak target and limiter; H3 | `test_mix_render.py::test_ec29_no_clipping` |
| 30 | Clicks at boundaries | Fades on every clip | `test_mix_render.py::test_ec30_segment_fades` |
| 31 | Long videos | Whole-file diarization; chunked ASR; block mixing; chunked diarization only after failure or out-of-memory | `test_resources.py::test_ec31_long_video_strategy` |
| 32 | Large temporary files | Per-attempt temp dirs, cleanup policy | `test_resources.py::test_ec32_temp_cleanup` |
| 33 | Worker crash | Leases, orphan kill, reclaim | `test_resilience.py::test_ec33_worker_crash_reclaim` |
| 34 | Restart after partial completion | Resume from verified stage and segment checkpoints | `test_resilience.py::test_ec34_resume_partial` |
| 35 | Duplicate submission | Idempotency key returns the existing job | `test_input.py::test_ec35_duplicate_submission` |
| 36 | Browser closed | Jobs run in the worker; `GET /api/jobs` | `test_input.py::test_ec36_job_survives_client_disconnect` |
| 37 | Disk full | Disk guard fails early | `test_resources.py::test_ec37_disk_guard` |
| 38 | Out of memory | `NeedsSmallerConfig` → `OOM_BACKOFF`, incl. SIGKILL mapping | `test_resources.py::test_ec38_oom_backoff_ladder` |
| 39 | Model download failure | `doctor`; readable error | `test_environment.py::test_ec39_model_download_failure` |
| 40 | Missing Hugging Face token | `doctor` lists missing gates; readable error | `test_environment.py::test_ec40_missing_hf_token` |
| 41 | Model version changes | Lock revision or hash mismatch refuses to load | `test_environment.py::test_ec41_lock_hash_mismatch` |
| 42 | FFmpeg unavailable | `doctor` and startup check | `test_environment.py::test_ec42_ffmpeg_missing` |
| 43 | Corrupt intermediate | Manifest check invalidates the stage and downstream | `test_resilience.py::test_ec43_corrupt_artifact_invalidates_downstream` |
| 44 | Invalid or missing audio in output | H1, H2 | `test_mix_render.py::test_ec44_output_audio_validated` |
| 45 | Audio/video duration mismatch | H4 | `test_mix_render.py::test_ec45_av_duration_match` |
| 46 | Songs and lyrics | Singing detected → not dubbed, original kept | `test_content.py::test_ec46_singing_not_dubbed` |
| 47 | Laughs, cries, sighs, screams | Dialogue-stem lay-back outside dubbed spans (§10.2) | `test_content.py::test_ec47_nonverbal_layback_no_leak` |
| 48 | Mixed-language speech | Per-segment language ID; kept original by default | `test_content.py::test_ec48_foreign_language_kept` |
| 49 | Audio start offset | Offset applied (§8.2, §11); H6 | `test_content.py::test_ec49_audio_start_offset_sync` |
| 50 | Multiple audio tracks or 5.1 | Track selection and ITU downmix; recorded; overridable | `test_content.py::test_ec50_track_selection_and_downmix` |
| 51 | Duration over `MAX_VIDEO_MINUTES` | Fails at `INGESTING` before compute | `test_input.py::test_ec51_duration_limit` |

---

## 16. Testing

### 16.1 Levels and markers

- Unit and integration tests run on CPU with mock providers (mocks only in `tests/`).
- Marker `models`: loads real models (run manually). Marker `long`: media ≥ 5 minutes. Default run: `uv run pytest -m "not models and not long"`.
- Real-model smoke tests use the smallest model variants.

### 16.2 Synthetic fixture

`scripts/make_fixture.py` generates it (commit the script, not the output) with FFmpeg `lavfi`:

- Turkish female and male voices that return later, an overlap, silences, very short utterances, one English sentence (edge case 48).
- Synthetic background music made with `lavfi` (no downloaded music).
- Variants: audio start offset (edge case 49); 5.1 with two language-tagged audio tracks (edge case 50).
- Turkish speech comes from a local TTS whose license permits this use (dev-only tooling; check per-voice licenses). English speech from Kokoro (Apache-2.0).
- Real singing and laughter clips (CC0, listed in `docs/footage.md`) are used only by `models` tests; CPU tests mock the audio-event provider.

### 16.3 Required tests (beyond §15)

License gate; lock-hash mismatch; offline enforcement; hallucination filters; language ID; segment building; overlap detection; speaker confidence, outliers and proposals; cast overrides invalidating hashes; `--auto-cast` refused outside test mode; audition selection; conditioning reload on actor switch (interleaved order); drift gate (regeneration, best-of, centroid update, rebuild on resume); bank voice assigned per actor, never per segment; fitting thresholds and terminal policy; batched rewrite rounds; lay-back without leakage; background-mode selection; block mixing equal to whole-file mixing on a short clip; atomic outputs; segment checkpoints; lease reclaim and orphan kill; `kill -9` resume at every stage; out-of-memory ladder; SSRF blocking; duplicate submission; purge; FFmpeg stderr surfaced; artifact download path-traversal attempt; CPU-vs-MPS diarization parity on a golden clip (`models`).

### 16.4 Golden clips

`golden/` holds ≥ 5 rights-cleared multi-speaker Turkish clips (1–5 minutes) plus one long clip (≥ 60 minutes) for Phase 12. Media files are not committed; `golden/manifest.json` (name, sha256, source) is. Sources, licenses and attributions are recorded in `docs/footage.md`.

---

## 17. Phases

One numbering, Phase 0 to 12. Each phase ends runnable, with automated tests, and is committed.

| Phase | Scope | Exit |
| --- | --- | --- |
| 0 | Feasibility, licenses, footage (below) | `docs/spikes.md`, `docs/footage.md`, `models.lock.json`, `MODEL_LICENSES.md`, `NOTICE`, initial `THIRD_PARTY_LICENSES.md`, `config/defaults.yaml`; §19 resolved or moved to `docs/OPEN_QUESTIONS.md` |
| 1 | Skeleton: repo layout, uv workspace, `dubber` package, api (127.0.0.1), worker, SQLite WAL and migrations, data model (§7), stage engine (hashing, Artifact rows, manifest, atomic per-attempt dirs, segment checkpoints), provider protocol with license gate and offline enforcement, local storage, FFmpeg wrapper, `INGESTING`, `EXTRACTING_AUDIO`, pass-through `RENDERING_VIDEO`, `doctor`, CLI | Upload → pass-through MP4 with two audio tracks; edge cases 1–6, 35, 36, 42, 50, 51 tested; 49 tested for offset handling (H6 sync check added in Phase 8) |
| 2 | Audio analysis: `SEPARATING_AUDIO`, `DETECTING_SPEECH`, `TRANSCRIBING`, `ALIGNING_WORDS`, `DIARIZING`, `BUILDING_SEGMENTS` | Segments with speakers and flags on the fixture |
| 3 | Identity: `BUILDING_SPEAKER_PROFILES`, `CAST_REVIEW` (API and `dubber cast` CLI; UI in Phase 10), `EXTRACTING_REFERENCES`, gender, voice-bank assets | Cast review round-trip changes hashes |
| 4 | Translation: `TRANSLATING` (opus-mt baseline, then LLM with context, glossary, keyed JSON, budgets, validation), rewrite provider, `TRANSLATION_REVIEW` | Validated translations on the fixture |
| 5 | Voices and TTS: TTS provider (variant and backend from Phase 0), `AUDITIONING_VOICES`, `REGISTERING_VOICES`, `GENERATING_TTS` with drift gate, per-actor fallback, optional VC lock | Drift gate and voice-consistency tests pass |
| 6 | `FIT_AND_PLACE` (§9), including batched rewrite rounds and overlap placement | Fitting tests on fixture |
| 7 | `MIXING_AUDIO` (§10) | Mix tests incl. lay-back leakage |
| 8 | `RENDERING_VIDEO` and `VALIDATING` (§11, §12), report | Hard checks pass on the fixture |
| 9 | Resilience: leases and heartbeats, orphan kill, `kill -9` resume at every stage, out-of-memory ladder, cancel, disk guard, purge, `retry` with `from_stage` | §15 resilience and resource tests pass |
| 10 | React UI (§14), including the cast review screen | UI drives a full job |
| 11 | Golden clips end to end with human cast review; tune thresholds | §2 criteria 1–6 and 9–10 |
| 12 | Long video: 90-minute run; speed, memory, `kill -9` resume; chunked diarization only if whole-file fails | §2 criteria 7–8 |

**Phase 0 — feasibility, licenses, footage.** Must finish before any provider code; spike scripts live in `scripts/spikes/` and are throwaway.

1. Hardware: detect chip and RAM (`sysctl -n machdep.cpu.brand_string hw.memsize`), macOS version and MPS availability; record them in `docs/spikes.md`. Do not assume a RAM size.
2. Benchmarks (real-time factor and peak memory on 60-second and 5-minute clips): VAD; ASR (mlx-whisper large-v3 vs large-v3-turbo; faster-whisper CPU int8); alignment; diarization CPU vs MPS (with parity check); separation TIGER-DnR vs Bandit v2 vs Demucs on a 5-minute clip; TTS Chatterbox Multilingual V3, Chatterbox English, Turbo/Nano and Qwen3-TTS, each on CPU vs MPS vs hybrid-MLX (`chatterbox-mlx` fork); translation TranslateGemma 4B vs 12B and the rewrite LLM via Ollama.
3. TTS bake-off (Turkish reference, English text): speaker similarity, re-transcription WER, real-time factor, memory, listening tests; voice-consistency metrics (drift over 50 segments per actor, cosine to centroid, variance across seeds); VC lock on vs off; exaggeration band; `cfg_weight` 0 vs default, including its effect on clip duration (hypothesis: 0 lengthens clips); reference length 5–15 s vs 10–30 s.
4. Calibrate thresholds (§19 item 12) on golden clips.
5. Footage: source rights-cleared multi-speaker Turkish footage (CC-BY or the owner's recordings) for `golden/`; record source, license and attribution in `docs/footage.md`. If none can be found, ask the owner. Never use copyrighted TV footage.
6. Licenses: build `models.lock.json`, `MODEL_LICENSES.md`, `NOTICE`, initial `THIRD_PARTY_LICENSES.md`; work through §19.
7. Output: `docs/spikes.md` with every number, the chosen defaults and the projected 90-minute wall-clock against §2 criterion 7; `config/defaults.yaml`.

---

## 18. Environment and guides

### 18.1 Reference machine

Apple Silicon Mac (M1 Pro), native. Chip and RAM are recorded in `docs/spikes.md` by Phase 0. ML workers run natively with uv; Ollama runs on the host; Docker Compose runs api and frontend only. An optional later `linux-nvidia` profile (NVIDIA driver, Container Toolkit, GPU reservations in Compose) is not required for §2.

### 18.2 G1 — Local setup

Install with Homebrew: `ffmpeg` (includes ffprobe; its GPL build is fine for local use because it is not redistributed), `deno` (URL ingest only), `uv` (installs Python 3.11 for providers), Ollama. Create a free Hugging Face account and a read token; accept the conditions of `pyannote/speaker-diarization-community-1` and any other gated model; export `HF_TOKEN`. Run `python -m dubber doctor` until it is green: FFmpeg and required filters, Deno, Ollama reachable, gates accepted, model cache, lock hashes, free disk, RAM, MPS.

### 18.3 G2 — Repo layout

```
apps/api/            FastAPI app (no ML imports)
apps/frontend/       React + Vite + TypeScript
core/dubber/         engine, schemas, storage, ffmpeg wrapper, worker, CLI (no ML imports)
providers/<name>/    own pyproject.toml and uv.lock (asr, alignment, vad, audio_events, separation,
                     diarization, embedding, gender, translation, tts_chatterbox, nc_plugins/...)
config/              defaults.yaml, license_allowlist.yaml, hallucination_blacklist.<lang>.txt,
                     audition_sentences.<lang>.txt
assets/voice_bank/   bank clips with LICENSE and PROVENANCE
scripts/             make_fixture.py, license_report.py, spikes/
tests/               unit/, integration/, edge_cases/, mocks/
golden/              rights-cleared clips (media git-ignored; manifest.json committed)
docs/                SPEC.md, DECISIONS.md, OPEN_QUESTIONS.md, spikes.md, footage.md, archive/
models.lock.json  MODEL_LICENSES.md  NOTICE  THIRD_PARTY_LICENSES.md  CLAUDE.md
```

### 18.4 G3 — Working with Claude Code

Keep `CLAUDE.md` short. One phase per session; plan first and review the plan before code; tests first; commit per phase; start each session by pointing at the relevant sections of this file only. Review each phase's diff in a separate session. Log surprises in `docs/spikes.md`.

### 18.5 G4 — Debugging audio

Keep intermediates while developing. `ffprobe -show_streams -show_format`; `ffmpeg -i x.wav -af ebur128 -f null -` (loudness); `ffmpeg -i x.wav -lavfi showspectrumpic=s=1200x400 out.png` (spectrogram); `ffplay` for listening. Debug on 30–60 s clips; judge fit and mix by ear before long files.

### 18.6 G5 — Memory on Apple Silicon

Unified memory is shared by CPU and GPU. One model process at a time; exit the process rather than relying on cache clearing. Set `PYTORCH_ENABLE_MPS_FALLBACK=1` and record which ops fall back to CPU. Ollama uses `keep_alive=0`. Implement the out-of-memory ladder (Phase 9) before Phase 12.

### 18.7 G6 — Legal and ethical checklist

Process only content you have the right to dub; voice references only with consent; keep the TTS watermark; label outputs as AI-dubbed in metadata and wherever they are published; respect platform terms (prefer uploading files you own over downloading); keep `NOTICE` current for CC-BY models; keep non-commercial plugins disabled; purge jobs you no longer need (biometric data).

### 18.8 G7 — Reading list

pyannote community-1 model card (https://huggingface.co/pyannote/speaker-diarization-community-1); Chatterbox README (https://github.com/resemble-ai/chatterbox); yt-dlp JavaScript runtime announcement (https://github.com/yt-dlp/yt-dlp/issues/15012); open-dubbing reference pipeline (https://github.com/Softcatala/open-dubbing); Bandit cinematic separation (https://github.com/karnwatcharasupat/bandit); opus-mt-tr-en (https://huggingface.co/Helsinki-NLP/opus-mt-tr-en); MADLAD-400 (https://huggingface.co/google/madlad400-3b-mt).

---

## 19. Verify in Phase 0

1. Licenses: Turkish WhisperX alignment model; TIGER-DnR weights; Bandit v2 weights; audio-event tagger; QC embedder; `chatterbox-mlx` fork; Turkish fixture TTS voices; voice-bank sources.
2. Model names and revisions exist as named: Chatterbox Multilingual V3, Chatterbox Turbo and Nano, Qwen3-TTS sizes, TranslateGemma sizes in Ollama.
3. pyannote community-1: whether the pipeline exposes per-speaker embeddings (else add a separate embedding model); MPS works; CPU-vs-MPS parity.
4. mlx-whisper: per-segment `avg_logprob`, `no_speech_prob`, `compression_ratio`, word timestamps and language detection; the faster-whisper equivalents on CPU.
5. WhisperX `align()` works on mlx-whisper transcripts.
6. Chatterbox: memory per backend; maximum useful reference length; maximum input length per call; saving and loading conditioning; whether voice state carries over between calls; cross-lingual quality; effect of `cfg_weight` on duration; VC availability.
7. Perth watermark survives `atempo`, mixing, `loudnorm` and AAC (detector check).
8. TranslateGemma: Hugging Face gating vs Ollama pull (the Gemma terms apply either way); whether it follows context, glossary, keyed-JSON and budget instructions; which size fits in memory. Rewrite LLM with thinking disabled.
9. `transformers` v5 and `pipeline("translation")` for opus-mt.
10. Ollama `keep_alive=0` frees memory before the next model process starts.
11. FFmpeg build: license (GPL or LGPL); filters present (`loudnorm`, `sidechaincompress`, `atempo`, `ebur128`, `alimiter`, `pan`); MP4 stream copy of VP9 and AV1.
12. Thresholds: `speaker_confidence` formula, `OUTLIER_COS`, `OUTLIER_MARGIN`, `MERGE_COS`, `SPLIT_COS`, `AUDITION_MIN_COS`, `DRIFT_MIN_COS`, F0 gender bands, fit thresholds, separation thresholds, reference SNR and quality floors, `LID_MIN_CONF`, singing threshold, hallucination thresholds for Turkish.
13. `ASR_INPUT` and `DIARIZATION_INPUT`: dialogue stem vs original (WER and diarization error on golden clips).
14. Reference denoise: none vs DeepFilterNet.
15. Speed: per-stage real-time factors, projected to a 90-minute video.
