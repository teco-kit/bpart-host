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

import time
import random
import binascii
import pexpect
from threading import Thread
import logging

#Currently not used
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

   
    def getCharacteristics(self, forUUID=None):
        if not self.chars: # Unset, or empty
            self.chars = self.peripheral.getCharacteristics(self.hndStart, self.hndEnd)
        # Get Characteristic which corresponds with the UUID 
        if forUUID != None:
            u = UUID(forUUID)
            return [ ch for ch in self.chars if ch.uuid==u ]
        return self.chars

    def __str__(self):
        return "Service <%s>" % (str(self.uuid))

class Characteristic:
    def __init__(self, *args):
        (self.peripheral, uuidVal, self.handle, self.properties, self.valHandle) = args
        self.uuid = UUID(uuidVal)

    def read(self):
        return self.peripheral.readCharacteristic(self.valHandle)

    def write(self,val):
        self.peripheral.writeCharacteristic(self.valHandle,val)


    def __str__(self):
        return "Characteristic <%s>" % (self.uuid)


class Peripheral(Thread):
    '''
    This is an abstract class. It represents a bluetooth low energy device.
    It uses the gatttool utility.
    '''

    INITIALIZING=0
    INITIALIZED=1
    

    def __init__(self, deviceAddr):
        Thread.__init__(self)
        self._helper = None
        self.services = {} # Indexed by UUID
        self.discoveredAllServices = False
        self.running = True
        self.initializingStatus = Peripheral.INITIALIZING
        self.connected = False
        if len( deviceAddr.split(":") ) != 6:
            raise ValueError("Expected MAC address, got %s", repr(addr))
        else:
            self.deviceAddr = deviceAddr
            
        self.notificationHandles = []
        


    def _startHelper(self):
        # starts an external process which runs gatttool
        if self._helper == None:
            self._helper = pexpect.spawn('gatttool -I') 

    def _stopHelper(self):
        # ends the externel process
        if self._helper != None:
            self._helper.sendline('exit')
            self._helper = None

    def _writeCmd(self, cmd):
        # send a command to gatttool
        if self._helper == None:
            raise BTLEException(BTLEException.INTERNAL_ERROR, "Helper not started (did you call connect()?)")
        self._helper.sendline(cmd)


    def _getResp(self, wantType, tout=3):
        # get a response from gatttool. wantType can be either a string or a regular expression (also as string)
        # expect() returns when either exactly the same string or a string corresponding to the regular expression
        # has been received from gatttool
        self._helper.expect(wantType, timeout=tout)
        after = self._helper.after
        return after

    def initialize(self):
        '''
        This abstract method must be implemented by child classes.
        It is run after the device is already connected.
        In here you can put tasks which must be executed once after connecting.
        For example you could active sensors in here.
        '''
        raise NotImplementedError('Child must implement this method')

    def connect(self):
        '''
        Connects to the device.
        '''
        # Discover services and characteristics
        services = self.getServices()
        for service in services:
            service.getCharacteristics()
        self._getNotificationHandles()
        
        
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
        '''
        Disconnects from the device.
        '''
        
        self.running=False #stop the thread
        self.connected = False
        if self._helper==None:
            return

        self._writeCmd("disconnect")
        logging.info('Disconnected from %s' %self.deviceAddr)
        self._stopHelper()

    
    def _getNotificationHandles(self):
        '''
        Get all notification handles which can be used to activate notifications.
        Must be run before connect().
        '''
        handles = pexpect.run("gatttool --char-read --uuid=0x2902 -b " + self.deviceAddr)
        handles = handles.splitlines()
        for line in handles:
          self.notificationHandles.append(line.split(' ')[1])
          
         
    def activateNotifications(self):
        '''
        Activates notifications for all notification handles.
        Must be run after _getNotificationHandles.
        '''
        for notHnd in self.notificationHandles:
            self._writeCmd('char-write-req {0} 0100'.format(notHnd))
            self._getResp('Characteristic value was written successfully')
                

    def deactivateNotifications(self):
        '''
        Deactivates notifications for all notification handles.
        Must be run after _getNotificationHandles.
        '''
        for notHnd in self.notificationHandles:
            self._writeCmd('char-write-req {0} 0100'.format(notHnd))
            self._getResp('Characteristic value was written successfully')
        

    def _handleNotification(self, notification):
        '''
        Abstract. Must be implemented by child classes. notification contains the complete notification message as string.
        Example for notification: "Notification handle = 0x0019 value: 00 00 00 ff 00 43"
        '''
        raise NotImplementedError('Child classes have to implement this method to handle notifications')
            
    def run(self):
        
        while self.running:
            '''
            Main loop
            '''
            while not self.connected:
                # try to connect to the device
                try:
                    #services = self.getServices()
                    #for service in services:
                    #    service.getCharacteristics()
                    #self._getNotificationHandles()
                    self.connect()
                except pexpect.EOF:
                    return
                except BTLEException:
                    logging.info(self.deviceAddr + ': Could not connect')
                    self.connected = False
                    time.sleep(random.random())

            while self.initializingStatus == Peripheral.INITIALIZING:
                # initialize the device
                try:
                    self.initialize()
                    self.initializingStatus = Peripheral.INITIALIZED
                except pexpect.EOF:
                    return
                except pexpect.TIMEOUT:
                    self.connected = False
                    logging.info(self.deviceAddr + ': Connection lost while initializing')

            if self.initializingStatus == Peripheral.INITIALIZED:
                try:
                    notification = self._getResp('Notification handle = .*? \r',9)
                    self._handleNotification(notification)
                except pexpect.TIMEOUT:
                    self.connected = False
                    self.initializingStatus = Peripheral.INITIALIZING
                    logging.debug(self.deviceAddr + ": Timeout during notification loop")
                    logging.info(self.deviceAddr + ': Connection lost')
                except pexpect.EOF:
                    logging.debug(self.deviceAddr + ": Helper has exited during notification loop")
                    return

    

    def discoverServices(self):
        '''
        Discover all the services.
        Must be run befor calling connect()
        '''
        services = pexpect.run("gatttool --primary -b " + self.deviceAddr)
        logging.debug(self.deviceAddr + ": Services \n" + services)
        services = services.replace(',','')
        services = services.splitlines()

        for service in services:
            temp = service.split()
            if len(temp) < 9:
                raise BTLEException(BTLEException.INTERNAL_ERROR, "Error discovering devices")
            self.services[temp[-1]] = Service(self, temp[-1], temp[3], temp[8])
        self.discoveredAllServices = True
        
    def getServices(self):
        '''
        Gets the services
        '''
        if not self.discoveredAllServices:
            self.discoverServices()
        return self.services.values()

    def getServiceByUUID(self,uuidVal):
        uuid=UUID(uuidVal)
        return self.services[uuid]


    def getCharacteristics(self,startHnd=1,endHnd=0xFFFF):
        '''
        Gets the characteristics. Must be run befor calling connect()
        '''
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


    def readCharacteristic(self,handle):
        '''
        Reads the characteristic value described by handle.
        Return format: 'xx xx xx ...' (x are hex values)
        '''
        try:
        
            self._writeCmd('char-read-hnd {0:0>4x}'.format(handle))
            resp = self._getResp('Characteristic value/descriptor: .*? \r')
            strVal = resp.replace('Characteristic value/descriptor: ','').strip()
            return strVal
        except pexpect.TIMEOUT:
            self.connected = False
            logging.debug(self.deviceAddr + ": Could not read Characteristic value")
        except pexpect.EOF:
            logging.debug(self.deviceAddr + ": Could not read Characteristic value, Helper has exited")


    def readCharacteristicByUUID(self,uuid):
        '''
        Reads the characteristic value described by UUID.
        Return format: 'xx xx xx ...' (x are hex values)
        '''
        try:
            self._writeCmd('char-read-uuid {0}'.format(str(UUID(uuid))))
            resp = self._getResp('handle: .*? \r')
            strVal = resp.split(' ')
            strVal = ' '.join(strVal[4:-1])
            return strVal
        except pexpect.TIMEOUT:
            self.connected = False
            logging.debug(self.deviceAddr + ": Could not read Characteristic value")
        except pexpect.EOF:
            logging.debug(self.deviceAddr + ": Could not read Characteristic value, Helper has exited")
    

    def writeCharacteristic(self,handle,val):
        '''
        Writes the characteristic value described by handle.
        '''
        try:
            self._writeCmd('char-write-req {0:0>4x} {1}'.format(int(handle,16),val))
            self._getResp('Characteristic value was written successfully')
        except pexpect.TIMEOUT:
            self.connected = False
            logging.debug(self.deviceAddr + ": Could not write Characteristic value")
        except pexpect.EOF:
            logging.debug(self.deviceAddr + ": Could not write Characteristic value, Helper has exited")

    def __del__(self):
        self.disconnect()
    
    #The following functions can not be used, they still have to be modified to use gatttool 
    # =================================================================================================
    def getDescriptors(self,startHnd=1,endHnd=0xFFFF):
        raise NotImplementedError('To be implemented in the future')
        self._writeCmd("desc %X %X\n" % (startHnd, endHnd) )
        resp = self._getResp('desc')
        nDesc = len(resp['hnd'])
        return [ Descriptor(self, resp['uuid'][i], resp['hnd'][i]) for i in range(nDesc) ]
    
    def setSecurityLevel(self,level):
        raise NotImplementedError('To be implemented in the future')
        self._writeCmd("secu %s\n" % level)
        return self._getResp('stat')
    
    def setMTU(self,mtu):
        raise NotImplementedError('To be implemented in the future')
        self._writeCmd("mtu %x\n" % mtu)
        return self._getResp('stat')
    # ===================================================================================================
