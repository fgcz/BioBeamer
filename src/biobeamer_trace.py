import logging
import socket
import time
from datetime import datetime
from pathlib import Path
import re

import BioBeamerParser
import MyLog


def run_biobeamer_trace(xml_path: str, san_password: str, xsd_path: str = None, hostname=None):
    """
    Run the BioBeamer trace with the given XML configuration and SAN password.

    :param xml_path: Path to the XML configuration file.
    :param san_password: Password for the SAN.
    :param xsd_path: Optional path to the XSD schema file.
    :param hostname: Optional hostname for logging.
    """
    hostname = hostname or socket.gethostname()
    logger = MyLog.MyLog()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    xml_path_abs = Path(xml_path).resolve()
    xml_path_url = f"file://{xml_path_abs}"
    xml_name = xml_path_abs.name
    log_file = Path(f"./log/{xml_name}_{now}.log").resolve()
    biobeamer_log = Path(f"./log/robocopy_{xml_name}.log").resolve()
    logger.add_file(file=log_file, level=logging.DEBUG)


    logger.logger.info("Starting BioBeamer trace")
    logger.logger.info(f"Retrieving XML configuration from: {xml_path_url} for hostname: {hostname}")

    biobeamer_parser = BioBeamerParser.BioBeamerParser(
        xml=xml_path_url,
        xsd=xsd_path,
        hostname=hostname,
        logger=logger.logger
    )

    logger.add_syshandler(address=(biobeamer_parser["syshandler_adress"], biobeamer_parser["syshandler_port"]))
    logger.set_log_level(level=logging.DEBUG)
    logger.logger.info(f"Starting Remote Logging from host {hostname}")

    time.sleep(biobeamer_parser.parameters["time_out"])
    biobeamer_parser.log_para()

    if re.match(r"^\\", biobeamer_parser.parameters["target_path"]):


