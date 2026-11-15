"""Base de regras NCM -> regime. Busca pelo prefixo mais longo (mais específico)."""
import csv
from dataclasses import dataclass, asdict
from functools import lru_cache
from pathlib import Path

from . import config
from .normalizacao import normalizar_ncm

# a_confirmar: a lei lista o NCM em anexos com regimes diferentes; nenhum foi escolhido automaticamente
REGIMES = {"padrao", "aliquota_zero", "reducao_60", "reducao_30", "especifico", "isento", "a_confirmar"}


@dataclass(frozen=True)
class Regra:
    ncm_prefixo: str
    descricao: str
    palavras_chave: str
    regime: str
    reducao_percentual: float
    cclasstrib: str
    fundamento: str
    validado: bool
    observacao: str
    texto_lei: str = ""   # linha literal do anexo da lei, para o contador conferir
    ressalva: str = ""    # aviso quando a lei traz exceção/condição para o item

    def to_dict(self) -> dict:
        return asdict(self)


def _ler(caminho: Path) -> list[Regra]:
    regras = []
    with open(caminho, encoding="utf-8") as f:
        for linha in csv.DictReader(f, delimiter=";"):
            regras.append(Regra(
                ncm_prefixo=normalizar_ncm(linha["ncm_prefixo"]),
                descricao=linha["descricao"].strip(),
                palavras_chave=linha.get("palavras_chave", "").strip(),
                regime=linha["regime"].strip(),
                reducao_percentual=float(linha["reducao_percentual"] or 0),
                cclasstrib=linha.get("cclasstrib", "").strip(),
                fundamento=linha["fundamento"].strip(),
                validado=linha.get("validado", "").strip().lower() in ("sim", "s", "true", "1"),
                observacao=linha.get("observacao", "").strip(),
                texto_lei=linha.get("texto_lei", "").strip(),
                ressalva=linha.get("ressalva", "").strip(),
            ))
    return regras


@lru_cache(maxsize=1)
def carregar(caminho: str | None = None) -> tuple[Regra, ...]:
    return tuple(_ler(Path(caminho) if caminho else config.ARQ_REGRAS))


def buscar_por_ncm(ncm: str, regras: tuple[Regra, ...] | None = None) -> Regra | None:
    """Retorna a regra cujo prefixo casa com o NCM, preferindo o prefixo mais longo."""
    codigo = normalizar_ncm(ncm)
    if not codigo:
        return None
    candidatas = [r for r in (regras or carregar()) if codigo.startswith(r.ncm_prefixo)]
    return max(candidatas, key=lambda r: len(r.ncm_prefixo), default=None)
