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
        if regra.ressalva:
            avisos.append(regra.ressalva)
        if regra.observacao:
            avisos.append(regra.observacao)

    indefinido = regime == "a_confirmar"  # conflito entre anexos: não há alíquota a informar
    fator = 1 - reducao / 100
    cbs = None if indefinido else _aplicar(p["cbs"], fator)
    ibs_uf = None if indefinido else _aplicar(p["ibs_uf"], fator)
    ibs_mun = None if indefinido else _aplicar(p["ibs_mun"], fator)
    if indefinido:
        avisos.insert(0, "REGIME NÃO DEFINIDO: a lei lista este NCM em mais de um anexo com regimes diferentes. "
                         "Nenhuma alíquota foi calculada; confirme o enquadramento com um contador.")
    elif None in (cbs, ibs_uf, ibs_mun):
        avisos.append(f"Alguma alíquota de {ano} ainda não foi definida oficialmente (valor null).")
    if p.get("observacao"):
        avisos.append(p["observacao"])

    total = None if None in (cbs, ibs_uf, ibs_mun) else round(cbs + ibs_uf + ibs_mun, 4)
    # Código incompleto na lei (5 ou 7 dígitos, ex.: "8517.1"): o benefício vale para o produto
    # DESCRITO, não para todo o código. Sem isso, um celular casaria com um aparelho para surdos.
    incompleto = bool(regra and len(regra.ncm_prefixo) in (5, 7) and regime not in ("padrao", "a_confirmar"))
    if incompleto:
        padrao = [p["cbs"], p["ibs_uf"], p["ibs_mun"]]
        total_padrao = None if None in padrao else round(sum(padrao), 4)
        avisos.insert(0, f"ATENÇÃO: o benefício vale só para o produto descrito na regra ('{descricao[:90]}'), "
                         f"não para todo o código {regra.ncm_prefixo} (a lei cita o código incompleto). "
                         f"Se o produto não for exatamente esse, aplica-se a alíquota padrão "
                         f"(total {total_padrao}% em {ano}).")
    return {
        "enquadramento_a_confirmar": incompleto or indefinido,
        "ncm": normalizar_ncm(ncm),
        "descricao_regra": descricao,
        "ano": ano,
        "regime": regime,
        "reducao_percentual": reducao,
        "cclasstrib": regra.cclasstrib if regra else "",
        "aliquotas_percentual": {"cbs": cbs, "ibs_uf": ibs_uf, "ibs_mun": ibs_mun, "total": total},
        "fundamento": fundamento,
        "texto_lei": regra.texto_lei if regra else "",
        "fonte_aliquotas": p.get("fonte"),
        "avisos": avisos,
    }
