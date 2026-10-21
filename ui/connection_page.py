from PySide6.QtCore import Qt, QThreadPool, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from adb_connection import (
    conectar_dispositivo,
    desconectar_dispositivo,
    emparelhar_dispositivo,
    obter_dispositivos,
)
from calibration import normalizar_calibracao
from pen_reader import PenReader, detectar_evento_caneta, diagnosticar_leitura
from workers import FunctionWorker


class ConnectionPage(QWidget):
    pen_state_changed = Signal(object)
    stream_ended = Signal()

    def __init__(self, calibration=None):
        super().__init__()
        self.pool = QThreadPool.globalInstance()
        self.workers = {}
        self.controls = []
        self.selecionado_serial = None
        self.selecionado_estado = None
        self.pen_reader = None
        self.reader_error = False
        self.calibration = normalizar_calibracao(calibration)
        self._build_ui()
        self._consultar_dispositivos()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(38, 30, 38, 26)
        layout.setSpacing(14)

        titulo = QLabel("Conexão e caneta do Windows")
        titulo.setObjectName("pageTitle")
        layout.addWidget(titulo)

        subtitulo = QLabel("Conecte o tablet e acompanhe a S Pen em tempo real.")
        subtitulo.setObjectName("muted")
        layout.addWidget(subtitulo)

        instrucoes = QLabel(
            "Ative Opções do desenvolvedor > Depuração sem fio no tablet. "
            "Para parear, use “Parear dispositivo com código” e informe o endereço, "
            "a porta de pareamento e o código. Depois, conecte pela porta principal."
        )
        instrucoes.setWordWrap(True)
        instrucoes.setObjectName("muted")
        layout.addWidget(instrucoes)

        pair_heading = QLabel("Parear dispositivo")
        pair_heading.setObjectName("sectionTitle")
        layout.addWidget(pair_heading)

        pair_form = QFormLayout()
        pair_form.setHorizontalSpacing(14)
        pair_form.setVerticalSpacing(8)
        self.pair_endpoint = QLineEdit()
        self.pair_endpoint.setPlaceholderText("Ex.: 192.168.1.20:37000")
        self.pair_code = QLineEdit()
        self.pair_code.setPlaceholderText("Código mostrado no tablet")
        self.pair_code.setEchoMode(QLineEdit.EchoMode.Password)
        pair_form.addRow("IP e porta de pareamento", self.pair_endpoint)
        pair_form.addRow("Código de pareamento", self.pair_code)
        layout.addLayout(pair_form)

        self.pair_button = QPushButton("Emparelhar")
        self.pair_button.setObjectName("secondary")
        self.pair_button.clicked.connect(self._emparelhar)
        layout.addWidget(self.pair_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.controls.extend((self.pair_endpoint, self.pair_code, self.pair_button))

        connect_heading = QLabel("Conexão ADB")
        connect_heading.setObjectName("sectionTitle")
        layout.addWidget(connect_heading)

        connect_row = QHBoxLayout()
        self.endpoint = QLineEdit()
        self.endpoint.setPlaceholderText("IP e porta principal, ex.: 192.168.1.20:5555")
        self.connect_button = QPushButton("Conectar")
        self.connect_button.setObjectName("primary")
        self.connect_button.clicked.connect(self._conectar)
        self.disconnect_button = QPushButton("Desconectar")
        self.disconnect_button.setObjectName("secondary")
        self.disconnect_button.clicked.connect(self._desconectar)
        connect_row.addWidget(self.endpoint, 1)
        connect_row.addWidget(self.connect_button)
        connect_row.addWidget(self.disconnect_button)
        layout.addLayout(connect_row)
        self.controls.extend((self.endpoint, self.connect_button, self.disconnect_button))

        devices_header = QHBoxLayout()
        devices_title = QLabel("Dispositivos detectados")
        devices_title.setObjectName("sectionTitle")
        devices_header.addWidget(devices_title)
        devices_header.addStretch()
        self.refresh_button = QPushButton("Atualizar")
        self.refresh_button.setObjectName("secondary")
        self.refresh_button.clicked.connect(self._consultar_dispositivos)
        devices_header.addWidget(self.refresh_button)
        self.diagnose_button = QPushButton("Testar acesso à S Pen")
        self.diagnose_button.setObjectName("secondary")
        self.diagnose_button.setEnabled(False)
        self.diagnose_button.clicked.connect(self._diagnosticar)
        devices_header.addWidget(self.diagnose_button)
        layout.addLayout(devices_header)
        self.controls.extend((self.refresh_button, self.diagnose_button))

        self.devices = QListWidget()
        self.devices.setMinimumHeight(88)
        self.devices.setMaximumHeight(116)
        self.devices.currentItemChanged.connect(self._selecionar_dispositivo)
        layout.addWidget(self.devices)
        self.controls.append(self.devices)

        pen_heading = QLabel("Eventos da caneta")
        pen_heading.setObjectName("sectionTitle")
        layout.addWidget(pen_heading)

        pen_actions = QHBoxLayout()
        self.start_button = QPushButton("Iniciar leitura")
        self.start_button.setObjectName("primary")
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self._iniciar_leitura)
        self.stop_button = QPushButton("Parar")
        self.stop_button.setObjectName("secondary")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._parar_leitura)
        self.inject_checkbox = QCheckBox("Controlar Windows com a S Pen")
        self.inject_checkbox.setToolTip(
            "Envia posição, pressão, inclinação e botões como entrada de caneta do Windows."
        )
        self.inject_checkbox.setEnabled(False)
        pen_actions.addWidget(self.start_button)
        pen_actions.addWidget(self.stop_button)
        pen_actions.addSpacing(10)
        pen_actions.addWidget(self.inject_checkbox, 1)
        layout.addLayout(pen_actions)
        self.controls.extend((self.start_button, self.stop_button, self.inject_checkbox))

        self.latest_state = QLabel("S Pen parada.")
        self.latest_state.setObjectName("status")
        self.latest_state.setWordWrap(True)
        layout.addWidget(self.latest_state)

        self.event_log = QPlainTextEdit()
        self.event_log.setReadOnly(True)
        self.event_log.setMaximumBlockCount(160)
        self.event_log.setMinimumHeight(145)
        self.event_log.setPlaceholderText("Os estados da S Pen aparecerão aqui.")
        layout.addWidget(self.event_log)

        self.status = QLabel("Verificando disponibilidade do ADB…")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        note = QLabel(
            "A leitura contínua depende da permissão do Android. A injeção usa a API "
            "de ponteiro sintético do Windows 10 1809 ou posterior."
        )
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)

        scroll.setWidget(content)
        root.addWidget(scroll)

    def _executar(
        self,
        function,
        *args,
        refresh_devices=False,
        device_query=False,
        task="adb",
        mensagem_espera="Aguardando resposta do ADB…",
    ):
        self._definir_ocupado(True)
        self.status.setText(mensagem_espera)
        self.status.setStyleSheet("")
        worker = FunctionWorker(function, *args)
        self.workers[worker] = (refresh_devices, device_query, task)
        worker.signals.finished.connect(self._concluir)
        self.pool.start(worker)

    def _concluir(self, worker, resultado):
        refresh_devices, device_query, task = self.workers.pop(worker)
        self._definir_ocupado(False)
        sucesso, mensagem = resultado

        if task == "pen_setup":
            if sucesso:
                self._iniciar_reader(mensagem)
            else:
                self._mostrar_status(mensagem, False)
            return

        if device_query:
            self.devices.clear()
            if sucesso:
                for dispositivo in mensagem:
                    estado = {
                        "device": "Conectado",
                        "unauthorized": "Autorize no tablet",
                        "offline": "Offline",
                    }.get(dispositivo.estado, dispositivo.estado)
                    item = QListWidgetItem(f"{dispositivo.serial}    {estado}")
                    item.setData(Qt.ItemDataRole.UserRole, dispositivo.serial)
                    item.setData(Qt.ItemDataRole.UserRole + 1, dispositivo.estado)
                    self.devices.addItem(item)
                if self.devices.count() == 1:
                    self.devices.setCurrentRow(0)
                if mensagem:
                    self._mostrar_status(f"{len(mensagem)} dispositivo(s) detectado(s).", True)
                else:
                    self._mostrar_status(
                        "Nenhum dispositivo conectado. Ative a Depuração sem fio e atualize a lista.",
                        False,
                    )
            else:
                self._mostrar_status(mensagem, False)
            return

        self._mostrar_status(mensagem, sucesso)
        if refresh_devices:
            self._consultar_dispositivos()

    def _mostrar_status(self, mensagem, sucesso):
        self.status.setText(str(mensagem))
        self.status.setStyleSheet(
            "background: #e7f4e8; color: #155724;"
            if sucesso
            else "background: #fdeaea; color: #8b1e1e;"
        )

    def _definir_ocupado(self, ocupado):
        for control in self.controls:
            disponivel = not ocupado
            if control in (self.diagnose_button, self.start_button, self.inject_checkbox):
                disponivel = disponivel and self.selecionado_estado == "device"
            if control is self.stop_button:
                disponivel = False
            control.setEnabled(disponivel)

    def _consultar_dispositivos(self):
        self._executar(obter_dispositivos, device_query=True)

    def _emparelhar(self):
        self._executar(
            emparelhar_dispositivo,
            self.pair_endpoint.text(),
            self.pair_code.text(),
        )

    def _conectar(self):
        self._executar(
            conectar_dispositivo,
            self.endpoint.text(),
            refresh_devices=True,
        )

    def _desconectar(self):
        self._executar(
            desconectar_dispositivo,
            self.endpoint.text(),
            refresh_devices=True,
        )

    def _diagnosticar(self):
        if self.selecionado_serial is None:
            self._mostrar_status("Selecione um dispositivo ADB primeiro.", False)
            return
        self._executar(
            diagnosticar_leitura,
            self.selecionado_serial,
            mensagem_espera="Mova ou encoste a S Pen; aguardando um evento por até 8 segundos…",
        )

    def _iniciar_leitura(self):
        if self.selecionado_serial is None or self.selecionado_estado != "device":
            self._mostrar_status("Selecione um dispositivo ADB autorizado.", False)
            return
        self.event_log.clear()
        self.latest_state.setText("Localizando o evento da S Pen…")
        self._executar(
            detectar_evento_caneta,
            self.selecionado_serial,
            task="pen_setup",
            mensagem_espera="Lendo a lista de dispositivos de entrada do Android…",
        )

    def _iniciar_reader(self, dispositivo):
        self.reader_error = False
        reader = PenReader(
            self.selecionado_serial,
            dispositivo,
            inject_windows=self.inject_checkbox.isChecked(),
            calibration=self.calibration,
        )
        reader.stream_ready.connect(self._stream_pronto)
        reader.state_received.connect(self._estado_recebido)
        reader.error_occurred.connect(self._erro_stream)
        reader.finished.connect(self._stream_finalizado)
        self.pen_reader = reader
        self._definir_streaming(True)
        reader.start()

    def _definir_streaming(self, ativo):
        for control in self.controls:
            disponivel = not ativo
            if control in (self.diagnose_button, self.start_button, self.inject_checkbox):
                disponivel = disponivel and self.selecionado_estado == "device"
            if control is self.stop_button:
                disponivel = ativo
            control.setEnabled(disponivel)

    def _stream_pronto(self, mensagem):
        self._mostrar_status(mensagem, True)
        self.latest_state.setText("Aguardando movimento da S Pen…")

    def _estado_recebido(self, estado):
        acao = "CONTATO" if estado.touching else ("HOVER" if estado.in_range else "FORA")
        linha = (
            f"{estado.seq:06d}  {acao:<7}  x={estado.x:.4f} y={estado.y:.4f} "
            f"pressão={estado.pressure:.3f} distância={estado.distance_raw} "
            f"inclinação=({estado.tilt_x:+d}, {estado.tilt_y:+d}) "
            f"botão={estado.button} botão2={estado.button2} borracha={estado.eraser}"
        )
        self.latest_state.setText(linha)
        self.event_log.appendPlainText(linha)
        self.pen_state_changed.emit(estado)

    def _erro_stream(self, mensagem):
        self.reader_error = True
        self._mostrar_status(mensagem, False)
        self.event_log.appendPlainText(f"ERRO: {mensagem}")

    def _stream_finalizado(self):
        if self.pen_reader is None:
            return
        self.pen_reader = None
        self.stream_ended.emit()
        self._definir_streaming(False)
        self.stop_button.setEnabled(False)
        if not self.reader_error:
            self.latest_state.setText("S Pen parada.")
            self.status.setText("Leitura da S Pen parada.")

    def _parar_leitura(self):
        if self.pen_reader:
            self.stop_button.setEnabled(False)
            self.status.setText("Encerrando a leitura da S Pen…")
            self.pen_reader.request_stop()

    def _selecionar_dispositivo(self, item):
        self.selecionado_serial = None
        self.selecionado_estado = None
        if item is None:
            self.diagnose_button.setEnabled(False)
            self.start_button.setEnabled(False)
            self.inject_checkbox.setEnabled(False)
            return

        self.selecionado_serial = item.data(Qt.ItemDataRole.UserRole)
        self.selecionado_estado = item.data(Qt.ItemDataRole.UserRole + 1)
        autorizado = self.selecionado_estado == "device"
        self.diagnose_button.setEnabled(autorizado)
        self.start_button.setEnabled(autorizado)
        self.inject_checkbox.setEnabled(autorizado)
        if ":" in self.selecionado_serial:
            self.endpoint.setText(self.selecionado_serial)

    def closeEvent(self, event):
        if not self.encerrar_leitura():
            event.ignore()
            return
        super().closeEvent(event)

    def encerrar_leitura(self, timeout=3000):
        if self.pen_reader:
            reader = self.pen_reader
            reader.request_stop()
            if not reader.wait(timeout):
                return False
            self.pen_reader = None
        return True

    def set_calibration(self, calibration):
        self.calibration = normalizar_calibracao(calibration)
        if self.pen_reader:
            self._mostrar_status(
                "Calibração atualizada. Pare e reinicie a leitura para aplicar.",
                True,
            )
