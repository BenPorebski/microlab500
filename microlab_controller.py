import sys, os, time, glob
import logging
import traceback

from PySide2.QtGui import *
from PySide2.QtWidgets import *
from PySide2.QtCore import *
from PySide2.QtUiTools import QUiLoader

import qdarkstyle

import backend





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
        self.backend = backend.pumpObject()

        self.threadpool = QThreadPool()

        self.setupUI()

        self.refreshCommPorts()

        self.statusTimer = QTimer()
        self.statusTimer.timeout.connect(self.pollStatus)
        self.statusTimer.start(500) ## Poll the pump status every 500ms.

        self.log_fh = open(backend.LOG_FILE, 'r')


    def setupUI(self):
        # x = qdarkstyle.load_stylesheet_pyside2()
        # app.setStyleSheet(x)

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
        self.window.pumpDispense.clicked.connect(self.pumpdispensecmd)




    def refreshCommPorts(self):
        backend.logging.info('Refreshing com ports.')

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



    def initialise(self):
        # Initialise the pump.
        worker = Worker(self.backend.initialise)
        self.threadpool.start(worker)



    def pollStatus(self):
        # Pump status polling.
        # Used to update buttons and pump status text on gui.

        status_text = ''
        if self.backend.__PUMP_CONNECTION__ == 0:
            status_text += 'Disconnected'
        elif self.backend.__PUMP_CONNECTION__ == 1:
            status_text += 'Connected'

        if self.backend.__PUMP_CONNECTION__ == 1:

            self.window.commConnect.setEnabled(False)
            self.window.commDisconnect.setEnabled(True)
            self.window.commInitialise.setEnabled(True)

            if self.backend.__PUMP_STATUS__ == 0:
                status_text += ', Uninitialised'
            elif self.backend.__PUMP_STATUS__ == 1:
                status_text += ', Ready'
                self.window.pumpGo.setEnabled(True)
                self.window.pumpDispense.setEnabled(True)
            elif self.backend.__PUMP_STATUS__ == 2:
                self.window.pumpGo.setEnabled(False)
                self.window.pumpDispense.setEnabled(False)
                status_text += ', Busy'

            # Pump buttons
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



        self.window.pumpStatus.setText(status_text)

        # Update the log file stream.
        log_data_line = self.log_fh.readline().rstrip()
        if log_data_line:
            self.window.log_data_view.appendPlainText(log_data_line)



        ## Pumping details. Update from backend variables only if actively pumping.
        if self.backend.__PUMP_STATUS__ == 2: ## Pump status of 2 is busy.

            # Current task.
            self.window.current_task.setText('%s %d µl at %d µl/minute.' % (
                self.backend.__direction__, self.backend.__pumping_volume__, self.backend.__flow_rate__))

            # Volume pumped.
            self.window.task_progress.setText('Progress: %d µl of %d µl.' % (
                self.backend.__pumped_volume__, self.backend.__total_volume__))

            # Time elapsed/total.
            time_elapsed = self.backend.__time_start__ - time.time()
            self.window.time_progress.setText('Time elapsed/Time total: %d seconds of %d seconds.' % (
                time_elapsed, self.backend.__time_estimated__))

        # else:
            # self.window.current_task.setText('')
        #     self.window.task_progress.setText('')
        #     self.window.time_progress.setText('')





    def pumpcmd(self):
        # Check to make sure rates are within spec of the pump.
        volume = float(self.window.volume.text())
        aspirate_rate = float(self.window.aspirate_rate.text())
        dispense_rate = float(self.window.dispense_rate.text())
        config_syringe_volume = float(self.window.config_syringe_volume.text())

        if self.window.volume_units.currentText() == 'ml':
            volume = volume *1000

        aspirate_sec_per_full_stroke = round(config_syringe_volume/(aspirate_rate/60.0))
        dispense_sec_per_full_stroke = round(config_syringe_volume/(dispense_rate/60.0))
        min_rate = config_syringe_volume*60.0/250.0
        max_rate = config_syringe_volume*60.0/1.0

        if aspirate_sec_per_full_stroke > 250 or aspirate_sec_per_full_stroke < 1:
            # Raise an error widget.
            rate_error = QMessageBox()
            rate_error.setIcon(QMessageBox.Critical)
            rate_error.setText("Invalid aspiration rate")
            rate_error.setInformativeText("Pump and syringe combination has a minimum and maximum aspiration rate of %d and %d ul/minute." % (
                min_rate, max_rate))
            rate_error.exec_()
            return

        if dispense_sec_per_full_stroke > 250 or dispense_sec_per_full_stroke < 1:
            # Raise an error widget.
            rate_error = QMessageBox()
            rate_error.setIcon(QMessageBox.Critical)
            rate_error.setText("Invalid dispense rate")
            rate_error.setInformativeText("Pump and syringe combination has a minimum and maximum dispense rate of %d and %d ul/minute." % (
                min_rate, max_rate))
            rate_error.exec_()
            return


        worker = Worker(self.backend.pumpCmd, syringe=self.window.syringeMode.currentText(), volume=volume,
            aspirate=aspirate_rate, dispense=dispense_rate, syringe_volume=config_syringe_volume)
        self.threadpool.start(worker)

    def pumpstopcmd(self):
        worker = Worker(self.backend.stopPump)
        self.threadpool.start(worker)

    def pumpdispensecmd(self):
        dispense_rate = float(self.window.dispense_rate.text())
        config_syringe_volume = float(self.window.config_syringe_volume.text())

        worker = Worker(self.backend.dispensePump, syringe=self.window.syringeMode.currentText(),
            dispense=dispense_rate, syringe_volume=config_syringe_volume)
        self.threadpool.start(worker)


if __name__ == "__main__":

    app = QApplication(sys.argv)
    app.setStyleSheet(qdarkstyle.load_stylesheet())

    window = mainWindow()


    sys.exit(app.exec_())
