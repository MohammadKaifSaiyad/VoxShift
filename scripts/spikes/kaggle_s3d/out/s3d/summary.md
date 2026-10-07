# Spike S3d results

Started 2026-10-07 07:24:51; finished 2026-10-07 07:59:07

| Stage | OK | Wall s | Peak GPU MB | Error |
| --- | --- | --- | --- | --- |
| sep | True | 90.0 | 869 |  |
| vad | True | 31.5 | 3 |  |
| tag | True | 123.6 | 1605 |  |
| asr | True | 65.1 | 4119 |  |
| diar | True | 164.1 | 2853 |  |
| build | True | 0.5 | 0 |  |
| refs | True | 0.7 | 0 |  |
| audition | True | 215.8 | 3961 |  |
| translate | True | 265.9 |  |  |
| opus | True | 26.1 | 453 |  |
| tts | True | 316.4 | 4009 |  |
| rewrite_1 | True | 15.9 |  |  |
| tts_round1 | True | 124.7 | 4001 |  |
| rewrite_2 | True | 12.9 |  |  |
| tts_round2 | True | 52.9 | 4137 |  |
| qc | True | 22.2 | 235 |  |
| mix | True | 180.2 | 0 |  |
| check | True | 42.7 | 4119 |  |

## S3 → S3b → S3c → S3d

| Clip | > 1.10× S3 → S3b → S3c → S3d | Truncated S3 → S3b → S3c → S3d | Overflow | Short lines (pre-roll used, tempo > 1.25) | Speech coverage | Untranscribed muted s | Check (lang, WER) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| QJH3CCrjda4 | 64% → 67% → 42% → **38%** | 21% → 22% → 5% → **19%** | 19% | 1 (1, 1) | 67% | 12.5 | en 0.074 |
| aLvkEaaDte8 | 93% → 54% → 54% → **32%** | 47% → 17% → 21% → **9%** | 14% | 5 (2, 2) | 83% | 4.6 | en 0.429 |
| cQ8J2vdB9VU | 89% → 50% → 39% → **45%** | 43% → 19% → 14% → **28%** | 14% | 4 (2, 1) | 80% | 11.0 | en 0.157 |

## Per clip

