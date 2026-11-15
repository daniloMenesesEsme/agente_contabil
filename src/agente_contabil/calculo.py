"""Cálculo das alíquotas efetivas de IBS/CBS para um NCM e ano."""
import json
from functools import lru_cache

from . import config
from .normalizacao import normalizar_ncm, ncm_valido
from .ncm_tabela import descricao_oficial
from .regras import Regra, buscar_por_ncm


@lru_cache(maxsize=1)
def parametros() -> dict:
    with open(config.ARQ_PARAMETROS, encoding="utf-8") as f:
        return json.load(f)


def _aplicar(aliquota: float | None, fator: float) -> float | None:
    return None if aliquota is None else round(aliquota * fator, 4)


def aliquotas(p: dict, reducao: float) -> dict:
    """CBS, IBS UF, IBS município e total (%) do ano `p` com a redução dada (None = indefinida)."""
    fator = 1 - reducao / 100
    cbs, uf, mun = (_aplicar(p[k], fator) for k in ("cbs", "ibs_uf", "ibs_mun"))
    total = None if None in (cbs, uf, mun) else round(cbs + uf + mun, 4)
    return {"cbs": cbs, "ibs_uf": uf, "ibs_mun": mun, "total": total}


SEM_ALIQUOTA = {"cbs": None, "ibs_uf": None, "ibs_mun": None, "total": None}


def consultar(ncm: str, ano: int | None = None) -> dict:
    """Resposta determinística (sem IA) para um NCM. Sempre inclui fundamento e avisos.

    Quando o enquadramento depende de conferência (código incompleto na lei, ou NCM em anexos com
    regimes diferentes), o topo da resposta NÃO afirma um regime: `regime="a_confirmar"`, alíquotas
    nulas e, se couber, os `cenarios` possíveis. Assim quem lê só o JSON não é induzido a erro."""
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
    # A regra vale só para o produto DESCRITO (não para todo o código) quando: a lei cita o código
    # incompleto (5 ou 7 dígitos, ex.: "8517.1": um celular casaria com um aparelho para surdos) ou
    # o NCM é compartilhado com um anexo revogado (coluna outros_produtos). Os demais produtos do
    # código ficam em `outros`: "padrao" ou "a_confirmar".
    outros = ""
    if regra and regime not in ("padrao", "a_confirmar"):
        outros = regra.outros_produtos or ("padrao" if len(regra.ncm_prefixo) in (5, 7) else "")
    incompleto = bool(outros)

    cenarios: list[dict] = []
    if incompleto:
        if outros == "padrao":
            outro = {"regime": "padrao", "reducao_percentual": 0.0, "aliquotas_percentual": aliquotas(p, 0.0)}
            fim_aviso = (f"Se o produto não for exatamente esse, aplica-se a alíquota padrão "
                         f"(total {outro['aliquotas_percentual']['total']}% em {ano}).")
        else:
            outro = {"regime": "a_confirmar", "reducao_percentual": None, "aliquotas_percentual": dict(SEM_ALIQUOTA)}
            fim_aviso = ("Para outros produtos com este NCM (ex.: medicamentos que constavam de anexo revogado) "
                         "o regime vigente NÃO foi identificado na base: confirme com um contador.")
        cenarios = [
            {"condicao": f"o produto é exatamente o descrito na regra: '{descricao}'",
             "regime": regime, "reducao_percentual": reducao, "aliquotas_percentual": aliquotas(p, reducao)},
            {"condicao": f"o produto é outro item do código {regra.ncm_prefixo}", **outro},
        ]
        avisos.insert(0, f"ATENÇÃO: o benefício vale só para o produto descrito na regra ('{descricao[:90]}'), "
                         f"não para todo o código {regra.ncm_prefixo}. {fim_aviso} Veja os cenarios.")
    if indefinido:
        avisos.insert(0, "REGIME NÃO DEFINIDO: a lei lista este NCM em mais de um anexo com regimes diferentes "
                         "(ou o anexo que o trazia foi revogado). Nenhuma alíquota foi calculada; "
                         "confirme o enquadramento com um contador.")

    if incompleto or indefinido:
        regime_topo, reducao_topo, aliq = "a_confirmar", None, dict(SEM_ALIQUOTA)
    else:
        regime_topo, reducao_topo, aliq = regime, reducao, aliquotas(p, reducao)
        if None in (aliq["cbs"], aliq["ibs_uf"], aliq["ibs_mun"]):
            avisos.append(f"Alguma alíquota de {ano} ainda não foi definida oficialmente (valor null).")
    if p.get("observacao"):
        avisos.append(p["observacao"])
    oficial = descricao_oficial(ncm)  # None se a tabela oficial não estiver instalada
    if oficial is not None and not oficial["existe"]:
        avisos.insert(0, f"NCM NÃO CONSTA da tabela oficial vigente ({oficial['tabela']}): confira o código no "
                         "cadastro do ERP e na nota fiscal do fornecedor antes de usar qualquer regime abaixo.")

    return {
        "ncm_oficial": oficial,
        "enquadramento_a_confirmar": incompleto or indefinido,
        "ncm": normalizar_ncm(ncm),
        "descricao_regra": descricao,
        "ano": ano,
        "regime": regime_topo,
        "reducao_percentual": reducao_topo,
        "cclasstrib": regra.cclasstrib if regra else "",
        "aliquotas_percentual": aliq,
        "cenarios": cenarios,
        "fundamento": fundamento,
        "texto_lei": regra.texto_lei if regra else "",
        "fonte_aliquotas": p.get("fonte"),
        "avisos": avisos,
    }
