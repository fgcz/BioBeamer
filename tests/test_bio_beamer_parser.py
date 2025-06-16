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
import pytest
import importlib.resources

from biobeamer2.BioBeamerParser import BioBeamerParser
from biobeamer2.MyLog import MyLog


def test_beam_and_check():
    logger = MyLog()
    with importlib.resources.path(
        "biobeamer2.configs", "BioBeamerTest.xml"
    ) as xml_path, importlib.resources.path(
        "biobeamer2.configs", "BioBeamer2.xsd"
    ) as xsd_path:
        xml_url = f"file://{xml_path}"
        xsd_url = f"file://{xsd_path}"
        bio_beamer_parser = BioBeamerParser(
            xml=xml_url,
            xsd=xsd_url,
            hostname="test_configuration",
            logger=logger.logger,
        )
        param = bio_beamer_parser.parameters
        assert param["name"] == "test_configuration"
        assert param["instrument"] == "test_instrument"
        assert param["min_size"] == 1024
        assert param["min_time_diff"] == 10800
        assert param["max_time_diff"] == 2419200
        assert param["max_time_delete"] == 1209600
        assert param["time_out"] == 3600
        assert param["simulate_copy"] is True
        assert param["simulate_delete"] is True
        assert param["func_target_mapping"] == ""
        assert param["robocopy_mov"] is False
        assert (
            param["pattern"]
            == r"^.{0,2}p[0-9]+.[MP][-0-9a-zA-Z_\\/\\.]+\\.(raw|RAW|wiff|wiff\\.scan)$"
        )
        assert param["source_path"] == "/srv/www/htdocs/Data2San"
        assert param["target_path"] == "/srv/www/htdocs"
        assert param["copied_files_log"] == "./log/test_copied_files.txt"
        assert param["syshandler_adress"] == "ms-fgcz.uzh.ch"
        assert param["syshandler_port"] == 514
        assert param["tool"] == "scp"
