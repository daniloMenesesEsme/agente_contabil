"""Auditoria das planilhas de NCM. NÃO altera os arquivos de dados/: grava SÓ em dados/validacao/.

Uso:
  python scripts/validar_e_preencher_ncm.py

O que faz (e o que deliberadamente NÃO faz):
- NCM dentro de cláusula "exceto" (falso positivo): confere célula a célula e respeitando parênteses
  (um "exceto" na DESCRIÇÃO não exclui o NCM da coluna ao lado). Só reporta e, se achar algum, grava a
  base sem eles. As regras `padrao` criadas de propósito por "exceção expressa" nunca são removidas.
- NCM que não existe na tabela oficial vigente: relatório (possível código alterado/revogado).
- Planilha de revisão: acrescenta a coluna `alerta_validacao` (fatos tirados dos dados). NÃO preenche
  decisao / regime_correto / observacao_contador: isso é decisão do contador. Conclusões jurídicas (artigos,
  alíquotas, notas técnicas) só entram com verificação no texto da lei (regra do projeto).
- Simples/MEI: relatório das linhas repetidas. NÃO remove nenhuma: onde há duas versões de uma tabela, só o
  texto da lei diz qual é a vigente.
"""
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extrair_anexos_lc214 import RE_EXCECAO, _escopo_excecao, achados_ncm_pos  # noqa: E402

DADOS = Path(__file__).resolve().parents[1] / "dados"
SAIDA = DADOS / "validacao"

# Entradas: os CSVs reais do projeto
ARQUIVO_REGRAS = DADOS / "regras_ncm.csv"
ARQUIVO_REVISAO = DADOS / "revisao_contador.csv"
ARQUIVO_TABELA_NCM = DADOS / "ncm_tabela.csv"
ARQUIVO_SIMPLES = DADOS / "simples_anexos.csv"

# Saídas (todas em dados/validacao/)
SAIDA_EXCECOES = SAIDA / "relatorio_ncms_excecao_indevida.csv"
SAIDA_OBSOLETOS = SAIDA / "relatorio_ncms_obsoletos_tipi.csv"
SAIDA_REGRAS_LIMPAS = SAIDA / "regras_ncm_corrigido.csv"
SAIDA_REVISAO_ALERTAS = SAIDA / "revisao_contador_com_alertas.csv"
SAIDA_SIMPLES_DUPLICADAS = SAIDA / "simples_linhas_repetidas.csv"


def normalizar_ncm(codigo: str) -> str:
    """Remove pontos e espaços, mantendo apenas dígitos."""
    return re.sub(r"\D", "", str(codigo)).strip()


def ncm_em_clausula_de_excecao(texto_lei: str, ncm: str) -> bool:
    """True se `ncm` aparece DEPOIS de um 'exceto/exclusive/salvo...' na MESMA célula da linha da lei.

    A linha vem como 'item | descrição | códigos'. O alcance do 'exceto' é a própria célula e, se ele estiver
    entre parênteses, só até o fechamento. Assim 'Leite (exceto fermentado) | 0401.10.10' NÃO exclui 0401.10.10."""
    if not isinstance(texto_lei, str) or not ncm:
        return False
    for celula in texto_lei.split(" | "):
        m = RE_EXCECAO.search(celula)
        if not m:
            continue
        limite = _escopo_excecao(celula, m.start())
        for codigo, pos in achados_ncm_pos(celula):
            excluido = normalizar_ncm(codigo)
            # NCM igual ao excluído ou DENTRO dele (a lei exclui a subposição 0306.11: 03061100 também sai)
            if m.start() < pos <= limite and len(excluido) >= 4 and ncm.startswith(excluido):
                return True
    return False


