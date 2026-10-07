# Open questions

These are items `docs/SPEC.md` could not settle.

- **Provisional items** are already applied in the spec (see the linked decision). Each needs the owner's confirmation or a Phase 0 result.
- **When an item is resolved:** record the answer in `docs/DECISIONS.md`, update the spec, and delete the item here.

The Phase 0 completion plan (`docs/superpowers/plans/2026-10-07-phase-0-completion.md`) gives a recommendation for each item and names the task that answers it.

## A. Provisional choices — confirm or change

| # | Question | Current choice in SPEC | Decision |
| --- | --- | --- | --- |
| Q-12 | Should translation output be JSON keyed by segment id? | Keyed JSON, with per-segment translation as the fallback | D-51 |

**Conflict on Q-12:** the owner's answer to Q-27 conflicts with D-51. That answer is a provider adapter in which each model gets its own prompt format, and keyed JSON is not forced on TranslateGemma. D-51 stays provisional until Q-27 is recorded (plan Task 2).

## B. Unresolved — needs the owner or Phase 0

| # | Question | Why it is open |
| --- | --- | --- |
| Q-17 | Singing detection (edge case 46): which audio-event tagger, and what if no license-safe tagger works? | AST (`MIT/ast-finetuned-audioset-10-10-0.4593`, reported BSD-3) ran in S1–S3d at 38–62× real time and returns singing probabilities. Proposed: adopt it, and close this item once its model card is checked at lock time. |
| Q-18 | Do "Chatterbox Multilingual V3" and "Chatterbox Nano (110M)" exist under those names? | Desk research says yes (`docs/feasibility.md` §2): V3 was released 2026-06-10 under MIT and includes Turkish; Nano is MIT, gated and English-only. There is also a new Chatterbox Flash. S1 loaded the multilingual model from `ResembleAI/chatterbox` through `chatterbox-tts` 0.1.7, but whether those weights are V3 is unconfirmed. S2 records the revision. |
| Q-19 | Is the ≤ 3× target reachable on the M1 Pro? | Kaggle T4 measured about 1.6× (S1). The Mac is unmeasured. Measurement there is staged (D-66): spike S4a measures Chatterbox TTS first, and the other stages follow. |
| Q-24 | With Demucs as default (D-62), does singing (for example Teneke's street musician) vanish from the separated background? | Demucs puts singing in the dialogue stem. S3b found no singing in the three films (AST maximum 0.03–0.09), so this is still untested. If singing does vanish, songs must be kept from the original (edge case 46). |
| Q-25 | The timing target (§2 criterion 4: ≤ 15% of lines over 1.10×) is not met on rapid drama dialogue (S3d: 32–45%, truncation 9–28%). Should §9 get a "ripple" rule? | Per-line greedy fitting has reached its limits. Proposal: when a line still overflows after rewrites and tempo, the next line may start up to 0.25 s late, one line deep, if it still ends before its own hard limit. **The owner answered yes; to be recorded in Task 2.** |
| Q-26 | Rewrite model: keep Qwen3-4B-Instruct-2507 (Apache-2.0)? | In S3d, round 1 shortens 64–82% of over-long lines but can be telegraphic. **Owner: keep it; benchmark a larger model in S4. To be recorded in Task 2.** |
| Q-27 | SPEC §8.14 assumes the translator takes context and a glossary and returns keyed JSON. TranslateGemma uses a fixed one-line prompt. | **Owner: use a provider adapter and do not force keyed JSON on TranslateGemma; change the spec.** This resolves Q-12 once it is recorded in Task 2. |
| Q-28 | Which QC embedder runs inside the TTS venv? | `chatterbox-tts` pins torch 2.6, but pyannote.audio 4 needs torch ≥ 2.8. **Owner: WeSpeaker through ONNX Runtime. To be recorded in Task 2.** |
| Q-29 | Should the 11 S3–S3d mechanisms go into the spec (plan Task 2)? | **Owner: adopt all 11. To be recorded in Task 2.** |
| Q-30 | Consented Turkish voices for the TTS bake-off (S2) | **Owner: 2–3 consenting Turkish speakers, ≥ 2 min each. To be recorded in Task 2.** |
| Q-31 | Keep TIGER-DnR and Bandit v2 as fallback separators? | **Owner: Demucs only; the ducked original is the fallback. To be recorded in Task 2.** |
| Q-32 | Sources for bank voices (§3.3) and fixture voices (D-59) | **Owner: Kokoro voices for the bank and Chatterbox Turkish for the fixture, both behind the license gate. To be recorded in Task 2.** |
| Q-33 | `chatterbox-tts` 0.1.7 requires `pykakasi==2.3.0` (GPL-3.0-or-later) and `gradio==6.8.0` | **Owner: if S4 shows the tr/en runtime does not need them, exclude them and declare dependencies explicitly. To be recorded in Task 2.** |
| Q-35 | D-61 allows Kaggle only for S1 with synthetic audio, but practice has gone further. | S3–S3d already processed the CC-BY films on Kaggle. D-66, D-67 and Q-30 also plan to use Kaggle for calibration with golden clips and consented voices. Should D-61 be amended to allow rights-cleared footage and consented voices in private Kaggle datasets that are deleted after use? |
| Q-36 | How loud should the dub be when the original is very quiet? | D-68 matches the original's loudness. An original near −50 LUFS would give a dub that can fail hard check H2 (mean volume > −50 dB). Anything below `QUIET_LUFS` (−40) would give a very quiet dub. Option: use the −16 LUFS fallback (or a floor) below `QUIET_LUFS`. |
| Q-37 | HEVC tag in MP4: always write `-tag:v hvc1`? | Task 1 found that FFmpeg writes `hev1` by default, while Apple players are commonly reported to need `hvc1`. SPEC §11 does not say. This matters for the render in Phase 8. |

## C. Environment notes

| # | Note |
| --- | --- |
| Q-34 | `origin/main` on GitHub already contains the S3 spike `review_*.md` files, which hold the Turkish and English lines of the CC-BY films. **Owner: the repository is private; stop committing film review artifacts. To be applied in Task 12.** |
