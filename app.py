import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
from fpdf import FPDF
import io

# --- 1. CONFIGURACIÓN E INICIALIZACIÓN ---
st.set_page_config(page_title="GESTOR PRO ONCE", page_icon="🟢", layout="wide")

# Conexión a Base de Datos (Se crea un archivo .db local)
CONN = sqlite3.connect('gestor_once_pro.db', check_same_thread=False)
C = CONN.cursor()

def init_db():
    # Tabla Perfil
    C.execute('''CREATE TABLE IF NOT EXISTS perfil 
                 (id INTEGER PRIMARY KEY, nombre TEXT, id_vendedor TEXT, tipo TEXT)''')
    # Tabla Stock General (Cupón Papel)
    C.execute('''CREATE TABLE IF NOT EXISTS stock_papel 
                 (fecha DATE, producto TEXT, cantidad INTEGER, estado TEXT)''')
    # Tabla Rascas (Lógica compleja)
    C.execute('''CREATE TABLE IF NOT EXISTS rascas 
                 (uuid INTEGER PRIMARY KEY AUTOINCREMENT, juego TEXT, codigo TEXT, 
                  precio_libro REAL, estado TEXT, fecha_cambio DATE)''')
    # Tabla Cierres TPV
    C.execute('''CREATE TABLE IF NOT EXISTS cierres 
                 (fecha DATE, ventas_tpv REAL, premios REAL, tarjeta REAL, 
                  rascas_vendidos REAL, papel_vendido REAL, saldo_bolsillo REAL)''')
    # Tabla Extras
    C.execute('''CREATE TABLE IF NOT EXISTS extras 
                 (nombre TEXT, fecha_sorteo DATE, cantidad INTEGER, precio REAL, estado TEXT)''')
    # Tabla Agenda
    C.execute('''CREATE TABLE IF NOT EXISTS agenda 
                 (fecha DATE, nota TEXT, tipo TEXT)''')
    CONN.commit()

init_db()

# --- 2. FUNCIONES AUXILIARES (Lógica de Negocio) ---

def obtener_asignacion_tipo4():
    dia_semana = datetime.now().weekday() # 0=Lunes, 6=Domingo
    # Regla Tipo 4:
    if dia_semana in [0, 1]: return 40 # Lunes/Martes (Devolución)
    if dia_semana in [2, 3]: return 60 # Miércoles/Jueves
    if dia_semana == 4: return 80      # Viernes (Cuponazo)
    if dia_semana in [5, 6]: return 60 # Sábado/Domingo
    return 0

def generar_pdf_informe(df_cierres):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="INFORME DE GESTIÓN - ONCE TIPO 4", ln=1, align="C")
    pdf.ln(10)
    
    # Cabecera
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(30, 10, "Fecha", 1)
    pdf.cell(30, 10, "Ventas TPV", 1)
    pdf.cell(30, 10, "Premios", 1)
    pdf.cell(30, 10, "Bolsillo", 1)
    pdf.ln()
    
    # Datos
    pdf.set_font("Arial", size=10)
    for index, row in df_cierres.iterrows():
        pdf.cell(30, 10, str(row['fecha']), 1)
        pdf.cell(30, 10, f"{row['ventas_tpv']}E", 1)
        pdf.cell(30, 10, f"{row['premios']}E", 1)
        pdf.cell(30, 10, f"{row['saldo_bolsillo']}E", 1)
        pdf.ln()
        
    return pdf.output(dest='S').encode('latin-1')

# --- 3. INTERFAZ GRÁFICA (Las 7 Pestañas) ---

st.title("🟢 GESTOR PRO ONCE")
st.markdown("**ERP Móvil para Vendedor Tipo 4** | Auditoría & Stock")

# Creamos las pestañas
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "👤 Perfil", "📦 Almacén", "🎟️ Rascas", "💰 TPV Diaria", "🌟 Extras", "📊 Informes", "🗓️ Agenda"
])

