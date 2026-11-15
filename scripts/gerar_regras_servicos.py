"""Gera dados/regras_servicos.csv a partir dos anexos de SERVIÇOS da LC 214 (tabelas 'item | descrição | NBS').

Uso:
  python scripts/gerar_regras_servicos.py "dados/brutos/Lcp 214.html" [--sobrescrever]

Só entram anexos com tipo=servico em dados/anexos_regimes.csv (regime lido do título oficial).
Serviço não tem NCM: o código é a NBS. Uma linha por item da lei; todas com validado=nao.
"""
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extrair_anexos_lc214 import ler_texto, ocorrencias_anexos  # noqa: E402
from gerar_regras import palavras_chave  # noqa: E402

ANEXOS = Path("dados/anexos_regimes.csv")
DESTINO = Path("dados/regras_servicos.csv")
COLUNAS = ["item", "descricao", "palavras_chave", "nbs", "regime", "reducao_percentual", "fundamento",
           "validado", "observacao", "texto_lei"]
# NBS: 1.2301.10.00 (9 dígitos) ou prefixos como 1.2301 / 1.2301.10
RE_NBS = re.compile(r"(?<![\d.])\d\.\d{2,4}(?:\.\d{2}){0,2}(?![\d.]*\d)")


def nbs_da_celula(celula: str) -> list[str]:
    """Códigos NBS da célula, só dígitos ('1.2301.10.00' -> '123011000'), sem repetição."""
    vistos: list[str] = []
    for m in RE_NBS.finditer(celula):
        cod = re.sub(r"\D", "", m.group(0))
        if cod not in vistos:
            vistos.append(cod)
    return vistos


def linhas_do_anexo(corpo: list[str], anexo: dict) -> list[dict]:
    regras = []
    for linha in corpo:
        celulas = [c.strip() for c in linha.split(" | ")]
        if len(celulas) < 2 or celulas[0].upper().startswith("ITEM"):
            continue  # cabeçalho ou texto fora da tabela
        codigos = nbs_da_celula(celulas[2]) if len(celulas) > 2 else []
        descricao = re.sub(r"\s+", " ", celulas[1]).strip(" ,;:-–.")
        regras.append({
            "item": f"{anexo['anexo']}-{celulas[0].strip(' .')}",
            "descricao": descricao, "palavras_chave": palavras_chave(descricao), "nbs": ",".join(codigos),
            "regime": anexo["regime"], "reducao_percentual": anexo["reducao_percentual"],
            "fundamento": anexo["fundamento"], "validado": "nao",
            "observacao": "" if codigos else "Código NBS não identificado nesta linha: confira o enquadramento pelo texto da lei.",
            "texto_lei": " | ".join(celulas)[:600],
        })
    return regras


def gerar(texto: str, anexos: dict[str, dict]) -> list[dict]:
    regras = []
    for oc in ocorrencias_anexos(texto):
        anexo = anexos.get(oc["chave"])
        if anexo and anexo["tipo"] == "servico" and anexo["regime"] != "a_definir":
            regras += linhas_do_anexo(oc["corpo"], anexo)
    return regras


def main(arquivo: str, sobrescrever: bool) -> None:
    if DESTINO.exists() and not sobrescrever:
        with open(DESTINO, encoding="utf-8", newline="") as f:
            if any(l["validado"].lower() in ("sim", "s") for l in csv.DictReader(f, delimiter=";")):
                sys.exit(f"{DESTINO} tem linhas validado=sim. Use --sobrescrever só se tiver certeza.")
    with open(ANEXOS, encoding="utf-8", newline="") as f:
        anexos = {a["anexo"]: a for a in csv.DictReader(f, delimiter=";")}
    regras = gerar(ler_texto(Path(arquivo)), anexos)
    with open(DESTINO, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS, delimiter=";")
        w.writeheader()
        w.writerows(regras)
    print(f"{len(regras)} serviços -> {DESTINO}")
    por = {}
    for r in regras:
        por.setdefault(r["fundamento"], [0, 0])
        por[r["fundamento"]][0] += 1
        por[r["fundamento"]][1] += bool(r["nbs"])
    for fund, (n, com) in por.items():
        print(f"  {fund}: {n} itens ({com} com NBS)")
    for r in regras[:3] + regras[-2:]:
        print(f"  {r['item']:6} {r['descricao'][:70]} | nbs={r['nbs'][:30]}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--sobrescrever"]
    if len(args) != 1:
        sys.exit(__doc__)
    main(args[0], "--sobrescrever" in sys.argv)
