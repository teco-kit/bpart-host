import config
import math
from time import sleep
import urllib2
import logging
from btle import Peripheral
import json
import struct

def calcPoly(coeffs, x):
    return coeffs[0] + (coeffs[1]*x) + (coeffs[2]*x*x)

class SensorTag(Peripheral):
    '''
    This class represents a TI SensorTag device. It provides functions to communicate with the device. You can activate sensors, read sensor data
    and handle notifications.
    
    If you only want to get sensor values and do not need to handle notifications, you have to call the connect() method first:
    
    ====================================
    sensortag = SensorTag("00:07:80:78:FA:5A")
    sensortag.connect()
    
    Your stuff...
    ====================================
    
    Note that the sensors are initially deactivated. Before reading any data you have to activate them.
    
    '''
    
    TEMPERATURE_UUID = 'F000AA00-0451-4000-B000-000000000000'
    TEMPERATURE_VALUE_UUID = 'F000AA01-0451-4000-B000-000000000000'
    TEMPERATURE_SENSOR_UUID = 'F000AA02-0451-4000-B000-000000000000'
   
    
    ACCELERATION_UUID = 'F000AA10-0451-4000-B000-000000000000'
    ACCELERATION_VALUE_UUID = 'F000AA11-0451-4000-B000-000000000000'
    ACCELERATION_SENSOR_UUID = 'F000AA12-0451-4000-B000-000000000000'

    HUMIDITY_UUID = 'F000AA20-0451-4000-B000-000000000000'
    HUMIDITY_VALUE_UUID = 'F000AA21-0451-4000-B000-000000000000'
    HUMIDITY_SENSOR_UUID = 'F000AA22-0451-4000-B000-000000000000'

    MAGNETOMETER_UUID = 'F000AA30-0451-4000-B000-000000000000'
    MAGNETOMETER_VALUE_UUID = 'F000AA31-0451-4000-B000-000000000000'
    MAGNETOMETER_SENSOR_UUID = 'F000AA32-0451-4000-B000-000000000000'

    BAROMETER_UUID = 'F000AA40-0451-4000-B000-000000000000'
    BAROMETER_VALUE_UUID = 'F000AA41-0451-4000-B000-000000000000'
    BAROMETER_SENSOR_UUID = 'F000AA42-0451-4000-B000-000000000000'
    BAROMETER_CALIB_UUID = 'F000AA43-0451-4000-B000-000000000000'

    GYROSCOPE_UUID = 'F000AA50-0451-4000-B000-000000000000'
    GYROSCOPE_VALUE_UUID = 'F000AA51-0451-4000-B000-000000000000'
    GYROSCOPE_SENSOR_UUID = 'F000AA52-0451-4000-B000-000000000000'

    def __init__(self, deviceAddr):
        Peripheral.__init__(self, deviceAddr)
        
        
    def _serviceToHandle(self, hnd):
        '''
        Gets the service uuid which is associated with the given handle
        '''
        for service in self.services.values():
            if int(hnd,16) >= int(service.hndStart,16) and int(hnd,16) <= int(service.hndEnd,16):
                return str(service.uuid)

    def _parseMagnetometer(self, data):
        temp = data.decode('hex')
        x_y_z = struct.unpack('<hhh', temp)
        return tuple([ 1000.0 * (v/32768.0) for v in x_y_z ])
        
    def _parseBarometer(self, data,(c1,c2,sensPoly,offsPoly)):
        temp = data.decode('hex')
        (rawT, rawP) = struct.unpack('<hH', temp)
        temp = (c1 * rawT) + c2
        sens = calcPoly( sensPoly, float(rawT) )
        offs = calcPoly( offsPoly, float(rawT) )
        pres = (sens * rawP + offs) / (100.0 * float(1<<14))
        return (temp,pres)
        
    def _parseGyroscope(self,data):
        temp = data.decode('hex')
        x_y_z = struct.unpack('<hhh', temp)
        return tuple([ 250.0 * (v/32768.0) for v in x_y_z ])
       
    def _parseTemperature(self,data):
        '''
        Parses the raw data (hexstring without spaces) into the temperature in Celsius
        '''
        
        Apoly = [1.0,      1.75e-3, -1.678e-5]
        Bpoly = [-2.94e-5, -5.7e-7,  4.63e-9]
        Cpoly = [0.0,      1.0,      13.4]
        
        temp = data.decode('hex')
        (rawVobj, rawTamb) = struct.unpack('<hh', temp)
        tAmb = rawTamb / 128.0
        Vobj = 1.5625e-7 * rawVobj
        
        tDie = tAmb + 273.15
        S   = 6.4e-14 * calcPoly(Apoly, tDie-298.15)
        Vos = calcPoly(Bpoly, tDie-298.15)
        fObj = calcPoly(Cpoly, Vobj-Vos)
        
        tObj = math.pow( math.pow(tDie,4.0) + (fObj/S), 0.25 )
        return (tAmb, tObj - 273.15)

    def _parseHumidity(self, data):
        '''
        Parses the raw data (hexstring without spaces).
        '''
        temp = data.decode('hex')
        (rawT, rawH) = struct.unpack('<HH', temp)
        temp = -46.85 + 175.72 * (rawT / 65536.0)
        RH = -6.0 + 125.0 * ((rawH & 0xFFFC)/65536.0)
        return (temp, RH)

    def _parseAcceleration(self, data):
        '''
        Parses the raw data (hexstring without spaces)
        '''
        temp = data.decode('hex')
        x_y_z = struct.unpack('bbb', temp)
        return tuple([ (val/64.0) for val in x_y_z ])
        
    def _handleNotification(self, notification):
        '''
        This function overwrites the abstract method in btle.Peripheral. It receives the notifications sent by the BPart,
        parses the data and sends the sensor values to CUMULUS.
        '''
        splitted = notification.split(' ')
        
        svcuuid = self._serviceToHandle(splitted[3])
        svcuuid = svcuuid.upper()

        # Decide which Service the data belongs to
        if svcuuid == SensorTag.TEMPERATURE_UUID:
            #Temperature data
            temp = ''.join(splitted[5:-1])
            temperature = self._parseTemperature(temp)
            print self.deviceAddr + ": Temperature = " + str(temperature)
        elif svcuuid == SensorTag.MAGNETOMETER_UUID:
            #Magnetometer data
            temp = ''.join(splitted[5:-1])
            magnetometer = self._parseMagnetometer(temp)
            print self.deviceAddr + ": Magnetometer = " + str(magnetometer)
        elif svcuuid == SensorTag.ACCELERATION_UUID:
            #Acceleration data
            temp = ''.join(splitted[5:-1])
            acceleration = self._parseAcceleration(temp)
            print self.deviceAddr + ": Acceleration = " + str(acceleration)
        elif svcuuid == SensorTag.HUMIDITY_UUID:
            #Humidity data
            temp = ''.join(splitted[5:-1])
            humidity = self._parseHumidity(temp)
            print self.deviceAddr + ": Humidity = " + str(humidity)
        elif svcuuid == SensorTag.GYROSCOPE_UUID:
            temp = ''.join(splitted[5:-1])
            gyro = self._parseGyroscope(temp)
            print self.deviceAddr + ": Gyroscope = " + str(gyro)
        elif svcuuid == SensorTag.BAROMETER_UUID:
            temp = ''.join(splitted[5:-1])
            print self.deviceAddr + ": Barometer = " + str(temp)

      
            
    def activateNotifications(self):
        self.writeCharacteristic('0x0026','0100')
        self.writeCharacteristic('0x002e','0100')
        self.writeCharacteristic('0x0039','0100')
        self.writeCharacteristic('0x0041','0100')

        print 'Notifications activated'

    def initialize(self):
        '''
        All the stuff which needs to be initialized before notifications can be received.
        This method is called by the notification loop immediately after the connection has been established.
        At this time services and characteristics are already well known.
        '''
        print 'Initializing'
        self.activateTemperatureSensor()
        self.activateAccelerationSensor()
        self.activateHumiditySensor()
        self.activateBarometerSensor()
        self.activateMagnetometerSensor()
        self.activateGyroscopeSensor()
        self.activateNotifications()
        self.calibrateBarometer()
        print 'Initialized!'    
            
    def activateMagnetometerSensor(self):
        lightSvc = self.getServiceByUUID(SensorTag.MAGNETOMETER_UUID)
        sensChr = lightSvc.getCharacteristics(SensorTag.MAGNETOMETER_SENSOR_UUID)[0]
        sensChr.write('01')
        
    def activateHumiditySensor(self):
        lightSvc = self.getServiceByUUID(SensorTag.HUMIDITY_UUID)
        sensChr = lightSvc.getCharacteristics(SensorTag.HUMIDITY_SENSOR_UUID)[0]
        sensChr.write('01')
        
    def activateAccelerationSensor(self):
        lightSvc = self.getServiceByUUID(SensorTag.ACCELERATION_UUID)
        sensChr = lightSvc.getCharacteristics(SensorTag.ACCELERATION_SENSOR_UUID)[0]
        sensChr.write('01')
       
    def activateTemperatureSensor(self):
        lightSvc = self.getServiceByUUID(SensorTag.TEMPERATURE_UUID)
        sensChr = lightSvc.getCharacteristics(SensorTag.TEMPERATURE_SENSOR_UUID)[0]
        sensChr.write('01')
        
    def activateBarometerSensor(self):
        lightSvc = self.getServiceByUUID(SensorTag.BAROMETER_UUID)
        sensChr = lightSvc.getCharacteristics(SensorTag.BAROMETER_SENSOR_UUID)[0]
        sensChr.write('01')
        
    def activateGyroscopeSensor(self):
        lightSvc = self.getServiceByUUID(SensorTag.GYROSCOPE_UUID)
        sensChr = lightSvc.getCharacteristics(SensorTag.GYROSCOPE_SENSOR_UUID)[0]
        sensChr.write('07')
    	
    def calibrateBarometer(self):
    	svc = self.getServiceByUUID(SensorTag.BAROMETER_UUID)
        sensChr = svc.getCharacteristics(SensorTag.BAROMETER_SENSOR_UUID)[0]
        sensChr.write('01')
    
    def deactivateMagnetometerSensor(self):
        lightSvc = self.getServiceByUUID(SensorTag.MAGNETOMETER_UUID)
        sensChr = lightSvc.getCharacteristics(SensorTag.MAGNETOMETER_SENSOR_UUID)[0]
        sensChr.write('00')
        
    def deactivateHumiditySensor(self):
        lightSvc = self.getServiceByUUID(SensorTag.HUMIDITY_UUID)
        sensChr = lightSvc.getCharacteristics(SensorTag.HUMIDITY_SENSOR_UUID)[0]
        sensChr.write('00')
        
    def deactivateAccelerationSensor(self):
        lightSvc = self.getServiceByUUID(SensorTag.ACCELERATION_UUID)
        sensChr = lightSvc.getCharacteristics(SensorTag.ACCELERATION_SENSOR_UUID)[0]
        sensChr.write('00')
       
    def deactivateTemperatureSensor(self):
        lightSvc = self.getServiceByUUID(SensorTag.TEMPERATURE_UUID)
        sensChr = lightSvc.getCharacteristics(SensorTag.TEMPERATURE_SENSOR_UUID)[0]
        sensChr.write('00')
        
    def deactivateBarometerSensor(self):
        lightSvc = self.getServiceByUUID(SensorTag.BAROMETER_UUID)
        sensChr = lightSvc.getCharacteristics(SensorTag.BAROMETER_SENSOR_UUID)[0]
        sensChr.write('00')
        
    def deactivateGyroscopeSensor(self):
        lightSvc = self.getServiceByUUID(SensorTag.GYROSCOPE_UUID)
        sensChr = lightSvc.getCharacteristics(SensorTag.GYROSCOPE_SENSOR_UUID)[0]
        sensChr.write('00')
    
    
    def getMagnetometer(self):
        val = self.readCharacteristicByUUID(SensorTag.MAGNETOMETER_VALUE_UUID)
        val = self._parseMagnetometer(val.replace(' ',''))
        return val
      
    def getHumidity(self):
        val = self.readCharacteristicByUUID(SensorTag.HUMIDITY_VALUE_UUID)
        val = self._parseHumidity(val.replace(' ',''))
        return val
      
    def getTemperature(self):
        val = self.readCharacteristicByUUID(SensorTag.TEMPERATURE_VALUE_UUID)
        val = self._parseTemperature(val.replace(' ',''))
        return val
      
    def getAcceleration(self):
        val = self.readCharacteristicByUUID(SensorTag.ACCELERATION_VALUE_UUID)
        val = self._parseAcceleration(val.replace(' ',''))
        return val

    def getBarometer(self):
        val = self.readCharacteristicByUUID(SensorTag.BAROMETER_VALUE_UUID)
        calib = self.getBarometerCalib()
        val = self._parseBarometer(val.replace(' ',''), calib)
        return val
        
    def getBarometerCalib(self):
    	calib = self.readCharacteristicByUUID(SensorTag.BAROMETER_CALIB_UUID)
        (c1,c2,c3,c4,c5,c6,c7,c8) = struct.unpack("<HHHHhhhh", calib.replace(' ','').decode('hex'))
        c1_s = c1/float(1 << 24)
        c2_s = c2/float(1 << 10)
        sensPoly = [ c3/1.0, c4/float(1 << 17), c5/float(1<<34) ]
        offsPoly = [ c6*float(1<<14), c7/8.0, c8/float(1<<19) ]
        return (c1_s, c2_s, sensPoly, offsPoly)

    def getGyroscope(self):
        val = self.readCharacteristicByUUID(SensorTag.GYROSCOPE_VALUE_UUID)
        val = self._parseGyroscope(val.replace(' ',''))
        return val
        

def sensorTagTest():
    tag = SensorTag("34:B1:F7:D1:73:8A")
    tag.connect()
    print "Connected"
    
    tag.initialize()
    sleep(10)

    print "Temperature: " + str(tag.getTemperature())
    print 'Humidity: ' + str(tag.getHumidity())
    print 'Magnetometer: ' + str(tag.getMagnetometer())
    print 'Acceleration: ' + str(tag.getAcceleration())
    print 'Barometer: ' + str(tag.getBarometer())
    print 'Gyrosope: ' + str(tag.getGyroscope())

    tag.disconnect()

def sensorTagTest_notifications():
    tag = SensorTag("34:B1:F7:D1:73:8A")
    tag.start()
    raw_input('--> Press any Button to exit\n')
    tag.disconnect()
	
if __name__ == '__main__':
    '''
    For testing purposes. The actual main code is in the main module.
    '''
    #sensorTagTest()   
    sensorTagTest_notifications()

