"""Busca de produto por texto livre -> NCMs candidatos (sem IA, custo zero)."""
from .normalizacao import tokens
from .regras import carregar


def buscar_produto(texto: str, limite: int = 5) -> list[dict]:
    consulta = tokens(texto)
    if not consulta:
        return []
    resultado = []
    for r in carregar():
        alvo = tokens(r.descricao) | tokens(r.palavras_chave.replace(",", " "))
        pontos = len(consulta & alvo)
        if pontos:
            resultado.append((pontos, r))
    resultado.sort(key=lambda x: (-x[0], -len(x[1].ncm_prefixo)))
    return [{"ncm_prefixo": r.ncm_prefixo, "descricao": r.descricao, "regime": r.regime,
             "validado": r.validado, "relevancia": p} for p, r in resultado[:limite]]
