# BPart Async Client

Part of this work is based on the blueby project by IanHarvey (https://github.com/IanHarvey/bluepy)

## License
This code is a Python interface to the bluez project, which is available under the Version 2 of the GNU Public License.

The Python code is released under the MIT License.

## Installation

exemplary installation on a Raspberry Pi:

1. Requirements
	- Raspberry Pi with Raspbian (http://www.raspberrypi.org/)
	- Bluetooth Dongle
	- Bluez Version 5.16 http://www.bluez.org/download/
	
2. Installation of bluez
	- Bluez is the official Bluetooth Stack for Linux
	
	1. Update repositories: sudo apt-get update
	2. Kernel ipdate: sudo rpi-update
	3. Dist upgrade: sudo apt-get dist-upgrade
	4. Install dependencies for bluez:
		sudo apt-get install libusb-dev libdbus-1-dev libglib2.0-dev automake libudev-dev libical-dev libreadline-dev
	5. Download bluez: wget http://www.kernel.org/pub/linux/bluetooth/bluez-5.16.tar.xz
	6. Untar: tar -xJf bluez-5.16.tar.xz
	7. Install (type the following commands in the bluez folder):
		- sudo ./configure -disable-systemd
		- sudo make
		- sudo make install
	8. Install gatttool (you can find it in the bluez-folder attrib/gatttool)
		- sudo cp ./attrib/gatttool /usr/local/bin/gatttool
		
3. Installation of the bPart tool
    1. install dependencies: pexpect (http://pexpect.readthedocs.org/en/latest/) 
	2. git clone
  
4. Activate Bluetooth interface: sudo hciconfig hci0 up (use "sudo hciconfig hci0 down" to deactivate)