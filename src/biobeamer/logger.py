import logging


class MyLog:
    def __init__(self, name="BioBeamer"):
        self.logger = logging.getLogger(name)
        self.formatter = logging.Formatter('%(name)s - %(asctime)s - %(levelname)s - %(message)s')

    def add_file(self, filename="./log/biobeamer.log", level=logging.DEBUG):
        file_handler = logging.FileHandler(filename)
        file_handler.setLevel(level)
        file_handler.setFormatter(self.formatter)
        self.logger.addHandler(file_handler)

    def add_syshandler(self, address=("130.60.81.148", 514), level=logging.DEBUG):
        syslog_handler = logging.handlers.SysLogHandler(address=address)
        syslog_handler.setLevel(level)
        syslog_handler.setFormatter(self.formatter)
        self.logger.addHandler(syslog_handler)

    def set_log_level(self, level=logging.INFO):
        self.logger.setLevel(level)
