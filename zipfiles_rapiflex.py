import logging
import socket
import sys
import BioBeamerParser
import MyLog
from datetime import datetime
import re

import os,string
import shutil
import errno, stat

def get_dirs_zip(path = "D:/Data2San",maxdepth = 3):
    path = os.path.normpath(path)
    res = []
    for root, dirs, files in os.walk(path, topdown=True):
        depth = root[len(path) + len(os.path.sep):].count(os.path.sep)
        if depth == maxdepth:
            # We're currently two directories in, so all subdirs have depth 3
            res += [os.path.join(root, d) for d in dirs]
            dirs[:] = [] # Don't recurse any deeper
    return(res)


def handleRemoveReadonly(func, path, exc):
  excvalue = exc[1]
  if func in (os.rmdir, os.remove) and excvalue.errno == errno.EACCES:
      os.chmod(path, stat.S_IRWXU| stat.S_IRWXG| stat.S_IRWXO) # 0777
      func(path)
  else:
      raise

if __name__ == "__main__":
    host = socket.gethostname()
    configuration_url = "file:///c:/FGCZ/BioBeamer"
    if len(sys.argv) >= 3:
        configuration_url = sys.argv[1]
        depth = int(sys.argv[2])
    else:
        print("need folder depth")
        exit(1)


    biobeamer_xsd = "{0}/BioBeamer2.xsd".format(configuration_url)
    biobeamer_xml = "{0}/BioBeamer2.xml".format(configuration_url)

    host = socket.gethostname()
    logger = MyLog.MyLog()
    now = datetime.now().strftime("%Y%m%d_%H%M%S")  # current date and time
    file = "log/biobeamer_{date}.log".format(date=now)
    logger.add_file(filename=file, level=logging.DEBUG)
    logger.logger.info("\n\n\nStarting new Biobeamer!")
    logger.logger.info("retrieving config from {} for hostname {}".format(biobeamer_xml, host))
    bio_beamer_parser = BioBeamerParser.BioBeamerParser(biobeamer_xsd, biobeamer_xml, hostname=host, logger=logger.logger)


    mypath = "D:/Data2San/"
    dirs = get_dirs_zip(mypath, maxdepth=depth)
    dirs = [k for k in dirs if os.path.isdir(k)]

    pattern = bio_beamer_parser.parameters['pattern']
    pattern = pattern.replace("\\.(zip)","")
    dirs = [k for k in dirs if os.path.isdir(k)]
    print(len(dirs))
    dirspatt = [k for k in dirs if re.match(pattern,k)]
    notdirs = [k for k in dirs if None == re.match(pattern, k)]
    print(len(dirspatt))

    textfile = open("AAA_folders_not_compressed.txt", "w")
    for element in notdirs:
        textfile.write(element + "\n")
    textfile.close()


    if not bio_beamer_parser.parameters['simulate_copy']:
        for dir in dirs:
            shutil.make_archive(dir,'zip', dir)
            shutil.rmtree(dir, ignore_errors=False, onerror=handleRemoveReadonly)

