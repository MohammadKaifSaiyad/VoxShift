# Spike S3b results

Started 2026-10-06 10:38:42; finished 2026-10-06 13:30:22

| Stage | OK | Wall s | Peak GPU MB | Error |
| --- | --- | --- | --- | --- |
| sep | True | 87.8 | 869 |  |
| tag | True | 113.2 | 1605 |  |
| asr | True | 60.5 | 5111 |  |
| diar | True | 143.8 | 2853 |  |
| build | True | 0.4 | 0 |  |
| refs | True | 0.6 | 0 |  |
| audition | True | 171.7 | 4077 |  |
| translate | True | 5643.8 |  |  |
| opus | True | 21.1 | 403 |  |
| tts | True | 242.9 | 3945 |  |
| rewrite_1 | True | 3470.5 |  |  |
| qc | True | 17.2 | 3157 |  |
| mix | True | 142.6 | 0 |  |
| check | True | 43.6 | 5143 |  |

## S3 → S3b

| Clip | Speakers auto → fixed (S3) | > 1.10× S3 → S3b | Truncated S3 → S3b | Overflow S3b | Kept original |
| --- | --- | --- | --- | --- | --- |
| QJH3CCrjda4 | 7 → 3 (7) | 64% → 67% | 21% → 22% | 33% | 0 |
| aLvkEaaDte8 | 4 → 2 (4) | 93% → 54% | 47% → 17% | 29% | 2 |
| cQ8J2vdB9VU | 5 → 2 (6) | 89% → 50% | 43% → 19% | 15% | 3 |

## Per clip

### QJH3CCrjda4
- sep `QJH3CCrjda4`: {"audio_s": 438.39, "run_s": 20.35, "x_realtime": 21.54, "rtf": 0.046}
- tag `QJH3CCrjda4`: {"audio_s": 438.39, "run_s": 27.38, "x_realtime": 16.01, "rtf": 0.062, "windows": 291, "singing_windows": 0, "max_singing": 0.093, "music_windows": 2}
- asr `QJH3CCrjda4`: {"audio_s": 438.39, "run_s": 9.44, "x_realtime": 46.45, "rtf": 0.022, "segments": 8, "words": 44}
- diar `QJH3CCrjda4_auto`: {"audio_s": 438.39, "run_s": 18.3, "x_realtime": 23.96, "rtf": 0.042, "speakers": 7, "speech_s_per_speaker": {"SPEAKER_00": 6.5, "SPEAKER_01": 4.6, "SPEAKER_02": 5.1, "SPEAKER_03": 7.9, "SPEAKER_04": 4.2, "SPEAKER_05": 4.1, "SPEAKER_06": 17.4}}
- diar `QJH3CCrjda4_fixed`: {"audio_s": 438.39, "run_s": 17.67, "x_realtime": 24.81, "rtf": 0.04, "speakers": 3, "speech_s_per_speaker": {"SPEAKER_00": 8.3, "SPEAKER_01": 19.5, "SPEAKER_02": 22.0}}
- build `QJH3CCrjda4`: {"segments": 9, "dubbable": 9, "skipped": {}, "speaker_flips_smoothed": 1, "fragments_merged": 0, "segments_under_1s": 0, "median_segment_s": 2.12, "speech_s_per_speaker": {"SPEAKER_00": 6.6, "SPEAKER_01": 23.4}}
- refs `QJH3CCrjda4`: {"SPEAKER_00": 6.6, "SPEAKER_01": 12.3}
- audition `QJH3CCrjda4`: {"SPEAKER_00": {"source": "cloned", "cps": 14.29}, "SPEAKER_01": {"source": "cloned", "cps": 15.34}}
- translate `QJH3CCrjda4`: {"segments": 9, "chosen": {"translategemma": 9, "qwen3": 0, "opus-mt": 0}}
- opus `QJH3CCrjda4`: {"filled_by_opus_mt": 0}
- tts `QJH3CCrjda4`: {"audio_s": 26.07, "run_s": 34.2, "x_realtime": 0.76, "rtf": 1.312, "segments": 9, "errors": 0, "silence_trimmed_s": 1.13}
- rewrite_1 `QJH3CCrjda4`: {"over_1_10": 6, "rewritten": 0}
- qc `QJH3CCrjda4`: {"SPEAKER_01": {"n": 6, "cos_to_own_centroid_mean": 0.777, "cos_to_own_centroid_p10": 0.69, "below_0_6": 0}, "SPEAKER_00": {"n": 3, "cos_to_own_centroid_mean": 0.824, "cos_to_own_centroid_p10": 0.802, "below_0_6": 0}, "between_speakers": {"SPEAKER_00~SPEAKER_01": 0.344}}
- mix `QJH3CCrjda4`: {"dubbed": 9, "kept_original": 0, "fit": {"none": 3, "tempo_le_1_10": 0, "tempo_gt_1_10": 1, "overflow": 3, "truncated": 2}, "ratio_median": 1.34, "share_over_1_10": 0.667, "share_truncated": 0.222, "share_overflow": 0.333}
- check `QJH3CCrjda4`: {"detected_language": "tr", "language_probability": 0.618, "wer_vs_translation": 1.0}

