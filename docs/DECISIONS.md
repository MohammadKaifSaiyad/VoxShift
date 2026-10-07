# Decision log

Every change to `docs/SPEC.md` gets a numbered entry here. "V1" = `docs/archive/SPEC_V1_original.md`; "v2" = `docs/archive/SPEC_V2.md`. Both are historical; `docs/SPEC.md` (v3) is the only source of truth.

Entries marked **provisional** resolve a conflict that the owner's decisions did not cover; they are also listed in `docs/OPEN_QUESTIONS.md` for confirmation.

## Changelog

| Date | Change |
| --- | --- |
| 2026-10-03 | v3 created: V1 and v2 consolidated into `docs/SPEC.md`; both moved unedited to `docs/archive/` (plain `mv`, because the folder is not yet a git repository). |
| 2026-10-05 | Desk research in `docs/feasibility.md`; D-61 added; spike S1 prepared in `scripts/spikes/kaggle_s1/` (not yet run). No SPEC.md change. |
| 2026-10-06 | S1 and S3 run (`docs/spikes.md`). Owner listening test → D-62 to D-64; SPEC §5 updated (separation default, `cfg_weight`). |
| 2026-10-07 | S3b and S3c run. Owner decision D-65 (short lines); SPEC §9 rule 5a added. |
| 2026-10-07 | S3d run. Phase 0 completion plan written (`docs/superpowers/plans/2026-10-07-phase-0-completion.md`). `docs/OPEN_QUESTIONS.md`: Q-21 and Q-22 closed (the git repository and `CLAUDE.md` exist); Q-25 to Q-34 added. No SPEC.md change. |

## Owner decisions (A–H)

