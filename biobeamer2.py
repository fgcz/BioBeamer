# This should go into the robocopy because otherwise it might conflict with the Checker class.
import time
import os

import logging
import logging.handlers

import urllib

import subprocess
from lxml import etree
import re
import sys
import socket
import mapping_functions


def create_logger(name="BioBeamer", filename="./log/biobeamer.log", address=("130.60.81.148", 514), make_syslog = False):
    logger = logging.getLogger(name)
    if not logger.handlers:

        formatter = logging.Formatter('%(name)s - %(asctime)s - %(levelname)s - %(message)s')

        file_handler = logging.FileHandler(filename)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        if make_syslog:
            syslog_handler = logging.handlers.SysLogHandler(address=address)
            syslog_handler.setFormatter(formatter)
            logger.addHandler(syslog_handler)

        logger.addHandler(file_handler)
        logger.setLevel(logging.INFO)
    return logger



class BioBeamerParser(object):
    """
    class for syncing data from instrument PC to archive
    """
    parameters = {'simulate': False,
                  'min_time_diff': 2 * 3600,
                  'max_time_diff': 24 * 3600 * 7 * 4,
                  'min_size': 100 * 1024,
                  'source_path' : "D:/Data2San/",
                  'target_path' : "\\\\130.60.81.21\\Data2San"}

    results = []

    def __init__(self, xsd, xml, hostname, logger):
        """
        :param xsd: BioBeamer.xsd
        :param xml: BioBeamer.xml
        :return:
        """
        self.logger = logger
        #self.parameters = {}

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
                            self.parameters['simulate'] = False
                        else:
                            self.parameters['simulate'] = True
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
                                       onerror=lambda e: logger.info("Error: {0}\n".format(e))):
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
    return(basename_dict)

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

def robocopy_filter(files_to_copy, regex, parameters):
    basename_dict = robocopy_get_basename_dict(files_to_copy)
    files = basename_dict.values()
    files = filter(lambda fl : robocopy_filter_sublist(fl , regex=regex, parameters=parameters), files )
    files = [item for sublist in files for item in sublist]
    return files


def log_files_stat(files_to_copy, logger):
    '''
    :param files_to_copy: list with files to copy
    :param logger: a logger
    :return: nil
    '''
    for file_to_copy in files_to_copy:
        logger.info("consider: '{0}'".format(file_to_copy))
        logger.info("getmtime={0}; getsize={1}"
                         .format(time.time() - os.path.getmtime(file_to_copy), os.path.getsize(file_to_copy)))


def robocopy_exec(file_to_copy, target_path, robocopy_args, logger, simulate = False):
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
    cmd = [
        "robocopy.exe",
        robocopy_args,
        os.path.dirname(file_to_copy),
        os.path.normpath(target_path),
        os.path.basename(file_to_copy)
    ]

    logger.info("try to run: '{0}'".format(" ".join(cmd)))

    if not(simulate):
        try:
            # TODO(cp): check if this is really necessary
            #os.chdir(self.parameters['source_path'])
            robocopy_process = subprocess.Popen(" ".join(cmd), shell=True)
            return_code = robocopy_process.wait()
            logger.info("robocopy return code: '{0}'".format(return_code))
            if return_code > 7:
                logger.warning("robocopy quit with return code highter than 7")
            robocopy_process.terminate()

        except:
            logger.error("robocopy exception raised.")
            raise

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


def rename_destination(filemap , mapping_function = lambda x : x):
    for key, value in filemap.iteritems():
        filemap[key] = mapping_function(value)
    return filemap


configuration_url = "http://fgcz-s-021.uzh.ch/config/"

tmp = '\\\\130.60.81.21\\Data2San\\p1001\\Data\\selevsek_20150119\\testdumm.raw'
tmp2 = '\\\\130.60.81.21\\Data2San\\p1001\\Data\\selevsek_20150119\\testdumm2.wiff'

if __name__ == "__main__":
    tmp_ = mapping_functions.map_data_analyst_qtrap_1(tmp)
    tmp2_ = mapping_functions.map_data_analyst_qtrap_1(tmp2)

    host = socket.gethostname()
    host = "fgcz-i-188"

    print("hostname is {0}.".format(socket.gethostname()))
    biobeamer_xsd = "{0}/BioBeamer.xsd".format(configuration_url)
    biobeamer_xml = "{0}/BioBeamer.xml".format(configuration_url)
    logger = create_logger()

    bbparser = BioBeamerParser(biobeamer_xsd, biobeamer_xml, hostname=host, logger=logger)

    parameters = bbparser.parameters
    regex = bbparser.regex

    files2copy = get_all_files(parameters["source_path"], logger=logger)
    filesRR = robocopy_filter(files2copy,regex,parameters)
    log_files_stat(filesRR, logger=logger)
    tmp = make_destination_files(filesRR, parameters["source_path"],parameters["target_path"])

    mapping_function_name = parameters["func_target_mapping"]
    if mapping_function_name != "":
        methodToCall = getattr(mapping_functions, mapping_function_name)
        res = rename_destination(tmp, mapping_function = methodToCall)

    print(len(files2copy))


