from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from calibration import (
    CALIBRACAO_PADRAO,
    normalizar_calibracao,
    orientar_coordenadas,
    salvar_calibracao,
)


class CalibrationPage(QWidget):
    calibration_saved = Signal(object)

    def __init__(self, calibration=None):
        super().__init__()
        self.calibration = normalizar_calibracao(calibration)
        self.latest_pen_state = None
        self.capture_buttons = {}
        self._build_ui()
        self._set_values(self.calibration)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(38, 30, 38, 26)
        layout.setSpacing(18)

        title = QLabel("Calibração")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        description = QLabel(
            "Ajuste o enquadramento e a orientação da S Pen para coincidir com a área de trabalho."
        )
        description.setObjectName("muted")
        description.setWordWrap(True)
        layout.addWidget(description)

        mapping_title = QLabel("Área ativa")
        mapping_title.setObjectName("sectionTitle")
        layout.addWidget(mapping_title)

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(14)
        self.orientation = QComboBox()
        self.orientation.addItem("Retrato", "portrait")
        self.orientation.addItem("Paisagem · giro horário", "landscape_cw")
        self.orientation.addItem("Paisagem · giro anti-horário", "landscape_ccw")
        form.addRow("Orientação dos dados", self.orientation)

        self.x0_spin = self._number(0.0, 1.0, 0.001, 3)
        self.x1_spin = self._number(0.0, 1.0, 0.001, 3)
        self.y0_spin = self._number(0.0, 1.0, 0.001, 3)
        self.y1_spin = self._number(0.0, 1.0, 0.001, 3)
        form.addRow("X0 · esquerda", self._boundary_row("x0", self.x0_spin))
        form.addRow("X1 · direita", self._boundary_row("x1", self.x1_spin))
        form.addRow("Y0 · topo", self._boundary_row("y0", self.y0_spin))
        form.addRow("Y1 · base", self._boundary_row("y1", self.y1_spin))

        self.scale_spin = self._number(0.25, 4.0, 0.05, 2)
        self.scale_slider = self._slider(25, 400)
        form.addRow("Escala", self._slider_row(self.scale_slider, self.scale_spin, 100))

        self.offset_x_spin = self._number(0.0, 1.0, 0.01, 2)
        self.offset_x_slider = self._slider(0, 100)
        form.addRow("Deslocamento horizontal", self._slider_row(self.offset_x_slider, self.offset_x_spin, 100))

        self.offset_y_spin = self._number(0.0, 1.0, 0.01, 2)
        self.offset_y_slider = self._slider(0, 100)
        form.addRow("Deslocamento vertical", self._slider_row(self.offset_y_slider, self.offset_y_spin, 100))
        layout.addLayout(form)

        orientation_title = QLabel("Orientação")
        orientation_title.setObjectName("sectionTitle")
        layout.addWidget(orientation_title)

        orientation = QHBoxLayout()
        self.swap_axes = QCheckBox("Trocar eixos X/Y")
        self.invert_x = QCheckBox("Inverter X")
        self.invert_y = QCheckBox("Inverter Y")
        orientation.addWidget(self.swap_axes)
        orientation.addWidget(self.invert_x)
        orientation.addWidget(self.invert_y)
        orientation.addStretch()
        layout.addLayout(orientation)

        actions = QHBoxLayout()
        self.save_button = QPushButton("Salvar calibração")
        self.save_button.setObjectName("primary")
        self.save_button.clicked.connect(self._save)
        self.reset_button = QPushButton("Restaurar padrão")
        self.reset_button.setObjectName("secondary")
        self.reset_button.clicked.connect(lambda: self._set_values(CALIBRACAO_PADRAO))
        actions.addWidget(self.save_button)
        actions.addWidget(self.reset_button)
        actions.addStretch()
        layout.addLayout(actions)

        self.status = QLabel("Os ajustes são aplicados ao iniciar a próxima leitura.")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.capture_status = QLabel(
            "Inicie a leitura e leve a ponta a cada extremo para capturar X0, X1, Y0 e Y1."
        )
        self.capture_status.setObjectName("muted")
        self.capture_status.setWordWrap(True)
        layout.addWidget(self.capture_status)
        layout.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll)

    @staticmethod
    def _number(minimum, maximum, step, decimals):
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        spin.setDecimals(decimals)
        spin.setFixedWidth(96)
        return spin

    @staticmethod
    def _slider(minimum, maximum):
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        return slider

    @staticmethod
    def _slider_row(slider, spin, multiplier):
        row = QHBoxLayout()
        slider.valueChanged.connect(lambda value: spin.setValue(value / multiplier))
        spin.valueChanged.connect(lambda value: slider.setValue(round(value * multiplier)))
        row.addWidget(slider, 1)
        row.addWidget(spin)
        return row

    def _boundary_row(self, name, spin):
        row = QHBoxLayout()
        row.addWidget(spin)
        button = QPushButton("Capturar posição")
        button.setObjectName("secondary")
        button.setEnabled(False)
        button.clicked.connect(lambda checked=False, key=name: self._capture_boundary(key))
        self.capture_buttons[name] = button
        row.addWidget(button)
        row.addStretch()
        return row

    def _set_values(self, calibration):
        values = normalizar_calibracao(calibration)
        self.scale_spin.setValue(values["scale"])
        self.offset_x_spin.setValue(values["offset_x"])
        self.offset_y_spin.setValue(values["offset_y"])
        self.x0_spin.setValue(values["x0"])
        self.x1_spin.setValue(values["x1"])
        self.y0_spin.setValue(values["y0"])
        self.y1_spin.setValue(values["y1"])
        self.orientation.setCurrentIndex(
            max(0, self.orientation.findData(values["orientation"]))
        )
        self.swap_axes.setChecked(values["swap_axes"])
        self.invert_x.setChecked(values["invert_x"])
        self.invert_y.setChecked(values["invert_y"])

    def _collect_values(self):
        return {
            "scale": self.scale_spin.value(),
            "offset_x": self.offset_x_spin.value(),
            "offset_y": self.offset_y_spin.value(),
            "orientation": self.orientation.currentData(),
            "x0": self.x0_spin.value(),
            "x1": self.x1_spin.value(),
            "y0": self.y0_spin.value(),
            "y1": self.y1_spin.value(),
            "swap_axes": self.swap_axes.isChecked(),
            "invert_x": self.invert_x.isChecked(),
            "invert_y": self.invert_y.isChecked(),
        }

    def _save(self):
        try:
            values = self._collect_values()
            if values["x1"] <= values["x0"]:
                raise ValueError("X1 (direita) precisa ser maior que X0 (esquerda).")
            if values["y1"] <= values["y0"]:
                raise ValueError("Y1 (base) precisa ser maior que Y0 (topo).")
            self.calibration = salvar_calibracao(normalizar_calibracao(values))
        except (OSError, ValueError) as erro:
            self.status.setText(f"Não foi possível salvar a calibração: {erro}")
            self.status.setStyleSheet("background: #fdeaea; color: #8b1e1e;")
            return

        self.status.setText("Calibração salva. Pare e reinicie a leitura para aplicar.")
        self.status.setStyleSheet("background: #e7f4e8; color: #155724;")
        self.calibration_saved.emit(dict(self.calibration))

    def update_pen_state(self, state):
        self.latest_pen_state = state
        calibration = normalizar_calibracao(
            {
                "orientation": self.orientation.currentData(),
                "swap_axes": self.swap_axes.isChecked(),
            }
        )
        x, y = orientar_coordenadas(state.x, state.y, calibration)
        self.capture_status.setText(f"Posição atual: X={x:.3f} · Y={y:.3f}")
        for button in self.capture_buttons.values():
            button.setEnabled(True)

    def _capture_boundary(self, name):
        if self.latest_pen_state is None:
            return
        calibration = normalizar_calibracao(
            {
                "orientation": self.orientation.currentData(),
                "swap_axes": self.swap_axes.isChecked(),
            }
        )
        x, y = orientar_coordenadas(
            self.latest_pen_state.x,
            self.latest_pen_state.y,
            calibration,
        )
        field = {
            "x0": self.x0_spin,
            "x1": self.x1_spin,
            "y0": self.y0_spin,
            "y1": self.y1_spin,
        }[name]
        field.setValue(x if name.startswith("x") else y)
        self.capture_status.setText(f"{name.upper()} capturado: {field.value():.3f}")