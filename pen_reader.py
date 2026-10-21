import re
import subprocess
import threading
import time
from dataclasses import dataclass

from PySide6.QtCore import QThread, Signal

from adb_connection import (
    ADBTimeoutError,
    criar_comando_adb,
    executar_comando_adb,
)


_DEVICE_RE = re.compile(r"add device \d+: (/dev/input/event\d+)")
_AXIS_RE = re.compile(
    r"\s+([0-9a-f]{4})\s+:\s+value\s+-?\d+,\s+min\s+(-?\d+),\s+max\s+(-?\d+)",
    re.IGNORECASE,
)
_EVENT_RE = re.compile(
    r"^(?:\[\s*(?P<timestamp>[\d.]+)\]\s+)?"
    r"(?:\S+:\s+)?(?P<type>[0-9a-f]{4})\s+"
    r"(?P<code>[0-9a-f]{4})\s+(?P<value>[0-9a-f]{8})$",
    re.IGNORECASE,
)
_PEN_NAMES = ("wacom", "stylus", "pen", "spen", "e-pen")
EV_SYN = 0x00
EV_KEY = 0x01
EV_ABS = 0x03
SYN_REPORT = 0x00
ABS_X = 0x00
ABS_Y = 0x01
ABS_PRESSURE = 0x18
ABS_DISTANCE = 0x19
ABS_TILT_X = 0x1A
ABS_TILT_Y = 0x1B
BTN_TOOL_PEN = 0x140
BTN_TOOL_RUBBER = 0x141
BTN_TOUCH = 0x14A
BTN_STYLUS = 0x14B
BTN_STYLUS2 = 0x14C


@dataclass(frozen=True)
class PenDevice:
    path: str
    name: str
    axis_ranges: dict


@dataclass(frozen=True)
class PenState:
    x_raw: int
    y_raw: int
    pressure_raw: int
    distance_raw: int
    tilt_x: int
    tilt_y: int
    x: float
    y: float
    pressure: float
    in_range: bool
    touching: bool
    eraser: bool
    button: bool
    button2: bool
    timestamp: float
    seq: int


def _encontrar_eventos_caneta(saida):
    dispositivos = []
    atual = None

    def finalizar():
        eixos_obrigatorios = {ABS_X, ABS_Y, ABS_PRESSURE}
        if (
            atual
            and atual["pressao"]
            and atual["caneta"]
            and eixos_obrigatorios.issubset(atual["eixos"])
        ):
            dispositivos.append(
                PenDevice(atual["caminho"], atual["nome"], atual["eixos"].copy())
            )

    for linha in saida.splitlines():
        correspondencia = _DEVICE_RE.match(linha.strip())
        if correspondencia:
            finalizar()
            atual = {
                "caminho": correspondencia.group(1),
                "nome": "",
                "pressao": False,
                "caneta": False,
                "eixos": {},
            }
            continue

        if atual is None:
            continue

        minuscula = linha.lower()
        if "name:" in minuscula:
            atual["nome"] = linha.split(":", 1)[1].strip().strip('"')
            if any(nome in atual["nome"].lower() for nome in _PEN_NAMES):
                atual["caneta"] = True
        if "0018" in linha:
            atual["pressao"] = True
        if "0140" in linha:
            atual["caneta"] = True
        eixo = _AXIS_RE.search(linha)
        if eixo:
            atual["eixos"][int(eixo.group(1), 16)] = (
                int(eixo.group(2)),
                int(eixo.group(3)),
            )

    finalizar()
    return dispositivos


def detectar_evento_caneta(serial):
    try:
        informacoes = executar_comando_adb(
            ["shell", "getevent", "-i"], timeout=10, serial=serial
        )
    except (FileNotFoundError, RuntimeError) as erro:
        return False, f"Não foi possível consultar os dispositivos de entrada: {erro}"

    candidatos = _encontrar_eventos_caneta(informacoes)
    if not candidatos:
        return False, (
            "O ADB respondeu, mas não encontrou um evento de caneta com faixas válidas "
            "para ABS_X, ABS_Y e ABS_PRESSURE, além de BTN_TOOL_PEN. "
            "Confira `adb shell getevent -i`."
        )

    return True, next(
        (candidato for candidato in candidatos if any(
            dica in candidato.name.lower() for dica in _PEN_NAMES
        )),
        candidatos[0],
    )


def diagnosticar_leitura(serial, timeout=8):
    sucesso, dispositivo = detectar_evento_caneta(serial)
    if not sucesso:
        return False, dispositivo

    try:
        saida = executar_comando_adb(
            ["shell", "getevent", "-t", "-c", "1", dispositivo.path],
            timeout=timeout,
            serial=serial,
        )
    except ADBTimeoutError:
        return False, (
            f"Evento candidato: {dispositivo.path} ({dispositivo.name}). "
            f"Nenhum evento chegou em {timeout}s. "
            "Isso não confirma falta de permissão: mova ou encoste a S Pen durante o teste."
        )
    except (FileNotFoundError, RuntimeError) as erro:
        detalhe = str(erro)
        if any(
            trecho in detalhe.lower()
            for trecho in ("permission denied", "operation not permitted", "couldn't open")
        ):
            return False, (
                f"O evento {dispositivo.path} foi encontrado, mas o Android negou a leitura: {detalhe}"
            )
        return False, f"Falha ao ler {dispositivo.path}: {detalhe}"

    if not saida.strip():
        return False, f"O comando terminou sem retornar dados de {dispositivo.path}."
    return True, f"Leitura confirmada em {dispositivo.path} ({dispositivo.name}): {saida.strip()}"


