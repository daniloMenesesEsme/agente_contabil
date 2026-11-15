"""Busca por texto sem IA, comum a produtos e serviços.

Como decide (nada de 'qualquer palavra em comum'):
- radicais: 'carne' e 'carnes' são a mesma palavra;
- peso por raridade: 'soja' (rara) vale mais que 'oleo' (comum);
- cobertura: fração do peso da pergunta que o item cobre. Se algum item cobre TUDO, os que cobrem
  só parte saem. Palavra da pergunta que nenhum item conhece ('frango') derruba a confiança;
- posição: palavra nas 3 primeiras da descrição (o substantivo principal) vale mais que citação solta;
- sinônimos: dados/sinonimos.csv (auxílio de busca revisável, não é fato tributário).
"""
import csv
import math
from functools import lru_cache
from pathlib import Path

from . import config
from .normalizacao import lista_tokens, normalizar_texto, radical

BONUS_INICIO = 1.5
LIMITE_ALTA, LIMITE_MEDIA = 0.999, 0.6


@lru_cache(maxsize=1)
def sinonimos() -> dict[str, frozenset[str]]:
    """radical -> grupo de radicais equivalentes (relação simétrica). Arquivo ausente = sem sinônimos."""
    mapa: dict[str, frozenset[str]] = {}
    arq = Path(config.ARQ_SINONIMOS)
    if not arq.exists():
        return mapa
    with open(arq, encoding="utf-8", newline="") as f:
        for linha in csv.DictReader(f, delimiter=";"):
            palavras = [linha["termo"], *linha["equivalentes"].split(",")]
            grupo = frozenset(radical(p) for texto in palavras for p in normalizar_texto(texto).split())
            for r in grupo:
                mapa[r] = mapa.get(r, frozenset()) | grupo
    return mapa


@lru_cache(maxsize=1)
def _avisos_por_termo() -> dict[str, str]:
    arq = Path(config.ARQ_AVISOS_BUSCA)
    if not arq.exists():
        return {}
    with open(arq, encoding="utf-8", newline="") as f:
        return {radical(normalizar_texto(l["termo"])): l["aviso"] for l in csv.DictReader(f, delimiter=";")}


def avisos_da_consulta(consulta: str) -> list[str]:
    """Avisos de dados/avisos_busca.csv para temas com lacuna conhecida citados na pergunta
    (ex.: medicamentos). Sem repetir o mesmo aviso para termos sinônimos."""
    avisos = _avisos_por_termo()
    saida: list[str] = []
    for t in lista_tokens(consulta):
        if t in avisos and avisos[t] not in saida:
            saida.append(avisos[t])
    return saida


def ranquear(consulta: str, docs: list[tuple[str, str]], genericas: frozenset[str] = frozenset()):
    """docs = [(descrição, palavras extras)]. Devolve (resultados, palavras_sem_correspondencia).

    resultados: [{indice, pontos, cobertura, confianca}] do melhor para o pior."""
    pergunta = [t for t in lista_tokens(consulta) if t not in genericas]
    if not pergunta:
        return [], []
    principais = [[t for t in lista_tokens(d) if t not in genericas] for d, _ in docs]
    todos = [set(p) | set(lista_tokens(e)) for p, (_, e) in zip(principais, docs)]
    df: dict[str, int] = {}
    for conjunto in todos:
        for t in conjunto:
            df[t] = df.get(t, 0) + 1
    n = len(docs)

    def idf(t: str) -> float:
        return math.log((n + 1) / (df.get(t, 0) + 1)) + 1

    grupo = sinonimos()
    alternativas = {t: {t} | set(grupo.get(t, ())) for t in pergunta}
    conhecidos = [t for t in pergunta if alternativas[t] & df.keys()]
    desconhecidos = [t for t in pergunta if t not in conhecidos]
    peso = {t: max(idf(a) for a in alternativas[t] & df.keys()) for t in conhecidos}
    peso_desconhecido = idf("")  # raridade máxima: palavra que nenhum item conhece é bem distintiva
    total = sum(peso.values()) + peso_desconhecido * len(desconhecidos)

    resultados = []
    for i, conjunto in enumerate(todos):
        achados = [t for t in conhecidos if alternativas[t] & conjunto]
        if not achados:
            continue
        inicio = set(principais[i][:3])
        pontos = sum(peso[t] * (BONUS_INICIO if alternativas[t] & inicio else 1.0) for t in achados)
        cobertura = sum(peso[t] for t in achados) / total
        # palavra só citada no meio/fim da descrição ("...para conservação de carne") não identifica o item
        so_citacao = not any(alternativas[t] & inicio for t in achados)
        resultados.append({"indice": i, "pontos": pontos, "cobertura": cobertura, "so_citacao": so_citacao})

    if any(r["cobertura"] >= LIMITE_ALTA for r in resultados):  # alguém cobre tudo: parciais saem
        resultados = [r for r in resultados if r["cobertura"] >= LIMITE_ALTA]
    for r in resultados:
        nivel = ("alta" if r["cobertura"] >= LIMITE_ALTA
                 else "media" if r["cobertura"] >= LIMITE_MEDIA else "baixa")
        r["confianca"] = "media" if nivel == "alta" and r["so_citacao"] else nivel
    resultados.sort(key=lambda r: (-round(r["cobertura"], 3), -r["pontos"]))
    originais = [p for p in normalizar_texto(consulta).split() if radical(p) in desconhecidos]
    return resultados, originais
