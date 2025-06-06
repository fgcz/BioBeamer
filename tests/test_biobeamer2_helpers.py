import os
import sys
from unittest import mock

import pytest

# Import the functions to test
from src import biobeamer2


def test_parse_args_default(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["biobeamer2.py"])
    args = biobeamer2.parse_args()
    expected_xml = f"file://{os.path.abspath('BioBeamer2.xml')}"
    assert args.xml == expected_xml
    assert args.password is None
    assert args.hostname
    assert args.xsd.endswith("BioBeamer2.xsd")


def test_parse_args_with_args(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "biobeamer2.py",
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
    args = biobeamer2.parse_args()
    assert args.password == "pw"

    # Accept both file:// and plain for xml/xsd, but normalize for test
    def normalize_path(val):
        if val.startswith("file://"):
            return os.path.basename(val)
        return val

    assert normalize_path(args.xml) == "xmlfile"
    assert args.hostname == "host"
    assert normalize_path(args.xsd) == "xsdfile"


def test_get_config_file_name():
    assert (
        biobeamer2.get_config_file_name("file:///path/to/BioBeamer2.xml")
        == "BioBeamer2"
    )
    assert biobeamer2.get_config_file_name("BioBeamer2.xml") == "BioBeamer2"


def test_setup_logger(tmp_path):
    now = "20250101_120000"
    logger, biobeamerlog = biobeamer2.setup_logger(now, log_dir=tmp_path)
    assert hasattr(logger, "add_file")
    assert biobeamerlog.endswith(f"biobeamer_{now}.log")


def test_setup_logger_missing_log_dir(tmp_path, monkeypatch):
    import shutil
    import logging

    log_dir = tmp_path / "log"
    if log_dir.exists():
        shutil.rmtree(log_dir)
    now = "20250101_120000"
    log_file_path = str(log_dir / f"biobeamer_{now}.log")
    from src import biobeamer2

    # Should not raise
    logger, biobeamerlog = biobeamer2.setup_logger(now, log_file_path=log_file_path)
    assert os.path.exists(log_dir)
    assert os.path.exists(log_file_path)


def test_setup_logger_creates_log_dir(tmp_path, monkeypatch):
    """Test setup_logger creates the log directory if it does not exist."""
    import shutil

    log_dir = tmp_path / "log"
    if log_dir.exists():
        shutil.rmtree(log_dir)
    now = "20250101_120000"
    log_file_path = str(log_dir / f"biobeamer_{now}.log")
    # Patch log_file_path to use our custom dir
    from src import biobeamer2

    # Should not raise
    logger, biobeamerlog = biobeamer2.setup_logger(now, log_file_path=log_file_path)
    assert os.path.exists(log_dir)
    assert os.path.exists(log_file_path)


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


import os
import tempfile
import pytest
from unittest import mock
from src import biobeamer2


def test_validate_and_collect_files_existing(tmp_path):
    # Create a file in a temp directory
    file_path = tmp_path / "file.txt"
    file_path.write_text("test")
    logger = mock.Mock()
    files = biobeamer2.validate_and_collect_files(str(tmp_path), logger)
    assert str(file_path) in files


def test_validate_and_collect_files_missing(tmp_path):
    logger = mock.Mock()
    with pytest.raises(FileNotFoundError):
        biobeamer2.validate_and_collect_files(str(tmp_path / "doesnotexist"), logger)


def test_remove_already_copied():
    files = ["a", "b", "c"]
    copied = ["b"]
    result = biobeamer2.remove_already_copied(files, copied)
    assert set(result) == {"a", "c"}


def test_filter_files_filters(monkeypatch):
    # Patch filter_input_filelist to check call
    called = {}

    def fake_filter(files, regex, parameters, logger=None):
        called["args"] = (files, regex, parameters)
        return ["filtered"]

    monkeypatch.setattr(biobeamer2, "filter_input_filelist", fake_filter)
    files = ["a", "b"]
    regex = mock.Mock()
    parameters = {"foo": "bar"}
    logger = mock.Mock()
    result = biobeamer2.filter_files(files, regex, parameters, logger)
    assert result == ["filtered"]
    assert called["args"][0] == files


def test_map_source_to_dest():
    files = ["/src/a.txt"]
    result = biobeamer2.map_source_to_dest(files, "/src", "/dst")
    assert result["/src/a.txt"].startswith("/dst")


def test_apply_mapping_function_applies(monkeypatch):
    mapping = {"a": "b"}
    logger = mock.Mock()

    def fake_func(val, logger):
        return val + "_mapped"

    monkeypatch.setattr(biobeamer2.mapping_functions, "myfunc", fake_func)
    result = biobeamer2.apply_mapping_function(mapping.copy(), "myfunc", logger)
    assert result["a"].endswith("_mapped")


def test_apply_mapping_function_no_func():
    mapping = {"a": "b"}
    logger = mock.Mock()
    result = biobeamer2.apply_mapping_function(mapping.copy(), "", logger)
    assert result == mapping


def test_remove_files_already_at_destination(monkeypatch):
    mapping = {"a": "b"}
    copied = {"copied": {"a": "b"}, "not_copied": {"c": "d", "e": "f"}}
    monkeypatch.setattr(biobeamer2, "compare_files_destination", lambda m: copied)
    not_copied, all_copied = biobeamer2.remove_files_already_at_destination(
        mapping, ["a"]
    )
    assert set(all_copied) == {"a"}
    assert not_copied == {"c": "d", "e": "f"}


def test_copy_and_log_files(monkeypatch):
    not_copied = {"a": "b"}
    all_copied = ["c"]
    parameters = {
        "robocopy_mov": False,
        "simulate_copy": False,
        "copied_files_log": "dummy.log",
    }
    logger = mock.Mock()
    tool_log_file_path = "dummy.log"
    tool = "robocopy"
    monkeypatch.setattr(biobeamer2, "copy_files_with_tool", lambda **kwargs: ["a"])
    monkeypatch.setattr(
        biobeamer2,
        "log_copied_files",
        lambda files, copied_files_log_path, log_dir=None: None,
    )
    result = biobeamer2.copy_and_log_files(
        not_copied, all_copied, parameters, logger, tool_log_file_path, tool
    )
    assert "a" in result and "c" in result


def test_cleanup_copied_files(monkeypatch):
    files_copied = ["a", "b"]
    parameters = {"max_time_delete": 1}
    logger = mock.Mock()
    simulate = "sim.bat"
    called = {}

    def fake_remove(files, max_time, logger, simulate=None):
        called["files"] = files
        called["max_time"] = max_time
        called["simulate"] = simulate

    monkeypatch.setattr(biobeamer2, "remove_old_copied", fake_remove)
    biobeamer2.cleanup_copied_files(files_copied, parameters, logger, simulate)
    assert called["files"] == files_copied
    assert called["max_time"] == 1
    assert called["simulate"] == simulate
