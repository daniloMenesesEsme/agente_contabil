from gerar_anexos_regimes import montar_tabela, regime_do_titulo


def test_regime_so_quando_o_titulo_diz():
    assert regime_do_titulo("DISPOSITIVOS SUBMETIDOS À REDUÇÃO DE 60% (SESSENTA POR CENTO) DAS ALÍQUOTAS") == ("reducao_60", 60)
    assert regime_do_titulo("X SUBMETIDOS À REDUÇÃO A ZERO DAS ALÍQUOTAS") == ("aliquota_zero", 100)
    assert regime_do_titulo("PRODUTOS SUBMETIDOS À REDUÇÃO DE 100% (CEM POR CENTO)") == ("aliquota_zero", 100)
    assert regime_do_titulo("LIMITE INFERIOR PARA FIXAÇÃO DA ALÍQUOTA PRÓPRIA") == ("a_definir", "")


def test_percentual_sem_regime_cadastrado_nao_e_inventado():
    assert regime_do_titulo("SUBMETIDOS À REDUÇÃO DE 50% DAS ALÍQUOTAS") == ("a_definir", "")


def test_titulo_ambiguo_fica_a_definir():
    assert regime_do_titulo("REDUÇÃO DE 60% ... e REDUÇÃO A ZERO") == ("a_definir", "")


def test_tabela_tipos_e_chaves_unicas():
    texto = ("ANEXO I\nALIMENTOS SUBMETIDOS À REDUÇÃO A ZERO DAS ALÍQUOTAS\n1006.20 arroz\n"
             "ANEXO II\nSERVIÇOS DE EDUCAÇÃO SUBMETIDOS À REDUÇÃO DE 60% DAS ALÍQUOTAS\n"
             "ANEXO I\nAlíquotas e Partilha do Simples Nacional - Comércio\nPara 2027 e 2028\n"
             "ANEXO XIV\n(Revogado pela Lei Complementar nº 227, de 2026)\n0101.21 x\n")
    t = {l["anexo"]: l for l in montar_tabela(texto)}
    assert set(t) == {"I", "II", "SN-I", "XIV"}
    assert (t["I"]["regime"], t["I"]["tipo"]) == ("aliquota_zero", "ncm")
    assert (t["II"]["regime"], t["II"]["tipo"]) == ("reducao_60", "servico")
    assert (t["SN-I"]["regime"], t["SN-I"]["tipo"]) == ("a_definir", "simples_mei")
    assert (t["XIV"]["regime"], t["XIV"]["tipo"]) == ("revogado", "revogado")
    assert all(l["validado"] == "nao" for l in t.values())
    assert t["I"]["fundamento"] == "LC 214/2025, Anexo I"
