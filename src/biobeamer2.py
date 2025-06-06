# This should go into the robocopy because otherwise it might conflict with the Checker class.
import argparse
import filecmp
import logging.handlers
import os
import re
import shlex
import socket
import time
from datetime import datetime
from subprocess import Popen

import BioBeamerParser
import MyLog
import mapping_functions
from mapNetworks import Drive


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
                logger.warning("robocopy quit with return code highter than 7")
            else:
                file_copied = file_to_copy

            robocopy_process.terminate()

            # make sure file was copied correctly
            if (
                False
            ):  # Windows API problem posted here https://stackoverflow.com/questions/60753914/os-path-exists-returns-false-on-windows-although-file-exists-max-path-260-windo
                xx = os.path.exists(target_path)
                if xx and filecmp.cmp(file_to_copy, target_path):
                    file_copied = file_to_copy
                else:
                    logger.error(
                        "Python check on robocopy failed on files - from: "
                        + file_to_copy
                        + " to "
                        + target_path
                        + " !!!"
                    )
                    logger.error(
                        "File size to copy ",
                        os.path.getsize(file_to_copy),
                        "; file size target " + os.path.getsize(target_path),
                    )
                    raise Exception(
                        "Python check on robocopy failed on files - from: "
                        + file_to_copy
                        + " to "
                        + target_path
                        + " !!!"
                    )
        except:
            logger.error(
                "robocopy exception raised on files - from "
                + file_to_copy
                + " to "
                + target_path
                + " !"
            )
            raise Exception(
                "robocopy exception raised on files - from "
                + file_to_copy
                + " to "
                + target_path
                + " !"
            )
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
    file_copied = None
    # Compose the scp command with verbose output
    cmd = ["scp", "-v", shlex.quote(source), shlex.quote(target)]
    cmd_str = " ".join(cmd)
    if not simulate_copy:
        logger.info(f"Running Command: [{cmd_str}]")
        try:
            # Write a header to the log file to ensure it is touched
            with open(tool_log_file, "a") as logf:
                logf.write(
                    f"--- Running SCP command at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n"
                )
                logf.flush()
                scp_process = Popen(cmd_str, shell=True, stdout=logf, stderr=logf)
                return_code = scp_process.wait()
            logger.info(f"scp return code: '{return_code}'")
            if return_code != 0:
                logger.warning("scp quit with non-zero return code")
            else:
                file_copied = source
            scp_process.terminate()
            # Optionally, check if file exists at target (if local path)
            # and compare size
            if os.path.exists(target):
                if os.path.getsize(source) == os.path.getsize(target):
                    file_copied = source
                else:
                    logger.error(
                        f"File size mismatch after scp: {source} ({os.path.getsize(source)}) vs {target} ({os.path.getsize(target)})"
                    )
        except Exception as e:
            logger.error(
                f"scp exception raised on files - from {source} to {target}! Exception: {e}"
            )
            raise Exception(
                f"scp exception raised on files - from {source} to {target}! Exception: {e}"
            )
    else:
        logger.info(f"Simulating Command: [{cmd_str}]")
    return file_copied


def copy_files_with_tool(
    source_results, mov, logger, tool_log_file, tool, simulate=False
):
    files_copied = []
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
        else:
            logger.error("Tool {0} not supported!".format(tool))
            raise NotImplementedError("Tool {0} not supported!".format(tool))
        if file_copied is not None:
            files_copied.append(file_copied)
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


def compare_files_destination(source_result_mapping):
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
            else:
                not_copied[file_to_copy] = target_file
    return {"copied": copied, "not_copied": not_copied}


def log_copied_files(copied_files, copied_files_log_path):
    if len(copied_files) > 0:
        copied_files.sort()
        with open(copied_files_log_path, "w") as file_log:
            for file in copied_files:
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
    simulate="../files2delete/files2delete.bat",
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


