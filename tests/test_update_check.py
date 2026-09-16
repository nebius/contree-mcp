from __future__ import annotations

import json
import logging
import time
from unittest.mock import MagicMock, patch

import pytest

from contree_mcp.update_check import UpdateChecker, UpdateState


def read_json(path):
    return json.loads(path.read_text())


def seed_state(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


@pytest.fixture()
def state_path(tmp_path, request):
    """Unique state file per test. Name disambiguator + explicit unlink so CI
    runners that reuse tmp_path (or any other path-collision quirk) cannot
    leak seeded state into a sibling test."""
    path = tmp_path / f"{request.node.name}_version_check.json"
    path.unlink(missing_ok=True)
    return path


HOUR = 3600.0
DAY = 86400.0


class TestParseVersion:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("1.2.3", ((1, 1), (2, 1), (3, 1))),
            ("0.0.1", ((0, 1), (0, 1), (1, 1))),
            ("0.4.2a1", ((0, 1), (4, 1), (2, 0))),
            ("1", ((1, 1),)),
            ("", ()),
            ("1.x.3", ((1, 1), (3, 1))),
            ("v1.2.3", ((1, 1), (2, 1), (3, 1))),
            ("1.0.0-rc.1", ((1, 1), (0, 1), (0, 0), (1, 1))),
        ],
    )
    def test_cases(self, value, expected):
        checker = UpdateChecker(state_path="/dev/null", current_version="0")
        assert checker.parse_version(value) == expected

    def test_pre_release_sorts_before_release(self):
        checker = UpdateChecker(state_path="/dev/null", current_version="0")
        assert checker.parse_version("0.4.2a1") < checker.parse_version("0.4.2")

    def test_higher_release_sorts_after_pre_release(self):
        checker = UpdateChecker(state_path="/dev/null", current_version="0")
        assert checker.parse_version("0.4.2") < checker.parse_version("0.4.21")

    def test_rc_sorts_before_release(self):
        checker = UpdateChecker(state_path="/dev/null", current_version="0")
        assert checker.parse_version("1.0.0-rc.1") < checker.parse_version("1.0.0")


class TestEnabled:
    def test_disabled_when_version_unknown(self, state_path):
        checker = UpdateChecker(state_path=state_path, current_version="unknown")
        assert checker.enabled is False

    def test_disabled_when_opt_out_env_set(self, state_path, monkeypatch):
        monkeypatch.setenv("CONTREE_NO_UPDATE_CHECK", "1")
        checker = UpdateChecker(state_path=state_path, current_version="0.1.0")
        assert checker.enabled is False

    def test_disabled_when_opt_out_env_set_to_empty(self, state_path, monkeypatch):
        """Presence (any value, even empty) opts out, per documented contract."""
        monkeypatch.setenv("CONTREE_NO_UPDATE_CHECK", "")
        checker = UpdateChecker(state_path=state_path, current_version="0.1.0")
        assert checker.enabled is False

    def test_enabled_normal(self, state_path):
        checker = UpdateChecker(state_path=state_path, current_version="0.1.0")
        assert checker.enabled is True


class TestIsCacheFresh:
    def test_returns_true_for_recent_last_check(self):
        checker = UpdateChecker(state_path="/dev/null", current_version="0")
        state = UpdateState(last_check=int(time.time() - HOUR), latest_version="x")
        assert checker.is_cache_fresh(state) is True

    def test_returns_false_for_old_last_check(self):
        checker = UpdateChecker(state_path="/dev/null", current_version="0")
        state = UpdateState(last_check=int(time.time() - 2 * DAY), latest_version="x")
        assert checker.is_cache_fresh(state) is False

    def test_returns_false_for_default_sentinel(self):
        checker = UpdateChecker(state_path="/dev/null", current_version="0")
        assert checker.is_cache_fresh(UpdateState()) is False


class TestUpdateState:
    def test_default_sentinel(self):
        state = UpdateState()
        assert state.last_check == 0
        assert state.latest_version == ""

    def test_from_file_missing_returns_sentinel(self, tmp_path):
        state = UpdateState.from_file(tmp_path / "missing.json")
        assert state == UpdateState()

    def test_from_file_corrupt_returns_sentinel(self, state_path):
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text("{not json")
        assert UpdateState.from_file(state_path) == UpdateState()

    def test_from_file_wrong_typed_returns_sentinel(self, state_path):
        seed_state(state_path, {"last_check": "iso-string", "latest_version": "1.0"})
        assert UpdateState.from_file(state_path) == UpdateState()

    def test_from_file_round_trip(self, state_path):
        original = UpdateState(last_check=12345, latest_version="1.2.3")
        original.to_file(state_path)
        assert UpdateState.from_file(state_path) == original

    def test_from_file_extra_fields_ignored(self, state_path):
        seed_state(
            state_path,
            {
                "last_check": 100,
                "latest_version": "1.0",
                "extra": "ignored",
            },
        )
        assert UpdateState.from_file(state_path) == UpdateState(
            last_check=100,
            latest_version="1.0",
        )


