import time
import cv2
from flask import Flask, Response
import threading

app = Flask(__name__)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.config["DEBUG"] = False
app.config["PROPAGATE_EXCEPTIONS"] = True

# グローバルでカメラリソースを管理
video_captures = {}
video_captures_lock = threading.Lock()


def initialize_camera(camera_id):
    """指定されたIDのカメラを初期化する"""
    with video_captures_lock:
        if camera_id not in video_captures:
            cap = cv2.VideoCapture(camera_id)
            if not cap.isOpened():
                raise ValueError(f"Failed to open camera {camera_id}")
            video_captures[camera_id] = cap


def release_all_cameras():
    """すべてのカメラを解放"""
    with video_captures_lock:
        for cap in video_captures.values():
            cap.release()
        video_captures.clear()


def generate_frames(camera_id):
    """指定されたカメラIDからフレームを生成する"""
    global video_captures
    while True:
        with video_captures_lock:
            if camera_id not in video_captures:
                print(f"[Error] Camera {camera_id} not initialized.")
                break
            cap = video_captures[camera_id]

        ret, frame = cap.read()
        if not ret:
            print(f"[Error] Failed to capture frame from camera {camera_id}.")
            break

        # 解像度を調整
        frame = cv2.resize(frame, (640, 480))

        # JPEG圧縮設定を調整
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
        ret, buffer = cv2.imencode(".jpg", frame, encode_param)
        if not ret:
            print(f"[Error] Failed to encode frame from camera {camera_id}.")
            continue

        print(f"[Info] Camera {camera_id}: Frame size: {len(buffer)} bytes")

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
        )


@app.route("/video_feed/<int:camera_id>")
def video_feed(camera_id):
    """指定されたカメラのストリームを返すエンドポイント"""
    try:
        initialize_camera(camera_id)
    except ValueError as e:
        return f"<h1>{e}</h1>", 500

    return Response(
        generate_frames(camera_id), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


def setup():
    """サーバー開始時の初期化処理"""
    print("[Info] Server is starting...")


def teardown():
    """サーバー終了時のクリーンアップ"""
    print("[Info] Server is shutting down...")
    release_all_cameras()


if __name__ == "__main__":
    try:
        setup()
        app.run(
            host="0.0.0.0", port=5000, debug=False, threaded=True, use_reloader=False
        )
    except KeyboardInterrupt:
        print("[Info] Server interrupted by user.")
    finally:
        teardown()
