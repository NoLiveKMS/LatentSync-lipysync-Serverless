import runpod
import uuid
import os
import logging
import shutil
import torch
from pathlib import Path

from utils.s3 import download_file, upload_file
from utils.utllity import load_environment, classify_env
from utils.video import load_pipe, generate_lipsync
from utils.caption_burn import burn_captions_with_audio_gpu

logging.basicConfig(level=logging.INFO)

_ = load_pipe()  # preload LatentSync
SEED = 1247


def handler(event):
    workdir = None

    try:
        payload = event["input"]
        inp_meta_list = payload["inp_meta"]
        level = payload.get("level")

        results = []

        # ---- Environment selection ----
        if level != "local":
            ref_video_path = inp_meta_list[0]["ref_video_path"]
            if not level and ref_video_path:
                parts = ref_video_path.split("/")
                level = classify_env(parts[2]) if len(parts) > 2 else None
            load_environment(level)

        # ---- Working directory ----
        workdir = Path("/tmp") / str(uuid.uuid4())
        workdir.mkdir(parents=True, exist_ok=True)

        for meta_idx, meta in enumerate(inp_meta_list):
            ref_video_path = meta["ref_video_path"]
            cc_enabled = meta.get("cc", False)
            audio_meta_list = meta["ref_audio_meta"]

            meta_outputs = []

            for audio_idx, audio_meta in enumerate(audio_meta_list):
                audio_path = audio_meta["audio_path"]
                srt_path = audio_meta.get("srt_path")

                job_id = str(uuid.uuid4())
                job_dir = workdir / job_id
                job_dir.mkdir(parents=True, exist_ok=True)

                local_video = job_dir / "input.mp4"
                local_audio = job_dir / "input.wav"
                local_srt = job_dir / "subs.srt"

                lipsync_out = job_dir / "lipsync.mp4"
                final_out = job_dir / "final.mp4"
                temp_dir = job_dir / "temp"

                # ---- Download inputs ----
                if level == "local":
                    local_video = Path(ref_video_path)
                    local_audio = Path(audio_path)
                    if srt_path:
                        local_srt = Path(srt_path)
                else:
                    download_file(ref_video_path, str(local_video))
                    download_file(audio_path, str(local_audio))
                    if srt_path:
                        download_file(srt_path, str(local_srt))

                # ---- Lip-sync ----
                logging.info("🎬 Generating lip-sync")
                generate_lipsync(
                    video_path=str(local_video),
                    audio_path=str(local_audio),
                    output_path=str(lipsync_out),
                    temp_dir=str(temp_dir),
                    seed=SEED,
                )

                # ---- Caption burn (optional) ----
                if cc_enabled and srt_path:
                    logging.info("📝 Burning captions")
                    burn_captions_with_audio_gpu(
                        input_video=str(lipsync_out),
                        srt_path=str(local_srt),
                        output_video=str(final_out),
                    )
                    upload_target = final_out
                else:
                    upload_target = lipsync_out

                # ---- Upload ----
                if level == "local":
                    s3_output = str(upload_target)
                else:
                    s3_key = f"video_gen/latentsync/{job_id}.mp4"
                    s3_output = upload_file(str(upload_target), s3_key)

                meta_outputs.append({
                    "audio_path": audio_path,
                    "srt_path": srt_path,
                    "output_video": s3_output,
                    "cc_applied": cc_enabled and bool(srt_path),
                })

            results.append({
                "ref_video_path": ref_video_path,
                "outputs": meta_outputs,
            })

        return {
            "status": "success",
            "results": results,
        }

    except Exception as e:
        logging.exception("❌ Pipeline failed")
        return {"error": str(e)}

    finally:
        # ---- Cleanup ----
        if workdir and workdir.exists():
            shutil.rmtree(workdir, ignore_errors=True)
        torch.cuda.empty_cache()


runpod.serverless.start({"handler": handler})
