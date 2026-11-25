import pandas as pd
import plotly.express as px
import streamlit as st
from db import run_query

st.set_page_config(
    page_title="Grammy Data Pipeline — Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Paleta temática (Dourado Grammy + Tons Neutros)
COR_OURO = "#D4AF37"
COR_SECUNDARIA = "#4A5568"
COR_DESTAQUE = "#B8860B"

# CSS sutil para melhorar espaçamento e cartões de métricas
st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1.8rem;
            padding-bottom: 2rem;
        }
        div[data-testid="stMetric"] {
            background-color: rgba(212, 175, 55, 0.06);
            border: 1px solid rgba(212, 175, 55, 0.25);
            padding: 0.85rem 1rem;
            border-radius: 0.6rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
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


@st.cache_data(ttl=600)
def carregar_contagens_banco() -> dict:
    contagens = {}
    for tabela in TABELAS_ESQUEMA:
        try:
            df_cnt = run_query(f"SELECT COUNT(*) AS total FROM `{tabela}`")
            contagens[tabela] = int(df_cnt["total"].iloc[0])
        except Exception:
            contagens[tabela] = 0
    return contagens


@st.cache_data(ttl=600)
def carregar_filtros():
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
    df_categorias = run_query(
        "SELECT DISTINCT nome FROM `Categoria` ORDER BY nome ASC"
    )
    return df_cerimonias, df_categorias


def estilizar_grafico_barras(fig, titulo_x: str):
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis_title=titulo_x,
        yaxis_title=None,
        margin=dict(l=10, r=20, t=20, b=20),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            title=None,
        ),
        height=420,
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(128,128,128,0.15)")
    fig.update_yaxes(autorange="reversed")
    return fig


# ---------------------------------------------------------
# CABEÇALHO
# ---------------------------------------------------------
st.title("Grammy Awards — Painel Analítico")
st.caption(
    "Consulta relacional consolidada a partir da base histórica do GRAMMY Awards "
    "enriquecida via MusicBrainz, Open Opus e Wikidata em MySQL."
)