class TestRefresh:
    def test_skips_when_version_unknown(self, state_path):
        checker = UpdateChecker(state_path=state_path, current_version="unknown")
        with patch.object(checker, "fetch_latest_version") as fetch:
            checker.refresh()
        fetch.assert_not_called()
        assert checker.state == UpdateState()

    def test_skips_when_opt_out_env_set(self, state_path, monkeypatch):
        monkeypatch.setenv("CONTREE_NO_UPDATE_CHECK", "1")
        checker = UpdateChecker(state_path=state_path, current_version="0.1.0")
        with patch.object(checker, "fetch_latest_version") as fetch:
            checker.refresh()
        fetch.assert_not_called()
        assert checker.state == UpdateState()

    def test_fetches_and_writes_when_no_cache(self, state_path):
        checker = UpdateChecker(state_path=state_path, current_version="0.1.0")
        with patch.object(checker, "fetch_latest_version", return_value="0.1.1"):
            checker.refresh()
        assert checker.state.latest_version == "0.1.1"
        data = read_json(state_path)
        assert data["latest_version"] == "0.1.1"
        assert isinstance(data["last_check"], int)

    def test_skips_network_within_interval(self, state_path):
        seed_state(
            state_path,
            {
                "last_check": int(time.time() - HOUR),
                "latest_version": "0.2.0",
            },
        )
        checker = UpdateChecker(state_path=state_path, current_version="0.1.0")
        with patch.object(checker, "fetch_latest_version") as fetch:
            checker.refresh()
        fetch.assert_not_called()
        assert checker.state.latest_version == "0.2.0"

    def test_refetches_after_interval_expires(self, state_path):
        seed_state(
            state_path,
            {
                "last_check": int(time.time() - 2 * DAY),
                "latest_version": "0.1.0",
            },
        )
        checker = UpdateChecker(state_path=state_path, current_version="0.1.0")
        with patch.object(
            checker, "fetch_latest_version", return_value="0.1.5"
        ) as fetch:
            checker.refresh()
        fetch.assert_called_once()
        assert checker.state.latest_version == "0.1.5"
        assert read_json(state_path)["latest_version"] == "0.1.5"

    def test_network_failure_keeps_cached_value(self, state_path):
        seed_state(
            state_path,
            {
                "last_check": int(time.time() - 2 * DAY),
                "latest_version": "0.1.0",
            },
        )
        checker = UpdateChecker(state_path=state_path, current_version="0.1.0")
        with patch.object(checker, "fetch_latest_version", return_value=None):
            checker.refresh()
        assert checker.state.latest_version == "0.1.0"
        assert read_json(state_path)["latest_version"] == "0.1.0"

    def test_network_failure_with_no_cache_leaves_state_default(self, state_path):
        checker = UpdateChecker(state_path=state_path, current_version="0.1.0")
        with patch.object(checker, "fetch_latest_version", return_value=None):
            checker.refresh()
        assert checker.state == UpdateState()
        assert not state_path.exists()

    def test_corrupt_cache_is_overwritten(self, state_path):
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text("{not json")
        checker = UpdateChecker(state_path=state_path, current_version="0.1.0")
        with patch.object(
            checker, "fetch_latest_version", return_value="0.1.1"
        ) as fetch:
            checker.refresh()
        fetch.assert_called_once()
        assert checker.state.latest_version == "0.1.1"
        assert read_json(state_path)["latest_version"] == "0.1.1"

    def test_legacy_iso_last_check_is_discarded(self, state_path):
        """An old cache file written before the epoch migration is treated
        as missing entirely."""
        seed_state(
            state_path,
            {
                "last_check": "2026-05-08T12:00:00+00:00",
                "latest_version": "0.1.0",
            },
        )
        checker = UpdateChecker(state_path=state_path, current_version="0.1.0")
        with patch.object(
            checker, "fetch_latest_version", return_value="0.1.5"
        ) as fetch:
            checker.refresh()
        fetch.assert_called_once()
        assert read_json(state_path)["latest_version"] == "0.1.5"
        assert checker.state.latest_version == "0.1.5"

    def test_refresh_does_not_log_warning(self, state_path, caplog):
        checker = UpdateChecker(state_path=state_path, current_version="0.1.0")
        with (
            caplog.at_level(logging.WARNING, logger="contree_mcp.update_check"),
            patch.object(checker, "fetch_latest_version", return_value="0.2.0"),
        ):
            checker.refresh()
        assert "available" not in caplog.text


