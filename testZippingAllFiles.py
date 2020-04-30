import glob
import os.path
import MyLog
import logging
import pathlib
import re

def get_all_files(source_path, logger):
    '''
    :param source_path:
    :param logger:
    :return: return list of files in directory
    '''
    all_files = []
    for (root, dirs, files) in os.walk(source_path,
                                       topdown=False, followlinks=False,
                                       onerror=lambda e: logger.error("os.walk: {0}\n".format(e))):
        # BioBeamer filters
        files_to_copy = map(lambda f: os.path.join(root, f), files)
        all_files += files_to_copy

    return all_files


logger = MyLog.MyLog()
logger.set_log_level(logging.ERROR)
files_to_copy = get_all_files("D:/Data2San", logger)

xx = map(lambda file: str(pathlib.Path(file).parent), files_to_copy)
xx = list(set(xx))

path = ".+\.PRO\\Data\\[0-9]{8}[-0-9a-zA-Z_\/\.\\]*"
regex = re.compile(".+\.PRO\\Data\\[0-9]{8}[-0-9a-zA-Z_\\\/\.]*")
xx = filter(regex.match, xx)
len(xx)

