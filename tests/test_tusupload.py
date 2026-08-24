"""Tests for the TUS upload backend.

The bfabricpy call is always mocked: these tests cover BioBeamer's own decisions (which
container, which workunit, which files count as done) rather than bfabricpy's transfer.
"""

import logging
import types

import pytest

from biobeamer import tusupload
from biobeamer.tusupload import (
    TusUploadError,
    compare_files_destination_tus,
    group_files_by_folder,
    resolve_container_id,
    upload_files_with_tus,
    upload_folder_with_tus,
)


@pytest.fixture
def logger():
    return logging.getLogger("test_tusupload")


@pytest.fixture
def parameters(tmp_path):
    return {
        "source_path": str(tmp_path),
        "tus_endpoint": "http://localhost:1337/files",
        "application_id": 447,
        "tus_on_duplicate": "upload",
        "tus_track_job": False,
        "instrument": "EXPLORIS_1",
    }


def _summary(uploads=(), links=(), skips=(), failures=(), workunit_id=1, job_id=None):
    """Build a stand-in for bfabricpy's UploadSummary (only the fields we read)."""
    mk = lambda name: types.SimpleNamespace(filename=name, resource_id=1, error="boom")
    return types.SimpleNamespace(
        workunit_id=workunit_id,
        job_id=job_id,
        uploads=[mk(n) for n in uploads],
        links=[mk(n) for n in links],
        skips=[mk(n) for n in skips],
        failures=[mk(n) for n in failures],
    )


# --- container resolution: strict, no fallback -------------------------------------------

@pytest.mark.parametrize(
    "path,expected",
    [
        ("/Data2San/p1234/Proteomics/EXPLORIS_1/run/a.raw", 1234),
        ("/Data2San/C4321/Proteomics/x/b.raw", 4321),
        (r"D:\Data2San\p999\Proteomics\y\c.raw", 999),
        ("/Data2San/p1/x/d.raw", 1),
    ],
)
def test_resolve_container_id_accepted_formats(path, expected, logger):
    assert resolve_container_id(path, {}, logger) == expected


@pytest.mark.parametrize(
    "path",
    [
        "/Data2San/NO_CONTAINER/run/a.raw",
        "/Data2San/project1234/run/a.raw",  # 'p' must start the segment
        "/Data2San/p/run/a.raw",  # no digits
    ],
)
def test_resolve_container_id_raises_without_container(path, logger):
    """There is deliberately no fallback: misfiling data is worse than failing."""
    with pytest.raises(TusUploadError) as excinfo:
        resolve_container_id(path, {}, logger)
    message = str(excinfo.value)
    # The message is the interface instrument staff act on, so it must name both the
    # offending path and the accepted formats.
    assert path in message
    assert "p<digits>" in message and "C<digits>" in message


def test_resolve_container_id_honours_custom_pattern(logger):
    params = {"tus_container_pattern": r"order_([0-9]+)"}
    assert resolve_container_id("/data/order_777/a.raw", params, logger) == 777


def test_resolve_container_id_rejects_bad_pattern(logger):
    with pytest.raises(TusUploadError, match="not a valid regex"):
        resolve_container_id("/data/p1/a.raw", {"tus_container_pattern": "([0-9"}, logger)


# --- grouping: one workunit per acquisition ---------------------------------------------

def test_group_files_by_folder_separates_runs():
    groups = group_files_by_folder(
        [
            "/s/p1/E1/run_A/f1.raw",
            "/s/p1/E1/run_A/f2.raw",
            "/s/p1/E1/run_B/f3.raw",
        ],
        "/s",
    )
    assert groups == {
        "p1/E1/run_A": ["/s/p1/E1/run_A/f1.raw", "/s/p1/E1/run_A/f2.raw"],
        "p1/E1/run_B": ["/s/p1/E1/run_B/f3.raw"],
    }


