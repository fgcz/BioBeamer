# This should go into the robocopy because otherwise it might conflict with the Checker class.
import argparse
import filecmp
import importlib.resources
import logging.handlers
import os
import re
import shlex
import socket
import time
from datetime import datetime
from pathlib import Path
import subprocess
from subprocess import CalledProcessError, Popen

from biobeamer.parser import BioBeamerParser
from biobeamer.networks import Drive
from biobeamer.sftpparamiko import copy_with_sftp_sub, noop_subprocess
from . import logger as MyLog, mapping


def get_all_files(source_path, logger):
    """
    :param source_path:
    :param logger:
    :return: return list of files in directory
    """
    all_files = []
    for root, dirs, files in os.walk(
        source_path,
        topdown=False,
        followlinks=False,
        onerror=lambda e: logger.error("os.walk: {0}\n".format(e)),
    ):
        # BioBeamer filters
        files_to_copy = map(lambda f: os.path.join(root, f), files)
        all_files += files_to_copy

    return all_files


def robocopy_get_basename_dict(files_to_copy):
    basename_dict = {}
    """
    here we have a dictionary containing all files having the same basename
    This is needed if the instrument aquires 2 files updating only 1 and we should not move the 1st.
    """

    for f in files_to_copy:
        file_basename = os.path.splitext(f)
        file_basename = file_basename[0]
        if not file_basename in basename_dict:
            basename_dict[file_basename] = []
        basename_dict[file_basename].append(f)
    return basename_dict


def robocopy_filter_sublist(files, regex, parameters, logger):
    """
    expecting a dictionary where the basename is the key
    returns True iff all files (values) fullfill the filter criteria
    """
    files_to_copy = []
    files.sort()
    for f in files:
        ok = True
        false_str = []
        if not regex.match(f):
            ok = False
            false_str.append("regex")
        if not time.time() - os.path.getctime(f) > parameters["min_time_diff"]:
            ok = False
            false_str.append(
                "min_time_diff = {}; observed = {}".format(
                    parameters["min_time_diff"], time.time() - os.path.getmtime(f)
                )
            )
        if not time.time() - os.path.getmtime(f) < parameters["max_time_diff"]:
            ok = False
            false_str.append(
                "max_time_diff = {}; observed = {}".format(
                    parameters["max_time_diff"], time.time() - os.path.getmtime(f)
                )
            )
        if not os.path.getsize(f) >= parameters["min_size"]:
            ok = False
            false_str.append(
                "min_size = {}; actual_size = {}".format(
                    parameters["min_size"], os.path.getsize(f)
                )
            )
        if ok:
            files_to_copy.append(f)

        if len(false_str) > 0:
            false_str = " & ".join(false_str)
            logger.debug(
                "not copying {file} for {reasons}".format(file=f, reasons=false_str)
            )

    if len(files_to_copy) < len(files):
        if len(files_to_copy) > 0:
            files_rejected = ", ".join(files)
            logger.debug(
                "not copying because of basename dictionary violation: {files}".format(
                    files=files_rejected
                )
            )
        return False
    return True


def robocopy_filter_sublist_deprec(f, regex, parameters, logger):
    files_to_copy = filter(regex.match, f)
    files_to_copy = filter(
        lambda f: time.time() - os.path.getmtime(f) > parameters["min_time_diff"],
        files_to_copy,
    )
    files_to_copy = filter(
        lambda f: time.time() - os.path.getmtime(f) < parameters["max_time_diff"],
        files_to_copy,
    )
    files_to_copy = filter(
        lambda f: os.path.getsize(f) > parameters["min_size"], files_to_copy
    )
    files_to_copy = list(files_to_copy)
    if len(files_to_copy) < len(f):
        return False
    return True


def filter_input_filelist(files_to_copy, regex, parameters, logger):
    files_to_copy.sort()
    basename_dict = robocopy_get_basename_dict(files_to_copy)
    files = basename_dict.values()
    files = filter(
        lambda fl: robocopy_filter_sublist(
            fl, regex=regex, parameters=parameters, logger=logger
        ),
        files,
    )
    files = [item for sublist in files for item in sublist]
    return files


