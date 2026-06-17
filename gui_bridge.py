from PyQt6.QtCore import QObject, pyqtSignal


class ExtractionSignals(QObject):
    progress      = pyqtSignal(str, float, str)
    page_detected = pyqtSignal(int, bytes)
    log           = pyqtSignal(str)
    error         = pyqtSignal(str)
    completed     = pyqtSignal(int)
    cancelled     = pyqtSignal()

    def wire(self, api):
        api.set_on_progress(lambda p, pc, d: self.progress.emit(p, pc, d))
        api.set_on_page_detected(lambda i, b: self.page_detected.emit(i, b))
        api.set_on_log(lambda m: self.log.emit(m))
        api.set_on_error(lambda m: self.error.emit(m))
        api.set_on_completed(lambda c: self.completed.emit(c))
        api.set_on_cancelled(lambda: self.cancelled.emit())
