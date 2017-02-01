import os
import base64
import subprocess


class Drive:
    def __init__(self, logger, networkPath="\\\\fgcz-ms.fgcz-net.unizh.ch\\Data2San",
                 user="FGCZ-NET\BioBeamer",
                 password="cGFzc3dvcmQ="):
        self._networkPath = networkPath
        self._user = user
        self._password = base64.b64decode(password)
        self._logger = logger

    def mapDrive(self):
        winCMD = "net use {networkPath} {password} /user:{user}".format(
            networkPath=self._networkPath,
            password=self._password, user=self._user)

        p = subprocess.Popen(winCMD, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        out, err = p.communicate()
        if not err == "":
            self._logger.error(winCMD)
            self._logger.error(err.replace("\r\n", " "))
        return p.returncode

    def unmapDrive(self):
        winCMD = "net use {networkPath} /delete".format(
            networkPath=self._networkPath)
        self._logger.info(winCMD)
        p = subprocess.Popen(winCMD, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        out, err = p.communicate()
        if not err == "":
            self._logger.error(winCMD)
            self._logger.error(err)
        return p.returncode
