from PySide6.QtCore import QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from button_mapping import carregar_mapeamento_atual
from calibration import carregar_calibracao
from ui.button_mapping_page import ButtonMappingPage
from ui.calibration_page import CalibrationPage
from ui.connection_page import ConnectionPage
from ui.pen_cursor import PenCursor
from windows_pen import WindowsPenError, WindowsPenInjector


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("S Pen Bridge")
        self.resize(1100, 760)
        self.setMinimumSize(820, 620)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(224)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(20, 26, 16, 20)
        sidebar_layout.setSpacing(8)

        brand = QLabel("S Pen Bridge")
        brand.setObjectName("brand")
        sidebar_layout.addWidget(brand)
        sidebar_layout.addSpacing(24)

        self.connection_button = QPushButton("Conexão e caneta")
        self.connection_button.setObjectName("navActive")
        self.connection_button.clicked.connect(lambda: self._show_page(0))
        sidebar_layout.addWidget(self.connection_button)

        self.calibration_button = QPushButton("Calibração")
        self.calibration_button.clicked.connect(lambda: self._show_page(1))
        sidebar_layout.addWidget(self.calibration_button)

        self.mapping_button = QPushButton("Mapeamento dos botões")
        self.mapping_button.clicked.connect(lambda: self._show_page(2))
        sidebar_layout.addWidget(self.mapping_button)
        sidebar_layout.addStretch()

        version = QLabel("Eventos ao vivo · Windows Ink")
        version.setObjectName("sidebarFooter")
        sidebar_layout.addWidget(version)

        layout.addWidget(sidebar)
        calibration = carregar_calibracao()
        self.pen_injector = None
        pointer_error = None
        try:
            self.pen_injector = WindowsPenInjector(
                calibration=calibration,
                button_mapping=carregar_mapeamento_atual(),
            )
        except WindowsPenError as erro:
            pointer_error = str(erro)

        self.pages = QStackedWidget()
        self.connection_page = ConnectionPage(
            calibration,
            pointer_available=self.pen_injector is not None,
            pointer_error=pointer_error,
        )
        self.calibration_page = CalibrationPage(calibration)
        self.mapping_page = ButtonMappingPage()
        self.calibration_page.calibration_saved.connect(self._set_calibration)
        self.mapping_page.mapping_saved.connect(self._set_button_mapping)
        self.connection_page.pen_state_changed.connect(self._update_pen_cursor)
        self.connection_page.pointer_state_changed.connect(self._inject_windows_pen)
        self.connection_page.pen_state_changed.connect(
            self.calibration_page.update_pen_state
        )
        self.connection_page.stream_ended.connect(self._hide_pen_cursor)
        self.pages.addWidget(self.connection_page)
        self.pages.addWidget(self.calibration_page)
        self.pages.addWidget(self.mapping_page)
        layout.addWidget(self.pages, 1)
        self.pen_cursor = PenCursor()
        self._navigation_buttons = (
            self.connection_button,
            self.calibration_button,
            self.mapping_button,
        )
        self.setCentralWidget(central)
        self.setStyleSheet(
            "QMainWindow, QWidget {"
            "font-family: 'Segoe UI'; font-size: 14px; color: #202020;"
            "}"
            "QMainWindow { background: #f7f8fa; }"
            "#sidebar { background: #f0f2f5; border-right: 1px solid #e1e4e8; }"
            "#brand { font-size: 20px; font-weight: 650; color: #16324f; }"
            "#sidebarFooter { color: #626b75; font-size: 12px; }"
            "QPushButton { min-height: 38px; padding: 0 12px; text-align: left;"
            "border: 0; border-radius: 6px; background: transparent; }"
            "QPushButton:hover:enabled { background: #e4e9ef; }"
            "QPushButton#navActive { background: #dceaf7; color: #064a83; font-weight: 600; }"
            "QPushButton:disabled { color: #838b94; }"
            "QLabel#pageTitle { font-size: 27px; font-weight: 600; color: #19232d; }"
            "QLabel#sectionTitle { font-size: 16px; font-weight: 600; }"
            "QLabel#muted { color: #5f6872; }"
            "QLabel#status { padding: 10px 12px; border-radius: 6px; background: #edf1f5; }"
            "QLabel#warning { color: #66551c; background: #fff7dc; padding: 10px 12px; border-radius: 6px; }"
            "QLineEdit, QListWidget { background: #ffffff; border: 1px solid #cbd1d8;"
            "border-radius: 6px; padding: 8px; selection-background-color: #cfe4f7; }"
            "QLineEdit:focus, QListWidget:focus { border: 1px solid #2878bd; }"
            "QPushButton#primary { background: #0867b2; color: white; font-weight: 600; }"
            "QPushButton#primary:hover:enabled { background: #075a9b; }"
            "QPushButton#secondary { background: #e9edf1; }"
            "QPushButton#secondary:hover:enabled { background: #dfe4e9; }"
            "QPushButton:disabled { color: #89919a; background: #e8ebef; }"
        )

    def _show_page(self, index):
        self.pages.setCurrentIndex(index)
        for button_index, button in enumerate(self._navigation_buttons):
            button.setObjectName("navActive" if button_index == index else "")
            button.style().unpolish(button)
            button.style().polish(button)

    def _update_pen_cursor(self, state):
        if self.connection_page.inject_checkbox.isChecked() and state.in_range:
            self.pen_cursor.follow(QCursor.pos())
        else:
            self.pen_cursor.hide()

    def _inject_windows_pen(self, state):
        if not self.connection_page.inject_checkbox.isChecked() or not self.pen_injector:
            return
        try:
            self.pen_injector.inject(state)
        except WindowsPenError as erro:
            self.connection_page.set_pointer_registration(False, str(erro))
            self.pen_injector.close()
            self.pen_injector = None
            self.pen_cursor.hide()

    def _set_calibration(self, calibration):
        self.connection_page.set_calibration(calibration)
        if self.pen_injector:
            self.pen_injector.set_calibration(calibration)

    def _set_button_mapping(self, mapping):
        if self.pen_injector:
            self.pen_injector.set_button_mapping(mapping)

    def _hide_pen_cursor(self):
        self.pen_cursor.hide()

    def closeEvent(self, event):
        if not self.connection_page.encerrar_leitura():
            event.ignore()
            QTimer.singleShot(100, self.close)
            return
        self.pen_cursor.hide()
        if self.pen_injector:
            self.pen_injector.close()
            self.pen_injector = None
        super().closeEvent(event)