class TestIsLatest:
    def test_returns_true_when_version_unknown(self, state_path):
        checker = UpdateChecker(state_path=state_path, current_version="unknown")
        checker.state = UpdateState(last_check=1, latest_version="9.9.9")
        assert checker.is_latest() is True

    def test_returns_true_when_opt_out_env_set(self, state_path, monkeypatch):
        monkeypatch.setenv("CONTREE_NO_UPDATE_CHECK", "1")
        checker = UpdateChecker(state_path=state_path, current_version="0.1.0")
        checker.state = UpdateState(last_check=1, latest_version="9.9.9")
        assert checker.is_latest() is True

    def test_returns_false_when_outdated(self, state_path):
        checker = UpdateChecker(state_path=state_path, current_version="0.1.0")
        checker.state = UpdateState(last_check=1, latest_version="0.2.0")
        assert checker.is_latest() is False

    def test_returns_true_when_up_to_date(self, state_path):
        checker = UpdateChecker(state_path=state_path, current_version="0.2.0")
        checker.state = UpdateState(last_check=1, latest_version="0.2.0")
        assert checker.is_latest() is True

    def test_returns_true_when_latest_unknown(self, state_path):
        checker = UpdateChecker(state_path=state_path, current_version="0.1.0")
        # Default sentinel state — latest_version is empty string.
        assert checker.is_latest() is True

    def test_returns_true_when_current_is_newer(self, state_path):
        checker = UpdateChecker(state_path=state_path, current_version="0.3.0")
        checker.state = UpdateState(last_check=1, latest_version="0.2.0")
        assert checker.is_latest() is True

    def test_returns_false_when_current_is_pre_release_of_same(self, state_path):
        """Pre-release of the same release is older, so warns to upgrade."""
        checker = UpdateChecker(state_path=state_path, current_version="0.2.0a1")
        checker.state = UpdateState(last_check=1, latest_version="0.2.0")
        assert checker.is_latest() is False

    def test_returns_true_when_latest_is_pre_release_of_same(self, state_path):
        """If pypi only knows a pre-release, an installed stable is fine."""
        checker = UpdateChecker(state_path=state_path, current_version="0.2.0")
        checker.state = UpdateState(last_check=1, latest_version="0.2.0a1")
        assert checker.is_latest() is True

    def test_does_not_touch_filesystem(self, state_path):
        checker = UpdateChecker(state_path=state_path, current_version="0.1.0")
        checker.state = UpdateState(last_check=1, latest_version="0.2.0")
        with patch.object(UpdateState, "from_file") as load:
            checker.is_latest()
        load.assert_not_called()

    def test_does_not_log(self, state_path, caplog):
        checker = UpdateChecker(state_path=state_path, current_version="0.1.0")
        checker.state = UpdateState(last_check=1, latest_version="0.2.0")
        with caplog.at_level(logging.WARNING, logger="contree_mcp.update_check"):
            assert checker.is_latest() is False
        assert caplog.records == []


class TestFetchLatestVersion:
    @staticmethod
    def fake_connection(payload, status: int = 200):
        response = MagicMock()
        response.status = status
        response.read.return_value = json.dumps(payload).encode()
        conn = MagicMock()
        conn.getresponse.return_value = response
        return conn

    def test_returns_version_on_success(self, tmp_path):
        checker = UpdateChecker(state_path=tmp_path / "v.json", current_version="0")
        conn = self.fake_connection({"info": {"version": "1.2.3"}})
        with patch("contree_mcp.update_check.HTTPSConnection", return_value=conn):
            assert checker.fetch_latest_version() == "1.2.3"

    def test_returns_none_on_exception(self, tmp_path):
        checker = UpdateChecker(state_path=tmp_path / "v.json", current_version="0")
        with patch("contree_mcp.update_check.HTTPSConnection", side_effect=OSError("boom")):
            assert checker.fetch_latest_version() is None

    def test_returns_none_on_http_error_status(self, tmp_path):
        checker = UpdateChecker(state_path=tmp_path / "v.json", current_version="0")
        conn = self.fake_connection({"detail": "not found"}, status=404)
        with patch("contree_mcp.update_check.HTTPSConnection", return_value=conn):
            assert checker.fetch_latest_version() is None

    def test_returns_none_on_unexpected_payload(self, tmp_path):
        checker = UpdateChecker(state_path=tmp_path / "v.json", current_version="0")
        conn = self.fake_connection([])
        with patch("contree_mcp.update_check.HTTPSConnection", return_value=conn):
            assert checker.fetch_latest_version() is None


class TestMcpVersion:
    def test_returns_installed_version_or_unknown(self):
        from contree_mcp.update_check import mcp_version

        version = mcp_version()
        assert isinstance(version, str)
        assert version  # non-empty
