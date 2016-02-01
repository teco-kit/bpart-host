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

import config
import urllib2
import logging
from btle import Peripheral
import json
import struct


class BPart(Peripheral):
    '''
    This class represents a BPart Bluetooth LE device. It provides functions to communicate with the device. You can activate sensors, read sensor data
    and handle notifications.
    
    If you only want to get sensor values and do not need to handle notifications, you have to call the connect() method first:
    
    ====================================
    bpart = BPart("00:07:80:78:FA:5A")
    bpart.connect()
    
    Your stuff...
    ====================================
    
    Note that the sensors are initially deactivated. Before reading any data you have to activate them.
    
    '''

    HUMIDITY_UUID = '4b822f30-3941-4a4b-a3cc-b2602ffe0d00'
    TEMPERATURE_UUID = '4b822f20-3941-4a4b-a3cc-b2602ffe0d00'
    ACCELERATION_UUID = '4b822f10-3941-4a4b-a3cc-b2602ffe0d00'
    LIGHT_UUID = '4b822f00-3941-4a4b-a3cc-b2602ffe0d00'
    
    HUMIDITY_VALUE_UUID = '4b822f31-3941-4a4b-a3cc-b2602ffe0d00'
    TEMPERATURE_VALUE_UUID = '4b822f21-3941-4a4b-a3cc-b2602ffe0d00'
    ACCELERATION_VALUE_UUID = '4b822f11-3941-4a4b-a3cc-b2602ffe0d00'
    LIGHT_VALUE_UUID = '4b822f01-3941-4a4b-a3cc-b2602ffe0d00'
    
    HUMIDITY_SENSOR_UUID = '4b822f32-3941-4a4b-a3cc-b2602ffe0d00'
    TEMPERATURE_SENSOR_UUID = '4b822f22-3941-4a4b-a3cc-b2602ffe0d00'
    ACCELERATION_SENSOR_UUID = '4b822f12-3941-4a4b-a3cc-b2602ffe0d00'
    LIGHT_SENSOR_UUID = '4b822f02-3941-4a4b-a3cc-b2602ffe0d00'
    

    def __init__(self, deviceAddr):
        Peripheral.__init__(self, deviceAddr)
        
        # Variables temporarily store the received sensor values
        self._light = None
        self._humidity = None
        self._acceleration = None
        self._temperature = None
        
    def _serviceToHandle(self, hnd):
        '''
        Gets the service uuid which is associated with the given handle
        '''
        for service in self.services.values():
            if int(hnd,16) >= int(service.hndStart,16) and int(hnd,16) <= int(service.hndEnd,16):
                return str(service.uuid)

    def _parseLight(self,data):
        '''
        Parses the raw data (hexstring without spaces) to an int value.
        '''
        temp = data.decode('hex')
        return struct.unpack('<I',temp)[0]
		
    def _parseTemperature(self,data):
        '''
        Parses the raw data (hexstring without spaces) into the temperature in Celsius
        '''
        temp = data.decode('hex')
        return (struct.unpack('<h',temp)[0] / 1000.0)

    def _parseHumidity(self, data):
        '''
        Parses the raw data (hexstring without spaces).
        '''
        temp = data.decode('hex')
        return struct.unpack('<H', temp)[0]

    def _parseAcceleration(self, data):
        '''
        Parses the raw data (hexstring without spaces)
        '''
        temp = data.decode('hex')
        (x,y,z) = struct.unpack('<hhh',temp)
        x = x / (1000.0 * 16)
        y = y / (1000.0 * 16)
        z = z / (1000.0 * 16)
        return (x,y,z)
        
    def _handleNotification(self, notification):
        '''
        This function overwrites the abstract method in btle.Peripheral. It receives the notifications sent by the BPart,
        parses the data and sends the sensor values to CUMULUS.
        '''
        splitted = notification.split(' ')
        
        svcuuid = self._serviceToHandle(splitted[3])
        
        # Decide which Service the data belongs to
        if svcuuid == BPart.TEMPERATURE_UUID:
            #Temperature data
            temp = splitted[5] + splitted[6]
            self._temperature = self._parseTemperature(temp)
            logging.debug(self.deviceAddr + ": Temperature = " + str(self._temperature))
        elif svcuuid == BPart.LIGHT_UUID:
            #Light data
            temp = splitted[5] + splitted[6] + splitted[7] + splitted[8]
            self._light = self._parseLight(temp)
            logging.debug(self.deviceAddr + ": Light = " + str(self._light))
        elif svcuuid == BPart.ACCELERATION_UUID:
            #Acceleration data
            temp = splitted[5] + splitted[6] + splitted[7] + splitted[8] + splitted[9] + splitted[10]
            self._acceleration = self._parseAcceleration(temp)
            logging.debug(self.deviceAddr + ": Acceleration= " + str(self._acceleration))
        elif svcuuid == BPart.HUMIDITY_UUID:
            #Humidity data
            temp = splitted[5] + splitted[6]
            self._humidity = self._parseHumidity(temp)
            logging.debug(self.deviceAddr + ": Humidity= " + str(self._humidity))

        # Only if all values have been received, send the data to cumulus
        if self._light and self._humidity and self._temperature and self._acceleration:
            jsonString = self._createJSONString(self._temperature, self._humidity,self._light, self._acceleration)
            logging.debug(self.deviceAddr + ": " + str(jsonString))
            self._sendDataToCumulus(self.deviceAddr,jsonString)
            
            #reset the temporary variables
            self._light = None
            self._humidity = None
            self._temperature = None
            self._acceleration = None

    def _createJSONString(self, temperature, humidity, light,(x,y,z)):
        '''
        This method constructs a json string out of the data.
        '''
        jsonString = json.dumps({'data':{'Temperature':{'value':str(temperature), 'unit':'degC'},'Humidity':{'value':str(humidity), 'unit':'Percent'},'Light':{'value':str(light), 'unit':'Number'},'AccelX':{'value':str(x),'unit':'Number'},'AccelY':{'value':str(y),'unit':'Number'},'AccelZ':{'value':str(z),'unit':'Number'    }}})
        return jsonString


    def _sendDataToCumulus(self,mac,jsonString):
        '''
        This method sends the data to CUMULUS
        '''
        url = config.CUMULUS_URL+mac.replace(':','')
        try:
            logging.debug(self.deviceAddr + ": Created URL: {0}".format(url))
            req = urllib2.Request(url, jsonString, {'Content-Type': 'application/x-www-form-urlencoded' })
            req.get_method = lambda: 'PUT'
            f = urllib2.urlopen(req)
            response = f.read()
            logging.debug(self.deviceAddr + ": CUMULUS Response: {0}\n".format(response))
            f.close()
        except urllib2.HTTPError as h:
            logging.warning("Error while sending data to {0}: HTTP Error {1}: {2}".format(url,h.code,h.msg))
            
    def initialize(self):
        '''
        All the stuff which needs to be initialized before notifications can be received.
        This method is called by the notification loop immediately after the connection has been established.
        At this time services and characteristics are already well known.
        '''
        self.activateLightSensor()
        self.activateHumiditySensor()
        self.activateAccelerationSensor()
        self.activateTemperatureSensor()
        self.activateNotifications()
            
            
    def activateLightSensor(self):
        lightSvc = self.getServiceByUUID(BPart.LIGHT_UUID)
        sensChr = lightSvc.getCharacteristics(BPart.LIGHT_SENSOR_UUID)[0]
        sensChr.write('01')
        
    def activateHumiditySensor(self):
        lightSvc = self.getServiceByUUID(BPart.HUMIDITY_UUID)
        sensChr = lightSvc.getCharacteristics(BPart.HUMIDITY_SENSOR_UUID)[0]
        sensChr.write('01')
        
    def activateAccelerationSensor(self):
        lightSvc = self.getServiceByUUID(BPart.ACCELERATION_UUID)
        sensChr = lightSvc.getCharacteristics(BPart.ACCELERATION_SENSOR_UUID)[0]
        sensChr.write('01')
       
    def activateTemperatureSensor(self):
        lightSvc = self.getServiceByUUID(BPart.TEMPERATURE_UUID)
        sensChr = lightSvc.getCharacteristics(BPart.TEMPERATURE_SENSOR_UUID)[0]
        sensChr.write('01')
        
    def deactivateLightSensor(self):
        lightSvc = self.getServiceByUUID(BPart.LIGHT_UUID)
        sensChr = lightSvc.getCharacteristics(BPart.LIGHT_SENSOR_UUID)[0]
        sensChr.write('00')
        
    def deactivateHumiditySensor(self):
        lightSvc = self.getServiceByUUID(BPart.HUMIDITY_UUID)
        sensChr = lightSvc.getCharacteristics(BPart.HUMIDITY_SENSOR_UUID)[0]
        sensChr.write('00')
        
    def deactivateAccelerationSensor(self):
        lightSvc = self.getServiceByUUID(BPart.ACCELERATION_UUID)
        sensChr = lightSvc.getCharacteristics(BPart.ACCELERATION_SENSOR_UUID)[0]
        sensChr.write('00')
       
    def deactivateTemperatureSensor(self):
        lightSvc = self.getServiceByUUID(BPart.TEMPERATURE_UUID)
        sensChr = lightSvc.getCharacteristics(BPart.TEMPERATURE_SENSOR_UUID)[0]
        sensChr.write('00')
    
    
    
    def getLight(self):
        light_val = self.readCharacteristicByUUID(BPart.LIGHT_VALUE_UUID)
        light_val = self._parseLight(light_val.replace(' ',''))
        # light_val is an int
        return light_val
      
    def getHumidity(self):
        humidity_val = self.readCharacteristicByUUID(BPart.HUMIDITY_VALUE_UUID)
        humidity_val = self._parseHumidity(humidity_val.replace(' ',''))
        # humidity_val is an int value
        return humidity_val
      
    def getTemperature(self):
        temperature_val = self.readCharacteristicByUUID(BPart.TEMPERATURE_VALUE_UUID)
        temperature_val = self._parseTemperature(temperature_val.replace(' ',''))
        # temperature_val is a double (Celsius)
        return temperature_val
      
    def getAcceleration(self):
        acceleration_val = self.readCharacteristicByUUID(BPart.ACCELERATION_VALUE_UUID)
        acceleration_val = self._parseAcceleration(acceleration_val.replace(' ',''))
        # acceleration_val is a tuple (double x, double y, double z)
        return acceleration_val
        
if __name__ == '__main__':
    '''
    For testing purposes. The actual main code is in the main module.
    '''
    conn = BPart("00:07:80:78:FA:5A")
       

    conn.connect()
    conn.activateLightSensor()
    conn.activateHumiditySensor()
    conn.activateAccelerationSensor()
    conn.activateTemperatureSensor()

    print "Temperature: " + str(conn.getTemperature())
    print "Humidity: " + str(conn.getHumidity())
    print "Acceleration: " + str(conn.getAcceleration())
    print "Light: " + str(conn.getLight())
    ''' 
    for serv in conn.services.values():
        print serv
        for char in serv.chars:
            print char
        print "\n"
    
    print 'Notification handles:'
    for hand in conn.notificationHandles:
    	print hand
    '''
    conn.disconnect()
        

