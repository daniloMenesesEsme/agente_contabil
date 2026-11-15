"""Uso:
  python -m agente_contabil.cli ncm 10063021 [--ano 2027]
  python -m agente_contabil.cli buscar "feijão"
  python -m agente_contabil.cli lote produtos_erp.csv [--ano 2027] [--saida resultado.csv]
  python -m agente_contabil.cli identificar "celular"
  python -m agente_contabil.cli verificar 10063021 "smartphone"
  python -m agente_contabil.cli servico "ensino médio" [--ano 2027]
  python -m agente_contabil.cli simples [I|II|III|IV|V|MEI]
  python -m agente_contabil.cli perguntar "qual a alíquota do arroz?"
"""
import argparse
import json

from .ferramentas import _resposta_busca
from .lote import analisar_lote, gravar_saida, itens_da_planilha, resumo
from .calculo import consultar
from .ncm_tabela import identificar_ncm, verificar_ncm
from .servicos import consultar_servico
from .simples import consultar_simples


def _rodar_lote(args) -> None:
    from pathlib import Path
    arquivo = Path(args.arquivo)
    try:
        itens = itens_da_planilha(arquivo, args.col_descricao, args.col_ncm)
        print(f"Conferindo {len(itens)} produtos (cerca de {max(1, round(len(itens) * 0.04))} s)...", flush=True)
        resultados = analisar_lote(itens, args.ano)
    except (ValueError, OSError) as e:
        raise SystemExit(f"Erro: {e}")
    destino = Path(args.saida) if args.saida else arquivo.with_name(arquivo.stem + "_conferido.csv")
    gravar_saida(resultados, destino)
    r = resumo(resultados)
    print(f"{r['total']} produtos conferidos -> {destino}")
    print(f"  {r['com_problema']} com problema no NCM | {r['a_confirmar']} a confirmar com o contador")
    for status, n in r["por_status"].items():
        print(f"    {n:4}  {status}")
    for x in resultados[:5]:
        if x["gravidade"] <= 4:
            print(f"  linha {x['linha']}: {x['descricao'][:40]} | {x['ncm_informado']} | {x['status']}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="agente_contabil")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("ncm"); a.add_argument("ncm"); a.add_argument("--ano", type=int)
    b = sub.add_parser("buscar"); b.add_argument("texto")
    lt = sub.add_parser("lote"); lt.add_argument("arquivo"); lt.add_argument("--ano", type=int)
    lt.add_argument("--saida"); lt.add_argument("--col-descricao"); lt.add_argument("--col-ncm")
    i = sub.add_parser("identificar"); i.add_argument("texto")
    v = sub.add_parser("verificar"); v.add_argument("ncm"); v.add_argument("produto")
    e = sub.add_parser("simples"); e.add_argument("anexo", nargs="?", default="")
    d = sub.add_parser("servico"); d.add_argument("texto"); d.add_argument("--ano", type=int)
    c = sub.add_parser("perguntar"); c.add_argument("pergunta"); c.add_argument("--ano", type=int)
    args = ap.parse_args()

    if args.cmd == "lote":
        _rodar_lote(args)
        return
    if args.cmd == "ncm":
        saida = consultar(args.ncm, args.ano)
    elif args.cmd == "identificar":
        saida = identificar_ncm(args.texto)
    elif args.cmd == "verificar":
        saida = verificar_ncm(args.ncm, args.produto)
    elif args.cmd == "simples":
        saida = consultar_simples(args.anexo)
    elif args.cmd == "servico":
        saida = consultar_servico(args.texto, args.ano)
    elif args.cmd == "buscar":
        saida = _resposta_busca(args.texto)  # candidatos + avisos, igual à ferramenta do agente
    else:
        from .agente import perguntar
        r = perguntar(args.pergunta, args.ano)
        print(r["resposta"]); print(f"\n[tokens] {r['uso']}")
        return
    print(json.dumps(saida, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
