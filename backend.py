import serial
import time
import PySide2
import PySide2.QtGui
from PySide2 import QtGui, QtCore, QtWidgets
from PySide2.QtUiTools import QUiLoader
from PySide2.QtWidgets import QApplication
from PySide2.QtCore import QFile, QTimer

class pumpObject:

    def __init__(self):
        self.__PUMP_CONNECTION__ = 0 # 0 = Disconnected, 1 = Connected
        self.__PUMP_STATUS__ = 0 # 0 = Uninitialised, 1 = Ready, 2 = Busy



    def connect(self, serial_port, baud=9600):
        print('Attempting to connect to %s.' % (serial_port))
        try:
            self.serialObject = serial.Serial(serial_port, baud, parity=serial.PARITY_ODD, bytesize=7, stopbits=serial.STOPBITS_ONE, timeout=10)
            self.__PUMP_CONNECTION__ = 1
        except:
            print('Unable to connect to device.')

        if self.__PUMP_CONNECTION__ == 1: ## We are connected to the serial port.
            print('Connected to %s.' % (self.serialObject.name))

            # Setup hardware address
            self.serialObject.write(b'1a\r')
            recv = self.read_from_pump()
            print(recv)
            recv = self.read_from_pump()
            print(recv)

            # Initialise the instrument.
            # self.serialObject.write(b'aXR\r')
            # recv = self.read_from_pump()
            # print(recv)
            # recv = self.read_from_pump()
            # print(recv)
            self.__PUMP_STATUS__ = 2


    def initialise(self):
            # Initialise the instrument.
            self.serialObject.write(b'aXR\r')
            recv = self.read_from_pump()
            print(recv)
            recv = self.read_from_pump()
            print(recv)
            self.__PUMP_STATUS__ = 2

    def disconnect(self):
        print('Attempting to disconnect from %s.' % (self.serialObject.name))
        self.serialObject.close()
        self.__PUMP_CONNECTION__ = 0
        self.__PUMP_STATUS__ = 0
        print('Disconnected.')



    def read_from_pump(self):
        QTimer.singleShot(10, lambda: None)
        recv_buffer = b''
        while True:
            recv_byte = self.serialObject.read(1)
            recv_buffer += recv_byte
            if recv_byte == b'\r':
                break
        return recv_buffer

    def getFirmwareVersion(self):
        self.serialObject.write(b'aU\r')
        firmware_bytes = self.serialObject.read_until(b'\r')
        print(firmware_bytes)
        return firmware_bytes


    def stopPump(self):
        self.serialObject.write(b'aK\r')
        ack = self.read_from_pump()
        ack = self.read_from_pump()
        self.serialObject.write(b'aV\r')
        ack = self.read_from_pump()
        ack = self.read_from_pump()
        print('Stopping pump! Clearing command queue.')


    def checkPumpConfig(self):
        ## Checks the pump configuration.

        print('Checking pump config.')
        self.serialObject.write(b'aH\r')
        ack = self.read_from_pump()
        configBytes = self.read_from_pump()

        config = configBytes[1:2].decode('utf-8')
        print(ack)
        print(configBytes)

        self.serialObject.write(b'aJ\r')
        ack = self.read_from_pump()
        configBytes = self.read_from_pump()

        config = configBytes[1:2].decode('utf-8')
        print(ack)
        print(configBytes)


    def pumpCmd(self, syringe='A+B', volume=100, aspirate=1000, dispense=2500):
        ## This function allows for pumping volumes greater than the syringe volume.

        stroke_steps = 1000.0
        syringe_volume = 500.0 # in uL

        volume_remaining = volume

        while volume_remaining > 0:
            # if self.__PUMP_STATUS__ == 2:
            #     time.sleep(0.3)

            if volume_remaining > syringe_volume:
                self.pumpCmdSingleStroke(syringe, syringe_volume, aspirate, dispense, stroke_steps, syringe_volume)
                volume_remaining = volume_remaining-syringe_volume
            else:
                self.pumpCmdSingleStroke(syringe, volume_remaining, aspirate, dispense, stroke_steps, syringe_volume)
                volume_remaining = volume_remaining-syringe_volume




    def pumpCmdSingleStroke(self, syringe='A+B', volume=100, aspirate=1000, dispense=2500, stroke_steps=1000.0, syringe_volume=500.0):
        ## Instructs the pump to pump a single stroke.

        if volume > syringe_volume:
            print("Error: Unable to pump %d ul as this is greater than the syringe volume of %d." % (volume, syringe_volume))
            return

        step_per_uL = stroke_steps/syringe_volume

        steps_to_pump = volume*step_per_uL

        # Instrument speed is seconds per full stroke.
        # Need to convert ul/minute to seconds per full stroke.
        seconds_per_full_stroke = round(syringe_volume/(aspirate/60.0))
        dispense_sec_per_full_stroke = round(syringe_volume/(dispense/60.0))


        ## Get the absolute step position of both syringes.
        self.serialObject.write(b'aBYQP\r')
        ack = self.read_from_pump()
        absStepPosB = float(self.read_from_pump()[1:-1])

        self.serialObject.write(b'aCYQP\r')
        ack = self.read_from_pump()
        absStepPosC = float(self.read_from_pump()[1:2])


        # If syringe does not have enough volume available, dump the volume to waste.
        pump_instruction = 'M0S%dN0' % (dispense_sec_per_full_stroke)

        if syringe == 'A+B':
            dispense_cmd_to_send = 'aBO%sOCO%sOR\r' % (pump_instruction, pump_instruction)
        elif syringe == 'A':
            dispense_cmd_to_send = 'aBO%sOR\r' % (pump_instruction)
        elif syringe == 'B':
            dispense_cmd_to_send = 'aCO%sOR\r' % (pump_instruction)

        if absStepPosB+steps_to_pump > stroke_steps or absStepPosC+steps_to_pump > stroke_steps:
            print("Dispensing syringe to waste.")
            self.serialObject.write(bytearray(dispense_cmd_to_send.encode('ascii')))
            ack = self.read_from_pump()
            cmdecho = self.read_from_pump()

            # self.serialObject.write(b'aBOM0S3N5OCOM0S3N5OR\r')
            # ack = self.read_from_pump()
            # cmdecho = self.read_from_pump()
            print(ack)
            print(cmdecho)
            self.__PUMP_STATUS__ = 2

        # if absStepPosC+steps_to_pump > stroke_steps:
        #     self.serialObject.write(b'aCOM0S3N5OR\r')
        #     ack = self.read_from_pump()
        #     cmdecho = self.read_from_pump()
        #     print(ack)
        #     print(cmdecho)
        #     self.__PUMP_STATUS__ = 2

        # Wait for pump to be ready.
        while self.__PUMP_STATUS__ == 2:
            QTimer.singleShot(200, lambda: None)
            self.pollPumpStatus()


        print('Aspirating %d uL.' % (volume))
        pump_instruction = 'P%dS%dN5' % (steps_to_pump, seconds_per_full_stroke)

        if syringe == 'A+B':
            cmd_to_send = 'aBI%sOCI%sOR\r' % (pump_instruction, pump_instruction)
        elif syringe == 'A':
            cmd_to_send = 'aBI%sOR\r' % (pump_instruction)
        elif syringe == 'B':
            cmd_to_send = 'aCI%sOR\r' % (pump_instruction)


        self.serialObject.write(bytearray(cmd_to_send.encode('ascii')))
        # self.serialObject.write(b'aBIP210S30N5OR\r')
        ack = self.read_from_pump()
        configBytes = self.read_from_pump()

        self.__PUMP_STATUS__ = 2

        # self.serialObject.write(b'aCIP1050S3N5OR\r')
        # ack = self.read_from_pump()
        # configBytes = self.read_from_pump()

        config = configBytes[1:2].decode('utf-8')
        print(ack)
        print(configBytes)

        while self.__PUMP_STATUS__ == 2:
            # time.sleep(0.3)
            QTimer.singleShot(200, lambda: None)
            self.pollPumpStatus()



    def pollPumpStatus(self):
        # Check if instrument is busy.
        self.serialObject.write(b'aF\r')
        ack = self.read_from_pump()
        statusBytes = self.read_from_pump()

        statusByte = statusBytes[1:2].decode('utf-8')
        # print(statusByte)

        if statusByte == '*': ## Instrument is busy
            self.__PUMP_STATUS__ = 2
        elif statusByte == 'Y': ## Instrument is idle with nothing in command queue
            self.__PUMP_STATUS__ = 1
        elif statusByte == 'N': ## Instrument is idle with a non-empty command queue
            self.__PUMP_STATUS__ = 2


        # print(len(ack))
        # print(ack)
        # print(len(statusBytes))
        # print(statusBytes)

        # statusByte = bytearray(statusBytes.hex()[2:4],'ascii').encode()

        # statusByte = statusBytes[2:4].encode('ascii').hex()
        # print(statusByte)
        # print(bin(int(statusByte)))
        # bits =
        # print(str(bin(statusByte))[2:])
        # print(bin(ord(statusBytes[2:])))
        # print(bin(statusByte))

        #   101000
        # 00101000
        # 00101000
        # 0b110101100110


        # print('')

        # print(b'%b' % statusByte)
        # return statusBytes





