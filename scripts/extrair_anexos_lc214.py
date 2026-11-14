"""Extrai NCMs dos anexos da LC 214/2025 (PDF oficial) para um CSV de REVISÃO.

Uso:
  python scripts/extrair_anexos_lc214.py dados/brutos/lc214.pdf

Gera dados/brutos/extraido_lc214.csv. NÃO altera regras_ncm.csv:
um contador deve revisar e copiar as linhas validadas (validado=sim).
"""
import csv
import re
import sys
from pathlib import Path

RE_ANEXO = re.compile(r"^\s*ANEXO\s+([IVXL]+)\b", re.IGNORECASE)
RE_NCM = re.compile(r"\b(\d{4}(?:\.\d{1,2}){0,2}|\d{8})\b")


def extrair_linhas(texto: str) -> list[dict]:
    """Percorre o texto e devolve {anexo, ncm, linha} para cada NCM encontrado."""
    anexo, saida = "", []
    for linha in texto.splitlines():
        m = RE_ANEXO.match(linha)
        if m:
            anexo = m.group(1).upper()
            continue
        if not anexo:
            continue
        for ncm in RE_NCM.findall(linha):
            digitos = re.sub(r"\D", "", ncm)
            if len(digitos) in (4, 6, 8) and not (1900 <= int(digitos[:4]) <= 2100 and len(digitos) == 4):
                saida.append({"anexo": anexo, "ncm": ncm, "linha": linha.strip()[:300]})
    return saida


def main(pdf: str) -> None:
    import pdfplumber
    with pdfplumber.open(pdf) as doc:
        texto = "\n".join(p.extract_text() or "" for p in doc.pages)
    linhas = extrair_linhas(texto)
    destino = Path("dados/brutos/extraido_lc214.csv")
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["anexo", "ncm", "linha"], delimiter=";")
        w.writeheader(); w.writerows(linhas)
    print(f"{len(linhas)} NCMs extraídos -> {destino}. Revise antes de usar.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
