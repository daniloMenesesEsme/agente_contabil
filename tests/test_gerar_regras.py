from pathlib import Path

import pytest

from gerar_regras import (aninhados_com_regime_diferente, categoria_do_anexo, descricao_da_linha, gerar,
                          marcar_codigos_compartilhados_com_medicamentos, palavras_chave, regras_medicamentos)

ANEXOS = {
    "I": {"anexo": "I", "titulo_oficial": "ALIMENTOS SUBMETIDOS À REDUÇÃO A ZERO DAS ALÍQUOTAS", "regime": "aliquota_zero",
          "reducao_percentual": "100", "fundamento": "LC 214/2025, Anexo I", "tipo": "ncm"},
    "IV": {"anexo": "IV", "titulo_oficial": "DISPOSITIVOS MÉDICOS SUBMETIDOS À REDUÇÃO DE 60%", "regime": "reducao_60",
           "reducao_percentual": "60", "fundamento": "LC 214/2025, Anexo IV", "tipo": "ncm"},
    "IX": {"anexo": "IX", "titulo_oficial": "INSUMOS SUBMETIDOS À REDUÇÃO A ZERO DAS ALÍQUOTAS", "regime": "aliquota_zero",
           "reducao_percentual": "100", "fundamento": "LC 214/2025, Anexo IX", "tipo": "ncm"},
    "XVI": {"anexo": "XVI", "titulo_oficial": "LIMITE INFERIOR", "regime": "a_definir",
            "reducao_percentual": "", "fundamento": "LC 214/2025, Anexo XVI", "tipo": "ncm"},
}


def _it(anexo, ncm, linha="1 | Produto qualquer | x", situacao=""):
    return {"anexo": anexo, "ncm": ncm, "linha": linha, "situacao": situacao}


def _por_prefixo(r):
    return {x["ncm_prefixo"]: x for x in r["regras"]}


def test_descricao_vem_da_linha_de_tabela_sem_codigos():
    assert descricao_da_linha("12 | Bengala inteiriça, dobrável | 6602.00.00") == "Bengala inteiriça, dobrável"
    assert descricao_da_linha("1006.20 e 1006.30 e do código 1006.40.00 da NCM/SH") is None  # texto corrido
    assert descricao_da_linha("3 | | 9018.90.99") is None


def test_palavras_chave_sem_acento_e_sem_repeticao():
    assert palavras_chave("Leite fermentado, leite em pó") == "leite,fermentado"


def test_categoria_do_anexo_tira_o_trecho_do_regime():
    assert categoria_do_anexo("DISPOSITIVOS MÉDICOS SUBMETIDOS À REDUÇÃO DE 60% (SESSENTA)") == "Dispositivos médicos"


def test_regime_vem_do_anexo_e_anexo_a_definir_e_ignorado():
    r = gerar([_it("I", "1006.20"), _it("XVI", "2710.12")], ANEXOS)
    assert [(x["ncm_prefixo"], x["regime"], x["reducao_percentual"], x["validado"]) for x in r["regras"]] == \
        [("100620", "aliquota_zero", "100", "nao")]
    assert r["ignorados"] == {"XVI": 1}


def test_ncm_em_anexos_com_regimes_diferentes_nao_escolhe_regime():
    r = gerar([_it("I", "1006.20"), _it("IV", "1006.20")], ANEXOS)
    assert {(c["anexo"], c["regime"]) for c in r["conflitos"]} == {("I", "aliquota_zero"), ("IV", "reducao_60")}
    (regra,) = r["regras"]  # nenhum regime foi escolhido: a regra é 'a_confirmar', sem alíquota
    assert regra["regime"] == "a_confirmar"
    assert "Anexo I: aliquota_zero" in regra["observacao"] and "Anexo IV: reducao_60" in regra["observacao"]
    assert "Anexo I" in regra["fundamento"] and "Anexo IV" in regra["fundamento"]


