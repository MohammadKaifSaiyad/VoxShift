# AI Video Dubber: V1 Spec v2 (zero-cost, license-safe)

Prepared 3 October 2026. This replaces the original V1 spec wherever the two differ. Everything not mentioned here (job model, artifact layout, API endpoints, the 45 edge cases, Definition of Done) stays as originally written.

## 0. Rules for Claude Code

1. Save this file as `docs/SPEC.md`. Create a short `CLAUDE.md` that points to it and repeats rules 2 to 8.
2. Work one phase at a time (section 10). Do not start a phase until the previous one has passing automated tests and a runnable app.
3. Write the failing test first, then the code.
4. Never add a dependency or model without an entry in `models.lock.json` and `MODEL_LICENSES.md` (section 2). Never hardcode a model name outside its provider package.
5. Mocks live only under `tests/`. The shipped pipeline always uses real providers.
6. The API/orchestrator process never imports torch or any ML library (section 4.1).
7. Before each commit run `uv run pytest -m "not gpu"`, lint and type-check. Commit at least once per phase.
8. If something in this spec proves wrong or unverifiable, stop and record it in `docs/spikes.md` instead of silently working around it.

## 1. What changed from v1, and why

- **Two v1 defaults were not free for commercial use.** NLLB-200 is CC-BY-NC and labelled a research model. XTTS-v2 is under the Coqui Public Model License (non-commercial) and the company is gone, so no commercial license can be bought. Both are replaced; both remain available only behind `ALLOW_NONCOMMERCIAL_MODELS=true`.
- **Demucs is a music separator.** Film dialogue is better handled by a dialogue/music/effects (cinematic) separator. Demucs becomes the fallback, installed from the maintained fork.
- **The common gender model (audeering) is CC-BY-NC-SA.** Replaced by an F0 heuristic with a confidence score.
- **pyannote community-1** needs a free Hugging Face token, accepted conditions and pyannote.audio 4.x (the `token=` argument replaces `use_auth_token=`).
- **YouTube downloading is fragile.** yt-dlp now needs a JavaScript runtime (Deno) plus `yt-dlp-ejs` and frequent updates. File upload becomes a first-class input; URL download is best-effort.
- **Isolated provider processes**, because torch, pyannote 4, WhisperX and Chatterbox pin conflicting dependency versions and VRAM is only fully released when a process exits.
- **Better timing:** elastic timeline plus length-budgeted translation rewriting, instead of mostly time-stretching.
- **New:** VAD-gated ASR, ASR and diarization on the dialogue stem, per-segment loudness matching, sidechain ducking, speech-mask ducking fallback, dual audio tracks in the MP4, measurable validation (WER, speaker similarity, LUFS), an optional review/edit pause, and a license gate enforced in code.

## 2. Zero-cost policy and license gate

- "Zero cost" means no paid API, paid license or paid SaaS. The only resource spent is compute (your GPU or a free notebook quota).
- **Allowed by default:** MIT, Apache-2.0, BSD-2/3, ISC, MPL-2.0, Unlicense, CC0, CC-BY-4.0 (attribution required). Custom-terms licenses (for example the Gemma Terms of Use) are allowed only if listed in `config/license_allowlist.yaml` with a note.
- **Blocked by default:** anything non-commercial, research-only or NC-share-alike.
- `models.lock.json` holds, per model: `id`, `hf_repo`, `revision` (commit sha), `license_spdx`, `commercial_ok`, `gated`, `attribution`, `sha256` of main weights, `notes` (training-data caveats). A provider refuses to load a model whose revision or hash differs (edge case 41) or whose `commercial_ok` is false while `ALLOW_NONCOMMERCIAL_MODELS=false` (raise `LicenseBlockedError`; unit-test this).
- A script generates `MODEL_LICENSES.md` and `NOTICE` (CC-BY attributions, for example pyannote community-1) from the lock file. Re-read each model card when locking; licenses change.
- **Hugging Face token:** needed only for gated models. Read from an env var or Docker secret, never logged. A first-run check prints which gates are not yet accepted. Gated models can be downloaded once and then used offline.
- If you ever monetize outputs (ads, sales), keep every NC plugin disabled.

## 3. Stack decisions

