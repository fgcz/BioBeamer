#!/usr/bin/python
# -*- coding: latin1 -*-

"""
$HeadURL: http://fgcz-svn.unizh.ch/repos/fgcz/stable/proteomics/BioBeamer/fgcz_biobeamer.py $
$Id: fgcz_biobeamer.py 7229 2015-02-05 09:46:15Z cpanse $
$Date: 2015-02-05 10:46:15 +0100 (Thu, 05 Feb 2015) $

Copyright 2015
Christian Panse <cp@fgcz.ethz.ch>
Christian Trachsel <christian.trachsel@fgcz.uzh.ch>
Witold E. Wolski <wew@fgcz.ethz.ch>

"""

import os
import time
import sys
import subprocess
import logging
import logging.handlers
import re
import socket
import unittest
import filecmp
import urllib
from lxml import etree


class BioBeamerParser(object):
    logger = logging.getLogger('BioBeamerParser')

    def __init__(self, xsd='BioBeamer.xsd', xml='BioBeamer.xml', hostname="fgcz-i-202"):
        """
        :param xsd:
        :param xml:
        :return:
        """
        syslog_handler = logging.handlers.SysLogHandler(address=("130.60.81.148", 514))
        formatter = logging.Formatter('%(name)s %(message)s')
        syslog_handler.setFormatter(formatter)
        self.logger.addHandler(syslog_handler)
        self.logger.setLevel(logging.INFO)

        self.parameters = {}
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
            self.logger.error("no host configuration could be found in '{0}'.".format(xml))
            sys.exit(1)


class BioBeamer(object):
    """
    class for syncing data from instrument PC to archive
    """
    parameters = dict()
    logger = logging.getLogger('BioBeamer')

    results = []
    # TODO(CP): log_host is static
    # TODO(CP): log_host_address can not be passed through logging.handlers.SysLogHandler
    def __init__(self, pattern=None, source_path="D:/Data2San/", target_path="\\\\130.60.81.21\\Data2San"):

        if pattern is None:
            self.parameters['pattern'] = ".+[-0-9a-zA-Z_\/\.\\\]+\.(raw|RAW|wiff|wiff\.scan)$"

        self.regex = re.compile(self.parameters['pattern'])

        self.set_para('simulate', False)
        self.parameters['source_path'] = os.path.normpath(source_path)
        self.parameters['target_path'] = os.path.normpath(target_path)
        self.parameters['min_time_diff'] = 2 * 3600  # 2.0 hours
        self.parameters['max_time_diff'] = 24 * 3600 * 7 * 4  # 4 weeks
        self.parameters['min_size'] = 100 * 1024  # 100 KBytes

        # setup logging                                    
        syslog_handler = logging.handlers.SysLogHandler(address=("130.60.81.148", 514))
        
        formatter = logging.Formatter('%(name)s %(message)s')
        syslog_handler.setFormatter(formatter)

        self.logger.addHandler(syslog_handler)
        self.logger.setLevel(logging.INFO)

    def para_from_url(self, xsd='BioBeamer.xsd', xml='BioBeamer.xml'):

        """
        :param xsd:
        :param xml:
        :return:
        """
        hostname = str(socket.gethostname())
        bio_beamer_parser = BioBeamerParser(xsd, xml, hostname)
        self.parameters = bio_beamer_parser.parameters

    def print_para(self):
        """ print class parameter setting """
        for k, v in self.parameters.items():
            sys.stdout.write("{0}\t=\t{1}\n".format(k, v))

    def set_para(self, key, value):
        """ class parameter setting """
        self.parameters[key] = value
        if key is 'pattern':
            self.regex = re.compile(self.parameters['pattern'])

    def sync(self, file_to_copy, func_target_mapping):
        """ default is printing only """
        source_file = os.path.normpath("{0}/{1}".format(self.parameters['source_path'], func_target_mapping(file_to_copy)))
        target_file = os.path.normpath("{0}/{1}".format(self.parameters['target_path'], func_target_mapping(file_to_copy)))

        sys.stdout.write("consider: '{0}'\n\t->'{1}'\n".format(source_file, target_file))
        self.results.append(file_to_copy)

    def filter(self, files_to_copy):
        files_to_copy = filter(self.regex.match, files_to_copy)
        files_to_copy = filter(lambda f: time.time() - os.path.getmtime(f) > self.parameters['min_time_diff'], files_to_copy)
        files_to_copy = filter(lambda f: time.time() - os.path.getmtime(f) < self.parameters['max_time_diff'], files_to_copy)
        files_to_copy = filter(lambda f: os.path.getsize(f) > self.parameters['min_size'], files_to_copy)
        return files_to_copy

    def run(self, func_target_mapping=lambda x: x):
        """
            main methode: does crawling, filtering, and starting the robocopy
            subprocess
        """

        self.print_para()

        self.logger.info("crawl source path = '{0}'".format(self.parameters['source_path']))
        try:
            os.chdir(self.parameters['source_path'])
        except:
            self.logger.error("can't change source path")
            raise

        for (root, dirs, files) in os.walk(os.path.normpath('.'),
                                           topdown=False, followlinks=False,
                                           onerror=lambda e: sys.stdout.write("Error: {0}\n".format(e))):

            # BioBeamer filters
            files_to_copy = map(lambda f: os.path.join(root, f), files)
            files_to_copy = self.filter(files_to_copy)

            for file_to_copy in files_to_copy:
                self.sync(file_to_copy, func_target_mapping)

        self.logger.info("done")

    def exec_cmd(self, file_to_copy, cmd):
        """ system call """
        self.logger.info("consider: '{0}'".format(file_to_copy))
        self.logger.info("try to run: '{0}'".format(" ".join(cmd)))
        self.logger.info("getmtime={0}; getsize={1}"
                         .format(time.time() - os.path.getmtime(file_to_copy), os.path.getsize(file_to_copy)))

        if self.parameters['simulate'] is True:
            self.logger.info("simulate is True. aboard.")
            return

        try:
            # todo(cp): check if this is really necessary
            os.chdir(self.parameters['source_path'])
            robocopy_process = subprocess.Popen(" ".join(cmd), shell=True)
            return_code = robocopy_process.wait()
            self.logger.info("robocopy return code: '{0}'".format(return_code))
            if return_code > 7:
                self.logger.warning("robocopy quit with return code highter than 7")
            robocopy_process.terminate()

        except:
            self.logger.error("robocopy exception raised.")
            raise


