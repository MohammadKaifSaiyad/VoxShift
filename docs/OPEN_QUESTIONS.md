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
| Q-19 | Is the ≤ 3× target reachable on the M1 Pro? | Kaggle T4 measured about 1.6× (S1). On the Mac, S4a measured Chatterbox at RTF 6.7 on MPS and 7.2 on CPU. That projects to about 8 h of TTS for a 90-min film, against a 4.5 h budget for the whole pipeline. The run was not clean (battery, busy machine, sleep). See Q-43. |
| Q-43 | Reference machine, revisited per D-66: S4a puts the Mac clearly over 3×. What next? | Options: (1) a clean rerun first, with no downloads; (2) a faster TTS on the Mac, such as Chatterbox Turbo (English-only, 2.5× faster on T4, accent from a Turkish reference untested) or the community `chatterbox-mlx` port (license unchecked); either is a model substitution and needs downloads; (3) run the heavy stages on Kaggle while the app and UI stay local, which is an architecture change, only allowed for personal use (D-81), and affects D-04 and D-56; (4) relax §2 criterion 7 for the Mac (for example, overnight runs), which changes an acceptance criterion. All four are owner decisions. |
| Q-44 | Exclude `spacy-pkuseg` from the TTS environment? | S4a: Chatterbox's tokenizer imports `spacy_pkuseg` on every load, and that package downloads `spacy_ontonotes.zip` from GitHub, outside the lock and the offline rule (§4.2). It is needed only for Chinese. Excluding it is consistent with D-77, but it is a dependency decision. |
| Q-24 | With Demucs as default (D-62), does singing (for example Teneke's street musician) vanish from the separated background? | Demucs puts singing in the dialogue stem. S3b found no singing in the three films (AST maximum 0.03–0.09), so this is still untested. If singing does vanish, songs must be kept from the original (edge case 46). |
| Q-38 | What happens to cast edits made before `set_speaker_count`? (D-73(a)) | Rerunning diarization replaces the speaker labels that earlier merges, renames, ignores and gender edits point to. Options: discard them with a warning in the UI, or allow `set_speaker_count` only before any other edit. |
| Q-39 | Footage acquisition vs YouTube's terms (`docs/platform_terms.md`) | YouTube's ToS forbid downloading except where the service allows it or with written permission, and CC-BY does not change that. The three S3 films were downloaded with yt-dlp; copies are in `media/` and the Kaggle dataset `voxshift-s3-clips`. Decide: re-obtain them through a sanctioned route, ask the creators, or delete. New golden clips come only from sanctioned routes (Wikimedia Commons, Vimeo downloads, creator-provided files)? |
| Q-40 | The film actors' voices | CC BY 4.0 does not license personality rights, so cloning the actors in test footage is not covered by the license. Today's rule is "private evaluation only, never published" (`docs/footage.md`). Confirm that, or require the actors' consent for golden clips. |
| Q-41 | CC footage on Kaggle | Kaggle's terms (§9) take a perpetual license over every upload, but CC licenses do not allow sublicensing content you do not own. Accept the risk for private evaluation, or keep CC footage off Kaggle (process it on the Mac only)? |
| Q-42 | Consent note for voice contributors (S2) | It must cover Kaggle's license, its access to private data, slow deletion (about 2 months, backups up to 6) and cross-border processing (checklist in `docs/platform_terms.md`). The contributors' local law (for example KVKK or GDPR, where voice can be biometric data) is not addressed by Kaggle's terms. Owner to review, possibly with legal advice. |

## C. Environment notes

None open.
