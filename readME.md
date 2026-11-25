# Grammy Awards Data Pipeline

Pipeline de dados desenvolvido a partir do histórico de indicações e premiações do Grammy Awards (1958–2024), utilizando como base um dataset público do Kaggle. O projeto abrange desde o tratamento de dados brutos e enriquecimento via APIs externas até a modelagem relacional em nuvem e a visualização em dashboard interativo.

**Acesse o Dashboard:** [Grammy Awards Dashboard](https://projeto-portifolio-grammy-mentoriagit-zkebh845pb58mujhuxfnb2.streamlit.app/)

## Objetivo

Estruturar registros históricos originalmente dispersos em um arquivo CSV do Kaggle em um banco de dados relacional normalizado, permitindo consultar e analisar tendências da premiação, desempenho de artistas e grupos, participação de gravadoras e evolução das categorias ao longo das edições.

## Etapas do Projeto

1. **Extração e Limpeza (ETL):** Leitura do arquivo CSV obtido no Kaggle, padronização de nomes de artistas, faixas e categorias, e tratamento de inconsistências.
2. **Enriquecimento de Dados:** Integração com as APIs do MusicBrainz, Open Opus (para compositores e obras de música clássica) e Wikidata para complementar os registros com metadados como nacionalidade, data de nascimento ou formação, gravadoras e distinção entre artistas solo, duplas e bandas.
3. **Modelagem e Armazenamento:** Criação de um esquema relacional normalizado no MySQL (`defaultdb`), hospedado na nuvem via Aiven, contemplando relacionamentos entre edições, categorias, obras (álbuns e músicas), gravadoras e indicados.
4. **Visualização:** Construção de um dashboard em Streamlit conectado ao banco de dados para exploração visual de métricas e rankings, disponível em [https://projeto-portifolio-grammy-mentoriagit-zkebh845pb58mujhuxfnb2.streamlit.app/](https://projeto-portifolio-grammy-mentoriagit-zkebh845pb58mujhuxfnb2.streamlit.app/).

## Tecnologias e Fontes de Dados

- **Python:** Tratamento de dados e consumo das APIs.
- **MySQL (Aiven):** Banco de dados relacional em nuvem.
- **Streamlit:** Interface web para exibição dos gráficos e indicadores.
- **Kaggle:** Fonte do dataset histórico original (CSV) das indicações e vencedores do Grammy.
- **MusicBrainz, Open Opus e Wikidata:** APIs externas utilizadas para o enriquecimento dos metadados musicais e biográficos.

## Estrutura do Repositório

```text
├── data/               # Dataset original do Kaggle (CSV) e arquivos processados
├── database/           # Diagrama ER, dicionário de dados e scripts SQL (DDL e DML)
├── src/                # Scripts Python de limpeza, consulta às APIs e carga no banco
├── app/                # Código da aplicação em Streamlit
└── requirements.txt    # Bibliotecas necessárias para execução
