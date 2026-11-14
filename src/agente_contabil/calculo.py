"""Cálculo das alíquotas efetivas de IBS/CBS para um NCM e ano."""
import json
from functools import lru_cache

from . import config
from .normalizacao import normalizar_ncm, ncm_valido
from .regras import Regra, buscar_por_ncm


@lru_cache(maxsize=1)
def parametros() -> dict:
    with open(config.ARQ_PARAMETROS, encoding="utf-8") as f:
        return json.load(f)


def _aplicar(aliquota: float | None, fator: float) -> float | None:
    return None if aliquota is None else round(aliquota * fator, 4)


def consultar(ncm: str, ano: int | None = None) -> dict:
    """Resposta determinística (sem IA) para um NCM. Sempre inclui fundamento e avisos."""
    ano = ano or config.ANO_PADRAO
    avisos: list[str] = []

    if not ncm_valido(ncm):
        return {"erro": f"NCM inválido: '{ncm}'. Informe 8 dígitos (ou prefixo de 2/4/6)."}

    p = parametros()["anos"].get(str(ano))
    if p is None:
        return {"erro": f"Ano {ano} não cadastrado em parametros.json."}

    regra: Regra | None = buscar_por_ncm(ncm)
    if regra is None:
        avisos.append("Nenhuma regra específica cadastrada para este NCM: presume-se alíquota padrão. "
                      "Confirme nos anexos da LC 214/2025.")
        regime, reducao, fundamento, descricao = "padrao", 0.0, "LC 214/2025, regra geral (presunção)", None
    else:
        regime, reducao, fundamento, descricao = (regra.regime, regra.reducao_percentual,
                                                  regra.fundamento, regra.descricao)
        if not regra.validado:
            avisos.append("Regra ainda NÃO validada por um contador. Use apenas como referência.")
        if regra.observacao:
            avisos.append(regra.observacao)

    fator = 1 - reducao / 100
    cbs = _aplicar(p["cbs"], fator)
    ibs_uf = _aplicar(p["ibs_uf"], fator)
    ibs_mun = _aplicar(p["ibs_mun"], fator)
    if None in (cbs, ibs_uf, ibs_mun):
        avisos.append(f"Alguma alíquota de {ano} ainda não foi definida oficialmente (valor null).")
    if p.get("observacao"):
        avisos.append(p["observacao"])

    total = None if None in (cbs, ibs_uf, ibs_mun) else round(cbs + ibs_uf + ibs_mun, 4)
    return {
        "ncm": normalizar_ncm(ncm),
        "descricao_regra": descricao,
        "ano": ano,
        "regime": regime,
        "reducao_percentual": reducao,
        "cclasstrib": regra.cclasstrib if regra else "",
        "aliquotas_percentual": {"cbs": cbs, "ibs_uf": ibs_uf, "ibs_mun": ibs_mun, "total": total},
        "fundamento": fundamento,
        "fonte_aliquotas": p.get("fonte"),
        "avisos": avisos,
    }
