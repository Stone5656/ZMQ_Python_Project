import zmq
import zlib
import cv2
import numpy as np

context = zmq.Context()
socket = context.socket(zmq.SUB)
socket.connect("tcp://127.0.0.1:5555")  # サーバーのアドレス
socket.setsockopt_string(zmq.SUBSCRIBE, "")  # 全メッセージを受信

while True:
    try:
        compressed_data = socket.recv()  # データを受信
        decompressed_data = zlib.decompress(compressed_data)  # 解凍
        frame = cv2.imdecode(
            np.frombuffer(decompressed_data, dtype=np.uint8), cv2.IMREAD_COLOR
        )
        cv2.imshow("Stream", frame)  # 受信したフレームを表示

        if cv2.waitKey(1) == 27:  # ESCキーで終了
            break
    except Exception as e:
        print(f"Error: {e}")
        break

cv2.destroyAllWindows()
