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
from itertools import combinations
from functools import lru_cache
from pathlib import Path

from . import config
from .normalizacao import lista_tokens, normalizar_texto, radical

BONUS_INICIO = 1.5
DESCONTO_SINONIMO = 0.75  # palavra que existe na base: casar pela palavra vale mais que pelo sinônimo
LIMITE_ALTA, LIMITE_MEDIA = 0.999, 0.6


_EXIBIR: dict[str, str] = {}  # radical -> palavra como está no arquivo (para mostrar 'gallus', não 'gallu')


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
            for texto in palavras:
                for p in normalizar_texto(texto).split():
                    _EXIBIR.setdefault(radical(p), p)
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


class IndiceBusca:
    """Índice de documentos (descrição, palavras extras). Construa uma vez e consulte várias."""

    def __init__(self, docs: list[tuple[str, str]], genericas: frozenset[str] = frozenset(),
                 modo_posicao: str = "inicio"):
        """modo_posicao: 'inicio' = bônus para palavra nas 3 primeiras da descrição e confiança máxima
        'média' se só aparece depois (texto corrido); 'principal' = bônus para qualquer palavra da descrição
        principal (textos hierárquicos, como a NCM: o 'principal' reúne o nível mais específico e o início de
        cada nível). Nos dois modos, palavra que só aparece fora do 'principal' é citação solta."""
        self.genericas = genericas
        self.modo_posicao = modo_posicao
        self.principais = [[t for t in lista_tokens(d) if t not in genericas] for d, _ in docs]
        self.todos = [set(p) | set(lista_tokens(e)) for p, (_, e) in zip(self.principais, docs)]
        self.n = len(docs)
        self.invertido: dict[str, list[int]] = {}
        for i, conjunto in enumerate(self.todos):
            for t in conjunto:
                self.invertido.setdefault(t, []).append(i)

    def _idf(self, t: str) -> float:
        return math.log((self.n + 1) / (len(self.invertido.get(t, ())) + 1)) + 1

    def buscar(self, consulta: str, apenas: list[int] | None = None, ignorar_desconhecidas: bool = False):
        """(resultados, palavras_sem_correspondencia). Com `apenas`, avalia só esses documentos e não
        descarta os parciais (usado para conferir um item específico). Com `ignorar_desconhecidas`, palavra
        que nenhum item conhece (marca, modelo) é informada mas NÃO derruba a cobertura (conferência de ERP).

        resultados: [{indice, pontos, cobertura, confianca, so_citacao, sinonimos}] do melhor ao pior."""
        pergunta = [t for t in lista_tokens(consulta) if t not in self.genericas]
        if not pergunta:
            return [], []
        grupo = sinonimos()
        alternativas = {t: {t} | set(grupo.get(t, ())) for t in pergunta}
        conhecidos = [t for t in pergunta if alternativas[t] & self.invertido.keys()]
        desconhecidos = [t for t in pergunta if t not in conhecidos]
        vocab = self.invertido.keys()
        # peso base: o da própria palavra se existe nos documentos; senão o do sinônimo mais raro
        peso = {t: self._idf(t) if t in vocab else max(self._idf(a) for a in alternativas[t] & vocab)
                for t in conhecidos}
        peso_desconhecido = self._idf("")  # raridade máxima: palavra que nenhum item conhece é bem distintiva
        total = sum(peso.values()) + (0 if ignorar_desconhecidas else peso_desconhecido * len(desconhecidos))
        if total == 0:  # só palavras desconhecidas: nada a comparar
            return [], [t for t in pergunta]
        original = {}
        for p in normalizar_texto(consulta).split():
            original.setdefault(radical(p), p)

        candidatos = set(apenas) if apenas is not None else {
            i for t in conhecidos for a in alternativas[t] for i in self.invertido.get(a, ())}
        resultados = []
        for i in sorted(candidatos):
            conjunto = self.todos[i]
            achados = [t for t in conhecidos if alternativas[t] & conjunto]
            if not achados:
                if apenas is not None:
                    resultados.append({"indice": i, "pontos": 0.0, "cobertura": 0.0, "so_citacao": True,
                                       "sinonimos": [], "cabeca": False})
                continue
            inicio = set(self.principais[i][:3]) if self.modo_posicao == "inicio" else set(self.principais[i])
            # casou pela palavra: peso cheio; só por sinônimo: o peso do sinônimo (limitado ao da palavra)
            w = {t: peso[t] if t in conjunto else
                 min(peso[t], max(self._idf(x) for x in alternativas[t] & conjunto)) * (DESCONTO_SINONIMO if t in vocab else 1.0)
                 for t in achados}
            pontos = sum(w[t] * (BONUS_INICIO if alternativas[t] & inicio else 1.0) for t in achados)
            cobertura = sum(w.values()) / total
            resultados.append({
                "indice": i, "pontos": pontos, "cobertura": cobertura,
                # o substantivo principal (1ª palavra com conteúdo da pergunta) casou? em português ele vem primeiro
                "cabeca": pergunta[0] in achados,
                # palavra só citada no meio/fim da descrição ("...para conservação de carne") não identifica
                "so_citacao": not any(alternativas[t] & inicio for t in achados),
                # transparência: palavra da pergunta que casou só por sinônimo ("frango→galinha")
                "sinonimos": [f"{original.get(t, t)}→{_EXIBIR.get(x, x)}"
                              for t in achados if t not in conjunto
                              for x in [max(alternativas[t] & conjunto, key=self._idf)]]})

        if apenas is None and any(r["cobertura"] >= LIMITE_ALTA for r in resultados):
            resultados = [r for r in resultados if r["cobertura"] >= LIMITE_ALTA]  # alguém cobre tudo
        for r in resultados:
            nivel = ("alta" if r["cobertura"] >= LIMITE_ALTA
                     else "media" if r["cobertura"] >= LIMITE_MEDIA else "baixa")
            r["confianca"] = "media" if nivel == "alta" and r["so_citacao"] else nivel
        resultados.sort(key=lambda r: (-round(r["cobertura"], 3), -r["pontos"]))
        return resultados, [original.get(t, t) for t in desconhecidos]


