"""Gera dados/regras_ncm.csv juntando extraido_lc214.csv (NCMs por anexo) e anexos_regimes.csv.

Uso:
  python scripts/gerar_regras.py [--sobrescrever]

Regras de segurança (o agente nunca inventa alíquota):
- Regime vem SÓ de anexos_regimes.csv (que vem do título do anexo). Anexo `a_definir`/revogado é ignorado.
- NCM em mais de um anexo com regimes diferentes: NÃO escolhe, grava em dados/brutos/conflitos.csv.
- NCM após "exceto..." no texto da lei: NÃO ganha o benefício. Vira regra `padrao` com aviso e vai
  para dados/brutos/excecoes.csv (senão o prefixo do pai, mais amplo, o cobriria por engano).
- Linha da lei com exceção/condição: o NCM entra, com `ressalva` obrigatória.
- Toda regra sai com validado=nao. Recusa sobrescrever um regras_ncm.csv com linhas validado=sim.
"""
import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from agente_contabil.normalizacao import normalizar_ncm, normalizar_texto  # noqa: E402
from agente_contabil.regras import REGIMES  # noqa: E402
from extrair_anexos_lc214 import RE_NCM  # noqa: E402

EXTRAIDO = Path("dados/brutos/extraido_lc214.csv")
REVOGADOS = Path("dados/brutos/extraido_revogados_lc214.csv")
ANEXOS = Path("dados/anexos_regimes.csv")
DESTINO = Path("dados/regras_ncm.csv")
CONFLITOS = Path("dados/brutos/conflitos.csv")
EXCECOES = Path("dados/brutos/excecoes.csv")
LIMITE_TEXTO = 600
COLUNAS = ["ncm_prefixo", "descricao", "palavras_chave", "regime", "reducao_percentual", "cclasstrib",
           "fundamento", "validado", "observacao", "texto_lei", "ressalva", "outros_produtos"]

AVISO_RESSALVA = ("O texto da lei traz exceção ou condição para este item (ex.: 'exceto', 'somente'): "
                  "leia o texto_lei e confirme se o produto se enquadra.")
AVISO_EXCECAO = ("Este NCM é EXCLUÍDO expressamente do benefício do anexo ('exceto' no texto da lei). "
                 "Se outro anexo listar este NCM, vale o outro. Confira o texto_lei.")
AVISO_COMPARTILHADO = ("Este NCM também constava do Anexo {anexo} (revogado): o benefício vigente vale só para o "
                       "produto descrito; para outros produtos deste NCM o regime vigente não foi identificado.")
OBS_GENERICA = "Descrição genérica (categoria do anexo): o texto da lei não traz o nome do produto nesta linha."
OBS_MULTI = "NCM listado em mais de um anexo, todos com o mesmo regime."

RE_SO_CODIGO = re.compile(r"^[\d\s.,;/e-]*$")
STOP = {"para", "com", "sem", "dos", "das", "uma", "que", "por", "nos", "nas", "aos", "como", "entre",
        "sobre", "desta", "deste", "esta", "este", "seus", "suas", "tais", "bem", "mais", "menos"}
CODIGOS = {"produto", "produtos", "codigo", "codigos", "ncm", "posicao", "posicoes", "subposicao", "subposicoes", "classificado",
           "classificados", "classificada", "classificadas", "item", "itens", "tipi", "capitulo", "alinea"}


def _significativas(texto: str) -> list[str]:
    return [t for t in normalizar_texto(texto).split()
            if len(t) >= 4 and t.isalpha() and t not in STOP and t not in CODIGOS]


def _cortar(texto: str, limite: int) -> str:
    if len(texto) <= limite:
        return texto
    return texto[:limite].rsplit(" ", 1)[0].rstrip(" ,;:-") + "…"


def categoria_do_anexo(titulo: str) -> str:
    """'PRODUTOS X SUBMETIDOS À REDUÇÃO...' -> 'Produtos x' (o que o anexo cobre, sem o regime)."""
    base = re.sub(r"\s+SUBMETID[OA]S?\b.*$", "", titulo, flags=re.IGNORECASE).strip()
    return _cortar(base[:1].upper() + base[1:].lower(), 90)


RE_EXCECAO = re.compile(r"\b(?:exceto|exclusive|salvo|ressalvad[oa]s?)\b", re.IGNORECASE)
RE_REFERENCIA = re.compile(r"\b(?:classificad[oa]s?\s+)?(?:d[oae]s?|n[oa]s?)\s+"
                           r"(?:subposi[cç][õo]es|subposi[cç][ãa]o|posi[cç][õo]es|posi[cç][ãa]o|c[óo]digos?)\b",
                           re.IGNORECASE)
