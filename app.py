import pandas as pd
import streamlit as st
from db import run_query

st.set_page_config(
    page_title="Grammy Data Pipeline — Dashboard",
    layout="wide",
)

st.title("Grammy Data Pipeline — Painel Analítico")
st.caption(
    "Consulta relacional consolidada a partir da base histórica do GRAMMY Awards "
    "enriquecida via API e armazenada em MySQL."
)

TABELAS_ESQUEMA = [
    "Pessoa",
    "Album",
    "Faixa",
    "Gravadora",
    "Categoria",
    "Cerimonia",
    "Indicação",
    "Genero",
    "contem",
    "participou",
    "interpreta",
    "produziu",
    "compos",
    "realizou",
]

try:
    # ---------------------------------------------------------
    # 1. VOLUME DE DADOS ARMAZENADOS NO BANCO RELACIONAL
    # ---------------------------------------------------------
    st.subheader("Volume de Dados Armazenados")

    contagens = {}
    for tabela in TABELAS_ESQUEMA:
        try:
            df_cnt = run_query(f"SELECT COUNT(*) AS total FROM `{tabela}`")
            contagens[tabela] = int(df_cnt["total"].iloc[0])
        except Exception:
            contagens[tabela] = 0

    total_geral = sum(contagens.values())

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total de Registros (14 tabelas)", f"{total_geral:,}".replace(",", "."))
    c2.metric("Indicações", contagens.get("Indicação", 0))
    c3.metric("Pessoas / Artistas", contagens.get("Pessoa", 0))
    c4.metric("Álbuns", contagens.get("Album", 0))
    c5.metric("Faixas", contagens.get("Faixa", 0))

    with st.expander("Ver contagem detalhada por tabela"):
        df_vol = pd.DataFrame(
            [{"Tabela": k, "Registros Armazenados": v} for k, v in contagens.items()]
        ).sort_values("Registros Armazenados", ascending=False)
        st.dataframe(df_vol, use_container_width=True, hide_index=True)

    st.divider()

    # ---------------------------------------------------------
    # 2. FILTROS INTERATIVOS (EDIÇÃO / ANO E CATEGORIA)
    # ---------------------------------------------------------
    st.sidebar.header("Filtros de Consulta")

    df_cerimonias = run_query(
        """
        SELECT DISTINCT
            c.edicao,
            YEAR(c.dataRealizacao) AS ano,
            c.dataRealizacao
        FROM `Cerimonia` c
        ORDER BY c.edicao DESC
        """
    )

    opcoes_edicao = ["Todas as edições"]
    mapa_edicao = {}
    for _, row in df_cerimonias.iterrows():
        label = f"{int(row['edicao'])}ª Edição ({int(row['ano'])})"
        opcoes_edicao.append(label)
        mapa_edicao[label] = int(row["edicao"])

    edicao_escolhida = st.sidebar.selectbox("Edição / Ano da Cerimônia", opcoes_edicao)

    df_categorias = run_query(
        "SELECT DISTINCT nome FROM `Categoria` ORDER BY nome ASC"
    )
    categorias_lista = ["Todas as categorias"] + df_categorias["nome"].dropna().tolist()
    categoria_escolhida = st.sidebar.selectbox("Categoria", categorias_lista)

    apenas_vencedores = st.sidebar.checkbox("Considerar apenas vencedores", value=False)

    # Monta cláusula WHERE dinâmica com base nos filtros
    condicoes = ["1=1"]
    if edicao_escolhida != "Todas as edições":
        edicao_num = mapa_edicao[edicao_escolhida]
        condicoes.append(f"i.Cerimonia_edicao = {edicao_num}")

    if categoria_escolhida != "Todas as categorias":
        cat_escapada = categoria_escolhida.replace("'", "''")
        condicoes.append(f"cat.nome = '{cat_escapada}'")

    if apenas_vencedores:
        condicoes.append("i.venceu = 1")

    where_sql = " AND ".join(condicoes)

    # ---------------------------------------------------------
    # 3. INFERÊNCIAS E RANKINGS ANALÍTICOS
    # ---------------------------------------------------------
    aba_artistas, aba_obras, aba_tabelas = st.tabs(
        [
            "Artistas com Mais Vitórias e Indicações",
            "Álbuns, Faixas, Gravadoras e Gêneros",
            "Explorar Tabelas do Banco",
        ]
    )

    with aba_artistas:
        st.subheader("Ranking de Artistas / Pessoas")

        df_artistas = run_query(
            f"""
            SELECT
                COALESCE(NULLIF(p.nomeArtistico, ''), p.Nome) AS Artista,
                p.Nacionalidade,
                COUNT(i.idIndicacao) AS Total_Indicacoes,
                SUM(CASE WHEN i.venceu = 1 THEN 1 ELSE 0 END) AS Vitorias,
                ROUND(
                    100.0 * SUM(CASE WHEN i.venceu = 1 THEN 1 ELSE 0 END) / COUNT(i.idIndicacao),
                    1
                ) AS Taxa_Vitoria_Pct
            FROM `Indicação` i
            INNER JOIN `Pessoa` p ON i.Pessoa_idPessoa = p.idPessoa
            INNER JOIN `Categoria` cat ON i.Categoria_idCategoria = cat.idCategoria
            WHERE {where_sql}
            GROUP BY p.idPessoa, Artista, p.Nacionalidade
            ORDER BY Vitorias DESC, Total_Indicacoes DESC, Artista ASC
            """
        )

        if df_artistas.empty:
            st.info("Nenhum registro encontrado para os filtros selecionados.")
        else:
            destaque = df_artistas.iloc[0]
            col_d1, col_d2, col_d3 = st.columns(3)
            col_d1.metric("Artista em Destaque", destaque["Artista"])
            col_d2.metric("Vitórias no Recorte", int(destaque["Vitorias"]))
            col_d3.metric("Indicações no Recorte", int(destaque["Total_Indicacoes"]))

            st.markdown("**Top 10 por número de vitórias**")
            top10 = df_artistas.head(10).set_index("Artista")[["Vitorias", "Total_Indicacoes"]]
            st.bar_chart(top10)

            st.markdown("**Tabela completa do ranking**")
            st.dataframe(df_artistas, use_container_width=True, hide_index=True)

    with aba_obras:
        col_esq, col_dir = st.columns(2)

        with col_esq:
            st.subheader("Gravadoras mais premiadas")
            df_gravadoras = run_query(
                f"""
                SELECT
                    g.nome AS Gravadora,
                    g.origem AS Origem,
                    COUNT(DISTINCT a.idAlbum) AS Albuns_Indicados,
                    SUM(CASE WHEN i.venceu = 1 THEN 1 ELSE 0 END) AS Vitorias
                FROM `Indicação` i
                INNER JOIN `Album` a ON i.Album_idAlbum = a.idAlbum
                INNER JOIN `Gravadora` g ON a.Gravadora_idGravadora = g.idGravadora
                INNER JOIN `Categoria` cat ON i.Categoria_idCategoria = cat.idCategoria
                WHERE {where_sql}
                GROUP BY g.idGravadora, g.nome, g.origem
                ORDER BY Vitorias DESC, Albuns_Indicados DESC
                """
            )
            st.dataframe(df_gravadoras, use_container_width=True, hide_index=True)

        with col_dir:
            st.subheader("Gêneros com mais indicações")
            df_generos = run_query(
                f"""
                SELECT
                    gen.genero AS Genero,
                    COUNT(DISTINCT i.idIndicacao) AS Indicacoes,
                    SUM(CASE WHEN i.venceu = 1 THEN 1 ELSE 0 END) AS Vitorias
                FROM `Indicação` i
                INNER JOIN `Album` a ON i.Album_idAlbum = a.idAlbum
                INNER JOIN `Genero` gen ON a.idAlbum = gen.Album_idAlbum
                INNER JOIN `Categoria` cat ON i.Categoria_idCategoria = cat.idCategoria
                WHERE {where_sql}
                GROUP BY gen.genero
                ORDER BY Vitorias DESC, Indicacoes DESC
                """
            )
            st.dataframe(df_generos, use_container_width=True, hide_index=True)

        st.subheader("Detalhamento das Indicações (Álbuns e Faixas)")
        df_detalhe = run_query(
            f"""
            SELECT
                c.edicao AS Edicao,
                YEAR(c.dataRealizacao) AS Ano,
                cat.nome AS Categoria,
                COALESCE(NULLIF(p.nomeArtistico, ''), p.Nome) AS Artista,
                a.nome AS Album,
                f.nome AS Faixa,
                CASE WHEN i.venceu = 1 THEN 'Vencedor' ELSE 'Indicado' END AS Resultado
            FROM `Indicação` i
            INNER JOIN `Cerimonia` c ON i.Cerimonia_edicao = c.edicao
            INNER JOIN `Categoria` cat ON i.Categoria_idCategoria = cat.idCategoria
            INNER JOIN `Pessoa` p ON i.Pessoa_idPessoa = p.idPessoa
            LEFT JOIN `Album` a ON i.Album_idAlbum = a.idAlbum
            LEFT JOIN `Faixa` f ON i.Faixa_idFaixa = f.idFaixa
            WHERE {where_sql}
            ORDER BY c.edicao DESC, i.venceu DESC, cat.nome ASC
            """
        )
        st.dataframe(df_detalhe, use_container_width=True, hide_index=True)

    with aba_tabelas:
        st.subheader("Inspeção Direta das 14 Tabelas Relacionais")
        tabela_sel = st.selectbox("Escolha a tabela", TABELAS_ESQUEMA)
        df_tab = run_query(f"SELECT * FROM `{tabela_sel}`")
        st.write(f"Total de registros em **{tabela_sel}**: `{len(df_tab)}`")
        st.dataframe(df_tab, use_container_width=True, hide_index=True)

except Exception as exc:
    st.error("Erro ao consultar o banco de dados.")
    st.exception(exc)
