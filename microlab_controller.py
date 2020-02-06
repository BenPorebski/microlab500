import sys, os, time, glob
import logging


from PySide2.QtGui import *
from PySide2.QtWidgets import *
from PySide2.QtCore import *
from PySide2.QtUiTools import QUiLoader

import qdarkstyle

import backend



## Configure the logger.
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO)










class WorkerSignals(QObject):
    '''
    Defines the signals available from a running worker thread.

    Supported signals are:

    finished
        No data

    error
        `tuple` (exctype, value, traceback.format_exc() )

    result
        `object` data returned from processing, anything

    progress
        `int` indicating % progress

    '''
    finished = Signal()
    error = Signal(tuple)
    result = Signal(object)
    progress = Signal(int)


class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
            super(Worker, self).__init__()

            self.fn = fn
            self.args = args
            self.kwargs = kwargs
            self.signals = WorkerSignals()


    @Slot()
    def run(self):
        '''Launch the thread runner and try execute the function requested.'''

        try:
            result = self.fn(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)  # Return the result of the processing
        finally:
            self.signals.finished.emit()  # Done



class mainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.threadpool = QThreadPool()

        self.backend = backend.pumpObject()

        self.setupUI()

        self.refreshCommPorts()

        self.statusTimer = QTimer()
        self.statusTimer.timeout.connect(self.pollStatus)
        self.statusTimer.start(500) ## Poll the pump status every 500ms.



    def setupUI(self):
        x = qdarkstyle.load_stylesheet_pyside2()
        app.setStyleSheet(x)

        ui_file = QFile("main.ui")
        ui_file.open(QFile.ReadOnly)

        loader = QUiLoader()
        self.window = loader.load(ui_file)
        ui_file.close()

        self.window.show()


        # Setup button connections
        self.window.commRefresh.clicked.connect(self.refreshCommPorts)
        self.window.commConnect.clicked.connect(self.connect)
        self.window.commDisconnect.clicked.connect(self.disconnect)
        self.window.commInitialise.clicked.connect(self.initialise)
        self.window.pumpGo.clicked.connect(self.pumpcmd)
        self.window.pumpStop.clicked.connect(self.pumpstopcmd)




    def refreshCommPorts(self):
        logging.info('Refreshing com ports.')

        search_dir = '/dev'
        files = glob.glob(os.path.join(search_dir, 'tty*'))
        files.sort(key=lambda x: os.path.getmtime(x), reverse=True)

        self.window.commCombo.clear()
        self.window.commCombo.addItems(files)


    def connect(self):
        ## Connect to pump.
        selected_com_port = self.window.commCombo.currentText()
        # self.backend.connect(selected_com_port)
        worker = Worker(self.backend.connect, selected_com_port)
        self.threadpool.start(worker)


    def disconnect(self):
        ## Disconnect from the pump.
        worker = Worker(self.backend.disconnect)
        self.threadpool.start(worker)

        # self.statusTimer.stop() # Stop the status timer.


    def initialise(self):
        # Initialise the pump.
        worker = Worker(self.backend.initialise)
        self.threadpool.start(worker)



    def pollStatus(self):
        # Pump status polling.
        # Used to update buttons and pump status text on gui.

        if self.backend.__PUMP_CONNECTION__ == 1:
            # if self.backend.__PUMP_STATUS__ != 2:
            #     worker = Worker(self.backend.pollPumpStatus)
            #     self.threadpool.start(worker)

            self.window.commConnect.setEnabled(False)
            self.window.commDisconnect.setEnabled(True)
            self.window.commInitialise.setEnabled(True)

            # Pump buttons
            self.window.pumpGo.setEnabled(True)
            self.window.pumpStop.setEnabled(True)
            self.window.repaint()
        else:
            self.window.commConnect.setEnabled(True)
            self.window.commDisconnect.setEnabled(False)
            self.window.commInitialise.setEnabled(False)

            # Pump buttons
            self.window.pumpGo.setEnabled(False)
            self.window.pumpStop.setEnabled(False)
            self.window.repaint()

        status_text = ''
        if self.backend.__PUMP_CONNECTION__ == 0:
            status_text += 'Disconnected'
        elif self.backend.__PUMP_CONNECTION__ == 1:
            status_text += 'Connected'

        if self.backend.__PUMP_STATUS__ == 0:
            status_text += ', Uninitialised'
        elif self.backend.__PUMP_STATUS__ == 1:
            status_text += ', Ready'
            self.window.pumpGo.setEnabled(True)
        elif self.backend.__PUMP_STATUS__ == 2:
            self.window.pumpGo.setEnabled(False)
            status_text += ', Busy'

        self.window.pumpStatus.setText(status_text)



    def pumpcmd(self):
        worker = Worker(self.backend.pumpCmd, syringe=self.window.syringeMode.currentText(), volume=float(self.window.volume.text()),
            aspirate=float(self.window.aspirate_rate.text()), dispense=float(self.window.dispense_rate.text()))
        self.threadpool.start(worker)

    def pumpstopcmd(self):
        worker = Worker(self.backend.stopPump)
        self.threadpool.start(worker)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = mainWindow()


    sys.exit(app.exec_())