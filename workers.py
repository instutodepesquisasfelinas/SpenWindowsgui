from PySide6.QtCore import QCoreApplication, QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    finished = Signal(object, object)

    def __init__(self):
        super().__init__(QCoreApplication.instance())


class FunctionWorker(QRunnable):
    def __init__(self, function, *args):
        super().__init__()
        self.function = function
        self.args = args
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            resultado = self.function(*self.args)
        except Exception as erro:
            resultado = (False, str(erro))
        self.signals.finished.emit(self, resultado)