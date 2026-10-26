"""Streaming quotas for ARI multipart uploads."""

from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.core.files.uploadhandler import FileUploadHandler


class AriAttachmentQuotaHandler(FileUploadHandler):
    """Stop oversized ARI uploads while Django is still receiving the body."""

    def __init__(self, request=None):
        super().__init__(request)
        content_type = (request.META.get("CONTENT_TYPE", "") if request else "").split(";", 1)[0]
        self.enabled = bool(
            request
            and request.method == "POST"
            and request.path_info.startswith("/ari/")
            and content_type.strip().casefold() == "multipart/form-data"
        )
        self.file_count = 0
        self.total_bytes = 0
        self.current_file_bytes = 0

    def new_file(self, *args, **kwargs):
        if not self.enabled:
            return
        self.file_count += 1
        if self.file_count > int(settings.ARI_MAX_ATTACHMENTS):
            raise RequestDataTooBig("The ARI attachment count exceeds its configured limit.")
        self.current_file_bytes = 0

    def receive_data_chunk(self, raw_data, start):
        if not self.enabled:
            return raw_data
        chunk_size = len(raw_data)
        self.current_file_bytes += chunk_size
        if self.current_file_bytes > int(settings.ARI_MAX_ATTACHMENT_BYTES):
            raise RequestDataTooBig("An ARI attachment exceeds its configured per-file limit.")
        self.total_bytes += chunk_size
        if self.total_bytes > int(settings.ARI_MAX_TOTAL_ATTACHMENT_BYTES):
            raise RequestDataTooBig("The ARI attachment bytes exceed their configured limit.")
        return raw_data

    def file_complete(self, file_size):
        return None
