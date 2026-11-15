"""Tabela OFICIAL da NCM (Receita/Siscomex, dados/ncm_tabela.csv; importada por scripts/importar_ncm.py).

Serve para três coisas que as regras de benefício sozinhas não resolvem:
- conferir se o NCM EXISTE (ERP com código errado ou desatualizado);
- mostrar o que o NCM significa oficialmente, para o lojista comparar com o produto que vende;
- achar o NCM de QUALQUER produto pela descrição oficial (não só dos que têm benefício).
Nada aqui define alíquota: o regime continua vindo só de dados/regras_ncm.csv.
"""
import csv
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from . import config
from .normalizacao import normalizar_ncm, radical
from .texto_busca import IndiceBusca

# Palavras que só estruturam a nomenclatura ("Outros", "Demais"): não identificam o produto.
GENERICAS = frozenset(radical(p) for p in ("outros", "outras", "demais", "exceto", "inclusive", "mesmo", "mesmos"))


@dataclass(frozen=True)
class NcmOficial:
    codigo: str       # formatado: 8517.13.00
    nivel: int        # dígitos: 2, 4, 5, 6, 7 ou 8
    descricao: str    # só o nível ("Outros")
    completa: str     # com os níveis acima ("Aparelhos telefônicos > Telefones inteligentes")


@lru_cache(maxsize=1)
def carregar() -> dict[str, NcmOficial]:
    """dígitos -> NCM oficial. Arquivo ausente = tabela indisponível (dicionário vazio)."""
    arq = Path(config.ARQ_NCM)
    if not arq.exists():
        return {}
    with open(arq, encoding="utf-8", newline="") as f:
        return {normalizar_ncm(l["codigo"]): NcmOficial(l["codigo"], int(l["nivel"]), l["descricao"], l["completa"])
                for l in csv.DictReader(f, delimiter=";")}


def disponivel() -> bool:
    return bool(carregar())


def meta() -> dict:
    arq = Path(config.ARQ_NCM_META)
    return json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}


def _texto_vigencia() -> str:
    m = meta()
    return " — ".join(x for x in (m.get("vigencia"), m.get("ato")) if x) or "vigência não informada"


def descricao_oficial(ncm: str) -> dict | None:
    """None se a tabela não está disponível; senão {existe, ...}. Aceita 2, 4, 5, 6, 7 ou 8 dígitos."""
    if not disponivel():
        return None
    item = carregar().get(normalizar_ncm(ncm))
    if item is None:
        return {"existe": False, "tabela": _texto_vigencia()}
    return {"existe": True, "codigo": item.codigo, "nivel": item.nivel, "descricao": item.descricao,
            "descricao_completa": item.completa, "tabela": _texto_vigencia()}


@lru_cache(maxsize=1)
def _indice() -> tuple[IndiceBusca, tuple[NcmOficial, ...]]:
    """Índice só dos NCMs completos (8 dígitos). O 'principal' é a descrição mais específica que não seja
    genérica; o texto completo entra como extra (cobertura), então 'outros' não vira o assunto."""
    folhas = tuple(sorted((n for n in carregar().values() if n.nivel == 8), key=lambda n: n.codigo))
    docs = []
    for n in folhas:
        partes = n.completa.split(" > ")
        principal = next((p for p in reversed(partes) if set(IndiceBusca([(p, "")]).principais[0])), partes[-1])
        # 'principal' = nível mais específico + início de cada nível: citação solta no fim de uma lista longa
        # do cabeçalho ("... caixas para pó de arroz ...") não identifica o item
        inicios = " ".join(" ".join(p.split()[:3]) for p in partes if p != principal)
        docs.append((f"{principal} {inicios}", n.completa))
    return IndiceBusca(docs, GENERICAS, modo_posicao="principal"), folhas