def test_ncm_em_anexos_com_o_mesmo_regime_gera_uma_regra_citando_os_dois():
    r = gerar([_it("I", "1006.20"), _it("IX", "1006.20")], ANEXOS)
    assert len(r["regras"]) == 1 and r["conflitos"] == []
    assert r["regras"][0]["fundamento"] == "LC 214/2025, Anexo I; LC 214/2025, Anexo IX"


def test_repeticao_no_mesmo_anexo_gera_uma_regra_e_mantem_a_ressalva():
    r = gerar([_it("I", "1006.20"), _it("I", "1006.20", situacao="ressalva")], ANEXOS)
    assert len(r["regras"]) == 1 and r["regras"][0]["ressalva"]


def test_ressalva_da_lei_gera_aviso_e_item_sem_ressalva_nao():
    r = gerar([_it("I", "0306.1", situacao="ressalva"), _it("I", "1006.20")], ANEXOS)
    x = _por_prefixo(r)
    assert x["03061"]["ressalva"].startswith("O texto da lei traz exceção ou condição")
    assert x["100620"]["ressalva"] == ""


def test_excecao_com_pai_beneficiado_vira_regra_padrao_protegida():
    r = gerar([_it("I", "0306.1", situacao="ressalva"), _it("I", "0306.11", situacao="excecao")], ANEXOS)
    x = _por_prefixo(r)
    assert x["03061"]["regime"] == "aliquota_zero"
    assert (x["030611"]["regime"], x["030611"]["reducao_percentual"]) == ("padrao", "0")
    assert "EXCLUÍDO" in x["030611"]["ressalva"] and "exceção expressa" in x["030611"]["fundamento"]


def test_excecao_sem_pai_nao_vira_regra_mas_fica_para_revisao():
    r = gerar([_it("I", "0306.11", situacao="excecao")], ANEXOS)
    assert r["regras"] == [] and len(r["excecoes"]) == 1 and len(r["excecoes_sem_pai"]) == 1


def test_excecao_nao_sobrepoe_regra_especifica_de_outro_anexo():
    r = gerar([_it("I", "0306.1"), _it("I", "0306.11", situacao="excecao"), _it("IV", "0306.11")], ANEXOS)
    assert _por_prefixo(r)["030611"]["regime"] == "reducao_60"


def test_aninhados_com_regime_diferente():
    regras = [{"ncm_prefixo": "1006", "regime": "aliquota_zero", "reducao_percentual": "100"},
              {"ncm_prefixo": "100620", "regime": "reducao_60", "reducao_percentual": "60"},
              {"ncm_prefixo": "100630", "regime": "aliquota_zero", "reducao_percentual": "100"}]
    assert aninhados_com_regime_diferente(regras) == [("1006", "100620")]


def test_dados_reais_passam_na_validacao(monkeypatch):
    """Estrutura do dados/regras_ncm.csv real (o fixture autouse aponta para a base de teste)."""
    from agente_contabil import config, regras
    from validar_regras import validar
    real = Path(config.RAIZ) / "dados" / "regras_ncm.csv"
    if not real.exists():
        pytest.skip("dados/regras_ncm.csv ausente")
    monkeypatch.setattr(config, "ARQ_REGRAS", real)
    regras.carregar.cache_clear()
    assert validar() == []


def test_descricao_sem_restos_de_codigo():
    assert descricao_da_linha("1 | Arroz das subposições 1006.20 e 1006.30 e do código 1006.40.00 da NCM/SH") == "Arroz"
    assert descricao_da_linha("2 | Dentifrícios do código 3306.10.00 da NCM/SH") == "Dentifrícios"
    assert descricao_da_linha("3 | Sabões de toucador classificados no código 3401.11.90 da NCM/SH") == "Sabões de toucador"


def test_descricao_corta_exceto_que_so_lista_codigos():
    linha = "4 | Aparelhos de eletrodiagnóstico, exceto os produtos classificados nos códigos 9018.11.00, 9018.12.10 e 9018.19.20"
    assert descricao_da_linha(linha) == "Aparelhos de eletrodiagnóstico"


