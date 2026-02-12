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
    key_prefix: str = "user-profiles",
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
    key = f"{key_prefix}/{user_id}/{file_name}"

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
