# Open questions

Items `docs/SPEC.md` could not settle. Each provisional item is already applied in the spec (see the linked decision) and needs the owner's confirmation or a Phase 0 result. When resolved, record the answer in `docs/DECISIONS.md`, update the spec, and delete the item here. The Phase 0 completion plan (`docs/superpowers/plans/2026-10-07-phase-0-completion.md`) gives a recommendation for each item and names the task that answers it.

## A. Provisional choices — confirm or change

| # | Question | Current choice in SPEC | Decision |
| --- | --- | --- | --- |
| Q-01 | Where is `background_mode` chosen? | `MIXING_AUDIO`, with the ducking mask = dubbed spans | D-22 |
| Q-02 | May the TTS worker load a second, small model (the QC embedder) so the drift gate can run per segment? | Yes; the only exception to "one model family per process" | D-26 |
| Q-03 | Is a 10% re-transcription sample in `VALIDATING` enough, instead of a per-segment check during TTS? | Yes, plus a per-segment duration sanity check | D-27 |
| Q-04 | ASR and diarization input: fixed by config from Phase 0 rather than switched per job? | Fixed by config | D-29 |
| Q-05 | When a clip still does not fit and the next speech blocks overflow: truncate with a fade, or keep the original audio? | `FIT_TERMINAL_POLICY=truncate` (flagged `needs_review`) | D-30 |
| Q-06 | True-peak target lowered from −1.5 to −2.0 dBTP to give AAC 1 dB of headroom below the −1.0 dBTP hard check. OK? | −2.0 dBTP | D-34 |
| Q-07 | Voice bank: only synthetic voices or consenting speakers, excluding CC0 / public-domain recordings of people who never agreed to cloning? | Synthetic or consented only | D-40 |
| Q-08 | MP4 codec allowlist `h264, hevc, av1, vp9` (MKV otherwise), to confirm in Phase 0 | As stated | D-41 |
| Q-09 | Does the ≤ 3× speed target exclude time spent `PAUSED` in review? | Excludes it | D-47 |
| Q-10 | Is `tr → en` the only pair that must pass acceptance in this release? | Yes; other pairs best-effort | D-48 |
| Q-11 | End-of-video sync as a hard check with a 45 ms threshold | Hard check H6, 45 ms | D-50 |
| Q-12 | Translation output as JSON keyed by segment id (needs Phase 0 to show TranslateGemma follows it; see Q-27) | Keyed JSON; per-segment fallback | D-51 |
| Q-13 | One background mode per job (no per-region switching) | One per job | D-53 |
| Q-14 | "Regenerate with the next seed (max 3)": 3 regenerations (4 attempts) or 3 attempts in total? | 3 regenerations, 4 attempts | D-57 |
| Q-15 | If no rights-cleared 90-minute Turkish footage exists, may concatenated golden clips be used for the speed and resilience criteria only? | Yes, for §2 criteria 7–8 only | D-60 |

## B. Unresolved — needs the owner or Phase 0

