# Spike S1 results

Started 2026-10-05 17:45:34; GPUs: ['GPU 0: Tesla T4 (UUID: GPU-494a1625-c610-e18f-1add-cebf203f0b10)', 'GPU 1: Tesla T4 (UUID: GPU-a79f779b-0727-e8d3-cca2-847922a126f5)']

| Bench | OK | Wall s | nvidia-smi peak MB | Key numbers | Error |
| --- | --- | --- | --- | --- | --- |
| tts | False | 55.9 | 3219 | {} | TypeError: 'NoneType' object is not callable |
| make_audio | True | 17.6 | 3 | {} |  |
| vad | True | 12.6 | 3 | {"load_s": 0.07, "60s": {"audio_s": 80.13, "run_s": 1.28, "x_realtime": 62.69, "rtf": 0.016, "regions": 15, "speech_recall": 0.95, "detected_speech_s": 67.8, "true_speech_s": 71.1, "device": "cpu"}, "300s": {"audio_s": 395.73, "run_s": 5.72, "x_realtime": 69.13, "rtf": 0.014, "regions": 72, "speech_recall": 0.954, "detected_speech_s": 341.0, "true_speech_s": 355.7, "device": "cpu"}} |  |
| asr | True | 91.0 | 4119 | {} |  |
| align | True | 36.2 | 1589 | {"load_s": 5.6, "speed_on_speech": {"audio_s": 71.15, "run_s": 7.4, "x_realtime": 9.62, "rtf": 0.104}} |  |
| diar | False | 24.1 | 0 | {} | RuntimeError: HF_TOKEN missing (attach the Kaggle secret and accept the model conditions on Hugging Face) |
| tiger | False | 7.4 | 0 | {} | ModuleNotFoundError: No module named 'pkg_resources' |
| demucs | False | 5.2 | 3 | {} | ModuleNotFoundError: No module named 'demucs.pretrained'; 'demucs' is not a package |
| tagger | True | 18.1 | 585 | {"load_s": 3.9} |  |
| opusmt | True | 25.1 | 651 | {"load_s": 8.9, "chrf_vs_reference": 73.3} |  |
| ollama | False |  |  | {} | ollama install failed (see logs/ollama.log) |

## Projection for a 90-minute video (minutes, single T4)

- ASR large-v3-turbo: 2.4
- ASR large-v3: 6.6
- VAD: 1.3
- Alignment (on ~55 min speech): 5.7

Install times and venv sizes: see results.json → install.