"""Conferência em lote da lista de produtos do ERP (sem IA: a lista não sai do computador).

Entrada: planilha CSV exportada do ERP (descrição + NCM, opcionalmente código). Saída: uma linha por produto com o
que está errado e o que fazer, PROBLEMAS PRIMEIRO. Pega os erros típicos de ERP: NCM que não existe, NCM de outro
produto, NCM com 7 dígitos (o Excel come o zero à esquerda), NCM incompleto e produto sem NCM.
O regime vem só de `consultar` (dados/regras_ncm.csv); nada aqui define alíquota.
"""
import csv
import io
import re
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path

from . import config
from .calculo import consultar
from .ncm_tabela import candidatos_por_descricao, descricao_oficial, disponivel, verificar_ncm
from .normalizacao import normalizar_ncm
from .regras import buscar_por_ncm

LIMITE_ITENS = 5000       # planilha na CLI
LIMITE_ITENS_API = 1000   # uma chamada HTTP: cerca de 35 ms por item

# status -> (gravidade, o que o lojista faz). Gravidade 1 = pior.
STATUS = {
    "NCM_INEXISTENTE": 1, "NCM_SEM_ZERO": 2, "NCM_NAO_CONFIRMADO": 3, "NCM_INCOMPLETO": 4, "REGIME_A_CONFIRMAR": 5,
    "SEM_NCM": 6, "CONFERIR": 7, "OK_SEM_BENEFICIO": 8, "OK_COM_BENEFICIO": 9,
}
COLUNAS_SAIDA = ["linha", "codigo", "descricao", "ncm_informado", "status", "gravidade", "o_que_fazer",
                 "ncm_sugerido", "descricao_oficial_ncm", "compatibilidade", "regime", "aliquota_total_percentual",
                 "cenarios", "fundamento", "regra_validada", "avisos"]
# nomes exatos aceitos, além do reconhecimento por trecho em _acha_coluna
NOMES_COLUNAS = {
    "descricao": ["produto", "nome", "item", "mercadoria"],
    "ncm": ["classfiscal", "classificacaofiscal"],
    "codigo": ["codigo", "cod", "sku", "id", "referencia", "ref", "codigointerno"],
}


# Palavras comerciais do cadastro de ERP que não fazem parte do nome técnico do produto: só saem da BUSCA
# (a descrição original continua na planilha). Quantidades como "5kg" já são descartadas na tokenização.
ENCHIMENTO_ERP = {"tipo", "tradicional", "classico", "original", "novo", "nova", "extra", "premium", "marca", "kit",
                  "pacote", "pct", "caixa", "cx", "unidade", "und", "fardo", "embalagem", "sabor", "cor", "tamanho", "tam"}


def descricao_para_busca(descricao: str) -> str:
    """Tira o enchimento comercial do ERP ('Arroz tipo 1 tradicional 5kg' -> 'Arroz 1 5kg')."""
    return " ".join(p for p in str(descricao or "").split() if _chave(p) not in ENCHIMENTO_ERP)


def _chave(texto: str) -> str:
    t = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", t)


def _acha_coluna(campo: str, por_chave: dict[str, str]) -> str | None:
    """Coluna do ERP para `campo`: 'Descrição do Produto', 'NCM/SH', 'Cód. Produto'... (por trecho do nome)."""
    for chave, original in por_chave.items():
        if campo == "descricao" and ("descri" in chave or chave in NOMES_COLUNAS["descricao"]):
            return original
        if campo == "ncm" and ("ncm" in chave or chave in NOMES_COLUNAS["ncm"]):
            return original
        if campo == "codigo" and "ncm" not in chave and "barra" not in chave and "ean" not in chave and (
                chave in NOMES_COLUNAS["codigo"] or chave.startswith(("cod", "sku", "ref"))):
            return original
    return None


def detectar_colunas(cabecalho: list[str], descricao: str | None = None, ncm: str | None = None) -> dict[str, str | None]:
    """Acha as colunas pelo nome (sem acento/maiúscula/símbolos) ou usa as informadas. Levanta ValueError se faltar."""
    por_chave = {_chave(c): c for c in cabecalho}
    achadas: dict[str, str | None] = {}
    for campo, explicito in (("descricao", descricao), ("ncm", ncm), ("codigo", None)):
        if explicito:
            if explicito not in cabecalho:
                raise ValueError(f"Coluna '{explicito}' não existe. Colunas: {', '.join(cabecalho)}")
            achadas[campo] = explicito
        else:
            achadas[campo] = _acha_coluna(campo, por_chave)
    if not achadas["ncm"] or not achadas["descricao"]:
        raise ValueError("Não achei as colunas de descrição e NCM. Use --col-descricao e --col-ncm. "
                         f"Colunas encontradas: {', '.join(cabecalho)}")
    return achadas


