
import sys

from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow


if __name__ == "__main__":
    app = QApplication(sys.argv)

    app.setApplicationName("S Pen Bridge")
    janela = MainWindow()
    janela.show()

    sys.exit(app.exec())
