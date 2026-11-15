from extrair_anexos_lc214 import (_Texto, anexos_revogados, extrair_linhas,
                                  linhas_simples, ocorrencias_anexos,
                                  titulos_anexos)


def _texto(html: str) -> str:
    p = _Texto()
    p.feed(html)
    return p.texto()


def test_texto_riscado_e_ignorado():
    t = _texto("<p>ANEXO I</p><p>1006.20 arroz <strike>0401.10 leite</strike> fim</p>")
    assert "arroz" in t and "fim" in t
    assert "leite" not in t and "0401.10" not in t


def test_riscado_com_tags_s_del_e_aninhadas():
    t = _texto("<p>a <s>b <del>c</del> d</s> e <del>f</del> g</p>")
    assert [x for x in t.split() if x] == ["a", "e", "g"]


def test_riscado_aninhado_do_mesmo_tipo_fecha_so_no_ultimo():
    t = _texto("<p><s>x<s>y</s>ainda riscado</s> visivel</p>")
    assert "ainda" not in t and "visivel" in t


def test_anexo_revogado_fica_fora_da_extracao():
    html = ("<p>ANEXO I</p><p>PRODUTOS A</p><p>1006.20 arroz</p>"
            "<p>ANEXO II</p><p>(Revogado pela Lei Complementar nº 227, de 2026)</p>"
            "<p>0401.10 leite</p>")
    texto = _texto(html)
    revogados = anexos_revogados(titulos_anexos(texto))
    assert revogados == ["II"]
    linhas = extrair_linhas(texto, frozenset(revogados))
    assert [(l["anexo"], l["ncm"]) for l in linhas] == [("I", "1006.20")]



def test_titulo_completo_junta_linhas_ate_a_tabela():
    html = ("<p>ANEXO IV</p><p>DISPOSITIVOS MÉDICOS SUBMETIDOS À REDUÇÃO DE 60%</p>"
            "<p>(SESSENTA POR CENTO) DAS ALÍQUOTAS</p>"
            "<table><tr><td>3004.90</td><td>remédio</td></tr></table>")
    info = titulos_anexos(_texto(html))["IV"]
    assert info["titulo"] == ("DISPOSITIVOS MÉDICOS SUBMETIDOS À REDUÇÃO DE 60% "
                              "(SESSENTA POR CENTO) DAS ALÍQUOTAS")


def test_titulo_para_no_primeiro_ncm_sem_tabela_e_ignora_ano():
    texto = "ANEXO V\nPRODUTOS DE 2025 PARA\nPESSOAS\n1006.20 arroz\nsobra"
    assert titulos_anexos(texto)["V"]["titulo"] == "PRODUTOS DE 2025 PARA PESSOAS"


def test_titulo_limitado_a_300_caracteres():
    texto = "ANEXO VI\n" + "\n".join(["PALAVRA " * 10] * 10) + "\n1006.20 arroz"
    assert len(titulos_anexos(texto)["VI"]["titulo"]) <= 300


def test_ocorrencias_duplicadas_mostram_titulo_ncms_e_exemplos():
    texto = ("ANEXO I\nTITULO ANTIGO\n1006.20 arroz\n"
             "ANEXO I\nTITULO NOVO\n0401.10 leite\n0402.10 leite em pó\n0403.10 iogurte\n")
    oc = ocorrencias_anexos(texto)
    assert [(o["titulo"], o["ncms"]) for o in oc] == [("TITULO ANTIGO", 1), ("TITULO NOVO", 3)]
    assert len(oc[1]["exemplos"]) == 2
    assert [o["chave"] for o in oc] == ["I", "I-2"]


TEXTO_DUPLO = ("ANEXO I\nPRODUTOS COM REDUÇÃO A ZERO DAS ALÍQUOTAS DO IBS E DA CBS\n1006.20 arroz\n"
               "ANEXO I\nAlíquotas e Partilha do Simples Nacional - Comércio (Vigência: 1º/1/2027)\n"
               "Para os anos-calendário 2027 e 2028\n4,00%\n"
               "ANEXO VII\nValores fixos do Microempreendedor Individual (MEI)\n"
               "Para o ano-calendário 2029\n")


