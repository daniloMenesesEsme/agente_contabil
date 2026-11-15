"""Simples Nacional e MEI: tabelas que a LC 214 traz, reproduzidas SEM interpretação.

Nada aqui calcula alíquota: as células vêm literais da lei, junto com os cabeçalhos que dizem o que
cada coluna significa. O enquadramento da empresa no anexo (atividade, faixa de receita) é decisão
do contador."""
import csv
import json
import re
from functools import lru_cache
from pathlib import Path

from . import config


@lru_cache(maxsize=1)
def carregar(caminho: str | None = None) -> tuple[dict, ...]:
    with open(Path(caminho) if caminho else config.ARQ_SIMPLES, encoding="utf-8", newline="") as f:
        return tuple({**l, "ordem": int(l["ordem"]), "celulas": json.loads(l["celulas"])}
                     for l in csv.DictReader(f, delimiter=";"))


def _chave(anexo: str) -> str:
    """'I' -> 'SN-I'; 'sn-iii' -> 'SN-III'; 'MEI' ou 'MEI-VII' -> 'MEI-VII'."""
    a = re.sub(r"\s+", "", anexo or "").upper()
    if a.startswith("MEI"):
        return "MEI-VII"
    return a if a.startswith("SN-") else f"SN-{a}"


def consultar_simples(anexo: str | None = None) -> dict:
    """Sem `anexo`: lista os anexos disponíveis. Com `anexo` (I a V ou MEI): as tabelas, por seção."""
    linhas = carregar()
    disponiveis = {}
    for l in linhas:
        disponiveis.setdefault(l["anexo"], l["titulo"])
    avisos = [
        "Texto da LC 214 que altera as tabelas do Simples Nacional/MEI (LC 123), reproduzido SEM interpretação e "
        "ainda NÃO validado por um contador. Use os `cabecalhos` para saber o que cada coluna significa.",
        "Qual anexo e qual faixa se aplicam à empresa depende da atividade e da receita bruta: decisão do contador. "
        "Verifique a `secao` (período de vigência) de cada tabela.",
    ]
    if not anexo or not anexo.strip():
        return {"anexos_disponiveis": disponiveis, "avisos": avisos}
    chave = _chave(anexo)
    if chave not in disponiveis:
        return {"erro": f"Anexo '{anexo}' não encontrado. Disponíveis: {', '.join(disponiveis)}."}
    secoes: dict[str, list[dict]] = {}
    for l in sorted((x for x in linhas if x["anexo"] == chave), key=lambda x: x["ordem"]):
        secoes.setdefault(l["secao"], []).append({"tipo": l["tipo"], "celulas": l["celulas"]})
    return {"anexo": chave, "titulo": disponiveis[chave],
            "fundamento": next(l["fundamento"] for l in linhas if l["anexo"] == chave),
            "secoes": [{"secao": s, "linhas": ls} for s, ls in secoes.items()], "avisos": avisos}
