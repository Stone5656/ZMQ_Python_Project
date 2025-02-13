import zmq
import numpy as np
import cv2
import time


def main():
    print("[INFO] Initializing ZMQ context and socket...")
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.connect("tcp://localhost:5558")  # C++側のIPに合わせる

    window_name = "Received Image"
    window_created = False  # ウィンドウが作成されたかを管理
    last_received_time = time.time()  # 最後に画像を受信した時間

    # ディスプレイ2の左上隅の座標（例: ディスプレイ1の幅が1920の場合）
    display2_x = -920  # ディスプレイ2のX座標
    display2_y = 150  # ディスプレイ2のY座標

    try:
        while True:
            print("[INFO] Sending request for image...")
            socket.send(b"request")  # 画像リクエストを送信

            print("[INFO] Waiting for image data...")
            # ヘッダーを受信
            header = socket.recv()
            rows, cols = np.frombuffer(header, dtype=np.int32)
            print(f"[INFO] Received header - Rows: {rows}, Cols: {cols}")

            # 画像データを受信
            image_data = socket.recv()
            print(f"[INFO] Received image data size: {len(image_data)} bytes")

            # 画像をデコード
            img = cv2.imdecode(
                np.frombuffer(image_data, dtype=np.uint8), cv2.IMREAD_COLOR
            )
            if img is None:
                print("[ERROR] Failed to decode image!")
                continue

            # 最後に画像を受信した時間を更新
            last_received_time = time.time()

            # 最初の画像受信時にウィンドウを作成
            if not window_created:
                cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
                cv2.resizeWindow(window_name, 500, 350)
                cv2.moveWindow(
                    window_name, display2_x, display2_y
                )  # ディスプレイ2に移動
                window_created = True  # ウィンドウ作成済みフラグをセット

            print("[INFO] Displaying image...")
            cv2.imshow(window_name, img)

            # ESCキーが押されたらループを終了
            if cv2.waitKey(1) & 0xFF == 27:
                print("[INFO] ESC key pressed, closing...")
                break

            # 5秒間画像が送られてこない場合、ウィンドウをリセット
            if time.time() - last_received_time > 5:
                print("[INFO] No image received for 5 seconds, resetting window...")
                cv2.destroyAllWindows()
                window_created = False
                last_received_time = time.time()  # タイマーをリセット

            # 過負荷防止のため短い待機時間を挿入
            time.sleep(0.05)

    except KeyboardInterrupt:
        print("[INFO] KeyboardInterrupt received, exiting...")
    except Exception as e:
        print(f"[ERROR] Exception occurred: {e}")
    finally:
        print("[INFO] Cleaning up resources...")
        cv2.destroyAllWindows()
        context.destroy()
        print("[INFO] Program terminated.")


if __name__ == "__main__":
    main()