@pytest.mark.parametrize("bundle", ["acq_01.d", "QDA_1.PRO"])
def test_group_files_by_folder_keeps_bundle_directories_together(bundle):
    """A Bruker .d / Waters .PRO acquisition is one workunit, not one per internal file."""
    files = [
        f"/s/p1/{bundle}/analysis.tdf",
        f"/s/p1/{bundle}/analysis.tdf_bin",
        f"/s/p1/{bundle}/nested/deeper.bin",
    ]
    groups = group_files_by_folder(files, "/s")
    assert list(groups) == [f"p1/{bundle}"]
    assert len(groups[f"p1/{bundle}"]) == 3


def test_group_files_by_folder_plain_raw_files_are_not_bundles():
    """Thermo .raw is a file: it must group by parent, not become its own group."""
    groups = group_files_by_folder(["/s/p1/E1/run/a.raw", "/s/p1/E1/run/b.raw"], "/s")
    assert list(groups) == ["p1/E1/run"]


def test_group_files_by_folder_loose_files_share_a_group():
    groups = group_files_by_folder(["/s/a.raw", "/s/b.raw"], "/s")
    assert list(groups) == [""]


# --- upload: outcome handling ------------------------------------------------------------

def test_upload_folder_simulate_uploads_nothing(mocker, parameters, logger, tmp_path):
    upload = mocker.patch("bfabric.operations.workunit.upload_files")
    f = tmp_path / "p1234" / "run" / "a.raw"
    f.parent.mkdir(parents=True)
    f.write_bytes(b"x")

    result = upload_folder_with_tus(
        "p1234/run", [str(f)], parameters, logger, str(tmp_path / "tool.log"),
        simulate_copy=True,
    )

    assert result == []
    upload.assert_not_called()


def test_upload_folder_counts_uploads_links_and_skips_as_done(
    mocker, parameters, logger, tmp_path
):
    """Links and skips are done: the bytes are stored, so they must not be retried."""
    files = []
    for name in ("a.raw", "b.raw", "c.raw"):
        f = tmp_path / "p1234" / "run" / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x")
        files.append(str(f))

    mocker.patch.object(tusupload._client_manager, "get_client", return_value=object())
    mocker.patch(
        "bfabric.operations.workunit.upload_files",
        return_value=_summary(uploads=["a.raw"], links=["b.raw"], skips=["c.raw"]),
    )

    result = upload_folder_with_tus(
        "p1234/run", files, parameters, logger, str(tmp_path / "tool.log")
    )

    assert sorted(result) == sorted(files)


def test_upload_folder_excludes_failures_so_they_retry(
    mocker, parameters, logger, tmp_path
):
    files = []
    for name in ("ok.raw", "bad.raw"):
        f = tmp_path / "p1234" / "run" / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x")
        files.append(str(f))

    mocker.patch.object(tusupload._client_manager, "get_client", return_value=object())
    mocker.patch(
        "bfabric.operations.workunit.upload_files",
        return_value=_summary(uploads=["ok.raw"], failures=["bad.raw"]),
    )

    result = upload_folder_with_tus(
        "p1234/run", files, parameters, logger, str(tmp_path / "tool.log")
    )

    assert [f for f in files if f.endswith("ok.raw")] == result
    assert not any(f.endswith("bad.raw") for f in result)


def test_upload_folder_requires_application_id(mocker, parameters, logger, tmp_path):
    parameters.pop("application_id")
    f = tmp_path / "p1234" / "run" / "a.raw"
    f.parent.mkdir(parents=True)
    f.write_bytes(b"x")
    with pytest.raises(TusUploadError, match="applicationID"):
        upload_folder_with_tus(
            "p1234/run", [str(f)], parameters, logger, str(tmp_path / "tool.log")
        )


