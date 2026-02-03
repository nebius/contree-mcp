import pytest


class TestCase:
    @pytest.fixture(autouse=True)
    def _contree_client(self, contree_client):
        return contree_client
