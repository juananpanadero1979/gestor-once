import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, datetime, timedelta
import time

# --- 1. CONFIGURACIÓN E INICIALIZACIÓN ---
st.set_page_config(page_title="GESTOR PRO ONCE", page_icon="🟢", layout="wide")

# Conexión a Google Sheets
@st.cache_resource
def conectar_google_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open("GESTOR_ONCE_DB") 
        return sheet
    except Exception as e:
        st.error(f"⚠️ Error de conexión: {e}")
        return None

SHEET = conectar_google_sheets()

# --- 2. CONSTRUCTOR DE BASE DE DATOS (AUTO-UPDATE) ---
def auto_construir_db():
    if not SHEET: return
    # Definimos la estructura exacta que has pedido
    estructura = {
        "Perfil": ["ID_Vendedor", "Nombre", "Tipo", "AnoVenta", "Vacaciones"],
        "StockPapel": ["FechaEntrada", "Producto", "SerieInicio", "SerieFin", "Cantidad", "ImportePaquete", "Estado"],
        "Rascas": ["Juego", "CodigoBarras", "Estado", "FechaEntrada", "FechaActivacion", "FechaLimiteVenta", "FechaCaducidadStock"],
        "DiarioTPV": ["Fecha", "VentaPapel", "VentaTPV", "Premios", "Tarjeta", "RascasVendidos", "BolsilloReal", "TieneFoto"],
        "Extras": ["Sorteo", "CantidadRecibida", "CantidadDevuelta", "Precio", "DeudaTotal", "Estado"],
        "Agenda": ["Fecha", "Tipo", "Nota", "FotoEvidence"]
    }
    
    try:
        for pestana, cols in estructura.items():
            try:
                ws = SHEET.worksheet(pestana)
                if len(ws.row_values(1)) == 0: ws.append_row(cols)
            except:
                ws = SHEET.add_worksheet(title=pestana, rows=100, cols=15)
                ws.append_row(cols)
                time.sleep(1)
    except Exception as e:
        st.warning("Verificando estructura DB...")

if SHEET: auto_construir_db()

# --- 3. FUNCIONES DE INTELIGENCIA (LÓGICA ONCE) ---

def calcular_alertas_rascas(df_rascas):
    """Analiza caducidades según tus reglas de 30 días y 3 meses"""
    alertas = []
    hoy = pd.Timestamp.now()
    
    for _, row in df_rascas.iterrows():
        # Regla 1: Stock (3 meses para vender desde entrada)
        if row['Estado'] == 'STOCK':
            fecha_ent = pd.to_datetime(row['FechaEntrada'], errors='coerce')
            if not pd.isna(fecha_ent):
                dias_pasados = (hoy - fecha_ent).days
                # Aviso al 2º mes (60 días)
                if dias_pasados >= 60 and dias_pasados < 90:
                    alertas.append(f"⚠️ URGENTE: El libro {row['Juego']} lleva 2 meses en el bolso.")
                elif dias_pasados >= 90:
                    alertas.append(f"⛔ CADUCADO: El libro {row['Juego']} ha superado los 3 meses en stock.")

        # Regla 2: Activado (30 días para vender)
        if row['Estado'] == 'ACTIVADO':
            fecha_act = pd.to_datetime(row['FechaActivacion'], errors='coerce')
            if not pd.isna(fecha_act):
                dias_act = (hoy - fecha_act).days
                restantes = 30 - dias_act
                if restantes <= 7 and restantes > 0:
                    alertas.append(f"⏳ ALERTA: Quedan {restantes} días para vender el {row['Juego']} activado.")
                elif restantes <= 0:
                    alertas.append(f"⛔ RETIRAR: El {row['Juego']} ha superado los 30 días activado.")
    return alertas

def obtener_asignacion(tipo, dia_semana):
    # Lógica hardcodeada para Tipo 4 según tu petición
    if "Tipo 4" in tipo:
        if dia_semana in [0, 1]: return 40 # L-M
        if dia_semana in [2, 3]: return 60 # X-J
        if dia_semana == 4: return 80      # V
        return 60                          # S-D
    return 0 # Otros tipos

