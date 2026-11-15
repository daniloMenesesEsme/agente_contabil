"""Gera dados/revisao_contador.csv: tudo que um contador precisa conferir, do MAIS ARRISCADO ao menos.

Uso:
  python scripts/gerar_planilha_revisao.py

Abre direto no Excel (UTF-8 com BOM, separador ';'). O contador preenche só as 3 últimas colunas:
  decisao          confirmar | corrigir | excluir   (vazio = pendente)
  regime_correto   aliquota_zero | reducao_60 | reducao_30 | padrao   (obrigatório se decisao=corrigir)
  observacao_contador
Depois: python scripts/aplicar_revisao.py (simula) e python scripts/aplicar_revisao.py --aplicar.
Prioridade: 1 = regime desconhecido; 2 = só vale para o produto descrito / anexo sem regime;
3 = exceções, tabelas e auxiliares de busca; 4 = ressalvas e serviços; 5 = regra sem alerta (conferência normal).
"""
import csv
import json
from collections import Counter
from pathlib import Path

DADOS = Path("dados")
DESTINO = DADOS / "revisao_contador.csv"
COLUNAS = ["prioridade", "categoria", "tipo_dado", "chave", "descricao", "regime_atual", "reducao_atual",
           "fundamento", "o_que_conferir", "texto_lei", "decisao", "regime_correto", "observacao_contador"]


def _linha(prioridade, categoria, tipo, chave, descricao="", regime="", reducao="", fundamento="",
           conferir="", texto="") -> dict:
    return {"prioridade": prioridade, "categoria": categoria, "tipo_dado": tipo, "chave": chave,
            "descricao": descricao, "regime_atual": regime, "reducao_atual": reducao, "fundamento": fundamento,
            "o_que_conferir": conferir, "texto_lei": texto, "decisao": "", "regime_correto": "",
            "observacao_contador": ""}


def categoria_regra(r: dict) -> tuple[int, str, str]:
    """(prioridade, categoria, o que conferir) de uma regra de NCM."""
    p, reg, fund = r["ncm_prefixo"], r["regime"], r["fundamento"]
    if reg == "a_confirmar" and "(revogado)" in fund:
        return 1, "regime_a_confirmar_anexo_revogado", (
            "O NCM constava de anexo REVOGADO (LC 227/2026) e nenhum anexo vigente o trata. Qual o regime vigente? "
            "Use decisao=corrigir e informe regime_correto (padrao se não houver benefício).")
    if reg == "a_confirmar":
        return 1, "regime_a_confirmar_conflito_entre_anexos", (
            f"A lei lista o NCM em anexos com regimes diferentes ({r['observacao'][:160]}). Qual vale para o produto? "
            "Use decisao=corrigir e informe regime_correto.")
    if r.get("outros_produtos"):
        return 2, "ncm_dividido_com_anexo_revogado", (
            "A regra vale só para o produto descrito; o NCM também constava de anexo revogado. Confirme o regime do "
            "produto descrito e anote em observacao_contador o regime dos OUTROS produtos deste NCM.")
    if len(p) in (5, 7) and reg != "padrao":
        return 2, "codigo_incompleto_na_lei", (
            f"A lei cita o código incompleto ({len(p)} dígitos). Confirme que o benefício vale só para o produto "
            "descrito (e não para todo o código).")
    if "exceção expressa" in fund:
        return 3, "excecao_expressa_padrao", (
            "NCM excluído do benefício por 'exceto' no anexo: confirme que vale a alíquota padrão (ou informe o "
            "regime de outro anexo).")
    if r["ressalva"]:
        return 4, "ressalva_da_lei", "Leia o texto da lei: a exceção ou condição se aplica a este produto?"
    return 5, "regra_sem_alerta", "Confira regime, redução e fundamento com o texto da lei."


