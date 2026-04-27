from django.conf import settings
from django.core.files.storage import FileSystemStorage

try:
    from storages.backends.s3 import S3Storage  # type: ignore
except Exception:
    S3Storage = None


if S3Storage and getattr(settings, "USE_S3", False):
    class BaseS3MediaStorage(S3Storage):
        """Shared S3 options for media storages."""

        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        region_name = settings.AWS_S3_REGION_NAME
        default_acl = None
        file_overwrite = False
        custom_domain = settings.AWS_S3_CUSTOM_DOMAIN or None


    class PublicMediaStorage(BaseS3MediaStorage):
        """Public files with unsigned URLs."""

        querystring_auth = False
        location = settings.AWS_PUBLIC_MEDIA_LOCATION


    class PrivateMediaStorage(BaseS3MediaStorage):
        """Private files with short-lived signed URLs."""

        querystring_auth = True
        querystring_expire = settings.AWS_PRIVATE_URL_EXPIRE
        location = settings.AWS_PRIVATE_MEDIA_LOCATION


    class MixedMediaStorage(BaseS3MediaStorage):
        """
        One storage backend with path-marker URL access:
        - /private/ marker in path -> signed URL
        - otherwise -> unsigned URL
        """

        location = settings.AWS_MEDIA_LOCATION
        querystring_auth = False
        private_path_markers = tuple(getattr(settings, 'AWS_PRIVATE_PATH_MARKERS', ()))
        querystring_expire = settings.AWS_PRIVATE_URL_EXPIRE

        def _is_private(self, name: str) -> bool:
            if not name:
                return False
            normalized_name = str(name).lstrip("/")
            return any(marker in f"/{normalized_name}" for marker in self.private_path_markers)

        def url(self, name, parameters=None, expire=None, http_method=None):
            # Temporarily toggle signing behavior by object path.
            original_querystring_auth = self.querystring_auth
            try:
                self.querystring_auth = self._is_private(name)
                effective_expire = expire or self.querystring_expire
                return super().url(
                    name,
                    parameters=parameters,
                    expire=effective_expire,
                    http_method=http_method,
                )
            finally:
                self.querystring_auth = original_querystring_auth
else:
    class BaseS3MediaStorage(FileSystemStorage):
        """Local filesystem fallback when S3 backend is disabled/unavailable."""

        def __init__(self, *args, **kwargs):
            kwargs.setdefault("location", settings.MEDIA_ROOT)
            kwargs.setdefault("base_url", settings.MEDIA_URL)
            super().__init__(*args, **kwargs)


    class PublicMediaStorage(BaseS3MediaStorage):
        pass


    class PrivateMediaStorage(BaseS3MediaStorage):
        pass


    class MixedMediaStorage(BaseS3MediaStorage):
        pass
