from abc import ABC, abstractmethod


class CMDBProvider(ABC):
    """Contract between a CMDB source and the local mirror synchronizer."""

    @abstractmethod
    def load_items(self):
        raise NotImplementedError

    @abstractmethod
    def validate(self):
        raise NotImplementedError

    @abstractmethod
    def normalize(self):
        raise NotImplementedError
