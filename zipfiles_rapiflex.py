import os
import MyLog
import biobeamer2
import re

from os.path import isfile, join

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
    logger = MyLog.MyLog()

    mypath = "D:/Data2San/"
    dirs = get_dirs_zip(mypath, maxdepth=3)
    dirs = [k for k in dirs if os.path.isdir(k)]

    for dir in dirs:
        bname = os.path.basename(dir)
        shutil.make_archive(dir,'zip', dir)
        shutil.rmtree(dir, ignore_errors=False, onerror=handleRemoveReadonly)

