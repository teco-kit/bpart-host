'''
This module contains some global configuration information.
'''

import logging

LOGFILE = "bpart.log"
LOGLEVEL = logging.DEBUG # must be one of the loglevels provided by the logging module
#LOGLEVEL = logging.INFO

READ_INTERVAL = 10

CUMULUS_URL = 'http://cumulus.teco.edu:52001/data/'

#List of the addresses of the bparts to which you wish to connect
#Must be in the format "xx:xx:xx:xx:xx:xx"
DEVICES = ["00:07:80:78:F5:C3","00:07:80:78:FA:5A"]
