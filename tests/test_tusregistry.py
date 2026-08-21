"""Tests for storage verification: a completed transfer is not confirmed storage.

The storage service's post-finish checks (virus scan, checksum, disk state) run after the tus
transfer completes and report to B-Fabric, not to the client. So a file BioBeamer recorded as copied
may have a resource marked ``failed`` -- and deleting the source on the strength of the ledger alone
would destroy the only copy.
"""

import logging
import os

import pytest

from biobeamer import cli
from biobeamer.tusregistry import (
    classify,
    forget,
    read_registry,
    record_uploads,
    registry_path,
    write_registry,
)


@pytest.fixture
def logger():
    return logging.getLogger("test_tusregistry")


@pytest.fixture
def params(tmp_path):
    return {
        "log_dir": str(tmp_path),
        "copied_files_log": str(tmp_path / "copied_files.txt"),
        "max_time_delete": 0,
    }


def _client(mocker, **status_by_id):
    """A client whose resource read answers with the given ``{id: status}``."""
    client = mocker.MagicMock()
    client.read.return_value = [
        {"id": int(rid), "status": status} for rid, status in status_by_id.items()
    ]
    return client


class TestRegistry:
    def test_round_trips_resource_ids(self, params, logger):
        path = registry_path(params)
        record_uploads(path, {"/d/a.raw": 101}, logger)

        assert read_registry(path, logger)[os.path.normpath("/d/a.raw")]["resource_id"] == 101

    def test_missing_file_is_empty_not_an_error(self, params, logger):
        assert read_registry(registry_path(params), logger) == {}

    def test_corrupt_file_is_empty_not_an_error(self, params, logger):
        path = registry_path(params)
        with open(path, "w") as handle:
            handle.write("{ not json")

        assert read_registry(path, logger) == {}

    def test_recording_keeps_earlier_entries(self, params, logger):
        path = registry_path(params)
        record_uploads(path, {"/d/a.raw": 101}, logger)
        record_uploads(path, {"/d/b.raw": 102}, logger)

        assert len(read_registry(path, logger)) == 2

    def test_forget_removes_one_entry(self, params, logger):
        path = registry_path(params)
        record_uploads(path, {"/d/a.raw": 101, "/d/b.raw": 102}, logger)
        forget(path, ["/d/a.raw"], logger)

        entries = read_registry(path, logger)
        assert os.path.normpath("/d/b.raw") in entries
        assert os.path.normpath("/d/a.raw") not in entries

    def test_a_future_format_version_is_ignored(self, params, logger):
        path = registry_path(params)
        write_registry(path, {"/d/a.raw": {"resource_id": 1}}, logger)
        with open(path) as handle:
            body = handle.read().replace('"version": 1', '"version": 99')
        with open(path, "w") as handle:
            handle.write(body)

        assert read_registry(path, logger) == {}


class TestClassify:
    """Only ``available`` authorises a delete; everything else is withheld."""

    def test_available_is_stored(self, mocker, params, logger):
        path = registry_path(params)
        record_uploads(path, {"/d/a.raw": 101}, logger)

        stored, rejected, unknown = classify(
            ["/d/a.raw"], path, _client(mocker, **{"101": "available"}), logger
        )

        assert stored == ["/d/a.raw"]
        assert not rejected and not unknown

    @pytest.mark.parametrize("status", ["failed", "invalid", "deleted", "expired"])
    def test_terminal_failure_is_rejected(self, mocker, params, logger, status):
        path = registry_path(params)
        record_uploads(path, {"/d/a.raw": 101}, logger)

        stored, rejected, _unknown = classify(
            ["/d/a.raw"], path, _client(mocker, **{"101": status}), logger
        )

        assert rejected == ["/d/a.raw"]
        assert not stored

    def test_pending_is_unknown_not_stored(self, mocker, params, logger):
        """The storage service has not ruled yet, so the file is not deletable."""
        path = registry_path(params)
        record_uploads(path, {"/d/a.raw": 101}, logger)

        stored, rejected, unknown = classify(
            ["/d/a.raw"], path, _client(mocker, **{"101": "pending"}), logger
        )

        assert unknown == ["/d/a.raw"]
        assert not stored and not rejected

    def test_unregistered_file_is_unknown(self, mocker, params, logger):
        stored, _rejected, unknown = classify(
            ["/d/never.raw"], registry_path(params), _client(mocker), logger
        )

        assert unknown == ["/d/never.raw"]
        assert not stored

    def test_unreadable_status_is_unknown(self, mocker, params, logger):
        """A read failure must not be mistaken for confirmation."""
        path = registry_path(params)
        record_uploads(path, {"/d/a.raw": 101}, logger)
        client = mocker.MagicMock()
        client.read.side_effect = RuntimeError("B-Fabric unreachable")

        stored, rejected, unknown = classify(["/d/a.raw"], path, client, logger)

        assert unknown == ["/d/a.raw"]
        assert not stored and not rejected


