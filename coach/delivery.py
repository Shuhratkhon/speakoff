"""Step 5: face on camera (Video Record mode). Gives an "On camera" score out of 100 and tips, shown on their
own: NOT part of the overall score or the IELTS / TOEFL / CEFR level (exams judge only what they hear).
Also a mouth-opening hint for pronunciation.

MediaPipe Face Landmarker (free, CPU) gives for every video frame: 478 face points, 52 "blendshapes"
(how much each face muscle moves, 0-1: jawOpen, mouthSmileLeft, eyeLookOutRight, eyeBlinkLeft, ...)
and the head rotation. From those we measure:
  face visible   : share of the video where the face is in the picture
  eye contact    : looking at the camera (head turned less than ~15-20 degrees AND eyes not looking away)
  expression     : smiling some of the time + face that moves (not frozen / monotone)
  mouth          : how clearly the mouth opens while speaking (mumbling = small, stiff movements)
  head movement  : natural nodding vs frozen vs restless
  blinks         : per minute (very high = nervous)

Run (from the Speaking_Coach folder):
  python -m coach.delivery samples/video_1.mp4
"""

import math
import sys
from pathlib import Path

import av
import numpy as np
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions, vision

MODEL = Path(__file__).resolve().parent.parent / "models" / "mediapipe" / "face_landmarker.task"
FPS = 10                       # frames per second we analyse (enough for faces, 3x faster than 30)
MIN_FACE_PIXELS = 120          # smaller faces: lips and eyelids are too few pixels to measure
WIDTH = 1280                   # frames are shrunk to at most this width (small faces need the detail)


def _landmarker(mode=vision.RunningMode.VIDEO):
    options = vision.FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(MODEL)),
        running_mode=mode,
        num_faces=1,
        output_face_blendshapes=True,
        output_facial_transformation_matrixes=True,
    )
    return vision.FaceLandmarker.create_from_options(options)


def head_angles(matrix):
    """4x4 face transformation matrix -> (yaw = left/right, pitch = up/down, roll = tilt) in degrees."""
    r = np.array(matrix)[:3, :3]
    yaw = math.degrees(math.atan2(r[0, 2], r[2, 2]))
    pitch = math.degrees(math.atan2(-r[1, 2], math.hypot(r[0, 2], r[2, 2])))
    roll = math.degrees(math.atan2(r[1, 0], r[1, 1]))
    return yaw, pitch, roll


def read_frames(path, max_seconds=None):
    """Yield (time in seconds, RGB numpy frame) about FPS times per second (only the first max_seconds)."""
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        next_t = 0.0
        for frame in container.decode(stream):
            if frame.time is None or frame.time < next_t:
                continue
            if max_seconds and frame.time > max_seconds:
                break
            next_t = frame.time + 1 / FPS
            w = min(WIDTH, frame.width)
            h = int(frame.height * w / frame.width) // 2 * 2
            yield frame.time, frame.reformat(width=w, height=h, format="rgb24").to_ndarray()


# MediaPipe face points: eye corners, upper/lower eyelid, iris centre (subject's right eye, left eye)
EYES = [(33, 133, 159, 145, 468), (362, 263, 386, 374, 473)]


def iris_position(lm):
    """Where the iris sits inside the eye: (0.5, 0.5) = centre; x: 0 = one corner, 1 = the other."""
    xs, ys = [], []
    for c1, c2, top, bottom, iris in EYES:
        xs.append((lm[iris].x - lm[c1].x) / (lm[c2].x - lm[c1].x + 1e-6))
        ys.append((lm[iris].y - lm[top].y) / (lm[bottom].y - lm[top].y + 1e-6))
    return float(np.mean(xs)), float(np.mean(ys))


def _record(t, res, width, zoom=1.0):
    lm = res.face_landmarks[0]
    bs = {c.category_name: c.score for c in res.face_blendshapes[0]}
    yaw, pitch, roll = head_angles(res.facial_transformation_matrixes[0])
    gx, gy = iris_position(lm)
    return {"t": t, "face": True, "bs": bs, "yaw": yaw, "pitch": pitch, "roll": roll,
            "gx": gx, "gy": gy, "size": (lm[454].x - lm[234].x) / zoom,       # face width / picture width
            "width": width}


def track_face(path, max_seconds=None):
    """One record per analysed frame: {"face": False} if no face, else blendshapes, head angles, iris.
    MediaPipe's face finder is made for faces close to the camera; when it finds nothing (face far away,
    e.g. whole body in the picture) we try again on a zoomed-in crop of the upper middle of the picture."""
    frames = []
    with _landmarker() as video_lm, _landmarker(vision.RunningMode.IMAGE) as image_lm:
        for t, img in read_frames(path, max_seconds):
            res = video_lm.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(img)),
                                            int(t * 1000))
            if res.face_landmarks:
                frames.append(_record(t, res, img.shape[1]))
                continue
            h, w = img.shape[:2]
            crop = np.ascontiguousarray(img[: int(h * 0.6), int(w * 0.25): int(w * 0.75)])
            res = image_lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=crop))
            frames.append(_record(t, res, img.shape[1], zoom=2.0) if res.face_landmarks else {"t": t, "face": False})
    return frames


