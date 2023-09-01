# This should go into the robocopy because otherwise it might conflict with the Checker class.
import filecmp
import time
import os

import logging.handlers
import MyLog
import BioBeamerParser

from subprocess import Popen
import re
import socket
import mapping_functions
import sys

from mapNetworks import Drive
from datetime import datetime


def get_all_files(source_path, logger):
    '''
    :param source_path:
    :param logger:
    :return: return list of files in directory
    '''
    all_files = []
    for (root, dirs, files) in os.walk(source_path,
                                       topdown=False, followlinks=False,
                                       onerror=lambda e: logger.error("os.walk: {0}\n".format(e))):
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
            false_str.append('regex')
        if not time.time() - os.path.getmtime(f) > parameters['min_time_diff']:
            ok = False
            false_str.append('min_time_diff = {}; observed = {}'.format(parameters['min_time_diff'],
                                                                        time.time() - os.path.getmtime(f)))
        if not time.time() - os.path.getmtime(f) < parameters['max_time_diff']:
            ok = False
            false_str.append('max_time_diff = {}; observed = {}'.format(parameters['max_time_diff'],
                                                                        time.time() - os.path.getmtime(f)))
        if not os.path.getsize(f) >= parameters['min_size']:
            ok = False
            false_str.append("min_size = {}; actual_size = {}".format(parameters['min_size'], os.path.getsize(f)))
        if ok:
            files_to_copy.append(f)

        if len(false_str) > 0:
            false_str = " & ".join(false_str)
            logger.debug("not copying {file} for {reasons}".format(file=f, reasons=false_str))

    if len(files_to_copy) < len(files):
        if len(files_to_copy) > 0:
            files_rejected = ", ".join(files)
            logger.debug("not copying because of basename dictionary violation: {files}".format(files=files_rejected))
        return False
    return True


def robocopy_filter_sublist_deprec(f, regex, parameters, logger):
    files_to_copy = filter(regex.match, f)
    files_to_copy = filter(lambda f: time.time() - os.path.getmtime(f) > parameters['min_time_diff'],
                           files_to_copy)
    files_to_copy = filter(lambda f: time.time() - os.path.getmtime(f) < parameters['max_time_diff'],
                           files_to_copy)
    files_to_copy = filter(lambda f: os.path.getsize(f) > parameters['min_size'], files_to_copy)
    files_to_copy = list(files_to_copy)
    if len(files_to_copy) < len(f):
        return False
    return True


def filter_input_filelist(files_to_copy, regex, parameters, logger):
    files_to_copy.sort()
    basename_dict = robocopy_get_basename_dict(files_to_copy)
    files = basename_dict.values()
    files = filter(lambda fl: robocopy_filter_sublist(fl, regex=regex, parameters=parameters, logger=logger), files)
    files = [item for sublist in files for item in sublist]
    return files


def log_files_stat(files_to_copy, parameters, logger):
    '''
    :param files_to_copy: list with files to copy
    :param logger: a logger
    :return: nil
    '''
    for file_to_copy in files_to_copy:
        logger.info(
            "consider: '{name}' filetime={time}; filesize={size}, maxtime={maxtime}, mintime={mintime}, minsize={minsize}".format(
                name=file_to_copy,
                time=time.time() - os.path.getmtime(file_to_copy),
                size=os.path.getsize(file_to_copy),
                mintime=parameters['min_time_diff'],
                maxtime=parameters['max_time_diff'],
                minsize=parameters['min_size'])
        )


