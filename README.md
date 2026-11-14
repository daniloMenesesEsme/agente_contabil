# Agente Contábil — IBS/CBS (Reforma Tributária)

Responde dúvidas sobre IBS/CBS por **NCM**, **produto** ou **categoria**, com fundamento legal.

## Como funciona (por que é preciso e barato)

```
Pergunta ──► IA (entende a pergunta) ──► ferramentas ──► dados/regras_ncm.csv + parametros.json
                    ▲                                         (percentuais SEMPRE vêm daqui)
                    └──── resposta com fundamento e avisos ◄──┘
```

- `/ncm/{ncm}` e `/buscar` **não usam IA** → custo zero, resposta instantânea.
- `/perguntar` usa a IA só para interpretar e explicar; o número vem da tabela.
- Regras com `validado=nao` geram aviso automático.

## Desenvolvimento com Docker + VS Code (recomendado)

Pré-requisitos no Windows: **Docker Desktop** (com WSL 2) e, no VS Code, a extensão **Dev Containers** (Microsoft).

1. Descompacte o projeto, por exemplo em `C:\agente_contabel\agente-contabil`
2. `copy .env.example .env` (preencha a chave da API depois, se for usar IA)
3. Abra a pasta no VS Code → `F1` → **Dev Containers: Reopen in Container**
4. Na primeira vez a imagem é construída (alguns minutos) e os testes rodam sozinhos
5. O **Claude Code** já vem instalado dentro do container: clique no ícone dele e faça login com sua conta Pro.
   O login fica salvo no volume `claude-config` (não precisa repetir ao reconstruir)

Dentro do container o terminal do VS Code já está em `/app` com tudo instalado:
```
pytest -q
python -m agente_contabil.cli ncm 10063021 --ano 2026
uvicorn agente_contabil.api:app --reload --host 0.0.0.0 --app-dir src   # http://localhost:8000/docs
```

Rodar a API em modo produção (imagem enxuta, sem ferramentas de dev):
```
docker compose --profile prod up --build api
```

## Instalação sem Docker (Windows / PowerShell)

```
cd C:\agente_contabel\agente-contabil
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
copy .env.example .env      # depois edite o .env e coloque sua ANTHROPIC_API_KEY
pytest -q                   # deve mostrar "11 passed"
```

## Uso

```
$env:PYTHONPATH="src"
python -m agente_contabil.cli ncm 10063021 --ano 2026
python -m agente_contabil.cli buscar "feijão"
python -m agente_contabil.cli perguntar "Qual a alíquota do arroz em 2026?"
uvicorn agente_contabil.api:app --reload --app-dir src   # abra http://127.0.0.1:8000/docs
```

## ⚠️ Antes de usar com clientes

1. **Os dados de `regras_ncm.csv` são EXEMPLOS** (`validado=nao`). Substitua pelos anexos oficiais:
   - Baixe o PDF da LC 214/2025 para `dados/brutos/lc214.pdf`
   - `python scripts/extrair_anexos_lc214.py dados/brutos/lc214.pdf`
   - Revise `dados/brutos/extraido_lc214.csv` e copie as linhas para `regras_ncm.csv`
   - Um contador marca `validado=sim` linha por linha
   - `python scripts/validar_regras.py`
2. **`parametros.json`**: preencha a CBS de 2027+ quando a alíquota de referência for publicada.
3. Preencha `cclasstrib` conforme a tabela oficial (Notas Técnicas da NF-e — Reforma Tributária).

## Custos

| Item | Custo |
|---|---|
| Consultas por NCM/busca | zero (não usa IA) |
| Perguntas em texto | tokens da API; prompt e ferramentas ficam em cache |
| Mais barato | no `.env`: `MODELO=claude-haiku-5-5` e `ESFORCO=low` |

Cada resposta de `/perguntar` mostra os tokens gastos em `uso`.

## Próximos passos (roadmap)

- [ ] Carregar os anexos oficiais completos e validar
- [ ] Tabela cClassTrib oficial
- [ ] Regimes específicos (combustíveis, serviços financeiros, imóveis etc.)
- [ ] Imposto Seletivo (bebidas, cigarros etc.)
- [ ] Cronograma completo 2029–2033 em `parametros.json`
- [ ] Interface: página web simples ou WhatsApp
- [ ] Histórico de conversa e importação de planilha de produtos (lote de NCMs)
