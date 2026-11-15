from agente_contabil.busca import buscar_produto
from agente_contabil.normalizacao import lista_tokens, radical
from agente_contabil.servicos import buscar_servico
from agente_contabil.texto_busca import ranquear, sinonimos


def _ncms(texto):
    return [r["ncm_prefixo"] for r in buscar_produto(texto)]


def test_radical_trata_plural():
    assert [radical(p) for p in ("carnes", "oleos", "saboes", "flores", "paes", "aves", "gas", "queijos")] == \
        ["carne", "oleo", "sabao", "flor", "pao", "ave", "gas", "queijo"]
    assert lista_tokens("Óleos de soja, de milho") == ["oleo", "soja", "milho"]


def test_singular_acha_plural_da_lei():
    r = buscar_produto("carne")[0]
    assert r["ncm_prefixo"] == "0201" and r["confianca"] == "alta"  # a lei diz "Carnes bovina..."


def test_palavra_rara_e_cobertura_afastam_o_item_parcial():
    # "oleo de soja": o babaçu cobre só "oleo" e sai quando alguém cobre tudo
    assert _ncms("oleo de soja") == ["150790"]
    # "oleo" sozinho: os dois são candidatos legítimos
    assert set(_ncms("oleo")) == {"150790", "151321"}


def test_citacao_solta_nao_empata_com_o_substantivo_principal():
    # "carne" aparece no fim da descrição do alho em pó, mas é o 1º termo das Carnes
    assert _ncms("carne")[:2] == ["0201", "071290"]


def test_sinonimo_do_arquivo_acha_o_termo_da_lei_e_corta_o_falso_candidato():
    r = buscar_produto("carne de frango")
    assert [x["ncm_prefixo"] for x in r] == ["0201"]          # alho em pó (só "carne") não aparece
    assert r[0]["confianca"] == "alta" and r[0]["palavras_sem_correspondencia"] == []
    assert "ave" in sinonimos()["frango"]


def test_palavra_que_nenhum_item_conhece_e_ignorada_com_transparencia(monkeypatch):
    from agente_contabil import config
    monkeypatch.setattr(config, "ARQ_SINONIMOS", config.RAIZ / "nao_existe.csv")
    sinonimos.cache_clear()
    r = buscar_produto("carne de frango")
    assert r[0]["ncm_prefixo"] == "0201"
    # nenhum item cobre "frango": ele é descartado, a confiança nunca fica "alta" e o usuário é avisado
    assert r[0]["confianca"] == "media" and r[0]["palavras_ignoradas"] == ["frango"]


def test_relaxamento_descarta_modificadores_do_fim_e_nunca_da_confianca_alta():
    r = buscar_produto("leite achocolatado extra")
    assert r[0]["descricao"].startswith("Leite") and r[0]["palavras_ignoradas"] == ["achocolatado", "extra"]
    assert r[0]["confianca"] == "media"
    assert buscar_produto("achocolatado leite")[0]["palavras_ignoradas"] == ["achocolatado"]  # só descarta o necessário
    assert buscar_produto("leite")[0]["palavras_ignoradas"] == []                              # cobre tudo: não relaxa


def test_itens_com_mesma_descricao_viram_um_resultado_com_os_outros_ncms():
    r = buscar_produto("leite")
    assert len([x for x in r if x["descricao"].startswith("Leite, em conformidade")]) == 1
    leite = next(x for x in r if x["descricao"].startswith("Leite, em conformidade"))
    assert leite["quantidade_ncms"] == 2 and leite["outros_ncms"] == ["04011090"]


def test_so_palavras_vazias_ou_sem_relacao_nao_retorna_nada():
    assert buscar_produto("de para com") == [] and buscar_produto("xyzzy") == []


def test_servico_usa_o_mesmo_motor_com_plural_e_generica():
    assert [r.item for r in buscar_servico("ensinos medios")] == ["II-3"]
    assert buscar_servico("serviço de consultoria") == []      # "serviço" é genérica


def test_ranquear_vazio():
    assert ranquear("", [("Arroz", "")]) == ([], [])


def test_palavra_so_citada_no_fim_da_descricao_nao_tem_confianca_alta():
    por_ncm = {r["ncm_prefixo"]: r["confianca"] for r in buscar_produto("carne")}
    assert por_ncm["0201"] == "alta"
    assert por_ncm["071290"] == "media"  # alho em pó: "carne" só aparece no fim ("conservação de carne")


def test_sinonimos_do_projeto_nao_incluem_equivalencias_perigosas():
    """'remedio' -> 'medicamento' casava vacina veterinária: sinônimo só entra se for equivalência estrita."""
    from agente_contabil import config
    import csv
    with open(config.RAIZ / "dados" / "sinonimos.csv", encoding="utf-8", newline="") as f:
        termos = {l["termo"] for l in csv.DictReader(f, delimiter=";")}
    assert "remedio" not in termos and "celular" not in termos


def test_tema_com_lacuna_conhecida_gera_aviso_da_busca():
    from agente_contabil.ferramentas import _resposta_busca
    from agente_contabil.texto_busca import avisos_da_consulta
    assert avisos_da_consulta("remédio para dor") == [] and avisos_da_consulta("medicamentos") != []
    r = _resposta_busca("medicamentos")
    assert any("AVISO DE TESTE" in a for a in r["avisos"])


def test_resposta_da_ferramenta_sem_candidato_ou_com_palavras_ignoradas_manda_nao_afirmar():
    from agente_contabil.ferramentas import _resposta_busca, executar
    r = _resposta_busca("xyzzy")
    assert r["candidatos"] == [] and any("identificar_ncm" in a and "padrão" in a for a in r["avisos"])
    r = _resposta_busca("leite achocolatado")
    assert r["candidatos"] and any("IGNOREI as palavras achocolatado" in a for a in r["avisos"])
    saida, erro = executar("buscar_produto", {"texto": "leite"})
    assert not erro and "candidatos" in saida