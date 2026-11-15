"""Verifica a consistência de dados/regras_ncm.csv. Rode antes de cada atualização."""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from agente_contabil.regras import REGIMES, carregar  # noqa: E402

ESPERADO = {"aliquota_zero": 100, "reducao_60": 60, "reducao_30": 30, "padrao": 0}


def validar() -> list[str]:
    erros, regras = [], carregar()
    for r in regras:
        if len(r.ncm_prefixo) not in (2, 4, 5, 6, 7, 8):
            erros.append(f"{r.ncm_prefixo}: prefixo deve ter 2, 4, 5, 6, 7 ou 8 dígitos")
        if r.regime not in REGIMES:
            erros.append(f"{r.ncm_prefixo}: regime desconhecido '{r.regime}'")
        if r.regime in ESPERADO and r.reducao_percentual != ESPERADO[r.regime]:
            erros.append(f"{r.ncm_prefixo}: regime {r.regime} exige redução {ESPERADO[r.regime]}")
        if r.outros_produtos not in ("", "padrao", "a_confirmar"):
            erros.append(f"{r.ncm_prefixo}: outros_produtos inválido '{r.outros_produtos}'")
        if not r.fundamento:
            erros.append(f"{r.ncm_prefixo}: sem fundamento legal")
    for ncm, n in Counter(r.ncm_prefixo for r in regras).items():
        if n > 1:
            erros.append(f"{ncm}: prefixo duplicado")
    pend = sum(not r.validado for r in regras)
    print(f"{len(regras)} regras | {pend} ainda não validadas")
    return erros


if __name__ == "__main__":
    erros = validar()
    print("\n".join(erros) or "OK: nenhum erro de estrutura.")
    sys.exit(1 if erros else 0)
