# Step 5: Face / Delivery (2026-11-22)

`coach/delivery.py` (MediaPipe Face Landmarker, free, CPU, `models/mediapipe/face_landmarker.task`).
Video files given to `python -m coach.rate` get audio scores + Delivery; overall = average of 4.

Measures: face visible %, eye contact % (head pose + iris position vs the speaker's own usual position),
smiling %, expressiveness (eyebrow + smile movement per 2 s), mouth opening while speaking (with Whisper times),
head movement (degrees per 2 s), blinks per minute. Faces smaller than 120 px: mouth/blinks are not judged and
the speaker is told to sit closer. Speed: ~30 s per minute of 1080p video.

| test video (NASA, public domain, `data/test_videos/`) | eye contact | smiling | head movement | Delivery |
|---|---|---|---|---|
| Megan McArthur (lively presenter) | 77% | 39% | 20 deg/2s | 89 |
| Nick Hague (calm, whole body in picture) | 91% | 10% | 6 deg/2s | 88 |

Fixes found while testing: tracking jitter (smoothing), cuts to other shots (measured per continuous stretch),
far-away faces (zoomed second try: face found 4% -> 80%), tiny faces giving fake blinks (pixel-size check).

**Not yet validated:** thresholds are from presentation-skills ranges, tested only on 2 professional speakers.
Needs 1-2 videos of real learners (one normal, one looking away / frozen face) to check the score separates them.

## Update 2026-11-22: no Delivery score
Decided: the face is **not scored**. IELTS / TOEFL / CEFR judge only what they hear, so audio and video get the same
4 section scores, overall and level. Video adds unscored "ON CAMERA" tips (eye contact, smile, face movement, head,
face in picture) and, under pronunciation, a mouth-opening hint when the mouth barely opens (mumbling).
`delivery_score()` was removed; `camera_tips()` and `mouth_tip()` replace `feedback()`.
- Later the same day: an **On camera score /100** came back (`camera_score()`, same weights as the old delivery score),
  shown on its own line and in the spoken feedback, but still NOT in the overall score or the level.
  Shuhratkhon videos: 5 -> 91, 6 -> 88 (good eye contact 87-90%, no smiling).
