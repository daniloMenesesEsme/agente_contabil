from verificar_artigos_lei import checar, contar_riscado_css, extrair_artigo, trecho

TEXTO = ("Art. 145. Texto anterior.\nArt. 146. Ficam reduzidas a zero as alíquotas de soros e vacinas, conforme "
         "lista a cada 120 dias, com registro na Anvisa.\nParágrafo único. Vale para o SUS.\n"
         "Art. 147. Outro artigo sobre diabetes.\n")


def test_extrai_so_o_artigo_pedido():
    a = extrair_artigo(TEXTO, 146)
    assert "soros" in a and "sus" in a and "diabetes" not in a and "texto anterior" not in a
    assert extrair_artigo(TEXTO, 999) is None


def test_checar_diz_quais_termos_aparecem():
    r = checar(extrair_artigo(TEXTO, 146), ["soro", "vacina", "diabet", "120"])
    assert r == {"soro": True, "vacina": True, "diabet": False, "120": True}
    assert checar(None, ["x"]) is None


def test_trecho_e_contagem_de_riscado():
    assert "soros" in trecho(extrair_artigo(TEXTO, 146), "soros") and trecho("abc", "z") == ""
    n = contar_riscado_css('<span style="text-decoration:line-through">x</span><STRIKE>y</STRIKE><s>z</s>')
    assert n["line-through"] == 1 and n["<strike>"] == 1 and n["<s>"] == 1 and n["text-decoration (qualquer)"] == 1
