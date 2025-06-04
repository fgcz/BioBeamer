import os
import shutil
import sys
import tempfile
import time
import shutil
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from src import biobeamer2


@pytest.fixture(autouse=True)
def cleanup_logs():
    log_files = [
        os.path.join("./log", "biobeamer_test.log"),
        os.path.join("./log", "tool_test.log"),
        os.path.join("./log", "copied_files_test_integration.txt"),
        "/tmp/copied_files.txt",
    ]
    for log_path in log_files:
        if os.path.exists(log_path):
            os.remove(log_path)


def test_main():
    with patch("src.biobeamer2.MyLog.MyLog") as mock_MyLog, patch(
        "src.biobeamer2.BioBeamerParser"
    ) as mock_BioBeamerParser, patch("src.biobeamer2.Drive") as mock_Drive, patch(
        "src.biobeamer2.copy_files"
    ) as mock_copy_files, patch(
        "src.biobeamer2.socket.gethostname", return_value="testhost"
    ), patch(
        "src.biobeamer2.time.sleep"
    ) as mock_sleep:
        test_args = [
            "biobeamer2.py",
            "--config-url",
            "file:///tmp/configs",
            "--password",
            "test_password",
            "--xml",
            "TestConfig.xml",
            "--hostname",
            "testhost",
        ]
        with patch.object(sys, "argv", test_args):
            # Setup mocks
            mock_logger = MagicMock()
            mock_MyLog.return_value = mock_logger
            mock_parser = MagicMock()
            mock_parser.parameters = {
                "syshandler_adress": "localhost",
                "syshandler_port": 1234,
                "time_out": 0,
                "target_path": "/tmp/target",
                "copied_files_log": "/tmp/copied_files.txt",
                "simulate_delete": False,
                "robocopy_mov": False,
                "simulate_copy": False,
                "max_time_delete": 9999,
                "source_path": "/tmp/source",
                "func_target_mapping": "",
                "tool": "robocopy",
            }
            mock_parser.regex = MagicMock()
            mock_BioBeamerParser.BioBeamerParser.return_value = mock_parser

            biobeamer2.main()
            assert mock_MyLog.called
            assert mock_BioBeamerParser.BioBeamerParser.called
            assert mock_copy_files.called


def is_tool_available(tool_name):
    """Check whether `tool_name` is on PATH and marked as executable."""
    from shutil import which

    return which(tool_name) is not None


@pytest.mark.skipif(
    not is_tool_available("robocopy"), reason="robocopy not available on system"
)
def test_bio_beamer_main_integration_robocopy():
    _run_bio_beamer_main_integration_with_tool("robocopy")


@pytest.mark.skipif(not is_tool_available("scp"), reason="scp not available on system")
def test_bio_beamer_main_integration_scp():
    _run_bio_beamer_main_integration_with_tool("scp")


def _run_bio_beamer_main_integration_with_tool(tool):
    import xml.etree.ElementTree as ET

    # Setup temp dirs and file
    src_dir = tempfile.mkdtemp()
    tgt_dir = tempfile.mkdtemp()
    src_file = os.path.join(src_dir, "testfile.txt")
    with open(src_file, "wb") as f:
        f.write(b"biobeamer integration test")
    # Patch configs/BioBeamerTest.xml for testhost_integration
    xml_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../configs/BioBeamerTest.xml")
    )
    with open(xml_path, "r") as f:
        original_xml = f.read()
    tree = ET.parse(xml_path)
    root = tree.getroot()
    for host in root.findall("host"):
        if host.attrib.get("name") == "testhost_integration":
            host.set("source_path", src_dir)
            host.set("target_path", tgt_dir)
            host.set("min_time_diff", "0")
            host.set("min_size", "0")
            host.set("pattern", ".*")
            host.set("tool", tool)
            # Use a dedicated log file for the test to avoid clutter, but always in ./log
            host.set(
                "copied_files_log",
                os.path.join("./log", f"copied_files_test_integration_{tool}.txt"),
            )
    tree.write(xml_path)
    # Prepare sys.argv with new style args
    sys.argv = [
        "biobeamer2.py",
        f"--config-url=file://{os.path.dirname(xml_path)}",
        f"--xml={os.path.basename(xml_path)}",
        f"--hostname=testhost_integration",
    ]
    # Patch time.sleep to skip delay
    original_sleep = time.sleep
    time.sleep = lambda x: None
    # Patch setup_logger to use a fixed log file in the ./log dir
    orig_setup_logger = biobeamer2.setup_logger

    def test_setup_logger(
        config_file_name, now, log_file_path=None, robocopy_log_file_path=None
    ):
        log_file = os.path.join("./log", f"biobeamer_test_{tool}.log")
        robocopy_log_file = os.path.join("./log", f"tool_test_{tool}.log")
        return orig_setup_logger(config_file_name, now, log_file, robocopy_log_file)

    biobeamer2.setup_logger = test_setup_logger
    try:
        # Run main
        biobeamer2.main()
        # Assert file copied
        copied_file = os.path.join(tgt_dir, "testfile.txt")
        assert os.path.exists(copied_file)
        with open(copied_file, "rb") as f:
            assert f.read() == b"biobeamer integration test"
    finally:
        # Restore original XML and logger
        with open(xml_path, "w") as f:
            f.write(original_xml)
        biobeamer2.setup_logger = orig_setup_logger
        shutil.rmtree(src_dir)
        shutil.rmtree(tgt_dir)
        time.sleep = original_sleep
