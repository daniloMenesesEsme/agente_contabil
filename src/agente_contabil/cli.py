"""Uso:
  python -m agente_contabil.cli ncm 10063021 [--ano 2027]
  python -m agente_contabil.cli buscar "feijão"
  python -m agente_contabil.cli servico "ensino médio" [--ano 2027]
  python -m agente_contabil.cli simples [I|II|III|IV|V|MEI]
  python -m agente_contabil.cli perguntar "qual a alíquota do arroz?"
"""
import argparse
import json

from .ferramentas import _resposta_busca
from .calculo import consultar
from .servicos import consultar_servico
from .simples import consultar_simples


def main() -> None:
    ap = argparse.ArgumentParser(prog="agente_contabil")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("ncm"); a.add_argument("ncm"); a.add_argument("--ano", type=int)
    b = sub.add_parser("buscar"); b.add_argument("texto")
    e = sub.add_parser("simples"); e.add_argument("anexo", nargs="?", default="")
    d = sub.add_parser("servico"); d.add_argument("texto"); d.add_argument("--ano", type=int)
    c = sub.add_parser("perguntar"); c.add_argument("pergunta"); c.add_argument("--ano", type=int)
    args = ap.parse_args()

    if args.cmd == "ncm":
        saida = consultar(args.ncm, args.ano)
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