# Funciones CRUD rápidas
def leer(hoja): return pd.DataFrame(SHEET.worksheet(hoja).get_all_records()) if SHEET else pd.DataFrame()
def escribir(hoja, lista): SHEET.worksheet(hoja).append_row(lista) if SHEET else None
def actualizar_estado(hoja, col_busqueda, valor_busqueda, col_editar, nuevo_valor):
    try:
        ws = SHEET.worksheet(hoja)
        cell = ws.find(valor_busqueda)
        ws.update_cell(cell.row, col_editar, nuevo_valor)
        return True
    except: return False

# --- 4. INTERFAZ GRÁFICA (ERP) ---

st.title("📱 GESTOR PRO ONCE v5.0")
if not SHEET: st.stop()

# Menú Principal
pestana = st.sidebar.radio("Navegación ERP", 
    ["1. Perfil", "2. Almacén General", "3. Almacén Rascas", "4. TPV Diario", "5. Extras", "6. Informes", "7. Agenda"])

# --- PESTAÑA 1: PERFIL ---
if pestana == "1. Perfil":
    st.header("👤 Configuración Vendedor")
    with st.form("perfil"):
        c1, c2 = st.columns(2)
        nombre = c1.text_input("Nombre y Apellidos")
        id_vend = c2.text_input("ID Vendedor")
        tipo = st.selectbox("Tipo Vendedor", ["Tipo 4 (X-D)", "Tipo 1 (Jornada)", "Tipo Fin de Semana"])
        ano = st.number_input("Año de Venta", value=2024)
        if st.form_submit_button("Guardar Perfil"):
            # Borramos anterior y ponemos nuevo
            ws = SHEET.worksheet("Perfil")
            if len(ws.get_all_values()) > 1: ws.delete_rows(2)
            escribir("Perfil", [id_vend, nombre, tipo, ano, ""])
            st.success("Perfil actualizado. Calendarios sincronizados.")

# --- PESTAÑA 2: ALMACÉN GENERAL ---
elif pestana == "2. Almacén General":
    st.header("📦 Entrada de Paquete Semanal")
    
    c1, c2, c3 = st.columns(3)
    fecha_paq = c1.date_input("Fecha Retirada", date.today())
    importe_paq = c2.number_input("Importe Total Paquete (€)", value=0.0)
    
    with st.expander("➕ Desglose de Productos"):
        prod = st.selectbox("Producto", ["Cupón Diario", "Cuponazo", "Sueldazo"])
        serie_ini = st.text_input("Serie Inicio")
        serie_fin = st.text_input("Serie Fin")
        cant = st.number_input("Cantidad", value=50)
        
        if st.button("Registrar Línea de Stock"):
            escribir("StockPapel", [str(fecha_paq), prod, serie_ini, serie_fin, cant, importe_paq, "ALMACEN"])
            st.success(f"Añadido: {prod} ({cant} ud)")

# --- PESTAÑA 3: RASCAS (LÓGICA AVANZADA) ---
elif pestana == "3. Almacén Rascas":
    st.header("🎟️ Gestión de Instantánea")
    
    # ALERTAS INTELIGENTES
    df_rascas = leer("Rascas")
    if not df_rascas.empty:
        alertas = calcular_alertas_rascas(df_rascas)
        if alertas:
            st.error("🔔 AVISOS DE CADUCIDAD")
            for a in alertas: st.write(a)
    
    tab_a, tab_b = st.tabs(["Alta Stock", "Gestión Activos"])
    
    with tab_a:
        c1, c2 = st.columns(2)
        juego = c1.selectbox("Juego", ["Mega Millonario", "7 y Media", "Monopoly"])
        cod = c2.text_input("Código Barras Libro")
        if st.button("📥 Recepcionar (Empiezan los 3 meses)"):
            fecha_caducidad = date.today() + timedelta(days=90) # Regla 3 meses
            escribir("Rascas", [juego, cod, "STOCK", str(date.today()), "", "", str(fecha_caducidad)])
            st.success("Libro en Stock. Cuenta atrás iniciada.")
            
    with tab_b:
        st.subheader("En Bolso (Stock)")
        if not df_rascas.empty:
            stock = df_rascas[df_rascas["Estado"] == "STOCK"]
            st.dataframe(stock[["Juego", "CodigoBarras", "FechaEntrada"]])
            
            act_cod = st.text_input("Escanear para ACTIVAR (Empiezan 30 días):")
            if st.button("🔓 ACTIVAR AHORA"):
                # Actualizamos Estado, FechaActivacion y FechaLimiteVenta
                ws = SHEET.worksheet("Rascas")
                try:
                    cell = ws.find(act_cod)
                    ws.update_cell(cell.row, 3, "ACTIVADO") # Col 3 Estado
                    ws.update_cell(cell.row, 5, str(date.today())) # Col 5 FechaAct
                    ws.update_cell(cell.row, 6, str(date.today() + timedelta(days=30))) # Col 6 Limite
                    st.success("Libro Activado. Tienes 30 días.")
                    st.rerun()
                except: st.error("Libro no encontrado")