def detectar_excecoes_indevidas(df_regras: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """(base sem os falsos positivos, relatório, nº de regras de exceção expressa preservadas)."""
    registros, remover, protetoras = [], [], 0
    for idx, row in df_regras.iterrows():
        ncm = normalizar_ncm(row.get("ncm_prefixo", ""))
        if not ncm_em_clausula_de_excecao(str(row.get("texto_lei", "")), ncm):
            continue
        if "exceção expressa" in str(row.get("fundamento", "")):
            protetoras += 1  # criada DE PROPÓSITO: protege o NCM excluído do benefício do prefixo-pai
            continue
        registros.append({"linha_csv": idx + 2, "ncm_prefixo": ncm, "regime_errado": row.get("regime"),
                          "fundamento": row.get("fundamento"), "descricao": row.get("descricao"),
                          "motivo": "Código consta na cláusula 'exceto' da própria célula do texto_lei"})
        remover.append(idx)
    return df_regras.drop(index=remover).copy(), pd.DataFrame(registros), protetoras


def verificar_ncms_obsoletos(df_regras: pd.DataFrame, df_tabela: pd.DataFrame) -> pd.DataFrame:
    """Prefixos da base de regras que não existem (nem como prefixo de código vigente) na tabela oficial."""
    prefixos_validos = set()
    for codigo in df_tabela["codigo"].dropna().map(normalizar_ncm):
        prefixos_validos.update(codigo[:n] for n in range(2, len(codigo) + 1))
    obsoletos = []
    for idx, row in df_regras.iterrows():
        ncm = normalizar_ncm(row.get("ncm_prefixo", ""))
        if ncm and ncm not in prefixos_validos:
            obsoletos.append({"linha_csv": idx + 2, "ncm_prefixo": ncm, "regime": row.get("regime"),
                              "fundamento": row.get("fundamento"), "descricao": row.get("descricao"),
                              "alerta": "Código não localizado na tabela NCM vigente (possível NCM revogado/alterado)."})
    return pd.DataFrame(obsoletos)


def adicionar_alertas_na_revisao(df_rev: pd.DataFrame, df_obsoletos: pd.DataFrame,
                                 df_excecoes: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta `alerta_validacao` (fatos dos dados). Nunca toca em decisao/regime_correto/observacao_contador."""
    df = df_rev.copy()
    df["alerta_validacao"] = ""
    obsoletos = set(df_obsoletos["ncm_prefixo"]) if len(df_obsoletos) else set()
    excecoes = set(df_excecoes["ncm_prefixo"]) if len(df_excecoes) else set()
    eh_regra = df["tipo_dado"] == "regra_ncm"
    chave = df["chave"].map(normalizar_ncm)
    df.loc[eh_regra & chave.isin(obsoletos), "alerta_validacao"] = (
        "NCM NÃO ENCONTRADO na tabela oficial vigente: possível código alterado ou revogado.")
    df.loc[eh_regra & chave.isin(excecoes), "alerta_validacao"] = (
        "NCM aparece na cláusula 'exceto' da própria linha da lei: possível inclusão indevida.")
    return df


def relatar_linhas_repetidas_simples(df_simples: pd.DataFrame) -> pd.DataFrame:
    """Linhas (exceto cabeçalhos) com o mesmo anexo, seção e conteúdo de outra anterior. Só relata."""
    df = df_simples.copy()
    df["ordem_num"] = pd.to_numeric(df["ordem"], errors="coerce")
    df = df.sort_values(["anexo", "secao", "ordem_num"])
    chave = ["anexo", "secao", "celulas"]
    primeira = df.groupby(chave)["ordem_num"].transform("min")
    # rótulo de cabeçalho repetido (IRPJ, CSLL, Cofins...) é normal numa tabela de partilha: só relata o resto
    rep = df[df.duplicated(subset=chave, keep="first") & (df["tipo"] != "cabecalho")].copy()
    rep["primeira_ocorrencia_ordem"] = primeira[rep.index]
    rep["primeira_celula"] = rep["celulas"].str.slice(0, 60)
    rep["motivo"] = "Mesmo conteúdo já aparece antes na mesma seção (possíveis duas versões da tabela)"
    return rep[["anexo", "secao", "ordem", "primeira_ocorrencia_ordem", "tipo", "primeira_celula", "motivo"]]


def _gravar(df: pd.DataFrame, caminho: Path) -> None:
    df.to_csv(caminho, sep=";", index=False, encoding="utf-8-sig")


def _ler(caminho: Path) -> pd.DataFrame:
    return pd.read_csv(caminho, sep=";", dtype=str, encoding="utf-8-sig", keep_default_na=False)


if __name__ == "__main__":
    print("=== Auditoria das planilhas de NCM (não altera dados/; saída em dados/validacao/) ===\n")
    faltando = [a.name for a in (ARQUIVO_REGRAS, ARQUIVO_TABELA_NCM, ARQUIVO_REVISAO, ARQUIVO_SIMPLES) if not a.exists()]
    if faltando:
        sys.exit(f"[ERRO] Arquivos não encontrados em {DADOS}: {', '.join(faltando)}")
    SAIDA.mkdir(exist_ok=True)

    regras = _ler(ARQUIVO_REGRAS)
    tabela = _ler(ARQUIVO_TABELA_NCM)

    limpas, df_excecoes, protetoras = detectar_excecoes_indevidas(regras)
    _gravar(df_excecoes, SAIDA_EXCECOES)
    print(f"[OK] {len(df_excecoes)} NCMs com exceção invertida em '{SAIDA_EXCECOES.name}' "
          f"({protetoras} regras de exceção expressa preservadas de propósito).")
    if len(df_excecoes):
        _gravar(limpas, SAIDA_REGRAS_LIMPAS)
        print(f"[OK] Base sem esses NCMs salva em '{SAIDA_REGRAS_LIMPAS.name}' ({len(limpas)} de {len(regras)} regras).")
    else:
        print("[OK] Nenhuma regra a remover: 'regras_ncm_corrigido.csv' não é necessário.")

    df_obs = verificar_ncms_obsoletos(limpas, tabela)
    _gravar(df_obs, SAIDA_OBSOLETOS)
    print(f"[OK] {len(df_obs)} NCMs fora da tabela oficial em '{SAIDA_OBSOLETOS.name}'.")

    revisao = adicionar_alertas_na_revisao(_ler(ARQUIVO_REVISAO), df_obs, df_excecoes)
    _gravar(revisao, SAIDA_REVISAO_ALERTAS)
    print(f"[OK] Revisão com {int((revisao['alerta_validacao'] != '').sum())} alertas em '{SAIDA_REVISAO_ALERTAS.name}' "
          "(decisões do contador intocadas).")

    df_rep = relatar_linhas_repetidas_simples(_ler(ARQUIVO_SIMPLES))
    _gravar(df_rep, SAIDA_SIMPLES_DUPLICADAS)
    print(f"[OK] {len(df_rep)} linhas repetidas do Simples em '{SAIDA_SIMPLES_DUPLICADAS.name}' (nada foi removido).")

    print("\n=== Processamento concluído! ===")
