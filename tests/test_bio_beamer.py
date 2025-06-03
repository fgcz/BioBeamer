import unittest
from unittest.mock import patch, MagicMock
import sys

from src import biobeamer2

class TestBioBeamer2Main(unittest.TestCase):
    @patch('src.biobeamer2.MyLog.MyLog')
    @patch('src.biobeamer2.BioBeamerParser')
    @patch('src.biobeamer2.Drive')
    @patch('src.biobeamer2.robocopy')
    @patch('src.biobeamer2.socket.gethostname', return_value='testhost')
    @patch('src.biobeamer2.time.sleep')
    def test_main(self, mock_sleep, mock_gethostname, mock_robocopy, mock_Drive, mock_BioBeamerParser, mock_MyLog):
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
            self.assertTrue(mock_robocopy.called)

if __name__ == '__main__':
    unittest.main()