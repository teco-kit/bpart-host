# Copyright (c) 2013, 2014 All Right Reserved, TECO, http://www.teco.edu
#
# THIS CODE AND INFORMATION ARE PROVIDED "AS IS" WITHOUT WARRANTY OF ANY 
# KIND, EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A
# PARTICULAR PURPOSE.
#
# @author: Carsten Strunk, Matthias Berning
# @email: strunk@teco.edu, berning@teco.edu
# @date: 2014/05/23

'''
This module contains some global configuration information.
'''

import logging

LOGFILE = "bpart.log"
LOGLEVEL = logging.DEBUG # must be one of the loglevels provided by the logging module
#LOGLEVEL = logging.INFO

CUMULUS_URL = 'http://cumulus.teco.edu:52001/data/'

#List of the addresses of the bparts to which you wish to connect
#Must be in the format "xx:xx:xx:xx:xx:xx"
DEVICES = ["00:07:80:78:F5:C3","00:07:80:78:FA:5A","00:07:80:78:F5:C9"]
#DEVICES = ["00:07:80:78:FA:5A"]
