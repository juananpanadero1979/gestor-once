import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, timedelta
import time

st.set_page_config(page_title="GESTOR PRO ONCE", page_icon="🟢", layout="wide")

# --- 1. CONEXIÓN BLINDADA ---
@st.cache_resource
def conectar_google_sheets():
    try:
        # Cargamos credenciales
        creds_dict = dict(st.secrets["gcp_service_account"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # Intentamos abrir la hoja
        sheet = client.open("GESTOR_ONCE_DB") 
        return sheet, creds.service_account_email
    except gspread.SpreadsheetNotFound:
        st.error("❌ NO ENCUENTRO EL ARCHIVO 'GESTOR_ONCE_DB'")
        st.info("Asegúrate de haber creado una hoja con ese nombre EXACTO en tu Google Drive.")
        return None, None
    except Exception as e:
        st.error(f"❌ ERROR DE CONEXIÓN: {e}")
        return None, None

SHEET, EMAIL_ROBOT = conectar_google_sheets()

# --- 2. DIAGNÓSTICO INICIAL (¡ESTO ES NUEVO!) ---
if not SHEET:
    st.stop() # Si no hay hoja, paramos aquí

# Mostramos el estado de la conexión para que veas si está bien
with st.expander("🔧 ESTADO DE LA CONEXIÓN (Abre si tienes errores)"):
    st.write(f"🤖 **Soy el Robot:** `{EMAIL_ROBOT}`")
    st.write("✅ He encontrado el archivo `GESTOR_ONCE_DB`")
    st.info("👆 COPIA ese correo y asegúrate de que está compartido como EDITOR en tu Google Sheet.")

# --- 3. CONSTRUCTOR DE BASE DE DATOS (REPARADO) ---
def chequear_y_construir():
    estruc = {
        "Perfil": ["ID_Vendedor", "Nombre", "Tipo", "AnoVenta", "Vacaciones"],
        "StockPapel": ["FechaEntrada", "Producto", "SerieInicio", "SerieFin", "Cantidad", "ImportePaquete", "Estado"],
        "Rascas": ["Juego", "CodigoBarras", "Estado", "FechaEntrada", "FechaActivacion", "FechaLimiteVenta", "FechaCaducidadStock"],
        "DiarioTPV": ["Fecha", "VentaPapel", "VentaTPV", "Premios", "Tarjeta", "RascasVendidos", "BolsilloReal", "TieneFoto"],
        "Extras": ["Sorteo", "CantidadRecibida", "CantidadDevuelta", "Precio", "DeudaTotal", "Estado"],
        "Agenda": ["Fecha", "Tipo", "Nota", "FotoEvidence"]
    }
    
    # Botón de emergencia por si faltan pestañas
    if st.button("🛠️ REPARAR / CREAR BASE DE DATOS"):
        barra = st.progress(0)
        idx = 0
        for pestana, columnas in estruc.items():
            try:
                try:
                    ws = SHEET.worksheet(pestana)
                except:
                    ws = SHEET.add_worksheet(title=pestana, rows=100, cols=20)
                
                # Si está vacía, ponemos cabeceras
                if not ws.get_all_values():
                    ws.append_row(columnas)
                
            except Exception as e:
                st.error(f"Error creando {pestana}: {e}")
            
            idx += 1
            barra.progress(idx / len(estruc))
        st.success("✅ Base de datos reparada. Recarga la página.")
        time.sleep(2)
        st.rerun()

chequear_y_construir()

# --- 4. FUNCIONES AUXILIARES ---
def leer(hoja):
    try:
        return pd.DataFrame(SHEET.worksheet(hoja).get_all_records())
    except:
        return pd.DataFrame()

def escribir(hoja, lista):
    try:
        SHEET.worksheet(hoja).append_row(lista)
        return True
    except Exception as e:
        st.error(f"Error escribiendo en {hoja}: {e}")
        return False

# --- 5. INTERFAZ GRÁFICA ---

st.title("📱 GESTOR PRO ONCE v5.1")

# Menú Seguro (No falla si falta la hoja)
pestana = st.sidebar.radio("Navegación", 
    ["1. Perfil", "2. Almacén General", "3. Almacén Rascas", "4. TPV Diario", "5. Extras", "7. Agenda"])

# --- PESTAÑA 1: PERFIL ---
if pestana == "1. Perfil":
    st.header("👤 Configuración")
    
    try:
        ws = SHEET.worksheet("Perfil")
        # Leemos datos actuales
        datos = ws.get_all_records()
        valores_actuales = datos[0] if datos else {}
    except:
        st.warning("⚠️ La pestaña 'Perfil' no existe o está vacía. Pulsa el botón 'REPARAR' arriba.")
        st.stop()

    with st.form("perfil"):
        c1, c2 = st.columns(2)
        nombre = c1.text_input("Nombre", value=valores_actuales.get("Nombre", ""))
        id_vend = c2.text_input("ID Vendedor", value=valores_actuales.get("ID_Vendedor", ""))
        tipo = st.selectbox("Tipo", ["Tipo 4 (X-D)", "Tipo 1 (Jornada)", "Tipo Fin de Semana"])
        ano = st.number_input("Año", value=2024)
        
        if st.form_submit_button("Guardar"):
            # Limpiamos y reescribimos
            ws.clear()
            ws.append_row(["ID_Vendedor", "Nombre", "Tipo", "AnoVenta", "Vacaciones"])
            ws.append_row([id_vend, nombre, tipo, ano, ""])
            st.success("Perfil Guardado")

# --- PESTAÑA 2: ALMACÉN ---
elif pestana == "2. Almacén General":
    st.header("📦 Entrada Paquete")
    c1, c2 = st.columns(2)
    fecha = c1.date_input("Fecha", date.today())
    importe = c2.number_input("Importe Paquete (€)", 0.0)
    
    with st.expander("➕ Añadir Producto"):
        prod = st.selectbox("Producto", ["Cupón Diario", "Cuponazo", "Sueldazo"])
        cant = st.number_input("Cantidad", 50)
        if st.button("Registrar"):
            escribir("StockPapel", [str(fecha), prod, "", "", cant, importe, "ALMACEN"])
            st.success("Guardado")

# --- PESTAÑA 3: RASCAS ---
elif pestana == "3. Almacén Rascas":
    st.header("🎟️ Rascas")
    
    tab1, tab2 = st.tabs(["Alta", "Activos"])
    with tab1:
        juego = st.selectbox("Juego", ["Mega Millonario", "7 y Media", "Monopoly"])
        cod = st.text_input("Código Barras")
        if st.button("Recepcionar"):
             # Calculamos 90 días para caducidad
             caducidad = date.today() + timedelta(days=90)
             escribir("Rascas", [juego, cod, "STOCK", str(date.today()), "", "", str(caducidad)])
             st.success("Libro registrado")
             
    with tab2:
        df = leer("Rascas")
        if not df.empty:
            st.dataframe(df)
            act = st.text_input("Escanear para ACTIVAR")
            if st.button("Activar Libro"):
                try:
                    ws = SHEET.worksheet("Rascas")
                    cell = ws.find(act)
                    ws.update_cell(cell.row, 3, "ACTIVADO")
                    st.success("Activado")
                except:
                    st.error("No encontrado")

# --- PESTAÑA 4: TPV ---
elif pestana == "4. TPV Diario":
    st.header("💰 Cierre Diario")
    v_tpv = st.number_input("Venta TPV")
    bolsillo = st.number_input("Bolsillo Real")
    
    if st.button("Cerrar Caja"):
        escribir("DiarioTPV", [str(date.today()), 0, v_tpv, 0, 0, 0, bolsillo, "NO"])
        st.balloons()