# --- PESTAÑA 1: PERFIL ---
with tab1:
    st.header("Configuración del Vendedor")
    
    # Cargar datos existentes
    perfil_actual = pd.read_sql("SELECT * FROM perfil", CONN)
    
    with st.form("form_perfil"):
        c1, c2 = st.columns(2)
        nombre = c1.text_input("Nombre", value=perfil_actual.iloc[0]['nombre'] if not perfil_actual.empty else "")
        id_vend = c2.text_input("ID Vendedor", value=perfil_actual.iloc[0]['id_vendedor'] if not perfil_actual.empty else "")
        tipo = st.selectbox("Tipo de Jornada", ["Tipo 4 (X-D)", "Jornada Completa", "Fin de Semana"], index=0)
        
        if st.form_submit_button("Guardar Perfil"):
            C.execute("DELETE FROM perfil") # Resetea para guardar el nuevo
            C.execute("INSERT INTO perfil (nombre, id_vendedor, tipo) VALUES (?,?,?)", (nombre, id_vend, tipo))
            CONN.commit()
            st.success("Perfil actualizado. La lógica de calendario se ha ajustado.")

# --- PESTAÑA 2: ALMACÉN GENERAL ---
with tab2:
    st.header("Entrada de Paquete Semanal")
    col1, col2 = st.columns([2,1])
    with col1:
        st.info("Escanea el código del paquete o introduce manualmente.")
        codigo_paquete = st.text_input("📦 Código de Barras Paquete / Serie")
    with col2:
        tipo_producto = st.selectbox("Contenido", ["Cupones (Preimpreso)", "Rollos Papel", "Marketing"])
        cantidad = st.number_input("Cantidad", min_value=1, value=50)
    
    if st.button("📥 Recepcionar Mercancía"):
        C.execute("INSERT INTO stock_papel VALUES (?,?,?,?)", 
                  (date.today(), tipo_producto, cantidad, 'ALMACEN'))
        CONN.commit()
        st.toast(f"Añadido: {cantidad} de {tipo_producto}")

# --- PESTAÑA 3: RASCAS (CORE) ---
with tab3:
    st.header("Control de Instantánea")
    
    # Sección 1: Alta
    with st.expander("➕ Añadir Nuevo Libro"):
        c1, c2, c3 = st.columns(3)
        juego = c1.selectbox("Juego", ["Mega Millonario (10€)", "Monopoly (3€)", "7 y Media (1€)", "Sueldazo (5€)"])
        cod_libro = c2.text_input("Código de Barras Libro")
        precio = c3.number_input("Valor Total Libro (€)", value=150.0)
        if st.button("Registrar Libro"):
            C.execute("INSERT INTO rascas (juego, codigo, precio_libro, estado, fecha_cambio) VALUES (?,?,?,?,?)",
                      (juego, cod_libro, precio, 'STOCK', date.today()))
            CONN.commit()
            st.rerun()

    # Sección 2: Gestión de Estados
    st.subheader("Inventario Activo")
    df_rascas = pd.read_sql("SELECT * FROM rascas WHERE estado != 'LIQUIDADO'", CONN)
    
    if not df_rascas.empty:
        for index, row in df_rascas.iterrows():
            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
            col1.write(f"**{row['juego']}**")
            col2.caption(f"Ref: {row['codigo']}")
            
            # Lógica de Semáforo
            estado = row['estado']
            if estado == 'STOCK':
                if col3.button("🔓 ACTIVAR", key=f"act_{row['uuid']}"):
                    C.execute("UPDATE rascas SET estado='ACTIVADO' WHERE uuid=?", (row['uuid'],))
                    CONN.commit()
                    st.rerun()
            elif estado == 'ACTIVADO':
                col3.success("EN EXPOSITOR")
                if col4.button("💰 COBRAR", key=f"cob_{row['uuid']}"):
                    C.execute("UPDATE rascas SET estado='LIQUIDADO', fecha_cambio=? WHERE uuid=?", (date.today(), row['uuid']))
                    CONN.commit()
                    st.rerun()
    else:
        st.info("No tienes rascas pendientes. ¡Añade libros!")

