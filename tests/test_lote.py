import csv

import pytest
from fastapi.testclient import TestClient

from agente_contabil.api import app
from agente_contabil.lote import (COLUNAS_SAIDA, LIMITE_ITENS, LIMITE_ITENS_API, STATUS, analisar_item, analisar_lote, detectar_colunas,
                                  gravar_saida, itens_da_planilha, ler_planilha, resumo)

ANO = 2026


def _status(descricao, ncm):
    return analisar_item(descricao, ncm, ANO)


def test_ncm_correto_de_produto_com_beneficio(tabela_ncm):
    r = _status("Arroz polido", "1006.30.21")
    assert r["status"] == "OK_COM_BENEFICIO" and r["regime"] == "aliquota_zero" and r["gravidade"] == STATUS["OK_COM_BENEFICIO"]
    assert r["compatibilidade"] == "alta" and "Polido ou brunido" in r["descricao_oficial_ncm"]
    assert r["regra_validada"] == "nao" and "validação do contador" in r["o_que_fazer"]


def test_erp_com_ncm_de_outro_produto_e_pego_e_sugere_o_certo(tabela_ncm):
    r = _status("Smartphone", "10063021")  # NCM de arroz num celular
    assert r["status"] == "NCM_NAO_CONFIRMADO" and "8517.13.00" in r["ncm_sugerido"]
    assert "Polido ou brunido" in r["descricao_oficial_ncm"] and "regime e CST errados" in r["o_que_fazer"]
    assert "diferença de nome" in r["o_que_fazer"]  # não afirma que o NCM está errado: o lojista compara


def test_ncm_que_nao_existe_na_tabela_oficial(tabela_ncm):
    r = _status("Celular", "8517.99.99")
    assert r["status"] == "NCM_INEXISTENTE" and "NÃO existe" in r["o_que_fazer"] and "8517.1" in r["ncm_sugerido"]


def test_zero_a_esquerda_perdido_no_excel(tabela_ncm):
    r = _status("Leite longa vida", "4011010")  # 0401.10.10 sem o zero
    assert r["status"] == "NCM_SEM_ZERO" and r["ncm_sugerido"] == "0401.10.10" and "zero à esquerda" in r["o_que_fazer"]
    assert _status("Qualquer", "1234567")["status"] == "NCM_INCOMPLETO"  # 7 dígitos que NÃO viram código com zero


def test_ncm_incompleto(tabela_ncm):
    assert _status("Celular", "8517")["status"] == "NCM_INCOMPLETO"
    assert "8 dígitos" in _status("Arroz", "100630")["o_que_fazer"]


def test_produto_sem_ncm_recebe_sugestoes_pela_descricao(tabela_ncm):
    r = _status("Smartphone", "")
    assert r["status"] == "SEM_NCM" and "8517.13.00" in r["ncm_sugerido"] and "valide" in r["o_que_fazer"]
    assert _status("xyzzy", "  ")["status"] == "SEM_NCM"


def test_regime_a_confirmar_por_conflito_e_por_codigo_incompleto_na_lei(tabela_ncm):
    conflito = _status("Preparações alimentícias", "2106.90.90")
    assert conflito["status"] == "REGIME_A_CONFIRMAR" and conflito["regime"] == "a_confirmar"
    assert conflito["aliquota_total_percentual"] == "indefinida"
    produto = _status("Bengala especial", "3926.90.99")  # regra "3926.9": vale só para o produto descrito
    assert produto["status"] == "REGIME_A_CONFIRMAR" and "o produto é exatamente o descrito" in produto["cenarios"]


def test_ncm_sem_beneficio_cadastrado_e_ok_com_presuncao(tabela_ncm):
    r = _status("Smartphone", "8517.13.00")  # a fixture tem 8517.13 como regime padrao
    assert r["status"] == "OK_SEM_BENEFICIO" and r["regime"] == "padrao" and r["aliquota_total_percentual"] == 1.0