def log_files_stat(files_to_copy, parameters, logger):
    """
    :param files_to_copy: list with files to copy
    :param logger: a logger
    :return: nil
    """
    for file_to_copy in files_to_copy:
        logger.info(
            "consider: '{name}' filetime={time}; filesize={size}, maxtime={maxtime}, mintime={mintime}, minsize={minsize}".format(
                name=file_to_copy,
                time=time.time() - os.path.getmtime(file_to_copy),
                size=os.path.getsize(file_to_copy),
                mintime=parameters["min_time_diff"],
                maxtime=parameters["max_time_diff"],
                minsize=parameters["min_size"],
            )
        )


def copy_with_robocopy(
    file_to_copy, target_path, logger, tool_log_file, mov=False, simulate_copy=False
):
    """
    wrapper function to
    compose robocopy.exe command line and call it out of python

    robocopy options:
    /E Copies subdirectories. Note that this option includes empty directories.
    /Z Copies files in Restart mode.
    /MOVE Moves files and directories, and deletes them from the source after they are copied.

    see also:
        https://technet.microsoft.com/en-us/library/cc733145.aspx
        :rtype: object
    """
    file_copied = None

    if not mov:
        robocopy_args = "/E /NP /R:0 /LOG+:{log}".format(log=tool_log_file)
    else:
        robocopy_args = "/E /NP /R:0 /MOV /LOG+:{log}".format(log=tool_log_file)

    cmd = [
        "robocopy.exe",
        robocopy_args,
        '"{}"'.format(os.path.dirname(file_to_copy)),
        '"{}"'.format(os.path.dirname(target_path)),
        '"{}"'.format(os.path.basename(file_to_copy)),
    ]

    if not simulate_copy:
        logger.info("Running Command: [{0}]".format(" ".join(cmd)))
        try:
            robocopy_process = Popen(" ".join(cmd), shell=True)
            return_code = robocopy_process.wait()
            logger.info("robocopy return code: '{0}'".format(return_code))
            if return_code > 7:
                logger.error("robocopy failed with return code > 7; treating as error.")
                robocopy_process.terminate()
                return None  # Signal failure
            else:
                file_copied = file_to_copy
            robocopy_process.terminate()

        except Exception as e:
            logger.error(
                "robocopy exception raised on files - from "
                + file_to_copy
                + " to "
                + target_path
                + f" ! Exception: {e}"
            )
            return None  # Signal failure
    else:
        logger.info("Simulating Command: [{0}]".format(" ".join(cmd)))
        
    return file_copied


def copy_with_scp(source, target, logger, tool_log_file, simulate_copy=False):
    """
    Executes an scp command to copy a file from source to target.
    :param tool_log_file: Log file path
    :param source: Source file path
    :param target: Target file path
    :param logger: Logger object
    :param simulate_copy: If True, only simulates the copy
    :return: The source file if copied successfully, else None
    """
    source = Path(source).as_posix()
    target = Path(target).as_posix()
    
    file_copied = None
    # Compose the scp command with verbose output
    if ":" in target:
        host_part, remote_path = target.split(":", 1)
        remote_dir = os.path.dirname(remote_path)
        mkdir_cmd = ["ssh", host_part, f"mkdir -p {remote_dir}"]
    else:
        # Local target - create directory locally
        local_dir = os.path.dirname(target)
        mkdir_cmd = ["mkdir", "-p", local_dir]
    cmd = ["scp", "-v", source, target]

    if not simulate_copy:
        logger.info(f"Running Command: [{shlex.join(mkdir_cmd)}]")
        logger.info(f"Running Command: [{shlex.join(cmd)}]")
        try:
            # Write a header to the log file to ensure it is touched
            with open(tool_log_file, "a") as logf:
                logf.write(
                    f"--- Running SCP command at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n"
                )
                logf.flush()
                subprocess.run(mkdir_cmd, check=True, stdout=logf, stderr=logf)
                subprocess.run(cmd, check=True, stdout=logf, stderr=logf)
                file_copied = source
            
        except CalledProcessError as e:
            file_copied = None
            logger.error(
                f"scp or ssh exception raised on files - from {source} to {target}! Exception: {e}",
                exc_info=True
            )
            
    else:
        logger.info(f"Simulating Command: [{shlex.join(mkdir_cmd)}]")
        logger.info(f"Simulating Command: [{shlex.join(cmd)}]")
        

    return file_copied