# ---------------------------------------------------------------- measures

def smooth(x, k=5):
    """Moving median over k frames (0.5 s): removes tracking jitter, keeps real movement."""
    x = np.asarray(x, float)
    pad = np.pad(x, k // 2, mode="edge")
    return np.array([np.median(pad[i:i + k]) for i in range(len(x))])


def looking_at_camera(yaw, pitch, gx, gy):
    """Eye contact per frame. Compared with the speaker's OWN usual position (median), because
    webcams sit above the screen and every face/eye shape is different; plus an absolute limit
    so someone who looks sideways the whole time is not counted as looking at the camera."""
    by, bp, bx, bgy = np.median(yaw), np.median(pitch), np.median(gx), np.median(gy)
    return ((np.abs(yaw - by) < 15) & (np.abs(pitch - bp) < 12) & (np.abs(yaw) < 25) &
            (np.abs(gx - bx) < 0.12) & (np.abs(gy - bgy) < 0.20))


def count_blinks(seq, threshold=0.5):
    closed = [s > threshold for s in seq]
    return sum(1 for a, b in zip(closed, closed[1:]) if b and not a)


def speaking_mask(frames, words):
    """True for frames during a spoken word (from Whisper times)."""
    if not words:
        return [True] * len(frames)
    spans = [(w["start"], w["end"]) for w in words]
    out, j = [], 0
    for f in frames:
        while j < len(spans) and spans[j][1] < f["t"]:
            j += 1
        out.append(j < len(spans) and spans[j][0] <= f["t"] <= spans[j][1])
    return out


def stretches(seen, gap=0.35):
    """Split face frames into continuous stretches (a cut or a lost face starts a new one)."""
    runs, cur = [], []
    for f in seen:
        if cur and f["t"] - cur[-1]["t"] > gap:
            runs.append(cur); cur = []
        cur.append(f)
    return runs + [cur] if cur else runs


def window_ranges(values, win=2 * FPS):
    """Range (max - min) inside each 2-second window: how much something moves."""
    return [float(np.ptp(values[i:i + win])) for i in range(0, len(values) - win + 1, win)]


def delivery_stats(frames, words=None):
    seen = [f for f in frames if f["face"]]
    duration = frames[-1]["t"] - frames[0]["t"] if len(frames) > 1 else 0
    if len(seen) < 5:
        return {"face_visible": round(100 * len(seen) / max(len(frames), 1), 1), "error": "face not found"}
    bs = lambda fs, k: np.array([f["bs"][k] for f in fs])

    looking, head, expr = [], [], []
    for run in stretches(seen):
        yaw, pitch = smooth([f["yaw"] for f in run]), smooth([f["pitch"] for f in run])
        gx, gy = smooth([f["gx"] for f in run]), smooth([f["gy"] for f in run])
        looking.append((yaw, pitch, gx, gy))
        head += [math.hypot(a, b) for a, b in zip(window_ranges(yaw), window_ranges(pitch))]
        brows = smooth(bs(run, "browInnerUp") + (bs(run, "browOuterUpLeft") + bs(run, "browOuterUpRight")) / 2)
        smile_run = smooth((bs(run, "mouthSmileLeft") + bs(run, "mouthSmileRight")) / 2)
        expr += [a + b for a, b in zip(window_ranges(brows), window_ranges(smile_run))]
    yaw, pitch, gx, gy = (np.concatenate([x[i] for x in looking]) for i in range(4))
    on_camera = looking_at_camera(yaw, pitch, gx, gy)

    smile = (bs(seen, "mouthSmileLeft") + bs(seen, "mouthSmileRight")) / 2
    blink = (bs(seen, "eyeBlinkLeft") + bs(seen, "eyeBlinkRight")) / 2
    speaking = np.array([s for s, f in zip(speaking_mask(frames, words), frames) if f["face"]])
    jaw = bs(seen, "jawOpen")
    jaw_speech = jaw[speaking] if speaking.any() else jaw
    seen_minutes = len(seen) / FPS / 60

    return {
        "duration": round(duration, 1),
        "face_visible": round(100 * len(seen) / len(frames), 1),
        "face_size": round(100 * float(np.median([f["size"] for f in seen])), 1),   # % of picture width
        "face_pixels": round(float(np.median([f["size"] * f["width"] for f in seen]))),  # face width in pixels
        "eye_contact": round(100 * float(np.mean(on_camera)), 1),
        "smile": round(100 * float(np.mean(smooth(smile) > 0.3)), 1),         # % of time smiling
        "expressiveness": round(float(np.median(expr)) if expr else 0.0, 3),  # face movement per 2 s (not frozen)
        "mouth_open": round(float(np.mean(jaw_speech)), 3),                    # average jaw opening while speaking
        "mouth_motion": round(float(np.std(jaw_speech)), 3),                   # how much it opens and closes
        "head_motion": round(float(np.median(head)) if head else 0.0, 1),     # degrees per 2 s
        "blinks_per_min": round(count_blinks(blink) / max(seen_minutes, 0.1), 1),
    }


def scale(value, bad, good):
    """0 at 'bad', 1 at 'good', straight line in between (works when bad > good too)."""
    if bad == good:
        return 1.0
    return min(max((value - bad) / (good - bad), 0.0), 1.0)


def band(value, low_bad, low_good, high_good, high_bad):
    """1 inside [low_good, high_good], falling to 0 at low_bad and high_bad (too little / too much)."""
    if value < low_good:
        return scale(value, low_bad, low_good)
    if value > high_good:
        return scale(value, high_bad, high_good)
    return 1.0


def camera_score(s):
    """On camera score out of 100. Shown on its own: NOT part of the overall score or the IELTS / CEFR /
    TOEFL level (exams judge only what they hear). Thresholds from presentation-skills ranges (provisional)."""
    if "error" in s:
        return 0
    small = s["face_pixels"] < MIN_FACE_PIXELS            # lips / eyelids too small to measure: neutral marks
    parts = {
        "eye_contact":   (35, scale(s["eye_contact"], 30, 80)),
        "face_visible":  (10, scale(s["face_visible"], 60, 95)),
        "expression":    (15, 0.5 * scale(s["expressiveness"], 0.03, 0.12) + 0.5 * band(s["smile"], 0, 10, 60, 95)),
        "mouth":         (20, 0.7 if small else
                          0.5 * scale(s["mouth_open"], 0.04, 0.15) + 0.5 * scale(s["mouth_motion"], 0.03, 0.10)),
        "head_movement": (15, band(s["head_motion"], 0.5, 2.5, 15, 30)),
        "blinks":        (5, 0.7 if small else band(s["blinks_per_min"], 0, 6, 30, 50)),
    }
    return round(sum(w * v for w, v in parts.values()))


def camera_tip_keys(s):
    """[(key, params)] for the unscored tips; the text is in i18n/<lang>.json ("cam_..." keys)."""
    if "error" in s:
        return [("cam_no_face", {})]
    tips = []
    small = s["face_pixels"] < MIN_FACE_PIXELS
    if small:
        tips.append(("cam_small", {}))
    if s["face_visible"] < 90:
        tips.append(("cam_out", {"pct": f"{100 - s['face_visible']:.0f}"}))
    if s["eye_contact"] < 60:
        tips.append(("cam_eye", {"pct": f"{s['eye_contact']:.0f}"}))
    if s["smile"] < 5:
        tips.append(("cam_smile", {}))
    if s["expressiveness"] < 0.12:
        tips.append(("cam_still_face", {}))
    if s["head_motion"] < 1.5:
        tips.append(("cam_still_head", {}))
    elif s["head_motion"] > 30:
        tips.append(("cam_head_moves", {}))
    if s["blinks_per_min"] > 35 and not small:
        tips.append(("cam_blinks", {}))
    return tips or [("cam_good", {})]


def camera_tips(s, lang="en"):
    """Unscored tips about how the speaker looks on camera (eye contact, face, head), in the app language."""
    from coach.i18n import t
    return [t(lang, k, **kw) for k, kw in camera_tip_keys(s)]


def mouth_tip(s, lang="en"):
    """Pronunciation hint from the video: a mouth that barely opens while speaking = mumbled sounds."""
    if "error" in s or s["face_pixels"] < MIN_FACE_PIXELS or s["mouth_open"] >= 0.07:
        return None
    from coach.i18n import t
    return t(lang, "cam_mouth")


def analyse_video(path, words=None, max_seconds=None):
    frames = track_face(path, max_seconds)
    stats = delivery_stats(frames, words)
    return {"stats": stats}


if __name__ == "__main__":
    path = sys.argv[1]
    words = None
    if "--words" in sys.argv:
        from coach.transcribe import transcribe
        words = transcribe(path)
    r = analyse_video(path, words)
    print("=== numbers ===")
    for k, v in r["stats"].items():
        print(f"  {k:16} {v}")
    print(f"\n=== ON CAMERA: {camera_score(r['stats'])}/100 (not in overall / level) ===")
    for t in camera_tips(r["stats"]) + [t for t in [mouth_tip(r["stats"])] if t]:
        print("  -", t)
