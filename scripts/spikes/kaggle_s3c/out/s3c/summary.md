# Spike S3c results

Started 2026-10-06 14:20:28; finished 2026-10-06 14:52:57

| Stage | OK | Wall s | Peak GPU MB | Error |
| --- | --- | --- | --- | --- |
| sep | True | 87.5 | 869 |  |
| vad | True | 29.7 | 3 |  |
| tag | True | 123.2 | 1605 |  |
| asr | True | 62.4 | 4119 |  |
| diar | True | 155.7 | 2853 |  |
| build | True | 0.5 | 0 |  |
| refs | True | 0.7 | 0 |  |
| audition | True | 213.1 | 4027 |  |
| translate | True | 233.3 |  |  |
| opus | True | 23.7 | 403 |  |
| tts | True | 299.3 | 3915 |  |
| rewrite_1 | True | 16.2 |  |  |
| tts_round1 | True | 99.5 | 3949 |  |
| rewrite_2 | True | 14.1 |  |  |
| tts_round2 | True | 40.2 | 3931 |  |
| qc | True | 21.9 | 217 |  |
| mix | True | 160.2 | 0 |  |
| check | True | 36.9 | 4119 |  |

## S3 → S3b → S3c

| Clip | Speakers auto → fixed | > 1.10× S3 → S3b → S3c | Truncated S3 → S3b → S3c | Overflow | Speech coverage | Untranscribed muted s | Check (lang, WER) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| QJH3CCrjda4 | 7 → 3 | 64% → 67% → 42% | 21% → 22% → 5% | 37% | 77% | 8.8 | en 0.121 |
| aLvkEaaDte8 | 4 → 2 | 93% → 54% → 54% | 47% → 17% → 21% | 17% | 86% | 3.7 | en 0.426 |
| cQ8J2vdB9VU | 7 → 2 | 89% → 50% → 39% | 43% → 19% → 14% | 22% | 79% | 11.4 | en 0.214 |

## Per clip

