"""Uso:
  python -m agente_contabil.cli ncm 10063021 [--ano 2027]
  python -m agente_contabil.cli buscar "feijão"
  python -m agente_contabil.cli perguntar "qual a alíquota do arroz?"
"""
import argparse
import json

from .busca import buscar_produto
from .calculo import consultar


def main() -> None:
    ap = argparse.ArgumentParser(prog="agente_contabil")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("ncm"); a.add_argument("ncm"); a.add_argument("--ano", type=int)
    b = sub.add_parser("buscar"); b.add_argument("texto")
    c = sub.add_parser("perguntar"); c.add_argument("pergunta"); c.add_argument("--ano", type=int)
    args = ap.parse_args()

    if args.cmd == "ncm":
        saida = consultar(args.ncm, args.ano)
    elif args.cmd == "buscar":
        saida = buscar_produto(args.texto)
    else:
        from .agente import perguntar
        r = perguntar(args.pergunta, args.ano)
        print(r["resposta"]); print(f"\n[tokens] {r['uso']}")
        return
    print(json.dumps(saida, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