def copy_files(bio_beamer_parser, logger, tool, tool_log_file_path):
    parameters = bio_beamer_parser.parameters
    regex = bio_beamer_parser.regex

    if os.path.exists(parameters["source_path"]):
        files2copy = get_all_files(parameters["source_path"], logger=logger)
    else:
        error = "source path: {source_path} does not exist!".format(
            source_path=parameters["source_path"]
        )
        logger.error(error)
        raise FileNotFoundError(error)

    files_copied_log = read_copied_files(
        copied_files_log_path=parameters["copied_files_log"]
    )  # added 02.2020
    files2copy = list(
        set(files2copy) - set(files_copied_log)
    )  # remove all files which were already copied.

    files_filtered = filter_input_filelist(files2copy, regex, parameters, logger=logger)

    simulate = (
        "../files2delete/files2delete.bat" if parameters["simulate_delete"] else ""
    )

    if len(files_filtered) != 0:

        source_result_mapping = make_destination_files(
            files_filtered, parameters["source_path"], parameters["target_path"]
        )

        mapping_function_name = parameters["func_target_mapping"]
        if mapping_function_name != "":
            logger.info(
                "trying to apply mapping function : {}.".format(mapping_function_name)
            )
            method_to_call = getattr(mapping_functions, mapping_function_name)
            source_result_mapping = rename_destination(
                source_result_mapping, logger, mapping_function=method_to_call
            )

        # check if files are already copied and if so remove them from source_result_mapping
        copied = compare_files_destination(source_result_mapping)

        all_copied = (
            list(copied["copied"].keys()) + files_copied_log
        )  # add it because you might start with empty copied file list.
        all_copied = set(all_copied)
        not_copied = copied["not_copied"]
        not_copied_keys = not_copied.keys() - set(all_copied)
        not_copied = dict((k, not_copied[k]) for k in not_copied_keys)

        files_copied = copy_files_with_tool(
            source_results=not_copied,
            mov=parameters["robocopy_mov"],
            logger=logger,
            tool_log_file=tool_log_file_path,
            tool=tool,
            simulate=parameters["simulate_copy"],
        )

        files_copied = set(list(all_copied) + files_copied)
        log_copied_files(
            list(files_copied), copied_files_log_path=parameters["copied_files_log"]
        )  # added 02.2020

        # removes files which have been copied
        remove_old_copied(
            files_copied, parameters["max_time_delete"], logger, simulate=simulate
        )
    else:
        remove_old_copied(
            files_copied_log, parameters["max_time_delete"], logger, simulate=simulate
        )


def parse_args():
    parser = argparse.ArgumentParser(description="BioBeamer2 command line arguments")
    parser.add_argument(
        "--xml",
        "-x",
        default="BioBeamer2.xml",
        help="BioBeamer XML file (default: BioBeamer2.xml)",
    )
    parser.add_argument(
        "--xsd",
        "-s",
        default=None,
        help="BioBeamer XSD file (optional, default: BioBeamer2.xsd in the same directory as the XML file)",
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
        default=None,
        help="Directory for all logs (overrides default log location)",
    )
    args = parser.parse_args()
    # Determine xsd path if not provided
    if args.xsd is None:
        xml_dir = os.path.dirname(args.xml)
        if not xml_dir:
            xml_dir = "."
        xsd_path = os.path.join(xml_dir, "BioBeamer2.xsd")
    else:
        xsd_path = args.xsd

    # Convert xml and xsd to URLs if needed
    def path_to_url(path: str) -> str:
        if (
            path.startswith("file://")
            or path.startswith("http://")
            or path.startswith("https://")
        ):
            return path
        return f"file://{os.path.abspath(path)}"

    args.xml = path_to_url(args.xml)
    args.xsd = path_to_url(xsd_path)
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
    return logger, biobeamer_log_file_path


def get_tool_log_file(log_dir, tool_name="robocopy", now=None):
    import os

    suffix = f"_{now}" if now else ""
    if log_dir is not None:
        os.makedirs(log_dir, exist_ok=True)
        tool_log_file_path = os.path.join(log_dir, f"{tool_name}{suffix}.log")
    else:
        tool_log_file_path = f"./log/{tool_name}{suffix}.log"
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

    bio_beamer_parser = BioBeamerParser.BioBeamerParser(
        xml=args.xml,
        xsd=args.xsd,
        hostname=args.hostname,
        logger=logger.logger,
    )
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
