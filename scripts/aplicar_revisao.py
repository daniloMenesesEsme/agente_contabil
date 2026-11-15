"""Aplica as decisões do contador (dados/revisao_contador.csv preenchido) em regras_ncm.csv e regras_servicos.csv.

Uso:
  python scripts/aplicar_revisao.py            # SIMULA: mostra o que faria e os erros, não grava nada
  python scripts/aplicar_revisao.py --aplicar  # grava (só se NÃO houver nenhum erro)

decisao: confirmar -> validado=sim | corrigir -> novo regime (regime_correto) + validado=sim | excluir -> remove a linha.
Regras de segurança:
- um regime `a_confirmar` NÃO pode ser 'confirmado': precisa de 'corrigir' com regime_correto;
- regime_correto só pode ser aliquota_zero, reducao_60, reducao_30 ou padrao (com a redução correspondente);
- qualquer erro aborta tudo (nada é gravado pela metade);
- linhas de tipo anexo/simples/sinonimo/aviso/parametro NÃO são aplicadas: saem na lista "manual".
"""
import csv
import sys
from pathlib import Path

DADOS = Path("dados")
PLANILHA = DADOS / "revisao_contador.csv"
REDUCAO = {"aliquota_zero": "100", "reducao_60": "60", "reducao_30": "30", "padrao": "0"}
DECISOES = {"confirmar", "corrigir", "excluir"}
APLICAVEIS = {"regra_ncm": ("ncm_prefixo", DADOS / "regras_ncm.csv"), "servico": ("item", DADOS / "regras_servicos.csv")}


def aplicar(decisoes: list[dict], bases: dict[str, list[dict]]) -> tuple[dict, list[str], list[str]]:
    """Pura. decisoes = linhas da planilha; bases = {tipo_dado: linhas do CSV}.
    Devolve (bases_novas, relatorio, erros). Se houver erros, as bases devem ser descartadas."""
    novas = {t: [dict(l) for l in linhas] for t, linhas in bases.items()}
    relatorio, erros = [], []
    for d in decisoes:
        decisao = (d.get("decisao") or "").strip().lower()
        if not decisao:
            continue
        tipo, chave = d["tipo_dado"], d["chave"]
        rotulo = f"{tipo} {chave}"
        if decisao not in DECISOES:
            erros.append(f"{rotulo}: decisão inválida '{decisao}' (use confirmar, corrigir ou excluir)")
            continue
        if tipo not in APLICAVEIS:
            relatorio.append(f"MANUAL  {rotulo}: {decisao} — {d.get('observacao_contador', '')[:120]}")
            continue
        campo = APLICAVEIS[tipo][0]
        alvo = [l for l in novas[tipo] if l[campo] == chave]
        if len(alvo) != 1:
            erros.append(f"{rotulo}: encontrei {len(alvo)} linhas na base (esperava 1)")
            continue
        linha, obs = alvo[0], (d.get("observacao_contador") or "").strip()
        if decisao == "excluir":
            novas[tipo].remove(linha)
            relatorio.append(f"EXCLUIR {rotulo}")
        elif decisao == "confirmar":
            if linha["regime"] == "a_confirmar":
                erros.append(f"{rotulo}: regime a_confirmar não pode ser 'confirmar'; use 'corrigir' com regime_correto")
                continue
            linha["validado"] = "sim"
            relatorio.append(f"CONFIRMAR {rotulo} ({linha['regime']})")
        else:
            regime = (d.get("regime_correto") or "").strip()
            if regime not in REDUCAO:
                erros.append(f"{rotulo}: regime_correto '{regime}' inválido (use {', '.join(REDUCAO)})")
                continue
            antes = linha["regime"]
            linha["regime"], linha["reducao_percentual"], linha["validado"] = regime, REDUCAO[regime], "sim"
            if antes == "a_confirmar":
                linha["observacao"] = "Regime definido na revisão do contador." + (f" {obs}" if obs else "")
            elif obs:
                linha["observacao"] = (linha.get("observacao", "") + f" Revisão do contador: {obs}").strip()
            relatorio.append(f"CORRIGIR {rotulo}: {antes} -> {regime}")
    return novas, relatorio, erros


def _ler(caminho: Path, enc: str = "utf-8") -> tuple[list[str], list[dict]]:
    with open(caminho, encoding=enc, newline="") as f:
        leitor = csv.DictReader(f, delimiter=";")
        return list(leitor.fieldnames), list(leitor)


def main(gravar: bool) -> None:
    if not PLANILHA.exists():
        sys.exit(f"{PLANILHA} não existe. Rode scripts/gerar_planilha_revisao.py e peça ao contador para preencher.")
    _, decisoes = _ler(PLANILHA, "utf-8-sig")
    colunas, bases = {}, {}
    for tipo, (_, caminho) in APLICAVEIS.items():
        colunas[tipo], bases[tipo] = _ler(caminho)
    novas, relatorio, erros = aplicar(decisoes, bases)
    preenchidas = sum(bool((d.get("decisao") or "").strip()) for d in decisoes)
    print(f"{preenchidas} decisões preenchidas de {len(decisoes)} itens")
    print("\n".join(relatorio) or "(nenhuma decisão aplicável)")
    if erros:
        print("\nERROS (nada foi gravado):\n  " + "\n  ".join(erros))
        sys.exit(1)
    if not gravar:
        print("\nSimulação: nada gravado. Use --aplicar para gravar.")
        return
    for tipo, (_, caminho) in APLICAVEIS.items():
        with open(caminho, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=colunas[tipo], delimiter=";")
            w.writeheader()
            w.writerows(novas[tipo])
    print("\nGravado. Rode: python scripts/validar_regras.py && pytest -q")


if __name__ == "__main__":
    main("--aplicar" in sys.argv)
