FROM python:3.9-slim

# 必要な依存ライブラリをインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libxext6 \
    libxrender1 \
    libx11-dev \
    libglib2.0-0 \
    libqt5widgets5 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Pythonパッケージのインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 作業ディレクトリを設定
WORKDIR /workspace

# プロジェクトファイルをコピー
COPY . .

# デフォルトコマンドを設定
CMD ["python3", "video_stream.py"]
