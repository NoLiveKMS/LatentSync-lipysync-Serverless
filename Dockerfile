FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# System dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    python3-dev \
    build-essential \
    git \
    ffmpeg \
    libgl1 \
    ca-certificates \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Make python3.10 default
RUN ln -sf /usr/bin/python3.10 /usr/bin/python

WORKDIR /app

# Python tooling
RUN python3 -m pip install --upgrade pip setuptools wheel

RUN pip install \
    torch==2.5.1 \
    torchvision==0.20.1 \
    --extra-index-url https://download.pytorch.org/whl/cu121

# Install Python deps
COPY requirements.txt .
RUN pip install -r requirements.txt

# HuggingFace CLI + tensorflow (needed by mediapipe)
RUN pip install huggingface-hub tensorflow-cpu

# Copy application code
COPY . .

# Clone LatentSync
RUN git clone https://github.com/bytedance/LatentSync.git /app/LatentSync

# Download InsightFace buffalo_l face model
RUN mkdir -p /app/checkpoints/auxiliary/models/buffalo_l && \
    wget -O /tmp/buffalo_l.zip \
      https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip && \
    unzip /tmp/buffalo_l.zip -d /app/checkpoints/auxiliary/models/buffalo_l && \
    rm /tmp/buffalo_l.zip

# Download LatentSync UNet checkpoint
# → saves to /app/checkpoints/latentsync_unet.pt
RUN huggingface-cli download ByteDance/LatentSync-1.6 \
    latentsync_unet.pt \
    --local-dir /app/checkpoints \
    --local-dir-use-symlinks False

# Download Whisper tiny model
# → saves to /app/checkpoints/whisper/tiny.pt  (matches video.py WHISPER_TINY path)
RUN huggingface-cli download ByteDance/LatentSync-1.6 \
    whisper/tiny.pt \
    --local-dir /app/checkpoints \
    --local-dir-use-symlinks False

# Pre-download VAE (stabilityai/sd-vae-ft-mse → ~/.cache/huggingface)
RUN python3 pre_model.py

ENV PYTHONPATH="/app/LatentSync:${PYTHONPATH}"

# Runtime command
CMD ["python3", "app.py"]
