from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class PenCursor(QWidget):
    DIAMETER = 22
    SAMSUNG_BLUE = "#1428A0"

    def __init__(self):
        flags = (
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(self.DIAMETER, self.DIAMETER)
        self.hide()

    def follow(self, position):
        self.move(
            QPoint(
                position.x() - self.width() // 2,
                position.y() - self.height() // 2,
            )
        )
        if not self.isVisible():
            self.show()
        self.raise_()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipRegion(event.region())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 65))
        painter.drawEllipse(QRectF(4, 5, 16, 16))

        painter.setPen(QPen(QColor("white"), 2))
        painter.setBrush(QColor(self.SAMSUNG_BLUE))
        painter.drawEllipse(QRectF(2, 2, 17, 17))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#75B7FF"))
        painter.drawEllipse(QRectF(6, 5, 4, 4))