def copy_with_sftp(source: str, target: str, logger, tool_log_file: str, simulate_copy: bool = False):
    """
    Executes an sftp command to copy a file from source to target.
    :param tool_log_file: Log file path
    :param source: Source file path
    :param target: Target file path
    :param logger: Logger object
    :param simulate_copy: If True, only simulates the copy
    :return: The source file if copied successfully, else None
    """

    source = Path(source).as_posix()
    target = Path(target).as_posix()
    file_copied = None
    
    
    if not simulate_copy:
        try:
            # Write a header to the log file to ensure it is touched
            with open(tool_log_file, "a") as logf:
                logf.write(
                    f"--- Running SCP command at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n"
                )
                cmd_str = copy_with_sftp_sub(source, target, subprocess.run)
                file_copied = source
                logf.write(cmd_str)
                logf.flush()
                logger.info(f"Running Command: [{cmd_str}]")
        except CalledProcessError as e:
            file_copied = None
            logger.error(
                f"sftp exception raised on files - from {source} to {target}! Exception: {e}",
                exc_info=True
            )
            
    else:
        cmd_str = copy_with_sftp_sub(source, target, noop_subprocess)
        logger.info(f"Simulating Command: {cmd_str}")
    return file_copied

def copy_files_with_tool(
    source_results, mov, logger, tool_log_file, tool, simulate=False
):
    files_copied = []
    failed_files = []
    sources = list(source_results.keys())
    sources.sort()
    for source in sources:
        if tool == "robocopy":
            file_copied = copy_with_robocopy(
                source,
                source_results[source],
                logger=logger,
                mov=mov,
                tool_log_file=tool_log_file,
                simulate_copy=simulate,
            )
        elif tool == "scp":
            file_copied = copy_with_scp(
                source,
                source_results[source],
                logger=logger,
                tool_log_file=tool_log_file,
                simulate_copy=simulate,
            )
        elif tool == "sftp":
            file_copied = copy_with_sftp(
                source,
                source_results[source],
                logger=logger,
                tool_log_file=tool_log_file,
                simulate_copy=simulate)
            
        else:
            logger.error("Tool {0} not supported!".format(tool))
            raise NotImplementedError("Tool {0} not supported!".format(tool))
        if file_copied is not None:
            files_copied.append(file_copied)
        else:
            # Only treat as failed if not simulating
            if not simulate:
                failed_files.append(source)
    if failed_files and not simulate:
        logger.error(f"Failed to copy files: {failed_files}")
        import sys

        sys.exit(2)
    return files_copied


def make_destination_files(files_to_copy, source_path, target_path):
    """
    :param files_to_copy:
    :param source_path:
    :param target_path:
    :return:
    """
    res = {}
    # target_path = target_path.replace('\\\\', '\\\\?\\')
    for file_to_copy in files_to_copy:
        target_sub_path = os.path.relpath(file_to_copy, source_path)
        target_file = os.path.normpath("{0}/{1}".format(target_path, target_sub_path))
        res[file_to_copy] = target_file
    return res


def rename_destination(filemap, logger, mapping_function):
    """
    uses mapping function to rename file
    :param filemap:
    :param logger:
    :param mapping_function:
    :return:
    """
    for key, value in filemap.items():
        filemap[key] = mapping_function(value, logger)
    return filemap


