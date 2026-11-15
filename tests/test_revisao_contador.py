import csv

from aplicar_revisao import aplicar
from gerar_planilha_revisao import COLUNAS, categoria_regra, linhas_revisao


def _r(prefixo, regime="reducao_60", fundamento="LC 214/2025, Anexo IV", ressalva="", outros="", obs="", validado="nao"):
    return {"ncm_prefixo": prefixo, "descricao": "x", "regime": regime, "reducao_percentual": "60",
            "fundamento": fundamento, "ressalva": ressalva, "outros_produtos": outros, "observacao": obs,
            "texto_lei": "t", "validado": validado}


def test_categorias_de_risco_das_regras():
    assert categoria_regra(_r("30049099", "a_confirmar", "LC 214/2025, Anexo XIV (revogado)"))[:2] == (1, "regime_a_confirmar_anexo_revogado")
    assert categoria_regra(_r("21069090", "a_confirmar"))[:2] == (1, "regime_a_confirmar_conflito_entre_anexos")
    assert categoria_regra(_r("30049099", outros="a_confirmar"))[:2] == (2, "ncm_dividido_com_anexo_revogado")
    assert categoria_regra(_r("85171"))[:2] == (2, "codigo_incompleto_na_lei")
    assert categoria_regra(_r("90181210", "padrao", "LC 214/2025, Anexo XII (exceção expressa)"))[:2] == (3, "excecao_expressa_padrao")
    assert categoria_regra(_r("10063021", ressalva="exceto"))[:2] == (4, "ressalva_da_lei")
    assert categoria_regra(_r("10063021"))[:2] == (5, "regra_sem_alerta")
    assert categoria_regra(_r("0306", "padrao"))[:2] == (5, "regra_sem_alerta")  # padrão de 4 dígitos não é "incompleto"


def test_planilha_ordena_por_risco_e_traz_o_que_conferir():
    anexos = [{"anexo": "XIV", "tipo": "revogado", "regime": "revogado", "titulo_oficial": "(Revogado...)", "fundamento": "f"},
              {"anexo": "XVI", "tipo": "ncm", "regime": "a_definir", "titulo_oficial": "LIMITE", "fundamento": "f"}]
    servicos = [{"item": "II-1", "descricao": "Ensino", "nbs": "", "regime": "reducao_60", "reducao_percentual": "60",
                 "fundamento": "f", "texto_lei": "t"}]
    simples = [{"anexo": "SN-I", "titulo": "Simples", "secao": "2027", "fundamento": "f"}]
    param = {"anos": {"2027": {"cbs": None, "ibs_uf": 0.05, "ibs_mun": 0.05, "fonte": "LC"}, "2026": {"cbs": 0.9, "ibs_uf": 0.1, "ibs_mun": 0.0}}}
    excecoes = [{"anexo": "I", "ncm": "0306.11", "linha": "exceto 0306.11"}, {"anexo": "I", "ncm": "1006.20", "linha": "x"}]
    regras = [_r("10063021"), _r("21069090", "a_confirmar"), _r("100620")]
    linhas = linhas_revisao(regras, servicos, anexos, simples, [{"termo": "frango", "equivalentes": "ave", "observacao": ""}],
                            [{"termo": "medicamento", "aviso": "a"}], param, excecoes)
    prioridades = [l["prioridade"] for l in linhas]
    assert prioridades == sorted(prioridades) and linhas[0]["prioridade"] == 1
    por = {(l["tipo_dado"], l["chave"]): l for l in linhas}
    assert ("parametro", "2027") in por and ("parametro", "2026") not in por        # só ano com valor nulo
    assert ("excecao", "0306.11") in por and ("excecao", "1006.20") not in por      # 100620 já tem regra
    assert por[("servico", "II-1")]["categoria"] == "servico_sem_codigo_nbs"
    assert all(l["o_que_conferir"] for l in linhas if l["tipo_dado"] != "regra_ncm" or l["prioridade"] < 5)
    assert all(set(l) == set(COLUNAS) and l["decisao"] == "" for l in linhas)


def _base():
    regras = [_r("10063021", "aliquota_zero"), _r("21069090", "a_confirmar"), _r("85171"), _r("99999999")]
    for r in regras:
        r.update({"reducao_percentual": "60"})
    return {"regra_ncm": regras, "servico": [{"item": "II-1", "regime": "reducao_60", "reducao_percentual": "60",
                                              "validado": "nao", "observacao": ""}]}


def _d(tipo, chave, decisao, regime="", obs=""):
    return {"tipo_dado": tipo, "chave": chave, "decisao": decisao, "regime_correto": regime, "observacao_contador": obs}


def test_aplicar_confirmar_corrigir_excluir():
    novas, rel, erros = aplicar([_d("regra_ncm", "10063021", "confirmar"),
                                 _d("regra_ncm", "21069090", "corrigir", "aliquota_zero", "vale o Anexo I"),
                                 _d("regra_ncm", "99999999", "excluir"), _d("servico", "II-1", "confirmar")], _base())
    assert erros == []
    por = {l["ncm_prefixo"]: l for l in novas["regra_ncm"]}
    assert por["10063021"]["validado"] == "sim" and por["10063021"]["regime"] == "aliquota_zero"
    assert (por["21069090"]["regime"], por["21069090"]["reducao_percentual"], por["21069090"]["validado"]) == ("aliquota_zero", "100", "sim")
    assert "Regime definido na revisão do contador. vale o Anexo I" == por["21069090"]["observacao"]
    assert "99999999" not in por and novas["servico"][0]["validado"] == "sim"
    assert por["85171"]["validado"] == "nao"  # sem decisão: intacto


def test_aplicar_nao_deixa_confirmar_a_confirmar_nem_regime_invalido_e_aborta_tudo():
    base = _base()
    novas, rel, erros = aplicar([_d("regra_ncm", "21069090", "confirmar"),
                                 _d("regra_ncm", "85171", "corrigir", "inventado"),
                                 _d("regra_ncm", "10063021", "talvez"), _d("regra_ncm", "00000000", "confirmar")], base)
    assert len(erros) == 4
    assert any("a_confirmar não pode ser 'confirmar'" in e for e in erros)
    assert any("regime_correto 'inventado' inválido" in e for e in erros)
    assert any("decisão inválida 'talvez'" in e for e in erros) and any("encontrei 0 linhas" in e for e in erros)
    assert base["regra_ncm"][0]["validado"] == "nao"  # a base original nunca é alterada


def test_aplicar_deixa_decisoes_de_anexo_simples_sinonimo_para_revisao_manual():
    _, rel, erros = aplicar([_d("anexo", "XIV", "corrigir", obs="regra nova de medicamentos"), _d("sinonimo", "frango", "confirmar")], _base())
    assert erros == [] and all(l.startswith("MANUAL") for l in rel) and len(rel) == 2


def test_planilha_gerada_abre_no_excel(tmp_path):
    """UTF-8 com BOM e ';' (Excel brasileiro) e cabeçalho completo."""
    import gerar_planilha_revisao as g
    destino = tmp_path / "rev.csv"
    with open(destino, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=g.COLUNAS, delimiter=";")
        w.writeheader()
    assert destino.read_bytes().startswith(b"\xef\xbb\xbf") and destino.read_text(encoding="utf-8-sig").startswith("prioridade;")
