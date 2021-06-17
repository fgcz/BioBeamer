import os
import re
from datetime import date

def map_data_G2HD_2(path, logger):
    """
    input:
    output:
    """

    pattern_dest = "^(\\\\\\\\fgcz-biobeamer.uzh.ch\\\\Data2San\\\\p[0-9]{1,4}\\\\[A-Za-z]{1,20}\\\\[A-Z0-9_]+)(\.PRO\\\\Data\\\\)([0-9]{8,8})(.+)$"
    regex_dest = re.compile(pattern_dest)
    match_dest = regex_dest.match(path)

    if match_dest:
        mg_path = match_dest.group(1)
        mg_date = match_dest.group(3)
        mg_folder = match_dest.group(4)
        path = os.path.normpath(
            "{path}\\analytic_{date}\\{date}{folder}".format(
                path=mg_path,
                date=mg_date,
                folder=mg_folder))
        return path
    else:
        return None

def map_data_order_QDA_G2HD(path, logger):
    res = map_data_QDA(path, logger)
    if res is None:
        res = map_data_G2HD_2(path, logger)
        if res is None:
            logger.error('Could not apply mapping function to {path}. Raising exception'.format(path=path))
            raise ValueError('Could not apply mapping function')

    return res


def map_data_QDA(path, logger):
    """
    input: '\\\\fgcz-biobeamer.fgcz-net.unizh.ch\\Data2San\\p65\\Proteomics\\QDA_1.PRO\\Data\\20201015_C22916_BSA.raw'


    input: "\\fgcz-biobeamer.uzh.ch\\Data2San\p65\Proteomics\QDA_1.PRO\Data\20201021_C22959_P16G08-Atto488_1.raw"
     output: "\\fgcz-biobeamer.uzh.ch\Data2San\p22959\Proteomics\QDA_1\analytic_20201021\20201021_C22959_P16G08-Atto488_1.raw
    """
    pattern_dest = "^(\\\\\\\\fgcz-biobeamer.uzh.ch\\\\Data2San\\\\)(p[0-9]{1,4})(\\\\[A-Za-z]{1,20}\\\\[A-Z0-9_]+)(\.PRO\\\\Data\\\\)([0-9]{8,8})_(C[0-9]{3,5})_(.+)$"
    regex_dest = re.compile(pattern_dest)
    match_dest = regex_dest.match(path)

    if match_dest:
        mg_path_1 = match_dest.group(1)
        mg_path_2 = match_dest.group(3)
        mg_date = match_dest.group(5)
        mg_container = match_dest.group(6)
        mg_folder = match_dest.group(7)
        project = mg_container.replace("C", "p")

        path = os.path.normpath(
            "{path1}{container}{path2}\\analytic_{date}\\{date}_{mg_container}_{folder}".format(
                path1=mg_path_1,
                container=project,
                path2=mg_path_2,
                date=mg_date,
                mg_container=mg_container,
                folder=mg_folder))
        return path
    else:
        return None

def map_data_for_container(dest_path, logger):
    """
    input: '\\\\fgcz-biobeamer.fgcz-net.unizh.ch\\Data2San\\20190206HM_11728_C6CYS.raw\\_PROC003.SIG'
    '\\\\fgcz-biobeamer.uzh.ch\\Data2San\\orders\\Proteomics\\QEXACTIVE_1\\analytic_20200923\\20200923_004_C22687_S267154_HA-IgG__A.raw'

    output: p65/Proteomics/G2HD_2/schesnov_20190000
    """

    pattern_dest = "^\\\\\\\\fgcz-biobeamer.uzh.ch\\\\Data2San\\\\orders\\\\[A-Za-z]{1,20}\\\\[A-Z]{1,20}_[0-9]{1,2}\\\\analytic_[0-9]{8}[_0-9A-Za-z]*\\\\[_0-9A-Za-z]+_(C[0-9]{1,6})_.+$"
    regex_dest = re.compile(pattern_dest)
    match_dest = regex_dest.match(dest_path)

    if match_dest:
        order_id = match_dest.group(1)
        order_id = order_id.replace("C", "p")
        dest_path = dest_path.replace("orders", order_id)

        dest_path = os.path.normpath(dest_path)
        return dest_path
    else:
        return dest_path


def map_data_analyst_tripletof_1(path, logger):
    """
    input:  'p1000/Data/selevsek_20150119'
    output: 'p1000/Proteomics/TRIPLETOF_1/selevsek_20150119'
    """

    pattern = ".*(p[0-9]+)\\\\Data\\\\([-0-9a-zA-Z_\\\.]+)$"
    regex = re.compile(pattern)
    match = regex.match(path)

    if match:
        return os.path.normpath("{0}/Proteomics/TRIPLETOF_1/{1}".format(match.group(1), match.group(2)))
    else:
        logger.error('Could not apply mapping function. Raising exception')
        raise ValueError('Could not apply mapping function')
    return None


def map_data_analyst_qtrap_1(path, logger):
    """
    input:  'p1000/Data/selevsek_20150119'
    output: 'p1000/Proteomics/TRIPLETOF_1/selevsek_20150119'
    """
    pattern = "(.*p[0-9]+)\\\\Data\\\\([-0-9a-zA-Z_\\\.]+)$"
    regex = re.compile(pattern)
    match = regex.match(path)

    if match:
        res = "{0}\\Proteomics\\QTRAP_1\\{1}".format(match.group(1), match.group(2))
        return res
    else:
        logger.error('Could not apply mapping function. Raising exception')
        raise ValueError('Could not apply mapping function')
    return None


def test_mapping_function(logger):
    '''
    Test mapping
    :return: nil
    '''
    tmp = '\\\\130.60.81.21\\Data2San\\p1001\\Data\\selevsek_20150119\\testdumm.raw'
    tmp2 = '\\\\130.60.81.21\\Data2San\\p1001\\Data\\selevsek_20150119\\testdumm2.wiff'
    tmp_ = map_data_analyst_qtrap_1(tmp, logger)
    if tmp_ != 'p1001\\Proteomics\\QTRAP_1\\selevsek_20150119\\testdumm.raw':
        print("mapping failed")
    tmp2_ = map_data_analyst_qtrap_1(tmp2, logger)
    if tmp2_ != 'p1001\\Proteomics\\QTRAP_1\\selevsek_20150119\\testdumm2.wiff':
        print("mapping failed")
