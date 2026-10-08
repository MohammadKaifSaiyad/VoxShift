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
| `device --device X --run-dir R` | Run 2 style: checks power, load and lid, runs `bench` under `caffeinate -dimsu`, then reads `pmset -g log` for sleep/wake in the run window |

## Run 2 — clean rerun (D-87)

Run 1 was not clean (battery, load ~10, the Mac slept, MPS memory grew to 13 GB). Run 2 reruns the timing with no new downloads. Everything goes to `out/s4a/run2/` (JSON, logs; audio in `run2/audio/`, git-ignored). Run 1's files are not touched.

```bash
cd ../../..   # repo root
PY=scripts/spikes/mac_s4/.venv/bin/python
$PY scripts/spikes/mac_s4/run_s4a.py device --device cpu --run-dir run2   # then, when it has finished:
$PY scripts/spikes/mac_s4/run_s4a.py device --device mps --run-dir run2
$PY scripts/spikes/mac_s4/run_s4a.py collect --run-dir run2
```

Differences from run 1:

- **Voice:** Chatterbox's built-in default voice (`model.conds`, loaded by `from_pretrained` from the repo's `conds.pt`). `prepare_conditionals` is not called. No film audio and no cloning (D-84). The run stops if `model.conds` is `None`.
- **Blocked modules:** `pykakasi`, `gradio` and `spacy_pkuseg` are set to `None` in `sys.modules` before Chatterbox is imported (D-77, D-88).
- **Memory freed after every generation (not timed):** MPS runs `torch.mps.synchronize()`, `gc.collect()` and `torch.mps.empty_cache()`; CPU runs `gc.collect()`. MPS driver memory is recorded right after each generation and again after the cleanup.
- **Conditions:**
  - The run stops unless `pmset -g batt` reports AC power.
  - It waits (20 s checks, up to 5 min) for a 1-minute load below 4, then runs anyway and records the load.
  - It records the lid state, the top CPU processes and free memory before and after.
  - `bench` runs under `caffeinate -dimsu`. The script checks the caffeinate assertions after 20 s and records the `pmset -g log` Sleep/Wake/DarkWake events for the run window.
- **Unchanged:** text (16 English lines, 3 Turkish sentences), settings, seeds and the warm-up.

The bench options are `--voice default`, `--empty-cache`, `--block-optional` and `--run-dir`. Without them, `bench` behaves as in run 1.

The venv (`.venv/`) and the Hugging Face cache are kept for the owner to decide on.
