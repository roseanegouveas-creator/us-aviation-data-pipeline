r"""
# SPEC — Dashboard de Aviação EUA
**Etapa 4 — Construção do painel executivo**

## CONTEXTO

Estou desenvolvendo um pipeline de dados em Python para análise da aviação dos Estados Unidos.

Trabalho com spec-driven development: esta SPEC é a fonte da verdade e o código é consequência dela.

Não invente requisitos, indicadores, colunas ou regras de negócio. Se alguma informação necessária não estiver nesta SPEC, pergunte antes de implementar.

O objetivo é construir um dashboard executivo que permita visualizar rapidamente o volume de voos, atrasos, cancelamentos e desempenho de aeroportos, companhias e rotas.

## 1. STACK

- Python 3.13.
- uv.
- DuckDB.
- Pandas.
- Streamlit.
- Plotly Express.

Banco de dados:

`aviation.duckdb`

Dependências necessárias:

```powershell
uv add streamlit plotly
```

Antes de instalar, confira se já estão disponíveis no `pyproject.toml`.

Não reinstale dependências desnecessariamente.

## 2. CONTROLE DE EXECUÇÃO E ACESSO AO BANCO

**Esta seção é obrigatória.**

Já houve bloqueio do banco porque o servidor MCP MotherDuck estava conectado ao arquivo `aviation.duckdb`.

Para evitar travamentos:

- Não iniciar servidor MCP.
- Não tentar consultar o banco pelo MCP.
- Não executar ferramentas de inspeção que abram conexões persistentes.
- Não ficar repetindo tentativas de conexão.
- Não executar `pipeline.marts` durante a implementação.
- Não tentar reconstruir os Marts automaticamente.
- Não executar processos paralelos que acessem o mesmo arquivo.

Os 12 Marts já estão materializados no banco real.

Última execução confirmada:

```text
TOTAL: 12 marts | 1.060 linhas
```

Portanto, utilize a estrutura documentada nesta SPEC.

Se precisar conferir alguma informação adicional, faça uma única consulta Python/DuckDB em modo somente leitura, com timeout de 10 segundos, fechando a conexão imediatamente.

Se houver bloqueio:
1. Não repetir a tentativa.
2. Informar o erro.
3. Identificar qual processo está utilizando o banco.
4. Aguardar liberação antes de continuar.

Não encerrar processos automaticamente.

### Regra de conexão do dashboard

A conexão deverá ser aberta em modo somente leitura:

```python
duckdb.connect("aviation.duckdb", read_only=True)
```

A conexão deve ser fechada dentro da função de leitura, inclusive em caso de erro.

Nunca manter conexão DuckDB aberta enquanto o usuário utiliza o dashboard.

**Motivo:** o orquestrador `pipeline.marts` precisa conseguir gravar no banco mesmo quando o dashboard estiver aberto.

## 3. O QUE JÁ EXISTE — NÃO REIMPLEMENTAR

Arquitetura:

- RAW
- REFINED
- MARTS

O dashboard consome exclusivamente o schema `marts`.

Orquestrador existente:

`pipeline/marts.py`

Comando de execução, somente quando solicitado em uma etapa separada:

```powershell
uv run python -m pipeline.marts
```

Os 12 Marts já estão criados e disponíveis.

### Estrutura real das tabelas

Utilize exatamente os nomes de colunas abaixo.

**Mart 01 — aeroportos_taxa_atrasos**

- codigo_iata: VARCHAR
- nome_aeroporto: VARCHAR
- cidade: VARCHAR
- estado: VARCHAR
- total_voos: BIGINT
- voos_atrasados: BIGINT
- taxa_atrasos_percentual: DOUBLE

**Mart 02 — aeroportos_taxa_cancelamentos**

- codigo_iata: VARCHAR
- nome_aeroporto: VARCHAR
- cidade: VARCHAR
- estado: VARCHAR
- total_voos: BIGINT
- voos_cancelados: BIGINT
- taxa_cancelamentos_percentual: DOUBLE

**Mart 03 — aeroportos_tempo_medio_atraso**

- codigo_iata: VARCHAR
- nome_aeroporto: VARCHAR
- cidade: VARCHAR
- estado: VARCHAR
- total_voos: BIGINT
- voos_atrasados: BIGINT
- tempo_medio_atraso_minutos: DOUBLE

**Mart 04 — companhias_taxa_atrasos**

- codigo_companhia: VARCHAR
- companhia_aerea: VARCHAR
- total_voos: BIGINT
- voos_atrasados: BIGINT
- taxa_atrasos_percentual: DOUBLE

**Mart 05 — companhias_taxa_cancelamentos**

- codigo_companhia: VARCHAR
- companhia_aerea: VARCHAR
- total_voos: BIGINT
- voos_cancelados: BIGINT
- taxa_cancelamentos_percentual: DOUBLE

**Mart 06 — companhias_comparativo_pontualidade**

- codigo_companhia: VARCHAR
- companhia_aerea: VARCHAR
- total_voos: BIGINT
- voos_pontuais: BIGINT
- voos_atrasados: BIGINT
- taxa_pontualidade_percentual: DOUBLE
- media_atraso_minutos: DOUBLE

**Mart 07 — rotas_taxa_atrasos**

- codigo_origem: VARCHAR
- aeroporto_origem: VARCHAR
- cidade_origem: VARCHAR
- codigo_destino: VARCHAR
- aeroporto_destino: VARCHAR
- cidade_destino: VARCHAR
- total_voos: BIGINT
- voos_atrasados: BIGINT
- taxa_atrasos_percentual: DOUBLE

**Mart 08 — rotas_quantidade_cancelamentos**

- codigo_origem: VARCHAR
- aeroporto_origem: VARCHAR
- cidade_origem: VARCHAR
- codigo_destino: VARCHAR
- aeroporto_destino: VARCHAR
- cidade_destino: VARCHAR
- total_voos: BIGINT
- voos_cancelados: BIGINT
- taxa_cancelamentos_percentual: DOUBLE

**Mart 09 — horarios_taxa_atrasos**

- faixa_horario_partida: VARCHAR
- total_voos: BIGINT
- voos_atrasados: BIGINT
- taxa_atrasos_percentual: DOUBLE
- media_atraso_minutos: DOUBLE

**Mart 10 — dias_semana_taxa_atrasos**

- dia_semana: INTEGER
- nome_dia_semana: VARCHAR
- total_voos: BIGINT
- voos_atrasados: BIGINT
- taxa_atrasos_percentual: DOUBLE
- media_atraso_minutos: DOUBLE

**Mart 11 — kpis**

- total_voos: BIGINT
- pct_atrasos: DOUBLE
- pct_cancelamentos: DOUBLE
- atraso_medio_minutos: DOUBLE
- total_companhias: BIGINT
- total_aeroportos: BIGINT

Grão: operação inteira, uma única linha.

Resultado já validado:
- total_voos: 120.000
- pct_atrasos: 21,56
- pct_cancelamentos: 1,49
- atraso_medio_minutos: 73,52
- total_companhias: 14
- total_aeroportos: valor retornado diretamente pelo banco.

**Mart 12 — operacao_por_estado**

- estado: VARCHAR
- total_voos: BIGINT
- pct_atrasos: DOUBLE
- pct_cancelamentos: DOUBLE

Grão: um estado de origem.

Resultado já validado: 52 linhas.

## 4. ARTEFATOS A PRODUZIR

Criar dois arquivos na raiz do projeto:

### painel.py

Responsável por:
- Ler os Marts.
- Formatar os valores.
- Preparar os dados para apresentação.
- Construir as figuras Plotly.

Não importar Streamlit neste arquivo.

### app.py

Responsável por:
- Configurar a página.
- Organizar o layout.
- Apresentar os cartões.
- Apresentar os gráficos.
- Gerenciar o cache.
- Apresentar erros.

Executar com:

```powershell
uv run streamlit run app.py
```

Não criar outros módulos sem necessidade.

## 5. LEITURA DOS DADOS — painel.py

Criar a função:

```python
ler(marts) -> dict
```

Recebe uma lista com os nomes das tabelas e retorna um dicionário de DataFrames.

Exemplo:

```python
{
    "kpis": dataframe,
    "aeroportos_taxa_atrasos": dataframe,
    "operacao_por_estado": dataframe
}
```

Para cada tabela, executar exclusivamente:

```sql
SELECT * FROM marts.<nome_da_tabela>
```

Regras:

- Não executar outras consultas SQL.
- Não consultar RAW ou REFINED.
- Não criar JOINs.
- Não recriar os Marts.
- Não modificar os dados retornados.
- Não calcular indicadores.

A conexão deve ser criada dentro da função, com `read_only=True`, e fechada com `try/finally`.

## 6. PROIBIÇÃO DE CÁLCULOS DE NEGÓCIO

Em `painel.py` e `app.py`, são proibidos:

- groupby
- sum
- mean
- count
- merge
- pivot
- JOIN
- Cálculos entre colunas.
- Recalcular percentuais.
- Criar indicadores novos.
- Recalcular médias.
- Alterar denominadores.

Permitido:

- Ordenar registros.
- Selecionar os 10 primeiros registros.
- Filtrar linhas para apresentação.
- Renomear colunas.
- Formatar números.
- Concatenar textos para rótulos.
- Configurar eixos e títulos.
- Construir gráficos com Plotly.

Se algum indicador necessário não existir nos Marts, interromper a implementação e informar qual Mart está faltando.

## 7. LAYOUT — app.py

Configuração:

```python
st.set_page_config(
    page_title="Aviação EUA | Visão da Operação",
    layout="wide"
)
```

### Identidade visual (revisada e aprovada; substitui o fundo escuro da referência Olist)

Tema claro de dashboard executivo: fundo `#f4f6f8`, cartões e gráficos em
blocos brancos com cantos arredondados e sombra suave, texto `#1d2433`
(principal) e `#5b6473` (secundário).

Cor única: o verde do cabeçalho, `#1f7a68` (contraste 5,2:1 sobre o branco),
em todos os gráficos e cartões. Uma versão com uma cor por categoria foi
testada e descartada a pedido da usuária.

- Todas as barras de todos os gráficos usam `#1f7a68`. Não colorir barras
  individualmente.
- Cartões: fundo verde-claro `#e5f2ef`, borda lateral e ícone em `#1f7a68`,
  valor em destaque no texto principal.
- Cada faixa tem um título curto: Indicadores gerais · Destaque · Atrasos por
  aeroporto · Aeroportos e companhias · Companhias e rotas · Rotas, horários e
  dias da semana · Visão geográfica.
- Gráficos: título em negrito; subtítulo em cinza quando houver (gráficos 01 e 02).
- A identidade visual não altera dados, ordenações, regras nem indicadores.

Não implementar filtro de período nesta versão.

### Cabeçalho

Título:

**Aviação EUA · Visão da operação**

Alinhado à esquerda, com ícone de avião, dentro de uma faixa de destaque na cor
teal da marca (`#1f7a68`), texto branco e o botão **Recarregar dados** à direita.

Conteúdo da faixa (contexto único; não se repete nos gráficos):

- Descrição: `Dashboard executivo de desempenho da aviação norte-americana`
- Período: `Período analisado: 2025 · Operação aérea dos Estados Unidos`
- Fonte: `Fonte: amostra de <total_voos> voos · camada analítica MARTS (aviation.duckdb)`

- `<total_voos>` vem de `kpis.total_voos`, no formato de número inteiro.
  Se o Mart 11 estiver indisponível, a fonte mostra só a camada analítica.
- Validação feita em `refined.voos_2025.data_voo`: de 2025-01-01 a 2025-12-31,
  365 dias, 10.000 voos por mês, nenhum registro sem data. Os estados de origem e
  destino são só dos EUA: 49 estados mais os territórios PR, VI e TT.
- "Amostra" é obrigatório: os 120.000 voos são uma amostra de 2025, não o total
  operado no ano.

### FAIXA 1 — CINCO CARTÕES

Utilizar `st.metric`.

Ordem obrigatória:

1. **Total de voos**
   - `kpis.total_voos`
   - Número inteiro com separador de milhar.

2. **Voos atrasados**
   - `kpis.pct_atrasos`
   - Percentual com duas casas decimais.

3. **Voos cancelados**
   - `kpis.pct_cancelamentos`
   - Percentual com duas casas decimais.

4. **Atraso médio**
   - `kpis.atraso_medio_minutos`
   - Duas casas decimais e unidade em minutos.

5. **Total de aeroportos**
   - `kpis.total_aeroportos`
   - Número inteiro com separador de milhar.

Não exibir o indicador total_companhias nesta primeira versão.

Não inserir valores fixos no código. Todos os cartões devem ler os dados do Mart 11.

### FAIXA 2 — GRÁFICO PRINCIPAL

**01 · Aeroportos com maior taxa de atrasos**

- Origem: `aeroportos_taxa_atrasos`.
- Tipo: barras horizontais.
- Grupo de análise: os 30 aeroportos com maior `total_voos` do próprio Mart 01
  (regra de volume descrita abaixo).
- Top 10 aeroportos, dentro desse grupo.
- Ordenar pela coluna `taxa_atrasos_percentual`, da maior para a menor.
- Maior taxa no topo.
- Identificar aeroportos por `codigo_iata` ou `nome_aeroporto`.
- Eixo de valores em percentual.
- Subtítulo informando que o ranking considera os 30 aeroportos com mais voos.

Este é o gráfico de maior destaque do dashboard.

#### Regra de volume dos gráficos 01 e 02 (aprovada após demonstração)

Motivo: aeroportos com pouquíssimos voos (5 a 27) ocupavam o Top 10 com taxas
distorcidas, nas quais um único atraso ou cancelamento alterava a taxa em
5 a 20 pontos percentuais.

1. Selecionar os 30 aeroportos com maior `total_voos` do Mart do próprio gráfico.
2. Desempate no volume: `codigo_iata` em ordem crescente, para resultado reproduzível.
3. Dentro desse grupo, exibir os 10 com maior taxa, em ordem decrescente.
   Empate na taxa: mantém a ordem da seleção (maior `total_voos`, depois `codigo_iata`).
4. Cada gráfico usa o volume do próprio Mart (01 ou 02). A seleção não é compartilhada,
   pois `total_voos` difere entre os Marts.
5. A regra só ordena e seleciona linhas. Nenhum valor é recalculado e os Marts não mudam.
6. Os demais gráficos e indicadores não usam essa regra.

### FAIXA 3 — TRÊS COLUNAS

**02 · Aeroportos com maior taxa de cancelamentos**

- Mart: `aeroportos_taxa_cancelamentos`.
- Barras horizontais.
- Grupo de análise: os 30 aeroportos com maior `total_voos` do próprio Mart 02
  (regra de volume dos gráficos 01 e 02).
- Top 10, dentro desse grupo.
- Ordenação por `taxa_cancelamentos_percentual`, decrescente.
- Eixo em percentual.
- Subtítulo informando que o ranking considera os 30 aeroportos com mais voos.

**03 · Aeroportos com maior tempo médio de atraso**

- Mart: `aeroportos_tempo_medio_atraso`.
- Barras horizontais.
- Top 10.
- Ordenação por `tempo_medio_atraso_minutos`, decrescente.
- Eixo em minutos.

**04 · Companhias com maior taxa de atrasos**

- Mart: `companhias_taxa_atrasos`.
- Barras horizontais.
- Ordenação por `taxa_atrasos_percentual`, decrescente.
- Eixo em percentual.

### FAIXA 4 — TRÊS COLUNAS

**05 · Companhias com maior taxa de cancelamentos**

- Mart: `companhias_taxa_cancelamentos`.
- Barras horizontais.
- Ordenação por `taxa_cancelamentos_percentual`, decrescente.
- Eixo em percentual.

**06 · Comparativo de pontualidade por companhia**

- Mart: `companhias_comparativo_pontualidade`.
- Barras horizontais.
- Utilizar `taxa_pontualidade_percentual`.
- Ordenar pela taxa de pontualidade.
- Mostrar companhia aérea.
- Eixo em percentual.

**07 · Rotas com maior taxa de atrasos**

- Mart: `rotas_taxa_atrasos`.
- Barras horizontais.
- Top 10.
- Ordenação por `taxa_atrasos_percentual`, decrescente.
- Eixo em percentual.

Para identificar uma rota, concatenar somente os códigos existentes:

`codigo_origem → codigo_destino`

Exemplo: `ATL → LAX`.

Essa concatenação é permitida porque é somente um rótulo de apresentação. Não cria indicador ou consulta nova.

### FAIXA 5 — TRÊS COLUNAS

**08 · Rotas com maior quantidade de cancelamentos**

- Mart: `rotas_quantidade_cancelamentos`.
- Barras horizontais.
- Top 10.
- Ordenação por `voos_cancelados`, decrescente.
- Eixo em quantidade de voos cancelados.
- Identificação da rota no formato `ATL → LAX`.

**09 · Horários com maior taxa de atrasos**

- Mart: `horarios_taxa_atrasos`.
- Gráfico de barras.
- Eixo em percentual.
- Utilizar `faixa_horario_partida`.
- Ordenar cronologicamente pela faixa inicial.

As faixas possuem formato textual padronizado, por exemplo:

- `00:01 - 05:59`
- `06:00 - 06:59`
- `07:00 - 07:59`
- ...
- `23:00 - 23:59`

A ordenação textual crescente funciona para esse padrão com horários preenchidos com zeros à esquerda.

Não utilizar ordenação alfabética decrescente.

Não criar uma coluna de cálculo para ordenar.

**10 · Dias da semana com maior taxa de atrasos**

- Mart: `dias_semana_taxa_atrasos`.
- Gráfico de barras.
- Eixo em percentual.
- Utilizar `nome_dia_semana`.
- Ordenar por `dia_semana`, crescente.
- Preservar a correspondência original entre número e nome do dia.
- Acentuação somente no rótulo exibido: `Terca-feira` → `Terça-feira` e
  `Sabado` → `Sábado`. O Mart permanece com os nomes originais; um nome não
  previsto é exibido como veio do banco.

### FAIXA 6 — VISÃO GEOGRÁFICA

**12 · Operação por estado**

- Mart: `operacao_por_estado`.
- Barras horizontais.
- Top 10 estados por `total_voos`.
- Ordenação decrescente.
- Eixo em quantidade de voos.
- Identificação pelo campo `estado`.

O percentual de atrasos e o percentual de cancelamentos já estão disponíveis no Mart, mas não devem ser recalculados.

## 8. FORMATAÇÃO — painel.py

Criar funções puras, sem acesso ao banco e sem importação de Streamlit.

### numero(valor, casas=0)

Exemplo:

`120000` → `120.000`

### pct(valor, casas=2)

Exemplo:

`21.56` → `21,56%`

### minutos(valor, casas=2)

Exemplo:

`73.52` → `73,52 min`

Regras:

- Milhar com ponto.
- Decimal com vírgula.
- Não depender do locale do sistema.
- Tratar valores nulos com `—`.
- Não modificar os valores numéricos originais.

### Funções de gráficos

Criar uma função independente para cada gráfico.

Cada função:

- Recebe um DataFrame.
- Utiliza apenas as colunas já existentes.
- Retorna uma figura Plotly.
- Não acessa o banco.
- Não importa Streamlit.
- Não calcula indicadores.

Motivo: permitir reaproveitar os gráficos futuramente em um relatório HTML.

## 9. CACHE E ATUALIZAÇÃO

A leitura deverá utilizar `st.cache_data` na integração com `app.py`.

A função `ler()` permanece independente do Streamlit, dentro de `painel.py`.

Criar botão:

**Recarregar dados**

Ao clicar:

- Limpar o cache.
- Fazer uma nova leitura dos Marts.
- Atualizar os cartões e gráficos.

A leitura deve fechar a conexão antes de retornar os DataFrames.

Não manter conexão aberta enquanto o painel estiver em execução.

## 10. TRATAMENTO DE ERROS

Se `aviation.duckdb` não existir:

- Mostrar `st.error`.
- Informar que o banco não foi encontrado.
- Interromper com `st.stop()`.

Se faltar algum dos 12 Marts:

- Informar os nomes das tabelas ausentes.
- Não tentar criar as tabelas automaticamente.
- Não executar `pipeline.marts` automaticamente.
- Orientar o usuário a executar manualmente:

```powershell
uv run python -m pipeline.marts
```

Antes de executar esse comando, o usuário deverá garantir que não há outro processo mantendo o banco aberto.

Se houver erro de conexão:

- Exibir a mensagem de erro.
- Não repetir tentativas automaticamente.
- Não iniciar MCP.
- Não encerrar processos automaticamente.

Se uma coluna esperada não existir:

- Informar o Mart e a coluna ausente.
- Interromper a implementação ou a apresentação afetada.
- Não inventar nomes alternativos.

Se um Mart estiver vazio:

- Informar o nome do Mart.
- Não apresentar gráfico vazio como se fosse válido.

Não apresentar resultados parciais como se todos os dados estivessem corretos.

## 11. CRITÉRIOS DE ACEITAÇÃO

### Leitura

- [ ] Os 12 Marts são lidos.
- [ ] Somente `SELECT *` é executado para cada Mart.
- [ ] Nenhuma consulta adicional de negócio é realizada.
- [ ] Conexão DuckDB em modo somente leitura.
- [ ] Conexão fechada após a leitura.
- [ ] Nenhuma conexão persistente.
- [ ] Nenhum uso do MCP para leitura.

### Cartões

- [ ] Total de voos: 120.000.
- [ ] Percentual de atrasos: 21,56%.
- [ ] Percentual de cancelamentos: 1,49%.
- [ ] Atraso médio: 73,52 minutos.
- [ ] Total de aeroportos: valor lido diretamente do Mart 11.

### Gráficos

- [ ] Gráfico 01: aeroportos com maior taxa de atrasos, entre os 30 com maior volume do Mart 01.
- [ ] Gráfico 02: aeroportos com maior taxa de cancelamentos, entre os 30 com maior volume do Mart 02.
- [ ] Gráficos 01 e 02: seleção dos 30 determinística (desempate por `codigo_iata`).
- [ ] Gráfico 03: aeroportos com maior tempo médio de atraso.
- [ ] Gráfico 04: companhias com maior taxa de atrasos.
- [ ] Gráfico 05: companhias com maior taxa de cancelamentos.
- [ ] Gráfico 06: comparativo de pontualidade.
- [ ] Gráfico 07: rotas com maior taxa de atrasos.
- [ ] Gráfico 08: rotas com maior quantidade de cancelamentos.
- [ ] Gráfico 09: horários em ordem cronológica.
- [ ] Gráfico 10: dias da semana em ordem correta, com acentuação apenas no rótulo.
- [ ] Gráfico 12: estados com maior quantidade de voos.

### Arquitetura

- [ ] `painel.py` não importa Streamlit.
- [ ] `app.py` não contém consultas SQL de negócio.
- [ ] Nenhum cálculo de negócio no Python.
- [ ] Nenhum JOIN no Python.
- [ ] Nenhum indicador novo.
- [ ] Formatação brasileira.
- [ ] Gráficos construídos com Plotly.

### Funcionamento e estabilidade

- [ ] Dashboard inicia com `uv run streamlit run app.py`.
- [ ] Botão de recarregar funciona.
- [ ] Banco ausente é tratado.
- [ ] Mart ausente é tratado.
- [ ] Erro de leitura é tratado.
- [ ] Conexão é fechada após cada leitura.
- [ ] O dashboard não mantém o banco bloqueado.
- [ ] O orquestrador pode executar depois que o dashboard fecha sua leitura, sem erro de lock.

## 12. ENTREGA

1. Colocar esta SPEC como docstring no topo de `painel.py`.
2. Implementar `painel.py`.
3. Implementar `app.py`.
4. Comentar o código somente onde a decisão não for óbvia.
5. Executar os testes.
6. Apresentar os resultados dos critérios de aceitação.
7. Apresentar uma lista de decisões assumidas que não estavam explicitamente descritas nesta SPEC.

## 13. ORDEM OBRIGATÓRIA DE EXECUÇÃO

Para evitar travamentos e alterações desnecessárias:

**ETAPA A — Conferência do projeto**

- Ler `pyproject.toml`.
- Conferir as dependências.
- Conferir se `painel.py` e `app.py` já existem.
- Não abrir conexão MCP.
- Não executar inspeção geral do banco.
- Não alterar arquivos existentes sem necessidade.

**ETAPA B — Implementar painel.py**

- Criar a docstring com esta SPEC.
- Implementar a leitura.
- Implementar as funções de formatação.
- Implementar as funções dos gráficos.
- Verificar sintaxe.

**ETAPA C — Implementar app.py**

- Criar o layout definido.
- Integrar a leitura com cache.
- Exibir os cinco cartões.
- Exibir os gráficos.
- Implementar recarga e tratamento de erros.

**ETAPA D — Validar**

- Executar verificações de sintaxe.
- Executar o dashboard.
- Validar cartões e gráficos.
- Testar recarga.
- Confirmar que a conexão é fechada.
- Não executar o orquestrador durante os testes.

**ETAPA E — Apresentar resultado**

Informar:
- Arquivos criados ou alterados.
- Testes executados.
- Critérios aprovados.
- Problemas encontrados.
- Decisões assumidas.

Não ficar repetindo comandos ou tentativas indefinidamente.

Se uma etapa falhar, parar, explicar o erro e aguardar orientação.

**Esta SPEC é a fonte da verdade para a implementação do Dashboard de Aviação EUA.**
"""