def compare_files_destination(source_result_mapping, logger):
    """
    :param source_result_mapping:
    :return: map with fields "copied" and "not_copied"
    """
    copied = {}
    not_copied = {}
    for file_to_copy, target_file in source_result_mapping.items():
        # tmp = os.path.exists(target_file)
        if not target_file is None:
            print(target_file + "\n")
            if os.path.exists(target_file) and filecmp.cmp(file_to_copy, target_file):
                copied[file_to_copy] = target_file
                logger.debug(
                    "not copying {file} for {reasons}".format(file=file_to_copy, reasons=" already copied to : " + target_file)
                )
            else:
                not_copied[file_to_copy] = target_file
    return {"copied": copied, "not_copied": not_copied}


def log_copied_files(copied_files, copied_files_log_path, log_dir=None):
    if log_dir:
        # Always write to log_dir, using only the filename part
        copied_files_log_path = os.path.join(
            log_dir, os.path.basename(copied_files_log_path)
        )
    # Always create the log file, even if empty
    log_dir_path = os.path.dirname(os.path.abspath(copied_files_log_path))
    if log_dir_path and not os.path.exists(log_dir_path):
        os.makedirs(log_dir_path, exist_ok=True)
    with open(copied_files_log_path, "w") as file_log:
        for file in sorted(copied_files):
            file_log.write(file + "\n")


def read_copied_files(copied_files_log_path):
    if os.path.isfile(copied_files_log_path):
        with open(copied_files_log_path, "r") as file_log:
            copied_files = file_log.read().splitlines()
            return copied_files
    else:
        return []


def remove_old_copied(
    source_result_mapping,
    max_time_diff,
    logger,
    simulate=None,
):
    """
    removes old files which have been already copied
    :param source_result_mapping:
    :param max_time_diff:
    :param logger:
    :param simulate:
    :return:
    """
    if simulate:
        myfile = open(simulate, "w")
        simulate_mode = True
    else:
        simulate_mode = False
        myfile = False

    for file_to_copy in source_result_mapping:
        if os.path.isfile(file_to_copy):
            time_diff = time.time() - os.path.getmtime(file_to_copy)
            if time_diff > max_time_diff:
                if not myfile and not simulate:
                    logger.info(
                        "removing file : [rm {0}] since tf {1} > max_time {2}".format(
                            file_to_copy, time_diff, max_time_diff
                        )
                    )
                    os.remove(file_to_copy)
                else:
                    logger.info(
                        "Simulating command : [rm {0}] since tf {1} > max_time {2}".format(
                            file_to_copy, time_diff, max_time_diff
                        )
                    )
                    myfile.write("rm {f2c}\n".format(f2c=file_to_copy))

    if simulate_mode and myfile:
        myfile.close()


def compare_copied_with_log(not_copied, files_copied_old):
    new_not_copied = {}
    for key, value in not_copied.items():
        if key not in set(files_copied_old):
            new_not_copied[key] = value
    return new_not_copied


def validate_and_collect_files(source_path, logger):
    if os.path.exists(source_path):
        return get_all_files(source_path, logger=logger)
    else:
        error = f"source path: {source_path} does not exist!"
        logger.error(error)
        raise FileNotFoundError(error)


def remove_already_copied(files, copied_log):
    return list(set(files) - set(copied_log))


def filter_files(files, regex, parameters, logger):
    return filter_input_filelist(files, regex, parameters, logger=logger)


def map_source_to_dest(files, source_path, target_path):
    return make_destination_files(files, source_path, target_path)


def apply_mapping_function(mapping_dict, func_name, logger):
    if func_name:
        logger.info(f"trying to apply mapping function : {func_name}.")
        method_to_call = getattr(mapping, func_name)
        return rename_destination(mapping_dict, logger, mapping_function=method_to_call)
    return mapping_dict


