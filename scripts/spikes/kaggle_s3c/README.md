# Spike S3c — S3b with its three failures fixed

Throwaway Phase 0 spike. Same films, models and mechanisms as S3b (`scripts/spikes/kaggle_s3b/README.md`), plus fixes for the S3b findings in `docs/spikes.md`. Private evaluation only (`docs/footage.md`).

| S3b finding | S3c fix |
| --- | --- |
| Qwen3 produced reasoning traces, so all translations were rejected, no rewrites happened and 2.5 h of GPU was lost | `Qwen3-4B-Instruct-2507` (Apache-2.0, no thinking mode; three Ollama tags tried in order). Every candidate must pass a probe (short answer, no reasoning). Output capped at 160 / 100 tokens; reasoning stripped up to `</think>`. A model averaging > 15 s per call is dropped for the rest of the run. |
| Untranscribed Turkish leaked through the −6 dB lay-back (ISLIK dub detected as Turkish) | Silero VAD on the dialogue stem. The stem returns only where VAD hears no speech or the AST tagger hears laughter, crying, screaming or a sigh. Uncovered speech is muted and reported as speech coverage (dubbed + kept + non-verbal ÷ detected speech). |
| ASR not repeatable (ISLIK 44 vs 69 words) | Decoding at temperature 0, plus a second ASR pass on VAD regions (≥ 0.6 s) that pass 1 left < 30% covered by words |

`summary.md` compares S3 → S3b → S3c (timing misses, truncation) and adds speech coverage, muted untranscribed seconds and the English re-transcription check.

## Run

```bash
export KAGGLE_USERNAME=<your-kaggle-username>
scripts/spikes/kaggle_s3c/push.sh    # uploads; its automatic run stops within a minute (no secret)
```

Then on Kaggle:
1. Open `voxshift-s3c` → **Edit**.
2. **Add-ons → Secrets:** tick `HF_TOKEN`.
3. Check **Input** shows `voxshift-s3-clips`.
4. **Save Version → Save & Run All.**
5. **Stop the editor session** (**View Active Events**); only the version run should remain.

Expected run time is about 30–40 minutes of GPU.

```bash
scripts/spikes/kaggle_s3c/fetch.sh   # status + download into out/
```