class TestDeletionGate:
    """``cleanup_copied_files`` may only delete what B-Fabric confirms it stored."""

    def test_tus_deletes_only_verified_files(self, mocker, params, logger):
        path = registry_path(params)
        record_uploads(path, {"/d/ok.raw": 101, "/d/virus.raw": 102}, logger)
        mocker.patch(
            "biobeamer.tusupload.get_client",
            return_value=_client(mocker, **{"101": "available", "102": "failed"}),
        )
        remove = mocker.patch("biobeamer.cli.remove_old_copied")

        cli.cleanup_copied_files(
            ["/d/ok.raw", "/d/virus.raw"], params, logger, None, "tus"
        )

        assert remove.call_args.args[0] == ["/d/ok.raw"]

    def test_other_tools_are_unaffected(self, mocker, params, logger):
        verify = mocker.patch("biobeamer.cli.verified_stored_files")
        remove = mocker.patch("biobeamer.cli.remove_old_copied")

        cli.cleanup_copied_files(["/d/a.raw"], params, logger, None, "scp")

        verify.assert_not_called()
        assert remove.call_args.args[0] == ["/d/a.raw"]

    def test_unreachable_bfabric_deletes_nothing(self, mocker, params, logger):
        mocker.patch("biobeamer.tusupload.get_client", side_effect=RuntimeError("no auth"))
        remove = mocker.patch("biobeamer.cli.remove_old_copied")

        cli.cleanup_copied_files(["/d/a.raw"], params, logger, None, "tus")

        assert remove.call_args.args[0] == []


class TestLedgerRepair:
    """A rejected upload must stop counting as done, or it is never retried."""

    def test_rejected_file_is_dropped_from_the_ledger(self, mocker, params, logger):
        path = registry_path(params)
        record_uploads(path, {"/d/ok.raw": 101, "/d/virus.raw": 102}, logger)
        mocker.patch(
            "biobeamer.tusupload.get_client",
            return_value=_client(mocker, **{"101": "available", "102": "failed"}),
        )

        repaired = cli.repair_ledger_for_rejected(
            ["/d/ok.raw", "/d/virus.raw"], params, logger
        )

        assert repaired == ["/d/ok.raw"]
        assert os.path.normpath("/d/virus.raw") not in read_registry(path, logger)

    def test_a_clean_ledger_is_returned_unchanged(self, mocker, params, logger):
        path = registry_path(params)
        record_uploads(path, {"/d/ok.raw": 101}, logger)
        mocker.patch(
            "biobeamer.tusupload.get_client",
            return_value=_client(mocker, **{"101": "available"}),
        )

        assert cli.repair_ledger_for_rejected(["/d/ok.raw"], params, logger) == ["/d/ok.raw"]

    def test_unreachable_bfabric_leaves_the_ledger_alone(self, mocker, params, logger):
        """Failing to check must not re-upload everything."""
        mocker.patch("biobeamer.tusupload.get_client", side_effect=RuntimeError("no auth"))

        assert cli.repair_ledger_for_rejected(["/d/a.raw"], params, logger) == ["/d/a.raw"]
