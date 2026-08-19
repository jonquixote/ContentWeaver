import abc


class ProviderError(Exception):
    pass


class Provider(abc.ABC):
    name = "base"
    base_url = ""

    def __init__(self, api_key=None):
        self.api_key = api_key or self._env_key()

    def _env_key(self):
        return None

    @abc.abstractmethod
    def list_models(self):
        raise NotImplementedError

    @abc.abstractmethod
    def chat(self, model, messages, **kwargs):
        raise NotImplementedError