| # | Decision | Reason | Overrides |
| --- | --- | --- | --- |
| D-01 | One self-contained spec; V1 and v2 archived; no "later doc wins" rule | Two overlapping specs with a precedence rule invite the agent to follow superseded instructions | v2 header ("replaces the original wherever the two differ"), v2 §0 rule 1 |
| D-02 | Typical input 60–90 min; `MAX_VIDEO_MINUTES=120`; reject longer inputs before any compute (edge case 51) | Target content is feature-length | V1 "Long-video strategy" (no limit stated); v2 Phase 12 (30–60 min) |
| D-03 | License-safe by default; `ALLOW_NONCOMMERCIAL_MODELS=false`; XTTS-v2, NLLB-200 and audeering only as optional non-commercial plugins | Defaults must permit commercial use | V1 "Recommended technology" (NLLB-200, XTTS-v2 initial) and "Provider interfaces" (NLLBProvider, XTTSProvider first) |
| D-04 | Reference machine: Apple Silicon Mac (M1 Pro), native; RAM detected in Phase 0; ML workers native via uv; Ollama on host; Docker Compose = api + frontend only; optional later `linux-nvidia` profile; memory-dependent defaults set by Phase 0 | Docker on macOS has no GPU access; the owner's machine has no NVIDIA GPU | V1 DoD (`docker compose up` for everything); v2 §4.1 (single GPU image with venvs), §11 (NVIDIA preferred, Kaggle/Colab) |
| D-05 | Definition of Done is measurable and input-agnostic (SPEC §2); upload accepted, URL not required; speed target ≤ 3× (stretch 2×, defect > 5×) provisional until Phase 0 | V1's DoD was not measurable and depended on URL download | V1 "Definition of Done"; v2 §1 (URL best-effort, but DoD unchanged) |
| D-06 | Voice consistency is a top-level section with two layers: identity (whole-file diarization, own `speaker_confidence`, proposals, mandatory `CAST_REVIEW`) and voice (canonical reference by audition, cached conditioning, drift gate) | Central product requirement; diarization alone is not reliable enough over 90 min | V1 "Speaker identity", "Speaker reference extraction", "Voice registry"; v2 §5.7–§5.9, §5.11 |
| D-07 | Fallback voice is per actor and decided before bulk TTS; v2's per-segment fallback voice removed; segment PATCH cannot change voice | A per-segment fallback swaps an actor's voice mid-video | v2 §5.11 ("then fall back to the fallback voice"); v2 §8 (`PATCH` edits "voice") |
| D-08 | Drift gate compares each segment with the running centroid of the actor's accepted TTS outputs, not with the source-language reference | Cross-language similarity is systematically lower and would misfire | v2 §5.11 and §9 soft check (similarity "between the TTS output and the reference") |
| D-09 | Canonical reference 10–15 s by default; Phase 0 compares 5–15 s and 10–30 s | Owner decision B; the owner's Phase 0 list (H) defines the comparison ranges | V1 "Speaker reference extraction" (10–30 s); v2 §5.8 (10–30 s) |
| D-10 | `Job.status` ∈ {QUEUED, RUNNING, PAUSED, COMPLETED, FAILED, CANCELLED}; one canonical 20-stage list for `current_stage` (mapping below); `ALIGNING_AUDIO` renamed `FIT_AND_PLACE` | V1 mixed statuses and stages and had no FAILED/CANCELLED/PAUSED; v2 had 15 stages with no states | V1 "Core architecture", "Job model"; v2 §4.2, §5 |
| D-11 | Job gains `source_type`, nullable `source_url`, `original_filename`, `source_sha256`, `consent_confirmed`, `idempotency_key`, `config_snapshot`, `background_mode`; `output_path` replaced by the `Artifact` table | Uploads and multiple outputs (video, SRT, report) | V1 "Job model"; v2 §4.3 |
| D-12 | The database is the authority for everything editable; files are derived snapshots; edits write DB + override rows that feed `input_hash` | Edits to the DB were invisible to file-checksum hashing, so regenerate could reuse stale audio | V1 "Artifact layout" (`translations.json` as data); v2 §4.2 (hash from artifact checksums only) |
| D-13 | Versioned artifact names (`<name>.<hash12>.<ext>`); never overwrite a file recorded by a completed StageRun; complete layout in SPEC §6.6; `source.<ext>` | Retries and regenerations overwrote recorded files; layout lacked many v2 outputs; `source.mp4` was wrong for other containers | V1 "Artifact layout" |
| D-14 | Separate worker process (`python -m dubber worker`) sharing SQLite (WAL); the API never runs stages | Stages inside the web server run twice under reload or multiple workers | V1 "background worker architecture" (unspecified); v2 §4.1 ("Orchestrator = FastAPI plus stage engine") |
| D-15 | Storage is local filesystem only, behind a thin interface | Providers take local paths and the engine relies on atomic rename | V1 "Storage" (abstraction for later cloud storage) |
| D-16 | API: list, purge (DELETE), retry with `from_stage`, download by artifact name validated against the Artifact table, cast GET/PUT, resume, segment PATCH, regenerate, report, stages; bind 127.0.0.1; no auth, documented | Gaps found in review (no list after browser close, no purge, ambiguous retry/download, path traversal risk) | V1 "API"; v2 §8 |
| D-17 | Logs carry IDs only; never transcript or translation text, never secrets | User content can contain personal data | V1 "Observability" (did not forbid text) |
| D-18 | Long video: whole-file diarization; ASR chunked internally; segment-level checkpoints; block-based mixing (5-min blocks, crossfaded) or memory-mapping; one model process at a time; chunked diarization with reconciliation only as a fallback on failure or out-of-memory (resolution of edge case 31) | A 90-min stereo float32 track is ~2 GB; whole-file diarization gives globally consistent labels | V1 "Long-video strategy" (chunking mandatory); v2 §5.7 and Phase 12 |
| D-19 | Edge cases 46–51 added (songs, non-verbal vocalizations, mixed language, audio start offset, multiple tracks / 5.1, duration limit), each with a handler and a named test | Common in Turkish drama and long films; not covered by 1–45 | V1 edge-case list; v2 §7 |
| D-20 | Apple Silicon stack: mlx-whisper primary, faster-whisper CPU int8 fallback; diarization and alignment on MPS with CPU fallback and a parity test; TTS backend (CPU / MPS / hybrid-MLX) benchmarked; `chatterbox-mlx` a candidate only | CTranslate2 has no Metal backend; pyannote does not certify MPS | v2 §3 (faster-whisper on NVIDIA), §11 |
| D-21 | One phase numbering, 0–12; Phase 0 expanded (hardware, benchmarks, TTS bake-off with consistency metrics, calibration, rights-cleared footage, licenses) and must finish before provider code | Two numberings with different content; Phase 0 too small for the real unknowns | V1 "Development phases"; v2 §10 |