import re
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px

CAMINHO_BANCO = Path(__file__).resolve().parent / "aviation.duckdb"

# Estrutura documentada na SPEC (seção 3). A ordem das chaves é a ordem de leitura.
COLUNAS = {
    "aeroportos_taxa_atrasos": [
        "codigo_iata",
        "nome_aeroporto",
        "cidade",
        "estado",
        "total_voos",
        "voos_atrasados",
        "taxa_atrasos_percentual",
    ],
    "aeroportos_taxa_cancelamentos": [
        "codigo_iata",
        "nome_aeroporto",
        "cidade",
        "estado",
        "total_voos",
        "voos_cancelados",
        "taxa_cancelamentos_percentual",
    ],
    "aeroportos_tempo_medio_atraso": [
        "codigo_iata",
        "nome_aeroporto",
        "cidade",
        "estado",
        "total_voos",
        "voos_atrasados",
        "tempo_medio_atraso_minutos",
    ],
    "companhias_taxa_atrasos": [
        "codigo_companhia",
        "companhia_aerea",
        "total_voos",
        "voos_atrasados",
        "taxa_atrasos_percentual",
    ],
    "companhias_taxa_cancelamentos": [
        "codigo_companhia",
        "companhia_aerea",
        "total_voos",
        "voos_cancelados",
        "taxa_cancelamentos_percentual",
    ],
    "companhias_comparativo_pontualidade": [
        "codigo_companhia",
        "companhia_aerea",
        "total_voos",
        "voos_pontuais",
        "voos_atrasados",
        "taxa_pontualidade_percentual",
        "media_atraso_minutos",
    ],
    "rotas_taxa_atrasos": [
        "codigo_origem",
        "aeroporto_origem",
        "cidade_origem",
        "codigo_destino",
        "aeroporto_destino",
        "cidade_destino",
        "total_voos",
        "voos_atrasados",
        "taxa_atrasos_percentual",
    ],
    "rotas_quantidade_cancelamentos": [
        "codigo_origem",
        "aeroporto_origem",
        "cidade_origem",
        "codigo_destino",
        "aeroporto_destino",
        "cidade_destino",
        "total_voos",
        "voos_cancelados",
        "taxa_cancelamentos_percentual",
    ],
    "horarios_taxa_atrasos": [
        "faixa_horario_partida",
        "total_voos",
        "voos_atrasados",
        "taxa_atrasos_percentual",
        "media_atraso_minutos",
    ],
    "dias_semana_taxa_atrasos": [
        "dia_semana",
        "nome_dia_semana",
        "total_voos",
        "voos_atrasados",
        "taxa_atrasos_percentual",
        "media_atraso_minutos",
    ],
    "kpis": [
        "total_voos",
        "pct_atrasos",
        "pct_cancelamentos",
        "atraso_medio_minutos",
        "total_companhias",
        "total_aeroportos",
    ],
    "operacao_por_estado": [
        "estado",
        "total_voos",
        "pct_atrasos",
        "pct_cancelamentos",
    ],
}

