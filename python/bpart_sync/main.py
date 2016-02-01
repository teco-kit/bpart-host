#!/usr/bin/python
'''
This Module connects to all bParts listed in config.DEVICES
It periodically reads out the sensor data supplied by the bparts

'''




import config
import logging
from threading import Thread
from Queue import Queue
from btle import BTLEException
from bpart import BPart
import time
import json
import urllib2

class Gateway(Thread):
	'''
	The Gateway class is responsible for reading the sensor data of the bParts.
	It's thread polls the bParts.
	'''

	def __init__(self, connector=None):
		Thread.__init__(self)
		self.disconnectedDevices = config.DEVICES
		self.connectedDevices = dict()
		self.deviceQueue = Queue()
		self.running = True
		self.BTConnector = connector

	def _createJSONString(self, temperature, humidity, light,(x,y,z)):
		jsonString = json.dumps({'data':{'Temperature':{'value':str(temperature), 'unit':'degC'},'Humidity':{'value':str(humidity), 'unit':'Percent'},'Light':{'value':str(light), 'unit':'Number'},'AccelX':{'value':str(x),'unit':'Number'},'AccelY':{'value':str(y),'unit':'Number'},'AccelZ':{'value':str(z),'unit':'Number'}}})
		return jsonString

	def _sendDataToCumulus(self, mac,jsonString):
		url = config.CUMULUS_URL+mac.replace(':','')
		try:
			logging.debug("Created URL: {0}".format(url))
			req = urllib2.Request(url, jsonString, {'Content-Type': 'application/x-www-form-urlencoded' })
			req.get_method = lambda: 'PUT'
			f = urllib2.urlopen(req)
			response = f.read()
			logging.debug("CUMULUS Response: {0}".format(response))
			f.close()
		except urllib2.HTTPError as h:
			logging.warning("Error while sending data to {0}: HTTP Error {1}: {2}".format(url,h.code,h.msg))

	def run(self):
		logging.info("Gateway Thread Started")
		while self.running:
			while not self.deviceQueue.empty():
				device = self.deviceQueue.get()
				self.connectedDevices[device.deviceAddr] = device

			macsToDelete = []
			for mac, device in self.connectedDevices.iteritems():
				try:
					temperature = device.Temperature.read()
					humidity = device.Humidity.read()
					light = device.Light.read()
					(x,y,z) = device.Acceleration.read()

					jsonstring = self._createJSONString(temperature, humidity, light,(x,y,z))
					logging.debug("Created JSON for {0}: {1}".format(mac,jsonstring))

					self._sendDataToCumulus(mac,jsonstring)
					
					time.sleep(config.READ_INTERVAL)
				except BTLEException:
					logging.warning("Device %s can no longer be reached" % mac)
					macsToDelete.append(mac)

			
			for mac in macsToDelete:
				del self.connectedDevices[mac]
				self.BTConnector.addDisconnectedDevice(mac)
		
		#Cleanup on shutdown
		for mac,device in self.connectedDevices.iteritems():
			try:
				device.disconnect()
				del device
			except BTLEException:
				logging.warning("Could not disconnect device %s" % mac)


	
	def addConnectedDevice(self, device):
		'''
		This method provides an interface for the BTDeviceConnector class.
		The device argument must be of type BPart (see bpart.py).
		'''
		self.deviceQueue.put(device)

	def stop(self):
		self.running = False


class BTDeviceConnector(Thread):
	'''
	This class tries to connect to alle devicse listed in config.DEVICES.
	Once a device has been connected it is passed to the Gateway class.
	It never stops trying to connect to the bparts.
	'''

	def __init__(self, gateway=None):
		Thread.__init__(self)
		self.disconnectedDevices = set(config.DEVICES)
		self.deviceQueue = Queue()
		self.running = True
		self.Gateway = gateway

	def run(self):
		logging.info("BTDeviceConnector thread started")
		while self.running:
			while not self.deviceQueue.empty():
				self.disconnectedDevices.append(self.deviceQueue.get())

			macsToRemove = []
			for mac in self.disconnectedDevices:
				try:
					device = BPart(mac)
					self.Gateway.addConnectedDevice(device)
					macsToRemove.append(mac)
					logging.info("Connected to Device %s" % mac)
				except BTLEException:
					logging.warning("Could not connect to device %s" % mac)

			for mac in macsToRemove:
				self.disconnectedDevices.remove(mac)
	
	def addDisconnectedDevice(self, mac):
		'''
		This method provides an interface for the Gateway class which can pass back the mac addresses
		of the bparts which can no longer be reached. mac must be a string.
		'''
		self.deviceQueue.put(mac)

	def setGateway(self, gateway):
		'''
		Associate a Gateway.
		'''
		self.Gateway = gateway

	def stop(self):
		'''
		Stop the Thread.
		'''
		self.running = False
		

	
def main():
	connector = BTDeviceConnector()
	gateway = Gateway(connector)
	connector.setGateway(gateway)
	gateway.start()
	connector.start()
	# Wait for any input
	raw_input("--> Press Any Button to exit")
	connector.stop()
	gateway.stop()


if __name__ == "__main__":
	#Clear the logfile
	with open(config.LOGFILE, 'w'):
		pass

	#Initialize Logger
	logging.basicConfig(format="%(asctime)s:%(levelname)s:%(message)s",filename=config.LOGFILE, level=config.LOGLEVEL)
	
	main()

