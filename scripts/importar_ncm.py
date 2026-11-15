"""Importa a tabela OFICIAL da NCM (Receita/Siscomex) para dados/ncm_tabela.csv.

Baixar (arquivo público, fora do projeto):
  curl -L -o ncm.json "https://portalunico.siscomex.gov.br/classif/api/publico/nomenclatura/download/json?perfil=PUBLICO"
Importar:
  python -I scripts/importar_ncm.py ncm.json [--fonte URL]

O arquivo baixado é dado externo: este script só lê JSON (nunca executa nada dele) e valida a estrutura.
As descrições da NCM são hierárquicas ('Outros', 'Polido ou brunido'): o CSV guarda também o texto COMPLETO,
juntando as descrições dos níveis acima ('Arroz > Descascado > Polido ou brunido').
"""
import csv
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

DESTINO = Path("dados/ncm_tabela.csv")
META = Path("dados/ncm_tabela_meta.json")
COLUNAS = ["codigo", "nivel", "descricao", "completa"]
FONTE_PADRAO = "https://portalunico.siscomex.gov.br/classif/api/publico/nomenclatura/download/json?perfil=PUBLICO"


def limpar(descricao: str) -> str:
    """Tira marcação HTML (<i>), entidades, travessões de nível ('- -') e pontuação final."""
    texto = html.unescape(re.sub(r"<[^>]+>", "", descricao or ""))
    texto = re.sub(r"^[\s\-–]+", "", texto)
    return re.sub(r"\s+", " ", texto).strip(" :.;")


def montar(itens: list[dict]) -> list[dict]:
    """Uma linha por código (qualquer nível), com a descrição completa pela cadeia de prefixos."""
    local = {}
    for it in itens:
        digitos = re.sub(r"\D", "", str(it.get("Codigo", "")))
        if digitos and it.get("Data_Fim", "").endswith("9999"):  # só vigentes
            local[digitos] = (it["Codigo"], limpar(it.get("Descricao", "")))
    linhas = []
    for digitos in sorted(local):
        cadeia = [local[digitos[:n]][1] for n in range(4, len(digitos)) if digitos[:n] in local]  # sem o capítulo (2 dígitos)
        cadeia.append(local[digitos][1])
        linhas.append({"codigo": local[digitos][0], "nivel": len(digitos), "descricao": local[digitos][1],
                       "completa": " > ".join(c for c in cadeia if c)})
    return linhas


def main(arquivo: str, fonte: str) -> None:
    dados = json.loads(Path(arquivo).read_text(encoding="utf-8"))
    itens = dados.get("Nomenclaturas") if isinstance(dados, dict) else None
    if not itens or not all({"Codigo", "Descricao"} <= set(i) for i in itens[:50]):
        sys.exit("Estrutura inesperada: esperava {'Nomenclaturas': [{'Codigo', 'Descricao', ...}]}.")
    linhas = montar(itens)
    with open(DESTINO, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS, delimiter=";")
        w.writeheader()
        w.writerows(linhas)
    META.write_text(json.dumps({"vigencia": dados.get("Data_Ultima_Atualizacao_NCM", ""), "ato": dados.get("Ato", ""),
                                "fonte": fonte, "importado_em": date.today().isoformat(),
                                "codigos": len(linhas)}, ensure_ascii=False, indent=2), encoding="utf-8")
    por_nivel = {}
    for l in linhas:
        por_nivel[l["nivel"]] = por_nivel.get(l["nivel"], 0) + 1
    print(f"{len(linhas)} códigos -> {DESTINO} | {dados.get('Data_Ultima_Atualizacao_NCM', '')} | {dados.get('Ato', '')}")
    print("  por nível (dígitos):", dict(sorted(por_nivel.items())))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--fonte")]
    fonte = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--fonte=")), FONTE_PADRAO)
    if len(args) != 1:
        sys.exit(__doc__)
    main(args[0], fonte)