MARTS = list(COLUNAS)

# Identidade visual (SPEC seção 7): uma única cor, o verde do cabeçalho, em todos os
# gráficos e cartões.
COR_MARCA = "#1f7a68"
COR_MARCA_SUAVE = "#e5f2ef"  # fundo dos cartões
COR_TEXTO = "#1d2433"
COR_TEXTO_SECUNDARIO = "#5b6473"
COR_GRADE = "#e6e9ee"


# ---------------------------------------------------------------- leitura


class BancoNaoEncontrado(Exception):
    pass


class MartsAusentes(Exception):
    def __init__(self, ausentes):
        self.ausentes = list(ausentes)
        super().__init__(", ".join(self.ausentes))


class ErroLeitura(Exception):
    pass


def ler(marts) -> dict:
    """Executa somente `SELECT * FROM marts.<nome>` para cada Mart e fecha a conexão."""
    for nome in marts:
        # O nome entra na SQL por interpolação; aceitar só identificadores simples.
        if not re.fullmatch(r"[a-z_][a-z0-9_]*", nome):
            raise ValueError(f"Nome de Mart inválido: {nome!r}")

    if not CAMINHO_BANCO.is_file():
        raise BancoNaoEncontrado(str(CAMINHO_BANCO))

    dados, ausentes = {}, []
    try:
        con = duckdb.connect(str(CAMINHO_BANCO), read_only=True)
    except duckdb.Error as erro:
        raise ErroLeitura(str(erro)) from erro

    try:
        for nome in marts:
            try:
                dados[nome] = con.execute(f"SELECT * FROM marts.{nome}").df()
            except duckdb.CatalogException:
                # Continua para listar todos os Marts ausentes de uma só vez.
                ausentes.append(nome)
    except duckdb.Error as erro:
        raise ErroLeitura(str(erro)) from erro
    finally:
        con.close()

    if ausentes:
        raise MartsAusentes(ausentes)
    return dados