### QJH3CCrjda4
- sep `QJH3CCrjda4`: {"audio_s": 438.39, "run_s": 20.85, "x_realtime": 21.03, "rtf": 0.048}
- vad `QJH3CCrjda4`: {"audio_s": 438.39, "run_s": 8.06, "x_realtime": 54.39, "rtf": 0.018, "regions": 21, "speech_s": 37.4}
- tag `QJH3CCrjda4`: {"audio_s": 438.39, "run_s": 29.62, "x_realtime": 14.8, "rtf": 0.068, "windows": 291, "singing_windows": 0, "max_singing": 0.092, "music_windows": 1}
- asr `QJH3CCrjda4`: {"audio_s": 438.39, "run_s": 13.65, "x_realtime": 32.12, "rtf": 0.031, "segments": 17, "words": 81, "vad_regions_missed_by_pass1": 3, "pass2_segments": 3, "pass2_words": 12}
- diar `QJH3CCrjda4_auto`: {"audio_s": 438.39, "run_s": 19.85, "x_realtime": 22.09, "rtf": 0.045, "speakers": 7, "speech_s_per_speaker": {"SPEAKER_00": 6.2, "SPEAKER_01": 4.5, "SPEAKER_02": 5.1, "SPEAKER_03": 7.8, "SPEAKER_04": 4.2, "SPEAKER_05": 4.1, "SPEAKER_06": 19.3}}
- diar `QJH3CCrjda4_fixed`: {"audio_s": 438.39, "run_s": 19.62, "x_realtime": 22.34, "rtf": 0.045, "speakers": 3, "speech_s_per_speaker": {"SPEAKER_00": 8.3, "SPEAKER_01": 19.2, "SPEAKER_02": 23.8}}
- build `QJH3CCrjda4`: {"segments": 16, "dubbable": 16, "skipped": {}, "asr_segments_dropped": {"whisper_scores": 0, "blacklist": 1, "pass2_scores": 1}, "speaker_flips_smoothed": 0, "fragments_merged": 0, "segments_under_1s": 1, "median_segment_s": 1.94, "speech_s_per_speaker": {"SPEAKER_00": 8.0, "SPEAKER_01": 19.5, "SPEAKER_02": 6.2}}
- refs `QJH3CCrjda4`: {"SPEAKER_00": 6.6, "SPEAKER_01": 13.2, "SPEAKER_02": 6.2}
- audition `QJH3CCrjda4`: {"SPEAKER_00": {"source": "cloned", "cps": 16.17}, "SPEAKER_01": {"source": "cloned", "cps": 15.07}, "SPEAKER_02": {"source": "cloned", "cps": 11.34}}
- translate `QJH3CCrjda4`: {"segments": 16, "chosen": {"translategemma": 16, "qwen3": 0, "opus-mt": 0}}
- opus `QJH3CCrjda4`: {"filled_by_opus_mt": 0}
- tts `QJH3CCrjda4`: {"audio_s": 46.19, "run_s": 66.13, "x_realtime": 0.7, "rtf": 1.432, "segments": 16, "errors": 0, "silence_trimmed_s": 1.17}
- rewrite_1 `QJH3CCrjda4`: {"over_1_10": 10, "rewritten": 9}
- tts_round1 `QJH3CCrjda4`: {"audio_s": 20.3, "run_s": 31.05, "x_realtime": 0.65, "rtf": 1.529, "segments": 9, "errors": 0, "silence_trimmed_s": 0.86}
- rewrite_2 `QJH3CCrjda4`: {"over_1_10": 5, "rewritten": 1}
- tts_round2 `QJH3CCrjda4`: {"audio_s": 2.32, "run_s": 4.04, "x_realtime": 0.57, "rtf": 1.741, "segments": 1, "errors": 0, "silence_trimmed_s": 0.32}
- qc `QJH3CCrjda4`: {"SPEAKER_02": {"n": 1, "cos_to_own_centroid_mean": 1.0, "cos_to_own_centroid_p10": 1.0, "below_0_6": 0}, "SPEAKER_01": {"n": 11, "cos_to_own_centroid_mean": 0.702, "cos_to_own_centroid_p10": 0.659, "below_0_6": 1}, "SPEAKER_00": {"n": 4, "cos_to_own_centroid_mean": 0.758, "cos_to_own_centroid_p10": 0.7, "below_0_6": 0}, "between_speakers": {"SPEAKER_00~SPEAKER_01": 0.242, "SPEAKER_00~SPEAKER_02": 0.327, "SPEAKER_01~SPEAKER_02": 0.368}}
- mix `QJH3CCrjda4`: {"dubbed": 16, "kept_original": 0, "fit": {"none": 8, "tempo_le_1_10": 2, "tempo_gt_1_10": 0, "overflow": 3, "truncated": 3}, "ratio_median": 1.0, "share_over_1_10": 0.375, "share_truncated": 0.188, "share_overflow": 0.188, "speech_s": 37.4, "speech_dubbed_s": 24.9, "speech_kept_original_s": 0.0, "speech_nonverbal_s": 0.0, "speech_untranscribed_muted_s": 12.5, "speech_coverage": 0.667, "short_lines": {"short": 1, "preroll_used": 1, "tempo_over_1_25": 1}}
- check `QJH3CCrjda4`: {"detected_language": "en", "language_probability": 0.967, "wer_vs_translation": 0.074}

