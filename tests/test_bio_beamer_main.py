import os
import shutil
import sys
import tempfile
import time
from unittest.mock import patch, MagicMock

import importlib.resources
import pytest
from biobeamer import cli
from biobeamer.networks import Drive


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
    with patch("biobeamer.logger.MyLog") as mock_MyLog, patch(
        "biobeamer.cli.BioBeamerParser"
    ) as mock_BioBeamerParser, patch(
        "biobeamer.networks.Drive"
    ) as mock_Drive, patch(
        "biobeamer.cli.copy_files"
    ) as mock_copy_files, patch(
        "biobeamer.cli.socket.gethostname", return_value="testhost"
    ), patch(
        "biobeamer.cli.time.sleep"
    ) as mock_sleep:
        test_args = [
            "biobeamer.py",
            "--password",
            "test_password",
            "--xml",
            "dummy.xml",  # Use a dummy value, parser is mocked
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
            mock_BioBeamerParser.return_value = mock_parser

            # Patch time.sleep to skip delay
            original_sleep = time.time
            time.time = lambda: 0
            # Patch setup_logger to use a fixed log file in the ./log dir
            orig_setup_logger = cli.setup_logger

            def test_setup_logger(now, log_file_path=None, log_dir=None):
                log_file = os.path.join("./log", f"biobeamer_test.log")
                return orig_setup_logger(now, log_file_path=log_file)

            cli.setup_logger = test_setup_logger
            try:
                cli.main()
                assert mock_MyLog.called
                assert mock_BioBeamerParser.called
                assert mock_copy_files.called
            finally:
                cli.setup_logger = orig_setup_logger
                time.time = original_sleep


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
    # Patch BioBeamerTest.xml for testhost_integration
    with importlib.resources.path(
        "biobeamer.configs", "BioBeamerTest.xml"
    ) as xml_path:
        xml_path = str(xml_path)
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
            "biobeamer.py",
            f"--xml={xml_path}",
            f"--hostname=testhost_integration",
        ]
        # Patch time.sleep to skip delay
        original_sleep = time.sleep
        time.sleep = lambda x: None
        # Patch setup_logger to use a fixed log file in the ./log dir
        orig_setup_logger = cli.setup_logger

        def test_setup_logger(now, log_file_path=None, log_dir=None):
            log_file = os.path.join("./log", f"biobeamer_test_{tool}.log")
            # Call the original with the new signature
            return orig_setup_logger(now, log_file_path=log_file)

        cli.setup_logger = test_setup_logger
        try:
            # Run main
            cli.main()
            # Assert file copied
            copied_file = os.path.join(tgt_dir, "testfile.txt")
            assert os.path.exists(copied_file)
            with open(copied_file, "rb") as f:
                assert f.read() == b"biobeamer integration test"
        finally:
            # Restore original XML and logger
            with open(xml_path, "w") as f:
                f.write(original_xml)
            cli.setup_logger = orig_setup_logger
            shutil.rmtree(src_dir)
            shutil.rmtree(tgt_dir)
            time.sleep = original_sleep