def _buscar_relaxado(self, consulta: str, max_descartes: int = 2, ignorar_desconhecidas: bool = False):
    """(resultados, sem_correspondencia, palavras_ignoradas).

    Se nada cobre bem a pergunta ('leite longa vida': a NCM não tem 'longa vida'), tenta descartar até
    `max_descartes` palavras, preferindo as do FIM (em português o modificador vem depois do substantivo).
    Só aceita quem passa a cobrir tudo e NUNCA com confiança 'alta': diz quais palavras ignorou."""
    resultados, sem = self.buscar(consulta, ignorar_desconhecidas=ignorar_desconhecidas)
    if any(r["confianca"] in ("alta", "media") for r in resultados):
        return resultados, sem, []
    palavras: list[str] = []
    for p in normalizar_texto(consulta).split():
        r = lista_tokens(p)
        if r and r[0] not in self.genericas and all(radical(q) != r[0] for q in palavras):
            palavras.append(p)
    for k in range(1, min(max_descartes, len(palavras) - 1) + 1):
        for descartar in sorted(combinations(range(len(palavras)), k), key=lambda c: -sum(c)):
            mantidas = [p for i, p in enumerate(palavras) if i not in descartar]
            achados, sem2 = self.buscar(" ".join(mantidas), ignorar_desconhecidas=ignorar_desconhecidas)
            if achados and achados[0]["confianca"] == "alta":
                for a in achados:
                    if a["confianca"] == "alta":
                        a["confianca"] = "media"
                return achados, sem2, [palavras[i] for i in descartar]
    return resultados, sem, []


IndiceBusca.buscar_relaxado = _buscar_relaxado


def ranquear(consulta: str, docs: list[tuple[str, str]], genericas: frozenset[str] = frozenset()):
    """Atalho para bases pequenas: monta o índice e consulta. Veja IndiceBusca.buscar."""
    return IndiceBusca(docs, genericas).buscar(consulta)