def problema(dados, mart):
    """Mensagem de erro de apresentação do Mart (colunas ausentes ou vazio), ou None."""
    df = dados[mart]
    faltando = [c for c in COLUNAS[mart] if c not in df.columns]
    if faltando:
        return f"Mart `{mart}`: coluna(s) ausente(s): {', '.join(faltando)}."
    if df.empty:
        return f"Mart `{mart}` está vazio."
    return None


# ------------------------------------------------------------- formatação


def numero(valor, casas=0):
    if valor is None or pd.isna(valor):
        return "—"
    # Formata no padrão en-US e troca os separadores: independe do locale do sistema.
    return f"{valor:,.{casas}f}".translate(str.maketrans(",.", ".,"))


def pct(valor, casas=2):
    texto = numero(valor, casas)
    return texto if texto == "—" else f"{texto}%"


def minutos(valor, casas=2):
    texto = numero(valor, casas)
    return texto if texto == "—" else f"{texto} min"


# ---------------------------------------------------------------- gráficos


def _estilo(fig, titulo, altura, subtitulo=None):
    fig.update_layout(
        title={
            "text": titulo,
            "x": 0,
            "xanchor": "left",
            "font": {"size": 16, "color": COR_TEXTO, "weight": 600},
            "subtitle": {
                "text": subtitulo or "",
                "font": {"size": 12, "color": COR_TEXTO_SECUNDARIO},
            },
        },
        height=altura,
        # Decimal com vírgula e milhar com ponto nos eixos, rótulos e tooltips.
        separators=",.",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": COR_TEXTO_SECUNDARIO, "size": 12},
        margin={"l": 8, "r": 56, "t": 76 if subtitulo else 52, "b": 8},
        bargap=0.35,
        barcornerradius=4,
        showlegend=False,
        hoverlabel={
            "bgcolor": "#ffffff",
            "font_color": COR_TEXTO,
            "bordercolor": COR_GRADE,
        },
    )
    fig.update_xaxes(
        gridcolor=COR_GRADE,
        zerolinecolor=COR_GRADE,
        linecolor=COR_GRADE,
        title_font_size=12,
    )
    fig.update_yaxes(
        gridcolor=COR_GRADE,
        zerolinecolor=COR_GRADE,
        linecolor=COR_GRADE,
        title_font_size=12,
    )
    return fig


