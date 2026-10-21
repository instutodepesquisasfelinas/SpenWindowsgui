import ctypes
import sys
from ctypes import wintypes

from calibration import normalizar_calibracao, orientar_coordenadas


PT_PEN = 3
POINTER_FEEDBACK_INDIRECT = 2

POINTER_FLAG_NEW = 0x00000001
POINTER_FLAG_INRANGE = 0x00000002
POINTER_FLAG_INCONTACT = 0x00000004
POINTER_FLAG_FIRSTBUTTON = 0x00000010
POINTER_FLAG_SECONDBUTTON = 0x00000020
POINTER_FLAG_DOWN = 0x00010000
POINTER_FLAG_UPDATE = 0x00020000
POINTER_FLAG_UP = 0x00040000

PEN_FLAG_BARREL = 0x00000001
PEN_FLAG_ERASER = 0x00000004
PEN_MASK_PRESSURE = 0x00000001
PEN_MASK_TILT_X = 0x00000004
PEN_MASK_TILT_Y = 0x00000008

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class POINTER_INFO(ctypes.Structure):
    _fields_ = [
        ("pointerType", wintypes.UINT),
        ("pointerId", wintypes.UINT),
        ("frameId", wintypes.UINT),
        ("pointerFlags", wintypes.UINT),
        ("sourceDevice", wintypes.HANDLE),
        ("hwndTarget", wintypes.HWND),
        ("ptPixelLocation", POINT),
        ("ptHimetricLocation", POINT),
        ("ptPixelLocationRaw", POINT),
        ("ptHimetricLocationRaw", POINT),
        ("dwTime", wintypes.DWORD),
        ("historyCount", wintypes.UINT),
        ("InputData", wintypes.LONG),
        ("dwKeyStates", wintypes.DWORD),
        ("PerformanceCount", ctypes.c_uint64),
        ("ButtonChangeType", ctypes.c_int),
    ]


class POINTER_PEN_INFO(ctypes.Structure):
    _fields_ = [
        ("pointerInfo", POINTER_INFO),
        ("penFlags", wintypes.UINT),
        ("penMask", wintypes.UINT),
        ("pressure", wintypes.UINT),
        ("rotation", wintypes.UINT),
        ("tiltX", wintypes.LONG),
        ("tiltY", wintypes.LONG),
    ]


class _POINTER_INFO_UNION(ctypes.Union):
    _fields_ = [("pointerInfo", POINTER_INFO), ("penInfo", POINTER_PEN_INFO)]


class POINTER_TYPE_INFO(ctypes.Structure):
    _fields_ = [("type", wintypes.UINT), ("u", _POINTER_INFO_UNION)]


class WindowsPenError(RuntimeError):
    pass


