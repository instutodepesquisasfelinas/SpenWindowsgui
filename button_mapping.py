import json
from app_paths import get_profiles_path

ARQUIVO_PERFIS = get_profiles_path()

ACOES_DISPONIVEIS = [
    "Desativado",
    "Clique esquerdo",
    "Clique direito",
    "Voltar",
    "Avançar",
    "Espaço",
    "Ctrl+Z",
    "Ctrl+S"
]


def carregar_perfis():
    if not ARQUIVO_PERFIS.exists():
        return {"Perfil atual": "Desenho", "perfis": {}}

    with open(ARQUIVO_PERFIS, "r", encoding="utf-8") as arquivo:
        return json.load(arquivo)


def salvar_perfis(dados):
    with open(ARQUIVO_PERFIS, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=4)


def salvar_mapeamento(perfil, botao_lateral, botao_extra):
    dados = carregar_perfis()

    dados.setdefault("perfis", {})
    dados["perfis"][perfil] = {
        "botao_lateral": botao_lateral,
        "botao_extra": botao_extra
    }
    dados["Perfil atual"] = perfil

    salvar_perfis(dados)