def remove_files_already_at_destination(mapping, copied_log, logger):
    copied = compare_files_destination(mapping, logger)
    all_copied = list(copied["copied"].keys()) + copied_log
    all_copied = set(all_copied)
    not_copied = copied["not_copied"]
    not_copied_keys = not_copied.keys() - set(all_copied)
    return dict((k, not_copied[k]) for k in not_copied_keys), all_copied


def copy_and_log_files(
    not_copied, all_copied, parameters, logger, tool_log_file_path, tool
):
    files_copied = copy_files_with_tool(
        source_results=not_copied,
        mov=parameters["robocopy_mov"],
        logger=logger,
        tool_log_file=tool_log_file_path,
        tool=tool,
        simulate=parameters["simulate_copy"],
    )
    files_copied = set(list(all_copied) + files_copied)
    # Use log_dir if present in parameters
    log_dir = parameters.get("log_dir", None)
    log_copied_files(
        list(files_copied),
        copied_files_log_path=parameters["copied_files_log"],
        log_dir=log_dir,
    )
    return files_copied


def cleanup_copied_files(files_copied, parameters, logger, simulate):
    remove_old_copied(
        files_copied, parameters["max_time_delete"], logger, simulate=simulate
    )


def copy_files(bio_beamer_parser, logger, tool, tool_log_file_path):
    """
    Orchestrates the process of copying files from a source to a target directory.
    Steps:
    1. Validate source path and collect files.
    2. Remove already copied files (from log).
    3. Filter files by regex and parameters.
    4. Map source files to destination paths.
    5. Optionally apply a mapping function to destination names.
    6. Remove files already present at destination.
    7. Copy remaining files and log results.
    8. Remove old copied files if needed.
    """
    parameters = bio_beamer_parser.parameters
    regex = bio_beamer_parser.regex

    files2copy = validate_and_collect_files(parameters["source_path"], logger)
    files_copied_log = read_copied_files(
        copied_files_log_path=parameters["copied_files_log"]
    )
    files2copy = remove_already_copied(files2copy, files_copied_log)
    files_filtered = filter_files(files2copy, regex, parameters, logger)
    simulate = None
    if parameters["simulate_delete"]:
        log_dir = parameters.get("log_dir", "./log")
        os.makedirs(log_dir, exist_ok=True)
        simulate = os.path.join(log_dir, "files2delete.bat")

    if len(files_filtered) != 0:
        source_result_mapping = map_source_to_dest(
            files_filtered, parameters["source_path"], parameters["target_path"]
        )
        source_result_mapping = apply_mapping_function(
            source_result_mapping, parameters["func_target_mapping"], logger
        )
        not_copied, all_copied = remove_files_already_at_destination(
            source_result_mapping, files_copied_log, logger
        )
        files_copied = copy_and_log_files(
            not_copied, all_copied, parameters, logger, tool_log_file_path, tool
        )
        cleanup_copied_files(files_copied, parameters, logger, simulate)
    else:
        # Always create the copied files log, even if no files are copied
        log_dir = parameters.get("log_dir", None)
        log_copied_files(
            list(files_copied_log),
            copied_files_log_path=parameters["copied_files_log"],
            log_dir=log_dir,
        )
        cleanup_copied_files(files_copied_log, parameters, logger, simulate)


def path_to_url(path: str) -> str:
    if (
        path.startswith("file://")
        or path.startswith("http://")
        or path.startswith("https://")
    ):
        return path
    return Path(path).absolute().as_uri()


def resolve_xsd_path():
    # Always use the package's XSD file as a file URI
    import pathlib

    # Use importlib.resources.files for modern resource access
    xsd_file = importlib.resources.files("biobeamer.configs") / "BioBeamer2.xsd"
    with importlib.resources.as_file(xsd_file) as xsd_path:
        return pathlib.Path(xsd_path).absolute().as_uri()


