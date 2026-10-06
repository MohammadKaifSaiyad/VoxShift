# Spike S3 — rough end-to-end dub of real Turkish short films (Kaggle 2× T4)

Throwaway Phase 0 spike. Answers feasibility questions 4–7 on real audio: speaker identity, Turkish→English cloning, background preservation, and a full multi-speaker clip.

**Input:** the private Kaggle dataset `voxshift-s3-clips` holds the audio of three CC-BY short films (ISLIK, Teneke, Hediye). Sources and licenses are in `docs/footage.md`. **Private evaluation only:** outputs contain cloned voices of real people, so never publish them, and delete them after evaluation.

## Pipeline (one model family per venv, one process at a time)

1. **Prepare:** decode each film to 48 kHz stereo, 44.1 kHz stereo and 16 kHz mono.
2. **Separate:** Demucs htdemucs on every film; TIGER-DnR on ISLIK too, for an A/B listen.
3. **ASR:** faster-whisper large-v3 with word timestamps, on the dialogue stem and on the original (stem vs original comparison, SPEC §19.13).
4. **Diarize:** pyannote community-1 on the dialogue stem and on the original.
5. **Build segments:**
   - drop segments caught by the hallucination filters;
   - assign each word to the exclusive-diarization speaker;
   - merge or split by the SPEC §8.8 rules;
   - flag overlaps;
   - compute available time per SPEC §9.
6. **Translate:** TranslateGemma 4B via Ollama, one segment at a time.
7. **References:** about 12 s of the cleanest non-overlapped speech per speaker, cut from the dialogue stem.
8. **TTS:** Chatterbox Multilingual, conditioning prepared once per speaker. ISLIK runs with `cfg_weight` 0.5 and 0; the other two with 0.5.
9. **Voice QC:** speaker embeddings measure each speaker's consistency (cosine to its own centroid), similarity to its reference, and how distinct the speakers are from each other.
10. **Fit and mix:**
    - fit with `atempo` ≤ 1.25, else truncate with a fade;
    - match each segment's loudness to the original;
    - build two mixes: **separated** (Demucs background + dub + non-verbal lay-back at −6 dB) and **ducked** (original at −15 dB under the dub);
    - normalize to −16 LUFS and encode AAC.
11. **Check:** re-transcribe the dubbed mix (language detection + WER against the translation).

## Run

```bash
export KAGGLE_USERNAME=<your-kaggle-username>
scripts/spikes/kaggle_s3/push.sh     # uploads; its automatic run stops within a minute (no secret)
```

Then on Kaggle:
1. Open the `voxshift-s3` notebook → **Edit**.
2. **Add-ons → Secrets:** tick `HF_TOKEN`.
3. Check that **Input** shows `voxshift-s3-clips`.
4. **Save Version → Save & Run All.**
5. Stop the interactive editor session (**View Active Events**).

Expected run time is about 60–90 minutes of GPU.

```bash
scripts/spikes/kaggle_s3/fetch.sh    # status + download into out/
```

Read `out/s3/summary.md` and `out/s3/review_<clip>.md`, then listen to `out/s3/audio/`.
