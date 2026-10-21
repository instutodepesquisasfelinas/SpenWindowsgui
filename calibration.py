import json
from app_paths import get_profiles_path


ARQUIVO_PERFIS = get_profiles_path()
CALIBRACAO_PADRAO = {
    "scale": 1.0,
    "offset_x": 0.0,
    "offset_y": 0.0,
    "orientation": "portrait",
    "x0": 0.0,
    "x1": 1.0,
    "y0": 0.0,
    "y1": 1.0,
    "swap_axes": False,
    "invert_x": False,
    "invert_y": False,
}


def normalizar_calibracao(calibracao):
    resultado = dict(CALIBRACAO_PADRAO)
    resultado.update(calibracao or {})
    resultado["scale"] = min(4.0, max(0.25, float(resultado["scale"])))
    resultado["offset_x"] = min(1.0, max(0.0, float(resultado["offset_x"])))
    resultado["offset_y"] = min(1.0, max(0.0, float(resultado["offset_y"])))
    if resultado["orientation"] not in {"portrait", "landscape_cw", "landscape_ccw"}:
        resultado["orientation"] = "portrait"
    for chave in ("x0", "x1", "y0", "y1"):
        resultado[chave] = min(1.0, max(0.0, float(resultado[chave])))
    if resultado["x1"] <= resultado["x0"]:
        resultado["x0"], resultado["x1"] = 0.0, 1.0
    if resultado["y1"] <= resultado["y0"]:
        resultado["y0"], resultado["y1"] = 0.0, 1.0
    for chave in ("swap_axes", "invert_x", "invert_y"):
        resultado[chave] = bool(resultado[chave])
    return resultado


def orientar_coordenadas(x, y, calibracao):
    if calibracao["orientation"] == "landscape_cw":
        x, y = y, 1.0 - x
    elif calibracao["orientation"] == "landscape_ccw":
        x, y = 1.0 - y, x
    if calibracao["swap_axes"]:
        x, y = y, x
    return x, y


def carregar_calibracao():
    if not ARQUIVO_PERFIS.exists():
        return dict(CALIBRACAO_PADRAO)
    try:
        with ARQUIVO_PERFIS.open("r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (OSError, json.JSONDecodeError):
        return dict(CALIBRACAO_PADRAO)
    return normalizar_calibracao(dados.get("calibracao", {}))


def salvar_calibracao(calibracao):
    if ARQUIVO_PERFIS.exists():
        with ARQUIVO_PERFIS.open("r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    else:
        dados = {"Perfil atual": "Desenho", "perfis": {}}

    dados["calibracao"] = normalizar_calibracao(calibracao)
    with ARQUIVO_PERFIS.open("w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=4)
    return dados["calibracao"]