def _barras_h(
    df,
    x,
    y,
    titulo,
    eixo,
    formato,
    sufixo,
    hover,
    custom,
    cor,
    altura=380,
    subtitulo=None,
):
    fig = px.bar(df, x=x, y=y, orientation="h", custom_data=custom)
    fig.update_traces(
        marker_color=cor,
        texttemplate=f"%{{x:{formato}}}{sufixo}",
        textposition="outside",
        textfont_color=COR_TEXTO_SECUNDARIO,
        cliponaxis=False,
        hovertemplate=hover + "<extra></extra>",
    )
    # O DataFrame chega em ordem decrescente; inverter o eixo põe o maior no topo.
    fig.update_yaxes(type="category", autorange="reversed", title=None, showgrid=False)
    fig.update_xaxes(title=eixo, ticksuffix=sufixo)
    return _estilo(fig, titulo, altura, subtitulo)


def _barras_v(df, x, y, titulo, eixo, hover, custom, cor, altura=380):
    fig = px.bar(df, x=x, y=y, custom_data=custom)
    fig.update_traces(
        marker_color=cor,
        texttemplate="%{y:.2f}%",
        textposition="outside",
        textfont_color=COR_TEXTO_SECUNDARIO,
        cliponaxis=False,
        hovertemplate=hover + "<extra></extra>",
    )
    # Mantém a ordem do DataFrame no eixo de categorias.
    fig.update_xaxes(
        type="category",
        categoryorder="array",
        categoryarray=list(df[x]),
        title=None,
        showgrid=False,
    )
    fig.update_yaxes(title=eixo, ticksuffix="%")
    return _estilo(fig, titulo, altura)


