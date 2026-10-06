# Open questions

Items `docs/SPEC.md` could not settle. Each provisional item is already applied in the spec (see the linked decision) and needs the owner's confirmation or a Phase 0 result. When resolved, record the answer in `docs/DECISIONS.md`, update the spec, and delete the item here.

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
| Q-12 | Translation output as JSON keyed by segment id (needs Phase 0 to show TranslateGemma follows it) | Keyed JSON; per-segment fallback | D-51 |
| Q-13 | One background mode per job (no per-region switching) | One per job | D-53 |
| Q-14 | "Regenerate with the next seed (max 3)": 3 regenerations (4 attempts) or 3 attempts in total? | 3 regenerations, 4 attempts | D-57 |
| Q-15 | If no rights-cleared 90-minute Turkish footage exists, may concatenated golden clips be used for the speed and resilience criteria only? | Yes, for §2 criteria 7–8 only | D-60 |

## B. Unresolved — needs the owner or Phase 0

| # | Question | Why it is open |
| --- | --- | --- |
| Q-16 | Loudness target: keep −16 LUFS, or match the original track's measured loudness so switching audio tracks in a player is not jarring? | v2 chose −16 LUFS; the dual-track output makes a mismatch audible. The spec keeps −16 LUFS until decided. |
| Q-17 | Singing detection (edge case 46): which audio-event tagger, and what if no license-safe tagger works? | Model choice and license are Phase 0 work; a fallback heuristic may be needed. |
| Q-18 | Do "Chatterbox Multilingual V3" and "Chatterbox Nano (110M)" exist under those names? | Desk research says yes (V3 released 2026-06-10, MIT, includes Turkish; Nano MIT, gated, English), plus a new Chatterbox Flash (`docs/feasibility.md` §2). Close once spike S1 loads them. |
| Q-19 | Is the ≤ 3× target reachable on the M1 Pro? | TTS real-time factor (with drift-gate regenerations and audition) is the dominant unknown until Phase 0 benchmarks. |
| Q-20 | Golden-clip footage source | Phase 0 must find rights-cleared multi-speaker Turkish footage; the owner will be asked if none is found. |
| Q-24 | With Demucs as default (D-62), does singing (for example Teneke's street musician) vanish from the separated background? | Demucs puts singing in the dialogue stem. Check by listening to `aLvkEaaDte8_cfg05_separated` and in spike S3b (singing detection). If it does, songs must be kept from the original (edge case 46). |
| Q-23 | Reference machine for §2 (Definition of Done): the Mac (D-04) or Kaggle 2× T4 run headless? | Spike S1 measures Kaggle; Kaggle's terms reportedly limit it to personal, non-commercial use, so it fits only while the project stays personal R&D (D-61). |

## C. Environment notes

| # | Note |
| --- | --- |
| Q-21 | The project folder is not a git repository, so the archive move used plain `mv`. Working rule 6 (commit per phase) needs `git init` and a first commit before Phase 0. |
| Q-22 | No `CLAUDE.md` existed; a new one was created. |
