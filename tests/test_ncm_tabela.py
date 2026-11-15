from agente_contabil.calculo import consultar
from agente_contabil.ferramentas import FERRAMENTAS, executar
from agente_contabil.ncm_tabela import descricao_oficial, disponivel, identificar_ncm, verificar_ncm
from importar_ncm import limpar, montar


def test_sem_tabela_instalada_nada_quebra_e_nao_inventa_aviso():
    assert not disponivel() and descricao_oficial("85171300") is None
    r = consultar("85171300", 2026)
    assert r["ncm_oficial"] is None and not any("NÃO CONSTA" in a for a in r["avisos"])
    assert "erro" in verificar_ncm("85171300", "celular")


def test_descricao_oficial_do_ncm_completo_e_do_prefixo(tabela_ncm):
    o = descricao_oficial("8517.13.00")
    assert o["existe"] and o["nivel"] == 8 and "Telefones inteligentes (smartphones)" in o["descricao_completa"]
    assert "Vigente em 01/01/2026" in o["tabela"]
    assert descricao_oficial("8517")["existe"] and descricao_oficial("8517")["nivel"] == 4


def test_consultar_mostra_o_que_o_ncm_e_e_avisa_quando_nao_existe(tabela_ncm):
    r = consultar("85171300", 2026)
    assert r["ncm_oficial"]["existe"] and "smartphones" in r["ncm_oficial"]["descricao_completa"]
    errado = consultar("85179999", 2026)  # NCM que o ERP trouxe e não existe
    assert errado["ncm_oficial"]["existe"] is False
    assert errado["avisos"][0].startswith("NCM NÃO CONSTA da tabela oficial vigente")


def _ncms(texto):
    return [c["ncm"] for g in identificar_ncm(texto)["grupos"] for c in g["candidatos"]]


def test_identificar_ncm_acha_o_produto_pela_descricao_oficial(tabela_ncm):
    assert _ncms("smartphone")[0] == "8517.13.00"
    cel = _ncms("celular")  # o texto oficial do cabeçalho diz "redes celulares": sem sinônimo
    assert {"8517.12.00", "8517.13.00"} <= set(cel)


def test_identificar_agrupa_por_posicao(tabela_ncm):
    r = identificar_ncm("celular")
    (g,) = [g for g in r["grupos"] if g["posicao"] == "8517"]
    assert g["ncms_que_casam"] >= 2 and "telefônicos" in g["descricao_da_posicao"]
    assert r["ambigua"] is False and any("busca é por palavras" in a for a in r["avisos"])


def test_identificar_diz_se_ha_regra_de_beneficio(tabela_ncm):
    arroz = identificar_ncm("arroz polido")["grupos"][0]["candidatos"][0]
    assert arroz["ncm"] == "1006.30.21" and arroz["regra_cadastrada"]["regime"] == "aliquota_zero"
    sem_regra = next(c for g in identificar_ncm("smartphone")["grupos"] for c in g["candidatos"]
                     if c["ncm"] == "8517.13.00")
    assert sem_regra["regra_cadastrada"]["regime"] == "padrao"  # a fixture de teste tem 8517.13 como padrão
    carro = identificar_ncm("automovel de passageiros")["grupos"][0]["candidatos"][0]
    assert carro["ncm"] == "8703.22.10" and carro["regra_cadastrada"] is None


def test_regra_de_codigo_incompleto_nao_aparece_como_beneficio_firme(tabela_ncm):
    # a fixture tem a regra "3926.9" (7 dígitos? não: 5) -> usamos o NCM 3926.90 só em regras; aqui checamos o resumo
    from agente_contabil.ncm_tabela import _regra_resumida
    r = _regra_resumida("39269099")
    assert r["regime"] == "a_confirmar" and r["se_for_exatamente_o_produto_da_regra"] == "reducao_60"
    assert "só para o produto descrito" in r["aviso"]
    assert _regra_resumida("10063021")["regime"] == "aliquota_zero" and "aviso" not in _regra_resumida("10063021")


def test_palavra_que_cai_em_familias_diferentes_e_marcada_ambigua(tabela_ncm, monkeypatch):
    from agente_contabil import config, ncm_tabela
    import csv, tempfile, pathlib
    linhas = [("0101.10.00", "Terapia celular", "Produtos > Terapia celular"),
              ("4418.92.00", "Painéis celulares de madeira", "Madeira > Painéis celulares de madeira"),
              ("8517.12.00", "Telefones para redes celulares", "Telefones > Telefones para redes celulares"),
              ("8517.13.00", "Outros telefones celulares", "Telefones > Outros telefones celulares")]
    arq = pathlib.Path(tempfile.mkdtemp()) / "ncm.csv"
    with open(arq, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";"); w.writerow(["codigo", "nivel", "descricao", "completa"])
        for c, d, comp in linhas:
            w.writerow([c, 8, d, comp])
    monkeypatch.setattr(config, "ARQ_NCM", arq)
    ncm_tabela.carregar.cache_clear(); ncm_tabela._indice.cache_clear()
    r = identificar_ncm("celular")
    assert r["ambigua"] is True and any(a.startswith("AMBÍGUO") for a in r["avisos"])