class WindowsPenInjector:
    def __init__(self, user32=None, desktop_bounds=None, calibration=None):
        if user32 is None:
            if sys.platform != "win32":
                raise WindowsPenError(
                    "A injeção de caneta só está disponível no Windows 10 versão 1809 ou posterior."
                )
            user32 = ctypes.WinDLL("user32", use_last_error=True)

        self._user32 = user32
        self._configurar_assinaturas()
        self._device = self._user32.CreateSyntheticPointerDevice(
            PT_PEN, 1, POINTER_FEEDBACK_INDIRECT
        )
        if not self._device:
            raise WindowsPenError(self._erro_windows("Não foi possível criar o dispositivo de caneta"))

        self._bounds = desktop_bounds or self._obter_limites_da_area_de_trabalho()
        self.calibration = normalizar_calibracao(calibration)
        self._x = 0.0
        self._y = 0.0
        self._in_range = False
        self._is_down = False
        self._frame = 0
        self._closed = False

    def _configurar_assinaturas(self):
        assinaturas = (
            ("CreateSyntheticPointerDevice", [wintypes.UINT, wintypes.ULONG, wintypes.UINT], wintypes.HANDLE),
            (
                "InjectSyntheticPointerInput",
                [wintypes.HANDLE, ctypes.POINTER(POINTER_TYPE_INFO), wintypes.UINT],
                wintypes.BOOL,
            ),
            ("DestroySyntheticPointerDevice", [wintypes.HANDLE], None),
            ("GetSystemMetrics", [ctypes.c_int], ctypes.c_int),
            ("SetCursorPos", [ctypes.c_int, ctypes.c_int], wintypes.BOOL),
        )
        for nome, argumentos, retorno in assinaturas:
            try:
                funcao = getattr(self._user32, nome)
            except AttributeError as erro:
                raise WindowsPenError(
                    "A API de ponteiro sintético exige Windows 10 versão 1809 ou posterior."
                ) from erro
            try:
                funcao.argtypes = argumentos
                funcao.restype = retorno
            except AttributeError:
                pass

    def _obter_limites_da_area_de_trabalho(self):
        obter = self._user32.GetSystemMetrics
        limites = (
            obter(SM_XVIRTUALSCREEN),
            obter(SM_YVIRTUALSCREEN),
            obter(SM_CXVIRTUALSCREEN),
            obter(SM_CYVIRTUALSCREEN),
        )
        if limites[2] <= 0 or limites[3] <= 0:
            self._user32.DestroySyntheticPointerDevice(self._device)
            self._device = None
            raise WindowsPenError("O Windows informou uma área de trabalho inválida.")
        return limites

    @staticmethod
    def _erro_windows(contexto):
        codigo = ctypes.get_last_error()
        if codigo:
            return f"{contexto}. Erro do Windows {codigo}: {ctypes.FormatError(codigo).strip()}"
        return f"{contexto}. O Windows não informou um código de erro."

    def inject(self, state):
        if self._closed or not self._device:
            raise WindowsPenError("O dispositivo de caneta do Windows já foi encerrado.")

        x, y = orientar_coordenadas(state.x, state.y, self.calibration)
        x = (x - self.calibration["x0"]) / (
            self.calibration["x1"] - self.calibration["x0"]
        )
        y = (y - self.calibration["y0"]) / (
            self.calibration["y1"] - self.calibration["y0"]
        )
        x = (x - self.calibration["offset_x"]) * self.calibration["scale"]
        y = (y - self.calibration["offset_y"]) * self.calibration["scale"]
        if self.calibration["invert_x"]:
            x = 1.0 - x
        if self.calibration["invert_y"]:
            y = 1.0 - y
        self._x = max(0.0, min(1.0, x))
        self._y = max(0.0, min(1.0, y))
        x0, y0, largura, altura = self._bounds
        x = round(x0 + self._x * max(0, largura - 1))
        y = round(y0 + self._y * max(0, altura - 1))

        if not state.in_range:
            if not self._in_range:
                return
            flags = POINTER_FLAG_UPDATE
            if self._is_down:
                flags |= POINTER_FLAG_UP
            self._send(x, y, state, flags)
            self._in_range = False
            self._is_down = False
            return

        flags = POINTER_FLAG_INRANGE | POINTER_FLAG_UPDATE
        if not self._in_range:
            flags |= POINTER_FLAG_NEW

        down = state.touching and state.pressure > 0
        if down:
            flags |= POINTER_FLAG_INCONTACT | POINTER_FLAG_FIRSTBUTTON
            if not self._is_down:
                flags |= POINTER_FLAG_DOWN
        elif self._is_down:
            flags |= POINTER_FLAG_UP

        if state.button2:
            flags |= POINTER_FLAG_SECONDBUTTON

        self._send(x, y, state, flags)
        if not self._user32.SetCursorPos(x, y):
            raise WindowsPenError(self._erro_windows("Não foi possível mover o cursor do mouse"))
        self._in_range = True
        self._is_down = down

    def _send(self, x, y, state, flags):
        pen = POINTER_PEN_INFO()
        pen.pointerInfo.pointerType = PT_PEN
        pen.pointerInfo.pointerId = 0
        pen.pointerInfo.frameId = self._frame
        pen.pointerInfo.pointerFlags = flags
        pen.pointerInfo.ptPixelLocation = POINT(x, y)
        pen.pointerInfo.ptPixelLocationRaw = POINT(x, y)
        pen.pointerInfo.historyCount = 1
        pen.penMask = PEN_MASK_PRESSURE | PEN_MASK_TILT_X | PEN_MASK_TILT_Y
        pen.pressure = round(max(0.0, min(1.0, state.pressure)) * 1024)
        pen.tiltX = max(-90, min(90, state.tilt_x))
        pen.tiltY = max(-90, min(90, state.tilt_y))
        if state.button:
            pen.penFlags |= PEN_FLAG_BARREL
        if state.eraser:
            pen.penFlags |= PEN_FLAG_ERASER

        pointer = POINTER_TYPE_INFO()
        pointer.type = PT_PEN
        pointer.u.penInfo = pen
        sucesso = self._user32.InjectSyntheticPointerInput(
            self._device, ctypes.byref(pointer), 1
        )
        if not sucesso:
            raise WindowsPenError(
                self._erro_windows("O Windows recusou a injeção do evento de caneta")
            )
        self._frame += 1

    def close(self):
        if self._closed:
            return
        self._closed = True
        if not self._device:
            return
        try:
            if self._in_range:
                state = type(
                    "ReleaseState",
                    (),
                    {
                        "pressure": 0.0,
                        "tilt_x": 0,
                        "tilt_y": 0,
                        "button": False,
                        "button2": False,
                        "eraser": False,
                    },
                )()
                flags = POINTER_FLAG_UPDATE
                if self._is_down:
                    flags |= POINTER_FLAG_UP
                x0, y0, largura, altura = self._bounds
                x = round(x0 + self._x * max(0, largura - 1))
                y = round(y0 + self._y * max(0, altura - 1))
                self._send(x, y, state, flags)
        finally:
            self._user32.DestroySyntheticPointerDevice(self._device)
            self._device = None