def test_upload_folder_passes_container_and_application_to_bfabric(
    mocker, parameters, logger, tmp_path
):
    f = tmp_path / "p1234" / "run" / "a.raw"
    f.parent.mkdir(parents=True)
    f.write_bytes(b"x")
    parameters["tus_track_job"] = True

    mocker.patch.object(tusupload._client_manager, "get_client", return_value=object())
    upload = mocker.patch(
        "bfabric.operations.workunit.upload_files",
        return_value=_summary(uploads=["a.raw"]),
    )

    upload_folder_with_tus(
        "p1234/run", [str(f)], parameters, logger, str(tmp_path / "tool.log")
    )

    params = upload.call_args[0][1]
    assert params.container_id == 1234
    assert params.application_id == 447
    assert params.workunit_name == "run"
    assert params.track_job is True


# --- batch entry point -------------------------------------------------------------------

def test_upload_files_with_tus_one_call_per_group(mocker, parameters, logger, tmp_path):
    files = {}
    for rel in ("p1234/run_A/a.raw", "p1234/run_A/b.raw", "p1234/run_B/c.raw"):
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x")
        files[str(f)] = str(f)

    folder = mocker.patch(
        "biobeamer.tusupload.upload_folder_with_tus", return_value=["done"]
    )
    result = upload_files_with_tus(files, parameters, logger, str(tmp_path / "t.log"))

    # Two acquisition folders -> two workunits, not three (one per file).
    assert folder.call_count == 2
    assert result == ["done", "done"]


def test_upload_files_with_tus_requires_endpoint(parameters, logger, tmp_path):
    parameters.pop("tus_endpoint")
    with pytest.raises(TusUploadError, match="tus_endpoint"):
        upload_files_with_tus({}, parameters, logger, str(tmp_path / "t.log"))


def test_upload_files_with_tus_raises_when_a_group_fails(
    mocker, parameters, logger, tmp_path
):
    """A failing acquisition must surface, so the caller can exit non-zero."""
    files = {}
    for rel in ("p1234/run_A/a.raw", "p1234/run_B/b.raw"):
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x")
        files[str(f)] = str(f)

    mocker.patch(
        "biobeamer.tusupload.upload_folder_with_tus",
        side_effect=[["ok"], TusUploadError("nope")],
    )
    with pytest.raises(tusupload.TusUploadFailed) as excinfo:
        upload_files_with_tus(files, parameters, logger, str(tmp_path / "t.log"))
    assert "1 of 2 group" in str(excinfo.value)
    # The successful group is carried on the exception so the caller can still record it;
    # otherwise the next run would re-send bytes already stored in B-Fabric.
    assert excinfo.value.files_copied == ["ok"]


# --- destination comparison --------------------------------------------------------------

def test_compare_files_destination_tus_defers_to_bfabric(logger):
    """Dedup is B-Fabric's job (container-wide MD5), so nothing is pre-filtered locally."""
    mapping = {"/s/a.raw": "/s/a.raw", "/s/b.raw": "/s/b.raw"}
    result = compare_files_destination_tus(mapping, logger)
    assert result["copied"] == {}
    assert result["not_copied"] == mapping


# --- credential handling -----------------------------------------------------------------

def test_client_manager_rejects_scope_without_tus(mocker, logger, monkeypatch):
    monkeypatch.setenv("BFABRIC_CLIENT_SECRET", "s3cr3t")
    manager = tusupload._BfabricClientManager()
    with pytest.raises(TusUploadError, match="must include 'tus'"):
        manager.get_client(
            {
                "bfabric_base_url": "https://bf/bfabric",
                "bfabric_client_id": "svc",
                "bfabric_scope": "api:read api:write",
            },
            logger,
        )