def _regra_resumida(ncm: str) -> dict | None:
    """Regra de benefício cadastrada, com o mesmo cuidado de `consultar`: se ela vale só para o produto
    descrito (código incompleto na lei, ou NCM dividido com anexo revogado), o regime fica a_confirmar."""
    from .regras import buscar_por_ncm  # evita import circular
    r = buscar_por_ncm(ncm)
    if r is None:
        return None
    so_descrito = r.regime not in ("padrao", "a_confirmar") and bool(
        r.outros_produtos or len(r.ncm_prefixo) in (5, 7))
    resumo = {"regime": "a_confirmar" if so_descrito else r.regime, "validado": r.validado,
              "fundamento": r.fundamento, "descricao_da_regra": r.descricao}
    if so_descrito:
        resumo["se_for_exatamente_o_produto_da_regra"] = r.regime
        resumo["aviso"] = ("O benefício vale só para o produto descrito em `descricao_da_regra`, não para todo "
                           "o NCM: use consultar_ncm para os cenários.")
    return resumo


def _folhas_candidatas(texto: str) -> tuple[list[dict], list[str], list[str]]:
    """NCMs de 8 dígitos que casam com o texto, do melhor ao pior (sem agrupar), + sem correspondência
    + palavras ignoradas pelo relaxamento."""
    indice, folhas = _indice()
    ranking, sem, ignoradas = indice.buscar_relaxado(texto, ignorar_desconhecidas=True)
    return [{"ncm": folhas[r["indice"]].codigo, "descricao_completa": folhas[r["indice"]].completa,
             "confianca": r["confianca"], "cobertura": round(r["cobertura"], 2), "pontos": r["pontos"],
             "sinonimos_usados": r["sinonimos"], "regra_cadastrada": _regra_resumida(folhas[r["indice"]].codigo)}
            for r in ranking], sem, ignoradas


def candidatos_por_descricao(texto: str, limite: int = 3) -> list[dict]:
    """Lista simples dos melhores NCMs (8 dígitos) para a descrição: [{ncm, descricao, confianca}]."""
    if not disponivel() or not (texto or "").strip():
        return []
    folhas, _, _ = _folhas_candidatas(texto)
    return [{"ncm": f["ncm"], "descricao": f["descricao_completa"].split(" > ")[-1], "confianca": f["confianca"]}
            for f in folhas[:limite]]


def identificar_ncm(texto: str, limite_grupos: int = 5) -> dict:
    """NCMs candidatos pela descrição oficial, AGRUPADOS por posição (4 dígitos): uma palavra que cai em
    famílias muito diferentes ('celular': telefone, terapia celular, painel de madeira) vem como `ambigua`."""
    if not disponivel():
        return {"grupos": [], "avisos": ["Tabela oficial da NCM indisponível (rode scripts/importar_ncm.py)."]}
    folhas, sem, ignoradas = _folhas_candidatas(texto)
    por_posicao: dict[str, list[dict]] = {}
    for f in folhas:
        por_posicao.setdefault(f["ncm"][:5], []).append(f)  # "8517."
    grupos = []
    for posicao, itens in por_posicao.items():
        topo = itens[0]
        grupos.append({"posicao": posicao.rstrip("."),
                       "descricao_da_posicao": (carregar().get(normalizar_ncm(posicao)) or NcmOficial("", 4, "", "")).descricao,
                       "confianca": topo["confianca"], "cobertura": topo["cobertura"],
                       "ncms_que_casam": len(itens),
                       "pontuacao_do_grupo": topo["pontos"] * (1 + 0.15 * math.log(len(itens))),
                       "candidatos": [{k: v for k, v in i.items() if k != "pontos"} for i in itens[:3]]})
    grupos.sort(key=lambda g: (-round(g["cobertura"], 3), -g["pontuacao_do_grupo"]))
    grupos = grupos[:limite_grupos]
    altos = [g for g in grupos if g["confianca"] == "alta"]
    ambigua = len(altos) >= 3 and altos[1]["pontuacao_do_grupo"] >= 0.6 * altos[0]["pontuacao_do_grupo"]
    avisos = []
    if ignoradas:
        avisos.append(f"Nenhum NCM cobre tudo que foi pedido: IGNOREI as palavras {', '.join(ignoradas)} "
                      "(a nomenclatura oficial não as usa). Confirme com o usuário se isso faz sentido.")
    if not grupos:
        avisos.append("Nenhum NCM encontrado pela descrição. A nomenclatura usa termos técnicos (ex.: bebida "
                      "não alcoólica adoçada = 'águas ... adicionadas de açúcar'): reformule com termos oficiais "
                      "ou peça ao usuário o material, a composição e o uso do produto.")
    elif ambigua:
        avisos.append("AMBÍGUO: a descrição casou com famílias muito diferentes de produtos. Não escolha por conta "
                      "própria: pergunte ao usuário o que é exatamente o produto (material, uso, composição).")
    elif not altos:
        avisos.append("CONFIANÇA BAIXA: nenhum candidato cobre tudo que foi pedido (veja "
                      "palavras_sem_correspondencia). Peça mais detalhes ao usuário.")
    avisos.append("A busca é por palavras, não por significado: confira se a descrição OFICIAL de cada candidato "
                  "faz sentido para o produto antes de usá-lo; se nenhuma fizer, diga isso.")
    for g in grupos:
        g["palavras_sem_correspondencia"] = sem
        g.pop("pontuacao_do_grupo")
    return {"ambigua": ambigua, "palavras_ignoradas": ignoradas, "grupos": grupos, "avisos": avisos}


