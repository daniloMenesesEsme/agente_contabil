"""Extrai NCMs dos anexos da LC 214/2025 para um CSV de REVISÃO.

Aceita a página oficial do Planalto salva como HTML (recomendado) ou um PDF com texto.

Uso:
  python scripts/extrair_anexos_lc214.py dados/brutos/lc214.htm
  python scripts/extrair_anexos_lc214.py dados/brutos/lc214.pdf

Gera dados/brutos/extraido_lc214.csv. NÃO altera regras_ncm.csv:
um contador deve revisar e copiar as linhas validadas (validado=sim).
"""
import csv
import re
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

# Título de anexo: linha contendo só "ANEXO I", "ANEXO XII" etc. (maiúsculas, como na lei)
RE_ANEXO = re.compile(r"^\s*ANEXO\s+([IVXL]+)\s*$")
# NCM: 1006.20 | 0401.10.10 | 10063021 | 1905 (4 dígitos sem ponto)
RE_NCM = re.compile(r"(?<![\d./])(\d{4}(?:\.\d{1,2}){1,2}|\d{8}|\d{4})(?![\d/]|\.\d)")
# 4 dígitos que na verdade são anos: "de 2025", "Lei nº 1.234/2025" etc.
RE_ANO = re.compile(r"(?:de|em|ano|/)\s*$", re.IGNORECASE)
# Marca inserida onde começa uma <table> no HTML (a linha com título termina nela)
MARCA_TABELA = "\ue000"
# Cabeçalho de tabela de NCMs (para PDF, que não tem a marca): "NCM", "CÓDIGO", "DESCRIÇÃO"...
RE_CABECALHO = re.compile(r"^(NCM|C[ÓO]DIGO|ITEM|DESCRI[ÇC][ÃA]O)\b")
LIMITE_TITULO = 300
# Anexos que alteram a LC 123 (Simples Nacional / MEI) reaproveitam a numeração I, II, III...
# da LC 214, mas não têm NCMs: são identificados pelo título, não pelo número.
RE_SIMPLES = re.compile(r"simples nacional|microempreendedor", re.IGNORECASE)


class _Texto(HTMLParser):
    """Converte HTML em texto, quebrando linha em parágrafos e células de tabela.

    Descarta o conteúdo riscado (<strike>, <s>, <del>): o Planalto marca assim o texto
    revogado ou alterado. Tags aninhadas são tratadas por contagem de profundidade.
    """
    QUEBRA = {"p", "br", "tr", "div", "li", "h1", "h2", "h3", "h4"}
    RISCADO = {"strike", "s", "del"}

    def __init__(self):
        super().__init__()
        self.partes: list[str] = []
        self._riscado = 0  # profundidade de tags de riscado abertas
        self._celulas = 0  # células já abertas na linha de tabela atual
        self._em_celula = 0  # profundidade de <td>/<th> abertas (parágrafos dentro da célula não quebram linha)

    def handle_starttag(self, tag, attrs):
        if tag in self.RISCADO:
            self._riscado += 1
        elif tag == "table":
            self.partes.append(f"\n{MARCA_TABELA}\n")
            self._celulas = 0
        elif tag in ("td", "th"):
            if self._celulas:
                self.partes.append(" | ")  # células da mesma linha ficam juntas (NCM + descrição)
            self._celulas += 1
            self._em_celula += 1
        elif tag in self.QUEBRA:
            if tag == "tr":
                self.partes.append("\n")
                self._celulas = 0
                self._em_celula = 0
            else:
                self.partes.append(" " if self._em_celula else "\n")

    def handle_endtag(self, tag):
        if tag in self.RISCADO and self._riscado > 0:
            self._riscado -= 1
        elif tag in ("td", "th") and self._em_celula > 0:
            self._em_celula -= 1

    def handle_data(self, data):
        if self._riscado == 0:
            # quebra de linha no código-fonte do HTML é só espaço: só as tags quebram linha
            self.partes.append(re.sub(r"\s+", " ", data.replace("\xa0", " ")))

    def texto(self) -> str:
        return "".join(self.partes)


