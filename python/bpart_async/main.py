#!/usr/bin/python
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
This is the main module of the BPart Tool.
It connects to all devices listed in config.
Then it receives notifications from the connected devices which are sending their current sensor values.
These values are then send to TecO's CUMULUS
'''
import config
from bpart import BPart
import logging


def startBParts(macs):
	'''
	Start all BParts listed in config
	'''
	bpartList = []
	for mac in macs:
		bpart = BPart(mac)
		bpart.start()
		bpartList.append(bpart)
	return bpartList

def stopBParts(bpartList):
	'''
	Disconnect from all the bparts
	'''
	for bpart in bpartList:
		bpart.disconnect()

if  __name__ == "__main__":
	# Empty logfile
	with open(config.LOGFILE, 'w'):
		pass

	logging.basicConfig(format="%(asctime)s:%(levelname)s:%(message)s",filename=config.LOGFILE, level=config.LOGLEVEL)
	
	bparts = startBParts(config.DEVICES)
	raw_input('--> Press any Button to exit')
	stopBParts(bparts)
		