def test_client_manager_reports_missing_credentials(logger, monkeypatch):
    monkeypatch.delenv("BFABRIC_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("BFABRIC_BASE_URL", raising=False)
    monkeypatch.delenv("BFABRIC_CLIENT_ID", raising=False)
    manager = tusupload._BfabricClientManager()
    with pytest.raises(TusUploadError) as excinfo:
        manager.get_client({}, logger)
    assert "BFABRIC_CLIENT_SECRET" in str(excinfo.value)


def test_client_manager_never_reads_secret_from_parameters(logger, monkeypatch):
    """The secret must come from the environment only -- never from the config XML."""
    monkeypatch.delenv("BFABRIC_CLIENT_SECRET", raising=False)
    manager = tusupload._BfabricClientManager()
    with pytest.raises(TusUploadError, match="BFABRIC_CLIENT_SECRET"):
        manager.get_client(
            {
                "bfabric_base_url": "https://bf/bfabric",
                "bfabric_client_id": "svc",
                "bfabric_scope": "api:read api:write tus",
                "bfabric_client_secret": "should-be-ignored",
            },
            logger,
        )


# --- bundle uploads: directory as a single entry -----------------------------------------

def _make_bundle(tmp_path, extra_on_disk=None):
    bundle = tmp_path / "p1234" / "acq_01.d"
    (bundle / "nested").mkdir(parents=True)
    files = [bundle / "analysis.tdf", bundle / "nested" / "deep.bin"]
    for f in files:
        f.write_bytes(b"x")
    if extra_on_disk:
        (bundle / extra_on_disk).write_bytes(b"y")
    return bundle, [str(f) for f in files]


def test_bundle_is_uploaded_as_one_directory_entry(
    mocker, parameters, logger, tmp_path
):
    """The .d directory goes up as a single entry so nested structure and names survive."""
    bundle, files = _make_bundle(tmp_path)
    mocker.patch.object(tusupload._client_manager, "get_client", return_value=object())
    upload = mocker.patch(
        "bfabric.operations.workunit.upload_files",
        return_value=_summary(uploads=["analysis.tdf", "nested/deep.bin"]),
    )

    result = upload_folder_with_tus(
        "p1234/acq_01.d", files, parameters, logger, str(tmp_path / "t.log")
    )

    params = upload.call_args[0][1]
    assert [str(p.path) for p in params.files] == [str(bundle)]
    # Both files are reported done, matched by their bundle-relative resource names.
    assert sorted(result) == sorted(files)


def test_partially_filtered_bundle_falls_back_to_individual_files(
    mocker, parameters, logger, tmp_path
):
    """Uploading the directory would send filtered-out files, so send the chosen ones."""
    bundle, files = _make_bundle(tmp_path, extra_on_disk="excluded.tmp")
    mocker.patch.object(tusupload._client_manager, "get_client", return_value=object())
    upload = mocker.patch(
        "bfabric.operations.workunit.upload_files",
        return_value=_summary(uploads=["analysis.tdf", "deep.bin"]),
    )

    result = upload_folder_with_tus(
        "p1234/acq_01.d", files, parameters, logger, str(tmp_path / "t.log")
    )

    params = upload.call_args[0][1]
    assert sorted(str(p.path) for p in params.files) == sorted(files)
    assert sorted(result) == sorted(files)


def test_resource_name_matches_bfabricpy_rules(tmp_path):
    """Mirror of bfabric.transfer._generic.checksums.compute_file_info."""
    # Directory entry: relative to the directory.
    assert (
        tusupload._resource_name("/s/p1/acq.d/nested/a.bin", "/s/p1/acq.d")
        == "nested/a.bin"
    )
    # File entry: basename only.
    assert tusupload._resource_name("/s/p1/run/a.raw", None) == "a.raw"


def test_missing_bfabric_on_old_python_says_python_is_the_problem(mocker, logger):
    """On <3.11 the tus extra installs nothing, so "re-run pip install" would mislead."""
    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def no_bfabric(name, *args, **kwargs):
        if name.startswith("bfabric"):
            raise ImportError("No module named 'bfabric'")
        return real_import(name, *args, **kwargs)

    mocker.patch("builtins.__import__", side_effect=no_bfabric)
    mocker.patch.object(tusupload.sys, "version_info", (3, 9, 0))

    manager = tusupload._BfabricClientManager()
    with pytest.raises(TusUploadError) as excinfo:
        manager.get_client({"bfabric_base_url": "x", "bfabric_client_id": "c"}, logger)
    message = str(excinfo.value)
    assert "3.11+" in message
    assert "pip install" not in message