### aLvkEaaDte8
- sep `aLvkEaaDte8`: {"audio_s": 516.13, "run_s": 24.27, "x_realtime": 21.26, "rtf": 0.047}
- vad `aLvkEaaDte8`: {"audio_s": 516.13, "run_s": 9.28, "x_realtime": 55.64, "rtf": 0.018, "regions": 27, "speech_s": 26.3}
- tag `aLvkEaaDte8`: {"audio_s": 516.13, "run_s": 36.82, "x_realtime": 14.02, "rtf": 0.071, "windows": 343, "singing_windows": 0, "max_singing": 0.024, "music_windows": 0}
- asr `aLvkEaaDte8`: {"audio_s": 516.13, "run_s": 7.24, "x_realtime": 71.31, "rtf": 0.014, "segments": 25, "words": 95, "vad_regions_missed_by_pass1": 1, "pass2_segments": 1, "pass2_words": 4}
- diar `aLvkEaaDte8_auto`: {"audio_s": 516.13, "run_s": 24.79, "x_realtime": 20.82, "rtf": 0.048, "speakers": 4, "speech_s_per_speaker": {"SPEAKER_00": 6.2, "SPEAKER_01": 21.0, "SPEAKER_02": 34.5, "SPEAKER_03": 20.3}}
- diar `aLvkEaaDte8_fixed`: {"audio_s": 516.13, "run_s": 24.71, "x_realtime": 20.88, "rtf": 0.048, "speakers": 2, "speech_s_per_speaker": {"SPEAKER_00": 20.3, "SPEAKER_01": 61.7}}
- build `aLvkEaaDte8`: {"segments": 23, "dubbable": 23, "skipped": {}, "asr_segments_dropped": {"whisper_scores": 0, "blacklist": 0, "pass2_scores": 0}, "speaker_flips_smoothed": 2, "fragments_merged": 5, "segments_under_1s": 6, "median_segment_s": 1.38, "speech_s_per_speaker": {"SPEAKER_00": 19.0, "SPEAKER_01": 15.8}}
- refs `aLvkEaaDte8`: {"SPEAKER_00": 7.0, "SPEAKER_01": 12.1}
- audition `aLvkEaaDte8`: {"SPEAKER_00": {"source": "cloned", "cps": 16.67}, "SPEAKER_01": {"source": "cloned", "cps": 11.6}}
- translate `aLvkEaaDte8`: {"segments": 23, "chosen": {"translategemma": 22, "qwen3": 0, "opus-mt": 1}}
- opus `aLvkEaaDte8`: {"filled_by_opus_mt": 1}
- tts `aLvkEaaDte8`: {"audio_s": 51.61, "run_s": 78.76, "x_realtime": 0.66, "rtf": 1.526, "segments": 22, "errors": 1, "silence_trimmed_s": 1.15}
- rewrite_1 `aLvkEaaDte8`: {"over_1_10": 11, "rewritten": 7}
- tts_round1 `aLvkEaaDte8`: {"audio_s": 9.27, "run_s": 16.85, "x_realtime": 0.55, "rtf": 1.817, "segments": 7, "errors": 0, "silence_trimmed_s": 0.41}
- rewrite_2 `aLvkEaaDte8`: {"over_1_10": 6, "rewritten": 0}
- tts_round2 `aLvkEaaDte8`: {"audio_s": 0.0, "run_s": 0.0, "x_realtime": null, "rtf": null, "segments": 0, "errors": 0, "silence_trimmed_s": 0.0}
- qc `aLvkEaaDte8`: {"SPEAKER_00": {"n": 11, "cos_to_own_centroid_mean": 0.712, "cos_to_own_centroid_p10": 0.627, "below_0_6": 1}, "SPEAKER_01": {"n": 7, "cos_to_own_centroid_mean": 0.656, "cos_to_own_centroid_p10": 0.496, "below_0_6": 2}, "between_speakers": {"SPEAKER_00~SPEAKER_01": 0.16}}
- mix `aLvkEaaDte8`: {"dubbed": 22, "kept_original": 1, "fit": {"none": 15, "tempo_le_1_10": 0, "tempo_gt_1_10": 2, "overflow": 3, "truncated": 2}, "ratio_median": 0.88, "share_over_1_10": 0.318, "share_truncated": 0.091, "share_overflow": 0.136, "speech_s": 26.3, "speech_dubbed_s": 21.4, "speech_kept_original_s": 0.0, "speech_nonverbal_s": 0.3, "speech_untranscribed_muted_s": 4.6, "speech_coverage": 0.827, "short_lines": {"short": 5, "preroll_used": 2, "tempo_over_1_25": 2}}
- check `aLvkEaaDte8`: {"detected_language": "en", "language_probability": 0.806, "wer_vs_translation": 0.429}

