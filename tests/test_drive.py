import unittest
from src.MyLog import MyLog
from src.mapNetworks import Drive


class TestDrive(unittest.TestCase):
    """
    """
    def test_map_drive(self):
        logger = MyLog()
        logger.add_file()
        drive = Drive(logger.logger)
        drive.mapDrive()
        drive.unmapDrive()

    def setUp(self):
        pass

    def tearDown(self):
        pass