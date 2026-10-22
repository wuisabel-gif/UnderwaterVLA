"""
Image source abstraction.

The brains only care about "give me the current frame", not whether it comes from a
screenshot, a USB camera or the ROV's UDP/RTSP video stream. This module provides one interface:

    source = make_image_source("camera:0")      # USB camera
    source = make_image_source("screen")         # screen capture (original behaviour)
    source = make_image_source("udp://192.168.2.1:5600")  # BlueROV video stream
    img = source.capture()                       # PIL.Image
"""
import io
import os
import time
import base64
from typing import Optional, Tuple

from PIL import Image


class ImageSource:
    """Image source base class"""

    def capture(self) -> Image.Image:
        raise NotImplementedError

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class ScreenSource(ImageSource):
    """Screen capture source. Keeps the original "rotate 90 degrees clockwise" behaviour (rotate defaults to -90)."""

    def __init__(self, rotate: int = -90):
        self.rotate = rotate

    def capture(self) -> Image.Image:
        from PIL import ImageGrab  # lazy import so headless environments do not fail
        img = ImageGrab.grab()
        if self.rotate:
            img = img.rotate(self.rotate, expand=True)
        return img


class CameraSource(ImageSource):
    """
    OpenCV-based camera/video stream source.

    source can be:
      - an integer device index, e.g. 0
      - a video file path
      - a network stream URL: udp://..., rtsp://..., http://...
      - a GStreamer pipeline string (needs OpenCV built with gstreamer)
    """

    def __init__(self, source, width: Optional[int] = None, height: Optional[int] = None,
                 flush_frames: int = 2, rotate: int = 0):
        try:
            import cv2
        except ImportError as e:
            raise ImportError("CameraSource needs opencv-python: pip install opencv-python") from e
        self._cv2 = cv2
        self.source = source
        self.flush_frames = flush_frames
        self.rotate = rotate
        self.cap = cv2.VideoCapture(source)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open video source: {source!r}")
        if width:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        if height:
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        # Keep the buffer small so we get "now" rather than a frame from seconds ago
        try:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

    def capture(self) -> Image.Image:
        cv2 = self._cv2
        # Drop stale frames from the buffer
        for _ in range(self.flush_frames):
            self.cap.grab()
        ok, frame = self.cap.read()
        if not ok or frame is None:
            raise RuntimeError(f"Failed to read a video frame: {self.source!r}")
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame)
        if self.rotate:
            img = img.rotate(self.rotate, expand=True)
        return img

    def close(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None


def make_image_source(spec: str, **kwargs) -> ImageSource:
    """
    Build an image source from a string:
      "screen"            -> ScreenSource
      "camera:0"          -> CameraSource(0)
      "camera:/path.mp4"  -> CameraSource("/path.mp4")
      "udp://..." / "rtsp://..." / "http://..." -> CameraSource(url)
      plain digits "0"    -> CameraSource(0)
    """
    spec = (spec or "screen").strip()
    if spec == "screen":
        return ScreenSource(**kwargs)
    if spec.startswith("camera:"):
        target = spec[len("camera:"):]
        if target.isdigit():
            target = int(target)
        return CameraSource(target, **kwargs)
    if spec.isdigit():
        return CameraSource(int(spec), **kwargs)
    if "://" in spec or os.path.exists(spec):
        return CameraSource(spec, **kwargs)
    raise ValueError(f"Unrecognised image source: {spec!r}")


def encode_image(img: Image.Image, save_dir: str = "FIG") -> Tuple[str, str]:
    """
    Save the image under save_dir and return (base64 string, filename).
    Same return format as the original BaseBrain.encode_image_to_base64.
    """
    os.makedirs(save_dir, exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    filename = os.path.join(save_dir, f"{timestamp}_{int(time.time() * 1000) % 1000:03d}.png")
    img.save(filename, format="PNG")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8"), filename