def test_descricao_mantem_exceto_que_descreve_o_produto():
    assert descricao_da_linha("5 | Peixes (exceto salmonídeos e bacalhaus) | 0302.31.00") == \
        "Peixes (exceto salmonídeos e bacalhaus)"


ANEXOS_REV = {**ANEXOS, "XIV": {"anexo": "XIV", "regime": "revogado", "reducao_percentual": "",
              "titulo_oficial": "(Revogado pela Lei Complementar nº 227, de 2026) MEDICAMENTOS A ZERO",
              "fundamento": "LC 214/2025, Anexo XIV", "tipo": "revogado"}}


def test_ncm_de_anexo_revogado_vira_a_confirmar_em_vez_de_padrao_presumido():
    rev = [_it("XIV", "3004.90.99", "7 | Medicamento X | 3004.90.99")]
    r = gerar([], ANEXOS_REV, rev)
    (regra,) = r["regras"]
    assert (regra["ncm_prefixo"], regra["regime"]) == ("30049099", "a_confirmar")
    assert "revogado" in regra["fundamento"] and "Anexo XIV" in regra["observacao"]
    assert "NÃO está na base" in regra["observacao"] and r["revogados_a_confirmar"] == 1


def test_ncm_revogado_que_um_anexo_vigente_trata_mantem_a_regra_vigente():
    r = gerar([_it("IV", "3004.90.99")], ANEXOS_REV, [_it("XIV", "3004.90.99")])
    assert [(x["regime"], x["fundamento"]) for x in r["regras"]] == [("reducao_60", "LC 214/2025, Anexo IV")]


def test_codigo_compartilhado_com_anexo_revogado_marca_outros_produtos_a_confirmar():
    r = gerar([_it("IV", "3004.90.99", "9 | Substitutos de enxerto ósseo | 3004.90.99")], ANEXOS_REV,
              [_it("XIV", "3004.90.99")])
    (regra,) = r["regras"]
    assert regra["regime"] == "reducao_60" and regra["outros_produtos"] == "a_confirmar"
    assert "Anexo XIV (revogado)" in regra["ressalva"] and r["compartilhados"] == 1


def test_medicamentos_viram_a_confirmar_citando_os_artigos_133_e_146():
    r = regras_medicamentos({"3004": "Medicamentos (exceto os produtos das posições 30.02...)"})
    assert [(x["ncm_prefixo"], x["regime"], x["validado"]) for x in r] == [("3003", "a_confirmar", "nao"), ("3004", "a_confirmar", "nao")]
    assert r[1]["descricao"].startswith("Medicamentos (exceto") and "arts. 133 e 146" in r[0]["fundamento"]
    for texto in ("revogado pela LC 227/2026", "60%", "Anvisa", "120 dias", "NÃO se define só pelo NCM"):
        assert texto in r[0]["observacao"]
    assert "alíquota zero" in r[0]["observacao"] and r[0]["reducao_percentual"] == "0"  # sem alíquota inventada


def test_regra_vigente_em_ncm_de_medicamento_vale_so_para_o_produto_descrito():
    regras = [{"ncm_prefixo": "30049099", "regime": "reducao_60", "outros_produtos": "", "ressalva": ""},
              {"ncm_prefixo": "30021221", "regime": "reducao_60", "outros_produtos": "", "ressalva": ""},
              {"ncm_prefixo": "3004", "regime": "a_confirmar", "outros_produtos": "", "ressalva": ""}]
    assert marcar_codigos_compartilhados_com_medicamentos(regras) == 1
    assert regras[0]["outros_produtos"] == "a_confirmar" and "arts. 133 e 146" in regras[0]["ressalva"]
    assert regras[1]["outros_produtos"] == "" and regras[2]["outros_produtos"] == ""  # outro capítulo / já a_confirmar
