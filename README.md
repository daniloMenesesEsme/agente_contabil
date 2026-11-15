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
     `python scripts/validar_regras.py`. Serviços e Simples/MEI têm geradores próprios:
     `python scripts/gerar_regras_servicos.py "dados/brutos/Lcp 214.html"` (→ `dados/regras_servicos.csv`) e
     `python scripts/gerar_simples.py "dados/brutos/Lcp 214.html"` (→ `dados/simples_anexos.csv`). Os geradores se recusam a sobrescrever arquivos já revisados
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
     - **Medicamentos:** o Anexo XIV (lista fixa de NCMs com alíquota zero) foi **revogado pela LC 227/2026** e vem
       riscado no HTML da lei, então o extrator o descarta. Pelo texto da lei (conferido com
       `scripts/verificar_artigos_lei.py`): o art. 133 reduz em 60% as alíquotas de medicamentos registrados na
       Anvisa; o art. 146 dá alíquota zero aos da lista divulgada a cada 120 dias por ato conjunto MF/CGIBS, a soros
       e vacinas e ao fornecimento aos entes do §1º. Por isso o regime **não se define só pelo NCM**: as posições
       3003 e 3004 ficam `a_confirmar` (sem alíquota), e a regra vigente que divide NCM com elas (ex.: dispositivo do
       Anexo IV em 3004.90.99) vale só para o produto descrito. Um contador precisa confirmar.
     - **Anexos XVI e XVII** (limite de alíquota própria; Imposto Seletivo) ficaram `a_definir` e fora das regras.
   - **Serviços (`consultar_servico`):** só os Anexos II e III (educação e saúde, 39 itens, redução de 60%) estão
     cadastrados, por NBS ou texto. Serviço fora da lista recebe "presunção de alíquota padrão" com aviso, nunca
     "sem imposto". Outros regimes de serviços (ex.: financeiros) ainda não estão cadastrados.
   - **Texto riscado:** o Planalto marca texto revogado/alterado com `<strike>` e, na maioria (milhares de trechos), com
     CSS `text-decoration: line-through`. O extrator trata os dois (e classes CSS, com pilha de elementos para o HTML
     sem `</p>`). Texto riscado nunca entra nos dados.
   - **Simples Nacional e MEI (`consultar_simples`):** as tabelas que a LC 214 traz (anexos I a V e MEI, por
     período de 2027 a 2033) estão reproduzidas **literalmente**, com cabeçalhos, sem cálculo nem interpretação.
     O agente não escolhe anexo nem faixa da empresa. Falta estruturar e validar essas tabelas com um contador.
   - **Busca por texto** (`buscar_produto`, `consultar_servico`; sem IA): usa radicais (carne = carnes), peso por
     raridade, cobertura da pergunta e posição da palavra na descrição, e devolve `confianca`
     (alta/média/baixa) e `palavras_sem_correspondencia`. Dois arquivos de auxílio, **revisáveis por contador**:
     `dados/sinonimos.csv` (só equivalências estritas; ex.: frango = ave, porque a lei diz "aves") e
     `dados/avisos_busca.csv` (tema com lacuna conhecida, ex.: medicamentos, vira aviso). Sinônimo ruim induz
     a erro (um "remédio = medicamento" casava vacina veterinária e foi removido): acrescente com cuidado.
   - **Tabela oficial da NCM** (`dados/ncm_tabela.csv`, 15.157 códigos, vigência e ato em
     `dados/ncm_tabela_meta.json`): vem da Receita/Siscomex e é a base de `identificar_ncm` (acha o NCM de
     QUALQUER produto, agrupado por posição, com `ambigua` e `confianca`), `verificar_ncm` (o NCM do ERP bate com o
     produto? existe?) e do bloco `ncm_oficial` de `consultar_ncm`. Atualize quando sair nova Resolução Gecex:
     `curl -L -o ncm.json "https://portalunico.siscomex.gov.br/classif/api/publico/nomenclatura/download/json?perfil=PUBLICO"`
     e `python -I scripts/importar_ncm.py ncm.json` (o arquivo baixado é tratado como dado externo: só lido como JSON).
     A tabela não define alíquota: o regime continua vindo só de `regras_ncm.csv`.
   - **Limites da busca:** é por palavras, não por significado (a NCM não usa "refrigerante" para a bebida). O motor
     usa radicais, peso por raridade, bônus para a descrição mais específica, desconto para sinônimo, e quando nada
     cobre o pedido descarta palavras do fim e **diz quais ignorou** (confiança no máximo média). O agente deve
     julgar o sentido e reformular com termos oficiais, sempre usando só NCMs devolvidos pela tabela.
2. **`parametros.json`**: preencha a CBS de 2027+ quando a alíquota de referência for publicada.
3. Preencha `cclasstrib` conforme a tabela oficial (Notas Técnicas da NF-e — Reforma Tributária).

## Revisão pelo contador

`python scripts/gerar_planilha_revisao.py` gera `dados/revisao_contador.csv` (abre direto no Excel): **tudo que
precisa de conferência, do mais arriscado ao menos**, com a coluna `o_que_conferir` e o `texto_lei` de cada linha.

| Prioridade | O que é |
|---|---|
| 1 | Regime desconhecido: NCMs `a_confirmar` (conflito entre anexos) e as posições de medicamentos 3003/3004 |
| 2 | Vale só para o produto descrito (código incompleto, NCM dividido com medicamentos), NCM que não existe na tabela oficial, anexos sem regime, CBS 2027/2028 indefinida |
| 3 | Exceções ("exceto"), tabelas do Simples/MEI, serviços sem NBS, sinônimos e avisos de busca |
| 4 | Ressalvas da lei e serviços |
| 5 | Regras sem alerta (conferência normal) |

O contador preenche só `decisao` (`confirmar`, `corrigir` ou `excluir`), `regime_correto`
(`aliquota_zero`, `reducao_60`, `reducao_30` ou `padrao`, obrigatório em `corrigir`) e `observacao_contador`.
Depois: `python scripts/aplicar_revisao.py` **simula** (mostra o que faria e os erros) e
`python scripts/aplicar_revisao.py --aplicar` grava em `regras_ncm.csv` e `regras_servicos.csv`
(`validado=sim`). Regras de segurança: um `a_confirmar` não pode ser "confirmado" (precisa de regime), qualquer erro
aborta tudo, e anexos, Simples/MEI, sinônimos, avisos e parâmetros **não** são aplicados automaticamente (saem na
lista MANUAL). Depois de validadas, os geradores se recusam a sobrescrever as regras. O gerador da planilha **recusa
refazê-la se já houver decisões preenchidas** (`--sobrescrever` força). `python scripts/validar_e_preencher_ncm.py` audita as
bases (exceções indevidas, NCMs fora da tabela oficial, linhas repetidas do Simples) e grava só em `dados/validacao/`.

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
- [x] Serviços dos Anexos II e III e tabelas do Simples/MEI cadastrados (sem validação)
- [ ] Validar serviços e Simples/MEI com contador; demais regimes de serviços; interpretar colunas do Simples
- [ ] Regimes específicos (combustíveis, serviços financeiros, imóveis etc.)
- [ ] Imposto Seletivo (bebidas, cigarros etc.)
- [ ] Cronograma completo 2029–2033 em `parametros.json`
- [ ] Interface: página web simples ou WhatsApp
- [ ] Histórico de conversa e importação de planilha de produtos (lote de NCMs)
