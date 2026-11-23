import streamlit as st
from db import run_query

st.title("🏆 Grammy Data Pipeline")

try:
    # Testa a conexão listando as tabelas do banco
    tabelas = run_query("SHOW TABLES")
    st.success("Conectado ao MySQL com sucesso!")
    st.dataframe(tabelas)

except Exception as e:
    st.error("Não foi possível conectar ao banco de dados.")
    st.code(str(e))