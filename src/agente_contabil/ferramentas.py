"""Ferramentas (tools) expostas ao modelo. Todas determinísticas, lendo dados/."""
import json

from .busca import buscar_produto
from .calculo import consultar
from .servicos import consultar_servico
from .simples import consultar_simples
from .texto_busca import avisos_da_consulta

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
    if not candidatos:
        avisos.append("Nenhum produto encontrado na base. Não afirme regime: peça o NCM ao usuário.")
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