def robocopy_exec(file_to_copy,
                  target_path,
                  logger,
                  mov=False,
                  logfile="./log/robocopy.log",
                  simulate_copy=False):
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
        robocopy_args = "/E /NP /R:0 /LOG+:{log}".format(log=logfile)
    else:
        robocopy_args = "/E /NP /R:0 /MOV /LOG+:{log}".format(log=logfile)

    cmd = [
        "robocopy.exe",
        robocopy_args,
        '"{}"'.format(os.path.dirname(file_to_copy)),
        '"{}"'.format(os.path.dirname(target_path)),
        '"{}"'.format(os.path.basename(file_to_copy))
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
            if False:  # Windows API problem posted here https://stackoverflow.com/questions/60753914/os-path-exists-returns-false-on-windows-although-file-exists-max-path-260-windo
                xx = os.path.exists(target_path)
                if xx and filecmp.cmp(file_to_copy, target_path):
                    file_copied = file_to_copy
                else:
                    logger.error(
                        "Python check on robocopy failed on files - from: " + file_to_copy + " to " + target_path + " !!!")
                    logger.error("File size to copy ", os.path.getsize(file_to_copy),
                                 "; file size target " + os.path.getsize(target_path))
                    raise Exception(
                        "Python check on robocopy failed on files - from: " + file_to_copy + " to " + target_path + " !!!")
        except:
            logger.error("robocopy exception raised on files - from " + file_to_copy + " to " + target_path + " !")
            raise Exception("robocopy exception raised on files - from " + file_to_copy + " to " + target_path + " !")
    else:
        logger.info("Simulating Command: [{0}]".format(" ".join(cmd)))

    return file_copied


def robocopy_exec_map(source_results,
                      mov,
                      logger,
                      logfile,
                      simulate=False):
    files_copied = []
    sources = list(source_results.keys())
    sources.sort()
    for source in sources:
        file_copied = robocopy_exec(source,
                                    source_results[source],
                                    logger=logger,
                                    mov=mov,
                                    logfile=logfile,
                                    simulate_copy=simulate)
        if file_copied is not None:
            files_copied.append(file_copied)
    return files_copied


def make_destination_files(files_to_copy, source_path, target_path):
    '''
    :param files_to_copy:
    :param source_path:
    :param target_path:
    :return:
    '''
    res = {}
    # target_path = target_path.replace('\\\\', '\\\\?\\')
    for file_to_copy in files_to_copy:
        target_sub_path = os.path.relpath(file_to_copy, source_path)
        target_file = os.path.normpath("{0}/{1}".format(target_path, target_sub_path))
        res[file_to_copy] = target_file
    return res


def rename_destination(filemap, logger, mapping_function):
    '''
    uses mapping function to rename file
    :param filemap:
    :param logger:
    :param mapping_function:
    :return:
    '''
    for key, value in filemap.items():
        filemap[key] = mapping_function(value, logger)
    return filemap


def compare_files_destination(source_result_mapping):
    '''
    :param source_result_mapping:
    :return: map with fields "copied" and "not_copied"
    '''
    copied = {}
    not_copied = {}
    for file_to_copy, target_file in source_result_mapping.items():
        # tmp = os.path.exists(target_file)
        if not target_file is None:
            if os.path.exists(target_file) and filecmp.cmp(file_to_copy, target_file):
                copied[file_to_copy] = target_file
            else:
                not_copied[file_to_copy] = target_file
    return ({"copied": copied, "not_copied": not_copied})


def log_copied_files(copied_files,
                     storage="./log/copied_files.txt"):
    if len(copied_files) > 0:
        copied_files.sort()
        with open(storage, "w") as file_log:
            for file in copied_files:
                file_log.write(file + "\n")


def read_copied_files(storage="./log/copied_files.txt"):
    if os.path.isfile(storage):
        with open(storage, "r") as file_log:
            copied_files = file_log.read().splitlines()
            return copied_files
    else:
        return []


def remove_old_copied(source_result_mapping,
                      max_time_diff,
                      logger,
                      simulate="files2delete/files2delete.bat"):
    '''
    removes old files which have been already copied
    :param source_result_mapping:
    :param max_time_diff:
    :param logger:
    :param simulate:
    :return:
    '''
    if simulate:
        with open(simulate, "w") as myfile:
            simulate_mode = True
    else:
        simulate_mode = False

    for file_to_copy in source_result_mapping:
        if os.path.isfile(file_to_copy):
            time_diff = time.time() - os.path.getmtime(file_to_copy)
            if time_diff > max_time_diff:
                if not myfile and not simulate:
                    logger.info("removing file : [rm {0}] since tf {1} > max_time {2}".format(file_to_copy, time_diff,
                                                                                              max_time_diff))
                    os.remove(file_to_copy)
                else:
                    logger.info(
                        "Simulating command : [rm {0}] since tf {1} > max_time {2}".format(file_to_copy, time_diff,
                                                                                           max_time_diff))
                    myfile.write("rm {0}\n".format(file_to_copy))

    if simulate_mode and myfile:
        myfile.close()

def compare_copied_with_log(not_copied, files_copied_old):
    new_not_copied = {}
    for (key, value) in not_copied.items():
        if key not in set(files_copied_old):
            new_not_copied[key] = value
    return new_not_copied


def robocopy(bio_beamer_parser, logger):
    parameters = bio_beamer_parser.parameters
    regex = bio_beamer_parser.regex

    if os.path.exists(parameters["source_path"]):
        files2copy = get_all_files(parameters["source_path"], logger=logger)
    else:
        error = 'source path: {source_path} does not exist!'.format(source_path=parameters["source_path"])
        logger.error(error)
        raise FileNotFoundError(error)

    files_copied_log = read_copied_files(storage=parameters["copied_files_log"])  # added 02.2020
    files2copy = list(set(files2copy) - set(files_copied_log))  # remove all files which were already copied.

    files_filtered = filter_input_filelist(files2copy, regex, parameters, logger=logger)

    simulate = 'files2delete/files2delete.bat' if parameters['simulate_delete'] else ''

    if len(files_filtered) != 0:

        source_result_mapping = make_destination_files(files_filtered, parameters["source_path"],
                                                       parameters["target_path"])

        mapping_function_name = parameters["func_target_mapping"]
        if mapping_function_name != "":
            logger.info("trying to apply mapping function : {}.".format(mapping_function_name))
            method_to_call = getattr(mapping_functions, mapping_function_name)
            source_result_mapping = rename_destination(source_result_mapping,
                                                       logger,
                                                       mapping_function=method_to_call)

        # check if files are already copied and if so remove them from source_result_mapping
        copied = compare_files_destination(source_result_mapping)

        all_copied = list(
            copied["copied"].keys()) + files_copied_log  # add it because you might start with empty copied file list.
        all_copied = set(all_copied)
        not_copied = copied["not_copied"]
        not_copied_keys = not_copied.keys() - set(all_copied)
        not_copied = dict((k, not_copied[k]) for k in not_copied_keys)

        files_copied = robocopy_exec_map(not_copied,
                                         parameters["robocopy_mov"],
                                         logger,
                                         logfile="./log/robocopy.log",
                                         simulate=parameters['simulate_copy'])

        files_copied = set(list(all_copied) + files_copied)
        log_copied_files(list(files_copied), storage=parameters["copied_files_log"])  # added 02.2020

        # removes files which have been copied
        remove_old_copied(files_copied,
                          parameters["max_time_delete"],
                          logger,
                          simulate=simulate)
    else:
        remove_old_copied(files_copied_log,
                          parameters["max_time_delete"],
                          logger,
                          simulate=simulate)


if __name__ == "__main__":

    configuration_url = "file:///c:/FGCZ/BioBeamer"
    biobeamer_xml = "BioBeamer2.xml"
    if len(sys.argv) >= 3:
        configuration_url = sys.argv[1]
        password = sys.argv[2]
    if len(sys.argv) == 4:
        biobeamer_xml = sys.argv[3]

    biobeamer_xsd = "{0}/BioBeamer2.xsd".format(configuration_url)
    biobeamer_xml_path = ("{0}/"+biobeamer_xml).format(configuration_url)

    host = socket.gethostname()
    logger = MyLog.MyLog()
    now = datetime.now().strftime("%Y%m%d_%H%M%S")  # current date and time
    file = "log/biobeamer_{xml}_{date}.log".format(xml = biobeamer_xml, date=now)
    logger.add_file(filename=file, level=logging.DEBUG)
    logger.logger.info("\n\n\nStarting new Biobeamer!")
    logger.logger.info("retrieving config from {} for hostname {}".format(biobeamer_xml, host))

    bio_beamer_parser = BioBeamerParser.BioBeamerParser(biobeamer_xsd, biobeamer_xml_path, hostname=host,
                                                        logger=logger.logger)
    logger.add_syshandler(address=(bio_beamer_parser.parameters["syshandler_adress"],
                                   bio_beamer_parser.parameters["syshandler_port"]))
    logger.set_log_level(level=logging.DEBUG)

    logger.logger.info("Starting Remote Logging from host {}".format(host))

    time_out = bio_beamer_parser.parameters["time_out"]
    time.sleep(time_out)

    bio_beamer_parser.log_para()

    drive = 0
    if re.match("^\\\\", bio_beamer_parser.parameters['target_path']):
        drive = Drive(logger.logger, password=password, networkPath=bio_beamer_parser.parameters['target_path'])
        if not drive.mapDrive() == 0:
            logger.logger.error("Can't map network drive {}".format(bio_beamer_parser.parameters['target_path']))
            exit(0)

    robocopy(bio_beamer_parser, logger.logger)

    if not drive == 0:
        drive.unmapDrive()