### QJH3CCrjda4
- sep `QJH3CCrjda4`: {"audio_s": 438.39, "run_s": 21.21, "x_realtime": 20.66, "rtf": 0.048}
- vad `QJH3CCrjda4`: {"audio_s": 438.39, "run_s": 8.11, "x_realtime": 54.04, "rtf": 0.019, "regions": 21, "speech_s": 37.8}
- tag `QJH3CCrjda4`: {"audio_s": 438.39, "run_s": 29.72, "x_realtime": 14.75, "rtf": 0.068, "windows": 291, "singing_windows": 0, "max_singing": 0.091, "music_windows": 4}
- asr `QJH3CCrjda4`: {"audio_s": 438.39, "run_s": 11.54, "x_realtime": 37.98, "rtf": 0.026, "segments": 19, "words": 82, "vad_regions_missed_by_pass1": 5, "pass2_segments": 4, "pass2_words": 13}
- diar `QJH3CCrjda4_auto`: {"audio_s": 438.39, "run_s": 19.54, "x_realtime": 22.44, "rtf": 0.045, "speakers": 7, "speech_s_per_speaker": {"SPEAKER_00": 6.1, "SPEAKER_01": 4.6, "SPEAKER_02": 5.2, "SPEAKER_03": 8.1, "SPEAKER_04": 4.2, "SPEAKER_05": 4.1, "SPEAKER_06": 16.6}}
- diar `QJH3CCrjda4_fixed`: {"audio_s": 438.39, "run_s": 19.88, "x_realtime": 22.05, "rtf": 0.045, "speakers": 3, "speech_s_per_speaker": {"SPEAKER_00": 8.3, "SPEAKER_01": 19.4, "SPEAKER_02": 21.1}}
- build `QJH3CCrjda4`: {"segments": 19, "dubbable": 19, "skipped": {}, "speaker_flips_smoothed": 1, "fragments_merged": 1, "segments_under_1s": 2, "median_segment_s": 1.52, "speech_s_per_speaker": {"SPEAKER_00": 7.9, "SPEAKER_01": 19.2, "SPEAKER_02": 3.4, "UNKNOWN": 0.9}}
- refs `QJH3CCrjda4`: {"SPEAKER_00": 6.5, "SPEAKER_01": 12.1, "SPEAKER_02": 3.4, "UNKNOWN": 0.0}
- audition `QJH3CCrjda4`: {"SPEAKER_00": {"source": "cloned", "cps": 13.25}, "SPEAKER_01": {"source": "cloned", "cps": 17.32}, "SPEAKER_02": {"source": "cloned", "cps": 10.48}, "UNKNOWN": {"source": "fallback_bank_a", "cps": 19.16}}
- translate `QJH3CCrjda4`: {"segments": 19, "chosen": {"qwen3": 19, "translategemma": 0, "opus-mt": 0}}
- opus `QJH3CCrjda4`: {"filled_by_opus_mt": 0}
- tts `QJH3CCrjda4`: {"audio_s": 45.09, "run_s": 63.99, "x_realtime": 0.7, "rtf": 1.419, "segments": 19, "errors": 0, "silence_trimmed_s": 1.71}
- rewrite_1 `QJH3CCrjda4`: {"over_1_10": 11, "rewritten": 6}
- tts_round1 `QJH3CCrjda4`: {"audio_s": 15.88, "run_s": 21.86, "x_realtime": 0.73, "rtf": 1.376, "segments": 6, "errors": 0, "silence_trimmed_s": 0.4}
- rewrite_2 `QJH3CCrjda4`: {"over_1_10": 8, "rewritten": 0}
- tts_round2 `QJH3CCrjda4`: {"audio_s": 0.0, "run_s": 0.0, "x_realtime": null, "rtf": null, "segments": 0, "errors": 0, "silence_trimmed_s": 0.0}
- qc `QJH3CCrjda4`: {"SPEAKER_02": {"n": 2, "cos_to_own_centroid_mean": 0.9, "cos_to_own_centroid_p10": 0.9, "below_0_6": 0}, "UNKNOWN": {"n": 1, "cos_to_own_centroid_mean": 1.0, "cos_to_own_centroid_p10": 1.0, "below_0_6": 0}, "SPEAKER_01": {"n": 12, "cos_to_own_centroid_mean": 0.715, "cos_to_own_centroid_p10": 0.654, "below_0_6": 0}, "SPEAKER_00": {"n": 4, "cos_to_own_centroid_mean": 0.741, "cos_to_own_centroid_p10": 0.695, "below_0_6": 0}, "between_speakers": {"SPEAKER_00~SPEAKER_01": 0.365, "SPEAKER_00~SPEAKER_
- mix `QJH3CCrjda4`: {"dubbed": 19, "kept_original": 0, "fit": {"none": 10, "tempo_le_1_10": 1, "tempo_gt_1_10": 0, "overflow": 7, "truncated": 1}, "ratio_median": 1.0, "share_over_1_10": 0.421, "share_truncated": 0.053, "share_overflow": 0.368, "speech_s": 37.8, "speech_dubbed_s": 29.0, "speech_kept_original_s": 0.0, "speech_nonverbal_s": 0.0, "speech_untranscribed_muted_s": 8.8, "speech_coverage": 0.768}
- check `QJH3CCrjda4`: {"detected_language": "en", "language_probability": 0.967, "wer_vs_translation": 0.121}

### aLvkEaaDte8
- sep `aLvkEaaDte8`: {"audio_s": 516.13, "run_s": 24.8, "x_realtime": 20.81, "rtf": 0.048}
- vad `aLvkEaaDte8`: {"audio_s": 516.13, "run_s": 8.6, "x_realtime": 59.99, "rtf": 0.017, "regions": 27, "speech_s": 26.6}
- tag `aLvkEaaDte8`: {"audio_s": 516.13, "run_s": 36.71, "x_realtime": 14.06, "rtf": 0.071, "windows": 343, "singing_windows": 0, "max_singing": 0.02, "music_windows": 0}
- asr `aLvkEaaDte8`: {"audio_s": 516.13, "run_s": 7.01, "x_realtime": 73.64, "rtf": 0.014, "segments": 24, "words": 94, "vad_regions_missed_by_pass1": 1, "pass2_segments": 1, "pass2_words": 2}
- diar `aLvkEaaDte8_auto`: {"audio_s": 516.13, "run_s": 24.43, "x_realtime": 21.13, "rtf": 0.047, "speakers": 4, "speech_s_per_speaker": {"SPEAKER_00": 5.6, "SPEAKER_01": 28.5, "SPEAKER_02": 31.1, "SPEAKER_03": 20.2}}
- diar `aLvkEaaDte8_fixed`: {"audio_s": 516.13, "run_s": 23.1, "x_realtime": 22.34, "rtf": 0.045, "speakers": 2, "speech_s_per_speaker": {"SPEAKER_00": 20.2, "SPEAKER_01": 65.1}}
- build `aLvkEaaDte8`: {"segments": 25, "dubbable": 25, "skipped": {}, "speaker_flips_smoothed": 1, "fragments_merged": 5, "segments_under_1s": 9, "median_segment_s": 1.24, "speech_s_per_speaker": {"SPEAKER_00": 18.8, "SPEAKER_01": 18.2}}
- refs `aLvkEaaDte8`: {"SPEAKER_00": 9.0, "SPEAKER_01": 12.0}
- audition `aLvkEaaDte8`: {"SPEAKER_00": {"source": "cloned", "cps": 18.53}, "SPEAKER_01": {"source": "cloned", "cps": 12.85}}
- translate `aLvkEaaDte8`: {"segments": 25, "chosen": {"qwen3": 25, "translategemma": 0, "opus-mt": 0}}
- opus `aLvkEaaDte8`: {"filled_by_opus_mt": 0}
- tts `aLvkEaaDte8`: {"audio_s": 45.75, "run_s": 72.78, "x_realtime": 0.63, "rtf": 1.591, "segments": 24, "errors": 1, "silence_trimmed_s": 2.29}
- rewrite_1 `aLvkEaaDte8`: {"over_1_10": 14, "rewritten": 6}
- tts_round1 `aLvkEaaDte8`: {"audio_s": 9.82, "run_s": 16.09, "x_realtime": 0.61, "rtf": 1.638, "segments": 6, "errors": 0, "silence_trimmed_s": 0.42}
- rewrite_2 `aLvkEaaDte8`: {"over_1_10": 13, "rewritten": 0}
- tts_round2 `aLvkEaaDte8`: {"audio_s": 0.0, "run_s": 0.0, "x_realtime": null, "rtf": null, "segments": 0, "errors": 0, "silence_trimmed_s": 0.0}
- qc `aLvkEaaDte8`: {"SPEAKER_00": {"n": 14, "cos_to_own_centroid_mean": 0.67, "cos_to_own_centroid_p10": 0.545, "below_0_6": 4}, "SPEAKER_01": {"n": 9, "cos_to_own_centroid_mean": 0.692, "cos_to_own_centroid_p10": 0.627, "below_0_6": 1}, "between_speakers": {"SPEAKER_00~SPEAKER_01": 0.115}}
- mix `aLvkEaaDte8`: {"dubbed": 24, "kept_original": 1, "fit": {"none": 9, "tempo_le_1_10": 2, "tempo_gt_1_10": 4, "overflow": 4, "truncated": 5}, "ratio_median": 1.15, "share_over_1_10": 0.542, "share_truncated": 0.208, "share_overflow": 0.167, "speech_s": 26.6, "speech_dubbed_s": 22.5, "speech_kept_original_s": 0.3, "speech_nonverbal_s": 0.0, "speech_untranscribed_muted_s": 3.7, "speech_coverage": 0.859}
- check `aLvkEaaDte8`: {"detected_language": "en", "language_probability": 0.699, "wer_vs_translation": 0.426}

### cQ8J2vdB9VU
- sep `cQ8J2vdB9VU`: {"audio_s": 504.85, "run_s": 24.59, "x_realtime": 20.53, "rtf": 0.049}
- vad `cQ8J2vdB9VU`: {"audio_s": 504.85, "run_s": 8.49, "x_realtime": 59.49, "rtf": 0.017, "regions": 46, "speech_s": 53.9}
- tag `cQ8J2vdB9VU`: {"audio_s": 504.85, "run_s": 38.31, "x_realtime": 13.18, "rtf": 0.076, "windows": 335, "singing_windows": 0, "max_singing": 0.048, "music_windows": 3}
- asr `cQ8J2vdB9VU`: {"audio_s": 504.85, "run_s": 14.62, "x_realtime": 34.53, "rtf": 0.029, "segments": 40, "words": 156, "vad_regions_missed_by_pass1": 9, "pass2_segments": 9, "pass2_words": 14}
- diar `cQ8J2vdB9VU_auto`: {"audio_s": 504.85, "run_s": 22.17, "x_realtime": 22.77, "rtf": 0.044, "speakers": 7, "speech_s_per_speaker": {"SPEAKER_00": 8.6, "SPEAKER_01": 4.8, "SPEAKER_02": 6.9, "SPEAKER_03": 3.7, "SPEAKER_04": 34.6, "SPEAKER_05": 17.0, "SPEAKER_06": 13.6}}
- diar `cQ8J2vdB9VU_fixed`: {"audio_s": 504.85, "run_s": 22.78, "x_realtime": 22.16, "rtf": 0.045, "speakers": 2, "speech_s_per_speaker": {"SPEAKER_00": 50.4, "SPEAKER_01": 38.8}}
- build `cQ8J2vdB9VU`: {"segments": 40, "dubbable": 36, "skipped": {"low_confidence": 4}, "speaker_flips_smoothed": 1, "fragments_merged": 2, "segments_under_1s": 7, "median_segment_s": 1.34, "speech_s_per_speaker": {"SPEAKER_00": 45.9, "SPEAKER_01": 19.3, "UNKNOWN": 1.4}}
- refs `cQ8J2vdB9VU`: {"SPEAKER_00": 12.4, "SPEAKER_01": 13.4, "UNKNOWN": 0.0}
- audition `cQ8J2vdB9VU`: {"SPEAKER_00": {"source": "cloned", "cps": 17.37}, "SPEAKER_01": {"source": "cloned", "cps": 14.83}, "UNKNOWN": {"source": "fallback_bank_a", "cps": 19.16}}
- translate `cQ8J2vdB9VU`: {"segments": 36, "chosen": {"qwen3": 36, "translategemma": 0, "opus-mt": 0}}
- opus `cQ8J2vdB9VU`: {"filled_by_opus_mt": 0}
- tts `cQ8J2vdB9VU`: {"audio_s": 76.21, "run_s": 124.39, "x_realtime": 0.61, "rtf": 1.632, "segments": 36, "errors": 0, "silence_trimmed_s": 5.31}
- rewrite_1 `cQ8J2vdB9VU`: {"over_1_10": 21, "rewritten": 12}
- tts_round1 `cQ8J2vdB9VU`: {"audio_s": 19.91, "run_s": 33.12, "x_realtime": 0.6, "rtf": 1.663, "segments": 12, "errors": 0, "silence_trimmed_s": 1.17}
- rewrite_2 `cQ8J2vdB9VU`: {"over_1_10": 14, "rewritten": 3}
- tts_round2 `cQ8J2vdB9VU`: {"audio_s": 9.48, "run_s": 12.7, "x_realtime": 0.75, "rtf": 1.34, "segments": 3, "errors": 0, "silence_trimmed_s": 0.08}
- qc `cQ8J2vdB9VU`: {"SPEAKER_01": {"n": 10, "cos_to_own_centroid_mean": 0.74, "cos_to_own_centroid_p10": 0.63, "below_0_6": 1}, "UNKNOWN": {"n": 2, "cos_to_own_centroid_mean": 0.934, "cos_to_own_centroid_p10": 0.934, "below_0_6": 0}, "SPEAKER_00": {"n": 22, "cos_to_own_centroid_mean": 0.658, "cos_to_own_centroid_p10": 0.564, "below_0_6": 4}, "between_speakers": {"SPEAKER_00~SPEAKER_01": 0.188, "SPEAKER_00~UNKNOWN": 0.065, "SPEAKER_01~UNKNOWN": 0.289}}
- mix `cQ8J2vdB9VU`: {"dubbed": 36, "kept_original": 4, "fit": {"none": 20, "tempo_le_1_10": 2, "tempo_gt_1_10": 1, "overflow": 8, "truncated": 5}, "ratio_median": 0.92, "share_over_1_10": 0.389, "share_truncated": 0.139, "share_overflow": 0.222, "speech_s": 53.9, "speech_dubbed_s": 38.3, "speech_kept_original_s": 3.4, "speech_nonverbal_s": 0.8, "speech_untranscribed_muted_s": 11.4, "speech_coverage": 0.788}
- check `cQ8J2vdB9VU`: {"detected_language": "en", "language_probability": 0.833, "wer_vs_translation": 0.214}

LLM probes: {"translategemma:4b": {"seconds_incl_load": 91.6, "answer": "Hello, how are you?"}, "qwen3:4b-instruct": {"seconds_incl_load": 3.6, "answer": "Hello, how are you?"}}
Translators: {"translategemma": {"segments": 80, "within_budget": 0.013, "rejected": {"too_slow": 76}, "mean_chars_over_budget": 0.9, "mean_seconds_per_call": 18.52}, "qwen3": {"segments": 80, "within_budget": 0.775, "rejected": {}, "mean_chars_over_budget": 1.4, "mean_seconds_per_call": 0.67}}
Primary translator: qwen3

Listen: audio/<clip>_dub.m4a. Read: review_<clip>.md. Private evaluation only (docs/footage.md).