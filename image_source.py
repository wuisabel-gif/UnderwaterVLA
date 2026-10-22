"""
图像来源抽象层。

大脑/小脑只关心"给我一张当前画面"，不关心画面来自屏幕截图、USB相机、
还是ROV的UDP/RTSP视频流。本模块提供统一接口：

    source = make_image_source("camera:0")      # USB相机
    source = make_image_source("screen")         # 屏幕截图（旧行为）
    source = make_image_source("udp://192.168.2.1:5600")  # BlueROV视频流
    img = source.capture()                       # PIL.Image
"""
import io
import os
import time
import base64
from typing import Optional, Tuple

from PIL import Image


class ImageSource:
    """图像来源基类"""

    def capture(self) -> Image.Image:
        raise NotImplementedError

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class ScreenSource(ImageSource):
    """屏幕截图来源。保留原项目的"顺时针旋转90度"行为（rotate 默认 -90）。"""

    def __init__(self, rotate: int = -90):
        self.rotate = rotate

    def capture(self) -> Image.Image:
        from PIL import ImageGrab  # 延迟导入，无显示环境时不报错
        img = ImageGrab.grab()
        if self.rotate:
            img = img.rotate(self.rotate, expand=True)
        return img


class CameraSource(ImageSource):
    """
    基于 OpenCV 的相机/视频流来源。

    source 可以是：
      - 整数设备号，例如 0
      - 视频文件路径
      - 网络流 URL：udp://..., rtsp://..., http://...
      - GStreamer pipeline 字符串（需要带 gstreamer 的 OpenCV）
    """

    def __init__(self, source, width: Optional[int] = None, height: Optional[int] = None,
                 flush_frames: int = 2, rotate: int = 0):
        try:
            import cv2
        except ImportError as e:
            raise ImportError("CameraSource 需要 opencv-python: pip install opencv-python") from e
        self._cv2 = cv2
        self.source = source
        self.flush_frames = flush_frames
        self.rotate = rotate
        self.cap = cv2.VideoCapture(source)
        if not self.cap.isOpened():
            raise RuntimeError(f"无法打开视频来源: {source!r}")
        if width:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        if height:
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        # 尽量减小缓冲，拿到的是"现在"而不是几秒前的帧
        try:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

    def capture(self) -> Image.Image:
        cv2 = self._cv2
        # 丢掉缓冲里的旧帧
        for _ in range(self.flush_frames):
            self.cap.grab()
        ok, frame = self.cap.read()
        if not ok or frame is None:
            raise RuntimeError(f"读取视频帧失败: {self.source!r}")
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
    根据字符串创建图像来源：
      "screen"            -> ScreenSource
      "camera:0"          -> CameraSource(0)
      "camera:/path.mp4"  -> CameraSource("/path.mp4")
      "udp://..." / "rtsp://..." / "http://..." -> CameraSource(url)
      纯数字 "0"          -> CameraSource(0)
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
    raise ValueError(f"无法识别的图像来源: {spec!r}")


def encode_image(img: Image.Image, save_dir: str = "FIG") -> Tuple[str, str]:
    """
    把图像保存到 save_dir 并返回 (base64字符串, 文件名)。
    与原 BaseBrain.encode_image_to_base64 的返回格式一致。
    """
    os.makedirs(save_dir, exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    filename = os.path.join(save_dir, f"{timestamp}_{int(time.time() * 1000) % 1000:03d}.png")
    img.save(filename, format="PNG")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8"), filename
