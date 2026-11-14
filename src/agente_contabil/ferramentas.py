"""Ferramentas (tools) expostas ao modelo. Todas determinísticas, lendo dados/."""
import json

from .busca import buscar_produto
from .calculo import consultar

FERRAMENTAS = [
    {
        "name": "consultar_ncm",
        "description": "Retorna regime, alíquotas de CBS/IBS, fundamento legal e avisos para um NCM em um ano.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "ncm": {"type": "string", "description": "NCM com 8 dígitos (pontos opcionais)."},
                "ano": {"type": "integer", "description": "Ano de referência, ex.: 2027."},
            },
            "required": ["ncm", "ano"],
            "additionalProperties": False,
        },
    },
    {
        "name": "buscar_produto",
        "description": "Busca NCMs candidatos a partir do nome ou categoria de um produto.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"texto": {"type": "string", "description": "Nome ou categoria do produto."}},
            "required": ["texto"],
            "additionalProperties": False,
        },
    },
]


def executar(nome: str, entrada: dict) -> tuple[str, bool]:
    """Executa a ferramenta. Retorna (conteúdo JSON, is_error)."""
    try:
        if nome == "consultar_ncm":
            r = consultar(entrada["ncm"], int(entrada["ano"]))
            return json.dumps(r, ensure_ascii=False), "erro" in r
        if nome == "buscar_produto":
            r = buscar_produto(entrada["texto"])
            return json.dumps(r or {"aviso": "Nenhum produto encontrado na base."}, ensure_ascii=False), False
        return f"Ferramenta desconhecida: {nome}", True
    except (KeyError, ValueError, TypeError) as e:
        return f"Entrada inválida para {nome}: {e}", True