def ler_planilha(caminho: Path) -> tuple[list[str], list[dict]]:
    """CSV de ERP: detecta ';' ou ',' ou tabulação e a codificação (UTF-8 com/sem BOM ou Latin-1)."""
    bruto = Path(caminho).read_bytes()
    for enc in ("utf-8-sig", "latin-1"):
        try:
            texto = bruto.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    amostra = texto[:4096]
    try:
        dialeto = csv.Sniffer().sniff(amostra, delimiters=";,\t|")
    except csv.Error:
        dialeto = csv.excel
        dialeto.delimiter = ";" if amostra.count(";") >= amostra.count(",") else ","
    leitor = csv.DictReader(io.StringIO(texto), dialect=dialeto)
    linhas = [{k.strip(): (v or "").strip() for k, v in l.items() if k} for l in leitor]
    return [c.strip() for c in leitor.fieldnames or []], linhas


@lru_cache(maxsize=4096)
def _consulta(ncm: str, ano: int) -> dict:
    return consultar(ncm, ano)


@lru_cache(maxsize=4096)
def _sugestoes(busca: str) -> tuple:
    return tuple(candidatos_por_descricao(busca))


@lru_cache(maxsize=4096)
def _verificacao(digitos: str, busca: str) -> dict:
    return verificar_ncm(digitos, busca)


def _formatar_candidatos(candidatos: list[dict]) -> str:
    return " | ".join(f"{c['ncm']} ({c['descricao'][:45]})" for c in candidatos)


def _sem_zero(digitos: str) -> str | None:
    """NCM de 7 dígitos que vira válido com um zero à esquerda (o Excel descarta o zero)."""
    if len(digitos) == 7 and disponivel():
        candidato = "0" + digitos
        oficial = descricao_oficial(candidato)
        if oficial and oficial["existe"]:
            return candidato
    return None


def analisar_item(descricao: str, ncm: str, ano: int, codigo: str = "", linha: int = 0) -> dict:
    """Confere um produto. Sempre devolve todas as colunas de COLUNAS_SAIDA."""
    descricao, ncm_informado = (descricao or "").strip(), (ncm or "").strip()
    busca = descricao_para_busca(descricao)
    digitos = normalizar_ncm(ncm_informado)
    r = {c: "" for c in COLUNAS_SAIDA}
    r.update(linha=linha, codigo=codigo, descricao=descricao, ncm_informado=ncm_informado)

    aviso_tabela = ("" if disponivel() else "Tabela oficial da NCM indisponível: não foi possível conferir se o NCM "
                                            "existe nem se bate com o produto.")

    def fechar(status: str, o_que_fazer: str) -> dict:
        r.update(status=status, gravidade=STATUS[status], o_que_fazer=o_que_fazer)
        r["avisos"] = " || ".join(x for x in (aviso_tabela, r["avisos"]) if x)
        return r

    if not digitos:
        sugestoes = list(_sugestoes(busca))
        r["ncm_sugerido"] = _formatar_candidatos(sugestoes)
        return fechar("SEM_NCM", "Produto sem NCM. Confira a nota fiscal do fornecedor; sugestões pela descrição "
                                 "(valide antes de usar)." if sugestoes else "Produto sem NCM e sem sugestão pela descrição: "
                                 "pegue o NCM na nota fiscal do fornecedor.")

    corrigido = _sem_zero(digitos)
    if corrigido:
        oficial = descricao_oficial(corrigido)
        r["ncm_sugerido"] = oficial["codigo"]
        r["descricao_oficial_ncm"] = oficial["descricao_completa"]
        return fechar("NCM_SEM_ZERO", f"O NCM tem 7 dígitos: provavelmente perdeu o zero à esquerda (comum ao abrir no Excel). "
                                     f"Use {oficial['codigo']} se for esse produto: {oficial['descricao'][:80]}.")
    if len(digitos) != 8:
        return fechar("NCM_INCOMPLETO", f"O NCM tem {len(digitos)} dígitos; o cadastro precisa do NCM completo (8 dígitos) "
                                        "para definir o regime. Complete pela nota fiscal do fornecedor.")

    oficial = descricao_oficial(digitos)
    if oficial is not None and not oficial["existe"]:
        sugestoes = list(_sugestoes(busca))
        r["ncm_sugerido"] = _formatar_candidatos(sugestoes)
        return fechar("NCM_INEXISTENTE", "Este NCM NÃO existe na tabela oficial vigente: provavelmente digitado errado ou "
                                         "desatualizado. Confira na nota fiscal do fornecedor" +
                      (" (sugestões pela descrição abaixo)." if sugestoes else "."))
    if oficial is not None:
        r["descricao_oficial_ncm"] = oficial["descricao_completa"]
        verif = _verificacao(digitos, busca) if busca else {"compatibilidade": "nao_avaliada"}
        r["compatibilidade"] = verif.get("compatibilidade", "")
        if verif.get("compatibilidade") == "baixa":
            alternativas = [{"ncm": c["ncm"], "descricao": c["descricao_completa"].split(" > ")[-1]}
                            for c in verif.get("candidatos_alternativos", [])]
            r["ncm_sugerido"] = _formatar_candidatos(alternativas)
            return fechar("NCM_NAO_CONFIRMADO", "Não consegui confirmar que este NCM é do produto pela descrição: pode ser NCM "
                                                "errado OU só diferença de nome (a NCM usa termo técnico). Compare com "
                                                "'descricao_oficial_ncm' e a nota fiscal do fornecedor; NCM errado leva a "
                                                "regime e CST errados." + (" Sugestões abaixo." if alternativas else ""))

    c = _consulta(digitos, ano)
    if "erro" in c:
        return fechar("NCM_INCOMPLETO", c["erro"])
    regra = buscar_por_ncm(digitos)
    total = c["aliquotas_percentual"]["total"]
    r.update(regime=c["regime"], aliquota_total_percentual="indefinida" if total is None else total,
             fundamento=c["fundamento"], regra_validada="sim" if regra and regra.validado else "nao",
             cenarios=" | ".join(f"{x['condicao'][:55]} -> {x['regime']}" for x in c["cenarios"]),
             avisos=" || ".join(a[:140] for a in c["avisos"][:2]))
    if c["regime"] == "a_confirmar" or c["enquadramento_a_confirmar"]:
        return fechar("REGIME_A_CONFIRMAR", "O regime deste NCM NÃO é único (vale só para um produto específico, ou há conflito "
                                            "entre anexos, ou a regra depende de outro fator). Veja 'cenarios' e confirme "
                                            "com o contador.")
    if regra is None or regra.regime == "padrao":
        return fechar("OK_SEM_BENEFICIO", "NCM existe e confere. Não consta de lista de benefício cadastrada: presume-se a "
                                          "alíquota padrão (confirme com o contador).")
    if regra.ressalva or r["compatibilidade"] == "media":
        return fechar("CONFERIR", "NCM provavelmente confere, mas há ressalva da lei ou a conferência da descrição foi parcial: "
                                  "leia 'avisos' e confirme que o produto se enquadra.")
    return fechar("OK_COM_BENEFICIO", f"NCM confere e a regra cadastrada é '{c['regime']}' ({c['fundamento']}). "
                                      "A regra ainda precisa de validação do contador" if not (regra and regra.validado)
                  else f"NCM confere; regra '{c['regime']}' validada pelo contador.")


