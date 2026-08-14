from abc import ABC, abstractmethod

class StorageProvider(ABC):
    @abstractmethod
    def put_object(self, key: str, data: bytes, content_type: str) -> None: ...

    @abstractmethod
    def get_object(self, key: str) -> bytes: ...

    @abstractmethod
    def get_presigned_url(self, key: str, expires=3600) -> str | None: ...

    @abstractmethod
    def get_presigned_upload_url(self, key: str, expires=600,
                                 content_type: str = 'application/octet-stream') -> str: ...

    @abstractmethod
    def delete_object(self, key: str) -> None: ...

    @abstractmethod
    def object_exists(self, key: str) -> bool: ...