# This should go into the robocopy because otherwise it might conflict with the Checker class.
import filecmp
import time
import os

import logging
import logging.handlers
import urllib

import subprocess
from lxml import etree
import re
import socket
import mapping_functions
import sys

from mapNetworks import Drive


class MyLog:
    def __init__(self, name="BioBeamer"):
        self.logger = logging.getLogger(name)
        self.formatter = logging.Formatter('%(name)s - %(asctime)s - %(levelname)s - %(message)s')
        self.is_syshandler = False
        self.is_filehandler = False

    def add_file(self, filename="./log/biobeamer.log", level=logging.INFO):
        if not self.is_syshandler:
            file_handler = logging.FileHandler(filename)
            file_handler.setLevel(level)
            file_handler.setFormatter(self.formatter)
            self.logger.addHandler(file_handler)
            self.logger.setLevel(logging.INFO)

    def add_syshandler(self, address=("130.60.81.148", 514), level=logging.INFO):
        if not self.is_filehandler:
            syslog_handler = logging.handlers.SysLogHandler(address=address)
            syslog_handler.setLevel(level)
            syslog_handler.setFormatter(self.formatter)
            self.logger.addHandler(syslog_handler)


class BioBeamerParser(object):
    """
    class for syncing data from instrument PC to archive
    """
    parameters = {'simulate': False,
                  'min_time_diff': 2 * 3600,
                  'max_time_diff': 24 * 3600 * 7 * 4,
                  'min_size': 100 * 1024,
                  'source_path': "D:/Data2San/",
                  'target_path': "\\\\130.60.81.21\\Data2San"}

    results = []

    def __init__(self, xsd, xml, hostname, logger):
        """
        :param xsd: BioBeamer.xsd
        :param xml: BioBeamer.xml
        :return:
        """
        self.logger = logger
        # self.parameters = {}

        xml_url = xml
        # read config files from url
        try:
            f = urllib.urlopen(xml)
            xml = f.read()

            f = urllib.urlopen(xsd)
            xsd = f.read()

        except:
            self.logger.error("can not fetch xml or xsd information")
            raise

        schema = etree.XMLSchema(etree.XML(xsd))

        try:
            parser = etree.XMLParser(remove_blank_text=True, schema=schema)
            xml_bio_beamer = etree.fromstring(xml, parser)

        except:
            self.logger.error("config xml '{0}' can not be parsed.".format(xml))
            raise

        found_host_config = False
        # init para dictionary
        for i in xml_bio_beamer:
            if i.tag == 'host' and 'name' in i.attrib.keys():
                pass
            else:
                continue

            if i.attrib['name'] == hostname:
                for k in i.attrib.keys():
                    if k == 'source_path' or k == 'target_path':
                        self.parameters[k] = os.path.normpath(i.attrib[k])
                    elif k == 'pattern':
                        self.parameters[k] = i.attrib[k]
                        try:
                            self.regex = re.compile(self.parameters['pattern'])
                        except:
                            self.logger.error("re.compile pattern failed.")
                            raise
                    elif k == 'simulate':
                        if i.attrib[k] == "false":
                            self.parameters[k] = False
                        else:
                            self.parameters[k] = True
                    elif k == 'robocopy_mov':
                        if i.attrib[k] == "false":
                            self.parameters[k] = False
                        else:
                            self.parameters[k] = True

                    else:
                        try:
                            self.parameters[k] = int(i.attrib[k])
                        except ValueError:
                            self.parameters[k] = i.attrib[k]
                found_host_config = True

        if found_host_config is False:
            msg = "no host configuration could be found in '{0}'.".format(xml_url)
            print(msg)
            self.logger.error(msg)
            sys.exit(1)

    def print_para(self):
        """ print class parameter setting """
        for k, v in self.parameters.items():
            sys.stdout.write("{0}\t=\t{1}\n".format(k, v))

    def set_para(self, key, value):
        """ class parameter setting """
        self.parameters[key] = value
        if key is 'pattern':
            self.regex = re.compile(self.parameters['pattern'])


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
    basename_regex = re.compile(r"^(.+?)(\.[a-zA-Z0-9]+){1,2}$")
    for f in files_to_copy:
        # TODO(cp): check if this always works as basename
        result = basename_regex.match(f)
        if result:
            file_basename = result.group(1)
            if not file_basename in basename_dict:
                basename_dict[file_basename] = []
            basename_dict[file_basename].append(f)
    return (basename_dict)


