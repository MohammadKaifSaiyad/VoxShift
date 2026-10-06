# Spike S3b — S3 with the spec's timing and identity mechanisms

Throwaway Phase 0 spike. Same three CC-BY films and decided models as S3 (D-62 Demucs, D-63 `cfg_weight` 0.5, D-64 separated mix). It measures how far the spec's mechanisms close the gaps S3 found (`docs/spikes.md`). Private evaluation only (`docs/footage.md`).

| S3 problem | S3b mechanism |
| --- | --- |
| 2–3.5× too many speakers | Diarization with the known speaker count (3 / 2 / 2), standing in for cast review; auto run kept for comparison |
| Speaker flips mid-sentence | Runs under 0.5 s between the same other speaker are relabelled |
| One-word segments | Fragments under 1 s merge into a same-speaker neighbour within 1 s |
| Garbled opening not filtered | Segments with mean word probability < 0.45 keep the original audio |
| Singing with Demucs (Q-24) | AST tagger on the dialogue stem; segments > 50% singing keep the original audio |
| Same default voice for two speakers | Distinct synthetic bank voices (built-in voice plus two pitch/formant-shifted variants); audition measures each voice's characters per second |
| Lines too long | Budget = available time × voice chars/s × 0.95 in the prompt; TranslateGemma 4B vs Qwen3 4B, the better-complying model wins |
| Commentary instead of translation | Validation rejects empty, multi-line, bullet or commentary replies and output > 2× the source; the other model's line, then opus-mt, is used instead |
| Silence padding in TTS | Leading and trailing silence trimmed (−35 dB, 40 ms pad) |
| No rewrite rounds | Up to 2 rounds: segments over 1.10× are shortened by Qwen3 to 90% of the budget, then re-synthesized |
| Naive fitting | SPEC §9: tempo up to 1.25×, overflow into following silence, truncation only as a last resort |
| Final check missing | English re-transcription of each dubbed mix (language + WER) |

## Run

```bash
export KAGGLE_USERNAME=<your-kaggle-username>
scripts/spikes/kaggle_s3b/push.sh    # uploads; its automatic run stops within a minute (no secret)
```

Then on Kaggle:
1. Open `voxshift-s3b` → **Edit**.
2. **Add-ons → Secrets:** tick `HF_TOKEN`.
3. Check **Input** shows `voxshift-s3-clips`.
4. **Save Version → Save & Run All.**
5. Stop the editor session (**View Active Events**).

Expected run time is about 45–75 minutes of GPU.

```bash
scripts/spikes/kaggle_s3b/fetch.sh   # status + download into out/
```

Read `out/s3b/summary.md` (S3 → S3b table) and `out/s3b/review_<clip>.md`, then listen to `out/s3b/audio/<clip>_dub.m4a`.