def ler_texto(caminho: Path) -> str:
    if caminho.suffix.lower() in (".htm", ".html"):
        bruto = caminho.read_bytes()
        try:
            html = bruto.decode("utf-8")
        except UnicodeDecodeError:
            html = bruto.decode("latin-1")  # o Planalto costuma usar Windows-1252
        p = _Texto()
        p.feed(html)
        return p.texto()
    import pdfplumber
    with pdfplumber.open(caminho) as doc:
        return "\n".join(pg.extract_text() or "" for pg in doc.pages)


def achados_ncm_pos(linha: str) -> list[tuple[str, int]]:
    """(NCM, posição na linha) de cada NCM, descartando números de 4 dígitos que são anos."""
    saida = []
    for achado in RE_NCM.finditer(linha):
        ncm = achado.group(1)
        if "." not in ncm and len(ncm) == 4 and RE_ANO.search(linha[:achado.start()]):
            continue
        saida.append((ncm, achado.start()))
    return saida


def achados_ncm(linha: str) -> list[str]:
    """NCMs de uma linha, descartando números de 4 dígitos que são anos."""
    return [ncm for ncm, _ in achados_ncm_pos(linha)]


# "exceto os produtos da subposição 0306.11": NCMs depois disso NÃO têm o benefício.
RE_EXCECAO = re.compile(r"\b(exceto|exclusive|salvo|ressalvad[oa]s?|exclu[ií]d[oa]s?)\b", re.IGNORECASE)
# Condições que restringem o benefício: o agente deve avisar, mas o NCM continua na regra.
RE_CONDICAO = re.compile(r"\b(somente|apenas|desde que|quando)\b", re.IGNORECASE)
LIMITE_LINHA = 500  # tamanho máximo do texto da lei guardado por NCM
MAX_LINHAS_EXCECAO = 3  # a lista de exceções pode continuar nas linhas seguintes (texto corrido)


def eh_simples(titulo: str) -> bool:
    """True se o título é de anexo do Simples Nacional/MEI (alteração da LC 123)."""
    return bool(RE_SIMPLES.search(titulo))


def _titulo_completo(linhas: list[str], inicio: int) -> str:
    """Junta as linhas após 'ANEXO X' até a 1ª tabela, NCM, cabeçalho de tabela ou próximo anexo."""
    partes: list[str] = []
    for linha in linhas[inicio:]:
        if not linha:
            continue
        if (MARCA_TABELA in linha or RE_ANEXO.match(linha) or RE_CABECALHO.match(linha)
                or achados_ncm(linha)):
            break
        partes.append(" ".join(linha.split()))
        if len(" ".join(partes)) >= LIMITE_TITULO:
            break
    return " ".join(partes)[:LIMITE_TITULO]


def _chave(numeral: str, titulo: str, usadas: set[str]) -> str:
    """Identificador único do anexo. A lei repete a numeração (LC 214 x Simples x MEI): o mesmo
    número com conteúdo diferente ganha prefixo (SN-, MEI-) e, se ainda colidir, sufixo -2, -3..."""
    if "microempreendedor" in titulo.lower():
        base = f"MEI-{numeral}"
    elif eh_simples(titulo):
        base = f"SN-{numeral}"
    else:
        base = numeral
    chave, n = base, 1
    while chave in usadas:
        n += 1
        chave = f"{base}-{n}"
    usadas.add(chave)
    return chave


