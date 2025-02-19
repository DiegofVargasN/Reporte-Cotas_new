import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
import oracledb

st.title('Reporte Facturación NHDCOTAS')

# Configuración de conexión a Oracle
def connect_to_oracle():
    connection = oracledb.connect(
        user=st.secrets["oracle"]["user"],
        password=st.secrets["oracle"]["password"],
        dsn=st.secrets["oracle"]["dsn"]
    )
    return connection

@st.cache_data
def load_data(start_period, end_period):
    try:
        # Consulta SQL con fechas directamente
        query = f"""
            SELECT NHDCOTAS.SERCTO, 
                   CRM.SERVICIO.NOMSER, 
                   NHDCOTAS.PERIODO, 
                   NHDCOTAS.MTOTOTFAC, 
                   NHDCOTAS.ESTADO
            FROM NHDCOTAS
            JOIN CRM.SERVICIO 
              ON NHDCOTAS.CODSERV = CRM.SERVICIO.CODSER
            WHERE NHDCOTAS.PERIODO BETWEEN '{start_period}' AND '{end_period}'
        """
        
        # Ejecutar la consulta con los valores de fechas insertados
        conn = connect_to_oracle()
        df = pd.read_sql(query, conn)
        conn.close()

        # Procesar los datos
        df['PERIODO'] = pd.to_datetime(df['PERIODO'], format='%Y-%m', errors='coerce')
        df = df.dropna(subset=['PERIODO'])
        df['PERIODO_FMT'] = df['PERIODO'].dt.strftime('%Y-%m')

        return df
    except Exception as e:
        st.error(f"Error al cargar los datos: {str(e)}")
        return None

# Interfaz para ingresar el inicio y el fin del periodo
st.sidebar.header("Seleccione el rango de fechas")
start_period = st.sidebar.selectbox("Inicio del Periodo (YYYY-MM):", ["2024-01", "2024-02", "2024-03", "2024-04", "2024-05", "2024-06", "2024-07", "2024-08", "2024-09", "2024-10", "2024-11", "2024-12"])
end_period = st.sidebar.selectbox("Fin del Periodo (YYYY-MM):", ["2024-01", "2024-02", "2024-03", "2024-04", "2024-05", "2024-06", "2024-07", "2024-08", "2024-09", "2024-10", "2024-11", "2024-12"])

# Inicializamos las variables de filtros
if 'df' not in st.session_state:
    st.session_state.df = None

# Cargar los datos solo si es necesario
if st.sidebar.button("Ejecutar Análisis"):
    with st.spinner("Conectando y obteniendo datos desde Oracle..."):
        st.session_state.df = load_data(start_period, end_period)

# Si los datos ya están cargados, continuamos con los filtros
if st.session_state.df is not None:
    df = st.session_state.df
    codserv_options = ["Todos"] + sorted(df['NOMSER'].unique())
    selected_codserv = st.selectbox('Selecciona NOMSER:', codserv_options)
    estado_options = sorted(df['ESTADO'].unique())
    selected_estados = st.multiselect('Selecciona uno o más ESTADO:', estado_options, default=estado_options)

    # Filtrar los datos
    start_date, end_date = pd.to_datetime(start_period), pd.to_datetime(end_period)
    if selected_codserv == "Todos":
        mask = (df['ESTADO'].isin(selected_estados)) & (df['PERIODO'].between(start_date, end_date))
    else:
        mask = (df['NOMSER'] == selected_codserv) & (df['ESTADO'].isin(selected_estados)) & (df['PERIODO'].between(start_date, end_date))
    
    filtered_df = df.loc[mask]
    
    if not filtered_df.empty:
        trend_data = filtered_df.groupby('PERIODO_FMT').agg({'MTOTOTFAC': 'sum', 'SERCTO': 'count'}).reset_index().sort_values('PERIODO_FMT')

        st.subheader("Tabla de Tendencia")
        st.dataframe(trend_data)

        # Opción de visualización
        chart_type = st.radio("Selecciona el tipo de gráfico:", ["Línea", "Barras"], horizontal=True)

        if chart_type == "Línea":
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Scatter(x=trend_data['PERIODO_FMT'], y=trend_data['MTOTOTFAC'], mode='lines+markers', name='MTOTOTFAC', line=dict(color='royalblue', width=2)), secondary_y=False)
            fig.add_trace(go.Scatter(x=trend_data['PERIODO_FMT'], y=trend_data['SERCTO'], mode='lines+markers', name='Cuenta SERCTO', line=dict(color='firebrick', width=2, dash='dash')), secondary_y=True)
            fig.update_layout(title_text="Tendencia de Facturación y Cuenta SERCTO", xaxis_title="Periodo", template="plotly_white", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            fig.update_xaxes(tickangle=45)
            fig.update_yaxes(title_text="MTOTOTFAC", secondary_y=False)
            fig.update_yaxes(title_text="Cuenta SERCTO", secondary_y=True)
        else:
            fig = make_subplots(rows=2, cols=1, subplot_titles=("MTOTOTFAC", "Cuenta SERCTO"))
            fig.add_trace(go.Bar(x=trend_data['PERIODO_FMT'], y=trend_data['MTOTOTFAC'], name="MTOTOTFAC", marker_color='royalblue'), row=1, col=1)
            fig.add_trace(go.Bar(x=trend_data['PERIODO_FMT'], y=trend_data['SERCTO'], name="Cuenta SERCTO", marker_color='firebrick'), row=2, col=1)
            fig.update_layout(title_text="Comparación MTOTOTFAC y Cuenta SERCTO", xaxis_title="Periodo", template="plotly_white")

        st.plotly_chart(fig, use_container_width=True)

    else:
        st.warning("No hay datos que coincidan con los filtros.")

    # Gráfico Top 10: se aplica el filtro de ESTADO y PERIODO (sin el filtro de NOMSER)
    top_mask = (
        (df['ESTADO'].isin(selected_estados)) & 
        (df['PERIODO'] >= start_date) & 
        (df['PERIODO'] <= end_date)
    )
    top_df = (
        df.loc[top_mask]
        .groupby('NOMSER', as_index=False)['MTOTOTFAC']
        .sum()
    )
    top_df = top_df.sort_values('MTOTOTFAC', ascending=False).head(10)
    
    st.subheader("Top 10 NOMSER con Mayor Facturación")
    st.dataframe(top_df)
    
    # Gráfico de barras con valores exactos en el eje x
    fig_top10 = px.bar(
        top_df,
        x='NOMSER',
        y='MTOTOTFAC',
        labels={'NOMSER': 'Código de Servicio', 'MTOTOTFAC': 'Monto Total Facturado'},
        title='Top 10 NOMSER con Mayor Facturación',
        template='plotly_white',
        color='MTOTOTFAC', color_continuous_scale='blues'
    )
    fig_top10.update_xaxes(type='category')
    st.plotly_chart(fig_top10, use_container_width=True)


