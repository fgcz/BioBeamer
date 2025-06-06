import urllib
import urllib.request
from lxml import etree
import re
import os
import sys


class BioBeamerParser(object):
    """
    class for syncing data from instrument PC to archive
    """

    parameters = {
        "simulate_copy": False,
        "simulate_delete": True,
        "min_time_diff": 2 * 3600,
        "max_time_diff": 24 * 3600 * 7 * 4,
        "max_time_delete": 24 * 3600 * 7 * 2,
        "min_size": 100 * 1024,
        "source_path": "D:/Data2San/",
        "target_path": "\\\\130.60.81.21\\Data2San",
        "time_out": 3,
        "copied_files_log": "./log/copied_files.txt",
        "tool": "robocopy",  # default tool
    }

    results = []

    def __init__(self, xsd, xml, hostname, logger):
        """
        :param xsd: BioBeamer.xsd
        :param xml: BioBeamer.xml
        :return:
        """
        from pathlib import Path
        import urllib.parse

        self.logger = logger
        # Validate XML and XSD paths
        if not xml:
            self.logger.error("XML path/URL is empty!")
            raise ValueError("XML path/URL must not be empty")
        if not xsd:
            self.logger.error("XSD path/URL is empty!")
            raise ValueError("XSD path/URL must not be empty")

        # Convert to file URL if not already a URL
        def ensure_url(path):
            if urllib.parse.urlparse(path).scheme in ("http", "https", "file"):
                return path
            return Path(path).absolute().as_uri()

        xml_url = ensure_url(xml)
        xsd_url = ensure_url(xsd)
        self.logger.info(f"Resolved XML URL: {xml_url}")
        self.logger.info(f"Resolved XSD URL: {xsd_url}")
        # read config files from url
        try:
            f = urllib.request.urlopen(xml_url)
            xml = f.read()

            f = urllib.request.urlopen(xsd_url)
            xsd = f.read()

        except Exception as e:
            self.logger.error("can not fetch xml or xsd information")
            self.logger.error(f"XML URL: {xml_url}, XSD URL: {xsd_url}")
            self.logger.error(f"Exception: {e}")
            raise

        schema = etree.XMLSchema(etree.XML(xsd))

        try:
            parser = etree.XMLParser(remove_blank_text=True, schema=schema)
            xml_bio_beamer = etree.fromstring(xml, parser)

        except:
            self.logger.error("config xml '{0}' can not be parsed.".format(xml))
            raise

        found_host_config = False
        # init para dictionary
        for i in xml_bio_beamer:
            if i.tag == "host" and "name" in i.attrib.keys():
                pass
            else:
                continue
            att_hostname = i.attrib["name"].lower()
            if att_hostname == hostname.lower():
                for k in i.attrib.keys():
                    if k == "target_path":
                        self.parameters[k] = i.attrib[k]
                    elif k == "source_path":
                        self.parameters[k] = os.path.normpath(i.attrib[k])
                    elif k == "pattern":
                        self.parameters[k] = i.attrib[k]
                        try:
                            self.regex = re.compile(self.parameters["pattern"])
                        except:
                            self.logger.error("re.compile pattern failed.")
                            raise
                    elif k == "simulate_copy":
                        if i.attrib[k] == "false":
                            self.parameters[k] = False
                        else:
                            self.parameters[k] = True
                    elif k == "simulate_delete":
                        if i.attrib[k] == "false":
                            self.parameters[k] = False
                        else:
                            self.parameters[k] = True
                    elif k == "robocopy_mov":
                        if i.attrib[k] == "false":
                            self.parameters[k] = False
                        else:
                            self.parameters[k] = True
                    else:
                        try:
                            self.parameters[k] = int(i.attrib[k])
                        except ValueError:
                            self.parameters[k] = i.attrib[k]
                found_host_config = True

        if found_host_config is False:
            msg = "no host configuration could be found in '{0}'.".format(xml_url)
            print(msg)
            self.logger.error(msg)
            sys.exit(1)

    def print_para(self):
        """print class parameter setting"""
        for k, v in self.parameters.items():
            sys.stdout.write("{0}\t=\t{1}\n".format(k, v))

    def log_para(self):
        self.logger.info("Logging bio beamer paramters:")
        for k, v in self.parameters.items():
            self.logger.info("{0}\t=\t{1}".format(k, v))
        self.logger.info("END PARAMETERS\n")

    def set_para(self, key, value):
        """class parameter setting"""
        self.parameters[key] = value
        if key == "pattern":
            self.regex = re.compile(self.parameters["pattern"])
