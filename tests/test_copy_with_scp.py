import os
from subprocess import CalledProcessError
import tempfile
import shutil
import logging
import pytest
from biobeamer.cli import copy_with_scp, copy_with_sftp


@pytest.fixture
def logger():
    return logging.getLogger("test_logger")


@pytest.fixture
def file_paths():
    return {
        "source": "/tmp/source_file.txt",
        "target": "/tmp/hello/nice/world/target_file.txt",
        "logfile": "/tmp/scp_test.log",
    }


@pytest.fixture(autouse=True)
def cleanup_log():
    log_path = "/tmp/scp_test.log"
    if os.path.exists(log_path):
        os.remove(log_path)


@pytest.mark.parametrize("copy_func,tool_name", [
    (copy_with_scp, "scp"),
    (copy_with_sftp, "sftp")
])
def test_copy_simulate(mocker, logger, file_paths, copy_func, tool_name):
    mock_run = mocker.patch("subprocess.run")

    result = copy_func(
        file_paths["source"],
        file_paths["target"],
        logger,
        file_paths["logfile"],
        simulate_copy=True,
    )
    assert result is None
    mock_run.assert_not_called()


@pytest.mark.parametrize("copy_func,tool_name", [
    (copy_with_scp, "scp"),
    (copy_with_sftp, "sftp")
])
def test_copy_success(mocker, logger, file_paths, copy_func, tool_name):
    if tool_name == "sftp":
        # Mock SFTP manager methods to succeed
        mocker.patch("biobeamer.sftpparamiko._sftp_manager.connect")
        mocker.patch("biobeamer.sftpparamiko._sftp_manager.mkdir_p")
        mocker.patch("biobeamer.sftpparamiko._sftp_manager.put_file")
    else:
        # Mock subprocess for scp
        mocker.patch("subprocess.run")

    result = copy_func(
        file_paths["source"],
        file_paths["target"],
        logger,
        file_paths["logfile"],
        simulate_copy=False,
    )
    assert result == file_paths["source"]


@pytest.mark.parametrize("copy_func,tool_name", [
    (copy_with_scp, "scp"),
    (copy_with_sftp, "sftp")
])
def test_copy_failure(mocker, logger, file_paths, copy_func, tool_name):
    if tool_name == "sftp":
        # Mock SFTP manager to fail
        mocker.patch("biobeamer.sftpparamiko._sftp_manager.connect").side_effect = CalledProcessError(1, "sftp")
    else:
        # Mock subprocess for scp
        mocker.patch("subprocess.run").side_effect = CalledProcessError(1, tool_name)

    copied = copy_func(
            file_paths["source"],
            file_paths["target"],
            logger,
            file_paths["logfile"],
            simulate_copy=False,
        )
    assert copied is None




@pytest.mark.parametrize("copy_func,tool_name", [
    (copy_with_scp, "scp"),
    (copy_with_sftp, "sftp")
])
def test_copy_with_integration(logger, copy_func, tool_name):
    import subprocess

    logfile = "/tmp/scp_test.log"
    try:
        subprocess.run(["scp"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        pytest.skip("scp not available on this system")
    tmp_dir = tempfile.TemporaryDirectory()
    source_path = os.path.join(tmp_dir.name, "example.raw")
    with open(source_path, "wb") as src:
        src.write(b"integration test content")
        src.flush()
        source_path = src.name
    target_dir = os.path.join(tmp_dir.name, "hello", "world", "witold")
    
    
    target_path = os.path.join(target_dir, os.path.basename(source_path))
    try:
        result = copy_func(
            source_path, target_path, logger, logfile, simulate_copy=False
        )
        assert os.path.exists(target_path)
        with open(target_path, "rb") as f:
            assert f.read() == b"integration test content"
        assert result == source_path
    finally:
        os.remove(source_path)
        shutil.rmtree(target_dir)
