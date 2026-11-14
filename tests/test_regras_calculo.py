from agente_contabil.busca import buscar_produto
from agente_contabil.calculo import consultar
from agente_contabil.ferramentas import executar
from agente_contabil.normalizacao import normalizar_ncm, normalizar_texto
from agente_contabil.regras import Regra, buscar_por_ncm


def _r(prefixo, regime="padrao"):
    return Regra(prefixo, "x", "", regime, 0, "", "f", True, "")


def test_normalizacao():
    assert normalizar_ncm("1006.30.21") == "10063021"
    assert normalizar_texto("Feijão Preto!") == "feijao preto"


def test_prefixo_mais_longo_vence():
    regras = (_r("1006"), _r("100630", "aliquota_zero"))
    assert buscar_por_ncm("10063021", regras).ncm_prefixo == "100630"
    assert buscar_por_ncm("10061000", regras).ncm_prefixo == "1006"
    assert buscar_por_ncm("99999999", regras) is None


def test_aliquota_zero_2026():
    r = consultar("1006.30.21", 2026)
    assert r["regime"] == "aliquota_zero"
    assert r["aliquotas_percentual"]["total"] == 0
    assert any("NÃO validada" in a for a in r["avisos"])


def test_reducao_60_2026():
    r = consultar("30049099", 2026)
    assert r["aliquotas_percentual"]["cbs"] == 0.36   # 0,9% x 40%
    assert r["aliquotas_percentual"]["ibs_uf"] == 0.04


def test_sem_regra_presume_padrao_com_aviso():
    r = consultar("94036000", 2026)
    assert r["regime"] == "padrao"
    assert r["aliquotas_percentual"]["total"] == 1.0
    assert any("presume-se" in a for a in r["avisos"])


def test_aliquota_indefinida_retorna_null():
    r = consultar("85171300", 2027)
    assert r["aliquotas_percentual"]["cbs"] is None
    assert r["aliquotas_percentual"]["total"] is None


def test_entradas_invalidas():
    assert "erro" in consultar("abc", 2026)
    assert "erro" in consultar("10063021", 1999)


def test_busca_sem_acento():
    assert buscar_produto("feijao")[0]["ncm_prefixo"] == "071333"
    assert buscar_produto("CELULAR")[0]["ncm_prefixo"] == "851713"
    assert buscar_produto("xyz") == []


def test_ferramenta_erro_sinalizado():
    _, erro = executar("consultar_ncm", {"ncm": "1", "ano": 2026})
    assert erro
    _, erro = executar("inexistente", {})
    assert erro


def test_extracao_anexos():
    from extrair_anexos_lc214 import extrair_linhas
    texto = "Lei de 2025\nANEXO I\n1 Arroz 1006.20 e 1006.30\nANEXO VII\nItem 0401.10.10 leite"
    out = extrair_linhas(texto)
    assert [(o["anexo"], o["ncm"]) for o in out] == [("I", "1006.20"), ("I", "1006.30"), ("VII", "0401.10.10")]