def parse_args():
    parser = argparse.ArgumentParser(description="BioBeamer2 command line arguments")
    parser.add_argument(
        "--xml",
        "-x",
        required=True,
        help="BioBeamer XML file (required)",
    )
    parser.add_argument(
        "--password",
        "-p",
        default=None,
        help="Password for network drive (default: None)",
    )
    parser.add_argument(
        "--hostname",
        "-n",
        default=socket.gethostname(),
        help="Hostname (default: current machine hostname)",
    )
    parser.add_argument(
        "--log_dir",
        default="./log",
        help="Directory for all logs (default: ./log)",
    )
    args = parser.parse_args()
    # Convert xml to URL if needed
    args.xml = path_to_url(args.xml)
    return args


def setup_logger(now, log_file_path=None, log_dir=None):
    import os

    if log_dir is not None:
        os.makedirs(log_dir, exist_ok=True)
        biobeamer_log_file_path = os.path.join(log_dir, f"biobeamer_{now}.log")
    else:
        if log_file_path is None:
            biobeamer_log_file_path = f"./log/biobeamer_{now}.log"
        else:
            biobeamer_log_file_path = log_file_path
        log_dir = os.path.dirname(biobeamer_log_file_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
    logger = MyLog.MyLog()
    logger.add_file(filename=biobeamer_log_file_path, level=logging.DEBUG)
    logger.set_log_level(logging.DEBUG)  # Ensure logger level allows INFO/DEBUG
    return logger, biobeamer_log_file_path


def get_tool_log_file(log_dir, tool_name="robocopy", now=None):
    import os

    suffix = f"_{now}" if now else ""
    if log_dir is not None:
        os.makedirs(log_dir, exist_ok=True)
        tool_log_file_path = os.path.join(log_dir, f"{tool_name}{suffix}.log")
    else:
        tool_log_file_path = f"./log/{tool_name}{suffix}.log"

    with open(tool_log_file_path, "a"):
        # Ensure the file is created and ready for writing
        pass
    return tool_log_file_path


def get_config_file_name(biobeamer_xml):
    config_file_name = biobeamer_xml.replace("file://", "")
    config_file_name = os.path.basename(config_file_name)
    config_file_name, _ = os.path.splitext(config_file_name)
    return config_file_name


def setup_remote_logging(logger, bio_beamer_parser, host):
    logger.add_syshandler(
        address=(
            bio_beamer_parser.parameters["syshandler_adress"],
            bio_beamer_parser.parameters["syshandler_port"],
        )
    )
    logger.set_log_level(level=logging.DEBUG)
    logger.logger.info(f"Starting Remote Logging from host {host}")


def handle_network_drive(parameters, logger, password):
    tool = parameters["tool"]
    drive = None
    if tool == "robocopy":
        if re.match(r"^\\\\", parameters["target_path"]):
            drive = Drive(
                logger, password=password, networkPath=parameters["target_path"]
            )
            if drive.mapDrive() != 0:
                logger.error(f"Can't map network drive {parameters['target_path']}")
    # For 'scp', do not mount the drive at all
    return drive, tool


def main():
    args = parse_args()
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger, _ = setup_logger(now, log_dir=args.log_dir)
    logger.logger.info("\n\n\nStarting new Biobeamer!")
    logger.logger.info(
        f"retrieving config from {args.xml} for hostname {args.hostname}"
    )
    xsd_path = resolve_xsd_path()
    bio_beamer_parser = BioBeamerParser(
        xml=args.xml,
        xsd=xsd_path,
        hostname=args.hostname,
        logger=logger.logger,
        log_dir=args.log_dir,
    )
    # No need to patch copied_files_log here anymore
    setup_remote_logging(logger, bio_beamer_parser, args.hostname)
    time_out = bio_beamer_parser.parameters["time_out"]
    time.sleep(time_out)
    bio_beamer_parser.log_para()
    drive, tool = handle_network_drive(
        bio_beamer_parser.parameters, logger.logger, args.password
    )
    tool_log_file = get_tool_log_file(args.log_dir, tool, now)
    copy_files(bio_beamer_parser, logger.logger, tool, tool_log_file)
    if drive:
        drive.unmapDrive()


if __name__ == "__main__":
    main()