| Stage | Default (free) | Optional / fallback | Why not the v1 default |
| --- | --- | --- | --- |
| Download | yt-dlp (Unlicense) plus local file upload | none | URL path is best-effort (Deno, yt-dlp-ejs, frequent updates) |
| VAD | Silero VAD (MIT) | pyannote VAD | pyannote VAD may need gated access |
| ASR | faster-whisper (MIT) with Whisper large-v3 or large-v3-turbo; WhisperX alignment | smaller Whisper sizes on CPU | none |
| Separation | Cinematic 3-stem: TIGER-DnR (Apache-2.0 weights per its card; confirm) | Demucs v4 `htdemucs` from `adefossez/demucs` (MIT); Bandit v2 (check weights license) | Original Demucs repo is archived; it targets music, not film dialogue |
| Diarization | `pyannote/speaker-diarization-community-1` (CC-BY-4.0, gated, free) | none | 3.1 is superseded |
| Speaker embeddings | Embeddings returned by the pyannote pipeline (verify API), else SpeechBrain ECAPA or WeSpeaker (Apache-2.0; check training-data terms) | none | none |
| Gender | F0 heuristic (librosa pYIN, ISC; or torchcrepe, MIT) with confidence | audeering wav2vec2 age/gender, only under NC flag | CC-BY-NC-SA |
| Translation | Local LLM via Ollama or llama.cpp (MIT): TranslateGemma 4B/12B (Gemma ToU) for context-aware translation; `Helsinki-NLP/opus-mt-tr-en` (Apache-2.0) as light CPU fallback | MADLAD-400 3B (Apache-2.0) for other language pairs; an Apache-2.0 instruct LLM (for example Qwen3) for the shorten/rewrite step | NLLB-200 is CC-BY-NC |
| TTS | Chatterbox Multilingual V3 (MIT, 23 languages incl. Turkish and English) | Chatterbox-Turbo (350M, English) and Nano (110M, CPU, English); Qwen3-TTS 0.6B/1.7B (Apache-2.0, 10 languages, no Turkish) | XTTS-v2 is CPML non-commercial, vendor defunct |
| Mix/render | FFmpeg and ffprobe | none | Check your build's license (LGPL vs GPL) |

Notes:

- Chatterbox embeds the Perth watermark in all output. Keep it. Do not strip it.
- Chatterbox is tested on Python 3.11; pin 3.11 for provider environments.
- `transformers` v5 removed the `pipeline("translation")` helper. Load `AutoModelForSeq2SeqLM` directly.
- Per-language WhisperX alignment models (wav2vec2) have their own licenses. Audit the Turkish one in Phase 0.
- The TTS default is decided by a bake-off in Phase 0 (section 10), not by this table.

## 4. Architecture

### 4.1 Process-isolated providers

- Orchestrator = FastAPI plus stage engine plus SQLite. Pure Python, no ML imports.
- Each provider family lives in `providers/<name>/` with its own `pyproject.toml` and lockfile (uv), for example `asr`, `diarization`, `separation`, `tts_chatterbox`, `translation_llm`.
- The orchestrator runs a provider as a subprocess with a JSON request on stdin and JSON response on stdout. Files pass by path; heavy tensors never cross the boundary.
- One model family per process; the process exits afterwards, which frees VRAM completely. CUDA OOM is caught in the worker and reported as a typed error so the orchestrator retries with a smaller config (section 4.5).
- Docker: one GPU image containing several venvs under `/opt/venvs/*`, plus `api`, `frontend` and optionally an `ollama` service. Mount the Hugging Face cache and job storage as volumes.
- Also ship a headless CLI (`python -m dubber run --input file.mp4 --src tr --tgt en`) that works without Docker. Kaggle and Colab notebooks cannot run Docker, and the CLI is the fastest dev loop.

### 4.2 Stage engine

- Stages as in the original spec. Each stage declares `inputs`, `outputs`, `version` and `config_keys`.
- **Idempotency:** `input_hash = sha256(input artifact checksums + stage version + relevant config + model lock revisions)`. If a completed `StageRun` has the same hash and verified outputs, skip it.
- **Artifact manifest:** every output is recorded with size and sha256. Verify before reuse; a mismatch means the artifact is corrupt, so invalidate that stage and everything downstream (edge case 43).
- **Crash recovery:** a running stage holds a lease (`worker_id`, `heartbeat_at`). On startup, reclaim stages whose heartbeat is stale and rerun them. Write outputs to a temp dir, then atomic rename.
- **Retry:** per-stage `max_attempts` with exponential backoff. Typed errors: `Retryable`, `NeedsSmallerConfig`, `Fatal`. Store stderr for FFmpeg and subprocess failures.
- **Cancel:** cooperative, checked between segments; the stage subprocess is terminated.
- **Progress** = completed stages weighted by typical cost plus completed segments within the current stage. No timers.
- **Disk guard:** before each stage estimate the temp space needed and fail early with a readable message if free space is below a threshold (edge case 37). Delete intermediates only after a successful render, and only if `KEEP_INTERMEDIATES=false`.
- Use SQLite in WAL mode and a DB-backed queue; no Redis in V1.

