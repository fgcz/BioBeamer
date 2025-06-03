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
import unittest

from src.BioBeamerParser import BioBeamerParser
from src.MyLog import MyLog

xml_path = os.path.abspath("../configs/BioBeamerTest.xml")
xsd_path = os.path.abspath("../configs/BioBeamer2.xsd")
if not os.path.exists(xml_path):
    raise FileNotFoundError(f"XML configuration file not found: {xml_path}")
if not os.path.exists(xsd_path):
    raise FileNotFoundError(f"XSD configuration file not found: {xsd_path}")

xml_url = f"file://{xml_path}"
xsd_url = f"file://{xsd_path}"


class TestBioBeamerParser(unittest.TestCase):
    """
    """
    PARAM_TEST = {
        'name': 'test_configuration',
        'instrument': 'test_instrument',
        'min_size': 1024,
        'min_time_diff': 10800,
        'max_time_diff': 2419200,
        'max_time_delete': 1209600,
        'time_out': 3600,
        'simulate_copy': True,
        'simulate_delete': True,
        'func_target_mapping': '',
        'robocopy_mov': False,
        'pattern': r'^.{0,2}p[0-9]+.[MP][-0-9a-zA-Z_\\/\\.]+\\.(raw|RAW|wiff|wiff\\.scan)$',
        'source_path': '/srv/www/htdocs/Data2San',
        'target_path': '/srv/www/htdocs',
        'copied_files_log': './log/test_copied_files.txt',
        'syshandler_adress': 'ms-fgcz.uzh.ch',
        'syshandler_port': 514,
    }

    def test_beam_and_check(self):
        logger = MyLog()

        bio_beamer_parser = BioBeamerParser(xml=xml_url,
                                            xsd=xsd_url,
                                            hostname="test_configuration",
                                            logger=logger.logger)
        param = bio_beamer_parser.parameters
        self.assertEqual(param, self.PARAM_TEST, "Parameters from BioBeamerParser do not match expected values.")

    def setUp(self):
        pass

    def tearDown(self):
        pass