try:
    # ---------------------------------------------------------
    # 1. MÉTRICAS GERAIS DO BANCO RELACIONAL
    # ---------------------------------------------------------
    contagens = carregar_contagens_banco()
    total_geral = sum(contagens.values())

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Registros Totais (14 tabelas)", f"{total_geral:,}".replace(",", "."))
    c2.metric("Indicações", f"{contagens.get('Indicação', 0):,}".replace(",", "."))
    c3.metric("Pessoas / Artistas", f"{contagens.get('Pessoa', 0):,}".replace(",", "."))
    c4.metric("Álbuns", f"{contagens.get('Album', 0):,}".replace(",", "."))
    c5.metric("Faixas", f"{contagens.get('Faixa', 0):,}".replace(",", "."))

    with st.expander("Arquitetura Relacional — Ver volume detalhado por tabela"):
        df_vol = pd.DataFrame(
            [{"Tabela": k, "Registros Armazenados": v} for k, v in contagens.items()]
        ).sort_values("Registros Armazenados", ascending=False)

        col_v1, col_v2 = st.columns([1.2, 1])
        with col_v1:
            st.dataframe(
                df_vol,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Registros Armazenados": st.column_config.NumberColumn(
                        "Registros Armazenados", format="%d"
                    )
                },
            )
        with col_v2:
            fig_vol = px.bar(
                df_vol,
                x="Registros Armazenados",
                y="Tabela",
                orientation="h",
                color_discrete_sequence=[COR_OURO],
                text="Registros Armazenados",
            )
            fig_vol.update_traces(textposition="outside")
            fig_vol = estilizar_grafico_barras(fig_vol, "Quantidade de Registros")
            fig_vol.update_layout(height=360)
            st.plotly_chart(fig_vol, use_container_width=True)

    st.divider()

    # ---------------------------------------------------------
    # 2. FILTROS INTERATIVOS NA BARRA LATERAL
    # ---------------------------------------------------------
    st.sidebar.header("Filtros de Consulta")

    df_cerimonias, df_categorias = carregar_filtros()

    anos_disponiveis = sorted(df_cerimonias["ano"].dropna().astype(int).unique())
    if anos_disponiveis:
        ano_min, ano_max = min(anos_disponiveis), max(anos_disponiveis)
        intervalo_anos = st.sidebar.slider(
            "Intervalo de Anos",
            min_value=ano_min,
            max_value=ano_max,
            value=(ano_min, ano_max),
        )
    else:
        intervalo_anos = None

    opcoes_edicao = ["Todas as edições"]
    mapa_edicao = {}
    for _, row in df_cerimonias.iterrows():
        label = f"{int(row['edicao'])}ª Edição ({int(row['ano'])})"
        opcoes_edicao.append(label)
        mapa_edicao[label] = int(row["edicao"])

    edicao_escolhida = st.sidebar.selectbox("Edição Específica", opcoes_edicao)

    categorias_lista = ["Todas as categorias"] + df_categorias["nome"].dropna().tolist()
    categoria_escolhida = st.sidebar.selectbox("Categoria", categorias_lista)

    termo_busca = st.sidebar.text_input(
        "Buscar Artista, Álbum ou Faixa",
        placeholder="Ex: Beyoncé, Thriller, Taylor...",
    ).strip()

    apenas_vencedores = st.sidebar.toggle("Apenas vencedores", value=False)

    # Monta cláusula WHERE dinâmica
    condicoes = ["1=1"]

    if intervalo_anos is not None:
        condicoes.append(
            f"YEAR(c.dataRealizacao) BETWEEN {intervalo_anos[0]} AND {intervalo_anos[1]}"
        )

    if edicao_escolhida != "Todas as edições":
        edicao_num = mapa_edicao[edicao_escolhida]
        condicoes.append(f"i.Cerimonia_edicao = {edicao_num}")

    if categoria_escolhida != "Todas as categorias":
        cat_escapada = categoria_escolhida.replace("'", "''")
        condicoes.append(f"cat.nome = '{cat_escapada}'")

    if apenas_vencedores:
        condicoes.append("i.venceu = 1")

    where_base = " AND ".join(condicoes)

    # Filtro textual aplicado na consulta detalhada e de artistas
    filtro_texto_sql = ""
    if termo_busca:
        busca_esc = termo_busca.replace("'", "''")
        filtro_texto_sql = (
            f" AND (p.Nome LIKE '%{busca_esc}%' "
            f"OR p.nomeArtistico LIKE '%{busca_esc}%' "
            f"OR a.nome LIKE '%{busca_esc}%' "
            f"OR f.nome LIKE '%{busca_esc}%')"
        )

    # ---------------------------------------------------------
    # 3. ABAS ANALÍTICAS
    # ---------------------------------------------------------
    aba_artistas, aba_obras, aba_evolucao, aba_tabelas = st.tabs(
        [
            "Artistas e Pessoas",
            "Álbuns, Faixas, Gravadoras e Gêneros",
            "Evolução Histórica",
            "Explorar Tabelas",
        ]
    )

    # === ABA 1: ARTISTAS ===
    with aba_artistas:
        df_artistas = run_query(
            f"""
            SELECT
                COALESCE(NULLIF(p.nomeArtistico, ''), p.Nome) AS Artista,
                COALESCE(NULLIF(p.Nacionalidade, ''), 'Não informada') AS Nacionalidade,
                COUNT(i.idIndicacao) AS Total_Indicacoes,
                SUM(CASE WHEN i.venceu = 1 THEN 1 ELSE 0 END) AS Vitorias,
                ROUND(
                    100.0 * SUM(CASE WHEN i.venceu = 1 THEN 1 ELSE 0 END) / COUNT(i.idIndicacao),
                    1
                ) AS Taxa_Vitoria_Pct
            FROM `Indicação` i
            INNER JOIN `Cerimonia` c ON i.Cerimonia_edicao = c.edicao
            INNER JOIN `Pessoa` p ON i.Pessoa_idPessoa = p.idPessoa
            INNER JOIN `Categoria` cat ON i.Categoria_idCategoria = cat.idCategoria
            LEFT JOIN `Album` a ON i.Album_idAlbum = a.idAlbum
            LEFT JOIN `Faixa` f ON i.Faixa_idFaixa = f.idFaixa
            WHERE {where_base} {filtro_texto_sql}
            GROUP BY p.idPessoa, Artista, Nacionalidade
            ORDER BY Vitorias DESC, Total_Indicacoes DESC, Artista ASC
            """
        )

        if df_artistas.empty:
            st.info("Nenhum registro encontrado para os filtros selecionados.")
        else:
            destaque = df_artistas.iloc[0]
            col_d1, col_d2, col_d3, col_d4 = st.columns(4)
            col_d1.metric("Líder no Recorte", destaque["Artista"])
            col_d2.metric("Vitórias", int(destaque["Vitorias"]))
            col_d3.metric("Indicações", int(destaque["Total_Indicacoes"]))
            col_d4.metric("Aproveitamento", f"{destaque['Taxa_Vitoria_Pct']:.1f}%")

            col_g1, col_g2 = st.columns([1.4, 1])

            with col_g1:
                st.subheader("Top 10 Artistas — Vitórias vs. Indicações")
                top10 = df_artistas.head(10).copy()
                df_plot = top10.melt(
                    id_vars="Artista",
                    value_vars=["Vitorias", "Total_Indicacoes"],
                    var_name="Métrica",
                    value_name="Quantidade",
                )
                df_plot["Métrica"] = df_plot["Métrica"].replace(
                    {"Vitorias": "Vitórias", "Total_Indicacoes": "Total de Indicações"}
                )

                fig_art = px.bar(
                    df_plot,
                    x="Quantidade",
                    y="Artista",
                    color="Métrica",
                    barmode="group",
                    orientation="h",
                    color_discrete_map={
                        "Vitórias": COR_OURO,
                        "Total de Indicações": COR_SECUNDARIA,
                    },
                    text="Quantidade",
                )
                fig_art.update_traces(textposition="outside")
                fig_art = estilizar_grafico_barras(fig_art, "Quantidade")
                st.plotly_chart(fig_art, use_container_width=True)

            with col_g2:
                st.subheader("Distribuição por Nacionalidade (Top 10)")
                df_nac = (
                    df_artistas[df_artistas["Nacionalidade"] != "Não informada"]
                    .groupby("Nacionalidade", as_index=False)["Vitorias"]
                    .sum()
                    .sort_values("Vitorias", ascending=False)
                    .head(10)
                )
                if not df_nac.empty:
                    fig_nac = px.bar(
                        df_nac,
                        x="Vitorias",
                        y="Nacionalidade",
                        orientation="h",
                        color_discrete_sequence=[COR_DESTAQUE],
                        text="Vitorias",
                    )
                    fig_nac.update_traces(textposition="outside")
                    fig_nac = estilizar_grafico_barras(fig_nac, "Total de Vitórias")
                    st.plotly_chart(fig_nac, use_container_width=True)
                else:
                    st.caption("Sem dados de nacionalidade preenchidos para este recorte.")

            st.subheader("Ranking Completo")
            st.dataframe(
                df_artistas,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Artista": st.column_config.TextColumn("Artista / Pessoa"),
                    "Nacionalidade": st.column_config.TextColumn("Nacionalidade"),
                    "Total_Indicacoes": st.column_config.NumberColumn("Indicações", format="%d"),
                    "Vitorias": st.column_config.NumberColumn("Vitórias", format="%d"),
                    "Taxa_Vitoria_Pct": st.column_config.ProgressColumn(
                        "Aproveitamento (%)",
                        format="%.1f%%",
                        min_value=0,
                        max_value=100,
                    ),
                },
            )

    # === ABA 2: OBRAS, GRAVADORAS E GÊNEROS ===
    with aba_obras:
        col_esq, col_dir = st.columns(2)

        with col_esq:
            st.subheader("Top 10 Gravadoras Mais Premiadas")
            df_gravadoras = run_query(
                f"""
                SELECT
                    g.nome AS Gravadora,
                    COALESCE(NULLIF(g.origem, ''), '—') AS Origem,
                    COUNT(DISTINCT a.idAlbum) AS Albuns_Indicados,
                    SUM(CASE WHEN i.venceu = 1 THEN 1 ELSE 0 END) AS Vitorias
                FROM `Indicação` i
                INNER JOIN `Cerimonia` c ON i.Cerimonia_edicao = c.edicao
                INNER JOIN `Album` a ON i.Album_idAlbum = a.idAlbum
                INNER JOIN `Gravadora` g ON a.Gravadora_idGravadora = g.idGravadora
                INNER JOIN `Categoria` cat ON i.Categoria_idCategoria = cat.idCategoria
                WHERE {where_base}
                GROUP BY g.idGravadora, g.nome, Origem
                ORDER BY Vitorias DESC, Albuns_Indicados DESC
                """
            )
            if not df_gravadoras.empty:
                fig_grav = px.bar(
                    df_gravadoras.head(10),
                    x="Vitorias",
                    y="Gravadora",
                    orientation="h",
                    color_discrete_sequence=[COR_OURO],
                    text="Vitorias",
                )
                fig_grav.update_traces(textposition="outside")
                fig_grav = estilizar_grafico_barras(fig_grav, "Vitórias")
                fig_grav.update_layout(height=350)
                st.plotly_chart(fig_grav, use_container_width=True)

            st.dataframe(
                df_gravadoras,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Albuns_Indicados": st.column_config.NumberColumn("Álbuns Indicados"),
                    "Vitorias": st.column_config.NumberColumn("Vitórias"),
                },
            )

        with col_dir:
            st.subheader("Top 10 Gêneros Musicais")
            df_generos = run_query(
                f"""
                SELECT
                    gen.genero AS Genero,
                    COUNT(DISTINCT i.idIndicacao) AS Indicacoes,
                    SUM(CASE WHEN i.venceu = 1 THEN 1 ELSE 0 END) AS Vitorias
                FROM `Indicação` i
                INNER JOIN `Cerimonia` c ON i.Cerimonia_edicao = c.edicao
                INNER JOIN `Album` a ON i.Album_idAlbum = a.idAlbum
                INNER JOIN `Genero` gen ON a.idAlbum = gen.Album_idAlbum
                INNER JOIN `Categoria` cat ON i.Categoria_idCategoria = cat.idCategoria
                WHERE {where_base}
                GROUP BY gen.genero
                ORDER BY Vitorias DESC, Indicacoes DESC
                """
            )
            if not df_generos.empty:
                fig_gen = px.bar(
                    df_generos.head(10),
                    x="Indicacoes",
                    y="Genero",
                    orientation="h",
                    color_discrete_sequence=[COR_SECUNDARIA],
                    text="Indicacoes",
                )
                fig_gen.update_traces(textposition="outside")
                fig_gen = estilizar_grafico_barras(fig_gen, "Indicações")
                fig_gen.update_layout(height=350)
                st.plotly_chart(fig_gen, use_container_width=True)

            st.dataframe(
                df_generos,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Genero": st.column_config.TextColumn("Gênero"),
                    "Indicacoes": st.column_config.NumberColumn("Indicações"),
                    "Vitorias": st.column_config.NumberColumn("Vitórias"),
                },
            )

        st.divider()
        st.subheader("Detalhamento das Indicações (Álbuns e Faixas)")
        df_detalhe = run_query(
            f"""
            SELECT
                c.edicao AS Edicao,
                YEAR(c.dataRealizacao) AS Ano,
                cat.nome AS Categoria,
                COALESCE(NULLIF(p.nomeArtistico, ''), p.Nome) AS Artista,
                COALESCE(a.nome, '—') AS Album,
                COALESCE(f.nome, '—') AS Faixa,
                CASE WHEN i.venceu = 1 THEN 'Vencedor' ELSE 'Indicado' END AS Resultado
            FROM `Indicação` i
            INNER JOIN `Cerimonia` c ON i.Cerimonia_edicao = c.edicao
            INNER JOIN `Categoria` cat ON i.Categoria_idCategoria = cat.idCategoria
            INNER JOIN `Pessoa` p ON i.Pessoa_idPessoa = p.idPessoa
            LEFT JOIN `Album` a ON i.Album_idAlbum = a.idAlbum
            LEFT JOIN `Faixa` f ON i.Faixa_idFaixa = f.idFaixa
            WHERE {where_base} {filtro_texto_sql}
            ORDER BY c.edicao DESC, i.venceu DESC, cat.nome ASC
            """
        )
        st.caption(f"Exibindo {len(df_detalhe)} registros encontrados.")
        st.dataframe(
            df_detalhe,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Edicao": st.column_config.NumberColumn("Edição", format="%dª"),
                "Ano": st.column_config.NumberColumn("Ano", format="%d"),
                "Album": st.column_config.TextColumn("Álbum"),
            },
        )

    # === ABA 3: EVOLUÇÃO HISTÓRICA ===
    with aba_evolucao:
        st.subheader("Evolução de Indicações e Categorias por Ano")
        df_hist = run_query(
            f"""
            SELECT
                YEAR(c.dataRealizacao) AS Ano,
                c.edicao AS Edicao,
                COUNT(DISTINCT i.idIndicacao) AS Total_Indicacoes,
                COUNT(DISTINCT cat.idCategoria) AS Categorias_Ativas,
                SUM(CASE WHEN i.venceu = 1 THEN 1 ELSE 0 END) AS Total_Vencedores
            FROM `Indicação` i
            INNER JOIN `Cerimonia` c ON i.Cerimonia_edicao = c.edicao
            INNER JOIN `Categoria` cat ON i.Categoria_idCategoria = cat.idCategoria
            WHERE {where_base}
            GROUP BY YEAR(c.dataRealizacao), c.edicao
            ORDER BY Ano ASC
            """
        )

        if df_hist.empty:
            st.info("Sem dados históricos para exibir com os filtros selecionados.")
        else:
            fig_hist = px.area(
                df_hist,
                x="Ano",
                y="Total_Indicacoes",
                markers=True,
                color_discrete_sequence=[COR_OURO],
                labels={"Total_Indicacoes": "Total de Indicações", "Ano": "Ano"},
            )
            fig_hist.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                height=380,
                margin=dict(l=10, r=20, t=20, b=20),
            )
            fig_hist.update_yaxes(showgrid=True, gridcolor="rgba(128,128,128,0.15)")
            st.plotly_chart(fig_hist, use_container_width=True)

            st.dataframe(
                df_hist.sort_values("Ano", ascending=False),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Ano": st.column_config.NumberColumn("Ano", format="%d"),
                    "Edicao": st.column_config.NumberColumn("Edição", format="%dª"),
                    "Total_Indicacoes": st.column_config.NumberColumn("Indicações"),
                    "Categorias_Ativas": st.column_config.NumberColumn("Categorias"),
                    "Total_Vencedores": st.column_config.NumberColumn("Vencedores"),
                },
            )

    # === ABA 4: EXPLORAR TABELAS ===
    with aba_tabelas:
        st.subheader("Inspeção Direta das 14 Tabelas Relacionais")
        col_t1, col_t2 = st.columns([1, 2])
        with col_t1:
            tabela_sel = st.selectbox("Escolha a tabela", TABELAS_ESQUEMA)
        df_tab = run_query(f"SELECT * FROM `{tabela_sel}`")
        with col_t2:
            st.metric(f"Registros em {tabela_sel}", len(df_tab))
        st.dataframe(df_tab, use_container_width=True, hide_index=True)

except Exception as exc:
    st.error("Erro ao consultar o banco de dados.")
    st.exception(exc)