### 4.3 Data model (additions to the original)

- `StageRun`: job\_id, stage, attempt, status, input\_hash, started\_at, finished\_at, error\_type, error\_message, metrics JSON.
- `Segment`: id, job\_id, idx, speaker\_id, speaker\_confidence, src\_start, src\_end, src\_text, src\_words JSON, asr\_confidence, no\_speech\_prob, is\_overlap, tgt\_text, tgt\_status, voice\_id, tts\_path, seed, gen\_dur, final\_dur, fit\_method, retries, placement\_start, needs\_review, warnings JSON.
- `SpeakerProfile` as in the original plus `speech_seconds`, `embedding_path`, `reference_segment_ids`, `reference_quality`.
- `Voice`: voice\_id, job\_id, speaker\_id, source (`cloned` | `fallback_bank` | `provider_default`), provider, reference\_path, fallback\_reason. Immutable once created.
- `Job` gains `consent_confirmed` (bool, required), `idempotency_key`, `config_snapshot` JSON, `background_mode`.
- `Metric`: job\_id, stage, name, value (processing time, GPU seconds, peak VRAM, model ids, WER, similarity, LUFS).

### 4.4 Provider interfaces (Protocols)

```python
class VADProvider(Protocol):
    def speech_regions(self, wav: Path) -> list[Region]: ...
class TranscriptionProvider(Protocol):
    def transcribe(self, wav: Path, language: str, cfg: AsrConfig) -> Transcript: ...
class DiarizationProvider(Protocol):
    def diarize(self, wav: Path, cfg: DiarCfg) -> Diarization: ...  # turns, exclusive_turns, per-speaker embeddings
class SeparationProvider(Protocol):
    def separate(self, wav: Path, out: Path) -> SeparationResult: ...  # dialogue, background (music+fx), quality metrics
class GenderProvider(Protocol):
    def classify(self, wav: Path) -> GenderResult: ...  # label, confidence
class TranslationProvider(Protocol):
    def translate(self, groups: list[SegmentGroup], ctx: Context) -> list[Translation]: ...
    def rewrite_shorter(self, item: Translation, max_chars: int) -> Translation: ...
class TTSProvider(Protocol):
    def create_voice_profile(self, reference: Path, meta: VoiceMeta) -> VoiceProfile: ...
    def synthesize(self, text: str, voice: VoiceProfile, language: str, params: TtsParams) -> AudioResult: ...
```

Providers are registered by name from config. All inputs and outputs are Pydantic models with `schema_version`.

### 4.5 Config (pydantic-settings, env-overridable)

`PROVIDER_ASR`, `PROVIDER_TTS`, etc.; model sizes; compute dtype; batch sizes; chunk seconds; `ALLOW_NONCOMMERCIAL_MODELS`; `ALLOW_SINGLE_SPEAKER_FALLBACK`; `MAX_VIDEO_MINUTES`; `OOM_BACKOFF` (ordered list of smaller configs, for example batch 16, 8, 4, 1, then int8, then smaller model, then CPU); loudness target; fit thresholds (section 6).

## 5. Stages in detail (changes and additions)

**5.1 Ingest.** Upload or URL. For URLs: allow http(s) only; resolve DNS and block private, loopback and link-local ranges (SSRF); run yt-dlp as a subprocess with timeout, `--no-playlist`, max duration and size; prefer `avc1`+`mp4a` formats so the video can be stream-copied into MP4. Log the yt-dlp version at startup and warn if it is older than 60 days. Require the consent checkbox (rights to the video and to the voices). Compute the idempotency key from file sha256 or normalized URL plus languages plus config; return the existing job on a duplicate (edge case 35).

