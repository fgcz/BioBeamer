import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest.mock import patch, MagicMock

from src import biobeamer2


class TestBioBeamer2Main(unittest.TestCase):
    @patch('src.biobeamer2.MyLog.MyLog')
    @patch('src.biobeamer2.BioBeamerParser')
    @patch('src.biobeamer2.Drive')
    @patch('src.biobeamer2.copy_files')
    @patch('src.biobeamer2.socket.gethostname', return_value='testhost')
    @patch('src.biobeamer2.time.sleep')
    def test_main(self, mock_sleep, mock_gethostname, mock_copy_files, mock_Drive, mock_BioBeamerParser, mock_MyLog):
        test_args = ['biobeamer2.py', 'file:///tmp/configs', 'test_password', 'TestConfig.xml']
        with patch.object(sys, 'argv', test_args):
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
            }
            mock_parser.regex = MagicMock()
            mock_BioBeamerParser.BioBeamerParser.return_value = mock_parser

            biobeamer2.main()
            self.assertTrue(mock_MyLog.called)
            self.assertTrue(mock_BioBeamerParser.BioBeamerParser.called)
            self.assertTrue(mock_copy_files.called)

    def test_bio_beamer_main_integration(self):
        import xml.etree.ElementTree as ET
        # Setup temp dirs and file
        src_dir = tempfile.mkdtemp()
        tgt_dir = tempfile.mkdtemp()
        src_file = os.path.join(src_dir, "testfile.txt")
        with open(src_file, "wb") as f:
            f.write(b"biobeamer integration test")
        # Patch configs/BioBeamerTest.xml for testhost_integration
        xml_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../configs/BioBeamerTest.xml'))
        with open(xml_path, "r") as f:
            original_xml = f.read()
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for host in root.findall("host"):
            if host.attrib.get("name") == "testhost_integration":
                host.set("source_path", src_dir)
                host.set("target_path", tgt_dir)
        tree.write(xml_path)
        # Prepare sys.argv
        sys.argv = [
            "biobeamer2.py",
            f"file://{os.path.dirname(xml_path)}",
            None,
            os.path.basename(xml_path),
            "testhost_integration"
        ]
        # Patch time.sleep to skip delay
        original_sleep = time.sleep
        time.sleep = lambda x: None
        try:
            # Run main
            biobeamer2.main()
            # Assert file copied
            copied_file = os.path.join(tgt_dir, "testfile.txt")
            self.assertTrue(os.path.exists(copied_file))
            with open(copied_file, "rb") as f:
                self.assertEqual(f.read(), b"biobeamer integration test")
        finally:
            # Restore original XML
            with open(xml_path, "w") as f:
                f.write(original_xml)
            shutil.rmtree(src_dir)
            shutil.rmtree(tgt_dir)
            time.sleep = original_sleep


if __name__ == '__main__':
    unittest.main()
