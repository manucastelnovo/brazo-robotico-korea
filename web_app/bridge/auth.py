"""Face login decision, made on the server from the camera results."""

TARGET_IDX = "1"  # Face Recognition ID trained in slot 1 (IDs are 1-based)


class RecognitionGate:
    """Recognize ID 1 on `required_streak` consecutive new frames within `window_s`.

    Only new frames count (frame_count must change). Any non-matching frame
    resets the streak, and so does a streak that takes longer than window_s.
    """

    def __init__(self, threshold, required_streak, window_s):
        self.threshold = threshold
        self.required_streak = required_streak
        self.window_s = window_s
        self.reset()

    def reset(self):
        self.streak = 0
        self.first_match = None
        self.last_count = None
        self.last_face = None
        self.recognized = False

    def _matches(self, face):
        return (
            face is not None
            and face.get("idx") == TARGET_IDX
            and face.get("percent") is not None
            and face["percent"] >= self.threshold
        )

    def update(self, face, frame_count, now):
        if not self.recognized and frame_count != self.last_count:
            self.last_count = frame_count
            self.last_face = face
            if not self._matches(face):
                self.streak = 0
                self.first_match = None
            else:
                if self.first_match is None or now - self.first_match > self.window_s:
                    self.streak = 0
                    self.first_match = now
                self.streak += 1
                if self.streak >= self.required_streak:
                    self.recognized = True
        return self.state()

    def state(self):
        face = self.last_face or {}
        return {
            "state": "recognized" if self.recognized else "searching",
            "streak": self.streak,
            "idx": face.get("idx"),
            "percent": face.get("percent"),
        }
