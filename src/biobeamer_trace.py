import logging
import re
import socket
import time
from datetime import datetime
from pathlib import Path

import paramiko
from scp import SCPClient

import BioBeamerParser
import MyLog
from src.biobeamer2 import copy_files
from src.mapNetworks import Drive


def run_biobeamer_trace(xml_path: str, san_password: str, tool: str, xsd_path: str = None, hostname=None):
    """
    Run the BioBeamer trace with the given XML configuration and SAN password.

    :param tool: Tool to use for copying files (e.g., 'scp', 'robocopy').
    :param xml_path: Path to the XML configuration file.
    :param san_password: Password for the SAN.
    :param xsd_path: Optional path to the XSD schema file.
    :param hostname: Optional hostname for logging.
    """

    if tool not in ["scp", "robocopy"]:
        raise ValueError(f"Unsupported tool: {tool}. Supported tools are 'scp' and 'robocopy'.")
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

    if tool == "robocopy":
        robocopy_start(biobeamer_parser, logger, biobeamer_log, san_password)
    elif tool == "scp":
        scp_start(biobeamer_parser, logger, biobeamer_log)


def robocopy_start(biobeamer_parser: BioBeamerParser, logger: MyLog.MyLog, biobeamer_log: Path, password: str):
    drive = 0
    if re.match(r"^\\", biobeamer_parser.parameters["target_path"]):
        drive = Drive(logger.logger, password=password, networkPath=biobeamer_parser.parameters["target_path"])
        if not drive.mapDrive() == 0:
            logger.logger.error(f"Can't map network drive {biobeamer_parser.parameters['target_path']}")
            exit(0)
    copy_files(biobeamer_parser, logger, biobeamer_parser.parameters["target_path"])


def scp_start(biobeamer_parser: BioBeamerParser, logger: MyLog.MyLog, biobeamer_log: Path):
    """
    Copy files using SCP based on the BioBeamer parser configuration.

    :param biobeamer_parser: The BioBeamerParser instance with configuration.
    :param logger: The MyLog instance for logging.
    :param biobeamer_log: Path to the log file for SCP operations.
    """
    source_path = biobeamer_parser.parameters["source_path"]
    target_path = biobeamer_parser.parameters["target_path"]
    ssh_host = biobeamer_parser.parameters["syshandler_adress"]
    ssh_port = biobeamer_parser.parameters.get("syshandler_port", 22)
    ssh_user = biobeamer_parser.parameters.get("ssh_user", "your_username")
    ssh_password = biobeamer_parser.parameters.get("ssh_password", "your_password")

    try:
        # Establish SSH connection
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ssh_host, port=ssh_port, username=ssh_user, password=ssh_password)

        # Use SCP to copy files
        with SCPClient(ssh.get_transport()) as scp:
            scp.put(source_path, target_path, recursive=True)
            logger.logger.info(f"Copied files from {source_path} to {target_path} over SSH")

    except Exception as e:
        logger.logger.error(f"Error during SCP transfer: {e}")
    finally:
        ssh.close()
