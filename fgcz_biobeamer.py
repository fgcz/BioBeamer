#!/usr/bin/python
# -*- coding: latin1 -*-

"""
$HeadURL: http://fgcz-svn.unizh.ch/repos/fgcz/stable/proteomics/BioBeamer/fgcz_biobeamer.py $
$Id: fgcz_biobeamer.py 7229 2015-02-05 09:46:15Z cpanse $
$Date: 2015-02-05 10:46:15 +0100 (Thu, 05 Feb 2015) $

Copyright 2015
Christian Panse <cp@fgcz.ethz.ch>
Christian Trachsel <christian.trachsel@fgcz.uzh.ch>
"""

import os
import time
import re
import sys
import subprocess
import logging, logging.handlers
import re
import socket
import unittest

class BioBeamer(object):
    """
    class for syncinging data from instrument PC to archive

    """
    para = dict()
    logger = logging.getLogger('BioBeamer')

    #TODO(CP): log_host is static
    def __init__(self, pattern=None, log_host="130.60.81.148", source_path="D:/Data2San/", target_path="\\\\130.60.81.21\\Data2San"):

        if pattern is None:
            self.para['pattern'] = ".+[-0-9a-zA-Z_\/\.\\\]+\.(raw|RAW|wiff|wiff\.scan)$"

        self.regex = re.compile(self.para['pattern'])

        self.set_para('simulate', False)
        self.para['source_path'] = os.path.normpath(source_path)
        self.para['target_path'] = os.path.normpath(target_path)
        self.para['min_time_diff'] = 2 * 3600 # 2.0 hours
        self.para['min_size'] = 100 * 1024 # 100 KBytes

        # setup logging
        hdlr_syslog = logging.handlers.SysLogHandler(address=("130.60.81.148", 514))
        
        formatter = logging.Formatter('%(name)s %(message)s')
        hdlr_syslog.setFormatter(formatter)

        self.logger.addHandler(hdlr_syslog)
        self.logger.setLevel(logging.INFO)

    def print_para(self):
        """ print class parameter setting """
        for k, v in self.para.items():
            sys.stdout.write("{0}\t=\t{1}\n".format(k, v))

    def set_para(self, key, value):
        """ class parameter setting """
        self.para[key] = value
        if key is 'pattern':
            self.regex = re.compile(self.para['pattern'])

    def sync(self, file_to_copy, func_target_mapping):
        """ default is printing only """
        sys.stdout.write("consider: '{0}'\n\t->'{1}'\n" \
            .format(file_to_copy, func_target_mapping(os.path.dirname(file_to_copy))))

    def run(self, func_target_mapping=lambda x: x):
        """
            main methode: does crawling, filtering, and starting the robocopy
            subprocess
        """

        self.print_para()

        self.logger.info("crawl source path = '{0}'" \
            .format(self.para['source_path']))
        try:
            os.chdir(self.para['source_path'])
        except:
            raise

        for (root, dirs, files) in os.walk(os.path.normpath('.'), topdown=False, followlinks=False, onerror=lambda e: sys.stdout.write("Error: {0}\n".format(e))):

            # BioBeamer filters
            files_to_copy = map(lambda f: os.path.join(root, f), files)
            files_to_copy = filter(self.regex.match, files_to_copy)
            files_to_copy = filter(lambda f: time.time() - os.path.getmtime(f) > self.para['min_time_diff'], files_to_copy)
            files_to_copy = filter(lambda f: os.path.getsize(f) > self.para['min_size'], files_to_copy)

            for file_to_copy in files_to_copy:
                self.sync(file_to_copy, func_target_mapping)

        self.logger.info("done")


    def exec_cmd(self, file_to_copy, cmd):
        """ system call """
        self.logger.info("consider: '{0}'".format(file_to_copy))
        self.logger.info("try to run: '{0}'".format(" ".join(cmd)))
        self.logger.info("getmtime={0}; getsize={1}". \
            format(time.time() - os.path.getmtime(file_to_copy), os.path.getsize(file_to_copy)))

        if self.para['simulate'] is True:
            self.logger.info("simulate is True. aboard.")
            return

        try:
            # todo(cp): check if this is really necessary
            os.chdir(self.para['source_path'])
            rbcpy_process = subprocess.Popen(" ".join(cmd), shell=True)
            return_code = rbcpy_process.wait()
            self.logger.info("robocopy return code: '{0}'".format(return_code))
            if return_code > 7:
                self.logger.warning("robocopy quit with return code highter than 7")
            rbcpy_process.terminate()

        except:
            self.logger.error("robocopy exception raised.")
            raise