RE_NCMSH = re.compile(r"\b(?:d[oa]s?\s+)?NCM(?:/SH)?\b", re.IGNORECASE)
RE_RESTO = re.compile(r"(?:[\s,;]+e)+[\s,;]*$|[\s,;]+$")


def _limpar_descricao(texto: str) -> str:
    """Tira restos de referência a códigos ('das subposições e e do código da NCM/SH') da descrição."""
    m = RE_EXCECAO.search(texto)
    if m and not _significativas(RE_NCMSH.sub(" ", RE_REFERENCIA.sub(" ", texto[m.end():]))):
        texto = texto[:m.start()]  # 'exceto' seguido só de códigos (já removidos): a lista não é descrição
    texto = RE_NCMSH.sub(" ", RE_REFERENCIA.sub(" ", texto))
    texto = re.sub(r"\s+", " ", texto)
    texto = RE_RESTO.sub("", texto).strip(" ,;:-–.")
    if texto.count(")") > texto.count("(") and texto.endswith(")"):
        texto = texto[:-1].rstrip(" ,;:-–.")  # ")" sobrando no fim (a abertura foi cortada)
    return texto


def descricao_da_linha(linha: str) -> str | None:
    """Nome do produto a partir de uma linha de TABELA ('item | descrição | NCM'); None se não houver.

    Linhas de texto corrido (sem ' | ') citam só códigos: o nome não está na linha."""
    if " | " not in linha:
        return None
    partes = [p.strip() for p in linha.split(" | ") if not RE_SO_CODIGO.match(p.strip())]
    texto = _limpar_descricao(re.sub(r"\s+", " ", RE_NCM.sub(" ", " ".join(partes))))
    return _cortar(texto, 120) if len(_significativas(texto)) >= 1 else None


def palavras_chave(descricao: str) -> str:
    vistas = []
    for t in _significativas(descricao):
        if t not in vistas:
            vistas.append(t)
    return ",".join(vistas[:8])


def _regra(prefixo: str, item: dict, anexo: dict, **extra) -> dict:
    """Monta uma linha do regras_ncm.csv a partir do item extraído e do anexo."""
    desc = descricao_da_linha(item["linha"])
    obs = [] if desc else [OBS_GENERICA]
    ressalva = [AVISO_RESSALVA] if item["situacao"] == "ressalva" else []
    linha = {
        "ncm_prefixo": prefixo,
        "descricao": desc or categoria_do_anexo(anexo["titulo_oficial"]),
        "palavras_chave": palavras_chave(desc) if desc else "",
        "regime": anexo["regime"], "reducao_percentual": anexo["reducao_percentual"],
        "cclasstrib": "", "fundamento": anexo["fundamento"], "validado": "nao",
        "observacao": " ".join(obs), "texto_lei": item["linha"], "ressalva": " ".join(ressalva),
        "outros_produtos": "",
    }
    linha.update(extra)
    return linha


RE_REVOGACAO = re.compile(r"\(\s*Revogad[oa][^)]*\)", re.IGNORECASE)


