# Spike S1 — model families on Kaggle (2× T4)

Throwaway Phase 0 spike (`docs/feasibility.md` §10). It answers feasibility questions 1 (do the models work together) and 3 (speed and memory), measured on a Kaggle T4 instead of the Mac.

## What it does

All inside one Kaggle session, one model family at a time, each in its own uv venv (Python 3.11):

| Step | Family | Measures |
| --- | --- | --- |
| 1 | Chatterbox Multilingual + Turbo | Load time, real-time factor (Turkish, English, Turkish→English clone with `cfg_weight` 0.5 vs 0), peak GPU memory, duration effect of `cfg_weight=0`, watermark detection after `atempo` and AAC |
| 2 | Test audio | 60 s and 300 s two-speaker Turkish dialogue (synthetic voice + pitch-shifted copy) over synthetic music, with ground truth |
| 3 | Silero VAD | Speed, speech recall |
| 4 | faster-whisper large-v3-turbo and large-v3 | Speed, Turkish WER, English WER of the TTS output (intelligibility), segment fields needed by the hallucination filters, language detection |
| 5 | WhisperX alignment (Turkish) | Speed, which default model, words left without timestamps (digits) |
| 6 | pyannote community-1 | Speed, speakers found, segment speaker accuracy, whether the output exposes speaker embeddings |
| 7 | TIGER-DnR and Demucs htdemucs | Speed, peak memory, SI-SDR of the dialogue and background against ground truth |
| 8 | AST audio tagger | Speed, top labels |
| 9 | opus-mt tr→en, TranslateGemma 4B/12B (Ollama) | Speed (tok/s), chrF against reference translations, memory freed after `keep_alive=0` |

No user data is uploaded: every voice is the TTS model's built-in synthetic voice, and the music is generated. Expected GPU quota use: about 1 hour of the weekly 30.

## One-time setup (you)

1. Kaggle account → Settings: verify your phone number (needed for GPU and internet).
2. Kaggle Settings → API → create a token, and store it as Kaggle's instructions describe (`~/.kaggle/access_token`, `chmod 600`). Never paste it into chat or commit it. The scripts run Kaggle CLI ≥ 1.8 on Python 3.12 via `uvx`; older CLI releases only read the legacy `kaggle.json`.
3. Hugging Face: accept the conditions of `pyannote/speaker-diarization-community-1` and create a read token.
4. After the first push (below), open the notebook `voxshift-s1` on Kaggle → Add-ons → Secrets → add `HF_TOKEN` with the Hugging Face token and attach it to the notebook. Without it, the script stops within a minute, before any heavy work.

## Run

```bash
export KAGGLE_USERNAME=<your-kaggle-username>
scripts/spikes/kaggle_s1/push.sh      # uploads run_s1.py and starts it
scripts/spikes/kaggle_s1/fetch.sh     # later: status + download results into out/
```

Read `out/s1/summary.md` first. Full numbers are in `out/s1/results.json`, per-step logs in `out/s1/logs/`, and listening samples in `out/s1/audio_samples/`.

## Limits

Synthetic speech and music are fine for speed and memory, but say little about quality on real Turkish drama. Quality questions (4–7) need spikes S2 and S3 with consented voices and rights-cleared footage.
