import json

from agente_contabil.ferramentas import FERRAMENTAS, executar
from agente_contabil.servicos import buscar_servico, consultar_servico
from agente_contabil.simples import consultar_simples
from gerar_regras_servicos import linhas_do_anexo, nbs_da_celula
from gerar_simples import gerar as gerar_simples

ANEXO_II = {"anexo": "II", "regime": "reducao_60", "reducao_percentual": "60", "fundamento": "LC 214/2025, Anexo II"}


# ---------- serviços
def test_servico_por_texto_traz_regime_aliquota_e_fundamento():
    r = consultar_servico("ensino médio", 2026)
    item = r["encontrados"][0]
    assert item["item"] == "II-3" and item["regime"] == "reducao_60"
    assert item["aliquotas_percentual"]["total"] == 0.4 and item["fundamento"].startswith("LC 214/2025, Anexo II")
    assert r["regime_presumido_se_nao_encontrado"] is None
    assert any("exatamente o descrito" in a for a in r["avisos"])


def test_servico_por_codigo_nbs_casa_por_prefixo_nos_dois_sentidos():
    assert [r.item for r in buscar_servico("1.2201.30.00")] == ["II-3"]   # código completo
    assert [r.item for r in buscar_servico("1.2601.10.00")] == ["III-4"]  # a lei cita só o prefixo 12601
    assert [r.item for r in buscar_servico("1.2201")] == ["II-3"]         # consulta mais curta que o código


def test_servico_fora_da_lista_nao_e_declarado_isento_e_recebe_presuncao_com_aviso():
    r = consultar_servico("consultoria de marketing", 2026)
    assert r["encontrados"] == [] and r["regime_presumido_se_nao_encontrado"] == "padrao"
    assert r["aliquotas_presumidas_percentual"]["total"] == 1.0
    assert any("NÃO consta dos anexos de serviços" in a for a in r["avisos"])


def test_servico_sem_nbs_na_lei_avisa():
    item = consultar_servico("ensino infantil", 2026)["encontrados"][0]
    assert any("NBS não identificado" in a for a in item["avisos"])


def test_servico_entradas_invalidas():
    assert "erro" in consultar_servico("", 2026)
    assert "erro" in consultar_servico("ensino", 1999)


def test_ferramentas_expostas_e_executaveis():
    assert {"consultar_servico", "consultar_simples", "consultar_ncm", "buscar_produto"} <= {f["name"] for f in FERRAMENTAS}
    saida, erro = executar("consultar_servico", {"texto": "ensino médio", "ano": 2026})
    assert not erro and json.loads(saida)["encontrados"][0]["item"] == "II-3"
    _, erro = executar("consultar_simples", {"anexo": "ZZ"})
    assert erro


def test_nbs_da_celula_e_linhas_do_anexo():
    assert nbs_da_celula("1.2201.30.00 e 1.2202") == ["122013000", "12202"]
    assert nbs_da_celula("1.2201.30.00") == ["122013000"]
    assert nbs_da_celula("sem código") == []
    corpo = ["ITEM | DESCRIÇÃO | NBS", "1 | Ensino Infantil | ", "2 | Ensino Fundamental | 1.2201.20.00"]
    regras = linhas_do_anexo(corpo, ANEXO_II)
    assert [(r["item"], r["nbs"], r["validado"]) for r in regras] == [("II-1", "", "nao"), ("II-2", "122012000", "nao")]
    assert "NBS não identificado" in regras[0]["observacao"] and regras[1]["observacao"] == ""


# ---------- Simples / MEI
def test_simples_lista_anexos_e_avisa_que_nao_interpreta():
    r = consultar_simples("")
    assert set(r["anexos_disponiveis"]) == {"SN-I", "MEI-VII"}
    assert any("SEM interpretação" in a for a in r["avisos"])


def test_simples_anexo_traz_secoes_por_periodo_com_cabecalhos():
    r = consultar_simples("I")
    assert r["anexo"] == "SN-I"
    assert [s["secao"] for s in r["secoes"]] == ["Para os anos-calendário 2027 e 2028", "A partir do ano-calendário 2029"]
    primeira = r["secoes"][0]["linhas"]
    assert primeira[0] == {"tipo": "cabecalho", "celulas": ["Faixa", "Alíquota"]}
    assert primeira[1] == {"tipo": "faixa", "celulas": ["1ª Faixa", "4,00%"]}
    assert r["secoes"][1]["linhas"][0]["celulas"] == ["1ª Faixa", "5,00%"]  # outro período, outro valor


def test_simples_aceita_variacoes_de_nome_e_rejeita_desconhecido():
    assert consultar_simples("sn-i")["anexo"] == "SN-I"
    assert consultar_simples("mei")["anexo"] == "MEI-VII"
    assert "erro" in consultar_simples("IX")


def test_gerar_simples_classifica_linhas_e_secoes():
    texto = ("ANEXO I\nAlíquotas e Partilha do Simples Nacional - Comércio (Vigência: 1º/1/2027)\n"
             "Para os anos-calendário 2027 e 2028\nFaixa | Alíquota\n1ª Faixa | 4,00%\n"
             "(1) Nota longa explicando uma regra da tabela que passa de noventa caracteres para não ser tomada por título de seção.\n"
             "A partir do ano-calendário 2029\n1ª Faixa | 5,00%\n")
    linhas = gerar_simples(texto)
    assert [(l["secao"][:7], l["tipo"]) for l in linhas] == [
        ("Para os", "cabecalho"), ("Para os", "faixa"), ("Para os", "nota"), ("A parti", "faixa")]
    assert linhas[0]["anexo"] == "SN-I" and all(l["validado"] == "nao" for l in linhas)
    assert json.loads(linhas[1]["celulas"]) == ["1ª Faixa", "4,00%"]


def test_palavras_vazias_nao_casam_servicos_nem_produtos():
    from agente_contabil.busca import buscar_produto
    assert buscar_servico("serviços de contabilidade") == []        # "serviços" e "de" não identificam nada
    assert [r.item for r in buscar_servico("pronto socorro")] == ["III-4"]
    assert buscar_produto("de para") == []                           # só palavras vazias


def test_gerar_simples_nao_repete_o_titulo_como_nota():
    texto = ("ANEXO I\nAlíquotas e Partilha do Simples Nacional - Comércio\n(Vigência: 1º/1/2027 a 31/12/2028)\n"
             "Para os anos-calendário 2027 e 2028\n1ª Faixa | 4,00%\n")
    assert [l["tipo"] for l in gerar_simples(texto)] == ["faixa"]


def test_cabecalho_com_digitos_continua_cabecalho_e_valor_e_linha():
    from gerar_simples import _tipo
    assert _tipo(["Receita Bruta em 12 Meses (em R$)", "Alíquota", "Valor a Deduzir (em R$)"]) == "cabecalho"
    assert _tipo(["Comércio", "R$ 71,60"]) == "linha"
    assert _tipo(["2ª Faixa", "De 180.000,01 a 360.000,00", "7,30%"]) == "faixa"