def analisar_lote(itens: list[dict], ano: int | None = None, limite: int = LIMITE_ITENS) -> list[dict]:
    """itens: [{descricao, ncm, codigo?}]. Devolve ordenado por gravidade (problemas primeiro), mantendo a linha original."""
    if len(itens) > limite:
        raise ValueError(f"Lote com {len(itens)} itens; o limite é {limite}. Divida a planilha.")
    ano = ano or config.ANO_PADRAO
    resultados = [analisar_item(i.get("descricao", ""), i.get("ncm", ""), ano, i.get("codigo", ""), n)
                  for n, i in enumerate(itens, start=1)]
    return sorted(resultados, key=lambda x: (x["gravidade"], x["linha"]))


def resumo(resultados: list[dict]) -> dict:
    por = Counter(r["status"] for r in resultados)
    return {"total": len(resultados), "com_problema": sum(n for s, n in por.items() if STATUS[s] <= 4),
            "a_confirmar": por.get("REGIME_A_CONFIRMAR", 0) + por.get("CONFERIR", 0),
            "por_status": {s: por[s] for s in sorted(por, key=STATUS.get)}}


def itens_da_planilha(caminho: Path, col_descricao: str | None = None, col_ncm: str | None = None) -> list[dict]:
    cabecalho, linhas = ler_planilha(caminho)
    col = detectar_colunas(cabecalho, col_descricao, col_ncm)
    return [{"descricao": l.get(col["descricao"], ""), "ncm": l.get(col["ncm"], ""),
             "codigo": l.get(col["codigo"], "") if col["codigo"] else ""} for l in linhas]


def gravar_saida(resultados: list[dict], destino: Path) -> None:
    with open(destino, "w", encoding="utf-8-sig", newline="") as f:  # BOM + ';' = abre direto no Excel brasileiro
        w = csv.DictWriter(f, fieldnames=COLUNAS_SAIDA, delimiter=";")
        w.writeheader()
        w.writerows(resultados)
