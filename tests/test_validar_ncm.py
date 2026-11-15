import pandas as pd

from validar_e_preencher_ncm import (adicionar_alertas_na_revisao, detectar_excecoes_indevidas,
                                     ncm_em_clausula_de_excecao, relatar_linhas_repetidas_simples,
                                     verificar_ncms_obsoletos)


def test_exceto_na_descricao_nao_exclui_o_ncm_da_coluna_de_codigo():
    """O caso que o script original errava: 'exceto' na descrição + código na célula ao lado."""
    assert not ncm_em_clausula_de_excecao("13 | Aves de um dia, exceto as ornamentais | 0105.1", "01051")
    assert not ncm_em_clausula_de_excecao("19 | Carnes (exceto foie gras 0210.99) | 0206.10.00", "02061000")


def test_ncm_listado_depois_do_exceto_na_mesma_celula_e_detectado():
    linha = "1.3 | Aparelhos de eletrodiagnóstico, exceto os produtos classificados nos códigos 9018.11.00, 9018.12.10 | 9018.1"
    assert ncm_em_clausula_de_excecao(linha, "90181210")
    assert not ncm_em_clausula_de_excecao(linha, "90181")  # a coluna de código é outra célula


def test_excecao_entre_parenteses_vale_so_ate_fechar():
    assert ncm_em_clausula_de_excecao("Carnes (exceto foie gras 0210.99), dos códigos 0201.10.00", "021099")
    assert not ncm_em_clausula_de_excecao("Carnes (exceto foie gras 0210.99), dos códigos 0201.10.00", "02011000")


def test_entradas_vazias_nao_quebram():
    assert not ncm_em_clausula_de_excecao(None, "123") and not ncm_em_clausula_de_excecao("texto", "")


def _regras(linhas):
    return pd.DataFrame(linhas, columns=["ncm_prefixo", "regime", "fundamento", "descricao", "texto_lei"])


def test_regra_protetora_de_excecao_expressa_nunca_e_removida():
    df = _regras([
        ["90181210", "padrao", "LC 214/2025, Anexo XII (exceção expressa)", "x", "1.3 | Aparelhos, exceto os códigos 9018.12.10"],
        ["01051", "reducao_60", "LC 214/2025, Anexo IX", "y", "13 | Aves de um dia, exceto as ornamentais | 0105.1"]])
    limpas, rel, protetoras = detectar_excecoes_indevidas(df)
    assert protetoras == 1 and len(rel) == 0 and len(limpas) == 2  # nada removido


def test_inclusao_indevida_de_verdade_e_reportada_e_removida():
    df = _regras([["03061100", "reducao_60", "LC 214/2025, Anexo VII", "z",
                   "5 | Crustáceos, exceto os produtos da subposição 0306.11 e 0306.15.00"]])
    limpas, rel, _ = detectar_excecoes_indevidas(df)
    assert list(rel["ncm_prefixo"]) == ["03061100"] and len(limpas) == 0
    assert rel.iloc[0]["linha_csv"] == 2


def test_obsoletos_aceita_prefixo_de_qualquer_nivel_e_acusa_codigo_inexistente():
    tabela = pd.DataFrame({"codigo": ["8517.13.00", "1006.30.21"]})
    regras = _regras([["85171300", "padrao", "f", "a", ""], ["8517", "padrao", "f", "b", ""],
                      ["100630", "padrao", "f", "c", ""], ["28273998", "padrao", "f", "d", ""]])
    assert list(verificar_ncms_obsoletos(regras, tabela)["ncm_prefixo"]) == ["28273998"]


def test_alertas_nao_tocam_nas_colunas_do_contador():
    rev = pd.DataFrame({"tipo_dado": ["regra_ncm", "regra_ncm", "servico"], "chave": ["28273998", "10063021", "II-1"],
                        "decisao": ["", "confirmar", ""], "regime_correto": ["", "", ""],
                        "observacao_contador": ["", "ok", ""]})
    obs = pd.DataFrame({"ncm_prefixo": ["28273998"]})
    saida = adicionar_alertas_na_revisao(rev, obs, pd.DataFrame())
    assert list(saida["alerta_validacao"]) == ["NCM NÃO ENCONTRADO na tabela oficial vigente: possível código alterado ou revogado.", "", ""]
    for coluna in ("decisao", "regime_correto", "observacao_contador"):
        assert list(saida[coluna]) == list(rev[coluna])


def test_simples_so_relata_linhas_repetidas_e_nao_remove_nada():
    df = pd.DataFrame({"anexo": ["SN-III"] * 4, "secao": ["2027"] * 4, "ordem": ["1", "2", "3", "4"],
                       "tipo": ["faixa"] * 4, "celulas": ['["1ª Faixa", "4%"]', '["2ª Faixa", "7%"]', '["1ª Faixa", "4%"]', '["3ª Faixa", "9%"]']})
    rep = relatar_linhas_repetidas_simples(df)
    assert list(rep["ordem"]) == ["3"] and list(rep["primeira_ocorrencia_ordem"]) == [1.0]
    assert len(df) == 4  # a base original continua inteira


def test_ncm_completo_dentro_da_subposicao_excluida_tambem_e_excluido_mas_o_pai_nao():
    linha = "5 | Crustáceos, exceto os produtos da subposição 0306.11 | 0306.1"
    assert ncm_em_clausula_de_excecao(linha, "03061100")      # dentro de 0306.11
    assert ncm_em_clausula_de_excecao(linha, "030611")        # a própria subposição
    assert not ncm_em_clausula_de_excecao(linha, "03061")     # o pai (mais amplo) segue com o benefício
    assert not ncm_em_clausula_de_excecao(linha, "0306")


def test_cabecalho_repetido_nao_e_duplicata():
    df = pd.DataFrame({"anexo": ["SN-III"] * 4, "secao": ["2029"] * 4, "ordem": ["1", "2", "3", "4"],
                       "tipo": ["cabecalho", "cabecalho", "faixa", "faixa"],
                       "celulas": ['["IRPJ"]', '["IRPJ"]', '["1ª Faixa", "4%"]', '["1ª Faixa", "4%"]']})
    assert list(relatar_linhas_repetidas_simples(df)["ordem"]) == ["4"]  # só a faixa repetida
