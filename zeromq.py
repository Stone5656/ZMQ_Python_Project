import time
import cv2
import zmq
import zlib
import threading
import logging
from typing import Dict, Optional
from dataclasses import dataclass

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)


@dataclass
class CameraConfig:
    width: int = 1280
    height: int = 720
    fps: int = 60
    jpeg_quality: int = 85
    zlib_level: int = 1


class CameraManager:
    def __init__(self, config: CameraConfig = CameraConfig()):
        self.config = config
        self.cameras: Dict[int, cv2.VideoCapture] = {}
        self.lock = threading.RLock()
        self.running = threading.Event()
        self.running.set()

    def initialize_camera(self, camera_id: int) -> Optional[cv2.VideoCapture]:
        """カメラの初期化と設定"""
        with self.lock:
            if camera_id in self.cameras:
                return self.cameras[camera_id]

            try:
                cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
                if not cap.isOpened():
                    raise RuntimeError(f"Camera {camera_id} open failed")

                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
                cap.set(cv2.CAP_PROP_FPS, self.config.fps)

                self.cameras[camera_id] = cap
                logging.info(f"Camera {camera_id} initialized")
                return cap

            except Exception as e:
                logging.error(f"Camera {camera_id} init error: {str(e)}")
                return None

    def release_camera(self, camera_id: int):
        """カメラの安全な解放"""
        with self.lock:
            if camera_id in self.cameras:
                self.cameras[camera_id].release()
                del self.cameras[camera_id]
                logging.info(f"Camera {camera_id} released")

    def get_frame(self, camera_id: int) -> Optional[bytes]:
        """フレーム取得と圧縮"""
        with self.lock:
            cap = self.cameras.get(camera_id)
            if not cap:
                return None

            try:
                ret, frame = cap.read()
                if not ret:
                    logging.warning(f"Frame read failed: Camera {camera_id}")
                    return None

                # 圧縮パイプライン
                _, buffer = cv2.imencode(
                    ".jpg",
                    frame,
                    [int(cv2.IMWRITE_JPEG_QUALITY), self.config.jpeg_quality],
                )
                compressed = zlib.compress(
                    buffer.tobytes(), level=self.config.zlib_level
                )
                return compressed

            except Exception as e:
                logging.error(f"Frame processing error: {str(e)}")
                return None


class StreamServer:
    def __init__(self, manager: CameraManager):
        self.manager = manager
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind("tcp://*:5555")

    def start_streaming(self, camera_id: int):
        """ストリーミングスレッドの開始"""

        def streaming_task():
            while self.manager.running.is_set():
                data = self.manager.get_frame(camera_id)
                if data:
                    try:
                        self.socket.send(data, flags=zmq.NOBLOCK)
                    except zmq.Again:
                        logging.warning("Queue full, frame dropped")
                time.sleep(1 / self.manager.config.fps)

        thread = threading.Thread(target=streaming_task, daemon=True)
        thread.start()
        return thread


if __name__ == "__main__":
    config = CameraConfig(width=640, height=480, fps=30, jpeg_quality=90, zlib_level=1)

    manager = CameraManager(config)
    server = StreamServer(manager)

    # カメラ0を初期化してストリーミング開始
    if manager.initialize_camera(0):
        server.start_streaming(0)
        logging.info("Streaming started for camera 0")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            manager.running.clear()
            logging.info("Shutting down...")
            manager.release_camera(0)
