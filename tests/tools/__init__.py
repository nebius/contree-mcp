import pytest


class TestCase:
    @pytest.fixture(autouse=True)
    def _client_adapter(self, client_adapter_testing):
        pass
