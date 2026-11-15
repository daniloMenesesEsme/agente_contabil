"""Busca de produto por texto livre -> NCMs candidatos (sem IA, custo zero). Ver texto_busca.py."""
from .normalizacao import normalizar_texto
from .regras import carregar
from .texto_busca import IndiceBusca


def buscar_produto(texto: str, limite: int = 5) -> list[dict]:
    """Candidatos com `confianca` (alta/media/baixa) e `palavras_sem_correspondencia`.

    Itens com a mesma descrição e regime (ex.: 40 NCMs de 'Leite...') viram um só, com `outros_ncms`."""
    regras = carregar()
    indice = IndiceBusca([(r.descricao, r.palavras_chave.replace(",", " ")) for r in regras])
    ranking, sem, ignoradas = indice.buscar_relaxado(texto)
    grupos: dict[tuple, dict] = {}
    for item in ranking:
        r = regras[item["indice"]]
        chave = (normalizar_texto(r.descricao), r.regime, r.reducao_percentual)
        if chave in grupos:
            grupos[chave]["outros_ncms"].append(r.ncm_prefixo)
            grupos[chave]["quantidade_ncms"] += 1
            continue
        grupos[chave] = {"ncm_prefixo": r.ncm_prefixo, "descricao": r.descricao, "regime": r.regime,
                         "validado": r.validado, "relevancia": round(item["pontos"], 2),
                         "confianca": item["confianca"], "cobertura": round(item["cobertura"], 2),
                         "quantidade_ncms": 1, "outros_ncms": [], "palavras_sem_correspondencia": sem,
                         "sinonimos_usados": item["sinonimos"], "palavras_ignoradas": ignoradas}
    resultado = list(grupos.values())[:limite]
    for g in resultado:
        g["outros_ncms"] = g["outros_ncms"][:10]
    return resultado