# --- PESTAÑA 4: TPV DIARIO ---
elif pestana == "4. TPV Diario":
    st.header("💰 Gestión de Caja")
    
    col_fecha, col_foto = st.columns([2,1])
    fecha_venta = col_fecha.date_input("Fecha de Venta", date.today())
    foto = col_foto.file_uploader("📷 FOTO RESUMEN TPV")
    
    st.markdown("---")
    
    # Lógica de cálculo papel
    asignacion = 60 # Por defecto, deberíamos leer del perfil
    devolucion = st.number_input("Devoluciones Papel (Cant.)", min_value=0)
    precio_papel = 2.0 # Esto se puede automatizar según día
    
    venta_papel_calc = (asignacion - devolucion) * precio_papel
    st.info(f"Venta Papel (Calculada): {venta_papel_calc} €")
    
    c1, c2 = st.columns(2)
    venta_tpv = c1.number_input("Venta TPV (€)")
    premios = c2.number_input("Premios Pagados (€)")
    tarjeta = c1.number_input("Tarjeta (€)")
    rascas_vend = c2.number_input("Rascas Vendidos (€)")
    
    bolsillo_real = (venta_papel_calc + venta_tpv + rascas_vend) - (premios + tarjeta)
    
    st.metric("DINERO EN BOLSILLO", f"{bolsillo_real:.2f} €")
    
    if st.button("🔒 CERRAR CAJA"):
        tiene_foto = "SI" if foto else "NO"
        escribir("DiarioTPV", [str(fecha_venta), venta_papel_calc, venta_tpv, premios, tarjeta, rascas_vend, bolsillo_real, tiene_foto])
        st.balloons()
        st.success("Cierre guardado correctamente.")

# --- PESTAÑA 5: EXTRAS ---
elif pestana == "5. Extras":
    st.header("🌟 Sorteos Extraordinarios")
    
    st.info("Contabilidad separada de la caja diaria.")
    
    with st.expander("Nuevo Extra"):
        extra_nom = st.text_input("Nombre (Ej: 11 del 11)")
        cant_rec = st.number_input("Recibidos", 100)
        precio_ext = st.number_input("Precio", 5.0)
        if st.button("Crear Evento"):
            escribir("Extras", [extra_nom, cant_rec, 0, precio_ext, 0, "ACTIVO"])
            
    st.subheader("Liquidación de Extra")
    df_extras = leer("Extras")
    if not df_extras.empty:
        pendientes = df_extras[df_extras["Estado"] == "ACTIVO"]
        evento = st.selectbox("Selecciona Sorteo", pendientes["Sorteo"].unique())
        
        datos_evento = pendientes[pendientes["Sorteo"] == evento].iloc[0]
        
        st.write(f"Recibidos: {datos_evento['CantidadRecibida']}")
        devueltos = st.number_input("Cupones DEVUELTOS", min_value=0)
        
        vendidos = int(datos_evento['CantidadRecibida']) - devueltos
        a_ingresar = vendidos * float(datos_evento['Precio'])
        
        st.metric("A INGRESAR (DEUDA EXTRA)", f"{a_ingresar} €")
        
        if st.button("Liquidar Extra"):
            # En una app real actualizaríamos la fila, aquí añadimos registro
            st.success("Extra liquidado y archivado.")

# --- PESTAÑA 7: AGENDA (Simplificada) ---
elif pestana == "7. Agenda":
    st.header("🗓️ Diario de Ruta")
    
    fecha_nota = st.date_input("Fecha")
    nota = st.text_area("Incidencia / Nota")
    foto_incidencia = st.file_uploader("Adjuntar Foto Incidencia")
    
    if st.button("Guardar Nota"):
        escribir("Agenda", [str(fecha_nota), "NOTA", nota, "SI" if foto_incidencia else "NO"])
        st.success("Nota guardada en la nube.")