def _top(df, coluna, n=10):
    return df.sort_values(coluna, ascending=False, kind="stable").head(n)


AEROPORTOS_POR_VOLUME = 30
_SUBTITULO_VOLUME = f"Entre os {AEROPORTOS_POR_VOLUME} aeroportos com mais voos"


def _maiores_volumes(df, n=AEROPORTOS_POR_VOLUME):
    # Regra de volume dos gráficos 01 e 02 (SPEC seção 7): só ordena e seleciona.
    # O desempate por codigo_iata torna a seleção reproduzível; o _top seguinte é
    # estável, então empates na taxa mantêm essa ordem.
    return df.sort_values(
        ["total_voos", "codigo_iata"], ascending=[False, True], kind="stable"
    ).head(n)


def _com_rota(df):
    # Rótulo de apresentação apenas (SPEC seção 7, gráfico 07).
    return df.assign(rota=df["codigo_origem"] + " → " + df["codigo_destino"])


_HOVER_AEROPORTO = (
    "<b>%{y}</b> · %{customdata[0]}<br>%{customdata[1]} / %{customdata[2]}"
)
_HOVER_ROTA = "<b>%{y}</b><br>%{customdata[0]} (%{customdata[1]})<br>→ %{customdata[2]} (%{customdata[3]})"


