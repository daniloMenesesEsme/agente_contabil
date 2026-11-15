"""Gera dados/simples_anexos.csv: as tabelas do Simples Nacional/MEI que a LC 214 traz, SEM interpretar.

Uso:
  python scripts/gerar_simples.py "dados/brutos/Lcp 214.html" [--sobrescrever]

Cada linha da lei vira uma linha do CSV com a seção (período, ex.: 'Para os anos-calendário 2027 e 2028'),
o tipo (faixa | cabecalho | linha | nota) e as células literais (JSON). Nenhuma coluna é nomeada ou somada
aqui: o significado de cada célula vem dos cabeçalhos, que acompanham a consulta. validado=nao em tudo.
"""
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extrair_anexos_lc214 import ler_texto, ocorrencias_anexos  # noqa: E402

DESTINO = Path("dados/simples_anexos.csv")
COLUNAS = ["anexo", "titulo", "secao", "ordem", "tipo", "celulas", "texto_lei", "fundamento", "validado"]
RE_SECAO = re.compile(r"ano-calend|anos-calend|vig[eê]ncia|a partir d", re.IGNORECASE)
RE_FAIXA = re.compile(r"^\d+\s*ª")
RE_VALOR = re.compile(r"\d+,\d{2}|\d+\s*%|\d{1,3}\.\d{3}")  # valor em R$, percentual ou milhar
LIMITE_SECAO = 90  # linha curta de prosa com período = título de seção; as longas são notas


def _tipo(celulas: list[str]) -> str:
    if RE_FAIXA.match(celulas[0]):
        return "faixa"
    return "linha" if any(RE_VALOR.search(c) for c in celulas) else "cabecalho"


def linhas_do_anexo(oc: dict) -> list[dict]:
    secao, saida = "", []
    for linha in oc["corpo"]:
        texto = " ".join(linha.split())
        if " | " in linha:
            celulas = [" ".join(c.split()) for c in linha.split(" | ")]
            celulas = [c for c in celulas if c and c != "|"]
            if not celulas:
                continue
            tipo = _tipo(celulas)
        elif len(texto) <= 3:
            continue  # sobra de formatação
        elif not saida and not secao and texto in oc["titulo"]:
            continue  # pedaço do próprio título, antes da primeira tabela
        elif len(texto) <= LIMITE_SECAO and RE_SECAO.search(texto):
            secao = texto
            continue
        else:
            celulas, tipo = [texto], "nota"
        saida.append({"anexo": oc["chave"], "titulo": oc["titulo"], "secao": secao, "ordem": len(saida) + 1,
                      "tipo": tipo, "celulas": json.dumps(celulas, ensure_ascii=False),
                      "texto_lei": " | ".join(celulas)[:700], "fundamento": f"LC 214/2025, Anexo {oc['anexo']} "
                      f"({'MEI' if oc['chave'].startswith('MEI-') else 'Simples Nacional'})", "validado": "nao"})
    return saida


def gerar(texto: str) -> list[dict]:
    return [l for oc in ocorrencias_anexos(texto) if oc["tipo"] == "simples_mei" for l in linhas_do_anexo(oc)]


def main(arquivo: str, sobrescrever: bool) -> None:
    if DESTINO.exists() and not sobrescrever:
        with open(DESTINO, encoding="utf-8", newline="") as f:
            if any(l["validado"].lower() in ("sim", "s") for l in csv.DictReader(f, delimiter=";")):
                sys.exit(f"{DESTINO} tem linhas validado=sim. Use --sobrescrever só se tiver certeza.")
    linhas = gerar(ler_texto(Path(arquivo)))
    with open(DESTINO, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS, delimiter=";")
        w.writeheader()
        w.writerows(linhas)
    print(f"{len(linhas)} linhas -> {DESTINO}")
    por: dict = {}
    for l in linhas:
        d = por.setdefault(l["anexo"], {"faixa": 0, "cabecalho": 0, "linha": 0, "nota": 0, "secoes": set()})
        d[l["tipo"]] += 1
        d["secoes"].add(l["secao"])
    for anexo, d in por.items():
        print(f"  {anexo:8} faixas={d['faixa']:3} cabeçalhos={d['cabecalho']:2} linhas={d['linha']:2} "
              f"notas={d['nota']:2} seções={len(d['secoes'])}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--sobrescrever"]
    if len(args) != 1:
        sys.exit(__doc__)
    main(args[0], "--sobrescrever" in sys.argv)
