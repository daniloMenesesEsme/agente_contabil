"""Serviços (sem NCM): regras dos anexos de serviços da LC 214, buscadas por código NBS ou por texto.

Só os itens listados nos anexos (hoje: educação e saúde, redução de 60%) têm regra cadastrada.
Serviço fora da lista NÃO é declarado 'sem imposto': recebe a presunção de alíquota padrão, com aviso.
"""
import csv
import re
from dataclasses import dataclass, asdict
from functools import lru_cache
from pathlib import Path

from . import config
from .calculo import aliquotas, parametros
from .texto_busca import ranquear

GENERICAS = frozenset({"servico", "prestacao"})  # (radicais) estão em quase toda descrição: não identificam


@dataclass(frozen=True)
class RegraServico:
    item: str
    descricao: str
    palavras_chave: str
    nbs: tuple[str, ...]
    regime: str
    reducao_percentual: float
    fundamento: str
    validado: bool
    observacao: str
    texto_lei: str

    def to_dict(self) -> dict:
        return asdict(self)


@lru_cache(maxsize=1)
def carregar(caminho: str | None = None) -> tuple[RegraServico, ...]:
    regras = []
    with open(Path(caminho) if caminho else config.ARQ_SERVICOS, encoding="utf-8", newline="") as f:
        for l in csv.DictReader(f, delimiter=";"):
            regras.append(RegraServico(
                item=l["item"].strip(), descricao=l["descricao"].strip(),
                palavras_chave=(l.get("palavras_chave") or "").strip(),
                nbs=tuple(c for c in (l.get("nbs") or "").split(",") if c),
                regime=l["regime"].strip(), reducao_percentual=float(l["reducao_percentual"] or 0),
                fundamento=l["fundamento"].strip(),
                validado=(l.get("validado") or "").strip().lower() in ("sim", "s", "true", "1"),
                observacao=(l.get("observacao") or "").strip(), texto_lei=(l.get("texto_lei") or "").strip()))
    return tuple(regras)


def _eh_codigo_nbs(consulta: str) -> bool:
    return bool(re.fullmatch(r"[\d.\s]+", consulta.strip())) and len(re.sub(r"\D", "", consulta)) >= 4


def buscar_servico_detalhado(consulta: str, limite: int = 5) -> list[tuple[RegraServico, dict]]:
    """(regra, {confianca, cobertura}). Por código NBS (prefixo nos dois sentidos) ou por texto."""
    if _eh_codigo_nbs(consulta):
        cod = re.sub(r"\D", "", consulta)
        achadas = [r for r in carregar() if any(n.startswith(cod) or cod.startswith(n) for n in r.nbs)]
        return [(r, {"confianca": "alta", "cobertura": 1.0}) for r in achadas[:limite]]
    regras = carregar()
    ranking, _ = ranquear(consulta, [(r.descricao, r.palavras_chave.replace(",", " ")) for r in regras], GENERICAS)
    return [(regras[x["indice"]], {"confianca": x["confianca"], "cobertura": round(x["cobertura"], 2)})
            for x in ranking[:limite]]


def buscar_servico(consulta: str, limite: int = 5) -> list[RegraServico]:
    return [r for r, _ in buscar_servico_detalhado(consulta, limite)]


def consultar_servico(consulta: str, ano: int | None = None) -> dict:
    """Resposta determinística para um serviço (NBS ou texto). Sempre com fundamento e avisos."""
    ano = ano or config.ANO_PADRAO
    p = parametros()["anos"].get(str(ano))
    if p is None:
        return {"erro": f"Ano {ano} não cadastrado em parametros.json."}
    if not consulta or not consulta.strip():
        return {"erro": "Informe o serviço (nome ou código NBS)."}

    encontrados = []
    for r, info in buscar_servico_detalhado(consulta):
        avisos = [] if r.validado else ["Regra ainda NÃO validada por um contador. Use apenas como referência."]
        if r.observacao:
            avisos.append(r.observacao)
        encontrados.append({
            "item": r.item, "descricao": r.descricao, "nbs": list(r.nbs), "regime": r.regime,
            "reducao_percentual": r.reducao_percentual, "aliquotas_percentual": aliquotas(p, r.reducao_percentual),
            "fundamento": r.fundamento, "texto_lei": r.texto_lei, "avisos": avisos, **info})

    avisos = []
    if encontrados and all(e["confianca"] == "baixa" for e in encontrados):
        avisos.append("CONFIANÇA BAIXA: o serviço pedido só casou em parte com os itens abaixo. Não afirme que ele "
                      "está na lei sem o usuário confirmar o item.")
    if encontrados:
        avisos.append("Confirme que o serviço é exatamente o descrito em `descricao` e `texto_lei`: a busca é por "
                      "código ou palavras e pode trazer itens parecidos.")
    else:
        avisos.append("Serviço NÃO consta dos anexos de serviços cadastrados (hoje só educação e saúde, com "
                      "redução de 60%). Presume-se a alíquota padrão, mas a lei tem regimes específicos que "
                      "ainda não estão cadastrados: confirme com um contador.")
    avisos.append("Regras de Simples Nacional e MEI não se aplicam a esta consulta: consulte `consultar_simples`.")
    if p.get("observacao"):
        avisos.append(p["observacao"])
    return {
        "consulta": consulta, "ano": ano, "encontrados": encontrados,
        "regime_presumido_se_nao_encontrado": None if encontrados else "padrao",
        "aliquotas_presumidas_percentual": None if encontrados else aliquotas(p, 0.0),
        "fonte_aliquotas": p.get("fonte"), "avisos": avisos,
    }
