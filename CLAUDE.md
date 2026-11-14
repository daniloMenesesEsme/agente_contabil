# Agente Contábil — Reforma Tributária (IBS/CBS)

Agente que responde dúvidas de contadores e lojistas sobre IBS/CBS por produto, categoria ou NCM.

## Regra de ouro
- Percentuais e regimes vêm SEMPRE de `dados/` (regras_ncm.csv, parametros.json). A IA nunca inventa alíquota.
- Toda resposta cita o fundamento legal (artigo/anexo) que está na tabela.
- Regra com `validado=nao` deve gerar aviso ao usuário.

## Estrutura
- `src/agente_contabil/regras.py` — carrega CSV, busca NCM por prefixo mais longo
- `src/agente_contabil/calculo.py` — alíquotas por ano (parametros.json) × redução do regime
- `src/agente_contabil/busca.py` — busca produto por texto (sem IA)
- `src/agente_contabil/ferramentas.py` — tools expostas ao modelo
- `src/agente_contabil/agente.py` — loop com a API do Claude
- `src/agente_contabil/api.py` — FastAPI; `cli.py` — linha de comando
- `scripts/` — extração dos anexos da LC 214 (PDF → CSV para revisão) e validação do CSV

## Ambiente
- Roda num Dev Container (Docker). Código em `/app`, `PYTHONPATH=/app/src` já definido, usuário `dev`.
- Dependências: `requirements.txt` (execução) e `requirements-dev.txt` (testes/scripts). Ao adicionar uma, atualize o arquivo e reconstrua o container.

## Comandos
- Testes: `pytest -q`
- Validar dados: `python scripts/validar_regras.py`
- CLI: `python -m agente_contabil.cli ncm 10063021`
- API: `uvicorn agente_contabil.api:app --reload --host 0.0.0.0 --app-dir src`

## Convenções
- Python 3.10+, código e nomes em português, funções pequenas, sem dependências novas sem necessidade.
- Não ler `dados/brutos/` nem PDFs: use os scripts.
