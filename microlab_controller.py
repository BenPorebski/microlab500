import sys, os, time, glob
from PySide2.QtWidgets import QApplication, QMessageBox

import PySide2
import PySide2.QtGui
from PySide2 import QtGui, QtCore, QtWidgets

import qdarkstyle

from PySide2.QtUiTools import QUiLoader
from PySide2.QtWidgets import QApplication
from PySide2.QtCore import QFile, QTimer

import backend




def connect_to_pump():
    ## Connect to pump.
    selected_com_port = window.commCombo.currentText()

    pump.connect(selected_com_port)


def disconnect():
    ## Disconnect from the pump.
    pump.disconnect()

def initialise():
    # Reinitialise the pump.
    pump.initialise()

def pollStatus():

    if pump.__PUMP_CONNECTION__ == 1:
        pump.pollPumpStatus()
        window.commConnect.setEnabled(False)
        window.commDisconnect.setEnabled(True)
        window.commInitialise.setEnabled(True)

        # Pump buttons
        window.pumpGo.setEnabled(True)
        window.pumpStop.setEnabled(True)
        window.repaint()
    else:
        window.commConnect.setEnabled(True)
        window.commDisconnect.setEnabled(False)
        window.commInitialise.setEnabled(False)

        # Pump buttons
        window.pumpGo.setEnabled(False)
        window.pumpStop.setEnabled(False)
        window.repaint()



    status_text = ''
    if pump.__PUMP_CONNECTION__ == 0:
        status_text += 'Disconnected'
    elif pump.__PUMP_CONNECTION__ == 1:
        status_text += 'Connected'

    if pump.__PUMP_STATUS__ == 0:
        status_text += ', Uninitialised'
    elif pump.__PUMP_STATUS__ == 1:
        status_text += ', Ready'
        window.pumpGo.setEnabled(True)
    elif pump.__PUMP_STATUS__ == 2:
        window.pumpGo.setEnabled(False)
        status_text += ', Busy'

    window.pumpStatus.setText(status_text)



def refreshCommPorts():
    print('Refreshing com ports.')

    search_dir = '/dev'
    files = glob.glob(os.path.join(search_dir, 'tty*'))
    files.sort(key=lambda x: os.path.getmtime(x), reverse=True)

    window.commCombo.clear()
    window.commCombo.addItems(files)


def pumpcmd():
    pump.pumpCmd(syringe=window.syringeMode.currentText(), volume=float(window.volume.text()),
        aspirate=float(window.aspirate_rate.text()), dispense=float(window.dispense_rate.text()))

def pumpstopcmd():
    pump.stopPump()



if __name__ == "__main__":
    app = QApplication(sys.argv)

    x = qdarkstyle.load_stylesheet_pyside2()
    app.setStyleSheet(x)

    ui_file = QFile("main.ui")
    ui_file.open(QFile.ReadOnly)

    loader = QUiLoader()
    window = loader.load(ui_file)
    ui_file.close()

    # Instance the pump.
    pump = backend.pumpObject()

    ## Populate the comm port combo box.
    refreshCommPorts()

    # Setup button connections
    window.commRefresh.clicked.connect(refreshCommPorts)
    window.commConnect.clicked.connect(connect_to_pump)
    window.commDisconnect.clicked.connect(disconnect)
    window.commInitialise.clicked.connect(initialise)
    window.pumpGo.clicked.connect(pumpcmd)
    window.pumpStop.clicked.connect(pumpstopcmd)

    window.show()



    statusTimer = QTimer()
    statusTimer.timeout.connect(pollStatus)
    statusTimer.start(500) ## Poll the pump status every 500ms.





    sys.exit(app.exec_())