def ocorrencias_anexos(texto: str) -> list[dict]:
    """Uma entrada por cabeçalho 'ANEXO X', na ordem do texto:
    {chave, anexo, titulo, tipo, inicio, fim, corpo, ncms, exemplos}. `chave` é única."""
    linhas = [l.strip() for l in texto.splitlines()]
    cabecalhos = [i for i, l in enumerate(linhas) if RE_ANEXO.match(l)]
    saida, usadas = [], set()
    for k, i in enumerate(cabecalhos):
        fim = cabecalhos[k + 1] if k + 1 < len(cabecalhos) else len(linhas)
        numeral = RE_ANEXO.match(linhas[i]).group(1)
        titulo = _titulo_completo(linhas, i + 1)
        com_ncm = [" ".join(l.split())[:300] for l in linhas[i + 1:fim] if achados_ncm(l)]
        saida.append({
            "chave": _chave(numeral, titulo, usadas),
            "anexo": numeral,
            "titulo": titulo,
            "tipo": "simples_mei" if eh_simples(titulo) else "lc214",
            "inicio": i,
            "fim": fim,
            "corpo": [" ".join(l.split())[:300] for l in linhas[i + 1:fim]
                      if l and MARCA_TABELA not in l],
            "ncms": sum(len(achados_ncm(l)) for l in linhas[i + 1:fim]),
            "exemplos": com_ncm[:2],
        })
    return saida


def _escopo_excecao(texto: str, inicio: int) -> int:
    """Fim do alcance de um 'exceto' que começa em `inicio`.

    Entre parênteses — "Carnes (exceto foie gras), códigos 0201..." — vale só até o ')': o que vem
    depois é a lista dos itens INCLUÍDOS. Sem parênteses, vale até o fim do texto (célula/linha)."""
    if texto[:inicio].count("(") > texto[:inicio].count(")"):
        fecha = texto.find(")", inicio)
        return fecha if fecha != -1 else len(texto)
    return len(texto)


def _situacao_em_tabela(linha: str, pos: int) -> str:
    """Linha de tabela ('item | descrição | NCM'): 'exceto' só exclui NCM da MESMA célula, depois dele.

    Um 'exceto' na célula de descrição qualifica o item (ressalva), não exclui o NCM da coluna ao lado."""
    inicio = 0
    for celula in linha.split(" | "):
        fim = inicio + len(celula)
        if inicio <= pos <= fim:
            m = RE_EXCECAO.search(celula)
            if m and m.start() < pos - inicio <= _escopo_excecao(celula, m.start()):
                return "excecao"
            break
        inicio = fim + 3
    if RE_EXCECAO.search(linha) or RE_CONDICAO.search(linha):
        return "ressalva"
    return ""


def extrair_linhas(texto: str, excluir: frozenset[str] = frozenset(),
                   apenas: frozenset[str] | None = None) -> list[dict]:
    """Devolve {anexo, ncm, linha, situacao} para cada NCM de cada anexo da LC 214.

    `anexo` é a chave única. `situacao`: "" (sem restrição), "ressalva" (a linha traz exceção ou
    condição) ou "excecao" (o NCM aparece depois de 'exceto...': está EXCLUÍDO do benefício).
    Pula as chaves em `excluir` (ex.: revogados) e os anexos do Simples/MEI, que não trazem NCMs.
    Com `apenas`, processa SOMENTE essas chaves (usado para listar o que um anexo revogado continha)."""
    linhas = texto.splitlines()
    saida = []
    for oc in ocorrencias_anexos(texto):
        if oc["tipo"] != "lc214" or (oc["chave"] not in apenas if apenas is not None else oc["chave"] in excluir):
            continue
        restantes = 0  # linhas de texto corrido ainda dentro de uma lista de exceções
        for linha in linhas[oc["inicio"] + 1:oc["fim"]]:
            em_tabela = " | " in linha
            m = RE_EXCECAO.search(linha)
            for ncm, pos in achados_ncm_pos(linha):
                if em_tabela:
                    situacao = _situacao_em_tabela(linha, pos)
                elif (m and m.start() < pos <= _escopo_excecao(linha, m.start())) or (restantes and not m):
                    situacao = "excecao"
                elif m or RE_CONDICAO.search(linha):
                    situacao = "ressalva"
                else:
                    situacao = ""
                saida.append({"anexo": oc["chave"], "ncm": ncm, "situacao": situacao,
                              "linha": " ".join(linha.split())[:LIMITE_LINHA]})
            fim_de_frase = linha.rstrip().endswith((".", ";"))
            if em_tabela or fim_de_frase:
                restantes = 0
            elif m:
                # só continua na linha seguinte se o alcance do 'exceto' vai até o fim desta linha
                restantes = MAX_LINHAS_EXCECAO if _escopo_excecao(linha, m.start()) == len(linha) else 0
            elif restantes:
                restantes -= 1
    return saida