# --- PESTAÑA 4: TPV DIARIO ---
with tab4:
    st.header("Calculadora de Liquidación")
    
    # 1. Recuperar Rascas Vendidos Hoy
    rascas_hoy = pd.read_sql("SELECT sum(precio_libro) as total FROM rascas WHERE estado='LIQUIDADO' AND fecha_cambio=?", 
                             CONN, params=(date.today(),))
    total_rascas = rascas_hoy.iloc[0]['total'] if rascas_hoy.iloc[0]['total'] else 0.0
    
    # 2. Asignación Automática (Tipo 4)
    asignacion_base = obtener_asignacion_tipo4()
    
    with st.form("cierre_caja"):
        st.subheader("1. Cupón Físico (Papel)")
        c1, c2, c3 = st.columns(3)
        asig = c1.number_input("Asignación Fija", value=asignacion_base)
        devo = c2.number_input("Devoluciones (Cant.)", min_value=0)
        precio_cupon = c3.number_input("Precio Cupón (€)", value=2.0) # Ajustar según día (3€ Viernes)
        
        venta_papel = (asig - devo) * precio_cupon
        
        st.subheader("2. Datos TPV y Pagos")
        cc1, cc2 = st.columns(2)
        ventas_tpv = cc1.number_input("Ventas TPV (€)", min_value=0.0)
        premios = cc2.number_input("Premios Pagados (€)", min_value=0.0)
        tarjeta = cc1.number_input("Pagos con Tarjeta (€)", min_value=0.0)
        
        st.write(f"ℹ️ Rascas Liquidados Hoy (Automático): **{total_rascas} €**")
        
        if st.form_submit_button("AUDITAR BOLSILLO"):
            # FÓRMULA MAESTRA
            total_ingresos = venta_papel + ventas_tpv + total_rascas
            total_deducciones = premios + tarjeta
            a_ingresar = total_ingresos - total_deducciones
            
            st.divider()
            st.metric(label="DEBES TENER EN EFECTIVO", value=f"{a_ingresar:.2f} €")
            
            # Guardar Cierre
            C.execute("INSERT INTO cierres VALUES (?,?,?,?,?,?,?)", 
                      (date.today(), ventas_tpv, premios, tarjeta, total_rascas, venta_papel, a_ingresar))
            CONN.commit()
            st.success("Cierre guardado en Base de Datos.")

# --- PESTAÑA 5: EXTRAS ---
with tab5:
    st.header("Sorteos Extraordinarios")
    st.warning("⚠️ Contabilidad Separada: No mezclar con caja diaria.")
    
    nombre_extra = st.text_input("Nombre Sorteo (Ej: Extra Verano)")
    col1, col2 = st.columns(2)
    cant_extra = col1.number_input("Cupones Recibidos", min_value=0)
    precio_extra = col2.number_input("Precio Unitario", value=5.0)
    
    if st.button("Registrar Extra"):
        C.execute("INSERT INTO extras VALUES (?,?,?,?,?)", 
                  (nombre_extra, date.today(), cant_extra, precio_extra, 'PENDIENTE'))
        CONN.commit()
        st.success("Deuda Extra registrada.")
        
    # Tabla de Deuda Extra
    extras_db = pd.read_sql("SELECT * FROM extras", CONN)
    if not extras_db.empty:
        extras_db['Deuda Total'] = extras_db['cantidad'] * extras_db['precio']
        st.dataframe(extras_db)

# --- PESTAÑA 6: INFORMES ---
with tab6:
    st.header("Inteligencia de Negocio")
    
    df_cierres = pd.read_sql("SELECT * FROM cierres", CONN)
    
    if not df_cierres.empty:
        # Gráfica
        st.bar_chart(df_cierres.set_index('fecha')['saldo_bolsillo'])
        
        # Botón PDF
        pdf_bytes = generar_pdf_informe(df_cierres)
        st.download_button(label="📄 Descargar Informe PDF", 
                           data=pdf_bytes, 
                           file_name="informe_once.pdf", 
                           mime="application/pdf")
    else:
        st.info("No hay datos suficientes para generar informes.")

# --- PESTAÑA 7: AGENDA ---
with tab7:
    st.header("Diario de Ruta")
    
    fecha_nota = st.date_input("Fecha", date.today())
    texto_nota = st.text_area("Incidencias / Notas")
    tipo_nota = st.selectbox("Tipo", ["Incidencia TPV", "Reclamación", "Nota Personal"])
    
    if st.button("Guardar Nota"):
        C.execute("INSERT INTO agenda VALUES (?,?,?)", (fecha_nota, texto_nota, tipo_nota))
        CONN.commit()
        st.success("Nota guardada.")
        
    st.subheader("Historial")
    notas_db = pd.read_sql("SELECT * FROM agenda ORDER BY fecha DESC", CONN)
    st.dataframe(notas_db)
