import os
import base64
# from win32all import win32wnet


class Drive:

    def __init__(self,logger, networkPath="\\\\fgcz-ms.fgcz-net.unizh.ch\\Data2San",
                 user="FGCZ-NET\BioBeamer",
                 password="cGFzc3dvcmQ=" ):
        self._networkPath = networkPath
        self._user = user
        self._password = base64.b64decode(password)
        self._logger = logger

    def mapDrive(self):
        tmp = "net use {networkPath} {password} /user:{user}".format(
            networkPath=self._networkPath,
            password=self._password, user=self._user)
        self._logger.info(tmp)
        os.system(tmp)


    def unmapDrive(self):
        tmp = "net use {networkPath} /delete".format(
            networkPath=self._networkPath)
        self._logger.info(tmp)
        os.system(tmp)