def test_sem_a_tabela_oficial_avisa_e_nao_afirma_existencia():
    r = _status("Arroz", "10063021")  # tabela indisponível (padrão dos testes)
    assert "Tabela oficial da NCM indisponível" in r["avisos"] and r["compatibilidade"] == ""
    assert r["status"] in ("OK_COM_BENEFICIO", "CONFERIR")


def test_lote_vem_ordenado_com_os_problemas_primeiro_e_resumo(tabela_ncm):
    itens = [{"descricao": "Arroz polido", "ncm": "1006.30.21"},        # linha 1: ok
             {"descricao": "Celular", "ncm": "8517.99.99"},              # linha 2: inexistente
             {"descricao": "Smartphone", "ncm": "8517.13.00"},           # linha 3: ok sem benefício
             {"descricao": "Smartphone", "ncm": "10063021"},             # linha 4: não bate
             {"descricao": "Smartphone", "ncm": ""}]                     # linha 5: sem NCM
    res = analisar_lote(itens, ANO)
    assert [r["status"] for r in res] == ["NCM_INEXISTENTE", "NCM_NAO_CONFIRMADO", "SEM_NCM", "OK_SEM_BENEFICIO", "OK_COM_BENEFICIO"]
    assert [r["linha"] for r in res] == [2, 4, 5, 3, 1]   # a linha original é preservada
    s = resumo(res)
    assert s["total"] == 5 and s["com_problema"] == 2 and s["por_status"]["SEM_NCM"] == 1
    assert list(s["por_status"]) == sorted(s["por_status"], key=STATUS.get)


def test_deteccao_de_colunas_de_erp():
    c = detectar_colunas(["Código", "Descrição do Produto", "NCM/SH", "Preço"])
    assert (c["descricao"], c["ncm"], c["codigo"]) == ("Descrição do Produto", "NCM/SH", "Código")
    assert detectar_colunas(["SKU", "Produto", "Class. Fiscal"])["ncm"] == "Class. Fiscal"
    assert detectar_colunas(["a", "b", "c"], descricao="b", ncm="c")["ncm"] == "c"
    with pytest.raises(ValueError, match="não existe"):
        detectar_colunas(["a", "b"], descricao="zzz", ncm="b")
    with pytest.raises(ValueError, match="Não achei as colunas"):
        detectar_colunas(["preço", "estoque"])


def test_leitura_de_csv_do_excel_latin1_ponto_e_virgula_e_utf8_virgula(tmp_path):
    a = tmp_path / "a.csv"
    a.write_bytes("Código;Descrição;NCM\n1;Pão francês;19059090\n2;Açúcar;17019900\n".encode("latin-1"))
    cab, linhas = ler_planilha(a)
    assert cab == ["Código", "Descrição", "NCM"] and linhas[0]["Descrição"] == "Pão francês"
    b = tmp_path / "b.csv"
    b.write_text("﻿codigo,descricao,ncm\n1,Arroz,10063021\n", encoding="utf-8")
    assert itens_da_planilha(b) == [{"descricao": "Arroz", "ncm": "10063021", "codigo": "1"}]


def test_saida_abre_no_excel_e_tem_todas_as_colunas(tabela_ncm, tmp_path):
    res = analisar_lote([{"descricao": "Arroz polido", "ncm": "1006.30.21", "codigo": "A1"}], ANO)
    destino = tmp_path / "out.csv"
    gravar_saida(res, destino)
    assert destino.read_bytes().startswith(b"\xef\xbb\xbf")
    with open(destino, encoding="utf-8-sig", newline="") as f:
        linhas = list(csv.DictReader(f, delimiter=";"))
    assert list(linhas[0]) == COLUNAS_SAIDA and linhas[0]["codigo"] == "A1"


def test_limite_de_itens():
    with pytest.raises(ValueError, match="limite"):
        analisar_lote([{"descricao": "x", "ncm": ""}] * (LIMITE_ITENS + 1), ANO)