| # | Question | Why it is open |
| --- | --- | --- |
| Q-16 | Loudness target: keep −16 LUFS, or match the original track's measured loudness so switching audio tracks in a player is not jarring? | v2 chose −16 LUFS, but with dual-track output a mismatch is audible. The spec keeps −16 LUFS until this is decided. |
| Q-17 | Singing detection (edge case 46): which audio-event tagger, and what if no license-safe tagger works? | AST (`MIT/ast-finetuned-audioset-10-10-0.4593`, reported BSD-3) ran in S1–S3d at 38–62× real time and returns singing probabilities. Proposed: adopt it, and close this item once its model card is checked at lock time. |
| Q-18 | Do "Chatterbox Multilingual V3" and "Chatterbox Nano (110M)" exist under those names? | Desk research says yes (`docs/feasibility.md` §2): V3 was released 2026-06-10 under MIT and includes Turkish; Nano is MIT, gated and English-only. There is also a new Chatterbox Flash. S1 loaded the multilingual model from `ResembleAI/chatterbox` through `chatterbox-tts` 0.1.7, but whether those weights are V3 is unconfirmed. S2 records the revision. |
| Q-19 | Is the ≤ 3× target reachable on the M1 Pro? | Kaggle T4 measured about 1.6× for 90 min (S1). The Mac is unmeasured; spike S4 answers this. |
| Q-20 | Golden set: footage source and labels | We have 3 CC-BY shorts (`docs/footage.md`), but each has only 31–55 s of speech. The golden set needs ≥ 5 dialogue-dense clips of 1–5 min. It also needs reference transcripts and speaker labels to measure WER and diarization (§19.13). Who produces them? Proposed: the owner corrects the ASR output. |
| Q-23 | Reference machine for §2 (Definition of Done): the Mac (D-04), or Kaggle 2× T4 run headless? | Spike S1 measured Kaggle, whose terms reportedly limit it to personal, non-commercial use, so it fits only while the project stays personal R&D (D-61). The Mac (checked 2026-10-07) is an M1 Pro with 16 GB, 52 GB of free disk and no FFmpeg installed. A Kaggle reference would mean headless runs on Linux with CUDA, and the local UI would need a remote-run path the spec does not have. |
| Q-24 | With Demucs as default (D-62), does singing (for example Teneke's street musician) vanish from the separated background? | Demucs puts singing in the dialogue stem. S3b found no singing in the three films (AST maximum 0.03–0.09), so this is still untested. If singing does vanish, songs must be kept from the original (edge case 46). |
| Q-25 | The timing target (§2 criterion 4: ≤ 15% of lines over 1.10×) is not met on rapid drama dialogue (S3d: 32–45%, truncation 9–28%). Add a "ripple" rule to §9? | Per-line greedy fitting has reached its limits. Proposal: when a line still overflows after rewrites and tempo, the next line may start up to 0.25 s late, if it still ends before its own hard limit. This applies one line deep only. Alternatives: a larger rewrite model (Q-26), or revisiting SC4 after golden clips (Phase 11). |
| Q-26 | Rewrite model: keep Qwen3-4B-Instruct-2507 (Apache-2.0)? | Measured in S3d: round 1 shortens 64–82% of over-long lines, but the results can be telegraphic, and round 2 adds little. A larger model may shorten better; whether it fits in 16 GB is measured in S4. |
| Q-27 | SPEC §8.14 assumes the translator takes context and a glossary and returns keyed JSON. TranslateGemma uses a fixed one-line prompt, and the spikes never tested the §8.14 format with it. | Related to Q-12. If TranslateGemma cannot follow keyed JSON, translation becomes per segment in its native format, and context and glossary handling move to validation or the rewriter. |
| Q-28 | Which QC embedder runs inside the TTS venv? | D-26 loads the QC embedder in the TTS process. But `chatterbox-tts` pins torch 2.6, while pyannote.audio 4 needs torch ≥ 2.8, and the spikes ran WeSpeaker through pyannote.audio 4. Candidates: Chatterbox's own voice encoder, or WeSpeaker through ONNX Runtime. S2 compares them. |
| Q-29 | Adopt the S3–S3d mechanisms into the spec? These are: a cast-review speaker count, flip smoothing, fragment merging, deterministic ASR, a second ASR pass, the blacklist, stricter translation validation, TTS silence trimming, speech-aware lay-back, a coverage soft check, and LLM call rules. | Each worked in a spike but is not in the spec yet. Details and values: plan Task 2. |
| Q-30 | Consented Turkish voices for the TTS bake-off (S2) | S3 used the CC-BY actors, whose license covers the recordings but not cloning. A clean S2 needs 2–3 people who consent, with ≥ 2 min of speech each. |
| Q-31 | Keep TIGER-DnR and Bandit v2 as fallback separators? | Every enabled model needs a lock entry. TIGER-DnR has a non-commercial training-data caveat and is slow. Bandit v2's weights license is unknown. The ducked original (§10) is already the fallback. |
| Q-32 | Sources for bank voices (§3.3) and fixture voices (D-59) | §19.1 requires their licenses in Phase 0. Candidates: Kokoro-82M voices for the bank (Apache-2.0; voice provenance still to check), and Chatterbox in Turkish for the fixture. |
| Q-33 | `chatterbox-tts` 0.1.7 requires `pykakasi==2.3.0` (GPL-3.0-or-later) and `gradio==6.8.0` | §4.4 allows GPL only in dev tooling. If the tr/en path never imports these packages, install without them; if it does import them, the owner decides. S4 checks. |

## C. Environment notes

| # | Note |
| --- | --- |
| Q-34 | `origin/main` on GitHub already contains the S3 spike `review_*.md` files, which hold the Turkish and English lines of the CC-BY films. `docs/footage.md` says outputs stay private. Confirm the repository is private, and stop committing review files. |