def linhas_revisao(regras, servicos, anexos, simples, sinonimos, avisos, parametros, excecoes=()) -> list[dict]:
    """Pura (sem arquivos). Cada argumento é a lista de dicts do CSV correspondente (parametros: dict do JSON)."""
    saida = []
    for r in regras:
        prioridade, categoria, conferir = categoria_regra(r)
        if r["ressalva"] and categoria != "ressalva_da_lei":
            conferir += f" Ressalva: {r['ressalva'][:200]}"
        saida.append(_linha(prioridade, categoria, "regra_ncm", r["ncm_prefixo"], r["descricao"], r["regime"],
                            r["reducao_percentual"], r["fundamento"], conferir, r["texto_lei"]))
    com_regra = {r["ncm_prefixo"] for r in regras}
    vistos = set()
    for e in excecoes:  # NCM excluído por "exceto" que ficou SEM regra (não há benefício a proteger)
        p = "".join(c for c in e["ncm"] if c.isdigit())
        if p in com_regra or p in vistos:
            continue
        vistos.add(p)
        saida.append(_linha(3, "excecao_sem_regra", "excecao", e["ncm"], "", "", "", f"LC 214/2025, Anexo {e['anexo']}",
                            "O texto da lei EXCLUI este NCM do anexo ('exceto'), mas não há regra cadastrada: vale a "
                            "alíquota padrão ou outro anexo? Anote em observacao_contador (aplicação é manual).",
                            e["linha"][:300]))
    for s in servicos:
        sem_nbs = not s["nbs"]
        saida.append(_linha(3 if sem_nbs else 4, "servico_sem_codigo_nbs" if sem_nbs else "servico_nao_validado",
                            "servico", s["item"], s["descricao"], s["regime"], s["reducao_percentual"], s["fundamento"],
                            "Confira se o serviço está no anexo, o regime e " + (
                                "o código NBS (a lei não trouxe código nesta linha)." if sem_nbs else "o código NBS."),
                            s["texto_lei"]))
    for a in anexos:
        if a["tipo"] == "revogado":
            saida.append(_linha(1, "anexo_revogado_sem_substituto", "anexo", a["anexo"], a["titulo_oficial"][:200],
                                a["regime"], "", a["fundamento"],
                                "Anexo REVOGADO (medicamentos, redução a zero). Qual a regra VIGENTE para medicamentos "
                                "depois da LC 227/2026? Anote em observacao_contador (aplicação é manual)."))
        elif a["regime"] == "a_definir" and a["tipo"] == "ncm":
            saida.append(_linha(2, "anexo_sem_regime_definido", "anexo", a["anexo"], a["titulo_oficial"][:200],
                                a["regime"], "", a["fundamento"],
                                "O título não diz o regime. Qual artigo da LC 214 remete a este anexo e qual o efeito "
                                "(ficou fora das regras de NCM)? Anote em observacao_contador."))
    for anexo in sorted({l["anexo"] for l in simples}):
        linhas = [l for l in simples if l["anexo"] == anexo]
        saida.append(_linha(3, "tabela_simples_mei_transcrita", "simples", anexo, linhas[0]["titulo"][:200], "", "",
                            linhas[0]["fundamento"],
                            f"Tabela transcrita SEM interpretação ({len(linhas)} linhas, "
                            f"{len({l['secao'] for l in linhas})} períodos): confira faixas, alíquotas e períodos "
                            "com a lei. Anote divergências em observacao_contador (aplicação é manual)."))
    for s in sinonimos:
        saida.append(_linha(3, "sinonimo_de_busca", "sinonimo", s["termo"], f"{s['termo']} = {s['equivalentes']}",
                            conferir="É equivalência ESTRITA? Sinônimo ruim induz o agente a erro (já houve 'remédio'). "
                                     "Anote em observacao_contador (aplicação é manual).", texto=s.get("observacao", "")))
    for a in avisos:
        saida.append(_linha(3, "aviso_de_busca", "aviso", a["termo"], a["aviso"][:200],
                            conferir="O aviso está correto e suficiente? Anote em observacao_contador."))
    for ano, p in sorted(parametros.get("anos", {}).items()):
        nulos = [k for k in ("cbs", "ibs_uf", "ibs_mun") if p.get(k) is None]
        if nulos:
            saida.append(_linha(2, "aliquota_de_referencia_indefinida", "parametro", ano,
                                f"{', '.join(nulos).upper()} de {ano} sem valor (null)", fundamento=p.get("fonte", ""),
                                conferir="Informe a alíquota publicada (com a fonte) em observacao_contador; o "
                                         "ajuste do parametros.json é manual."))
    saida.sort(key=lambda l: (l["prioridade"], l["categoria"], str(l["chave"])))
    return saida


def _csv(caminho: Path) -> list[dict]:
    if not caminho.exists():
        return []
    with open(caminho, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def main() -> None:
    parametros = json.loads((DADOS / "parametros.json").read_text(encoding="utf-8"))
    linhas = linhas_revisao(_csv(DADOS / "regras_ncm.csv"), _csv(DADOS / "regras_servicos.csv"),
                            _csv(DADOS / "anexos_regimes.csv"), _csv(DADOS / "simples_anexos.csv"),
                            _csv(DADOS / "sinonimos.csv"), _csv(DADOS / "avisos_busca.csv"), parametros,
                            _csv(DADOS / "brutos" / "excecoes.csv"))
    with open(DESTINO, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS, delimiter=";")
        w.writeheader()
        w.writerows(linhas)
    print(f"{len(linhas)} itens para revisão -> {DESTINO}")
    por = Counter((l["prioridade"], l["categoria"]) for l in linhas)
    for (prioridade, categoria), n in sorted(por.items()):
        print(f"  prioridade {prioridade} | {n:4} | {categoria}")


if __name__ == "__main__":
    main()
