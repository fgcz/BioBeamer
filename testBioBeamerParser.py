"""
$HeadURL: http://fgcz-svn.unizh.ch/repos/fgcz/stable/proteomics/BioBeamer/fgcz_biobeamer.py $
$Id: fgcz_biobeamer.py 7229 2015-02-05 09:46:15Z cpanse $
$Date: 2015-02-05 10:46:15 +0100 (Thu, 05 Feb 2015) $

Copyright 2015
Christian Panse <cp@fgcz.ethz.ch>
Christian Trachsel <christian.trachsel@fgcz.uzh.ch>
Witold E. Wolski <wew@fgcz.ethz.ch>

"""

import unittest
from fgcz_biobeamer import BioBeamerParser


class TestBioBeamerParser(unittest.TestCase):
    """
    """

    PARAM_TEST = {'target_path': '/srv/www/htdocs', 'name': 'test-configuration',
             'pattern': '^.{0,2}p[0-9]+.[MP][-0-9a-zA-Z_\\/\\.]+\\.(raw|RAW|wiff|wiff\\.scan)$',
             'source_path': '/srv/www/htdocs/Data2San',
             'min_size': 1024, 'max_time_diff': 2419200,
             'robocopy_args': '',
             'simulate': True,
             'min_time_diff': 10800,
             'func_target_mapping': ''}

    def test_beam_and_check(self):
        bio_beamer_parser = BioBeamerParser(xml="BioBeamer.xml", xsd="BioBeamer.xsd", hostname="test-configuration")
        param = bio_beamer_parser.parameters
        assert self.PARAM_TEST == param

    def setUp(self):
        pass

    def tearDown(self):
        pass