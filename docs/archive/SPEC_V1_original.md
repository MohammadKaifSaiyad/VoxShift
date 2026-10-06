# AI Video Dubber — V1 Implementation Specification

## Goal

Build a local-first end-to-end AI video dubbing application.

Input:

* Video URL, initially YouTube-compatible URLs
* Source language, default `tr` (Turkish)
* Target language, default `en` (English)

Output:

* A playable dubbed `.mp4`
* Original video preserved
* Original background music/ambience/SFX preserved as much as possible
* Original dialogue replaced with translated target-language speech
* Multiple actors receive different voices
* The same actor/speaker must consistently use the same generated voice throughout the entire video
* Male/female voice characteristics should be preserved where confidently detectable
* Unknown/ambiguous gender must be supported
* The system must continue processing when one speaker or segment fails by using a controlled fallback

This is V1, so prioritize a reliable complete pipeline over perfect lip sync or perfect studio-quality output.

IMPORTANT:

* Do not use paid AI APIs as a required dependency.
* Prefer local/open-source models.
* All AI providers must be abstracted behind provider interfaces so they can later be replaced by commercial APIs.
* Do not hardcode model-specific logic throughout the pipeline.
* Build the system so each stage can be retried independently.
* Process only content the user has the legal right/permission to process and use voice references only where the user has the necessary rights/consent.

---

# Recommended technology

Backend:

* Python 3.11/3.12
* FastAPI
* SQLite for V1
* SQLAlchemy
* Pydantic
* background worker architecture
* Docker Compose

Frontend:

* React
* Vite
* TypeScript

Media:

* FFmpeg
* ffprobe
* yt-dlp

Speech:

* WhisperX / faster-whisper for ASR
* pyannote speaker-diarization-community-1 for speaker diarization
* WhisperX forced alignment where applicable

Audio separation:

* Demucs initially
* provider interface so another dialogue-separation model can be added later

Translation:

* NLLB-200 or another locally runnable multilingual translation model
* default Turkish → English
* provider abstraction

TTS:

* XTTS-v2 as initial implementation
* Turkish/English support
* cross-language voice cloning
* provider abstraction

Storage:

* local filesystem for V1
* storage abstraction so S3 can be added later

---

# Core architecture

Create the following pipeline:

QUEUED
→ DOWNLOADING
→ EXTRACTING_AUDIO
→ SEPARATING_AUDIO
→ TRANSCRIBING
→ DIARIZING
→ BUILDING_SPEAKER_PROFILES
→ TRANSLATING
→ GENERATING_TTS
→ ALIGNING_AUDIO
→ MIXING_AUDIO
→ RENDERING_VIDEO
→ VALIDATING
→ COMPLETED

Every stage must:

1. Have a clear input artifact.
2. Have a clear output artifact.
3. Persist status.
4. Persist errors.
5. Be independently retryable.
6. Be idempotent.
7. Avoid rerunning successful previous stages unnecessarily.

---

# Job model

Create a Job entity containing:

* id
* source_url
* source_language
* target_language
* status
* progress
* current_stage
* created_at
* updated_at
* error_message
* output_path
* metadata

Progress should be calculated from completed stages/segments rather than fake timers.

---

# Artifact layout

Each job should have:

job/
source.mp4
source_audio.wav

separated/
dialogue.wav
background.wav

transcription/
transcription.json
aligned.json

diarization/
diarization.rttm
speakers.json

translation/
translations.json

voices/
speaker_00_reference.wav
speaker_01_reference.wav
...

tts/
segment_000001.wav
segment_000002.wav
...

audio/
generated_dialogue.wav
mixed_audio.wav

output/
dubbed_video.mp4

Never make the final video the only source of truth.

---

# Transcription

Use WhisperX/faster-whisper.

The transcription result must preserve:

* text
* start
* end
* words when available
* language
* confidence where available

Do not translate immediately.

First create a stable source-language transcript.

Handle:

