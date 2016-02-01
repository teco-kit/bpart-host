'''
This module encapsulates the access to the TecO bparts.

'''

from btle import UUID, Peripheral
import struct
import subprocess


def _bpart_UUID(val):
	'''
	Utility function to calculate the UUID for a bpart.
	'''
	return UUID("%08X-3941-4a4b-a3cc-b2602ffe0d00" % (0x4B822000 + val))


class SensorBase(object):
	'''
	This abstract class can be implemented to gain access to bpart sensors.
	'''

	def __init__(self, periph):
		'''
		Initialize object, asscociate with the peripheral (bpart)
		'''
		self.periph = periph
		self.service = self.periph.getServiceByUUID(self.svcUUID)
		self.data = self.service.getCharacteristics(self.dataUUID)[0]


	def read(self):
		return self.data.read()


class BPartTemperatureSensor(SensorBase):
	'''
	This class connects to a bpart temperature sensor
	'''

	
	svcUUID = _bpart_UUID(0xF20)
	dataUUID = _bpart_UUID(0xF21)

	def __init__(self, periph):
		SensorBase.__init__(self,periph)

	def read(self):
		'''
		Read and parse the sensor data.
		'''
		rawdata = self.data.read()
		temperature = struct.unpack('<h',rawdata)
		return temperature[0]/1000.0

class BPartLightSensor(SensorBase):
	'''
	This class connects to a bpart light sensor.
	'''
	svcUUID = _bpart_UUID(0xF00)
	dataUUID = _bpart_UUID(0xF01)

	def __init__(self, periph):
		SensorBase.__init__(self,periph)

	def read(self):
		'''
		Read and parse the sensor data.
		'''
		rawdata = self.data.read()
		light = struct.unpack('<I',rawdata)
		return light[0]
		
class BPartHumiditySensor(SensorBase):
	'''
	This class connects to a bpart humidity sensor.
	'''

	svcUUID = _bpart_UUID(0xF30)
	dataUUID = _bpart_UUID(0xF31)

	def __init__(self, periph):
		SensorBase.__init__(self,periph)

	def read(self):
		'''
		Read and parse the sensor data.
		'''
		rawdata = self.data.read()
		humidity = struct.unpack('<H',rawdata)
		return humidity[0]
		

class BPartAccelerometer(SensorBase):
	'''
	This class connects to a bpart accelerometer.
	'''
	svcUUID = _bpart_UUID(0xF10)
	dataUUID = _bpart_UUID(0xF11)

	def __init__(self, periph):
		SensorBase.__init__(self,periph)

	def read(self):
		'''
		Read and parse the sensor data.
		'''
		rawdata = self.data.read()
		(x,y,z) = struct.unpack('<hhh',rawdata)
		x = x / (1000.0 * 16)
		y = y / (1000.0 * 16)
		z = z / (1000.0 * 16)
		return (x,y,z)
		


class BPart(Peripheral):
	'''
	This class abstracts a bpart and provides access to all it's sensor data.
	'''

	def __init__(self,addr):
		Peripheral.__init__(self,addr)
		self.discoverServices()
		self.Temperature = BPartTemperatureSensor(self)
		self.Light = BPartLightSensor(self)
		self.Humidity = BPartHumiditySensor(self)
		self.Acceleration = BPartAccelerometer(self)



#The following is for testing purposes only
if __name__ == "__main__":
	#print _bpart_UUID(0xF20)
	import time

	bpart = BPart("00:07:80:78:F5:C3")
	bpart2 = BPart("00:07:80:78:FA:5A")
	
	i = 0
	while i<3:
		#print bpart.Temperature
		temp = bpart.Temperature.read()
		light = bpart.Light.read()
		humidity = bpart.Humidity.read()
		(x,y,z) = bpart.Acceleration.read()
		
		temp2 = bpart2.Temperature.read()
		light2 = bpart2.Light.read()
		humidity2 = bpart2.Humidity.read()
		(x2,y2,z2) = bpart2.Acceleration.read()
		
		print "BPART 1"
		print "Temperature: ", temp
		print "Light: ", light
		print "Humidity: ", humidity
		print "Acceleration: ", x, " ", y, " ", z

		print "\n\nBPART 2"
		print "Temperature: ", temp2
		print "Light: ", light2
		print "Humidity: ", humidity2
		print "Acceleration: ", x2, " ", y2, " ", z2
		time.sleep(5.0)
		i = i + 1 
	if bpart:
		bpart.disconnect()
		del bpart
	if bpart2:
		bpart2.disconnect()
		del bpart2