**5.2 Extract audio.** `source_audio.wav` (48 kHz float stereo) and a 16 kHz mono copy for models. No audio stream: fail with a readable error. Very quiet audio: warn and use a normalized copy for ASR only.

**5.3 Separate.** Output `dialogue.wav` and `background.wav` (music + effects). Also compute `speech_in_background` (VAD on the background stem) and `dialogue_leak` (dialogue-stem energy where the original is non-speech). Choose and persist `background_mode`: `separated`, `speech_mask_ducked_original` (original mix attenuated 12 to 20 dB under a smoothed speech mask from diarization), or `attenuated_original`. Use the least destructive mode that passes the thresholds. Use the provider's chunked inference for long audio.

**5.4 Transcribe.** Run VAD first (Silero; works without any token). Run Whisper on the dialogue stem (fall back to the original if the stem is clearly worse), with `condition_on_previous_text=False`, fixed source language, word timestamps via alignment. Hallucination filters: flag or drop segments with high `no_speech_prob`, low average log-prob, high compression ratio, repeated n-grams, a configurable blacklist of known silence hallucinations, or under 50% overlap with VAD speech. Flagged segments are never sent to TTS. Persist confidences. `transcription.json` and `aligned.json` carry `schema_version`.

**5.5 Diarize.** pyannote community-1. Use the *exclusive* diarization to assign words to speakers and the regular diarization to detect overlap. Save RTTM, `speakers.json` (turns, per-speaker embeddings, speech seconds). Single-speaker fallback only if `ALLOW_SINGLE_SPEAKER_FALLBACK=true`, recorded as a warning.

**5.6 Build segments.** Assign each word to the speaker with maximum overlap; split at speaker changes; merge same-speaker fragments when the gap is under 0.35 s and no sentence end intervenes; cap at 12 s (split at punctuation or the largest word gap); minimum 0.3 s except true short utterances ("Yes", "What?"), which are kept. `speaker_confidence` = overlap fraction. `is_overlap` = another speaker's regular-diarization turn covers more than 20% of the segment.

**5.7 Speaker profiles.** One global registry per job. If the job was processed in chunks, reconcile labels by agglomerative clustering of embeddings with a cosine threshold calibrated in Phase 0. Merge labels above the merge threshold; between the merge and split thresholds keep them separate and flag "similar voices" (edge case 12). Speakers with under 2 s of speech get `status=minor` and a fallback voice.

