# US Aviation Data Pipeline

Pipeline de dados desenvolvido para analisar informações sobre voos domésticos dos Estados Unidos durante o ano de 2025.

O projeto contempla desde a ingestão e transformação dos dados até a construção de indicadores analíticos, disponibilizados por meio de um dashboard interativo e de um relatório em HTML.

A solução utiliza Python, SQL e DuckDB, seguindo uma arquitetura organizada em três camadas: RAW, REFINED e MARTS.

## Objetivo do projeto

Desenvolver um pipeline de dados capaz de processar informações de voos, realizar tratamentos e padronizações, construir indicadores analíticos e disponibilizar os resultados para análise.

O objetivo é apresentar uma visão da operação aérea dos Estados Unidos, permitindo analisar atrasos, cancelamentos, pontualidade das companhias aéreas, desempenho dos aeroportos e comportamento das operações ao longo do tempo.

## Fonte dos dados

Os dados utilizados neste projeto são provenientes do conjunto **US Flight Delays and Cancellations 2025–2026**, publicado no Kaggle.

**Fonte:**  
https://www.kaggle.com/datasets/samuelpombourcq/us-flight-delays-and-cancellations-2025-2026

**Publicador:** Samuel Pombourcq.

**Licença informada:** Creative Commons CC0 1.0 Universal (Public Domain Dedication).

https://creativecommons.org/publicdomain/zero/1.0/

### Recorte dos dados

O conjunto original possui um grande volume de informações. Para viabilizar o processamento e direcionar a análise, foi selecionado exclusivamente o período de janeiro a dezembro de 2025, contemplando os 12 meses completos.

O recorte utilizado no projeto apresenta:

| Característica | Informação |
|---|---|
| Período analisado | 01/01/2025 a 31/12/2025 |
| Total de voos | 120.000 |
| Companhias aéreas | 14 |
| Aeroportos | 361 |
| Meses analisados | 12 |

## Arquitetura do projeto

O pipeline está organizado em três camadas:

### RAW

Camada responsável por armazenar os dados brutos de origem, preservando os arquivos utilizados no processo de ingestão.

Os arquivos dessa camada estão localizados na pasta `raw/`.

### REFINED

Camada responsável pelo tratamento, limpeza e padronização dos dados, preparando as informações para as análises posteriores.

### MARTS

Camada responsável pela construção das tabelas analíticas e dos indicadores utilizados no dashboard e no relatório.

As consultas SQL responsáveis pela construção dos Marts estão organizadas na pasta `sql/marts/`.

### Consultas analíticas

O projeto possui 12 consultas SQL:

| Nº | Arquivo | Análise |
|---:|---|---|
| 01 | `01_aeroportos_taxa_atrasos.sql` | Taxa de atrasos por aeroporto |
| 02 | `02_aeroportos_taxa_cancelamentos.sql` | Taxa de cancelamentos por aeroporto |
| 03 | `03_aeroportos_tempo_medio_atraso.sql` | Tempo médio de atraso por aeroporto |
| 04 | `04_companhias_taxa_atrasos.sql` | Taxa de atrasos por companhia |
| 05 | `05_companhias_taxa_cancelamentos.sql` | Taxa de cancelamentos por companhia |
| 06 | `06_companhias_comparativo_pontualidade.sql` | Comparativo de pontualidade entre companhias |
| 07 | `07_rotas_taxa_atrasos.sql` | Taxa de atrasos por rota |
| 08 | `08_rotas_quantidade_cancelamentos.sql` | Quantidade de cancelamentos por rota |
| 09 | `09_horarios_taxa_atrasos.sql` | Taxa de atrasos por horário |
| 10 | `10_dias_semana_taxa_atrasos.sql` | Taxa de atrasos por dia da semana |
| 11 | `11_kpis.sql` | Indicadores gerais da operação |
| 12 | `12_operacao_por_estado.sql` | Análise da operação por estado |

## Indicadores principais

O dashboard apresenta cinco indicadores gerais da operação aérea:

| Indicador | Resultado |
|---|---:|
| Total de voos | 120.000 |
| Voos atrasados | 21,56% |
| Voos cancelados | 1,49% |
| Tempo médio de atraso | 73,52 minutos |
| Total de aeroportos | 361 |

Além dos indicadores principais, o projeto disponibiliza visualizações para análise de aeroportos, companhias aéreas, rotas, horários, dias da semana e operações por estado.

