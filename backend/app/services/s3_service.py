"""
S3 upload service for resume and file storage.
Stores files under user-profiles/{user_id}/{filename} for multi-resume per user.
"""
import boto3
from botocore.exceptions import ClientError

from backend.app.core.config import settings
from backend.app.core.logging_config import get_logger

logger = get_logger("services.s3")


def _get_s3_client():
    """Get configured S3 client."""
    if not settings.aws_access_key_id or not settings.aws_secret_access_key:
        raise ValueError("AWS credentials not configured (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)")
    return boto3.client(
        "s3",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region,
    )


def upload_file_to_s3(
    file_buffer: bytes,
    file_name: str,
    user_id: int,
    mime_type: str = "application/octet-stream",
    key_prefix: str | None = None,
) -> dict:
    """
    Upload file to S3 under user-profiles/{user_id}/{file_name}.

    Args:
        file_buffer: File content as bytes
        file_name: Filename (e.g. uuid.pdf)
        user_id: User ID for folder organization
        mime_type: Content type
        key_prefix: S3 key prefix (default: user-profiles)

    Returns:
        dict with key, url
    """
    prefix = key_prefix or settings.s3_key_prefix
    key = f"{prefix}/{user_id}/{file_name}"

    logger.info(
        "S3 upload started bucket=%s region=%s key=%s user_id=%s file_name=%s size_bytes=%d",
        settings.aws_bucket_name,
        settings.aws_region,
        key,
        user_id,
        file_name,
        len(file_buffer),
    )

    try:
        s3 = _get_s3_client()
        s3.put_object(
            Bucket=settings.aws_bucket_name,
            Key=key,
            Body=file_buffer,
            ContentType=mime_type,
        )
        url = f"https://{settings.aws_bucket_name}.s3.{settings.aws_region}.amazonaws.com/{key}"
        logger.info(
            "S3 upload success bucket=%s key=%s url=%s",
            settings.aws_bucket_name,
            key,
            url,
        )
        return {"key": key, "url": url}
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        msg = e.response.get("Error", {}).get("Message", str(e))
        logger.error(
            "S3 upload failed bucket=%s region=%s key=%s user_id=%s error_code=%s error_message=%s",
            settings.aws_bucket_name,
            settings.aws_region,
            key,
            user_id,
            code,
            msg,
        )
        raise RuntimeError(f"S3 upload failed - {code}: {msg}") from e


def generate_presigned_url(key: str, expiration: int | None = None) -> str:
    """
    Generate a presigned URL for temporary access to an S3 object.
    Default expiration from config (s3_presigned_url_expiration).
    """
    if not settings.aws_access_key_id or not settings.aws_secret_access_key:
        return ""
    exp = expiration if expiration is not None else settings.s3_presigned_url_expiration
    try:
        s3 = _get_s3_client()
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.aws_bucket_name, "Key": key},
            ExpiresIn=exp,
        )
        return url or ""
    except ClientError as e:
        logger.warning("Presigned URL generation failed key=%s error=%s", key, e)
        return ""


def delete_file_from_s3(key: str) -> bool:
    """Delete object from S3 by key. Returns True on success, False on missing/error."""
    if not settings.aws_access_key_id or not settings.aws_secret_access_key:
        return False
    try:
        s3 = _get_s3_client()
        s3.delete_object(Bucket=settings.aws_bucket_name, Key=key)
        logger.info("S3 delete success bucket=%s key=%s", settings.aws_bucket_name, key)
        return True
    except ClientError as e:
        logger.warning("S3 delete failed key=%s error=%s", key, e)
        return False


def parse_s3_key_from_url(url: str) -> str | None:
    """Extract S3 object key from S3 URL. Returns None if not a valid S3 URL."""
    if not url or not url.startswith("http"):
        return None
    # https://bucket.s3.region.amazonaws.com/user-profiles/1/file.pdf
    try:
        parts = url.replace("https://", "").replace("http://", "").split("/", 1)
        if len(parts) != 2:
            return None
        host, path = parts
        if settings.aws_bucket_name in host and path.startswith("user-profiles/"):
            return path
        return None
    except Exception:
        return None