def gerar(itens: list[dict], anexos: dict[str, dict], revogados: list[dict] = ()) -> dict:
    """Pura (sem arquivos). itens = linhas do extraido_lc214.csv; anexos = chave -> linha da tabela;
    revogados = linhas do extraido_revogados_lc214.csv (NCMs que um anexo revogado listava)."""
    ignorados: Counter = Counter()
    por_prefixo: dict[str, list[dict]] = defaultdict(list)
    excecoes = []
    for it in itens:
        anexo = anexos.get(it["anexo"])
        if anexo is None or anexo["regime"] not in REGIMES:
            ignorados[it["anexo"]] += 1
            continue
        prefixo = normalizar_ncm(it["ncm"])
        (excecoes if it["situacao"] == "excecao" else por_prefixo[prefixo]).append(
            {**it, "prefixo": prefixo} if it["situacao"] == "excecao" else {**it, "_anexo": anexo})

    regras, conflitos = {}, []
    for prefixo, lista in por_prefixo.items():
        distintos = {}
        for it in lista:  # repetição dentro do mesmo anexo: fica a 1ª, mas a ressalva de qualquer uma vale
            atual = distintos.setdefault(it["anexo"], it)
            if it["situacao"] == "ressalva":
                atual["situacao"] = "ressalva"
        regimes = {(i["_anexo"]["regime"], i["_anexo"]["reducao_percentual"]) for i in distintos.values()}
        if len(regimes) > 1:
            conflitos += [{"ncm_prefixo": prefixo, "anexo": i["anexo"], "regime": i["_anexo"]["regime"],
                           "reducao_percentual": i["_anexo"]["reducao_percentual"], "linha": i["linha"]}
                          for i in distintos.values()]
            itens_conf = list(distintos.values())
            detalhe = "; ".join(f"Anexo {i['anexo']}: {i['_anexo']['regime']}" for i in itens_conf)
            regras[prefixo] = _regra(
                prefixo, itens_conf[0], {**itens_conf[0]["_anexo"], "regime": "a_confirmar", "reducao_percentual": "0",
                                         "fundamento": "; ".join(i["_anexo"]["fundamento"] for i in itens_conf)},
                observacao=f"A lei lista este NCM em anexos com regimes diferentes ({detalhe}). "
                           "Nenhum foi escolhido: confirme o enquadramento com um contador.",
                texto_lei=" || ".join(i["linha"] for i in itens_conf)[:LIMITE_TEXTO])
            continue
        primeiro = next(iter(distintos.values()))
        extra = {}
        if len(distintos) > 1:
            extra = {"fundamento": "; ".join(i["_anexo"]["fundamento"] for i in distintos.values()),
                     "observacao": OBS_MULTI}
        regras[prefixo] = _regra(prefixo, primeiro, primeiro["_anexo"], **extra)

    # NCM excluído por "exceto": só vira regra `padrao` quando há um prefixo-pai com benefício que o
    # cobriria por engano. Sem pai, não há o que proteger e a leitura da lei pode estar errada: sem regra
    # (o agente avisa que não achou regra), e o NCM fica em excecoes.csv para revisão.
    conflitados = {c["ncm_prefixo"] for c in conflitos}
    sem_pai = []
    for ex in excecoes:
        p = ex["prefixo"]
        if p in regras or p in conflitados:
            continue  # outro anexo trata este NCM de forma específica: vale o outro
        pais = [regras[p[:n]] for n in range(2, len(p)) if p[:n] in regras]
        if not any(r["regime"] != "padrao" for r in pais):
            sem_pai.append(ex)
            continue
        anexo = anexos[ex["anexo"]]
        regras[p] = _regra(p, {**ex, "situacao": "ressalva"},
                           {**anexo, "regime": "padrao", "reducao_percentual": "0",
                            "fundamento": f"{anexo['fundamento']} (exceção expressa)"},
                           ressalva=AVISO_EXCECAO)
    # NCM que só constava de anexo REVOGADO: o regime vigente não está na base. Em vez de cair em
    # "alíquota padrão presumida" (provavelmente errada), vira a_confirmar, sem alíquota.
    revogados_a_confirmar = compartilhados = 0
    for it in revogados:
        p = normalizar_ncm(it["ncm"])
        anexo = anexos.get(it["anexo"])
        if anexo is None or it["situacao"] == "excecao":
            continue
        if p in regras:
            vigente = regras[p]
            if vigente["regime"] not in ("a_confirmar", "padrao") and not vigente["outros_produtos"]:
                # o código é compartilhado: a regra vigente vale só para o produto descrito
                vigente["outros_produtos"] = "a_confirmar"
                vigente["ressalva"] = (vigente["ressalva"] + " " + AVISO_COMPARTILHADO.format(
                    anexo=anexo["anexo"])).strip()
                compartilhados += 1
            continue
        m = RE_REVOGACAO.search(anexo["titulo_oficial"])
        aviso = m.group(0) if m else "(revogado)"
        regras[p] = _regra(
            p, it, {**anexo, "regime": "a_confirmar", "reducao_percentual": "0",
                    "fundamento": f"{anexo['fundamento']} (revogado)"},
            observacao=f"Este NCM constava do Anexo {anexo['anexo']}, revogado {aviso.strip('()').replace('Revogado', '').strip()}. "
                       "O regime vigente NÃO está na base: confirme na legislação atual com um contador.")
        revogados_a_confirmar += 1
    return {"revogados_a_confirmar": revogados_a_confirmar, "compartilhados": compartilhados,
            "regras": [regras[p] for p in sorted(regras)], "conflitos": conflitos,
            "excecoes": excecoes, "excecoes_sem_pai": sem_pai, "ignorados": ignorados}