## Dashboard e relatório

O projeto disponibiliza duas formas de visualização dos resultados:

**Dashboard interativo**

Desenvolvido com Streamlit e Plotly, permite explorar os indicadores e as análises da operação aérea.

Para executar:

```bash
uv run streamlit run app.py
```

**Relatório HTML**

Relatório analítico gerado a partir dos dados processados, disponibilizado no arquivo `relatorio.html`.

Para gerar novamente:

```bash
uv run python relatorio.py
```

## Tecnologias utilizadas

- **Python:** desenvolvimento e execução do pipeline.
- **DuckDB:** armazenamento e processamento analítico dos dados.
- **SQL:** transformação, agregação e construção dos indicadores.
- **Pandas:** manipulação e tratamento de dados.
- **Streamlit:** desenvolvimento do dashboard interativo.
- **Plotly:** construção de gráficos e visualizações.
- **Pytest:** testes automatizados.
- **pytest-cov:** acompanhamento da cobertura de testes.
- **uv:** gerenciamento de dependências e ambiente Python.

## Estrutura do repositório

```text
us-aviation-data-pipeline/
│
├── raw/                       # Dados brutos de origem
│
├── pipeline/
│   ├── db.py                  # Configurações do banco de dados
│   ├── ingestao.py             # Processo de ingestão
│   ├── transformacao.py        # Processo de transformação
│   └── marts.py                # Construção dos Marts
│
├── sql/
│   └── marts/                  # 12 consultas SQL analíticas
│
├── test/                       # Testes automatizados
│
├── app.py                      # Aplicação Streamlit
├── painel.py                   # Indicadores e visualizações
├── relatorio.py                # Geração do relatório HTML
├── relatorio.html              # Relatório gerado
├── ui.py                       # Interface auxiliar
│
├── pyproject.toml              # Dependências e configurações
├── uv.lock                     # Versões fixadas das dependências
├── README.md
└── LICENSE
```

Os bancos DuckDB são gerados localmente durante o processamento e não são versionados no Git.

## Como executar o projeto

### Pré-requisitos

- Python 3.13 ou superior.
- uv instalado.
- Git.

### 1. Clonar o repositório

```bash
git clone https://github.com/roseanegouveas-creator/us-aviation-data-pipeline.git
```

Acesse a pasta:

```bash
cd us-aviation-data-pipeline
```

### 2. Instalar as dependências

```bash
uv sync
```

### 3. Executar o pipeline

As etapas devem ser executadas na seguinte ordem:

**Ingestão dos dados**

```bash
uv run python -m pipeline.ingestao
```

**Transformação dos dados**

```bash
uv run python -m pipeline.transformacao
```

**Construção das tabelas analíticas (Marts)**

```bash
uv run python -m pipeline.marts
```

### 4. Executar o dashboard

```bash
uv run streamlit run app.py
```

### 5. Gerar o relatório HTML

```bash
uv run python relatorio.py
```

### 6. Executar os testes automatizados

```bash
uv run pytest --cov
```

## Testes e qualidade

O projeto possui testes automatizados para validar os principais componentes do pipeline:

- Conexão e operações com DuckDB.
- Ingestão de dados.
- Transformação e tratamento.
- Construção dos Marts.
- Indicadores e componentes do painel.
- Geração do relatório.

A execução dos testes utiliza Pytest, com acompanhamento da cobertura de código por meio do pytest-cov.

## Reprodutibilidade

Para reproduzir a análise, é necessário disponibilizar os arquivos de dados de origem na pasta `raw/` e executar as etapas do pipeline na ordem indicada.

Os arquivos SQL documentam as consultas utilizadas para construir as tabelas analíticas e os indicadores apresentados no dashboard.

Os bancos de dados são produzidos localmente durante a execução e não precisam ser baixados do repositório.

## Licença

Os dados utilizados neste projeto são identificados com a licença CC0 1.0, conforme informado para o conjunto de dados de origem.

Consulte o arquivo [LICENSE](LICENSE) para informações sobre a origem e a licença dos dados.

O código-fonte, as consultas SQL e os materiais de desenvolvimento deste projeto não estão automaticamente abrangidos pela licença CC0 aplicada aos dados.

---

Desenvolvido para fins de estudo, análise de dados e demonstração de construção de pipelines analíticos.