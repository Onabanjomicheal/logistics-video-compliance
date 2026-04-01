import cv2
import time
import re
import requests


class FrameSampler:
    def __init__(self, sample_interval_sec=2, max_frames=10):
        self.sample_interval_sec = sample_interval_sec
        self.max_frames = max_frames

    def _resolve_drive_url(self, url):
        file_id = None
        patterns = [
            r"drive\.google\.com/file/d/([a-zA-Z0-9_-]+)",
            r"drive\.google\.com/uc\?export=download&id=([a-zA-Z0-9_-]+)",
            r"docs\.google\.com/.*?/d/([a-zA-Z0-9_-]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                file_id = match.group(1)
                break

        if not file_id:
            return url

        return f"https://drive.usercontent.google.com/download?id={file_id}&export=download"

    def sample(self, stream_url):
        if "drive.google.com" in stream_url or "docs.google.com" in stream_url:
            stream_url = self._resolve_drive_url(stream_url)

        cap = cv2.VideoCapture(stream_url)
        if not cap.isOpened():
            raise RuntimeError(f"Unable to open video stream: {stream_url}")

        frames = []
        last_capture = 0.0
        try:
            while len(frames) < self.max_frames:
                ret, frame = cap.read()
                if not ret:
                    break
                now = time.time()
                if now - last_capture >= self.sample_interval_sec:
                    success, buffer = cv2.imencode(".jpg", frame)
                    if success:
                        frames.append(buffer.tobytes())
                        last_capture = now
        finally:
            cap.release()

        if not frames:
            raise RuntimeError("No frames captured from stream.")
        return frames