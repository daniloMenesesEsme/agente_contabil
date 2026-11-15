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
    texto = ("Lei de 2025\nconstantes do Anexo I desta Lei 1006.20\nANEXO I\n"
             "1 Arroz 1006.20 e 1006.30\nPães 1905 e sucos 2009\nvigência em 2027, Lei nº 10.833/2003\n"
             "ANEXO VII\nItem 0401.10.10 leite")
    out = [(o["anexo"], o["ncm"]) for o in extrair_linhas(texto)]
    assert out == [("I", "1006.20"), ("I", "1006.30"), ("I", "1905"), ("I", "2009"), ("VII", "0401.10.10")]


def test_extracao_html(tmp_path):
    from extrair_anexos_lc214 import extrair_linhas, ler_texto
    html = ("<html><body><p>Texto da lei de 2025</p><p align=center><b>ANEXO&nbsp;I</b></p>"
            "<table><tr><td>1</td><td>Arroz</td><td>1006.20, 1006.30 e 1006.40.00</td></tr></table>"
            "</body></html>")
    arq = tmp_path / "lc.htm"
    arq.write_bytes(html.encode("latin-1"))
    out = [o["ncm"] for o in extrair_linhas(ler_texto(arq))]
    assert out == ["1006.20", "1006.30", "1006.40.00"]


def test_titulos_anexos():
    from extrair_anexos_lc214 import titulos_anexos
    texto = "ANEXO I\n\nPRODUTOS DESTINADOS À ALIMENTAÇÃO\nArroz 1006.20\nANEXO II\nSERVIÇOS\nANEXO I\nOUTRO"
    t = titulos_anexos(texto)
    assert t["I"]["titulo"] == "PRODUTOS DESTINADOS À ALIMENTAÇÃO"
    assert t["II"]["titulo"] == "SERVIÇOS"
    # o segundo "ANEXO I" tem outro contexto: ganha chave própria em vez de se perder
    assert t["I-2"] == {"anexo": "I", "titulo": "OUTRO", "tipo": "lc214"}


def test_ressalva_e_texto_da_lei_acompanham_a_resposta():
    r = consultar("03061100", 2026)
    assert r["regime"] == "reducao_60"
    assert any("exceção ou condição" in a for a in r["avisos"])
    assert "exceto os produtos da subposição 0306.11" in r["texto_lei"]


def test_codigo_incompleto_na_lei_exige_confirmar_o_enquadramento():
    r = consultar("39269099", 2026)  # a regra é "3926.9": vale só para a bengala descrita
    assert r["regime"] == "reducao_60" and r["enquadramento_a_confirmar"] is True
    assert r["avisos"][0].startswith("ATENÇÃO: o benefício vale só para o produto descrito")
    assert "alíquota padrão (total 1.0% em 2026)" in r["avisos"][0]


def test_codigo_completo_nao_pede_confirmacao_de_enquadramento():
    assert consultar("10063021", 2026)["enquadramento_a_confirmar"] is False


def test_conflito_entre_anexos_nao_informa_aliquota():
    r = consultar("21069090", 2026)
    assert r["regime"] == "a_confirmar" and r["enquadramento_a_confirmar"] is True
    assert r["aliquotas_percentual"] == {"cbs": None, "ibs_uf": None, "ibs_mun": None, "total": None}
    assert r["avisos"][0].startswith("REGIME NÃO DEFINIDO")
    assert not any("ainda não foi definida oficialmente" in a for a in r["avisos"])
