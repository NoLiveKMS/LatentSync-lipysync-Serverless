import runpod
import uuid
import os
import logging
import shutil
import torch
from pathlib import Path

from utils.s3 import download_file, upload_file
from utils.utllity import (
    load_environment,
    classify_env,
)
from utils.video import load_pipe, generate_lipsync

logging.basicConfig(level=logging.INFO)

_ = load_pipe()  # preload LatentSync
SEED = 1247


def handler(event):
    workdir = None

    try:
        inp = event["input"]

        # ---- Info mode ----
        if inp.get("aleef") is True:
            return {
                "service": "latentsync-1.6",
                "version": "1.0",
                "inputs": ["ref_video_path", "ref_audio_path", "level"],
            }

        ref_video = inp["ref_video_path"]
        ref_audio = inp["ref_audio_path"]
        level = inp.get("level")

        # ---- Environment selection ----
        if level != "local":
            if not level and ref_video:
                parts = ref_video.split("/")
                level = classify_env(parts[2]) if len(parts) > 2 else None
            load_environment(level)

        # ---- Working directory ----
        workdir = Path("/tmp") / str(uuid.uuid4())
        workdir.mkdir(parents=True, exist_ok=True)

        local_video = workdir / "input.mp4"
        local_audio = workdir / "input.wav"
        output_video = workdir / "output.mp4"
        temp_dir = workdir / "temp"

        # ---- Input handling ----
        if level == "local":
            logging.info("🧪 Local mode detected — skipping S3 download")
            local_video = Path(ref_video)
            local_audio = Path(ref_audio)
        else:
            download_file(ref_video, str(local_video))
            download_file(ref_audio, str(local_audio))

        logging.info("🎬 Starting lip-sync generation")

        generate_lipsync(
            video_path=str(local_video),
            audio_path=str(local_audio),
            output_path=str(output_video),
            temp_dir=str(temp_dir),
            seed=SEED,
        )

        # ---- Output handling ----
        if level == "local":
            logging.info("🧪 Local mode — skipping S3 upload")
            return {
                "video_path": str(output_video)
            }

        key = f"video_gen/latentsync/{uuid.uuid4()}.mp4"
        s3_path = upload_file(str(output_video), key)

        return {"video_path": s3_path}

    except Exception as e:
        logging.exception("❌ Lip-sync generation failed")
        return {"error": str(e)}

    finally:
        # ---- Cleanup files ----
        if workdir and workdir.exists():
            shutil.rmtree(workdir, ignore_errors=True)

        # ---- Cleanup GPU ----
        torch.cuda.empty_cache()


runpod.serverless.start({"handler": handler})