* short utterances
* punctuation
* long utterances
* silence
* speech at scene boundaries
* noisy speech
* music-only sections
* speech overlapping with music

Do not generate TTS for non-speech sections.

---

# Speaker diarization

Use pyannote.

Output normalized segments:

{
"speaker": "SPEAKER_00",
"start": 12.31,
"end": 15.42
}

Join diarization information with transcription/alignment.

Every dialogue segment should eventually have:

* speaker_id
* source text
* start
* end

If speaker assignment is uncertain, mark:

speaker_confidence

Do not silently invent speaker identity.

---

# Global speaker registry

Create a SpeakerProfile entity:

* id
* job_id
* speaker_label
* embedding/reference information
* gender
* gender_confidence
* voice_id
* reference_audio_path
* confidence
* status

The most important rule:

A speaker gets ONE voice assignment per job.

Example:

SPEAKER_00 → voice_01
SPEAKER_01 → voice_02

Every segment belonging to SPEAKER_00 must use voice_01.

Never select a random TTS voice independently for each sentence.

---

# Speaker identity

Speaker identity must be based primarily on diarization/speaker embeddings.

Do NOT identify actors using gender alone.

Gender is metadata used for voice selection only.

Supported gender values:

* female
* male
* unknown

If confidence is low, use unknown and select a neutral compatible voice.

Do not crash because gender cannot be determined.

---

# Speaker reference extraction

For each speaker:

1. Find clean speech segments.
2. Prefer segments without overlapping speakers.
3. Prefer segments with good signal quality.
4. Remove excessive silence.
5. Avoid extremely short samples.
6. Combine the best available samples.
7. Generate a reference audio file.

Target approximately 10–30 seconds of useful speech when possible.

If enough clean audio is unavailable:

* use the best available shorter reference
* if cloning fails, use a predefined compatible target-language voice
* persist that fallback decision

The pipeline must continue.

---

# Voice registry

Example:

{
"SPEAKER_00": {
"voice_id": "voice_01",
"gender": "female",
"source": "cloned"
},
"SPEAKER_01": {
"voice_id": "voice_02",
"gender": "male",
"source": "cloned"
}
}

Cache voice assignments.

Never regenerate the identity for every TTS segment.

---

# Translation

Translate after speaker-aware transcript creation.

Use context-aware translation where practical.

Do not independently translate tiny fragments when they obviously belong to one sentence.

Preserve:

* names
* numbers
* important terminology
* emotional intent
* informal/formal relationships where possible

Translation output:

{
"segment_id": "...",
"speaker_id": "SPEAKER_00",
"source_text": "...",
"target_text": "...",
"start": 12.3,
"end": 15.4
}

Add validation that target_text is not empty.

---

# TTS

Use XTTS-v2 initially.

For every translated segment:

1. Find its speaker profile.
2. Load the cached speaker voice/reference.
3. Generate target-language speech.
4. Save segment audio.
5. Measure actual duration.
6. Compare with original target duration.

Do not regenerate the speaker identity between segments.

---

# Timing / duration fitting

Original segment:

start = 12.3
end = 15.4
target duration = 3.1 sec

Generated TTS may be:

4.2 sec

Implement:

1. Generate normal speech.
2. Measure duration.
3. If within acceptable range, accept.
4. If too long, retry with controlled speaking-rate adjustment if supported.
5. If still too long, apply conservative time-stretching.
6. If still impossible, shorten/rephrase the translation and regenerate.
7. Never allow a segment to overwrite the following dialogue unintentionally.

Do not use extreme time-stretching because it creates robotic audio.

Persist:

* original duration
* generated duration
* final duration
* fitting method
* retries

---

# Overlapping speech

Support overlapping speaker segments.

Example:

SPEAKER_00: 10.0–12.0
SPEAKER_01: 11.3–12.5

Generate separate audio tracks and mix them at their correct timestamps.

Never serialize overlapping dialogue into one sequential track.

---

# Background audio

