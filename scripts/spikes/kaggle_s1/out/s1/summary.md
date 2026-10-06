# Spike S1 results

Started 2026-10-05 17:56:33; GPUs: ['GPU 0: Tesla T4 (UUID: GPU-90ed4278-fdcc-4382-dc87-2da10a3d71be)', 'GPU 1: Tesla T4 (UUID: GPU-a65f392c-2010-9bf3-be14-194554c5761d)']

| Bench | OK | Wall s | nvidia-smi peak MB | Key numbers | Error |
| --- | --- | --- | --- | --- | --- |
| tts | True | 435.2 | 4557 | {"mtl_en_clone_cfg00": {"audio_s": 69.68, "run_s": 84.99, "x_realtime": 0.82, "rtf": 1.22}, "cfg_weight_0_vs_05_duration_ratio": 1.284, "watermark_detect": {"raw": 1.0, "atempo_1.2": 1.0, "aac_128k": 1.0, "atempo_1.2+aac": 1.0}, "turbo_en_clone": {"audio_s": 47.52, "run_s": 23.25, "x_realtime": 2.04, "rtf": 0.489}} |  |
| make_audio | True | 25.5 | 3 | {} |  |
| vad | True | 13.5 | 3 | {"load_s": 0.06, "60s": {"audio_s": 86.04, "run_s": 1.49, "x_realtime": 57.56, "rtf": 0.017, "regions": 13, "speech_recall": 0.709, "detected_speech_s": 54.6, "true_speech_s": 77.1, "device": "cpu"}, "300s": {"audio_s": 426.29, "run_s": 6.79, "x_realtime": 62.76, "rtf": 0.016, "regions": 67, "speech_recall": 0.712, "detected_speech_s": 274.2, "true_speech_s": 385.3, "device": "cpu"}} |  |
| asr | True | 128.0 | 4119 | {"large-v3-turbo": {"load_s": 18.6, "60s": {"audio_s": 86.04, "run_s": 5.35, "x_realtime": 16.09, "rtf": 0.062, "segments": 15, "wer_tr_vs_truth": 0.256}, "segment_fields": {"avg_logprob": true, "no_speech_prob": true, "compression_ratio": true, "words": true}, "300s": {"audio_s": 426.29, "run_s": 11.53, "x_realtime": 36.96, "rtf": 0.027, "segments": 69, "wer_tr_vs_truth": 0.198}, "wer_en_default" |  |
| align | True | 40.2 | 1941 | {"load_s": 5.8, "speed_on_speech": {"audio_s": 77.06, "run_s": 15.61, "x_realtime": 4.94, "rtf": 0.203}} |  |
| diar | False | 24.1 | 0 | {} | RuntimeError: HF_TOKEN missing (attach the Kaggle secret and accept the model conditions on Hugging Face) |
| tiger | True | 445.7 | 2951 | {"load_s": 1.7, "60s": {"audio_s": 86.04, "run_s": 75.07, "x_realtime": 1.15, "rtf": 0.872, "chunked": false, "peak_gpu_mb": 1184.2, "si_sdr_dialogue_db": 16.53, "si_sdr_background_db": -1.64, "si_sdr_mix_vs_dialogue_db": 16.78}, "300s": {"audio_s": 426.29, "run_s": 347.73, "x_realtime": 1.23, "rtf": 0.816, "chunked": false, "peak_gpu_mb": 2042.9, "si_sdr_dialogue_db": 16.45, "si_sdr_background_db |  |
| demucs | True | 37.8 | 869 | {"load_s": 2.8, "60s": {"audio_s": 86.04, "run_s": 6.41, "x_realtime": 13.43, "rtf": 0.074, "peak_gpu_mb": 550.8, "si_sdr_dialogue_db": 16.5, "si_sdr_background_db": -0.87}, "300s": {"audio_s": 426.29, "run_s": 21.35, "x_realtime": 19.96, "rtf": 0.05, "peak_gpu_mb": 550.8, "si_sdr_dialogue_db": 16.5, "si_sdr_background_db": -0.99}} |  |
| tagger | True | 16.9 | 585 | {"load_s": 3.8} |  |
| opusmt | True | 21.5 | 651 | {"load_s": 6.7, "chrf_vs_reference": 73.3} |  |
| ollama | True |  |  | {} |  |

## Projection for a 90-minute video (minutes, single T4)

- ASR large-v3-turbo: 2.4
- ASR large-v3: 7.1
- VAD: 1.4
- Separation TIGER-DnR: 73.2
- Separation Demucs: 4.5
- Alignment (on ~55 min speech): 11.1
- TTS multilingual clone (1 GPU): 87.2
- TTS Turbo (1 GPU): 35.0
- Translation TranslateGemma 4B (~1,200 segments): 9.2

Install times and venv sizes: see results.json → install.