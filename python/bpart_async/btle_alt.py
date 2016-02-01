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

import sys, os, time
import urllib2
import json
import config
import struct
import subprocess
import binascii
import pexpect
import re
from threading import Thread
import logging

Debugging = False

SEC_LEVEL_LOW    = "low"
SEC_LEVEL_MEDIUM = "medium"
SEC_LEVEL_HIGH   = "high"

 
class BTLEException(Exception):
    DISCONNECTED = 1
    COMM_ERROR = 2
    INTERNAL_ERROR = 3
    
    def __init__(self, code, message):
        self.code = code
        self.message = message

    def __str__(self):
        return self.message


class UUID:
    def __init__(self, val):
        '''We accept: 32-digit hex strings, with and without '-' characters,
           4 to 8 digit hex strings, and integers''' 
        if isinstance(val,int) or isinstance(val,long):
            if (val < 0) or (val > 0xFFFFFFFF):
                raise ValueError("Short form UUIDs must be in range 0..0xFFFFFFFF")
            val = "%04X" % val
        else:
            val = str(val) # Do our best

        val = val.replace("-","") 
        if len(val) <= 8: # Short form 
            val = ("0" * (8-len(val))) + val +"00001000800000805F9B34FB"

        self.binVal = binascii.a2b_hex(val) 
        if len(self.binVal) != 16:
            raise ValueError("UUID must be 16 bytes, got '%s'" % val)

    def __str__(self):
        s = binascii.b2a_hex(self.binVal)
        return "-".join([ s[0:8], s[8:12], s[12:16], s[16:20], s[20:32] ])

    def __cmp__(self, other):
        return cmp(str(self), str(other))

    def __hash__(self):
        return hash(str(self))

    def friendlyName(self):
        #TODO
        return str(self)

class Service:
    def __init__(self, *args):
        (self.peripheral, uuidVal, self.hndStart, self.hndEnd) = args
        self.uuid = UUID(uuidVal)
        self.chars = None
        self.description = "No Description"

    def getCharacteristics(self):
        if not self.chars: # Unset, or empty
            self.chars = self.peripheral.getCharacteristics(self.hndStart, self.hndEnd)
        return self.chars

    def __str__(self):
        return "Service <%s>: %s" % (str(self.uuid),self.description)

class Characteristic:
    def __init__(self, *args):
        (self.peripheral, uuidVal, self.handle, self.properties, self.valHandle) = args
        self.uuid = UUID(uuidVal)

    def read(self):
        return self.peripheral.readCharacteristic(self.valHandle)

    def write(self,val,withResponse=False):
        self.peripheral.writeCharacteristic(self.valHandle,val,withResponse)


    def __str__(self):
        return "Characteristic <%s>" % (self.uuid)