### aLvkEaaDte8
- sep `aLvkEaaDte8`: {"audio_s": 516.13, "run_s": 23.69, "x_realtime": 21.79, "rtf": 0.046}
- tag `aLvkEaaDte8`: {"audio_s": 516.13, "run_s": 33.52, "x_realtime": 15.4, "rtf": 0.065, "windows": 343, "singing_windows": 0, "max_singing": 0.03, "music_windows": 1}
- asr `aLvkEaaDte8`: {"audio_s": 516.13, "run_s": 6.24, "x_realtime": 82.7, "rtf": 0.012, "segments": 23, "words": 92}
- diar `aLvkEaaDte8_auto`: {"audio_s": 516.13, "run_s": 21.52, "x_realtime": 23.98, "rtf": 0.042, "speakers": 4, "speech_s_per_speaker": {"SPEAKER_00": 20.2, "SPEAKER_01": 7.8, "SPEAKER_02": 25.1, "SPEAKER_03": 30.9}}
- diar `aLvkEaaDte8_fixed`: {"audio_s": 516.13, "run_s": 21.79, "x_realtime": 23.69, "rtf": 0.042, "speakers": 2, "speech_s_per_speaker": {"SPEAKER_00": 20.2, "SPEAKER_01": 63.8}}
- build `aLvkEaaDte8`: {"segments": 26, "dubbable": 26, "skipped": {}, "speaker_flips_smoothed": 1, "fragments_merged": 3, "segments_under_1s": 11, "median_segment_s": 1.24, "speech_s_per_speaker": {"SPEAKER_00": 18.9, "SPEAKER_01": 15.3}}
- refs `aLvkEaaDte8`: {"SPEAKER_00": 9.1, "SPEAKER_01": 8.7}
- audition `aLvkEaaDte8`: {"SPEAKER_00": {"source": "cloned", "cps": 18.0}, "SPEAKER_01": {"source": "cloned", "cps": 9.41}}
- translate `aLvkEaaDte8`: {"segments": 26, "chosen": {"translategemma": 26, "qwen3": 0, "opus-mt": 0}}
- opus `aLvkEaaDte8`: {"filled_by_opus_mt": 0}
- tts `aLvkEaaDte8`: {"audio_s": 45.46, "run_s": 67.75, "x_realtime": 0.67, "rtf": 1.49, "segments": 24, "errors": 2, "silence_trimmed_s": 2.06}
- rewrite_1 `aLvkEaaDte8`: {"over_1_10": 13, "rewritten": 0}
- qc `aLvkEaaDte8`: {"SPEAKER_00": {"n": 12, "cos_to_own_centroid_mean": 0.741, "cos_to_own_centroid_p10": 0.707, "below_0_6": 1}, "SPEAKER_01": {"n": 10, "cos_to_own_centroid_mean": 0.703, "cos_to_own_centroid_p10": 0.645, "below_0_6": 1}, "between_speakers": {"SPEAKER_00~SPEAKER_01": 0.127}}
- mix `aLvkEaaDte8`: {"dubbed": 24, "kept_original": 2, "fit": {"none": 8, "tempo_le_1_10": 3, "tempo_gt_1_10": 2, "overflow": 7, "truncated": 4}, "ratio_median": 1.16, "share_over_1_10": 0.542, "share_truncated": 0.167, "share_overflow": 0.292}
- check `aLvkEaaDte8`: {"detected_language": "en", "language_probability": 0.909, "wer_vs_translation": 0.271}