def robocopy_filter_sublist(f, regex, parameters):
    """
    expecting a dictionary where the basename is the key
    returns True iff all files (values) fullfill the filter criteria
    """
    files_to_copy = filter(regex.match, f)
    files_to_copy = filter(lambda f: time.time() - os.path.getmtime(f) > parameters['min_time_diff'],
                           files_to_copy)
    files_to_copy = filter(lambda f: time.time() - os.path.getmtime(f) < parameters['max_time_diff'],
                           files_to_copy)
    files_to_copy = filter(lambda f: os.path.getsize(f) > parameters['min_size'], files_to_copy)

    if len(files_to_copy) < len(f):
        return False
    return True


def filter_input_filelist(files_to_copy, regex, parameters):
    basename_dict = robocopy_get_basename_dict(files_to_copy)
    files = basename_dict.values()
    files = filter(lambda fl: robocopy_filter_sublist(fl, regex=regex, parameters=parameters), files)
    files = [item for sublist in files for item in sublist]
    return files


def log_files_stat(files_to_copy, logger):
    '''
    :param files_to_copy: list with files to copy
    :param logger: a logger
    :return: nil
    '''
    for file_to_copy in files_to_copy:
        logger.info("consider: '{0}' getmtime={1}; getsize={1}".format(file_to_copy,time.time() - os.path.getmtime(file_to_copy), os.path.getsize(file_to_copy)))


def robocopy_exec(file_to_copy, target_path, logger, mov=False, logfile="./log/robocopy.log", simulate=False):
    """
    wrapper function to
    compose robocopy.exe command line and call it out of python

    robocopy options:
    /E Copies subdirectories. Note that this option includes empty directories.
    /Z Copies files in Restart mode.
    /MOVE Moves files and directories, and deletes them from the source after they are copied.

    see also:
        https://technet.microsoft.com/en-us/library/cc733145.aspx
    """
    if not mov:
        robocopy_args = "/E /Z /NP /R:0 /LOG+:{log}".format(log=logfile)
    else:
        robocopy_args = "/E /Z /NP /R:0 /MOV /LOG+:{log}".format(log=logfile)

    cmd = [
        "robocopy.exe",
        robocopy_args,
        '"{}"'.format(os.path.dirname(file_to_copy)),
        '"{}"'.format(os.path.dirname(target_path)),
        '"{}"'.format(os.path.basename(file_to_copy))
    ]

    if not (simulate):
        logger.info("Running Command: [{0}]".format(" ".join(cmd)))
        try:
            # TODO(cp): check if this is really necessary
            robocopy_process = subprocess.Popen(" ".join(cmd), shell=True)
            return_code = robocopy_process.wait()
            logger.info("robocopy return code: '{0}'".format(return_code))
            if return_code > 7:
                logger.warning("robocopy quit with return code highter than 7")
            robocopy_process.terminate()

        except:
            logger.error("robocopy exception raised.")
            raise

    else:
        logger.info("Simulating Command: [{0}]".format(" ".join(cmd)))


def robocopy_exec_map(source_results, mov, logger, logfile, simulate=False):
    for source, destination in source_results.iteritems():
        robocopy_exec(source, destination, logger=logger, mov=mov, logfile = logfile,  simulate=simulate)


def make_destination_files(files_to_copy, source_path, target_path):
    '''
    :param files_to_copy:
    :param source_path:
    :param target_path:
    :return:
    '''
    res = {}
    for file_to_copy in files_to_copy:
        target_sub_path = os.path.relpath(file_to_copy, source_path)
        target_file = os.path.normpath("{0}/{1}".format(target_path, target_sub_path))
        res[file_to_copy] = target_file
    return res


