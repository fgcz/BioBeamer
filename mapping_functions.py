import os
import re


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
    tmp_ = mapping_functions.map_data_analyst_qtrap_1(tmp, logger)
    if tmp_ != 'p1001\\Proteomics\\QTRAP_1\\selevsek_20150119\\testdumm.raw':
        print("mapping failed")
    tmp2_ = mapping_functions.map_data_analyst_qtrap_1(tmp2, logger)
    if tmp2_ != 'p1001\\Proteomics\\QTRAP_1\\selevsek_20150119\\testdumm2.wiff':
        print("mapping failed")