def grafico_01_aeroportos_atrasos(df):
    return _barras_h(
        _top(_maiores_volumes(df), "taxa_atrasos_percentual"),
        "taxa_atrasos_percentual",
        "codigo_iata",
        "01 · Aeroportos com maior taxa de atrasos",
        "Taxa de atrasos",
        ".2f",
        "%",
        _HOVER_AEROPORTO + "<br>Taxa de atrasos: %{x:.2f}%"
        "<br>Voos: %{customdata[3]:,.0f} · Atrasados: %{customdata[4]:,.0f}",
        ["nome_aeroporto", "cidade", "estado", "total_voos", "voos_atrasados"],
        altura=460,
        cor=COR_MARCA,
        subtitulo=_SUBTITULO_VOLUME,
    )


def grafico_02_aeroportos_cancelamentos(df):
    return _barras_h(
        _top(_maiores_volumes(df), "taxa_cancelamentos_percentual"),
        "taxa_cancelamentos_percentual",
        "codigo_iata",
        "02 · Aeroportos com maior taxa de cancelamentos",
        "Taxa de cancelamentos",
        ".2f",
        "%",
        _HOVER_AEROPORTO + "<br>Taxa de cancelamentos: %{x:.2f}%"
        "<br>Voos: %{customdata[3]:,.0f} · Cancelados: %{customdata[4]:,.0f}",
        ["nome_aeroporto", "cidade", "estado", "total_voos", "voos_cancelados"],
        cor=COR_MARCA,
        subtitulo=_SUBTITULO_VOLUME,
    )


def grafico_03_aeroportos_tempo_medio(df):
    return _barras_h(
        _top(df, "tempo_medio_atraso_minutos"),
        "tempo_medio_atraso_minutos",
        "codigo_iata",
        "03 · Aeroportos com maior tempo médio de atraso",
        "Minutos",
        ".2f",
        " min",
        _HOVER_AEROPORTO + "<br>Tempo médio de atraso: %{x:.2f} min"
        "<br>Voos: %{customdata[3]:,.0f} · Atrasados: %{customdata[4]:,.0f}",
        ["nome_aeroporto", "cidade", "estado", "total_voos", "voos_atrasados"],
        cor=COR_MARCA,
    )


def grafico_04_companhias_atrasos(df):
    return _barras_h(
        df.sort_values("taxa_atrasos_percentual", ascending=False, kind="stable"),
        "taxa_atrasos_percentual",
        "companhia_aerea",
        "04 · Companhias com maior taxa de atrasos",
        "Taxa de atrasos",
        ".2f",
        "%",
        "<b>%{y}</b> (%{customdata[0]})<br>Taxa de atrasos: %{x:.2f}%"
        "<br>Voos: %{customdata[1]:,.0f} · Atrasados: %{customdata[2]:,.0f}",
        ["codigo_companhia", "total_voos", "voos_atrasados"],
        altura=460,
        cor=COR_MARCA,
    )


def grafico_05_companhias_cancelamentos(df):
    return _barras_h(
        df.sort_values("taxa_cancelamentos_percentual", ascending=False, kind="stable"),
        "taxa_cancelamentos_percentual",
        "companhia_aerea",
        "05 · Companhias com maior taxa de cancelamentos",
        "Taxa de cancelamentos",
        ".2f",
        "%",
        "<b>%{y}</b> (%{customdata[0]})<br>Taxa de cancelamentos: %{x:.2f}%"
        "<br>Voos: %{customdata[1]:,.0f} · Cancelados: %{customdata[2]:,.0f}",
        ["codigo_companhia", "total_voos", "voos_cancelados"],
        altura=460,
        cor=COR_MARCA,
    )


