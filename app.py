import streamlit as st
import pandas as pd
from datetime import date

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Auditor ONCE T4", page_icon="🍀")

# --- 2. EL CEREBRO (Lógica) ---
def calcular_liquidacion(ventas, premios, tarjeta, efectivo_real):
    teorico = ventas - (premios + tarjeta)
    diferencia = efectivo_real - teorico
    return teorico, diferencia

# --- 3. LA PANTALLA (Lo que ves) ---
st.title("🍀 GESTOR TIPO 4 - VENDEDOR ONCE")
st.markdown("---")

# M E N Ú   L A T E R A L
menu = st.sidebar.radio("¿Qué vamos a hacer?", ["💰 Liquidación Diaria", "📦 Simular Stock"])

if menu == "💰 Liquidación Diaria":
    st.header("🧮 Calculadora de Cierre")
    st.info("Introduce los datos de tu TPV y cuenta tu dinero.")

    col1, col2 = st.columns(2)
    with col1:
        ventas = st.number_input("Total Ventas TPV (€)", min_value=0.0, step=0.5)
        efectivo_bolsillo = st.number_input("💵 DINERO EN TU BOLSILLO (€)", min_value=0.0, step=0.5)
    with col2:
        premios = st.number_input("Premios Pagados (€)", min_value=0.0, step=0.5)
        tarjeta = st.number_input("Cobros con Tarjeta (€)", min_value=0.0, step=0.5)

    if st.button("AUDITAR CAJA"):
        teorico, diferencia = calcular_liquidacion(ventas, premios, tarjeta, efectivo_bolsillo)
        
        st.write("---")
        st.subheader(f"Debes ingresar en el Banco: {teorico:.2f} €")
        
        if diferencia == 0:
            st.success("✅ ¡PERFECTO! La caja cuadra exacta.")
        elif diferencia > 0:
            st.success(f"🤑 Te sobra: {diferencia:.2f} € (A la hucha)")
        else:
            st.error(f"🚨 TE FALTA: {diferencia:.2f} € (Revisa tickets)")

elif menu == "📦 Simular Stock":
    st.header("📦 Almacén de Rascas")
    st.warning("Módulo de prueba visual")
    
    # Creamos una tabla falsa para que veas cómo queda
    datos = {
        "Juego": ["Mega Millonario", "7 y Media", "Sueldo Vida"],
        "Estado": ["ACTIVADO", "EN BOLSO", "VENDIDO"],
        "Valor Libro (€)": [150, 50, 60]
    }
    st.table(pd.DataFrame(datos))
    st.button("Escanear Nuevo Libro (Simulado)")
