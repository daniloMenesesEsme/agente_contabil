"""Gera dados/anexos_regimes.csv: regime de cada anexo da LC 214, lido SÓ do título oficial.

Uso:
  python scripts/gerar_anexos_regimes.py "dados/brutos/Lcp 214.html" [--sobrescrever]

Regra de ouro: o regime só é preenchido quando o título diz explicitamente
("REDUÇÃO DE 60%", "REDUÇÃO A ZERO"...). Caso contrário fica `a_definir`: um contador confere o
artigo da LC 214 que remete ao anexo. Todas as linhas saem com validado=nao.
O script se recusa a sobrescrever um arquivo existente (pode ter revisão manual).
"""
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extrair_anexos_lc214 import ler_texto, ocorrencias_anexos  # noqa: E402

DESTINO = Path("dados/anexos_regimes.csv")
COLUNAS = ["anexo", "titulo_oficial", "regime", "reducao_percentual", "fundamento", "validado", "tipo"]

RE_ZERO = re.compile(r"redu[cç][aã]o\s+a\s+zero|al[ií]quota\s+zero", re.IGNORECASE)
RE_PERCENTUAL = re.compile(r"redu[cç][aã]o\s+de\s+(\d{1,3})\s*%", re.IGNORECASE)
REGIME_POR_PERCENTUAL = {100: ("aliquota_zero", 100), 60: ("reducao_60", 60), 30: ("reducao_30", 30)}


def regime_do_titulo(titulo: str) -> tuple[str, str]:
    """(regime, redução %) quando o título diz explicitamente; senão ('a_definir', '')."""
    achados = set()
    if RE_ZERO.search(titulo):
        achados.add(("aliquota_zero", 100))
    for pct in RE_PERCENTUAL.findall(titulo):
        achados.add(REGIME_POR_PERCENTUAL.get(int(pct), ("a_definir", "")))
    if len(achados) != 1:
        return "a_definir", ""  # nenhum regime no título, ou títulos ambíguos
    regime, reducao = achados.pop()
    return regime, reducao


def _tipo(oc: dict) -> str:
    titulo = oc["titulo"].lower()
    if "revogad" in titulo:
        return "revogado"
    if oc["tipo"] == "simples_mei":
        return "simples_mei"
    if oc["ncms"]:
        return "ncm"
    return "servico" if titulo.startswith("serviço") or titulo.startswith("servico") else "outro"


def _fundamento(oc: dict) -> str:
    if oc["tipo"] == "simples_mei":
        quem = "MEI" if oc["chave"].startswith("MEI-") else "Simples Nacional"
        return f"LC 214/2025, Anexo {oc['anexo']} (trecho do {quem})"
    return f"LC 214/2025, Anexo {oc['anexo']}"


def montar_tabela(texto: str) -> list[dict]:
    tabela = []
    for oc in ocorrencias_anexos(texto):
        tipo = _tipo(oc)
        regime, reducao = ("revogado", "") if tipo == "revogado" else regime_do_titulo(oc["titulo"])
        if tipo == "simples_mei":
            regime, reducao = "a_definir", ""  # percentuais do título (se houver) não se aplicam
        tabela.append({"anexo": oc["chave"], "titulo_oficial": oc["titulo"], "regime": regime,
                       "reducao_percentual": reducao, "fundamento": _fundamento(oc),
                       "validado": "nao", "tipo": tipo})
    return tabela


def main(arquivo: str, sobrescrever: bool) -> None:
    if DESTINO.exists() and not sobrescrever:
        sys.exit(f"{DESTINO} já existe (pode ter revisão manual). Use --sobrescrever para refazer.")
    tabela = montar_tabela(ler_texto(Path(arquivo)))
    with open(DESTINO, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS, delimiter=";")
        w.writeheader()
        w.writerows(tabela)
    print(f"{len(tabela)} anexos -> {DESTINO}")
    for linha in tabela:
        print(f"  {linha['anexo']:8} {linha['regime']:14} {str(linha['reducao_percentual']):>4} "
              f"{linha['tipo']:12} {linha['titulo_oficial'][:70]}")
    pendentes = [l["anexo"] for l in tabela if l["regime"] == "a_definir" and l["tipo"] == "ncm"]
    print(f"\nAnexos COM NCMs e regime a_definir (conferir o artigo da lei): {pendentes or 'nenhum'}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--sobrescrever"]
    if len(args) != 1:
        sys.exit(__doc__)
    main(args[0], "--sobrescrever" in sys.argv)
