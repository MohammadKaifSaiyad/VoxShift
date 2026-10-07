# Spike S4a — Chatterbox Multilingual TTS on the Mac (CPU vs MPS)

Throwaway Phase 0 spike. It measures `chatterbox-tts` 0.1.7 (Multilingual, `ResembleAI/chatterbox`) on the reference Mac (M1 Pro, 16 GB) on CPU and on MPS. It also checks whether `pykakasi` (GPL) and `gradio` are needed for English and Turkish (Q-33). Results go in `docs/spikes.md` (S4a). Private evaluation only (`docs/footage.md`).

- **Inputs:**
  - Reference voice: ISLIK `media/QJH3CCrjda4.m4a`, S3d `SPEAKER_01`, one continuous stretch 165.40–177.20 s (11.8 s, mono 24 kHz, original mix, no separation).
  - Text: the first non-empty `English (final)` lines of `scripts/spikes/kaggle_s3d/out/s3d/review_QJH3CCrjda4.md`. Only 16 exist.
  - Three Turkish weather sentences of our own, for the import check.
- **Settings (as in S3d):** `language_id="en"`, `cfg_weight=0.5`, `exaggeration=0.5`, `torch.manual_seed(1000 + i)`, `prepare_conditionals` once, and one warm-up generation (excluded).
- **No text in outputs:** dialogue text is never printed or saved. Logs and JSON hold indices and character counts only. Audio (`out/s4a/audio/*.wav`) is git-ignored.
- **Guards in every model-loading process:**
  - `spacy_pkuseg` is blocked. Otherwise Chatterbox's tokenizer downloads `spacy_ontonotes.zip` (a Chinese word segmenter) from GitHub on every model load, whatever the language. Chatterbox catches the `ImportError` and only Chinese segmentation is skipped.
  - A socket guard records and refuses network hosts. The `fetch` step allows only `huggingface.co`/`hf.co`. The timed steps allow none and also run with `HF_HUB_OFFLINE=1`.

## Run

```bash
cd scripts/spikes/mac_s4
uv python install 3.11
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python "chatterbox-tts==0.1.7" "setuptools<81" soundfile psutil
.venv/bin/python run_s4a.py all        # ref, importtime, fetch (online, first time only), bench cpu, bench mps, blocked
```

Each step runs in a fresh process under `/usr/bin/time -l` (`out/s4a/logs/<step>.log`).

| Command | What it does |
| --- | --- |
| `ref` | Cuts the reference with ffmpeg and writes `ref.json` |
| `importtime` | Runs `python -X importtime` on the Chatterbox import and checks for `pykakasi`/`gradio` |
| `fetch` | First online `from_pretrained`; records files and revision |
| `bench --device cpu\|mps` | Load, conditioning, warm-up, timed lines, Turkish check, memory, warnings |
| `blocked --device X` | `pykakasi` and `gradio` set to `None` in `sys.modules` before import, then one English and one Turkish generation |
| `collect` | Writes `out/s4a/<run>/results.json` (run 1: `out/s4a/run1/`) |

The venv (`.venv/`) and the Hugging Face cache are kept for the owner to decide on.
