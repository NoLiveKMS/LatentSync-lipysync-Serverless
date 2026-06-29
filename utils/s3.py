import boto3
import os
import requests


def get_s3_client():
    """
    AWS S3 client for downloading input files (stag / prod buckets).
    """
    return boto3.client(
        "s3",
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region_name=os.environ.get("AWS_REGION", "us-east-2"),
    )


def get_b2_client():
    """
    Backblaze B2 S3-compatible client for uploading output files.
    """
    return boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY"],
        aws_secret_access_key=os.environ["R2_SECRET_KEY"],
        region_name="us-east-005",
    )


def download_file(uri, local_path):
    """
    Download a file from S3 (s3://bucket/key) or HTTP (https://...).
    """
    if uri.startswith("http"):
        r = requests.get(uri, timeout=60, stream=True)
        r.raise_for_status()
        with open(local_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return

    # s3://bucket/key
    _, _, bucket, *key_parts = uri.split("/")
    key = "/".join(key_parts)
    s3 = get_s3_client()
    s3.download_file(bucket, key, local_path)


def upload_file(local_path, key):
    """
    Upload a file to Backblaze B2 and return its public URL.
    Public URL format: {R2_PUBLIC_BASE}/{key}
    """
    b2 = get_b2_client()
    bucket = os.environ["R2_BUCKET"]

    b2.upload_file(
        local_path,
        bucket,
        key,
        ExtraArgs={"ContentType": "video/mp4"},
    )

    public_base = os.environ["R2_PUBLIC_BASE"].rstrip("/")
    return f"{public_base}/{key}"
