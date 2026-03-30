import cv2
import time


class FrameSampler:
    def __init__(self, sample_interval_sec=2, max_frames=10):
        self.sample_interval_sec = sample_interval_sec
        self.max_frames = max_frames

    def sample(self, stream_url):
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