**5.8 Reference extraction.** From the dialogue stem. Candidates: not overlapped, `speaker_confidence` of at least 0.9, good ASR confidence, estimated SNR above a threshold, 2 to 12 s long. Trim silence, join the best clips to 10 to 30 s (check the TTS model's useful maximum in Phase 0), resample to the TTS rate, store a `reference_quality` score and the chosen segment ids. If too little clean audio exists, use the best shorter reference; if cloning fails or quality is below threshold, use the fallback voice and persist `fallback_reason`. The reference is Turkish and the output English: for Chatterbox set `cfg_weight=0` to limit accent bleed, as its README advises.

**5.9 Voice registry and gender.** One `Voice` per speaker per job, created once, cached, never re-rolled. Cloning inherits the speaker's gender, so gender matters mainly for fallback selection and the UI. Heuristic: median F0 over clean voiced frames; roughly below 155 Hz male, above 185 Hz female, in between unknown (calibrate in Phase 0); confidence from the margin and the amount of voiced audio; return `unknown` for children, whispering or stylized voices. Fallback bank: 4 to 6 reference clips (2 female, 2 male, 1 to 2 neutral) with redistributable licenses (CC0 or public domain, for example Common Voice CC0 clips or LibriVox recordings), each with a license file.

**5.10 Translate.** Group consecutive segments of one speaker (gap under 1 s) into utterances. Translate with context (previous 3 and next 1 source sentences) and a glossary of names and numbers, then split the result back onto segments at clause boundaries; if the split fails, translate per segment with context. Rules: numbers preserved, names untranslated, `target_text` non-empty (retry once, then fall back to opus-mt, then mark the segment failed, keep the source text and leave the original audio in that region instead of muting). Strip characters the TTS tokenizer cannot handle. Include a character/syllable budget in the prompt, derived from the speaker's measured characters-per-second.

**5.11 TTS.** For every segment: load the cached voice, synthesize with a stored seed, measure duration and loudness, run the quality checks (section 9: speaker similarity and a re-transcription spot check), retry up to 2 times with new seeds, then fall back to the fallback voice, then mark `needs_review`. Cap input length per call at the model's safe limit (verify in Phase 0) by splitting at sentence boundaries.

**5.12 Fit and place.** See section 6.

**5.13 Mix.** Per speaker, build a track at 48 kHz float. Apply 10 to 20 ms fades to every segment (no clicks). Match each segment's loudness to the original dialogue loudness over the same time span, so whispers stay quiet and shouts stay loud. Sum speaker tracks (overlaps are mixed, never serialized). Duck the background under the dialogue with FFmpeg `sidechaincompress`. Master with two-pass `loudnorm` (default -16 LUFS, true peak -1.5 dBTP; configurable) and verify no clipping. Preserve background stereo; keep dialogue near center.

**5.14 Render.** Stream-copy the video. Output audio track 0 = dubbed mix (AAC, default), track 1 = original audio (stream copy, falling back to AAC), optional English SRT as `mov_text`, `-movflags +faststart`. If the source video codec cannot live in MP4 (for example VP9 or AV1 from a webm), remux to MKV and offer MP4 transcoding as an explicit, logged fallback; this is the only permitted video re-encode. Capture FFmpeg stderr on failure.

**5.15 Validate.** See section 9. A job is `COMPLETED` only if all hard checks pass; soft-check failures produce warnings and `needs_review` flags.

## 6. Timing and fitting algorithm

For each segment, compute `available = min(next_speech_start_any_speaker - src_start - 0.12 s, 1.25 * src_dur)`. Never extend over another speaker's speech unless the source segments genuinely overlap. Let `r = gen_dur / available`.

1. `r <= 1.0`: accept. Never slow speech down to fill time; pad with silence. Start at `src_start`.
2. `1.0 < r <= 1.10`: apply `atempo` up to 1.10 (FFmpeg `atempo`, LGPL-safe; do not depend on the GPL rubberband filter). Record `fit_method=tempo`.
3. `1.10 < r <= 1.25`: ask the translator to rewrite shorter with a tighter character budget (max 2 rewrites), regenerate, then apply `atempo` up to 1.25 if still needed.
4. `r > 1.25` after rewrites: allow overflow only into following silence, apply `atempo` up to 1.25 plus a trailing fade, set `needs_review=true`. Never overwrite later dialogue.
5. Very short results (`gen_dur < 0.5 * src_dur`): keep as is, centered on the original segment midpoint if natural, otherwise at `src_start`.

Persist `src_dur`, `gen_dur`, `final_dur`, `fit_method`, `retries`, `placement_start`. All thresholds live in config and are tuned in Phase 6 with real clips. Video is never slowed or sped up in V1.

## 7. Edge cases: handling groups

All 45 original edge cases remain in scope. Each must map to at least one test in `tests/edge_cases/`.

| Group | Cases | Handling |
| --- | --- | --- |
| Input | 1 to 4, 35, 36 | Validate, SSRF guard, readable errors, idempotency key, jobs run server-side so closing the browser is harmless |
| Audio quality | 5, 6, 7, 16, 17, 18 | No-audio fatal; quiet warn; VAD gating and hallucination filters; background and crowd voices flagged low-confidence and not dubbed |
| Speakers | 8 to 15 | One registry, similar-voice flag, minor speakers use fallback voice, overlaps mixed at timestamps |
| Text | 19, 20, 23, 24, 25 | Timestamp sanity checks, length-budgeted rewrite, short-utterance rules, non-empty validation, character normalization |
| TTS and timing | 21, 22, 26, 27 | Section 6; retry then fallback voice then `needs_review` |
| Separation and audio | 28, 29, 30, 44, 45 | `background_mode` fallbacks, loudness and clipping checks, fades, ffprobe checks of streams and durations |
| Scale and resources | 31, 32, 37, 38 | Chunked inference per model, disk guard, temp cleanup, OOM backoff ladder |
| Resilience | 33, 34, 43 | Lease and heartbeat, resume from last verified stage, manifest checksums |
| Models and environment | 39, 40, 41, 42 | Preflight check (`doctor` command): ffmpeg, Deno, HF token and gates, model cache, lock hashes |

## 8. API and UI deltas

- `POST /api/jobs` accepts multipart upload or `source_url`, plus `consent_confirmed=true` (required) and optional `pause_after_translation`.
- Add `POST /api/jobs/{id}/resume` for the review pause, `PATCH /api/jobs/{id}/segments/{sid}` (edit target text, voice), `POST /api/jobs/{id}/segments/{sid}/regenerate`, `GET /api/jobs/{id}/report` (validation metrics) and `GET /api/jobs/{id}/stages`.
- Status via polling every 2 s in V1 (SSE later).
- UI: job form with file or URL, consent checkbox and language selectors; progress by stage; speakers table (gender with confidence, voice source, segment count, reference preview, "similar voices" warning); segment table with source, translation, fit method, `needs_review` flag and per-segment audio preview; edit and regenerate; original vs dubbed player; download buttons for MP4, SRT and the validation report.

## 9. Testing and validation

- Unit and integration tests run on CPU with mock providers (mocks only in `tests/`). GPU tests are marked `gpu` and run manually or in a self-hosted job. Real-model smoke tests use the smallest models.
- Generate the synthetic fixture with a script, not a binary: synthesize two voices with a permissively licensed local TTS (for example Kokoro or Piper), add looped CC0 background music, silences, overlaps and very short utterances, using FFmpeg `lavfi`. Commit the script, not the output.
- Keep a `golden/` folder of 5 short permitted real clips for manual A/B listening and metric tracking.
- Add tests for: license gate, lock-hash mismatch, hallucination filters, segment building, overlap detection, fallback voice selection, fitting thresholds, atomic stage outputs, lease reclaim after simulated crash, OOM backoff ladder, SSRF blocking, duplicate submission, FFmpeg failure surfacing stderr.
- **Hard validation checks** (job fails if any fails): playable MP4 per ffprobe; at least one video and one audio stream; audio not silent (mean volume above -50 dB); no clipping (true peak at or below -1 dBTP); audio and video durations within 0.5 s; every non-skipped segment has audio.
- **Soft checks** (warn and flag): integrated loudness within 1.5 LU of target; WER of a re-transcribed 10% sample against `target_text` at or below 25%; per-segment speaker similarity (embedding cosine between the TTS output and the reference) above a threshold calibrated in Phase 0; per-speaker consistency; share of segments using `atempo` above 1.10 under 15%.
- Record processing time, GPU seconds, peak VRAM and model ids per stage (cost tracking).

## 10. Phases (each ends runnable, with automated tests)

- **Phase 0, feasibility and licenses (1 to 2 days):** benchmark your GPU; build the lock file and `MODEL_LICENSES.md`; run spike scripts per model on a 60 s clip; **TTS bake-off** (Chatterbox Multilingual V3 vs Chatterbox English/Turbo vs Qwen3-TTS) scored on speaker similarity, WER of re-transcription, real-time factor, VRAM and listening tests with a Turkish reference and English text; calibrate speaker-similarity and F0 thresholds; confirm items in section 13. Output: `docs/spikes.md` and chosen defaults.
- **Phase 1, skeleton:** repo layout, uv workspaces, FastAPI, SQLite (WAL), stage engine with idempotency and manifest, storage abstraction, FFmpeg wrapper, ingest (upload and URL), extract audio, passthrough render, `doctor` command, CLI.
- **Phase 2, separation, ASR, diarization:** VAD, separator with quality metrics, transcription with filters, diarization, segment builder.
- **Phase 3, speakers and voices:** registry, reference extraction, F0 gender, voice registry, fallback bank.
- **Phase 4, translation:** opus-mt baseline, then LLM translation with context, glossary, validation and rewrite.
- **Phase 5, TTS:** Chatterbox provider, caching, retries, fallback voice, quality checks.
- **Phase 6, fitting and timeline:** section 6, overlap placement.
- **Phase 7, mixing:** loudness matching, ducking, `loudnorm`, `background_mode` fallbacks.
- **Phase 8, render and validation report.**
- **Phase 9, resilience:** leases, crash recovery, OOM ladder, cancel, disk guard, resume.
- **Phase 10, React UI:** as in section 8.
- **Phase 11:** 5-minute permitted real clip, tune thresholds.
- **Phase 12:** 30 to 60 minute clip. First try whole-file diarization and chunked ASR; add chunked diarization with embedding reconciliation only if memory or time requires it.

## 11. Hardware and free compute

- Preferred: an NVIDIA GPU. Exact VRAM needs come from Phase 0; because models run one at a time in separate processes, peak VRAM equals the largest single model, not the sum.
- CPU-only is possible but slow; Chatterbox-Nano and small Whisper sizes are the CPU-friendly options.
- Free cloud GPUs: Kaggle shows a weekly GPU quota in account settings (commonly about 30 hours) with 12-hour sessions; Colab's free tier gives no guaranteed GPU or quota and disconnects on idle. Use the headless CLI there.
- Disk: budget tens of GB for model caches plus several times the source video size per job.
- Docker GPU access needs the NVIDIA driver and Container Toolkit; request GPUs via `deploy.resources.reservations.devices` in Compose and provide a CPU profile.

## 12. Development guides

**G1. Local setup checklist.** Install `uv`, FFmpeg (with ffprobe), Deno (for yt-dlp on YouTube), NVIDIA driver and Container Toolkit if using Docker. Create a free Hugging Face account, make a read token, accept the conditions on `pyannote/speaker-diarization-community-1` (and any other gated model you choose), export `HF_TOKEN`. Run `python -m dubber doctor` until it is green.

**G2. Repo layout.** `apps/api`, `apps/frontend`, `core/` (stage engine, schemas, storage, ffmpeg), `providers/<name>/` (own pyproject and lock), `config/`, `scripts/` (fixture generator, license report), `tests/`, `docs/SPEC.md`, `docs/spikes.md`, `models.lock.json`, `MODEL_LICENSES.md`, `NOTICE`, `CLAUDE.md`.

**G3. Working with Claude Code.** Keep the spec in the repo and the `CLAUDE.md` short. One phase per session; ask for a plan first and review it before any code; tests first; commit per phase; start each new session by pointing at the relevant sections only. Review each phase's diff in a separate session as an independent check. Ask Claude Code to log surprises into `docs/spikes.md`.

**G4. Debugging audio.** Always keep intermediates while developing. Useful commands: `ffprobe -show_streams -show_format`, `ffmpeg -i x.wav -af ebur128 -f null -` (loudness), `ffmpeg -i x.wav -lavfi showspectrumpic=s=1200x400 out.png` (spectrogram), `ffplay` for quick listening. Debug on 30 to 60 s clips; judge fit and mix by ear before running long files.

**G5. GPU memory habits.** One model family per process. Do not rely on `torch.cuda.empty_cache()`; exit the process. Try `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`. Use fp16 or int8 compute for faster-whisper. Implement the OOM ladder before tackling long videos.

**G6. Legal and ethical checklist.** Process only content you have the right to dub. Use voice references only with consent. Keep the TTS watermark. Label outputs as AI-dubbed in file metadata and in any place you publish them. Respect the source platform's terms (for YouTube, prefer uploading a file you own over scraping). Keep the NOTICE file current for CC-BY models. Keep NC models disabled if you earn money from the output.

**G7. Reading list.** pyannote community-1 model card (https://huggingface.co/pyannote/speaker-diarization-community-1); Chatterbox README (https://github.com/resemble-ai/chatterbox); yt-dlp JS runtime announcement (https://github.com/yt-dlp/yt-dlp/issues/15012); open-dubbing, a small open-source reference pipeline that also supports editing intermediate JSON and rebuilding (https://github.com/Softcatala/open-dubbing); Bandit cinematic separation (https://github.com/karnwatcharasupat/bandit); opus-mt-tr-en (https://huggingface.co/Helsinki-NLP/opus-mt-tr-en); MADLAD-400 (https://huggingface.co/google/madlad400-3b-mt).

## 13. Verify in Phase 0 (not confirmed during planning)

- Exact license of the Turkish WhisperX alignment model, of TIGER-DnR weights, and of Bandit v2 weights.
- Whether the installed pyannote version returns per-speaker embeddings from the pipeline; otherwise add a separate embedding model.
- Chatterbox: VRAM use, maximum useful reference length, maximum input length per call, and quality of Turkish-reference to English output.
- Whether `vad_method=silero` is available in the installed WhisperX version.
- TranslateGemma gating (Hugging Face) vs pulling through Ollama, and which model size fits your GPU next to other stages.
- Whether your FFmpeg build is LGPL or GPL, and whether it includes the filters used (`loudnorm`, `sidechaincompress`, `atempo`).
- Thresholds: speaker-similarity floor, F0 gender bands, merge/split cosine thresholds, fit thresholds.
