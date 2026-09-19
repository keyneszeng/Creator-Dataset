import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.core.errors import IntegrationNotInstalled
from app.storage.base import StoredObject


class S3ObjectStore:
    name = "s3"

    def __init__(
        self,
        *,
        bucket: str,
        region: str | None = None,
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        prefix: str = "",
    ) -> None:
        try:
            import boto3
        except ImportError as exc:
            raise IntegrationNotInstalled(
                'Install cloud storage dependencies with pip install -e ".[cloud]".'
            ) from exc

        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )

    def _key(self, key: str) -> str:
        normalized = key.strip("/")
        if not normalized or ".." in Path(normalized).parts:
            raise ValueError("Invalid object key.")
        return f"{self.prefix}/{normalized}" if self.prefix else normalized

    def put_file(self, source: Path, *, key: str) -> StoredObject:
        object_key = self._key(key)
        self.client.upload_file(str(source), self.bucket, object_key)
        return StoredObject(
            backend=self.name,
            key=key,
            size=source.stat().st_size,
            local_path=None,
            uri=f"s3://{self.bucket}/{object_key}",
        )

    def exists(self, *, key: str) -> bool:
        try:
            self.client.head_object(
                Bucket=self.bucket,
                Key=self._key(key),
            )
            return True
        except self.client.exceptions.ClientError:
            return False

    def delete(self, *, key: str) -> None:
        self.client.delete_object(
            Bucket=self.bucket,
            Key=self._key(key),
        )

    @contextmanager
    def materialize(
        self,
        *,
        key: str,
        suffix: str = "",
    ) -> Iterator[Path]:
        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False,
        ) as handle:
            path = Path(handle.name)

        try:
            self.client.download_file(
                self.bucket,
                self._key(key),
                str(path),
            )
            yield path
        finally:
            path.unlink(missing_ok=True)