def verificar_ncm(ncm: str, produto: str) -> dict:
    """Confere se o NCM (ex.: o do ERP) combina com o produto descrito. Não decide: mostra o que o NCM é,
    quanto do produto casa e, se não combinar, candidatos alternativos."""
    if not disponivel():
        return {"erro": "Tabela oficial da NCM indisponível (rode scripts/importar_ncm.py)."}
    if not produto or not produto.strip():
        return {"erro": "Informe o produto."}
    codigo = normalizar_ncm(ncm)
    oficial = descricao_oficial(codigo)
    avisos = []
    base = {"ncm_informado": ncm, "produto_informado": produto, "descricao_oficial": oficial}
    if not oficial["existe"]:
        avisos.append("NCM NÃO CONSTA da tabela oficial vigente: provavelmente digitado errado ou desatualizado "
                      "no ERP. Veja os candidatos pela descrição do produto.")
        return {**base, "compatibilidade": "indeterminada", "palavras_do_produto_sem_correspondencia": [],
                "candidatos_alternativos": [{k: v for k, v in c.items() if k != "pontos"}
                                            for c in _folhas_candidatas(produto)[0][:3]], "avisos": avisos}
    if oficial["nivel"] != 8:
        avisos.append("Informe o NCM completo (8 dígitos) para conferir o produto.")
        return {**base, "compatibilidade": "nao_avaliada", "palavras_do_produto_sem_correspondencia": [],
                "candidatos_alternativos": [], "avisos": avisos}
    indice, folhas = _indice()
    posicao = next(i for i, n in enumerate(folhas) if normalizar_ncm(n.codigo) == codigo)
    resultados, sem = indice.buscar(produto, apenas=[posicao], ignorar_desconhecidas=True)
    cobertura = round(resultados[0]["cobertura"], 2) if resultados else 0.0
    compat = resultados[0]["confianca"] if resultados and cobertura > 0 else "baixa"
    if compat == "baixa" and resultados and resultados[0].get("cabeca"):
        compat = "media"  # o substantivo principal casa: o resto são modificadores ("refinado", "orgânico")
    alternativos = [] if compat == "alta" else [
        {k: v for k, v in c.items() if k != "pontos"} for c in _folhas_candidatas(produto)[0]
        if c["ncm"] != oficial["codigo"]][:3]
    if compat != "alta":
        avisos.append("O produto informado NÃO bate claramente com a descrição oficial deste NCM: confira o "
                      "cadastro no ERP e a nota fiscal do fornecedor antes de aplicar qualquer regime.")
    else:
        avisos.append("A descrição bate com o NCM, mas a conferência é por palavras: a classificação correta é "
                      "responsabilidade do contador/fornecedor.")
    return {**base, "compatibilidade": compat, "cobertura": cobertura, "palavras_do_produto_sem_correspondencia": sem,
            "candidatos_alternativos": alternativos, "avisos": avisos}