class BPart(Thread):

    NOTIFICATION_ACTIVE=0
    NOTIFICATION_ACTIVATING=1
    NOTIFICATION_INACTIVE=2

    HUMIDITY_UUID = '4b822f30-3941-4a4b-a3cc-b2602ffe0d00'
    TEMPERATURE_UUID = '4b822f20-3941-4a4b-a3cc-b2602ffe0d00'
    ACCELERATION_UUID = '4b822f10-3941-4a4b-a3cc-b2602ffe0d00'
    LIGHT_UUID = '4b822f00-3941-4a4b-a3cc-b2602ffe0d00'

    def __init__(self, deviceAddr):
        Thread.__init__(self)
        self._helper = None
        self.services = {} # Indexed by UUID
        self.discoveredAllServices = False
        self.running = True
        self.notificationStatus = BPart.NOTIFICATION_INACTIVE
        self.connected = False
        if len( deviceAddr.split(":") ) != 6:
            raise ValueError("Expected MAC address, got %s", repr(addr))
        else:
            self.deviceAddr = deviceAddr
        
        self._light = None
        self._humidity = None
        self._acceleration = None
        self._temperature = None
        #if deviceAddr != None:
        #    self.connect(deviceAddr)


    def _startHelper(self):
        if self._helper == None:
            self._helper = pexpect.spawn('gatttool -I') 

    def _stopHelper(self):
        if self._helper != None:
            self._helper.sendline('exit')
            self._helper = None

    def _writeCmd(self, cmd):
        if self._helper == None:
            raise BTLEException(BTLEException.INTERNAL_ERROR, "Helper not started (did you call connect()?)")
        self._helper.sendline(cmd)


    def _getResp(self, wantType, tout=3):
        self._helper.expect(wantType, timeout=tout)
        after = self._helper.after
        return after


    def connect(self):
        self._startHelper()
        self._writeCmd('connect %s\n' % self.deviceAddr)
        try:
            self._getResp('Connection successful', tout=5)
            logging.info('Connected to %s' %self.deviceAddr)
            self.connected = True
        except pexpect.TIMEOUT:
            self._stopHelper()
            raise BTLEException(BTLEException.DISCONNECTED, "Failed to connect to peripheral")

    def disconnect(self):
        self.running=False
        self.connected = False
        if self._helper==None:
            return

        self._writeCmd("disconnect")
        self._stopHelper()

    def activateNotifications(self):
        #self._writeCmd('char-read-uuid 2902')
        #exp = re.compile(r'^.*handle: .? value: .?$',re.MULTILINE)
        #resp = self._getResp(exp)
        if self.connected:
            try:
                self._writeCmd('char-write-req 0014 0100')
                self._getResp('Characteristic value was written successfully')
                self._writeCmd('char-write-req 0018 0100')
                self._getResp('Characteristic value was written successfully')
                self._writeCmd('char-write-req 001c 0100')
                self._getResp('Characteristic value was written successfully')
                self._writeCmd('char-write-req 0020 0100')
                self._getResp('Characteristic value was written successfully')
                self.notificationStatus = BPart.NOTIFICATION_ACTIVE
            except pexpect.TIMEOUT:
                self.notificationStatus = BPart.NOTIFICATION_ACTIVATING
                logging.debug("Could not activate notifications, %s is probably not connected" %self.deviceAddr)
        else:
            self.notificationStatus = BPart.NOTIFICATION_ACTIVATING
            

    def deactivateNotifications(self):
        #self._writeCmd('char-read-uuid 2902')
        #exp = re.compile(r'^.*handle: .? value: .?$',re.MULTILINE)
        #resp = self._getResp(exp)
        try:
            self._writeCmd('char-write-cmd 0014 0000')
            self._getResp('Characteristic value was written successfully')
            self._writeCmd('char-write-cmd 0018 0000')
            self._getResp('Characteristic value was written successfully')
            self._writeCmd('char-write-cmd 001c 0000')
            self._getResp('Characteristic value was written successfully')
            self._writeCmd('char-write-cmd 0020 0000')
            self._getResp('Characteristic value was written successfully')
            self.notificationStatus = BPart.NOTIFICATION_INACTIVE
        except pexpect.TIMEOUT:
            logging.debug("Could not deactivate notification, bpart is probably not connected")

    def stop(self):
        self.running = False

    def _handleNotification(self, notification):
        #logging.debug(self.deviceAddr + ": " + notification)
        splitted = notification.split(' ')
        if splitted[3] == '0x001b':
            temp = splitted[5] + splitted[6]
            temp = temp.decode('hex')
            self._temperature = struct.unpack('<h',temp)[0] / 1000.0
            logging.debug(self.deviceAddr + ": Temperature = " + str(self._temperature))
        elif splitted[3] == '0x0013':
            self._light= struct.unpack('<I',(splitted[5] + splitted[6] + splitted[7] + splitted[8]).decode('hex'))[0]
            logging.debug(self.deviceAddr + ": Light = " + str(self._light))
        elif splitted[3] == '0x0017':
            (x,y,z) = struct.unpack('<hhh',(splitted[5]+splitted[6]+splitted[7]+splitted[8]+splitted[9]+splitted[10]).decode('hex'))
            x = x / (1000.0 * 16)
            y = y / (1000.0 * 16)
            z = z / (1000.0 * 16)
            self._acceleration = (x,y,z)
            logging.debug(self.deviceAddr + ": Acceleration= " + str(self._acceleration))
        elif splitted[3] == '0x001f':
            self._humidity= struct.unpack('<H', (splitted[5] + splitted[6]).decode('hex'))[0]
            logging.debug(self.deviceAddr + ": Humidity= " + str(self._humidity))


        if self._light and self._humidity and self._temperature and self._acceleration:
            jsonString = self._createJSONString(self._temperature, self._humidity,self._light, self._acceleration)
            logging.debug(self.deviceAddr + ": " + str(jsonString))
            self._sendDataToCumulus(self.deviceAddr,jsonString)
            self._light = None
            self._humidity = None
            self._temperature = None
            self._acceleration = None

    def _createJSONString(self, temperature, humidity, light,(x,y,z)):
        jsonString = json.dumps({'data':{'Temperature':{'value':str(temperature), 'unit':'degC'},'Humidity':{'value':str(humidity), 'unit':'Percent'},'Light':{'value':str(light), 'unit':'Number'},'AccelX':{'value':str(x),'unit':'Number'},'AccelY':{'value':str(y),'unit':'Number'},'AccelZ':{'value':str(z),'unit':'Number'    }}})
        return jsonString


    def _sendDataToCumulus(self,mac,jsonString):
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
            
        while self.running:
            while not self.connected:
                try:
                    services = self.getServices()
                    for service in services:
                        service.getCharacteristics()
                    self.connect()
                except pexpect.EOF:
                    return
                except BTLEException:
                    pass

            while self.notificationStatus == BPart.NOTIFICATION_ACTIVATING:
                try:
                    self.activateNotifications()
                except pexpect.EOF:
                    return

            if self.notificationStatus == BPart.NOTIFICATION_ACTIVE:
                try:
                    self._helper.expect('Notification handle = .*? \r',timeout=1)
                    self._handleNotification(self._helper.after)
                except pexpect.TIMEOUT:
                    self.connected = False
                    self.notificationStatus = BPart.NOTIFICATION_ACTIVATING
                    logging.debug(self.deviceAddr + ": Timeout during notification loop")
                except pexpect.EOF:
                    logging.debug(self.deviceAddr + ": Helper has exited during notification loop")
                    return

    

    def discoverServices(self):
        services = pexpect.run("gatttool --primary -b " + self.deviceAddr)
        services = services.replace(',','')
        services = services.splitlines()
        for service in services:
            temp = service.split()
            self.services[temp[-1]] = Service(self, temp[-1], temp[3], temp[8])
            if temp[-1] == BPart.HUMIDITY_UUID:
                self.services[temp[-1]].description = "Humidity"
            elif temp[-1] == BPart.TEMPERATURE_UUID:
                self.services[temp[-1]].description = "Temperature"
            elif temp[-1] == BPart.ACCELERATION_UUID:
                self.services[temp[-1]].description = "Acceleration"
            elif temp[-1] == BPart.LIGHT_UUID:
                self.services[temp[-1]].description = "Light"
        self.discoveredAllServices = True
        
    def getServices(self):
        if not self.discoveredAllServices:
            self.discoverServices()
        return self.services.values()

    def getServiceByUUID(self,uuidVal):
        uuid=UUID(uuidVal)
        return self.services[uuid]

    '''
    def _getIncludedServices(self,startHnd=1,endHnd=0xFFFF):
        # TODO: No working example of this yet
        self._writeCmd("incl %X %X\n" % (startHnd, endHnd) )
        return self._getResp('find')
    '''

    def getCharacteristics(self,startHnd=1,endHnd=0xFFFF):
        charStr = pexpect.run("gatttool --characteristics -s {0} -e {1} -b {2}".format(startHnd,endHnd,self.deviceAddr))
        if not 'Discover all characteristics failed:' in charStr:
            charStr = charStr.replace(',','')
            charStr = charStr.splitlines()
            chars = []
            for char in charStr:
                temp = char.split()
                chars.append(Characteristic(self, temp[-1], temp[2], temp[6], temp[11]))
            return chars
        else:
            raise BTLEException(BTLEException.DISCONNECTED, "Failed to get characteristics")

    #The following functions can not be used, they still have to be modified to use gatttool
    '''
    def getDescriptors(self,startHnd=1,endHnd=0xFFFF):
        self._writeCmd("desc %X %X\n" % (startHnd, endHnd) )
        resp = self._getResp('desc')
        nDesc = len(resp['hnd'])
        return [ Descriptor(self, resp['uuid'][i], resp['hnd'][i]) for i in range(nDesc) ]
    '''

    def readCharacteristic(self,handle):
        try:
            self._writeCmd('char-read-hnd {0:0>4x}'.format(handle))
            self._helper.expect('Characteristic value/descriptor: .*? \r')
            strVal = self._helper.after.replace('Characteristic value/descriptor: ','').strip()
            return strVal
        except pexpect.TIMEOUT:
            self.connected = False
            logging.debug(self.deviceAddr + ": Could not read Characteristic value")
        except pexpect.EOF:
            logging.debug(self.deviceAddr + ": Could not read Characteristic value, Helper has exited")



    def _readCharacteristicByUUID(self,uuid,startHnd,endHnd):
        # Not used at present
        self._writeCmd("rdu %s %X %X\n" % (str(UUID(uuid)), startHnd, endHnd) )
        return self._getResp('rd')

    def writeCharacteristic(self,handle,val):
        try:
            self._writeCmd('char-write-req {0:0>4x} {1}'.format(handle,val))
            self._helper.expect('Characteristic value was written successfully')
        except pexpect.TIMEOUT:
            self.connected = False
            logging.debug(self.deviceAddr + ": Could not write Characteristic value")
        except pexpect.EOF:
            logging.debug(self.deviceAddr + ": Could not write Characteristic value, Helper has exited")


    def setSecurityLevel(self,level):
        self._writeCmd("secu %s\n" % level)
        return self._getResp('stat')
    
    def setMTU(self,mtu):
        self._writeCmd("mtu %x\n" % mtu)
        return self._getResp('stat')
  
    def __del__(self):
        self.disconnect()

