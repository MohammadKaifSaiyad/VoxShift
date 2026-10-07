# Spike S3d — S3c plus the translation split and the short-line rule

Throwaway Phase 0 spike. Same films, models and mechanisms as S3c (`scripts/spikes/kaggle_s3c/README.md`), plus the changes the owner approved after S3c (`docs/spikes.md`, D-65). Private evaluation only (`docs/footage.md`).

| S3c finding | S3d change |
| --- | --- |
| Qwen3-4B fast and budget-compliant but wrong on idioms; TranslateGemma never fairly tested (latency guard counted a model reload) | **Translation split** (SPEC §8.14): TranslateGemma translates every line, and Qwen3 only shortens (rewrite rounds). Qwen3 also translates every line, used only as fallback and shown side by side in `review_<clip>.md`. Each model translates all clips in one block (no reload per clip); the guard measures generation time only. |
| Untranslated / half-Turkish output passed validation | Validation also rejects output that is mostly source words, and lowercase Turkish words left in the English line. Capitalized names and loanwords pass. |
| Whisper phantom lines ("İzlediğiniz için teşekkür ederim", "Altyazı M.K.") | Hallucination blacklist (SPEC §8.5) on both ASR passes; second-pass segments also need `avg_logprob ≥ −0.8` and `no_speech_prob ≤ 0.5` |
| Remaining timing misses are sub-second lines | **D-65 / SPEC §9 rule 5a:** lines under 1 s get an `atempo` cap of 1.5 and up to 0.3 s pre-roll into preceding silence, used only as far as needed |

`summary.md` compares S3 → S3b → S3c → S3d and reports short-line statistics. `review_<clip>.md` adds the Qwen3 alternative and the early start per line.

## Run

```bash
export KAGGLE_USERNAME=<your-kaggle-username>
scripts/spikes/kaggle_s3d/push.sh    # uploads; its automatic run stops within a minute (no secret)
```

Then on Kaggle:
1. Open `voxshift-s3d` → **Edit**.
2. **Add-ons → Secrets:** tick `HF_TOKEN`.
3. Check **Input** shows `voxshift-s3-clips`.
4. **Save Version → Save & Run All.**
5. **Stop the editor session** (**View Active Events**); only the version run should remain.

Expected run time is about 30–40 minutes of GPU.

```bash
scripts/spikes/kaggle_s3d/fetch.sh   # status + download into out/
```