def grafico_06_pontualidade(df):
    return _barras_h(
        df.sort_values("taxa_pontualidade_percentual", ascending=False, kind="stable"),
        "taxa_pontualidade_percentual",
        "companhia_aerea",
        "06 · Comparativo de pontualidade por companhia",
        "Taxa de pontualidade",
        ".2f",
        "%",
        "<b>%{y}</b> (%{customdata[0]})<br>Taxa de pontualidade: %{x:.2f}%"
        "<br>Voos: %{customdata[1]:,.0f} · Pontuais: %{customdata[2]:,.0f}"
        " · Atrasados: %{customdata[3]:,.0f}<br>Média de atraso: %{customdata[4]:.2f} min",
        [
            "codigo_companhia",
            "total_voos",
            "voos_pontuais",
            "voos_atrasados",
            "media_atraso_minutos",
        ],
        altura=460,
        cor=COR_MARCA,
    )


def grafico_07_rotas_atrasos(df):
    return _barras_h(
        _com_rota(_top(df, "taxa_atrasos_percentual")),
        "taxa_atrasos_percentual",
        "rota",
        "07 · Rotas com maior taxa de atrasos",
        "Taxa de atrasos",
        ".2f",
        "%",
        _HOVER_ROTA + "<br>Taxa de atrasos: %{x:.2f}%"
        "<br>Voos: %{customdata[4]:,.0f} · Atrasados: %{customdata[5]:,.0f}",
        [
            "aeroporto_origem",
            "cidade_origem",
            "aeroporto_destino",
            "cidade_destino",
            "total_voos",
            "voos_atrasados",
        ],
        altura=460,
        cor=COR_MARCA,
    )


def grafico_08_rotas_cancelamentos(df):
    return _barras_h(
        _com_rota(_top(df, "voos_cancelados")),
        "voos_cancelados",
        "rota",
        "08 · Rotas com maior quantidade de cancelamentos",
        "Voos cancelados",
        ",.0f",
        "",
        _HOVER_ROTA + "<br>Voos cancelados: %{x:,.0f}"
        "<br>Voos: %{customdata[4]:,.0f} · Taxa de cancelamentos: %{customdata[5]:.2f}%",
        [
            "aeroporto_origem",
            "cidade_origem",
            "aeroporto_destino",
            "cidade_destino",
            "total_voos",
            "taxa_cancelamentos_percentual",
        ],
        cor=COR_MARCA,
    )


def grafico_09_horarios(df):
    # Ordenação textual crescente = cronológica, pois as faixas têm zeros à esquerda.
    return _barras_v(
        df.sort_values("faixa_horario_partida", kind="stable"),
        "faixa_horario_partida",
        "taxa_atrasos_percentual",
        "09 · Horários com maior taxa de atrasos",
        "Taxa de atrasos",
        "<b>%{x}</b><br>Taxa de atrasos: %{y:.2f}%"
        "<br>Voos: %{customdata[0]:,.0f} · Atrasados: %{customdata[1]:,.0f}"
        "<br>Média de atraso: %{customdata[2]:.2f} min",
        ["total_voos", "voos_atrasados", "media_atraso_minutos"],
        cor=COR_MARCA,
    )


# Só o texto exibido ganha acento; o Mart continua com os nomes originais.
# Nome que não estiver aqui é mostrado como veio do banco.
_ACENTOS_DIA_SEMANA = {"Terca-feira": "Terça-feira", "Sabado": "Sábado"}


def grafico_10_dias_semana(df):
    return _barras_v(
        df.sort_values("dia_semana", kind="stable").assign(
            dia_rotulo=lambda d: d["nome_dia_semana"].replace(_ACENTOS_DIA_SEMANA)
        ),
        "dia_rotulo",
        "taxa_atrasos_percentual",
        "10 · Dias da semana com maior taxa de atrasos",
        "Taxa de atrasos",
        "<b>%{x}</b><br>Taxa de atrasos: %{y:.2f}%"
        "<br>Voos: %{customdata[0]:,.0f} · Atrasados: %{customdata[1]:,.0f}"
        "<br>Média de atraso: %{customdata[2]:.2f} min",
        ["total_voos", "voos_atrasados", "media_atraso_minutos"],
        cor=COR_MARCA,
    )


def grafico_12_estados(df):
    return _barras_h(
        _top(df, "total_voos"),
        "total_voos",
        "estado",
        "12 · Operação por estado",
        "Quantidade de voos",
        ",.0f",
        "",
        "<b>%{y}</b><br>Voos: %{x:,.0f}"
        "<br>Atrasos: %{customdata[0]:.2f}% · Cancelamentos: %{customdata[1]:.2f}%",
        ["pct_atrasos", "pct_cancelamentos"],
        altura=420,
        cor=COR_MARCA,
    )


GRAFICOS = {
    "aeroportos_taxa_atrasos": grafico_01_aeroportos_atrasos,
    "aeroportos_taxa_cancelamentos": grafico_02_aeroportos_cancelamentos,
    "aeroportos_tempo_medio_atraso": grafico_03_aeroportos_tempo_medio,
    "companhias_taxa_atrasos": grafico_04_companhias_atrasos,
    "companhias_taxa_cancelamentos": grafico_05_companhias_cancelamentos,
    "companhias_comparativo_pontualidade": grafico_06_pontualidade,
    "rotas_taxa_atrasos": grafico_07_rotas_atrasos,
    "rotas_quantidade_cancelamentos": grafico_08_rotas_cancelamentos,
    "horarios_taxa_atrasos": grafico_09_horarios,
    "dias_semana_taxa_atrasos": grafico_10_dias_semana,
    "operacao_por_estado": grafico_12_estados,
}