def strList(l, indent="  "):
    sep = ",\n" + indent
    return indent + (sep.join([ str(i) for i in l ]))

if __name__ == '__main__':
    conn = BPart("00:07:80:78:FA:5A")
    conn.discoverServices()
    for serv in conn.services.values():
        serv.getCharacteristics()
    
    conn.connect()
    conn.writeCharacteristic(0x16,'01')

    print conn.readCharacteristic(0x13)
    for serv in conn.services.values():
        print serv
        for char in serv.chars:
            print char
        print "\n"
    
    conn.disconnect()
'''
print UUID(0x270A)
print UUID("f000aa11-0451-4000-b000-000000000000")
print UUID("f000aa1204514000b000000000000000")

conn = Peripheral("BC:6A:29:AB:D3:7A")
try:
for svc in conn.getServices():
    print str(svc), ": ----"
    print strList(svc.getCharacteristics())
svc = conn.getServiceByUUID("f000aa10-0451-4000-b000-000000000000") # Accelerometer
config = svc.getCharacteristics("f000aa12-0451-4000-b000-000000000000")[0]
config.write("\x01") # Enable
accel = svc.getCharacteristics("f000aa11-0451-4000-b000-000000000000")[0]
for i in range(10):
    raw = accel.read()
    (x,y,z) = [ ((ord(db) ^ 0x80) - 0x80)/64.0 for db in raw ]
    print "X=%.2f Y=%.2f Z=%.2f" % (x,y,z)
finally:
conn.disconnect()
''' 

    