Attempt to separate dialogue/speech from background audio using Demucs or the configured separation provider.

Create:

dialogue.wav
background.wav

Final audio should be approximately:

background.wav
+
generated English dialogue

Preserve:

* music
* ambience
* SFX

as much as the separation quality allows.

Do not assume source separation is perfect.

If separation quality is poor, use a configurable fallback such as:

* original audio at reduced volume
* generated dialogue mixed over original audio
* separated background

Choose the least destructive fallback based on validation.

---

# Audio quality

Before final rendering:

* normalize levels
* avoid clipping
* avoid severe volume jumps
* use short fades at segment boundaries when necessary
* prevent clicks/pops
* preserve stereo where appropriate
* generate a continuous dialogue track
* mix with background track

---

# Video rendering

Keep the original video stream whenever possible.

Replace/mux the audio using FFmpeg.

Do not unnecessarily re-encode the video.

Output:

dubbed_video.mp4

Validate with ffprobe.

---

# Failure handling

Every stage must support controlled failure.

Examples:

Download failure:
→ retry
→ expose readable error

Transcription failure:
→ retry
→ fail job if unrecoverable

Diarization failure:
→ retry
→ fallback to transcription-only speaker if explicitly configured

Speaker reference failure:
→ fallback target voice

Translation failure:
→ retry
→ preserve source text and mark segment failed

TTS failure:
→ retry
→ fallback voice
→ mark segment if still unsuccessful

Audio mixing failure:
→ retry

FFmpeg failure:
→ capture stderr
→ expose useful error
→ do not mark job completed

One failed segment must not automatically destroy the entire job if a fallback can produce valid output.

---

# Edge cases that MUST be handled

1. Invalid URL.
2. Unsupported URL.
3. Private/unavailable video.
4. Video download failure.
5. Video has no audio.
6. Audio is extremely quiet.
7. Audio contains mostly music.
8. Video contains only one speaker.
9. Video contains many speakers.
10. Same speaker appears throughout the entire video.
11. Speaker appears only once.
12. Two speakers have similar voices.
13. Male/female classification is uncertain.
14. Speaker has insufficient clean reference audio.
15. Multiple speakers talk simultaneously.
16. Background TV/radio voices.
17. Crowd speech.
18. Whisper hallucination during music/silence.
19. Incorrect timestamps.
20. Translation becomes substantially longer than source.
21. TTS is longer than source segment.
22. TTS is much shorter than source segment.
23. Extremely short utterances such as "What?", "Yes", "No".
24. Empty translation.
25. Translation contains unsupported characters.
26. TTS generation failure.
27. One speaker's voice cloning fails.
28. Background separation fails.
29. Audio clipping.
30. Segment boundary clicks.
31. Long videos.
32. Large temporary files.
33. Worker process crash.
34. Job restarted after partial completion.
35. Duplicate job submission.
36. User closes browser while processing.
37. Disk runs out of space.
38. GPU out-of-memory.
39. Model download failure.
40. Missing Hugging Face authentication/token for gated model.
41. Model version changes.
42. FFmpeg unavailable.
43. Corrupt intermediate artifact.
44. Final MP4 has invalid/missing audio.
45. Final audio/video durations don't match.

---

# GPU memory handling

AI models must be loaded lazily where appropriate.

Do not keep every model permanently on GPU.

Provide:

* GPU detection
* CPU fallback where practical
* configurable model sizes
* configurable compute dtype
* configurable batch size
* configurable chunk duration

Catch CUDA OOM and retry using a smaller configuration.

---

# Long-video strategy

Do not load an entire one-hour video into memory.

Use chunked processing.

However, speaker identity must remain global.

Implement:

local chunk speaker information
+
speaker embeddings
+
global speaker registry

so that:

chunk 1 SPEAKER_00
and
chunk 5 SPEAKER_03

can be reconciled as the same global speaker when evidence supports it.

---

# Provider interfaces

Create abstractions:

