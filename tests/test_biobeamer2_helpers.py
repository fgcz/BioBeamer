import sys
import os
import logging
import types
import pytest
from unittest import mock

# Import the functions to test
from src import biobeamer2


def test_parse_args_default(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["biobeamer2.py"])
    config_url, xml, password, hostname, xsd_path = biobeamer2.parse_args()
    assert config_url.startswith("file://")
    assert xml == "BioBeamer2.xml"
    assert password is None
    assert hostname
    assert xsd_path.endswith("BioBeamer2.xsd")


def test_parse_args_with_args(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "biobeamer2.py",
            "--config-url",
            "url",
            "--password",
            "pw",
            "--xml",
            "xmlfile",
            "--hostname",
            "host",
            "--xsd",
            "xsdfile",
        ],
    )
    config_url, xml, password, hostname, xsd_path = biobeamer2.parse_args()
    assert config_url == "url"
    assert password == "pw"
    assert xml == "xmlfile"
    assert hostname == "host"
    assert xsd_path == "xsdfile"


def test_get_config_file_name():
    assert (
        biobeamer2.get_config_file_name("file:///path/to/BioBeamer2.xml")
        == "BioBeamer2"
    )
    assert biobeamer2.get_config_file_name("BioBeamer2.xml") == "BioBeamer2"


def test_setup_logger(tmp_path):
    config_file_name = "TestConfig_test_setup_logger"
    now = "20250101_120000"
    logger, biobeamerlog = biobeamer2.setup_logger(config_file_name, now)
    assert hasattr(logger, "add_file")
    assert biobeamerlog.endswith(f"robocopy_{config_file_name}.log")


def test_setup_biobeamer_parser(monkeypatch):
    class DummyParser:
        def __init__(self, xsd, xml, hostname, logger):
            self.xsd = xsd
            self.xml = xml
            self.hostname = hostname
            self.logger = logger

    monkeypatch.setattr(biobeamer2.BioBeamerParser, "BioBeamerParser", DummyParser)
    parser = biobeamer2.setup_biobeamer_parser("url", "xml", "host", "logger")
    assert parser.xsd == "url/BioBeamer2.xsd"
    assert parser.xml == "url/xml"
    assert parser.hostname == "host"
    assert parser.logger == "logger"


def test_copy_files_with_tool_robocopy(monkeypatch):
    # Prepare mock functions and data
    source_results = {"/src/file1.txt": "/dst/file1.txt"}
    logger = mock.Mock()
    logfile = "dummy.log"
    mov = False
    tool = "robocopy"
    simulate = False
    # Patch copy_with_robocopy
    monkeypatch.setattr(
        biobeamer2, "copy_with_robocopy", lambda src, dst, **kwargs: True
    )
    # Patch copy_with_scp to ensure it's not called
    monkeypatch.setattr(biobeamer2, "copy_with_scp", lambda *a, **k: False)
    result = biobeamer2.copy_files_with_tool(
        source_results, mov, logger, logfile, tool, simulate
    )
    assert result == [True]


def test_copy_files_with_tool_scp(monkeypatch):
    source_results = {"/src/file2.txt": "/dst/file2.txt"}
    logger = mock.Mock()
    logfile = "dummy.log"
    mov = False
    tool = "scp"
    simulate = False
    monkeypatch.setattr(biobeamer2, "copy_with_robocopy", lambda *a, **k: False)
    monkeypatch.setattr(
        biobeamer2, "copy_with_scp", lambda src, dst, **kwargs: "copied"
    )
    result = biobeamer2.copy_files_with_tool(
        source_results, mov, logger, logfile, tool, simulate
    )
    assert result == ["copied"]


def test_copy_files_with_tool_invalid_tool(monkeypatch):
    source_results = {"/src/file3.txt": "/dst/file3.txt"}
    logger = mock.Mock()
    logfile = "dummy.log"
    mov = False
    tool = "rsync"  # unsupported tool
    simulate = False
    # Patch copy_with_robocopy and copy_with_scp to ensure they're not called
    monkeypatch.setattr(biobeamer2, "copy_with_robocopy", lambda *a, **k: False)
    monkeypatch.setattr(biobeamer2, "copy_with_scp", lambda *a, **k: False)
    with pytest.raises(Exception):
        biobeamer2.copy_files_with_tool(
            source_results, mov, logger, logfile, tool, simulate
        )


def test_copy_files(monkeypatch):
    DummyParser = mock.Mock()
    DummyParser.parameters = {
        "source_path": "/mock/source",
        "copied_files_log": "/mock/copied.log",
        "simulate_delete": False,
        "robocopy_mov": False,
        "func_target_mapping": "",
        "target_path": "/mock/target",
        "simulate_copy": False,
        "max_time_delete": 1,
    }
    DummyParser.regex = None
    logger = mock.Mock()
    tool = "robocopy"
    biobeamerlog = "dummy.log"
    # Patch os.path.exists
    monkeypatch.setattr(os.path, "exists", lambda p: True)
    # Patch get_all_files
    monkeypatch.setattr(
        biobeamer2, "get_all_files", lambda p, logger=None: ["a.txt", "b.txt"]
    )
    # Patch read_copied_files
    monkeypatch.setattr(biobeamer2, "read_copied_files", lambda *a, **k: ["b.txt"])
    # Patch filter_input_filelist
    monkeypatch.setattr(
        biobeamer2,
        "filter_input_filelist",
        lambda files, regex, params, logger=None: files,
    )
    # Patch make_destination_files
    monkeypatch.setattr(
        biobeamer2,
        "make_destination_files",
        lambda files, src, dst: {f: f"{dst}/{f}" for f in files},
    )
    # Patch compare_files_destination
    monkeypatch.setattr(
        biobeamer2,
        "compare_files_destination",
        lambda mapping: {"copied": {}, "not_copied": mapping},
    )
    # Patch copy_files_with_tool
    monkeypatch.setattr(biobeamer2, "copy_files_with_tool", lambda **kwargs: ["a.txt"])
    # Patch log_copied_files and remove_old_copied
    monkeypatch.setattr(biobeamer2, "log_copied_files", lambda *a, **k: None)
    monkeypatch.setattr(biobeamer2, "remove_old_copied", lambda *a, **k: None)
    # Patch mapping_functions
    monkeypatch.setattr(biobeamer2, "mapping_functions", mock.Mock())
    # Call function
    biobeamer2.copy_files(DummyParser, logger, tool, biobeamerlog)
    # If no exception, test passes
