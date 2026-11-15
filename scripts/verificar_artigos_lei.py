"""Confere afirmações jurídicas contra o TEXTO DA LEI do projeto (dados/brutos/Lcp 214.html).

Uso (rode você; a leitura de dados/brutos/ é bloqueada para o agente):
  python scripts/verificar_artigos_lei.py            # só verdadeiro/falso
  python scripts/verificar_artigos_lei.py --trechos  # inclui ~240 caracteres em torno do 1º termo achado

Cada afirmação vem de uma nota escrita fora do projeto (artigos, prazos, notas técnicas) e NÃO verificada.
O resultado diz, para cada artigo, quais termos aparecem ou não. Termo ausente = a nota não se sustenta
naquele artigo. Também conta texto riscado por CSS no HTML (o extrator só trata <s>, <strike> e <del>).
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extrair_anexos_lc214 import ler_texto  # noqa: E402

ARQUIVO = Path("dados/brutos/Lcp 214.html")

# (artigo, afirmação a verificar, termos que devem aparecer no artigo)
AFIRMACOES = [
    (146, "alíquota zero para soros, vacinas e tratamento de diabetes", ["soro", "vacina", "diabet", "alíquota zero"]),
    (146, "lista/ato periódico (120 dias ou quadrimestral)", ["120", "quadrimestr"]),
    (146, "condicionado a registro na Anvisa e a adquirentes SUS/CEBAS/Farmácia Popular", ["anvisa", "sus", "cebas", "farmácia popular"]),
    (133, "redução de 60% para medicamentos registrados na Anvisa", ["60%", "medicament", "anvisa"]),
    (15, "piso das alíquotas próprias (Anexo XVI)", ["anexo xvi", "alíquota de referência"]),
    (409, "Imposto Seletivo (Anexo XVII)", ["imposto seletivo", "anexo xvii"]),
]
# termos que a nota atribui à lei: só aparecem se a lei realmente os contém
TERMOS_GERAIS = ["tcu", "11,3", "nota técnica", "redutor", "resolução do senado", "227"]


def extrair_artigo(texto: str, numero: int, limite: int = 12000) -> str | None:
    """Texto (minúsculo) do artigo `numero`, do 'Art. N' até o 'Art. N+1' (ou `limite` caracteres)."""
    inicio = re.search(rf"(?m)^\s*Art\.\s*{numero}\s*[º°o.]*\s", texto)
    if not inicio:
        return None
    fim = re.search(rf"(?m)^\s*Art\.\s*{numero + 1}\s*[º°o.]*\s", texto[inicio.end():])
    return texto[inicio.start(): inicio.end() + (fim.start() if fim else limite)].lower()


def checar(artigo: str | None, termos: list[str]) -> dict[str, bool] | None:
    return None if artigo is None else {t: t in artigo for t in termos}


def trecho(artigo: str, termo: str, largura: int = 120) -> str:
    i = artigo.find(termo)
    return " ".join(artigo[max(0, i - largura): i + largura].split()) if i >= 0 else ""


def contar_riscado_css(html: str) -> dict[str, int]:
    h = html.lower()
    return {"<strike>": h.count("<strike"), "<s>": h.count("<s>"), "<del>": h.count("<del"),
            "line-through": len(re.findall(r"line-through", h)),
            "text-decoration (qualquer)": len(re.findall(r"text-decoration\s*:", h))}


def main(com_trechos: bool) -> None:
    if not ARQUIVO.exists():
        sys.exit(f"{ARQUIVO} não encontrado (rode na raiz do projeto).")
    texto = ler_texto(ARQUIVO)
    print("=== A) Afirmações da nota, conferidas no texto da lei ===")
    for numero, afirmacao, termos in AFIRMACOES:
        artigo = extrair_artigo(texto, numero)
        resultado = checar(artigo, termos)
        if resultado is None:
            print(f"Art. {numero}: NÃO ENCONTRADO no texto  |  {afirmacao}")
            continue
        marca = "SUSTENTADA" if all(resultado.values()) else "NÃO SUSTENTADA (termo ausente)"
        print(f"Art. {numero} ({len(artigo)} caracteres): {marca}  |  {afirmacao}")
        print("   " + ", ".join(f"'{t}'={'sim' if ok else 'NÃO'}" for t, ok in resultado.items()))
        if com_trechos:
            achado = next((t for t, ok in resultado.items() if ok), None)
            if achado:
                print(f"   trecho ('{achado}'): ...{trecho(artigo, achado)}...")
    print("\n=== B) Termos que a nota atribui à lei, procurados no texto inteiro ===")
    baixo = texto.lower()
    print("   " + ", ".join(f"'{t}'={'sim' if t in baixo else 'NÃO'}" for t in TERMOS_GERAIS))
    print("\n=== C) Texto riscado no HTML (o extrator só trata <s>, <strike>, <del>) ===")
    for chave, n in contar_riscado_css(ARQUIVO.read_bytes().decode("utf-8", errors="replace")).items():
        print(f"   {chave}: {n}")


if __name__ == "__main__":
    main("--trechos" in sys.argv)