TranscriptionProvider
DiarizationProvider
SeparationProvider
TranslationProvider
TTSProvider

Example:

class TTSProvider:
def create_voice_profile(...):
...

```
def synthesize(...):
    ...
```

Implement local providers first:

WhisperXProvider
PyannoteProvider
DemucsProvider
NLLBProvider
XTTSProvider

Do not couple the pipeline directly to these implementations.

---

# API

Implement:

POST /api/jobs

GET /api/jobs/{job_id}

POST /api/jobs/{job_id}/retry

POST /api/jobs/{job_id}/cancel

GET /api/jobs/{job_id}/segments

GET /api/jobs/{job_id}/speakers

GET /api/jobs/{job_id}/artifacts

GET /api/jobs/{job_id}/download

---

# Frontend

Create a simple UI.

Input:

* video URL
* source language
* target language

Show:

* job status
* progress
* current stage
* speakers detected
* speaker → voice mapping
* errors/warnings
* completed output
* download button

For example:

Speaker list:

SPEAKER_00
Female / confidence 0.91
Voice: cloned
Segments: 83

SPEAKER_01
Male / confidence 0.88
Voice: cloned
Segments: 57

SPEAKER_02
Unknown / confidence 0.42
Voice: fallback
Segments: 4

---

# Observability

Log every pipeline stage.

Include:

job_id
stage
segment_id
speaker_id
duration
model
device
memory usage where available
retry_count
error

Do not log secrets.

---

# Cost tracking

Even though V1 uses local/open-source models, record:

* processing time
* GPU time where measurable
* CPU time
* model used
* approximate compute usage

This allows future comparison against paid APIs.

---

# Testing strategy

Create tests for:

1. transcription artifact schema
2. diarization mapping
3. speaker registry
4. speaker-to-voice consistency
5. translation schema
6. timing calculations
7. duration fitting
8. overlapping segments
9. fallback voice selection
10. retry behavior
11. idempotent stages
12. failed-stage recovery
13. FFmpeg output validation
14. corrupted intermediate files
15. job restart
16. duplicate job submission

Create a small synthetic test video containing:

* male speaker
* female speaker
* same speakers returning later
* overlapping speech
* background music
* silence
* very short utterances

Use this as the deterministic integration fixture.

---

# Development phases

Phase 1:
Build the pipeline with a 30–60 second test video.

Phase 2:
Add transcription + diarization.

Phase 3:
Add speaker registry + voice reference extraction.

Phase 4:
Add translation.

Phase 5:
Add XTTS voice generation.

Phase 6:
Add timing/duration fitting.

Phase 7:
Add background separation/mixing.

Phase 8:
Add FFmpeg final rendering.

Phase 9:
Add retries, resumability and validation.

Phase 10:
Add React UI.

Phase 11:
Test with 5-minute real Turkish drama footage.

Phase 12:
Test with 30–60 minute footage.

Do not move to the next phase until the previous phase has a working automated test.

---

# Important implementation rule

Do not attempt to build everything in one giant implementation.

First create the architecture and contracts.

Then implement each provider independently.

Then integrate them through the pipeline.

At every phase, produce a runnable application.

Do not replace failed components with fake/mock implementations in the final pipeline.

Mocks are acceptable only inside automated tests.

---

# Definition of Done

V1 is complete when I can run:

docker compose up

open the web UI

paste a permitted Turkish video URL

select English

start the job

and receive:

dubbed_video.mp4

where:

* the video plays
* Turkish dialogue has been replaced with English
* different speakers use different voices
* the same speaker consistently uses the same voice
* female/male/unknown voice characteristics are handled
* background audio remains where possible
* overlapping speech does not crash the pipeline
* long processing can resume after failure
* individual stages can be retried
* the final output is validated
* no paid API is required for the default local pipeline

Before coding, inspect the available open-source model licenses and current APIs and document them in `MODEL_LICENSES.md`.

Do not silently substitute a model whose license does not satisfy the project's intended usage.