def test_anexo_simples_mei_nao_gera_ncm_mesmo_com_numeracao_repetida():
    linhas = extrair_linhas(TEXTO_DUPLO)
    assert [(l["anexo"], l["ncm"]) for l in linhas] == [("I", "1006.20")]


def test_titulo_com_alíquotas_da_lc214_nao_e_tratado_como_simples():
    tipos = [o["tipo"] for o in ocorrencias_anexos(TEXTO_DUPLO)]
    assert tipos == ["lc214", "simples_mei", "simples_mei"]


def test_linhas_simples_guarda_o_conteudo_cru_para_revisao():
    linhas = linhas_simples(TEXTO_DUPLO)
    assert {l["anexo"] for l in linhas} == {"SN-I", "MEI-VII"}
    assert any(l["linha"] == "4,00%" for l in linhas)
    assert not any("arroz" in l["linha"] for l in linhas)


def test_mesma_numeracao_gera_chaves_unicas_por_contexto():
    chaves = [o["chave"] for o in ocorrencias_anexos(TEXTO_DUPLO)]
    assert chaves == ["I", "SN-I", "MEI-VII"]
    assert set(titulos_anexos(TEXTO_DUPLO)) == {"I", "SN-I", "MEI-VII"}


def test_titulo_repetido_no_mesmo_contexto_recebe_sufixo_em_vez_de_se_perder():
    texto = "ANEXO I\nPRODUTOS A\n1006.20 arroz\nANEXO I\nPRODUTOS B\n0401.10 leite\n"
    linhas = extrair_linhas(texto)
    assert [(l["anexo"], l["ncm"]) for l in linhas] == [("I", "1006.20"), ("I-2", "0401.10")]


def test_quebra_de_linha_no_codigo_fonte_nao_separa_celulas_da_mesma_linha():
    html = ("<table><tr><td>1\n.</td>\n<td>Arroz\npolido\n</td><td>\n1006.20</td></tr>"
            "<tr><td>2</td><td>Feijão</td><td>0713.33</td></tr></table>")
    linhas = [" ".join(l.split()) for l in _texto(html).splitlines() if l.strip() and "" not in l]
    assert linhas == ["1 . | Arroz polido | 1006.20", "2 | Feijão | 0713.33"]


def test_excecao_na_descricao_da_tabela_nao_exclui_o_ncm_da_coluna_ao_lado():
    html = ("<p>ANEXO I</p><p>ALIMENTOS SUBMETIDOS À REDUÇÃO A ZERO</p><table>"
            "<tr><td>1</td><td>Leite, exceto o fermentado</td><td>0401.10.10</td></tr>"
            "<tr><td>2</td><td>Crustáceos exceto o da subposição 0306.11</td><td>0306.1</td></tr></table>")
    s = {l["ncm"]: l["situacao"] for l in extrair_linhas(_texto(html))}
    assert s == {"0401.10.10": "ressalva", "0306.11": "excecao", "0306.1": "ressalva"}


def test_excecao_em_texto_corrido_continua_nas_linhas_seguintes():
    texto = ("ANEXO I\nALIMENTOS A ZERO\n0306.1 e 0306.3, exceto os produtos da subposição\n"
             "0306.11 e dos códigos 0306.15.00,\n0306.31.00.\n0401.10 leite\n")
    s = {l["ncm"]: l["situacao"] for l in extrair_linhas(texto)}
    assert s["0306.1"] == "ressalva" and s["0306.3"] == "ressalva"
    assert s["0306.11"] == s["0306.15.00"] == s["0306.31.00"] == "excecao"
    assert s["0401.10"] == ""  # a frase terminou: o item seguinte volta ao normal


def test_excecao_entre_parenteses_so_vale_ate_fechar_o_parentese():
    html = ("<p>ANEXO I</p><p>ALIMENTOS A ZERO</p><table>"
            "<tr><td>1</td><td>Carnes (exceto foie gras 0210.99), dos códigos 0201.10.00 e 0202.10.00</td></tr></table>")
    s = {l["ncm"]: l["situacao"] for l in extrair_linhas(_texto(html))}
    assert s["0210.99"] == "excecao"
    assert s["0201.10.00"] == s["0202.10.00"] == "ressalva"  # incluídos, mas com ressalva do 'exceto'