def rename_destination(filemap, logger, mapping_function=lambda x, logger: x, ):
    '''
    uses mapping function to rename file
    :param filemap:
    :param logger:
    :param mapping_function:
    :return:
    '''
    for key, value in filemap.iteritems():
        filemap[key] = mapping_function(value, logger)
    return filemap


def compare_files(source_result_mapping):
    '''
    :param source_result_mapping:
    :return: map with fields "copied" and "not_copied"
    '''
    copied = {}
    not_copied = {}
    for file_to_copy, target_file in source_result_mapping.iteritems():
        tmp = os.path.exists(target_file)
        if os.path.exists(target_file) and filecmp.cmp(file_to_copy, target_file):
            copied[file_to_copy] = target_file
        else:
            not_copied[file_to_copy] = target_file
    return ({"copied": copied, "not_copied": not_copied})


def remove_old_copied(source_result_mapping, max_time_diff, logger, simulate="files2delete/files2delete.bat"):
    '''
    removes old files which have been already copied
    :param source_result_mapping:
    :param max_time_diff:
    :param logger:
    :param simulate:
    :return:
    '''
    for file_to_copy in source_result_mapping.keys():

        time_diff = time.time() - os.path.getmtime(file_to_copy)
        if time_diff > max_time_diff:
            logger.info("removing file : [rm {0}] since tf {1} > max_time {2}".format(file_to_copy), time_diff,
                        max_time_diff)
            if not simulate:
                os.remove(file_to_copy)
            else:
                with open(simulate, "wa") as myfile:
                    myfile.write("rm {0}".format(file_to_copy))


def robocopy(bbparser, logger):
    parameters = bbparser.parameters
    regex = bbparser.regex
    files2copy = get_all_files(parameters["source_path"], logger=logger)

    filesRR = filter_input_filelist(files2copy, regex, parameters)
    if len(filesRR) == 0:
        return
    log_files_stat(filesRR, logger=logger)
    source_result_mapping = make_destination_files(filesRR, parameters["source_path"], parameters["target_path"])

    mapping_function_name = parameters["func_target_mapping"]

    if mapping_function_name != "":
        logger.info("trying to apply mapping function : {}.".format(mapping_function_name))
        method_to_call = getattr(mapping_functions, mapping_function_name)
        source_result_mapping = rename_destination(source_result_mapping, logger, mapping_function=method_to_call)

    # check if files are already copied and if so remove them from source_result_mapping
    copied = compare_files(source_result_mapping)

    robocopy_exec_map(copied["not_copied"], parameters["robocopy_mov"], logger, logfile="./log/robocopy.log", simulate=False)
    # it might be that there are not enough files since strict robocopy filtering is applied.
    remove_old_copied(copied["copied"], parameters["max_time_diff"] / 2, logger, simulate="files2delete/files2delete.bat")

if __name__ == "__main__":
    configuration_url = "http://fgcz-ms.fgcz-net.unizh.ch/config/"

    configuration_url = "file:///c:/FGCZ/BioBeamer"
    if len(sys.argv) == 3:
        configuration_url = sys.argv[1]
        password = sys.argv[2]


    biobeamer_xsd = "{0}/BioBeamer2.xsd".format(configuration_url)
    biobeamer_xml = "{0}/BioBeamer2.xml".format(configuration_url)

    host = socket.gethostname()

    logger = MyLog()
    logger.add_file()

    bbparser = BioBeamerParser(biobeamer_xsd, biobeamer_xml, hostname=host, logger=logger.logger)
    logger.add_syshandler(address=(bbparser.parameters["syshandler_adress"], bbparser.parameters["syshandler_port"]))

    drive = 0
    if re.match("^\\\\", bbparser.parameters['target_path']):
        drive = Drive(logger.logger, password=password, networkPath=bbparser.parameters['target_path'])
        if not drive.mapDrive() == 0:
            logger.logger.error("Can't map network drive {}".format(bbparser.parameters['target_path']))
            exit(0)

    logger.logger.info("hostname is {0}.".format(host))
    robocopy(bbparser, logger.logger)

    if not drive == 0:
        drive.unmapDrive()