def test_busca_sem_resultado_orienta_a_reformular_com_termos_oficiais(tabela_ncm):
    r = identificar_ncm("refrigerante de cola")
    assert r["grupos"] == [] and any("reformule com termos oficiais" in a for a in r["avisos"])


def test_outros_nao_vira_o_assunto_da_busca(tabela_ncm):
    assert "8517.18.00" not in _ncms("outros")


def test_verificar_ncm_bate_com_o_produto(tabela_ncm):
    r = verificar_ncm("8517.13.00", "smartphone")
    assert r["compatibilidade"] == "alta" and r["candidatos_alternativos"] == []


def test_verificar_ncm_de_erp_errado_avisa_e_sugere_alternativas(tabela_ncm):
    r = verificar_ncm("1006.30.21", "smartphone")   # ERP com NCM de arroz para um celular
    assert r["compatibilidade"] == "baixa"
    assert r["candidatos_alternativos"][0]["ncm"] == "8517.13.00"
    assert "pontos" not in r["candidatos_alternativos"][0]
    assert any("NÃO bate claramente" in a for a in r["avisos"])


def test_verificar_ncm_inexistente_e_prefixo(tabela_ncm):
    r = verificar_ncm("8517.99.99", "celular")
    assert r["compatibilidade"] == "indeterminada" and r["candidatos_alternativos"]
    assert any("NÃO CONSTA" in a for a in r["avisos"])
    assert verificar_ncm("8517", "celular")["compatibilidade"] == "nao_avaliada"
    assert "erro" in verificar_ncm("8517.13.00", " ")


def test_ferramentas_de_ncm_oficial_expostas(tabela_ncm):
    assert {"identificar_ncm", "verificar_ncm"} <= {f["name"] for f in FERRAMENTAS}
    saida, erro = executar("identificar_ncm", {"texto": "arroz polido"})
    assert not erro and "1006.30.21" in saida and '"grupos"' in saida
    saida, erro = executar("verificar_ncm", {"ncm": "1006.30.21", "produto": "smartphone"})
    assert not erro and "baixa" in saida


def test_importador_monta_texto_completo_sem_capitulo_e_limpa_html():
    itens = [{"Codigo": "10", "Descricao": "Cereais.", "Data_Fim": "31/12/9999"},
             {"Codigo": "10.06", "Descricao": "Arroz.", "Data_Fim": "31/12/9999"},
             {"Codigo": "1006.3", "Descricao": "- Arroz <i>semibranqueado</i>:", "Data_Fim": "31/12/9999"},
             {"Codigo": "1006.30.21", "Descricao": "- - Polido&nbsp;ou brunido", "Data_Fim": "31/12/9999"},
             {"Codigo": "9999.99.99", "Descricao": "Revogado", "Data_Fim": "31/12/2020"}]
    linhas = {l["codigo"]: l for l in montar(itens)}
    assert linhas["1006.30.21"]["completa"] == "Arroz > Arroz semibranqueado > Polido ou brunido"
    assert linhas["10"]["completa"] == "Cereais" and "9999.99.99" not in linhas
    assert limpar("- - <i>X</i> &amp; Y:") == "X & Y"


def test_sinonimo_mais_especifico_desempata_e_aparece_na_transparencia(monkeypatch):
    """frango = aves (peru também é ave) = Gallus: o item que casa por 'gallus' vale mais que o que casa por 'ave'."""
    import csv, pathlib, tempfile
    from agente_contabil import config, ncm_tabela
    linhas = [("0207.27.00", "Carnes de aves > De peruas e de perus > Pedaços congelados"),
              ("0207.14.00", "Carnes de aves > De aves da espécie Gallus domesticus > Pedaços congelados")]
    arq = pathlib.Path(tempfile.mkdtemp()) / "ncm.csv"
    with open(arq, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";"); w.writerow(["codigo", "nivel", "descricao", "completa"])
        for c, comp in linhas:
            w.writerow([c, 8, comp.split(" > ")[-1], comp])
    monkeypatch.setattr(config, "ARQ_NCM", arq)
    ncm_tabela.carregar.cache_clear(); ncm_tabela._indice.cache_clear()
    primeiro = identificar_ncm("frango congelado")["grupos"][0]["candidatos"][0]
    assert primeiro["ncm"] == "0207.14.00" and primeiro["sinonimos_usados"] == ["frango→gallus"]
