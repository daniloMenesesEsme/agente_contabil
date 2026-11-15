"""Uso:
  python -m agente_contabil.cli ncm 10063021 [--ano 2027]
  python -m agente_contabil.cli buscar "feijão"
  python -m agente_contabil.cli identificar "celular"
  python -m agente_contabil.cli verificar 10063021 "smartphone"
  python -m agente_contabil.cli servico "ensino médio" [--ano 2027]
  python -m agente_contabil.cli simples [I|II|III|IV|V|MEI]
  python -m agente_contabil.cli perguntar "qual a alíquota do arroz?"
"""
import argparse
import json

from .ferramentas import _resposta_busca
from .calculo import consultar
from .ncm_tabela import identificar_ncm, verificar_ncm
from .servicos import consultar_servico
from .simples import consultar_simples


def main() -> None:
    ap = argparse.ArgumentParser(prog="agente_contabil")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("ncm"); a.add_argument("ncm"); a.add_argument("--ano", type=int)
    b = sub.add_parser("buscar"); b.add_argument("texto")
    i = sub.add_parser("identificar"); i.add_argument("texto")
    v = sub.add_parser("verificar"); v.add_argument("ncm"); v.add_argument("produto")
    e = sub.add_parser("simples"); e.add_argument("anexo", nargs="?", default="")
    d = sub.add_parser("servico"); d.add_argument("texto"); d.add_argument("--ano", type=int)
    c = sub.add_parser("perguntar"); c.add_argument("pergunta"); c.add_argument("--ano", type=int)
    args = ap.parse_args()

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
