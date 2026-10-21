import shutil
import subprocess
from dataclasses import dataclass


ADB_NAO_ENCONTRADO = (
    "ADB não encontrado. Instale o Android SDK Platform-Tools "
    "e adicione a pasta ao PATH do Windows."
)


@dataclass(frozen=True)
class DispositivoADB:
    serial: str
    estado: str


class ADBTimeoutError(RuntimeError):
    pass


def verificar_adb():
    return shutil.which("adb") is not None


def criar_comando_adb(argumentos, serial=None):
    executavel = shutil.which("adb")
    if executavel is None:
        raise FileNotFoundError(ADB_NAO_ENCONTRADO)

    comando = [executavel]
    if serial:
        comando.extend(["-s", serial])
    comando.extend(argumentos)
    return comando


def executar_comando_adb(argumentos, timeout=10, serial=None):
    comando = criar_comando_adb(argumentos, serial)

    try:
        resultado = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    except subprocess.TimeoutExpired as erro:
        raise ADBTimeoutError(
            f"O ADB não respondeu dentro do limite de {timeout} segundos."
        ) from erro
    except OSError as erro:
        raise RuntimeError(f"Não foi possível iniciar o ADB: {erro}") from erro

    saida = resultado.stdout.strip()
    if resultado.returncode != 0:
        detalhe = resultado.stderr.strip() or saida
        raise RuntimeError(detalhe or "O comando ADB falhou sem informar o motivo.")
    return saida


def obter_dispositivos():
    try:
        saida = executar_comando_adb(["devices"])
        dispositivos = []

        for linha in saida.splitlines():
            partes = linha.strip().split()
            if len(partes) >= 2 and partes[0] not in {"List", "*"}:
                dispositivos.append(DispositivoADB(partes[0], partes[1]))

        return True, dispositivos
    except (FileNotFoundError, RuntimeError) as erro:
        return False, str(erro)


def listar_dispositivos():
    sucesso, resultado = obter_dispositivos()
    if not sucesso:
        return False, resultado

    if resultado:
        return True, "\n".join(
            f"{dispositivo.serial} — {dispositivo.estado}"
            for dispositivo in resultado
        )

    return False, (
        "Nenhum dispositivo conectado. Ative a Depuração sem fio "
        "ou conecte um dispositivo por USB."
    )


def _validar_endpoint(endpoint):
    partes = endpoint.strip().rsplit(":", 1)
    if len(partes) != 2 or not partes[0] or not partes[1].isdigit():
        return False, "Informe o endereço no formato IP:porta, por exemplo 192.168.1.20:5555."

    porta = int(partes[1])
    if not 1 <= porta <= 65535:
        return False, "A porta deve estar entre 1 e 65535."

    return True, f"{partes[0]}:{porta}"


def emparelhar_dispositivo(endpoint, codigo):
    valido, resultado = _validar_endpoint(endpoint)
    if not valido:
        return False, resultado
    if not codigo.strip():
        return False, "Informe o código de pareamento exibido no tablet."

    try:
        saida = executar_comando_adb(["pair", resultado, codigo.strip()], timeout=30)
    except (FileNotFoundError, RuntimeError) as erro:
        return False, str(erro)

    saida_minuscula = saida.lower()
    if "successfully paired" in saida_minuscula:
        return True, saida
    return False, saida or "O ADB não confirmou o pareamento. Confira o código e a porta."


def conectar_dispositivo(endpoint):
    valido, resultado = _validar_endpoint(endpoint)
    if not valido:
        return False, resultado

    try:
        saida = executar_comando_adb(["connect", resultado], timeout=15)
    except (FileNotFoundError, RuntimeError) as erro:
        return False, str(erro)

    saida_minuscula = saida.lower()
    if "connected to" in saida_minuscula or "already connected to" in saida_minuscula:
        return True, saida
    return False, saida or "O ADB não confirmou a conexão. Confira o endereço e a porta."


def desconectar_dispositivo(endpoint):
    valido, resultado = _validar_endpoint(endpoint)
    if not valido:
        return False, resultado

    try:
        saida = executar_comando_adb(["disconnect", resultado], timeout=15)
    except (FileNotFoundError, RuntimeError) as erro:
        return False, str(erro)

    if "disconnect" in saida.lower():
        return True, saida
    return False, saida or "O ADB não confirmou a desconexão."