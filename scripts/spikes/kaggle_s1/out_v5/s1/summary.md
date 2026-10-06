# Spike S1 results

Started 2026-10-06 06:01:23; GPUs: ['GPU 0: Tesla T4 (UUID: GPU-1e7da925-700e-522a-1f07-bf31d5d5f32a)', 'GPU 1: Tesla T4 (UUID: GPU-f4303515-4f3f-40b1-ec3c-f49aad224ef2)']

| Bench | OK | Wall s | nvidia-smi peak MB | Key numbers | Error |
| --- | --- | --- | --- | --- | --- |
| tts | True | 461.5 | 4557 | {"mtl_en_clone_cfg00": {"audio_s": 69.68, "run_s": 89.99, "x_realtime": 0.77, "rtf": 1.291}, "cfg_weight_0_vs_05_duration_ratio": 1.284, "watermark_detect": {"raw": 1.0, "atempo_1.2": 1.0, "aac_128k": 1.0, "atempo_1.2+aac": 1.0}, "turbo_en_clone": {"audio_s": 47.52, "run_s": 25.38, "x_realtime": 1.87, "rtf": 0.534}} |  |
| make_audio | True | 27.6 | 3 | {} |  |
| diar | True | 52.3 | 2853 | {"load_s": 4.8, "60s": {"audio_s": 86.04, "run_s": 4.59, "x_realtime": 18.74, "rtf": 0.053, "speakers_found": 1, "speakers_true": 2, "labels_distinct": false, "segment_speaker_accuracy": 1.0, "peak_gpu_mb": 1628.8, "output_fields": ["exclusive_speaker_diarization", "serialize", "speaker_diarization", "speaker_embeddings"], "speaker_embeddings_shape": [1, 256], "has_exclusive_diarization": true}, " |  |

## Projection for a 90-minute video (minutes, single T4)

- Diarization: 3.7
- TTS multilingual clone (1 GPU): 92.3
- TTS Turbo (1 GPU): 38.2

Install times and venv sizes: see results.json → install.