## Conflict resolutions not covered by A–H

| # | Decision | Reason | Overrides | Status |
| --- | --- | --- | --- | --- |
| D-22 | `background_mode` is chosen in `MIXING_AUDIO`; the ducking mask is the dubbed spans | v2 chose it in Separate, using a diarization mask that did not exist yet | v2 §5.3 | provisional |
| D-23 | VAD runs in its own stage `DETECTING_SPEECH` after separation (original + both stems), together with audio-event tagging and separation metrics | v2 needed VAD in Separate (§5.3) but ran it in Transcribe (§5.4); owner decision C1 requires a VAD stage | v2 §5.3, §5.4 | final |
| D-24 | Provider interfaces are batch-shaped; a stage may call several provider processes sequentially; `FIT_AND_PLACE` runs batched rewrite rounds (one translation call + one TTS call per round, max 2) | v2's per-item interfaces plus one process per call meant a model reload per segment, and its per-segment rewrite loop needed two model families at once | v2 §4.4, §6 step 3 | final |
| D-25 | Provider protocol uses `request.json` / `result.json` files plus NDJSON events; stdout/stderr go to a log | Single stdout JSON could not report per-item progress or heartbeats, and library prints corrupt it | v2 §4.1 | final |
| D-26 | The QC embedder is loaded inside the TTS worker, which runs the drift gate per segment | A per-segment gate needs embeddings during generation; this relaxes "one model family per process" for one small auxiliary model | v2 §4.1 | provisional |
| D-27 | Re-transcription check moved from the per-segment TTS loop to a 10% sample in `VALIDATING`; per-segment duration sanity check added instead | Running ASR per segment inside TTS breaks process isolation | v2 §5.11 | provisional |
| D-28 | TTS failure after all seeds → `KEPT_ORIGINAL` (`tts_failed`) + `needs_review` | Follows from D-07 (no per-segment voice fallback) | V1 "Failure handling" (TTS → fallback voice), v2 §5.11 | final |
| D-29 | ASR and diarization input (dialogue stem vs original) fixed by config, chosen in Phase 0 | v2's per-job "fall back if the stem is clearly worse" had no measurable criterion | v2 §5.4 | provisional |
| D-30 | Fitting fixes: `next_speech` excludes overlapping partners; explicit `hard_limit_s`; terminal policy `FIT_TERMINAL_POLICY` (default `truncate`); short clips always at `src_start`; rewrite budget from the voice's target-language `voice_cps` | v2 §6 had no terminal case when the next speech is the binding limit; overlapping segments got near-zero slots; "centered if natural" was untestable; v2 §5.10 budgeted from the source speaker's rate | v2 §5.10, §6 | provisional (terminal policy) |
| D-31 | Threshold timeline: initial values from Phase 0, checked on fixtures in Phase 6, tuned on golden clips in Phase 11 | v2 said both Phase 6 and Phase 11 | v2 §6, §10 | final |
| D-32 | `cfg_weight` is a per-voice value chosen by Phase 0 (0 vs provider default), not fixed at 0 | It may lengthen clips (owner decision H treats this as a hypothesis) | v2 §5.8 | final |
| D-33 | V1's "speaking-rate adjustment" fitting step dropped | The default TTS has no rate control; fitting uses `atempo` and rewrites | V1 "Timing / duration fitting" step 4 | final |
| D-34 | True-peak target −2.0 dBTP (was −1.5); hard check stays ≤ −1.0 dBTP, measured on decoded track 0 only | AAC encoding can overshoot the master by ~0.5 dB, making a 0.5 dB margin flaky; the original track may clip on its own | v2 §5.13, §9 | provisional |
| D-35 | `loudnorm` two-pass with `linear=true`; if it reports dynamic mode, use static gain + true-peak limiter | Dynamic mode would undo per-segment loudness matching | v2 §5.13 | final |
| D-36 | In `separated` mode, kept-original segments and ignored speakers get the dialogue stem back at 0 dB; non-verbal lay-back at −6 dB elsewhere outside dubbed spans | V1/v2 said "leave the original audio" for failed segments, but separated mode discarded the dialogue stem | V1 "Failure handling" (translation), v2 §5.10, §5.13 | final |
| D-37 | Ollama requests use `keep_alive=0`; lock file gains `source` and registry-digest support | Ollama keeps models resident by default; v2's lock schema was Hugging Face-only | v2 §2, §11 | final |
| D-38 | Providers run offline (`HF_HUB_OFFLINE=1`) after preflight and load explicit local paths | Libraries download sub-models themselves, bypassing the license gate | v2 §2 | final |
| D-39 | Package licenses audited separately (`THIRD_PARTY_LICENSES.md`); LGPL allowed for runtime libraries; GPL only in dev tooling; native `aac` only, never `libfdk_aac` | v2 rule 4 put dependencies in the model lock; `libfdk_aac` is not redistributable | v2 §0 rule 4, §2, §3 | final |
| D-40 | Voice bank sources: synthetic voices or recordings of people who consented to cloning; redistributable license | v2's Common Voice / LibriVox clips conflict with its own rule "voice references only with consent" | v2 §5.9, G6 | provisional |
| D-41 | Render writes AI-dubbed metadata and language/title tags; MP4 codec allowlist `h264, hevc, av1, vp9` (MKV otherwise), to confirm in Phase 0 | v2 G6 required labels but §5.14 did not write them; v2's claim that VP9/AV1 cannot be stream-copied into MP4 appears inaccurate | v2 §5.14, G6 | provisional (allowlist) |
| D-42 | Gender values `female | male | unknown`, an F0 estimate used only for bank selection and editable in cast review | Cloning already carries the voice's characteristics; V1 forbids identity by gender | V1 "Speaker identity" (kept); v2 §5.9 | final |
| D-43 | `Voice.source` ∈ {`cloned`, `fallback_bank`} | v2's `provider_default` had no use case | v2 §4.3 | final |
| D-44 | Test markers `models` and `long` replace `gpu`; default run `uv run pytest -m "not models and not long"` | The reference machine has no CUDA GPU | v2 §0 rule 7, §9 | final |
| D-45 | Segment edits and regenerations are overrides applied by a run from the earliest affected stage; regenerate starts at `GENERATING_TTS`; unchanged segments reused via `seg_hash` | Defines how edits reach the final video without a full rerun | v2 §8 | final |
| D-46 | `--auto-cast` accepted only with `DUBBER_TEST_MODE=true`; report records `cast_review_mode` | Owner decision B says tests only; DoD requires human review | — | final |
| D-47 | Speed target excludes time spent `PAUSED` | Human review time is not compute | — | provisional |
| D-48 | Only `tr → en` is acceptance-tested; other pairs configurable, best-effort | V1/v2 default pair only; MADLAD-400 path untested | V1 "Goal", v2 §3 | provisional |
| D-49 | Hallucination thresholds start from Whisper defaults (0.6 / −1.0 / 2.4) with a Turkish blacklist file | v2 named the filters but no values | v2 §5.4 | final |
| D-50 | End-of-video sync is hard check H6 (lag ≤ 45 ms) | Owner decision F49 requires verifying sync at the end | — | provisional (threshold) |
| D-51 | Translation returns JSON keyed by segment id instead of splitting a group translation at clause boundaries; per-segment translation is the fallback | Turkish and English order clauses differently, so splitting back is fragile; Phase 0 checks the model follows the format | v2 §5.10 | provisional |
| D-52 | `tgt_text` (display, digits) and `tts_text` (spoken, numbers as words) are separate; WER compares against `tts_text` with Whisper's English normalizer | "Numbers preserved" is right for subtitles but TTS needs words; avoids "3" vs "three" WER inflation | v2 §5.10, §9 | final |
| D-53 | Background mode is one per job | Per-region modes add complexity; listed as out of scope | V1 "Background audio" (unspecified) | provisional |
| D-54 | Separation metric `dialogue_leak` renamed `background_in_dialogue`; `dialogue_coverage` added | v2's name described the opposite direction of leakage | v2 §5.3 | final |
| D-55 | URL ingest keeps v2's SSRF rules plus an extractor allowlist; the redirect / DNS-rebinding gap is documented as acceptable while the API binds to localhost | Pre-resolution checks alone cannot cover yt-dlp's own requests | v2 §5.1 | final |
| D-56 | Kaggle and Colab are no longer targets; the CLI remains | Reference machine is the owner's Mac | v2 §4.1, §11 | final |
| D-57 | Drift gate allows 3 regenerations after the first attempt (4 attempts in total) | Owner wording "next seed (max 3)" read as 3 regenerations | — | provisional |
| D-58 | Reference denoise default is none; DeepFilterNet only if Phase 0 shows benefit | Denoisers can add artifacts that hurt cloning; the dialogue stem is already cleaned | — | final |
| D-59 | Fixture: Turkish voices from a local TTS whose license permits dev use (GPL tools allowed because nothing ships); English from Kokoro; background music synthesized with `lavfi` | Kokoro has no Turkish; downloaded music makes tests non-hermetic | v2 §9 | final |
| D-60 | A 90-min rights-cleared clip is needed for §2 criteria 7–8; if none exists, concatenated golden clips may be used for speed and resilience only | Long rights-cleared Turkish footage may be hard to find | V1 Phase 12, v2 Phase 12 | provisional |
| D-62 | Separation default is Demucs `htdemucs` (adefossez fork); TIGER-DnR and Bandit v2 are fallbacks | Owner listening test on S3 ("covers the background"); 21× vs 1.3× real time on a T4 (≈ 4.5 vs ≈ 70 min for 90 min) | SPEC §5 (TIGER-DnR was default); SPEC §19 item 1 keeps the Demucs training-data check | final (singing caveat: Q-24) |
| D-63 | `cfg_weight` default 0.5; 0.3 is the per-voice fallback for strong accents; 0 not used | Owner heard no disturbing accent at 0.5. On ISLIK, cfg 0 gave median length ÷ slot 1.64 vs 1.17 and truncations 43% vs 21%, for only +0.04–0.11 similarity to the original voice | D-32 (left `cfg_weight` to Phase 0); v2 §5.8 (mandated 0) | final |
| D-64 | Background mode: the separated mix is confirmed as the first choice; the ducked original stays the automatic fallback | Owner listening test on S3 (ISLIK separated vs ducked) | Confirms D-22 and SPEC §10.1; no SPEC change | final |
| D-65 | Short lines (source < 1.0 s): `atempo` cap 1.5 instead of 1.25, and up to 0.3 s pre-roll into preceding silence; one-word interjections are still dubbed | S3c: the remaining timing misses are mostly 0.3–0.5 s source lines ("bak.", "Oğlum") whose English needs 0.6–1 s, with no silence to overflow into. Owner chose options (a) and (b), not (c) | SPEC §9 (new rule 5a) | final |
| D-61 | Project context is personal R&D (owner, 2026-10-05). Feasibility spike S1 runs on Kaggle 2× T4 (`scripts/spikes/kaggle_s1/`), with synthetic audio only. The default license policy (D-03) is unchanged. | The Mac has 51 GB free disk and borderline speed; Kaggle's terms reportedly allow personal, non-commercial use, which matches this context | D-56 (Kaggle not a target), for spikes only; the §2 reference machine is unchanged pending Q-23 | final |