def test_api_lote(tabela_ncm):
    c = TestClient(app)
    r = c.post("/lote", json={"ano": ANO, "itens": [{"descricao": "Celular", "ncm": "8517.99.99"},
                                                    {"descricao": "Arroz polido", "ncm": "1006.30.21"}]})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["resumo"]["com_problema"] == 1 and corpo["itens"][0]["status"] == "NCM_INEXISTENTE"
    assert c.post("/lote", json={"itens": [{"descricao": "x"}] * (LIMITE_ITENS_API + 1)}).status_code == 400
    assert c.post("/lote", json={}).status_code == 422


def test_colunas_de_erp_variadas_e_codigo_de_barras_nao_vira_codigo_do_produto():
    c = detectar_colunas(["Cód. Produto", "Código de Barras", "Descrição", "Código NCM", "Preço"])
    assert (c["descricao"], c["ncm"], c["codigo"]) == ("Descrição", "Código NCM", "Cód. Produto")
    assert detectar_colunas(["REF", "NOME", "NCM"]) == {"descricao": "NOME", "ncm": "NCM", "codigo": "REF"}
    assert detectar_colunas(["EAN", "Descrição", "NCM"])["codigo"] is None


def test_descricao_de_erp_com_tamanho_marca_e_enchimento_nao_gera_falso_alarme(tabela_ncm):
    """O caso real que gerava falso alarme: NCM correto, descrição com tamanho/tipo/marca."""
    for descricao in ("Arroz tipo 1 polido 5kg", "ARROZ POLIDO TRADICIONAL PACOTE 1KG", "Arroz Camil polido 5 kg"):
        r = _status(descricao, "1006.30.21")
        assert r["status"] == "OK_COM_BENEFICIO", (descricao, r["status"], r["compatibilidade"])


def test_marca_desconhecida_nao_derruba_mas_produto_errado_continua_sendo_pego(tabela_ncm):
    assert _status("Smartphone Galaxy A15 128GB", "8517.13.00")["status"] == "OK_SEM_BENEFICIO"
    assert _status("Smartphone Galaxy A15 128GB", "1006.30.21")["status"] == "NCM_NAO_CONFIRMADO"


def test_descricao_para_busca_tira_so_o_enchimento():
    from agente_contabil.lote import descricao_para_busca
    assert descricao_para_busca("Arroz tipo 1 tradicional 5kg") == "Arroz 1 5kg"
    assert descricao_para_busca("Leite integral") == "Leite integral"


def test_substantivo_principal_que_casa_garante_pelo_menos_media_e_o_que_nao_casa_continua_baixo(tabela_ncm):
    """'Arroz telefone': 'telefone' é palavra conhecida e sobra, mas o substantivo (arroz) casa -> confere em parte.
    'Telefone arroz': o substantivo (telefone) não casa com o NCM de arroz -> não confirmado."""
    assert _status("Arroz telefone", "1006.30.21")["status"] == "CONFERIR"
    assert _status("Telefone arroz", "1006.30.21")["status"] == "NCM_NAO_CONFIRMADO"


def test_ferramenta_conferir_produtos_para_lista_pequena(tabela_ncm):
    import json
    from agente_contabil.ferramentas import FERRAMENTAS, executar
    ferramenta = next(f for f in FERRAMENTAS if f["name"] == "conferir_produtos")
    assert ferramenta["input_schema"]["properties"]["produtos"]["maxItems"] == 30
    saida, erro = executar("conferir_produtos", {"ano": ANO, "produtos": [
        {"descricao": "Arroz polido", "ncm": "1006.30.21"}, {"descricao": "Celular", "ncm": "8517.99.99"}]})
    corpo = json.loads(saida)
    assert not erro and corpo["resumo"]["com_problema"] == 1
    assert [p["status"] for p in corpo["produtos"]] == ["NCM_INEXISTENTE", "OK_COM_BENEFICIO"]  # problemas primeiro
    _, erro = executar("conferir_produtos", {"ano": ANO, "produtos": [{"descricao": "x", "ncm": ""}] * 31})
    assert erro  # passou do limite do chat: orienta usar o lote