def _parse_evento(linha):
    correspondencia = _EVENT_RE.match(linha.strip())
    if correspondencia is None:
        return None

    valor = int(correspondencia.group("value"), 16)
    if valor >= 0x80000000:
        valor -= 0x100000000
    timestamp = correspondencia.group("timestamp")
    return (
        float(timestamp) if timestamp else time.monotonic(),
        int(correspondencia.group("type"), 16),
        int(correspondencia.group("code"), 16),
        valor,
    )


class PenEventParser:
    def __init__(self, dispositivo):
        self.dispositivo = dispositivo
        self.raw = {
            "x": 0,
            "y": 0,
            "pressure": 0,
            "distance": 0,
            "tilt_x": 0,
            "tilt_y": 0,
        }
        self.keys = {
            "in_range": False,
            "touching": False,
            "eraser": False,
            "button": False,
            "button2": False,
        }
        self.seq = 0

    def feed(self, linha):
        evento = _parse_evento(linha)
        if evento is None:
            return None

        timestamp, tipo, codigo, valor = evento
        if tipo == EV_ABS:
            campo = {
                ABS_X: "x",
                ABS_Y: "y",
                ABS_PRESSURE: "pressure",
                ABS_DISTANCE: "distance",
                ABS_TILT_X: "tilt_x",
                ABS_TILT_Y: "tilt_y",
            }.get(codigo)
            if campo:
                self.raw[campo] = valor
        elif tipo == EV_KEY:
            campo = {
                BTN_TOOL_PEN: "in_range",
                BTN_TOUCH: "touching",
                BTN_TOOL_RUBBER: "eraser",
                BTN_STYLUS: "button",
                BTN_STYLUS2: "button2",
            }.get(codigo)
            if campo:
                self.keys[campo] = bool(valor)
        elif tipo == EV_SYN and codigo == SYN_REPORT:
            state = PenState(
                x_raw=self.raw["x"],
                y_raw=self.raw["y"],
                pressure_raw=self.raw["pressure"],
                distance_raw=self.raw["distance"],
                tilt_x=self.raw["tilt_x"],
                tilt_y=self.raw["tilt_y"],
                x=self._normalizar(ABS_X, self.raw["x"]),
                y=self._normalizar(ABS_Y, self.raw["y"]),
                pressure=self._normalizar(ABS_PRESSURE, self.raw["pressure"]),
                in_range=self.keys["in_range"] or self.keys["touching"] or self.keys["eraser"],
                touching=self.keys["touching"],
                eraser=self.keys["eraser"],
                button=self.keys["button"],
                button2=self.keys["button2"],
                timestamp=timestamp,
                seq=self.seq,
            )
            self.seq += 1
            return state
        return None

    def _normalizar(self, eixo, valor):
        if eixo not in self.dispositivo.axis_ranges:
            raise ValueError(f"A calibração do eixo ABS {eixo:04x} não foi encontrada.")
        minimo, maximo = self.dispositivo.axis_ranges[eixo]
        if maximo <= minimo:
            return 0.0
        return max(0.0, min(1.0, (valor - minimo) / (maximo - minimo)))


class PenReader(QThread):
    state_received = Signal(object)
    stream_ready = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, serial, dispositivo, inject_windows=False, calibration=None):
        super().__init__()
        self.serial = serial
        self.dispositivo = dispositivo
        self.inject_windows = inject_windows
        self.calibration = calibration
        self._process = None
        self._process_lock = threading.Lock()

    def request_stop(self):
        self.requestInterruption()
        with self._process_lock:
            if self._process and self._process.poll() is None:
                self._process.terminate()

    def run(self):
        process = None
        injector = None
        try:
            if self.inject_windows:
                from windows_pen import WindowsPenInjector

                injector = WindowsPenInjector(calibration=self.calibration)

            command = criar_comando_adb(
                ["shell", "getevent", "-t", self.dispositivo.path],
                serial=self.serial,
            )
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            with self._process_lock:
                self._process = process

            self.stream_ready.emit(
                f"Lendo {self.dispositivo.path} ({self.dispositivo.name})"
                + (" e enviando a caneta para o Windows." if injector else ".")
            )
            parser = PenEventParser(self.dispositivo)
            ultima_atualizacao = 0.0
            mensagens_erro = []

            for linha in process.stdout:
                if self.isInterruptionRequested():
                    break
                estado = parser.feed(linha)
                if estado is None:
                    if any(
                        termo in linha.lower()
                        for termo in (
                            "permission denied",
                            "operation not permitted",
                            "couldn't open",
                            "device not found",
                            "no devices/emulators found",
                        )
                    ):
                        mensagens_erro.append(linha.strip())
                    continue

                if injector:
                    injector.inject(estado)
                agora = time.monotonic()
                if agora - ultima_atualizacao >= 0.033:
                    self.state_received.emit(estado)
                    ultima_atualizacao = agora

            if not self.isInterruptionRequested():
                codigo_saida = process.wait()
                detalhe = "\n".join(mensagens_erro)
                if detalhe:
                    raise RuntimeError(detalhe)
                if codigo_saida:
                    raise RuntimeError(
                        f"O processo ADB de leitura terminou com código {codigo_saida}."
                    )
        except Exception as erro:
            if not self.isInterruptionRequested():
                self.error_occurred.emit(str(erro))
        finally:
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            with self._process_lock:
                self._process = None
            if injector:
                try:
                    injector.close()
                except Exception as erro:
                    if not self.isInterruptionRequested():
                        self.error_occurred.emit(
                            f"Falha ao encerrar o dispositivo de caneta do Windows: {erro}"
                        )


class LegacyPenReader:
    def __init__(self):
        self.conectado = False

    def iniciar(self):
        raise NotImplementedError(
            "A leitura contínua dos eventos da S Pen ainda não foi implementada."
        )

    def parar(self):
        self.conectado = False