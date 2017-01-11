#!/usr/bin/python
# -*- coding: latin1 -*-

"""
$HeadURL: http://fgcz-svn.uzh.ch/repos/fgcz/stable/proteomics/BioBeamer/fgcz_biobeamer.py $
$Id: fgcz_biobeamer.py 7915 2015-12-21 08:16:17Z cpanse $
$Date: 2015-12-21 09:16:17 +0100 (Mon, 21 Dec 2015) $

Copyright 2006-2015 Functional Genomics Center Zurich

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

Author / Maintainer: Christian Panse <cp@fgcz.ethz.ch>, Witold E. Wolski <wew@fgcz.ethz.ch>
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



def create_logger(name="BioBeamer", filename="./log/biobeamer.log", address=("130.60.81.148", 514)):
    logger = logging.getLogger(name)
    if not logger.handlers:
        formatter = logging.Formatter('%(name)s - %(asctime)s - %(levelname)s - %(message)s')

        file_handler = logging.FileHandler(filename)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)

        syslog_handler = logging.handlers.SysLogHandler(address=address)
        syslog_handler.setFormatter(formatter)
        logger.addHandler(syslog_handler)

        logger.addHandler(file_handler)
        logger.setLevel(logging.INFO)
    return logger


class BioBeamerParser(object):
    def __init__(self, xsd, xml, hostname="fgcz-i-202"):
        """
        :param xsd: BioBeamer.xsd
        :param xml: BioBeamer.xml
        :return:
        """
        self.logger = create_logger()
        self.parameters = {}

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



def get_basename_dict(files_to_copy):
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


class BioBeamer(object):
    """
    class for syncing data from instrument PC to archive
    """

    parameters = {'simulate': False,
                  'min_time_diff': 2 * 3600,
                  'max_time_diff': 24 * 3600 * 7 * 4,
                  'min_size': 100 * 1024}

    results = []

    def __init__(self, pattern=None, source_path="D:/Data2San/", target_path="\\\\130.60.81.21\\Data2San"):
        self.logger = create_logger()
        if pattern is None:
            self.parameters['pattern'] = ".+[-0-9a-zA-Z_\/\.\\\]+\.(raw|RAW|wiff|wiff\.scan)$"

        self.regex = re.compile(self.parameters['pattern'])
        self.parameters['source_path'] = os.path.normpath(source_path)
        self.parameters['target_path'] = os.path.normpath(target_path)

    def para_from_url(self, xsd, xml):
        """
        :param xsd: BioBeamer.xsd
        :param xml: BioBeamer.xml
        :return:
        """
        hostname = str(socket.gethostname())
        bio_beamer_parser = BioBeamerParser(xsd, xml, hostname)
        self.parameters = bio_beamer_parser.parameters
        # TODO(wew,cp) is this really smart
        self.regex = bio_beamer_parser.regex

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

        target_sub_path = os.path.relpath(file_to_copy, self.parameters['source_path'])
        target_file = os.path.normpath("{0}/{1}".format(self.parameters['target_path'], target_sub_path))

        source_file = os.path.normpath(file_to_copy)
        target_file = os.path.normpath(target_file)

        sys.stdout.write("consider: '{0}'\n\t->'{1}'\n".format(source_file, target_file))
        self.results.append(file_to_copy)

    # This should go into the robocopy because otherwise it might conflict with the Checker class.
    def bb_filter(self, f):
        """
        expecting a dictionary where the basename is the key
        returns True iff all files (values) fullfill the filter criteria
        """
        files_to_copy = filter(self.regex.match, f)
        files_to_copy = filter(lambda f: time.time() - os.path.getmtime(f) > self.parameters['min_time_diff'],
                               files_to_copy)
        files_to_copy = filter(lambda f: time.time() - os.path.getmtime(f) < self.parameters['max_time_diff'],
                               files_to_copy)
        files_to_copy = filter(lambda f: os.path.getsize(f) > self.parameters['min_size'], files_to_copy)

        if len(files_to_copy) < len(f):
            return False
        return True

    def run(self, func_target_mapping=lambda x: x):
        """
            main methode: does crawling, filtering, and starting the robocopy
            subprocess
        """

        self.print_para()
        self.logger.info("crawl source path = '{0}'".format(self.parameters['source_path']))

        '''
        try:
            os.chdir(self.parameters['source_path'])
        except:
            self.logger.error("can't change source path")
            raise
        '''
        #source_path = self.parameters['source_path']

        for (root, dirs, files) in os.walk(self.parameters['source_path'],
                                           topdown=False, followlinks=False,
                                           onerror=lambda e: sys.stdout.write("Error: {0}\n".format(e))):

            # BioBeamer filters
            files_to_copy = map(lambda f: os.path.join(root, f), files)

            basename_dict = get_basename_dict(files_to_copy)
            basename_values = basename_dict.values()
            # not clear what happens here because this is list!!!
            files_to_copy = filter(self.bb_filter, basename_values)

            # TODO(cp): remove the for loop
            for file_to_copy in files_to_copy:
                map(lambda f: self.sync(f, func_target_mapping), file_to_copy)

        self.logger.info("done")

    def exec_cmd(self, file_to_copy, cmd):
        """ system call """
        self.logger.info("consider: '{0}'".format(file_to_copy))
        self.logger.info("try to run: '{0}'".format(" ".join(cmd)))
        self.logger.info("getmtime={0}; getsize={1}"
                         .format(time.time() - os.path.getmtime(file_to_copy), os.path.getsize(file_to_copy)))

        if self.parameters['simulate'] is True:
            self.logger.info("simulate is True. aboard.")
            print("getmtime = {0};\ngetsize = {1} diff={2}".format(time.time() - os.path.getmtime(file_to_copy),
                                                                   os.path.getsize(file_to_copy),
                                                                   os.path.getsize(file_to_copy) - self.parameters[
                                                                       'min_size']))
            return

        try:
            # TODO(cp): check if this is really necessary
            #os.chdir(self.parameters['source_path'])
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
    def __init__(self, pattern=None, source_path="D:/Data2San/", target_path="\\\\130.60.81.21\\Data2San", deletefile = "files2delete/files_to_be_deleted.bat"):
        """ just call the super class """
        super(Checker, self).__init__(pattern, source_path, target_path)
        self.temp_file = deletefile

        if os.path.isfile(self.temp_file):
            os.remove(self.temp_file)
        self.logger.info("write file status information to '{0}'.".format(self.temp_file))

    # not used yet.
    def isFiles2remove(self, file_to_copy):
        res =  bool(self.regex.match(file_to_copy)) & (time.time() - os.path.getmtime(file_to_copy) > self.parameters['max_time_diff']/2.)
        return res

    def sync(self, file_to_copy, func_target_mapping=lambda x: x):

        target_sub_path = os.path.relpath(file_to_copy, self.parameters['source_path'])
        target_file = os.path.normpath("{0}/{1}".format(self.parameters['target_path'], target_sub_path))

        with open(self.temp_file, 'w+') as f:
            if os.path.isfile(target_file):
                if self.isFiles2remove(file_to_copy) & filecmp.cmp(file_to_copy, target_file):
                    # TODO(cp): if delete works just uncomment it
                    # os.remove(file_to_copy)
                    f.write("delete {0}\n".format(file_to_copy))
                else:
                    f.write("rem file '{0}' is different\n".format(file_to_copy))
            else:
                f.write("rem ERROR: file '{0}' missing\n".format(target_file))
        f.close()



class Robocopy(BioBeamer):
    """
    BioBeamer class using robocopy.exe

    the sync is done by using MS robocopy.exe or on UNIX by using rsync
    """

    def __init__(self, pattern=None, source_path="D:/Data2San/", target_path="\\\\130.60.81.21\\Data2San"):
        """ just call the super class """
        super(Robocopy, self).__init__(pattern, source_path, target_path)
        self.set_para('robocopy_args', "/E /Z /MOV /NP /LOG+:.\\log\\robocopy.log")

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
        target_sub_path = os.path.relpath(os.path.dirname(file_to_copy), self.parameters['source_path'] )

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


