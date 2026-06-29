import os
import logging
import subprocess
import json

from dotenv import load_dotenv, find_dotenv


def load_environment(env_key: str = "stag"):
    """
    Load stag/prod AWS credentials for downloading input files.
    Backblaze B2 credentials (R2_*) are always present as RunPod env vars.
    """
    if env_key not in ("stag", "prod"):
        raise ValueError("env_key must be 'stag' or 'prod'")

    env_file = find_dotenv(f"{env_key}.env", usecwd=True)
    if env_file:
        load_dotenv(env_file, override=False)
        logging.info(f"🟢 Loaded local {env_key}.env")
    else:
        logging.info("🟡 Using injected RunPod env vars")

    if env_key == "stag":
        os.environ["AWS_ACCESS_KEY_ID"] = os.environ["STAG_AWS_ACCESS_KEY_ID"]
        os.environ["AWS_SECRET_ACCESS_KEY"] = os.environ["STAG_AWS_SECRET_ACCESS_KEY"]
        os.environ["LAMBDA_BUCKET"] = os.environ["STAG_S3_BUCKET"]
    else:
        os.environ["AWS_ACCESS_KEY_ID"] = os.environ["PROD_AWS_ACCESS_KEY_ID"]
        os.environ["AWS_SECRET_ACCESS_KEY"] = os.environ["PROD_AWS_SECRET_ACCESS_KEY"]
        os.environ["LAMBDA_BUCKET"] = os.environ["PROD_S3_BUCKET"]

    os.environ.setdefault("AWS_REGION", "us-east-2")

    logging.info(f"✅ Runtime environment configured: {env_key}")
    return env_key


def classify_env(value: str, default: str = "stag") -> str:
    if not value:
        return default

    val = value.lower()
    if "prod" in val or "production" in val:
        return "prod"
    if "stag" in val or "staging" in val:
        return "stag"
    return default


def get_audio_duration(audio_path, padding_seconds=1.0):
    """
    Returns audio duration in seconds + padding.
    Falls back to 5s if ffprobe fails.
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            str(audio_path),
        ]
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )
        duration = float(json.loads(result.stdout)["format"]["duration"])
        return duration + padding_seconds
    except Exception as e:
        logging.warning(f"⚠️ Could not get audio duration for {audio_path}: {e}. Using 5s fallback.")
        return 5.0 + padding_seconds
