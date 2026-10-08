# Open questions

These are items `docs/SPEC.md` could not settle.

- **Provisional items** are already applied in the spec (see the linked decision). Each needs the owner's confirmation or a Phase 0 result.
- **When an item is resolved:** record the answer in `docs/DECISIONS.md`, update the spec, and delete the item here.

The Phase 0 completion plan (`docs/superpowers/plans/2026-10-07-phase-0-completion.md`) gives a recommendation for each item and names the task that answers it.

## A. Provisional choices — confirm or change

None open.

## B. Unresolved — needs the owner or Phase 0

| # | Question | Why it is open |
| --- | --- | --- |
| Q-17 | Singing detection (edge case 46): which audio-event tagger, and what if no license-safe tagger works? | AST (`MIT/ast-finetuned-audioset-10-10-0.4593`, reported BSD-3) ran in S1–S3d at 38–62× real time and returns singing probabilities. Proposed: adopt it, and close this item once its model card is checked at lock time. |
| Q-18 | Do "Chatterbox Multilingual V3" and "Chatterbox Nano (110M)" exist under those names? | Desk research says yes (`docs/feasibility.md` §2): V3 was released 2026-06-10 under MIT and includes Turkish; Nano is MIT, gated and English-only. There is also a new Chatterbox Flash. S1 loaded the multilingual model from `ResembleAI/chatterbox` through `chatterbox-tts` 0.1.7, but whether those weights are V3 is unconfirmed. S2 records the revision. |
| Q-19 | Is the ≤ 3× target reachable on the M1 Pro? | Kaggle T4 measured about 1.6× (S1). On the Mac, Chatterbox measured RTF 6.7 on MPS and 7.2 on CPU in S4a run 1, which was not clean. The clean run 2 (D-87, 2026-10-08) measured RTF 5.45 on CPU and 6.47 on MPS. That projects to about 390 min (6.5 h) of TTS alone for a 90-min film, against a 270 min budget for the whole pipeline. See Q-43. |
| Q-43 | Reference machine, revisited per D-66: S4a puts the Mac clearly over 3×. What next? | Decided first step (D-87): a clean S4a rerun on the Mac (AC power, lid open, no other heavy apps, sleep prevented, MPS cache freed per line), with no new downloads. Result (run 2, 2026-10-08): CPU RTF 5.45 is the best, about 390 min of TTS alone, so the Mac remains clearly over 3×. MPS memory is not bounded even when the cache is freed after every line (peak 19.4 GB driver memory, 27.3 GB footprint). Remaining options: (2) a faster TTS on the Mac, such as Chatterbox Turbo (English-only, 2.5× faster on T4, accent from a Turkish reference untested) or the community `chatterbox-mlx` port (license unchecked); either is a model substitution and needs downloads; (3) run the heavy stages on Kaggle while the app and UI stay local, which is an architecture change, only allowed for personal use (D-81) and, for CC film footage, limited by D-85, and affects D-04 and D-56; (4) relax §2 criterion 7 for the Mac (for example, overnight runs), which changes an acceptance criterion. All are owner decisions. Under D-84, the rerun must not clone a film actor; proposed: use Chatterbox's built-in default voice (speed does not depend on the voice). |
| Q-45 | Golden clips under D-84: how are actors dubbed when they have not consented to cloning? | The golden clips are the acceptance set (§2 criteria 1–6, Phase 11, and Phase 12 via D-60). Audition, the drift gate and the WER check assume cloned voices. Options: (a) ask the filmmakers for the actors' consent; (b) dub actors without consent using bank voices, which still tests ASR, speakers, translation, timing and mixing, while cloning quality is tested in S2 with consenting speakers; or both. |
| Q-46 | Clean-up of material made before D-84 and D-85 | The S3–S3d dubs (local git-ignored audio and Kaggle notebook outputs) and the S4a audio contain cloned voices of the films' actors, made without consent. The Kaggle dataset `voxshift-s3-clips` holds the three CC films, which D-85 keeps off Kaggle. Proposed: delete the cloned-voice audio (keep numbers and reports), the Kaggle dataset, and the Kaggle notebook versions holding film audio. Deletion is irreversible, so it needs the owner's OK. |
| Q-47 | Voice contributors' local law (for example Turkey's KVKK or the EU's GDPR, where voice can count as biometric data) | D-86 settles the content of the consent note but not whether a legal review is needed. Kaggle's terms do not address biometric data (`docs/platform_terms.md`, items 6–8). |
| Q-24 | With Demucs as default (D-62), does singing (for example Teneke's street musician) vanish from the separated background? | Demucs puts singing in the dialogue stem. S3b found no singing in the three films (AST maximum 0.03–0.09), so this is still untested. If singing does vanish, songs must be kept from the original (edge case 46). |

## C. Environment notes

None open.
