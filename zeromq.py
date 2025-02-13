import argparse
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
    # 解像度の幅（横ピクセル数）
    width: int = 1280
    # 解像度の高さ（縦ピクセル数）
    height: int = 720
    # フレームレート（1秒間に取得するフレーム数）
    fps: int = 60
    # JPEG画像の圧縮率（0-100の範囲、高いほど高品質）
    jpeg_quality: int = 85
    # zlib圧縮レベル（0-9の範囲、高いほど圧縮率が高いが遅くなる）
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
    def __init__(self, manager: CameraManager, port: int):
        self.manager = manager
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind(f"tcp://*:{port}")

    def start_streaming(self, camera_id: int):
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


def parse_arguments():
    """コマンドライン引数の解析"""
    parser = argparse.ArgumentParser(description="ZeroMQ Camera Streamer")
    parser.add_argument("--camera_id", type=int, default=0, help="使用するカメラのID")
    parser.add_argument("--width", type=int, default=1280, help="カメラ解像度の幅")
    parser.add_argument("--height", type=int, default=720, help="カメラ解像度の高さ")
    parser.add_argument("--fps", type=int, default=30, help="フレームレート")
    parser.add_argument("--jpeg_quality", type=int, default=85, help="JPEG圧縮率")
    parser.add_argument("--zlib_level", type=int, default=1, help="zlib圧縮レベル")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()

    config = CameraConfig(
        width=args.width,
        height=args.height,
        fps=args.fps,
        jpeg_quality=args.jpeg_quality,
        zlib_level=args.zlib_level,
    )

    manager = CameraManager(config)
    # カメラIDとポートの対応付け
    cameras = [(0, 5554), (2, 5556)]  #

    servers = []
    for camera_id, port in cameras:
        if manager.initialize_camera(camera_id):
            server = StreamServer(manager, port)
            server.start_streaming(camera_id)
            servers.append(server)
            logging.info(f"Streaming started for camera {camera_id} on port {port}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        manager.running.clear()
        logging.info("Shutting down...")
        for camera_id, _ in cameras:
            manager.release_camera(camera_id)
