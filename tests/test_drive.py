import os
import pytest
from biobeamer2.MyLog import MyLog
from biobeamer2.mapNetworks import Drive


@pytest.fixture
def logger():
    log_path = "tests/log/biobeamer_drive_test.log"
    if os.path.exists(log_path):
        os.remove(log_path)
    logger = MyLog()
    logger.add_file(filename="log/biobeamer_drive_test.log")
    return logger


def test_map_drive(logger):
    drive = Drive(logger.logger)
    drive.mapDrive()
    drive.unmapDrive()
