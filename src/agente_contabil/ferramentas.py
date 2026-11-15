"""Ferramentas (tools) expostas ao modelo. Todas determinísticas, lendo dados/."""
import json

from .busca import buscar_produto
from .calculo import consultar
from .lote import analisar_lote, resumo
from .ncm_tabela import identificar_ncm, verificar_ncm
from .servicos import consultar_servico
from .simples import consultar_simples
from .texto_busca import avisos_da_consulta

LIMITE_CONFERENCIA_CHAT = 30

FERRAMENTAS = [
    {
        "name": "consultar_ncm",
        "description": "Retorna regime, alíquotas de CBS/IBS, fundamento legal e avisos para um NCM em um ano.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "ncm": {"type": "string", "description": "NCM com 8 dígitos (pontos opcionais)."},
                "ano": {"type": "integer", "description": "Ano de referência, ex.: 2027."},
            },
            "required": ["ncm", "ano"],
            "additionalProperties": False,
        },
    },
    {
        "name": "conferir_produtos",
        "description": "Confere uma LISTA PEQUENA de produtos (até 30) do ERP do usuário numa chamada só: para cada um diz se o NCM "
                       "existe, se combina com a descrição, o regime e o que fazer, com os problemas primeiro. Para planilhas "
                       "grandes, oriente o usuário a usar a conferência em lote (CLI `lote` ou API /lote).",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "produtos": {"type": "array", "maxItems": 30, "items": {
                    "type": "object",
                    "properties": {"descricao": {"type": "string", "description": "Nome do produto como no cadastro."},
                                   "ncm": {"type": "string", "description": "NCM do cadastro (vazio se não tem)."}},
                    "required": ["descricao", "ncm"], "additionalProperties": False}},
                "ano": {"type": "integer", "description": "Ano de referência, ex.: 2027."},
            },
            "required": ["produtos", "ano"],
            "additionalProperties": False,
        },
    },
    {
        "name": "identificar_ncm",
        "description": "Acha o NCM de QUALQUER produto pela descrição oficial da tabela da Receita (não só dos que têm "
                       "benefício), agrupado por posição. Traz o texto oficial, `confianca`, `ambigua` e "
                       "`regra_cadastrada` (null = sem benefício cadastrado). A busca é por palavras: JULGUE se a "
                       "descrição oficial faz sentido; reformule com termos técnicos se nada servir. Depois use "
                       "`consultar_ncm` no NCM que o usuário confirmar.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"texto": {"type": "string", "description": "Nome ou descrição do produto."}},
            "required": ["texto"],
            "additionalProperties": False,
        },
    },
    {
        "name": "verificar_ncm",
        "description": "Confere se um NCM (ex.: o do ERP do lojista) combina com o produto que ele vende: devolve o texto "
                       "oficial do NCM, a compatibilidade (alta/media/baixa) e candidatos alternativos; avisa se o NCM "
                       "não existe na tabela oficial.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "ncm": {"type": "string", "description": "NCM com 8 dígitos (pontos opcionais)."},
                "produto": {"type": "string", "description": "Nome do produto como o usuário o descreve."},
            },
            "required": ["ncm", "produto"],
            "additionalProperties": False,
        },
    },
    {
        "name": "consultar_servico",
        "description": "Para SERVIÇOS (sem NCM): busca por código NBS ou nome do serviço e retorna regime, alíquotas, "
                       "fundamento, texto da lei e avisos. Serviço não encontrado = presunção de alíquota padrão (com aviso).",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "texto": {"type": "string", "description": "Nome do serviço ou código NBS."},
                "ano": {"type": "integer", "description": "Ano de referência, ex.: 2027."},
            },
            "required": ["texto", "ano"],
            "additionalProperties": False,
        },
    },
    {
        "name": "consultar_simples",
        "description": "Tabelas do Simples Nacional (anexos I a V) e do MEI que a LC 214 traz, SEM interpretação: "
                       "retorna cabeçalhos, faixas e notas literais por período. Passe string vazia para listar os anexos.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"anexo": {"type": "string", "description": "I, II, III, IV, V ou MEI; vazio para listar."}},
            "required": ["anexo"],
            "additionalProperties": False,
        },
    },
    {
        "name": "buscar_produto",
        "description": "Busca NCMs candidatos a partir do nome ou categoria de um produto. Cada candidato traz "
                       "`confianca` (alta/media/baixa) e `palavras_sem_correspondencia`; `avisos` traz lacunas conhecidas.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"texto": {"type": "string", "description": "Nome ou categoria do produto."}},
            "required": ["texto"],
            "additionalProperties": False,
        },
    },
]


def _resposta_busca(texto: str) -> dict:
    """Candidatos + avisos (tema com lacuna conhecida, nada encontrado, confiança baixa)."""
    candidatos = buscar_produto(texto)
    avisos = avisos_da_consulta(texto)
    ignoradas = next((c["palavras_ignoradas"] for c in candidatos if c.get("palavras_ignoradas")), [])
    if ignoradas:
        avisos.append(f"Nenhum item cobre tudo que foi pedido: IGNOREI as palavras {', '.join(ignoradas)}. "
                      "Diga isso ao usuário e confirme o item antes de afirmar regime.")
    if not candidatos:
        avisos.append("Nenhum produto encontrado na base. Se o NCM do produto não estiver nas listas de benefício, "
                      "aplica-se a alíquota padrão (presunção): use `identificar_ncm` para achar o NCM oficial "
                      "e `consultar_ncm`; não afirme regime sem isso.")
    elif all(c["confianca"] == "baixa" for c in candidatos):
        avisos.append("CONFIANÇA BAIXA: nenhum candidato cobre o que foi pedido (veja palavras_sem_correspondencia). "
                      "Não afirme regime sem o usuário confirmar o item.")
    return {"candidatos": candidatos, "avisos": avisos}


def executar(nome: str, entrada: dict) -> tuple[str, bool]:
    """Executa a ferramenta. Retorna (conteúdo JSON, is_error)."""
    try:
        if nome == "consultar_ncm":
            r = consultar(entrada["ncm"], int(entrada["ano"]))
            return json.dumps(r, ensure_ascii=False), "erro" in r
        if nome == "conferir_produtos":
            resultados = analisar_lote(entrada["produtos"], int(entrada["ano"]), limite=LIMITE_CONFERENCIA_CHAT)
            compactos = [{k: r[k] for k in ("linha", "descricao", "ncm_informado", "status", "o_que_fazer", "ncm_sugerido",
                                            "regime", "aliquota_total_percentual", "cenarios", "regra_validada", "avisos")}
                         for r in resultados]
            return json.dumps({"resumo": resumo(resultados), "produtos": compactos}, ensure_ascii=False), False
        if nome == "identificar_ncm":
            return json.dumps(identificar_ncm(entrada["texto"]), ensure_ascii=False), False
        if nome == "verificar_ncm":
            r = verificar_ncm(entrada["ncm"], entrada["produto"])
            return json.dumps(r, ensure_ascii=False), "erro" in r
        if nome == "consultar_servico":
            r = consultar_servico(entrada["texto"], int(entrada["ano"]))
            return json.dumps(r, ensure_ascii=False), "erro" in r
        if nome == "consultar_simples":
            r = consultar_simples(entrada["anexo"])
            return json.dumps(r, ensure_ascii=False), "erro" in r
        if nome == "buscar_produto":
            return json.dumps(_resposta_busca(entrada["texto"]), ensure_ascii=False), False
        return f"Ferramenta desconhecida: {nome}", True
    except (KeyError, ValueError, TypeError) as e:
        return f"Entrada inválida para {nome}: {e}", True