## Stage mapping (V1 / v2 → v3)

| v3 `current_stage` | V1 | v2 |
| --- | --- | --- |
| *(status `QUEUED`)* | `QUEUED` (in stage list) | — |
| `INGESTING` | `DOWNLOADING` | §5.1 Ingest |
| `EXTRACTING_AUDIO` | `EXTRACTING_AUDIO` | §5.2 Extract audio |
| `SEPARATING_AUDIO` | `SEPARATING_AUDIO` | §5.3 Separate (minus the background-mode choice) |
| `DETECTING_SPEECH` | — | VAD from §5.4 + metrics from §5.3 |
| `TRANSCRIBING` | `TRANSCRIBING` | §5.4 Transcribe |
| `ALIGNING_WORDS` | inside `TRANSCRIBING` | alignment part of §5.4 |
| `DIARIZING` | `DIARIZING` | §5.5 Diarize |
| `BUILDING_SEGMENTS` | inside `DIARIZING` ("join") | §5.6 Build segments |
| `BUILDING_SPEAKER_PROFILES` | `BUILDING_SPEAKER_PROFILES` | §5.7 Speaker profiles + gender from §5.9 |
| `CAST_REVIEW` | — (new) | — (new) |
| `EXTRACTING_REFERENCES` | inside `BUILDING_SPEAKER_PROFILES` | §5.8 Reference extraction |
| `AUDITIONING_VOICES` | — (new) | — (new) |
| `REGISTERING_VOICES` | "Voice registry" section | §5.9 Voice registry |
| `TRANSLATING` | `TRANSLATING` | §5.10 Translate |
| `TRANSLATION_REVIEW` | — | §8 `pause_after_translation` |
| `GENERATING_TTS` | `GENERATING_TTS` | §5.11 TTS |
| `FIT_AND_PLACE` | `ALIGNING_AUDIO` | §5.12 Fit and place |
| `MIXING_AUDIO` | `MIXING_AUDIO` | §5.13 Mix (+ background-mode choice from §5.3) |
| `RENDERING_VIDEO` | `RENDERING_VIDEO` | §5.14 Render |
| `VALIDATING` | `VALIDATING` | §5.15 Validate |
| *(status `COMPLETED`)* | `COMPLETED` (in stage list) | — |

## Phase mapping (V1 → v3; v2 numbering kept)

| V1 phase | v3 phase |
| --- | --- |
| 1 Pipeline with a 30–60 s video | 1 Skeleton (pass-through render) |
| 2 Transcription + diarization | 2 Audio analysis (separation moved here from V1 phase 7) |
| 3 Speaker registry + references | 3 Identity (incl. cast review) |
| 4 Translation | 4 Translation |
| 5 XTTS voice generation | 5 Voices and TTS (Chatterbox; XTTS-v2 only as non-commercial plugin) |
| 6 Timing / fitting | 6 Fit and place |
| 7 Separation / mixing | 7 Mixing (separation is in phase 2) |
| 8 FFmpeg rendering | 8 Render and validation |
| 9 Retries, resumability, validation | 9 Resilience (validation in phase 8) |
| 10 React UI | 10 UI |
| 11 5-min real Turkish drama | 11 Golden clips (rights-cleared only; no TV drama) |
| 12 30–60 min footage | 12 90-minute run |
| — | 0 Feasibility, licenses, footage (from v2, expanded) |