class Checker(BioBeamer):
    def __init__(self, pattern=None, source_path="D:/Data2San/", target_path="\\\\130.60.81.21\\Data2San"):
        """ just call the super class """
        super(Checker, self).__init__(pattern, source_path, target_path)

    def filter(self, files_to_copy):
        files_to_copy = filter(self.regex.match, files_to_copy)
        files_to_copy = filter(lambda f: time.time() - os.path.getmtime(f) > self.parameters['max_time_diff'], files_to_copy)
        return files_to_copy

    def sync(self, file_to_copy, func_target_mapping=lambda x: x):
        # target_sub_path = func_target_mapping(os.path.dirname(file_to_copy))

        target_file = os.path.normpath("{0}/{1}".format(self.parameters['target_path'], func_target_mapping(file_to_copy)))

        try:
            f = open('files_to_be_deleted.bat', 'w')
        except:
            raise

        if os.path.isfile(target_file):
            if filecmp.cmp(file_to_copy, target_file):
                # os.remove(file_to_copy)
                f.write("delete {0}\n".format(file_to_copy))
            else:
                f.write("rem file '{0}' is different\n".format(file_to_copy))
        else:
            f.write("rem ERROR: file '{0}' missing\n".format(target_file))


class Robocopy(BioBeamer):
    """
    BioBeamer class using robocopy.exe

    the sync is done by using MS robocopy.exe or on UNIX by using rsync
    """
    def __init__(self, pattern=None, source_path="D:/Data2San/", target_path="\\\\130.60.81.21\\Data2San"):
        """ just call the super class """
        super(Robocopy, self).__init__(pattern, source_path, target_path)
        self.set_para('robocopy_args', "/E /Z /MOV /NP /LOG+:C:\\Progra~1\\BioBeamer\\robocopy.log")

    def sync(self, file_to_copy, func_target_mapping):
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
        target_sub_path = func_target_mapping(os.path.dirname(file_to_copy))
        if target_sub_path is None:
            # self.logger.info("func_target_mapping returned 'None'")
            return

        cmd = [
            "robocopy.exe",
            self.parameters['robocopy_args'],
            os.path.dirname(file_to_copy),
            os.path.normpath("{0}/{1}".format(self.parameters['target_path'], target_sub_path)),
            os.path.basename(file_to_copy)
        ]
        self.exec_cmd(file_to_copy, cmd)


def map_data_analyst_tripletof_1(path):
    """
    input:  'p1000/Data/selevsek_20150119'
    output: 'p1000/Proteomics/TRIPLETOF_1/selevsek_20150119'
    """

    pattern = ".*(p[0-9]+)\\\\Data\\\\([-0-9a-zA-Z_\.]+)$"
    regex = re.compile(pattern)
    match = regex.match(path)

    if match:
        return os.path.normpath("{0}/Proteomics/TRIPLETOF_1/{1}".format(match.group(1), match.group(2)))

    return None


def map_data_analyst_qtrap_1(path):
    """
    input:  'p1000/Data/selevsek_20150119'
    output: 'p1000/Proteomics/TRIPLETOF_1/selevsek_20150119'
    """

    pattern = ".*(p[0-9]+)\\\\Data\\\\([-0-9a-zA-Z_\.]+)$"
    regex = re.compile(pattern)
    match = regex.match(path)

    if match:
        return os.path.normpath("{0}/Proteomics/QTRAP_1/{1}".format(match.group(1), match.group(2)))
    return None


class TestTargetMapping(unittest.TestCase):
    """
    run
        python -m unittest -v fgcz_biobeamer
    """
    def setUp(self):
        pass

    def test_tripletof(self):
        desired_result = os.path.normpath('p1000/Proteomics/TRIPLETOF_1/selevsek_20150119')
        self.assertTrue(desired_result == map_data_analyst_tripletof_1('p1000\Data\selevsek_20150119'))
        self.assertTrue(map_data_analyst_tripletof_1('p1000\data\selevsek_20150119') is None)


if __name__ == "__main__":
    bio_beamer = BioBeamer()
    bio_beamer.para_from_url(xsd='http://fgcz-s-021.uzh.ch/BioBeamer/BioBeamer.xsd',
                     xml='http://fgcz-s-021.uzh.ch/BioBeamer/BioBeamer.xml')
    bio_beamer.run()

    BBChecker = Checker()
    BBChecker.para_from_url(xsd='http://fgcz-s-021.uzh.ch/BioBeamer/BioBeamer.xsd',
                            xml='http://fgcz-s-021.uzh.ch/BioBeamer/BioBeamer.xml')
    BBChecker.run()

    sys.stdout.write("done. exit 0\n")
    time.sleep(5)
    sys.exit(0)