class Robocopy(BioBeamer):
    """
    BioBeamer class using robocopy.exe

    the sync is done by using MS robocopy.exe or on UNIX by using rsync
    """
    def __init__(self, pattern=None, log_file="C:/Progra~1/BioBeamer/fgcz_biobeamer.log", source_path="D:/Data2San/", target_path="\\\\130.60.81.21\\Data2San"):
        """ just call the super class """
        super(Robocopy, self).__init__(pattern, log_file, source_path, target_path)
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
            self.para['robocopy_args'],
            os.path.dirname(file_to_copy),
            os.path.normpath("{0}/{1}" \
                .format(self.para['target_path'], target_sub_path)),
            os.path.basename(file_to_copy)
        ]
        self.exec_cmd(file_to_copy, cmd)

def map_data_analyst(path):
    """
    input:  'p1000/Data/selevsek_20150119'
    output: 'p1000/Proteomics/TRIPLETOF_1/selevsek_20150119'
    """

    pattern = ".*(p[0-9]+)\\\\Data\\\\([-0-9a-zA-Z_\.]+)$"
    regex = re.compile(pattern)
    match = regex.match(path)

    if match:
        return os.path.normpath("{0}/Proteomics/TRIPLETOF_1/{1}" \
            .format(match.group(1), match.group(2)))

    return None

class TestTargetMapping(unittest.TestCase):
    """
    run
        python -m unittest -v fgcz_biobeamer

    """
    def setUp(self):
        pass

    def test_tripletoff(self):
        desired_result = os.path.normpath('p1000/Proteomics/TRIPLETOF_1/selevsek_20150119')
        self.assertTrue(desired_result == map_data_analyst('p1000\Data\selevsek_20150119'))
        self.assertTrue(map_data_analyst('p1000\data\selevsek_20150119') is None)


if __name__ == "__main__":
    if str(socket.gethostname()) == 'fgcz-s-021':
        print socket.gethostname()
        BB = BioBeamer(
            source_path="/srv/www/htdocs/Data2San",
            target_path="/scratch/dump"
        )
        BB.set_para('pattern', ".+p1000.+QEXACTIVEHF_1.+\.raw")
        BB.set_para('simulate', True)
        BB.run(func_target_mapping=lambda x: "__{0}".format(x))

    # TRIPLETOF_1
    elif str(socket.gethostname()) == 'fgcz-i-180':
        BB = Robocopy(
            source_path="D:/Analyst Data/Projects/",
            target_path="\\\\130.60.81.21\\Data2San"
        )
        BB.set_para('min_time_diff', 3600 * 3)
        BB.set_para('simulate', False)
        BB.set_para('robocopy_args', "/E /Z /NP /LOG+:C:\\Progra~1\\BioBeamer\\robocopy.log")
        BB.run(func_target_mapping=map_data_analyst)

    # QEXACTIVEHF_1, FUSION_2, QEXACTIVE_2
    else:
        BB = Robocopy(
            source_path="D:/Data2San/",
            target_path="\\\\130.60.81.21\\Data2San"
        )
        BB.set_para('simulate', False)
        BB.run()

sys.stdout.write("done. exit 0\n")
time.sleep(5)
sys.exit(0)