### cQ8J2vdB9VU
- sep `cQ8J2vdB9VU`: {"audio_s": 504.85, "run_s": 23.33, "x_realtime": 21.64, "rtf": 0.046}
- tag `cQ8J2vdB9VU`: {"audio_s": 504.85, "run_s": 34.06, "x_realtime": 14.82, "rtf": 0.067, "windows": 335, "singing_windows": 0, "max_singing": 0.043, "music_windows": 3}
- asr `cQ8J2vdB9VU`: {"audio_s": 504.85, "run_s": 13.97, "x_realtime": 36.14, "rtf": 0.028, "segments": 32, "words": 146}
- diar `cQ8J2vdB9VU_auto`: {"audio_s": 504.85, "run_s": 20.36, "x_realtime": 24.8, "rtf": 0.04, "speakers": 5, "speech_s_per_speaker": {"SPEAKER_00": 9.7, "SPEAKER_01": 19.4, "SPEAKER_02": 15.0, "SPEAKER_03": 37.7, "SPEAKER_04": 3.6}}
- diar `cQ8J2vdB9VU_fixed`: {"audio_s": 504.85, "run_s": 20.25, "x_realtime": 24.93, "rtf": 0.04, "speakers": 2, "speech_s_per_speaker": {"SPEAKER_00": 40.8, "SPEAKER_01": 44.6}}
- build `cQ8J2vdB9VU`: {"segments": 29, "dubbable": 26, "skipped": {"low_confidence": 3}, "speaker_flips_smoothed": 1, "fragments_merged": 6, "segments_under_1s": 2, "median_segment_s": 1.9, "speech_s_per_speaker": {"SPEAKER_00": 39.3, "SPEAKER_01": 18.7}}
- refs `cQ8J2vdB9VU`: {"SPEAKER_00": 13.3, "SPEAKER_01": 13.1}
- audition `cQ8J2vdB9VU`: {"SPEAKER_00": {"source": "cloned", "cps": 17.48}, "SPEAKER_01": {"source": "cloned", "cps": 19.39}}
- translate `cQ8J2vdB9VU`: {"segments": 26, "chosen": {"translategemma": 26, "qwen3": 0, "opus-mt": 0}}
- opus `cQ8J2vdB9VU`: {"filled_by_opus_mt": 0}
- tts `cQ8J2vdB9VU`: {"audio_s": 72.59, "run_s": 103.94, "x_realtime": 0.7, "rtf": 1.432, "segments": 26, "errors": 0, "silence_trimmed_s": 3.17}
- rewrite_1 `cQ8J2vdB9VU`: {"over_1_10": 13, "rewritten": 0}
- qc `cQ8J2vdB9VU`: {"SPEAKER_01": {"n": 7, "cos_to_own_centroid_mean": 0.777, "cos_to_own_centroid_p10": 0.721, "below_0_6": 0}, "SPEAKER_00": {"n": 19, "cos_to_own_centroid_mean": 0.707, "cos_to_own_centroid_p10": 0.648, "below_0_6": 1}, "between_speakers": {"SPEAKER_00~SPEAKER_01": 0.217}}
- mix `cQ8J2vdB9VU`: {"dubbed": 26, "kept_original": 3, "fit": {"none": 9, "tempo_le_1_10": 4, "tempo_gt_1_10": 4, "overflow": 4, "truncated": 5}, "ratio_median": 1.1, "share_over_1_10": 0.5, "share_truncated": 0.192, "share_overflow": 0.154}
- check `cQ8J2vdB9VU`: {"detected_language": "en", "language_probability": 0.837, "wer_vs_translation": 0.128}

Translators: {"translategemma": {"segments": 61, "within_budget": 0.574, "rejected": {}, "mean_chars_over_budget": 4.6}, "qwen3": {"segments": 61, "within_budget": 0.0, "rejected": {"multiline": 61}, "mean_chars_over_budget": 14632.1}}
Primary translator: translategemma

Listen: audio/<clip>_dub.m4a. Read: review_<clip>.md. Private evaluation only (docs/footage.md).