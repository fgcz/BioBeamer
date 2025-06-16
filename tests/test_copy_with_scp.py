import os
import tempfile
import shutil
import logging
import pytest
from biobeamer2.biobeamer2 import copy_with_scp


@pytest.fixture
def logger():
    return logging.getLogger("test_logger")


@pytest.fixture
def file_paths():
    return {
        "source": "/tmp/source_file.txt",
        "target": "/tmp/target_file.txt",
        "logfile": "/tmp/scp_test.log",
    }


@pytest.fixture
def dummy_popen_success():
    class DummyPopen:
        def __init__(self, *args, **kwargs):
            self._returncode = 0

        def wait(self):
            return self._returncode

        def terminate(self):
            pass

    return DummyPopen


@pytest.fixture
def dummy_popen_failure():
    class DummyPopen:
        def __init__(self, *args, **kwargs):
            self._returncode = 1

        def wait(self):
            return self._returncode

        def terminate(self):
            pass

    return DummyPopen


@pytest.fixture(autouse=True)
def cleanup_log():
    log_path = "/tmp/scp_test.log"
    if os.path.exists(log_path):
        os.remove(log_path)


def test_copy_with_scp_simulate(monkeypatch, logger, file_paths, dummy_popen_success):
    monkeypatch.setattr("biobeamer2.biobeamer2.Popen", dummy_popen_success)
    monkeypatch.setattr("biobeamer2.biobeamer2.os.path.exists", lambda x: True)
    result = copy_with_scp(
        file_paths["source"],
        file_paths["target"],
        logger,
        file_paths["logfile"],
        simulate_copy=True,
    )
    assert result is None


def test_copy_with_scp_success(monkeypatch, logger, file_paths, dummy_popen_success):
    monkeypatch.setattr("biobeamer2.biobeamer2.Popen", dummy_popen_success)
    monkeypatch.setattr("biobeamer2.biobeamer2.os.path.exists", lambda x: True)
    monkeypatch.setattr("biobeamer2.biobeamer2.os.path.getsize", lambda x: 123)
    result = copy_with_scp(
        file_paths["source"],
        file_paths["target"],
        logger,
        file_paths["logfile"],
        simulate_copy=False,
    )
    assert result == file_paths["source"]


def test_copy_with_scp_failure(monkeypatch, logger, file_paths, dummy_popen_failure):
    monkeypatch.setattr("biobeamer2.biobeamer2.Popen", dummy_popen_failure)
    monkeypatch.setattr(
        "biobeamer2.biobeamer2.os.path.exists", lambda x: x == file_paths["target"]
    )

    def getsize_side_effect(x):
        if x == file_paths["source"]:
            raise FileNotFoundError(f"No such file or directory: '{x}'")
        return 123

    monkeypatch.setattr("biobeamer2.biobeamer2.os.path.getsize", getsize_side_effect)
    with pytest.raises(Exception) as excinfo:
        copy_with_scp(
            file_paths["source"],
            file_paths["target"],
            logger,
            file_paths["logfile"],
            simulate_copy=False,
        )
    assert "scp exception raised on files" in str(excinfo.value)


def test_copy_with_scp_integration(logger):
    import subprocess

    logfile = "/tmp/scp_test.log"
    try:
        subprocess.run(["scp"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        pytest.skip("scp not available on this system")
    with tempfile.NamedTemporaryFile(delete=False) as src:
        src.write(b"integration test content")
        src.flush()
        source_path = src.name
    target_dir = tempfile.mkdtemp()
    target_path = os.path.join(target_dir, os.path.basename(source_path))
    try:
        result = copy_with_scp(
            source_path, target_path, logger, logfile, simulate_copy=False
        )
        assert os.path.exists(target_path)
        with open(target_path, "rb") as f:
            assert f.read() == b"integration test content"
        assert result == source_path
    finally:
        os.remove(source_path)
        shutil.rmtree(target_dir)
