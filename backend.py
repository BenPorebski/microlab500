import serial
import time
import logging
from datetime import datetime





## Configure the logger.

LOG_FILE = '%s_microlab.log' % (datetime.now().strftime("%Y:%m:%d:%H:%M:%S"))
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO, filename=LOG_FILE)


class pumpObject():

    def __init__(self):
        self.__PUMP_CONNECTION__ = 0 # 0 = Disconnected, 1 = Connected
        self.__PUMP_STATUS__ = 0 # 0 = Uninitialised, 1 = Ready, 2 = Busy
        self.__PUMP_STOP__ = 0 # 0 = Nothing, 1 = Immediate stop, break all pumping loops.


        ## Pumping state details.
        # Current action of a single stroke.
        self.__direction__ = '' # Aspirate or dispense.
        self.__pumping_volume__ = 0 ## ul.
        self.__flow_rate__ = 0 # ul/minute.

        # Compound task.
        self.__pumped_volume__ = 0 # ul.
        self.__total_volume__ = 0 # ul.

        # Time.
        self.__time_start__ = 0 # unix time stamp.
        self.__time_elapsed__ = 0 # seconds.
        self.__time_estimated__ = 0 # seconds.






    def connect(self, serial_port, baud=9600):
        logging.info('Attempting to connect to %s.' % (serial_port))
        try:
            self.serialObject = serial.Serial(serial_port, baud, parity=serial.PARITY_ODD, bytesize=7, stopbits=serial.STOPBITS_ONE, timeout=10)
            self.__PUMP_CONNECTION__ = 1
        except:
            logging.info('Unable to connect to device.')

        if self.__PUMP_CONNECTION__ == 1: ## We are connected to the serial port.
            logging.info('Connected to %s.' % (self.serialObject.name))

            # Setup hardware address
            self.serialObject.write(b'1a\r')
            recv = self.read_from_pump()
            logging.info(recv)
            recv = self.read_from_pump()
            logging.info(recv)

            # Initialise the instrument.
            # self.serialObject.write(b'aXR\r')
            # recv = self.read_from_pump()
            # print(recv)
            # recv = self.read_from_pump()
            # print(recv)
            self.__PUMP_STATUS__ = 2

            while self.__PUMP_STATUS__ == 2:
                time.sleep(0.1)
                self.pollPumpStatus()


    def initialise(self):
        # Initialise the instrument.
        self.serialObject.write(b'aXR\r')
        recv = self.read_from_pump()
        logging.info(recv)
        recv = self.read_from_pump()
        logging.info(recv)
        self.__PUMP_STATUS__ = 2

        while self.__PUMP_STATUS__ == 2:
            time.sleep(0.1)
            self.pollPumpStatus()


    def disconnect(self):
        logging.info('Attempting to disconnect from %s.' % (self.serialObject.name))
        self.serialObject.close()
        self.__PUMP_CONNECTION__ = 0
        self.__PUMP_STATUS__ = 0
        logging.info('Disconnected.')



    def read_from_pump(self):
        time.sleep(0.01)
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
        logging.info(firmware_bytes)
        return firmware_bytes


    def stopPump(self):
        self.__PUMP_STOP__ = 1

        self.serialObject.write(b'aK\r')
        ack = self.read_from_pump()
        ack = self.read_from_pump()
        time.sleep(0.1)
        self.serialObject.write(b'aV\r')
        ack = self.read_from_pump()
        ack = self.read_from_pump()
        logging.info('Stopping pump! Clearing command queue.')

        # Wait for pump to be ready.
        while self.__PUMP_STATUS__ == 2:
            time.sleep(0.1)
            self.pollPumpStatus()
        logging.info('Pump stopped.')


    def dispensePump(self, syringe='A+B', dispense=2500, syringe_volume=500.0, stroke_steps=1000.0):
        # Dispense syringe volume to waste.
        dispense_sec_per_full_stroke = round(syringe_volume/(dispense/60.0))
        pump_instruction = 'M0S%dN0' % (dispense_sec_per_full_stroke)

        if syringe == 'A+B':
            dispense_cmd_to_send = 'aBO%sOCO%sOR\r' % (pump_instruction, pump_instruction)
        elif syringe == 'A':
            dispense_cmd_to_send = 'aBO%sOR\r' % (pump_instruction)
        elif syringe == 'B':
            dispense_cmd_to_send = 'aCO%sOR\r' % (pump_instruction)


        logging.info("Dispensing syringe to waste.")
        self.__direction__ = 'Dispensing'
        self.__pumping_volume__ = syringe_volume
        self.__flow_rate__ = dispense

        self.serialObject.write(bytearray(dispense_cmd_to_send.encode('ascii')))
        ack = self.read_from_pump()
        cmdecho = self.read_from_pump()

        logging.info(ack)
        logging.info(cmdecho)
        self.__PUMP_STATUS__ = 2


        # Wait for pump to be ready.
        while self.__PUMP_STATUS__ == 2:
            time.sleep(0.1)
            self.pollPumpStatus()
            if self.__PUMP_STOP__ == 1:
                break



    def checkPumpConfig(self):
        ## Checks the pump configuration.

        logging.info('Checking pump config.')
        self.serialObject.write(b'aH\r')
        ack = self.read_from_pump()
        configBytes = self.read_from_pump()

        config = configBytes[1:2].decode('utf-8')
        logging.info(ack)
        logging.info(configBytes)

        self.serialObject.write(b'aJ\r')
        ack = self.read_from_pump()
        configBytes = self.read_from_pump()

        config = configBytes[1:2].decode('utf-8')
        logging.info(ack)
        logging.info(configBytes)


    def pumpCmd(self, syringe='A+B', volume=100, aspirate=1000, dispense=2500, syringe_volume=500.0):
        ## This function allows for pumping volumes greater than the syringe volume.

        stroke_steps = 1000.0

        volume_remaining = volume

        while volume_remaining > 0:
            # if self.__PUMP_STATUS__ == 2:
            #     time.sleep(0.3)

            # If we observe the stop command, break this loop.
            if self.__PUMP_STOP__ == 1:
                break

            if volume_remaining > syringe_volume:
                self.pumpCmdSingleStroke(syringe, syringe_volume, aspirate, dispense, stroke_steps, syringe_volume)
                volume_remaining = volume_remaining-syringe_volume
            else:
                self.pumpCmdSingleStroke(syringe, volume_remaining, aspirate, dispense, stroke_steps, syringe_volume)
                volume_remaining = volume_remaining-syringe_volume

        self.__PUMP_STOP__ = 0


    def pumpCmdSingleStroke(self, syringe='A+B', volume=100, aspirate=1000, dispense=2500, stroke_steps=1000.0, syringe_volume=500.0):
        ## Instructs the pump to pump a single stroke.

        if volume > syringe_volume:
            logging.error("Unable to pump %d ul as this is greater than the syringe volume of %d." % (volume, syringe_volume))
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
            logging.info("Dispensing syringe to waste.")
            self.__direction__ = 'Dispensing'
            self.__pumping_volume__ = syringe_volume
            self.__flow_rate__ = dispense

            self.serialObject.write(bytearray(dispense_cmd_to_send.encode('ascii')))
            ack = self.read_from_pump()
            cmdecho = self.read_from_pump()

            logging.info(ack)
            logging.info(cmdecho)
            self.__PUMP_STATUS__ = 2


        # Wait for pump to be ready.
        while self.__PUMP_STATUS__ == 2:
            time.sleep(0.1)
            self.pollPumpStatus()
            if self.__PUMP_STOP__ == 1:
                break


        # Aspirate the syringe.
        logging.info('Aspirating %d uL.' % (volume))
        self.__direction__ = 'Aspirating'
        self.__pumping_volume__ = volume
        self.__flow_rate__ = aspirate

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

        config = configBytes[1:2].decode('utf-8')
        logging.info(ack)
        logging.info(configBytes)

        while self.__PUMP_STATUS__ == 2:
            time.sleep(0.1)
            self.pollPumpStatus()



    def pollPumpStatus(self):
        if self.__PUMP_CONNECTION__ == 1:
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