def titulos_anexos(texto: str) -> dict[str, dict]:
    """Para cada chave de anexo: {anexo (numeral), titulo oficial completo, tipo}."""
    return {oc["chave"]: {"anexo": oc["anexo"], "titulo": oc["titulo"], "tipo": oc["tipo"]}
            for oc in ocorrencias_anexos(texto)}


def linhas_simples(texto: str) -> list[dict]:
    """Linhas dos anexos do Simples/MEI, cruas, para revisão: {anexo (chave), titulo, linha}."""
    return [{"anexo": oc["chave"], "titulo": oc["titulo"], "linha": l}
            for oc in ocorrencias_anexos(texto) if oc["tipo"] == "simples_mei"
            for l in oc["corpo"]]


def anexos_revogados(titulos: dict[str, dict]) -> list[str]:
    """Anexos cujo título contém 'Revogado' (na ordem em que aparecem na lei)."""
    return [nome for nome, info in titulos.items() if "revogad" in info["titulo"].lower()]


def main(arquivo: str) -> None:
    caminho = Path(arquivo)
    texto = ler_texto(caminho)
    if len(texto.strip()) < 1000:
        sys.exit("Quase nenhum texto lido. O PDF pode ser uma imagem (escaneado). "
                 "Use a página do Planalto salva como HTML.")
    titulos = titulos_anexos(texto)
    revogados = anexos_revogados(titulos)
    linhas = extrair_linhas(texto, frozenset(revogados))
    destino = Path("dados/brutos/extraido_lc214.csv")
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["anexo", "ncm", "situacao", "linha"], delimiter=";")
        w.writeheader()
        w.writerows(linhas)
    destino_rev = Path("dados/brutos/extraido_revogados_lc214.csv")
    revogadas = extrair_linhas(texto, apenas=frozenset(revogados))
    with open(destino_rev, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["anexo", "ncm", "situacao", "linha"], delimiter=";")
        w.writeheader()
        w.writerows(revogadas)
    simples = linhas_simples(texto)
    destino_simples = Path("dados/brutos/extraido_simples_lc214.csv")
    with open(destino_simples, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["anexo", "titulo", "linha"], delimiter=";")
        w.writeheader()
        w.writerows(simples)
    anexos = Counter(l["anexo"] for l in linhas)
    ocs = ocorrencias_anexos(texto)
    print(f"{len(texto):,} caracteres lidos | {len(linhas)} NCMs extraídos -> {destino}")
    for nome, qtd in anexos.items():
        print(f"  Anexo {nome}: {qtd} NCMs | {titulos.get(nome, {}).get('titulo', '')}")
    for oc in ocs:
        if oc["tipo"] == "simples_mei":
            print(f"  Anexo {oc['chave']} (Simples/MEI, fora das regras de NCM): "
                  f"{len(oc['corpo'])} linhas -> {destino_simples} | {oc['titulo']}")
    for oc in ocs:
        if oc["tipo"] == "lc214" and oc["chave"] not in anexos and oc["chave"] not in revogados:
            print(f"  Anexo {oc['chave']}: sem NCMs (a conferir na Etapa 3) | {oc['titulo']}")
    for nome in revogados:
        qtd_rev = sum(l["anexo"] == nome for l in revogadas)
        print(f"  Anexo {nome}: revogado (excluído das regras; {qtd_rev} NCMs listados em {destino_rev}) "
              f"| {titulos[nome]['titulo']}")
    if not linhas:
        print("Nenhum NCM: confira se o arquivo contém os ANEXOS da lei (ficam no final do texto).")
    else:
        print("Revise o CSV antes de usar.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