### cQ8J2vdB9VU
- sep `cQ8J2vdB9VU`: {"audio_s": 504.85, "run_s": 24.22, "x_realtime": 20.84, "rtf": 0.048}
- vad `cQ8J2vdB9VU`: {"audio_s": 504.85, "run_s": 9.02, "x_realtime": 55.99, "rtf": 0.018, "regions": 48, "speech_s": 53.7}
- tag `cQ8J2vdB9VU`: {"audio_s": 504.85, "run_s": 38.57, "x_realtime": 13.09, "rtf": 0.076, "windows": 335, "singing_windows": 0, "max_singing": 0.045, "music_windows": 3}
- asr `cQ8J2vdB9VU`: {"audio_s": 504.85, "run_s": 13.19, "x_realtime": 38.26, "rtf": 0.026, "segments": 35, "words": 149, "vad_regions_missed_by_pass1": 7, "pass2_segments": 6, "pass2_words": 7}
- diar `cQ8J2vdB9VU_auto`: {"audio_s": 504.85, "run_s": 23.13, "x_realtime": 21.83, "rtf": 0.046, "speakers": 5, "speech_s_per_speaker": {"SPEAKER_00": 8.6, "SPEAKER_01": 8.4, "SPEAKER_02": 14.0, "SPEAKER_03": 18.4, "SPEAKER_04": 36.0}}
- diar `cQ8J2vdB9VU_fixed`: {"audio_s": 504.85, "run_s": 23.39, "x_realtime": 21.58, "rtf": 0.046, "speakers": 2, "speech_s_per_speaker": {"SPEAKER_00": 48.0, "SPEAKER_01": 37.4}}
- build `cQ8J2vdB9VU`: {"segments": 32, "dubbable": 29, "skipped": {"low_confidence": 3}, "asr_segments_dropped": {"whisper_scores": 0, "blacklist": 0, "pass2_scores": 5}, "speaker_flips_smoothed": 0, "fragments_merged": 2, "segments_under_1s": 5, "median_segment_s": 1.64, "speech_s_per_speaker": {"SPEAKER_00": 40.8, "SPEAKER_01": 18.0, "UNKNOWN": 1.4}}
- refs `cQ8J2vdB9VU`: {"SPEAKER_00": 13.8, "SPEAKER_01": 11.4, "UNKNOWN": 0.0}
- audition `cQ8J2vdB9VU`: {"SPEAKER_00": {"source": "cloned", "cps": 17.14}, "SPEAKER_01": {"source": "cloned", "cps": 16.77}, "UNKNOWN": {"source": "fallback_bank_a", "cps": 19.16}}
- translate `cQ8J2vdB9VU`: {"segments": 29, "chosen": {"translategemma": 29, "qwen3": 0, "opus-mt": 0}}
- opus `cQ8J2vdB9VU`: {"filled_by_opus_mt": 0}
- tts `cQ8J2vdB9VU`: {"audio_s": 80.94, "run_s": 129.84, "x_realtime": 0.62, "rtf": 1.604, "segments": 29, "errors": 0, "silence_trimmed_s": 3.02}
- rewrite_1 `cQ8J2vdB9VU`: {"over_1_10": 16, "rewritten": 12}
- tts_round1 `cQ8J2vdB9VU`: {"audio_s": 29.47, "run_s": 45.68, "x_realtime": 0.65, "rtf": 1.55, "segments": 12, "errors": 0, "silence_trimmed_s": 1.21}
- rewrite_2 `cQ8J2vdB9VU`: {"over_1_10": 14, "rewritten": 4}
- tts_round2 `cQ8J2vdB9VU`: {"audio_s": 13.45, "run_s": 18.44, "x_realtime": 0.73, "rtf": 1.371, "segments": 4, "errors": 0, "silence_trimmed_s": 0.15}
- qc `cQ8J2vdB9VU`: {"SPEAKER_01": {"n": 7, "cos_to_own_centroid_mean": 0.756, "cos_to_own_centroid_p10": 0.72, "below_0_6": 0}, "SPEAKER_00": {"n": 20, "cos_to_own_centroid_mean": 0.676, "cos_to_own_centroid_p10": 0.541, "below_0_6": 3}, "between_speakers": {"SPEAKER_00~SPEAKER_01": 0.174}}
- mix `cQ8J2vdB9VU`: {"dubbed": 29, "kept_original": 3, "fit": {"none": 11, "tempo_le_1_10": 5, "tempo_gt_1_10": 1, "overflow": 4, "truncated": 8}, "ratio_median": 1.06, "share_over_1_10": 0.448, "share_truncated": 0.276, "share_overflow": 0.138, "speech_s": 53.7, "speech_dubbed_s": 40.5, "speech_kept_original_s": 0.4, "speech_nonverbal_s": 1.8, "speech_untranscribed_muted_s": 11.0, "speech_coverage": 0.795, "short_lines": {"short": 4, "preroll_used": 2, "tempo_over_1_25": 1}}
- check `cQ8J2vdB9VU`: {"detected_language": "en", "language_probability": 0.798, "wer_vs_translation": 0.157}

LLM probes: {"translategemma:4b": {"seconds_incl_load": 104.9, "answer": "Hello, how are you?"}, "qwen3:4b-instruct": {"seconds_incl_load": 3.9, "answer": "Hello, how are you?"}}
Translators: {"translategemma": {"segments": 68, "within_budget": 0.515, "rejected": {"commentary": 1}, "mean_chars_over_budget": 5.3, "mean_generation_s": 0.81}, "qwen3": {"segments": 68, "within_budget": 0.662, "rejected": {"commentary": 1}, "mean_chars_over_budget": 1.7, "mean_generation_s": 0.47}}
Primary translator: translategemma

Listen: audio/<clip>_dub.m4a. Read: review_<clip>.md. Private evaluation only (docs/footage.md).