def aninhados_com_regime_diferente(regras: list[dict]) -> list[tuple[str, str]]:
    """Pares (prefixo curto, prefixo longo) em que o mais longo tem regime diferente (vale o mais longo)."""
    por = {r["ncm_prefixo"]: r for r in regras}
    return [(p[:n], p) for p in por for n in range(2, len(p)) if p[:n] in por
            and (por[p[:n]]["regime"], por[p[:n]]["reducao_percentual"]) != (por[p]["regime"], por[p]["reducao_percentual"])]


def _ler_csv(caminho: Path) -> list[dict]:
    with open(caminho, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def _gravar(caminho: Path, colunas: list[str], linhas: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=colunas, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(linhas)


def main(sobrescrever: bool) -> None:
    for arq in (EXTRAIDO, ANEXOS):
        if not arq.exists():
            sys.exit(f"Falta {arq}. Rode antes extrair_anexos_lc214.py e gerar_anexos_regimes.py.")
    if DESTINO.exists() and not sobrescrever:
        if any(l.get("validado", "").lower() in ("sim", "s") for l in _ler_csv(DESTINO)):
            sys.exit(f"{DESTINO} tem regras validado=sim (revisão de contador). Use --sobrescrever só se tiver certeza.")
    anexos = {a["anexo"]: a for a in _ler_csv(ANEXOS)}
    r = gerar(_ler_csv(EXTRAIDO), anexos, _ler_csv(REVOGADOS) if REVOGADOS.exists() else [])
    _gravar(DESTINO, COLUNAS, r["regras"])
    _gravar(CONFLITOS, ["ncm_prefixo", "anexo", "regime", "reducao_percentual", "linha"], r["conflitos"])
    _gravar(EXCECOES, ["anexo", "ncm", "linha"], r["excecoes"])

    regras = r["regras"]
    print(f"{len(regras)} regras -> {DESTINO}")
    print("  por regime:", dict(Counter(x["regime"] for x in regras)))
    print("  por anexo :", dict(Counter(x["fundamento"].replace("LC 214/2025, ", "")[:30] for x in regras)))
    print(f"  com descrição genérica (nome do produto não está na linha): {sum(x['observacao'] == OBS_GENERICA for x in regras)}")
    print(f"  com ressalva obrigatória: {sum(bool(x['ressalva']) for x in regras)}")
    print(f"  regras 'padrao' criadas por exceção expressa ('exceto'): {sum('exceção expressa' in x['fundamento'] for x in regras)}")
    print(f"  NCMs em exceção ('exceto' do texto da lei): {len(r['excecoes'])} -> {EXCECOES}")
    print(f"    sem prefixo-pai beneficiado (sem regra; revisar): {len(r['excecoes_sem_pai'])}")
    print(f"  conflitos (NCM em anexos com regimes diferentes): {len({c['ncm_prefixo'] for c in r['conflitos']})} NCMs "
          f"-> regra a_confirmar (sem alíquota) + {CONFLITOS}")
    print(f"  NCMs de anexo revogado, sem tratamento vigente na base -> a_confirmar: {r['revogados_a_confirmar']}")
    print(f"  regras vigentes cujo NCM também constava do anexo revogado (outros produtos -> a_confirmar): {r['compartilhados']}")
    print(f"  anexos ignorados (regime a_definir/revogado): {dict(r['ignorados']) or 'nenhum'}")
    nest = aninhados_com_regime_diferente(regras)
    print(f"  prefixos aninhados com regime diferente (vale o mais longo): {len(nest)}")

    # detalhes (só códigos, anexos e regimes — sem texto da lei) para revisão
    por = {x["ncm_prefixo"]: x["regime"] for x in regras}
    print(f"  prefixos incompletos (5 ou 7 dígitos; benefício só para o produto descrito): "
          f"{sum(len(x['ncm_prefixo']) in (5, 7) for x in regras)}")
    conf = defaultdict(list)
    for c in r["conflitos"]:
        conf[c["ncm_prefixo"]].append(f"Anexo {c['anexo']}={c['regime']}")
    if conf:
        print("\nCONFLITOS (regra a_confirmar, sem alíquota):")
        for k, v in conf.items():
            print(f"  {k:9} " + " x ".join(v))
    if nest:
        print("\nPREFIXOS ANINHADOS (pai > filho):")
        for pai, filho in nest:
            print(f"  {pai:8} ({por[pai]}) > {filho:9} ({por[filho]})")
    if r["excecoes"]:
        sem = {e["prefixo"] for e in r["excecoes_sem_pai"]}
        print(f"\nNCMs em exceção sem regra (sem prefixo-pai beneficiado): {', '.join(sorted(sem)) or 'nenhum'}")


if __name__ == "__main__":
    main("--sobrescrever" in sys.argv)
