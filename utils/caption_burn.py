import subprocess
import os


def _nvenc_usable() -> bool:
    """
    Real NVENC check.
    ffmpeg listing encoders is NOT enough on RunPod.
    """
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "-q"],
            stderr=subprocess.DEVNULL
        ).decode()
        return "Encoder" in out
    except Exception:
        return False


def burn_captions_with_audio_gpu(
    input_video: str,
    srt_path: str,
    output_video: str,
    font_name: str = "DejaVu Sans",
    font_size: int = 36,
    bottom_margin: int = 40,
    prefer_nvenc: bool = True,
):
    """
    Burn subtitles using FFmpeg + libass.
    Uses NVENC when actually available, otherwise safely falls back to CPU.
    Audio is preserved without re-encoding.
    """

    # ---- ASS style ----
    style = (
        f"FontName={font_name},"
        f"FontSize={font_size},"
        "PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,"
        "Outline=2,"
        "Shadow=0,"
        f"MarginV={bottom_margin}"
    )

    subtitles_filter = (
        f"subtitles='{srt_path}':"
        f"force_style='{style}'"
    )

    # ---- Decide encoder ----
    use_nvenc = prefer_nvenc and _nvenc_usable()

    if use_nvenc:
        print("🚀 Using NVENC for caption burn")
        cmd = [
            "ffmpeg", "-y",
            "-i", input_video,
            "-vf", subtitles_filter,
            "-c:v", "h264_nvenc",
            "-preset", "p4",
            "-profile:v", "high",
            "-rc", "vbr",
            "-cq", "19",
            "-c:a", "copy",
            output_video,
        ]
    else:
        print("⚠️ NVENC unavailable (RunPod / serverless). Falling back to CPU.")
        cmd = [
            "ffmpeg", "-y",
            "-i", input_video,
            "-vf", subtitles_filter,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "18",
            "-c:a", "copy",
            output_video,
        ]

    subprocess.run(cmd, check=True)
