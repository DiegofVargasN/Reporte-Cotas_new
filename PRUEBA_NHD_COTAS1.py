import streamlit as st
import pandas as pd
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.graph_objects as go

# Función de autenticación
def authenticate(username, password):
    users = st.secrets["users"]
    if username in users and users[username] == password:
        return True
    return False

# UI de Login
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("Inicio de Sesión Cotas NHDCOTAS")
    username = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")
    if st.button("Ingresar"):
        if authenticate(username, password):
            st.session_state.authenticated = True
            st.session_state.username = username
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos")
    st.stop()

# Botón de cierre de sesión
if st.button("Cerrar Sesión"):
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.rerun()

# Título de la app
st.title(f'Reporte Facturación NHDCOTAS - Usuario: {st.session_state.username}')

@st.cache_data
def load_data(uploaded_file):
    try:
        df = pd.read_excel(
            uploaded_file, 
            usecols=['PERIODO', 'CODSERV', 'MTOTOTFAC', 'ESTADO', 'SERCTO']
        )
        df['CODSERV'] = df['CODSERV'].astype(str)
        df['PERIODO'] = pd.to_datetime(df['PERIODO'], format='%Y-%m', errors='coerce')
        df = df.dropna(subset=['PERIODO'])
        df['PERIODO_FMT'] = df['PERIODO'].dt.strftime('%Y-%m')
        return df
    except Exception as e:
        st.error(f"Error al cargar el archivo: {str(e)}")
        return None

uploaded_file = st.file_uploader("Sube tu archivo Excel", type=['xlsx'], key='file_uploader_1')

if uploaded_file:
    df = load_data(uploaded_file)
    
    if df is not None:
        codserv_options = ["Todos"] + sorted(df['CODSERV'].unique())
        selected_codserv = st.selectbox('Selecciona CODSERV:', codserv_options)
        
        estado_options = sorted(df['ESTADO'].unique())
        selected_estados = st.multiselect('Selecciona uno o más ESTADO:', estado_options, default=estado_options)
        
        periodos = sorted(df['PERIODO_FMT'].unique())
        start_period, end_period = st.select_slider(
            'Selecciona rango de periodos:', 
            options=periodos, 
            value=(periodos[0], periodos[-1])
        )
        start_date = pd.to_datetime(start_period, format='%Y-%m')
        end_date = pd.to_datetime(end_period, format='%Y-%m')
        
        mask = (df['ESTADO'].isin(selected_estados)) & (df['PERIODO'] >= start_date) & (df['PERIODO'] <= end_date)
        if selected_codserv != "Todos":
            mask &= df['CODSERV'] == selected_codserv
        filtered_df = df.loc[mask]
        
        if not filtered_df.empty:
            trend_data = filtered_df.groupby('PERIODO_FMT').agg({'MTOTOTFAC': 'sum', 'SERCTO': 'count'}).reset_index()
            
            st.subheader("Tabla de Tendencia")
            st.dataframe(trend_data)
            
            fig_trend = make_subplots(specs=[[{"secondary_y": True}]])
            fig_trend.add_trace(
                go.Scatter(x=trend_data['PERIODO_FMT'], y=trend_data['MTOTOTFAC'], mode='lines+markers', name='MTOTOTFAC', line=dict(color='royalblue', width=2)), secondary_y=False
            )
            fig_trend.add_trace(
                go.Scatter(x=trend_data['PERIODO_FMT'], y=trend_data['SERCTO'], mode='lines+markers', name='Cuenta SERCTO', line=dict(color='firebrick', width=2, dash='dash')), secondary_y=True
            )
            fig_trend.update_layout(title_text="Tendencia de Facturación y Cuenta SERCTO", xaxis_title="Periodo", template="plotly_white", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            fig_trend.update_xaxes(tickangle=45)
            fig_trend.update_yaxes(title_text="MTOTOTFAC", secondary_y=False)
            fig_trend.update_yaxes(title_text="Cuenta SERCTO", secondary_y=True)
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.warning("No hay datos que coincidan con los filtros para la tendencia.")
        
        top_mask = (df['ESTADO'].isin(selected_estados)) & (df['PERIODO'] >= start_date) & (df['PERIODO'] <= end_date)
        top_df = df.loc[top_mask].groupby('CODSERV', as_index=False)['MTOTOTFAC'].sum().sort_values('MTOTOTFAC', ascending=False).head(10)
        
        st.subheader("Top 10 CODSERV con Mayor Facturación")
        st.dataframe(top_df)
        
        fig_top10 = px.bar(
            top_df, x='CODSERV', y='MTOTOTFAC', labels={'CODSERV': 'Código de Servicio', 'MTOTOTFAC': 'Monto Total Facturado'},
            title='Top 10 CODSERV con Mayor Facturación', template='plotly_white', color='MTOTOTFAC', color_continuous_scale='blues'
        )
        fig_top10.update_xaxes(type='category')
        st.plotly_chart(fig_top10, use_container_width=True)
else:
    st.info("Por favor sube un archivo Excel para comenzar.")

