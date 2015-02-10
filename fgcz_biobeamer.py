#!/usr/bin/python
# -*- coding: latin1 -*-

"""
$HeadURL$
$Id$
$Date$

Copyright 2015
Christian Panse <cp@fgcz.ethz.ch>
Christian Trachsel <christian.trachsel@fgcz.uzh.ch>
"""

import os
import time
import re
import sys
import subprocess
import logging 
import re
import socket
import unittest


class BioBeamer:
    """
    class for syncinging data from instrument PC to archive

    the sync is done by using MS robocopy.exe or on UNIX by using rsync
    """
    def __init__(self, pattern=None, log_file="C:/Progra~1/BioBeamer/biobeamer.log", source_path="D:/Data2San/", target="\\\\130.60.81.21\\Data2San"):
        if pattern is None:
            pattern = ".+[-0-9a-zA-Z_\/\.\\\]+\.(raw|RAW|wiff|wiff\.scan)$"

        self.regex = re.compile(self.para['pattern'])

        self.set_para('simulate', False)
        self.para['source_path'] = os.path.normpath(source_path)
        self.para['target_path'] = os.path.normpath(target_path)
        self.para['min_time_diff'] = 2 * 3600 # 2.0 hours
        self.para['min_size'] = 100 * 1024 # 100 KBytes
        self.para['logging_file'] = os.path.normpath(log_file)

        # setup logging
        if not os.path.exists(self.logging_file):
            sys.stdout.write("'{0}' does not exist. aboard.".format(os.path.exists(self.logging_file)))
            sys.exit(1)

        self.logger = logging.getLogger('BioBeamer')
        hdlr = logging.FileHandler(self.logging_file)
        formatter = logging.Formatter(
            '%(asctime)s %(levelname)s %(message)s', 
            datefmt="%Y-%m-%d %H:%M:%S")
        hdlr.setFormatter(formatter)
        self.logger.addHandler(hdlr)
        self.logger.setLevel(logging.INFO)

    def set_robocopy_args(self, robocopy_args="/E /Z /NP /LOG+:C:\\Progra~1\\BioBeamer\\robocopy_log.txt"):
        self.robocopy_args = robocopy_args

    def set_simulate(self, sim=True):
        self.simulation_mode = sim

    def set_min_time_diff(self, min_time_diff=360000):
        """ set min modified time for os.path.getmtime """
        self.min_time_diff = min_time_diff

    def set_min_size(self, min_size=100000):
        """ set min file size """
        self.min_size = min_size

    def robocopy(self, file_to_copy, func_target_mapping):
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
            "robocopy.exe", self.robocopy_args,
            os.path.dirname(file_to_copy), 
            os.path.normpath("{0}/{1}".format(self.target, target_sub_path)),
            os.path.basename(file_to_copy)
        ]

        self.logger.info("consider: '{0}'".format(file_to_copy))
        self.logger.info("try to run: '{0}'".format(" ".join(cmd)))
        self.logger.info(
            "getmtime={0}; getsize={1}".format(
                time.time() - os.path.getmtime(file_to_copy), 
                os.path.getsize(file_to_copy)))

        if self.simulation_mode is True:
            return True

        try:
            # todo(cp): check if this is really necessary
            os.chdir(self.source_path)
            rbcpy_process = subprocess.Popen(" ".join(cmd), shell=True)
            return_code = rbcpy_process.wait()
            self.logger.info("robocopy return code: '{0}'".format(return_code))
            if return_code > 7:
                self.logger.warning("robocopy quit with return code highter than 7")
            rbcpy_process.terminate()

        except:
            self.logger.error("robocopy exception raised.")
            raise

    def run(self, func_target_mapping=lambda x: x):
        """
            main methode: does crawling, filtering, and starting the robocopy 
            subprocess
        """

        self.logger.info("crawl source path = '{0}'".format(self.source_path))
        try:
            os.chdir(self.source_path)
        except:
            raise

        for (root, dirs, files) in os.walk(
                os.path.normpath('.'), 
                topdown=False, 
                followlinks=False, 
                onerror=lambda e: sys.stdout.write("Error: {0}\n".format(e))):

            # BioBeamer filters
            files_to_copy = map(lambda f: os.path.join(root, f), files)
            files_to_copy = filter(self.regex.match, files_to_copy)
            # todo(cp): check if file is closed
            files_to_copy = filter(lambda f: time.time() - os.path.getmtime(f) > self.min_time_diff, files_to_copy)
            files_to_copy = filter(lambda f: os.path.getsize(f) > self.min_size, files_to_copy)

            for file_to_copy in files_to_copy:
                self.robocopy(file_to_copy, func_target_mapping)

        self.logger.info("done")

def mapping_data_analyst(path):
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

class TestNameMapping(unittest.TestCase):
    """
    run
        python -m unittest -v fgcz_biobeamer

    """
    def setUp(self):
        pass    

    def test_tripletoff(self):
        desired_result = os.path.normpath('p1000/Proteomics/TRIPLETOF_1/selevsek_20150119')
        self.assertTrue(desired_result == mapping_data_analyst('p1000\Data\selevsek_20150119'))
        self.assertTrue(mapping_data_analyst('p1000\data\selevsek_20150119') is None)


if __name__ == "__main__":
    if str(socket.gethostname()) == 'fgcz-s-021':
        print socket.gethostname()
        BB = BioBeamer(
            source_path="/srv/www/htdocs/Data2San", 
            target="/scratch/dump",
            log_file="/scratch/dump/biobeamer.log") 
        BB.set_simulate(True)
        BB.run(func_target_mapping=lambda x: "__{0}".format(x))

    # TRIPLETOF_1
    elif str(socket.gethostname()) == 'fgcz-i-180':
        BB = BioBeamer(
            source_path="D:/Analyst Data/Projects/", 
            target="\\\\130.60.81.21\\Data2San", 
            log_file="C:/Progra~1/BioBeamer/biobeamer.log") 
        BB.set_simulate(False)
        BB.set_min_time_diff(3*3600)
        BB.set_min_size(500000)        
        BB.set_robocopy_args(robocopy_args="/E /Z /NP /LOG+:C:\\Progra~1\\BioBeamer\\robocopy_log.txt")
        BB.run(func_target_mapping=mapping_data_analyst)

    # QEXACTIVEHF_1, FUSION_2
    else:
        BB = Robocopy(source_path = "D:/Data2San/", target_path = "\\\\130.60.81.21\\Data2San", log_file = "C:/Progra~1/BioBeamer/fgcz_biobeamer.log") 
        BB.set_para('simulate', False)
        BB.run()
sys.stdout.write("done. exit 0\n")
time.sleep(5)
sys.exit(0)
