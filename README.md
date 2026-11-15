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

1. **`regras_ncm.csv` foi gerado do texto da LC 214/2025 e NENHUMA regra está validada** (`validado=nao`).
   - Fonte: a página do Planalto salva como HTML em `dados/brutos/Lcp 214.html` (pasta fora do Git).
   - Pipeline (rode nesta ordem): `python scripts/extrair_anexos_lc214.py "dados/brutos/Lcp 214.html"` →
     `python scripts/gerar_anexos_regimes.py "dados/brutos/Lcp 214.html"` → `python scripts/gerar_regras.py` →
     `python scripts/validar_regras.py`. Os geradores se recusam a sobrescrever arquivos já revisados
     (`--sobrescrever` força).
   - O regime de cada anexo vem **só do título oficial** (`dados/anexos_regimes.csv`); título que não diz o regime
     fica `a_definir`. Cada regra guarda o `texto_lei` (linha literal do anexo) e a `ressalva` quando a lei traz
     "exceto"/"somente".
   - Um contador revisa linha a linha e marca `validado=sim`. Itens que exigem atenção especial:
     - **`a_confirmar` (7 NCMs):** a lei lista o NCM em dois anexos com regimes diferentes; nenhum foi escolhido
       e a consulta não devolve alíquota.
     - **Códigos incompletos (42 regras, 5 ou 7 dígitos, ex.: `8517.1`):** o benefício vale só para o produto
       descrito, não para todo o código. A consulta marca `enquadramento_a_confirmar`.
     - **Exceções ("exceto"):** 5 regras `padrao` protegem NCMs excluídos; 8 NCMs excluídos ficaram sem regra
       (veja a saída de `gerar_regras.py`).
     - **Medicamentos:** o Anexo XIV (medicamentos, redução a zero) foi **revogado pela LC 227/2026** e está fora
       da base; a maioria dos medicamentos cai em "alíquota padrão presumida". Confirme a regra vigente.
     - **Anexos XVI e XVII** (limite de alíquota própria; Imposto Seletivo) ficaram `a_definir` e fora das regras.
   - **Não cobertos ainda:** regras do Simples Nacional/MEI (o texto cru está em
     `dados/brutos/extraido_simples_lc214.csv`) e serviços sem NCM (Anexos II e III).
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

- [x] Carregar os anexos da LC 214 (gerados do texto da lei, pendentes de validação por contador)
- [ ] Validar `regras_ncm.csv` (contador) e resolver os `a_confirmar`
- [ ] Tabela cClassTrib oficial (a coluna `cclasstrib` existe, mas está vazia)
- [ ] Regras de serviços (por NBS) e do Simples Nacional/MEI, estruturadas e validadas
- [ ] Regimes específicos (combustíveis, serviços financeiros, imóveis etc.)
- [ ] Imposto Seletivo (bebidas, cigarros etc.)
- [ ] Cronograma completo 2029–2033 em `parametros.json`
- [ ] Interface: página web simples ou WhatsApp
- [ ] Histórico de conversa e importação de planilha de produtos (lote de NCMs)
