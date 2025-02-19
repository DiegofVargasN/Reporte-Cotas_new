import streamlit as st
import pandas as pd
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import streamlit_authenticator as stauth

# Obtener las credenciales del archivo secrets.toml
usernames = st.secrets["auth"]["usernames"]
passwords = st.secrets["auth"]["passwords"]
names = st.secrets["auth"]["names"]

# Aplicar el hash a cada contraseña
hashed_passwords = stauth.Hasher(passwords).generate()

# Crear un diccionario de credenciales
credentials = {
    "usernames": {usernames[i]: {"password": hashed_passwords[i], "name": names[i]} for i in range(len(usernames))}
}

# Crear el autenticador con el diccionario de credenciales
authenticator = stauth.Authenticate(
    credentials=credentials,
    cookie_name="cookie_name",
    key="your_key",  # Reemplaza con tu clave secreta
    cookie_expiry_days=30
)

# Autenticación
name, authentication_status = authenticator.login("Iniciar sesión", "main")

if authentication_status:
    st.write(f"Bienvenido {name}")
    
    st.title('Reporte Facturación NHDCOTAS')

    @st.cache_data
    def load_data(uploaded_file):
        try:
            df = pd.read_excel(
                uploaded_file, 
                usecols=['PERIODO', 'CODSERV', 'MTOTOTFAC', 'ESTADO', 'SERCTO']
            )
            # Convertir CODSERV a string para tratarlo como categoría
            df['CODSERV'] = df['CODSERV'].astype(str)
            
            # Convertir PERIODO a datetime y eliminar filas inválidas
            df['PERIODO'] = pd.to_datetime(df['PERIODO'], format='%Y-%m', errors='coerce')
            df = df.dropna(subset=['PERIODO'])
            df['PERIODO_FMT'] = df['PERIODO'].dt.strftime('%Y-%m')
            return df
        except Exception as e:
            st.error(f"Error al cargar el archivo: {str(e)}")
            return None

    # Carga de archivo con key único
    uploaded_file = st.file_uploader("Sube tu archivo Excel", type=['xlsx'], key='file_uploader_1')

    if uploaded_file:
        df = load_data(uploaded_file)
        
        if df is not None:
            # Agregar opción "Todos" para CODSERV
            codserv_options = sorted(df['CODSERV'].unique())
            codserv_options = ["Todos"] + codserv_options
            selected_codserv = st.selectbox('Selecciona CODSERV:', codserv_options)
            
            # Selector múltiple para ESTADO
            estado_options = sorted(df['ESTADO'].unique())
            selected_estados = st.multiselect('Selecciona uno o más ESTADO:', estado_options, default=estado_options)
            
            # Selector de rango de PERIODO
            periodos = sorted(df['PERIODO_FMT'].unique())
            start_period, end_period = st.select_slider(
                'Selecciona rango de periodos:', 
                options=periodos, 
                value=(periodos[0], periodos[-1])
            )
            start_date = pd.to_datetime(start_period, format='%Y-%m')
            end_date = pd.to_datetime(end_period, format='%Y-%m')
            
            # Filtrar datos para el gráfico de tendencia:
            # Si se selecciona "Todos" se ignora el filtro de CODSERV.
            if selected_codserv == "Todos":
                mask = (
                    (df['ESTADO'].isin(selected_estados)) & 
                    (df['PERIODO'] >= start_date) & 
                    (df['PERIODO'] <= end_date)
                )
            else:
                mask = (
                    (df['CODSERV'] == selected_codserv) & 
                    (df['ESTADO'].isin(selected_estados)) & 
                    (df['PERIODO'] >= start_date) & 
                    (df['PERIODO'] <= end_date)
                )
            filtered_df = df.loc[mask]
            
            if not filtered_df.empty:
                trend_data = (
                    filtered_df.groupby('PERIODO_FMT')
                    .agg({'MTOTOTFAC': 'sum', 'SERCTO': 'count'})
                    .reset_index()
                    .sort_values('PERIODO_FMT')
                )
                
                st.subheader("Tabla de Tendencia")
                st.dataframe(trend_data)
                
                # Gráfico de tendencia con doble eje usando Plotly
                fig_trend = make_subplots(specs=[[{"secondary_y": True}]])
                fig_trend.add_trace(
                    go.Scatter(
                        x=trend_data['PERIODO_FMT'], 
                        y=trend_data['MTOTOTFAC'],
                        mode='lines+markers',
                        name='MTOTOTFAC',
                        line=dict(color='royalblue', width=2)
                    ),
                    secondary_y=False
                )
                fig_trend.add_trace(
                    go.Scatter(
                        x=trend_data['PERIODO_FMT'], 
                        y=trend_data['SERCTO'],
                        mode='lines+markers',
                        name='Cuenta SERCTO',
                        line=dict(color='firebrick', width=2, dash='dash')
                    ),
                    secondary_y=True
                )
                fig_trend.update_layout(
                    title_text="Tendencia de Facturación y Cuenta SERCTO",
                    xaxis_title="Periodo",
                    template="plotly_white",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                fig_trend.update_xaxes(tickangle=45)
                fig_trend.update_yaxes(title_text="MTOTOTFAC", secondary_y=False)
                fig_trend.update_yaxes(title_text="Cuenta SERCTO", secondary_y=True)
                st.plotly_chart(fig_trend, use_container_width=True)
            else:
                st.warning("No hay datos que coincidan con los filtros para la tendencia.")
            
            # ---------------------------
            # Gráfico Top 10: se aplica el filtro de ESTADO y PERIODO (sin el filtro de CODSERV)
            top_mask = (
                (df['ESTADO'].isin(selected_estados)) & 
                (df['PERIODO'] >= start_date) & 
                (df['PERIODO'] <= end_date)
            )
            top_df = (
                df.loc[top_mask]
                .groupby('CODSERV', as_index=False)['MTOTOTFAC']
                .sum()
            )
            top_df = top_df.sort_values('MTOTOTFAC', ascending=False).head(10)
            
            st.subheader("Top 10 CODSERV con Mayor Facturación")
            st.dataframe(top_df)
            
            # Gráfico de barras con valores exactos en el eje x
            fig_top10 = px.bar(
                top_df,
                x='CODSERV',
                y='MTOTOTFAC',
                labels={'CODSERV': 'Código de Servicio', 'MTOTOTFAC': 'Monto Total Facturado'},
                title='Top 10 CODSERV con Mayor Facturación',
                template='plotly_white',
                color='MTOTOTFAC', color_continuous_scale='blues'
            )
            fig_top10.update_xaxes(type='category')
            st.plotly_chart(fig_top10, use_container_width=True)
    else:
        st.info("Por favor sube un archivo Excel para comenzar.")
else:
    st.warning("Por favor, inicia sesión para acceder al reporte.")


