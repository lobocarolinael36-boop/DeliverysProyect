import tkinter as tk
from tkinter import messagebox, ttk
import requests
import tkintermapview
from datetime import datetime
import threading

# ── Credenciales API GCBA ──────────────────────────────────────────────────────
GCBA_CLIENT_ID     = "09d5119087564abe95e0b062200f32ae"
GCBA_CLIENT_SECRET = "3Cb1AD4CFCd34100B2F7e4a3143A2a3C"
GCBA_BASE_URL      = "https://apitransporte.buenosaires.gob.ar"

# ── Paleta de colores ──────────────────────────────────────────────────────────
C_BG      = "#1e2a3a"
C_PANEL   = "#2c3e50"
C_DARK    = "#1a252f"
C_ENTRY   = "#34495e"
C_BTN     = "#2980b9"
C_GREEN   = "#16a085"
C_RED     = "#e74c3c"
C_ORANGE  = "#e67e22"
C_TEXT    = "#ecf0f1"
C_MUTED   = "#7f8c8d"

despachos_log = []

# ══════════════════════════════════════════════════════════════════════════════
# Lógica de negocio
# ══════════════════════════════════════════════════════════════════════════════

def _factor_trafico(hora_texto):
    hora = datetime.strptime(hora_texto, "%H:%M").time()
    h = hora.hour + hora.minute / 60.0
    if   7.0 <= h < 10.0: return 2.0,  "Hora pico mañana",  "alto"
    elif 16.0 <= h < 19.0: return 2.5, "Hora pico tarde",   "critico"
    elif 10.0 <= h < 16.0: return 1.2, "Tráfico normal",    "medio"
    else:                   return 1.0, "Tráfico fluido",    "bajo"


def calcular_recorrido():
    salida   = entrada_salida.get().strip()
    destino  = entrada_destino.get().strip()
    hora_txt = entrada_hora.get().strip()

    if not salida or not destino or not hora_txt:
        messagebox.showwarning("Datos incompletos", "Complete todos los campos.")
        return

    try:
        factor, estado_tr, nivel_tr = _factor_trafico(hora_txt)
    except ValueError:
        messagebox.showwarning("Formato inválido", "Ingrese la hora como HH:MM  (ej: 08:30).")
        return

    btn_calcular.config(state="disabled", text="Calculando…")
    _set_estado("Calculando ruta…")

    def _work():
        try:
            hdr  = {"User-Agent": "LogisticaDespacho/2.0"}
            geo  = "https://nominatim.openstreetmap.org/search"

            r = requests.get(geo, params={"format": "json", "q": f"{salida}, CABA, Argentina"},
                             headers=hdr, timeout=10).json()
            if not r: raise Exception("No se encontró la dirección de salida.")
            ls, lo = float(r[0]["lat"]), float(r[0]["lon"])

            r = requests.get(geo, params={"format": "json", "q": f"{destino}, CABA, Argentina"},
                             headers=hdr, timeout=10).json()
            if not r: raise Exception("No se encontró la dirección de destino.")
            ld, lo_d = float(r[0]["lat"]), float(r[0]["lon"])

            ruta_url = (f"https://router.project-osrm.org/route/v1/driving/"
                        f"{lo},{ls};{lo_d},{ld}?overview=full&geometries=geojson")
            ruta = requests.get(ruta_url, timeout=10).json()
            if "routes" not in ruta: raise Exception("Ruta no disponible (OSRM).")

            dist_km  = ruta["routes"][0]["distance"] / 1000
            dur_min  = int((ruta["routes"][0]["duration"] / 60) * factor)
            coords   = ruta["routes"][0]["geometry"]["coordinates"]

            clima_url = (f"https://api.open-meteo.com/v1/forecast?"
                         f"latitude={ld}&longitude={lo_d}&current=temperature_2m,weather_code")
            cl = requests.get(clima_url, timeout=10).json()
            temp   = cl["current"]["temperature_2m"]
            wcode  = cl["current"]["weather_code"]

            if   51 <= wcode <= 67: cielo, riesgo_c = "Lluvioso",  "medio"
            elif wcode >= 95:       cielo, riesgo_c = "Tormenta",  "alto"
            else:                   cielo, riesgo_c = "Despejado", "bajo"

            root.after(0, lambda: _actualizar_ui(
                dist_km, dur_min, temp, cielo, estado_tr, nivel_tr, riesgo_c,
                ls, lo, ld, lo_d, coords, salida, destino, hora_txt))

        except Exception as exc:
            root.after(0, lambda: (
                messagebox.showerror("Error de conexión", str(exc)),
                btn_calcular.config(state="normal", text="Calcular Recorrido"),
                _set_estado("Error al calcular")))

    threading.Thread(target=_work, daemon=True).start()


def _actualizar_ui(dist_km, dur_min, temp, cielo, estado_tr, nivel_tr, riesgo_c,
                   ls, lo, ld, lo_d, coords, salida, destino, hora):

    lbl_dist.config(text=f"  Distancia:  {dist_km:.2f} km")
    lbl_tiempo.config(text=f"  Tiempo est: {dur_min} min")
    lbl_clima.config(text=f"  Clima:  {temp}°C  —  {cielo}")
    lbl_trafico.config(text=f"  Tráfico:  {estado_tr}")

    if cielo == "Tormenta" or nivel_tr == "critico":
        color, msg = C_RED,    "RIESGO ALTO — Tormenta o tráfico crítico"
    elif cielo == "Lluvioso" or nivel_tr == "alto":
        color, msg = C_ORANGE, "PRECAUCIÓN — Condiciones adversas"
    else:
        color, msg = C_GREEN,  "RUTA SEGURA — Condiciones favorables"

    lbl_alerta.config(text=msg, fg=color)

    mapa.delete_all_marker()
    mapa.delete_all_path()
    mapa.set_marker(ls, lo, text="Salida")
    mapa.set_marker(ld, lo_d, text="Destino")
    mapa.set_path([(c[1], c[0]) for c in coords], color="deepskyblue", width=4)
    mapa.set_position((ls + ld) / 2, (lo + lo_d) / 2)
    mapa.set_zoom(13)

    ts = datetime.now().strftime("%H:%M:%S")
    entrada = f"[{ts}]  {salida[:22]}… → {destino[:22]}…  |  {dist_km:.1f}km  {dur_min}min  {cielo}"
    despachos_log.insert(0, entrada)
    lb_historial.insert(0, entrada)

    btn_calcular.config(state="normal", text="Calcular Recorrido")
    _set_estado(f"Último cálculo: {ts}")


# ══════════════════════════════════════════════════════════════════════════════
# Alertas GCBA
# ══════════════════════════════════════════════════════════════════════════════

def cargar_alertas():
    btn_gcba.config(state="disabled", text="Consultando…")
    lb_alertas.delete(0, tk.END)
    lb_alertas.insert(tk.END, "Conectando con la API de Transporte GCBA…")
    _set_estado("Consultando API GCBA…")

    def _fetch():
        url    = f"{GCBA_BASE_URL}/subtes/serviceAlerts"
        params = {"client_id": GCBA_CLIENT_ID,
                  "client_secret": GCBA_CLIENT_SECRET,
                  "json": 1}
        try:
            resp = requests.get(url, params=params, timeout=12)
            resp.raise_for_status()
            data = resp.json()
            root.after(0, lambda: _mostrar_alertas(data))
        except requests.exceptions.HTTPError as e:
            root.after(0, lambda: _mostrar_alertas({"_http_error": str(e)}))
        except Exception as e:
            root.after(0, lambda: _mostrar_alertas({"_conn_error": str(e)}))

    threading.Thread(target=_fetch, daemon=True).start()


def _mostrar_alertas(data):
    lb_alertas.delete(0, tk.END)
    btn_gcba.config(state="normal", text="Actualizar alertas GCBA")

    if "_http_error" in data:
        lb_alertas.insert(tk.END, f"Error HTTP: {data['_http_error']}")
        _set_estado("Error HTTP al consultar GCBA")
        return
    if "_conn_error" in data:
        lb_alertas.insert(tk.END, f"Sin conexión: {data['_conn_error']}")
        _set_estado("Sin conexión con GCBA")
        return

    entidades = data.get("entity", [])
    if not entidades:
        lb_alertas.insert(tk.END, "  Sin alertas activas en este momento.")
        _set_estado("GCBA: sin alertas activas")
        return

    count = 0
    for ent in entidades:
        alerta = ent.get("alert", {})
        traducciones = alerta.get("header_text", {}).get("translation", [])
        header = traducciones[0].get("text", "Sin descripción") if traducciones else "Sin descripción"

        desc_tr = alerta.get("description_text", {}).get("translation", [])
        desc    = desc_tr[0].get("text", "") if desc_tr else ""

        afectados = alerta.get("informed_entity", [])
        lineas = list({str(a.get("route_id", "")) for a in afectados if a.get("route_id")})

        lineas_str = f"  [Líneas: {', '.join(lineas[:4])}]" if lineas else ""
        lb_alertas.insert(tk.END, f"  ALERTA: {header}{lineas_str}")
        if desc and desc.strip() != header.strip():
            lb_alertas.insert(tk.END, f"    ↳ {desc[:90]}{'…' if len(desc) > 90 else ''}")
        lb_alertas.insert(tk.END, "")
        count += 1

    _set_estado(f"GCBA: {count} alerta(s) cargadas")


def _set_estado(msg):
    lbl_estado.config(text=f"  {msg}")


# ══════════════════════════════════════════════════════════════════════════════
# Construcción de la interfaz
# ══════════════════════════════════════════════════════════════════════════════

root = tk.Tk()
root.title("Sistema de Monitoreo y Gestión Logística de Despacho Seguro — CABA")
root.geometry("1140x700")
root.minsize(900, 580)
root.configure(bg=C_BG)

# Estilo del notebook
style = ttk.Style()
style.theme_use("clam")
style.configure("TNotebook",       background=C_PANEL, borderwidth=0, tabmargins=0)
style.configure("TNotebook.Tab",   background=C_DARK,  foreground=C_MUTED,
                padding=[12, 5],   font=("Arial", 9))
style.map("TNotebook.Tab",
          background=[("selected", C_BTN)],
          foreground=[("selected", "white")])
style.configure("TFrame", background=C_PANEL)

# ── Barra de estado (abajo, se empaca primero) ─────────────────────────────
bar_estado = tk.Frame(root, bg=C_DARK, height=22)
bar_estado.pack(side=tk.BOTTOM, fill=tk.X)
bar_estado.pack_propagate(False)
lbl_estado = tk.Label(bar_estado, text="  Sistema listo", bg=C_DARK, fg=C_MUTED,
                      font=("Arial", 8), anchor="w")
lbl_estado.pack(side=tk.LEFT, fill=tk.X, expand=True)
tk.Label(bar_estado, text="GCBA API  |  OSRM  |  Nominatim  |  Open-Meteo  ",
         bg=C_DARK, fg="#3d5166", font=("Arial", 8)).pack(side=tk.RIGHT)

# ── Panel izquierdo ────────────────────────────────────────────────────────
fr_izq = tk.Frame(root, bg=C_PANEL, width=380)
fr_izq.pack(side=tk.LEFT, fill=tk.Y)
fr_izq.pack_propagate(False)

tk.Label(fr_izq, text="DESPACHO SEGURO", bg=C_PANEL, fg=C_TEXT,
         font=("Arial", 13, "bold")).pack(pady=(14, 1))
tk.Label(fr_izq, text="Sistema Logístico · Ciudad de Buenos Aires",
         bg=C_PANEL, fg=C_MUTED, font=("Arial", 8)).pack()
tk.Frame(fr_izq, height=1, bg=C_ENTRY).pack(fill=tk.X, padx=10, pady=8)

notebook = ttk.Notebook(fr_izq)
notebook.pack(fill=tk.BOTH, expand=True, padx=6, pady=0)


# ── Tab 1 · Planificador ───────────────────────────────────────────────────
tab1 = ttk.Frame(notebook, style="TFrame")
notebook.add(tab1, text="  Planificador  ")


def _lbl(p, t):
    tk.Label(p, text=t, bg=C_PANEL, fg="#bdc3c7",
             font=("Arial", 9, "bold"), anchor="w").pack(fill=tk.X, padx=14, pady=(8, 1))


def _entry(p):
    e = tk.Entry(p, font=("Arial", 10), bg=C_ENTRY, fg=C_TEXT,
                 insertbackground=C_TEXT, relief="flat", bd=4)
    e.pack(fill=tk.X, padx=14, pady=(0, 2))
    return e


_lbl(tab1, "Punto de salida:")
entrada_salida  = _entry(tab1)
_lbl(tab1, "Punto de destino:")
entrada_destino = _entry(tab1)
_lbl(tab1, "Hora de salida (HH:MM):")
entrada_hora    = _entry(tab1)
entrada_hora.insert(0, "12:00")

btn_calcular = tk.Button(tab1, text="Calcular Recorrido",
    bg=C_BTN, fg="white", font=("Arial", 10, "bold"),
    relief="flat", cursor="hand2", pady=6, command=calcular_recorrido)
btn_calcular.pack(fill=tk.X, padx=14, pady=(10, 4))

# Cuadro de resultados
fr_res = tk.Frame(tab1, bg=C_DARK, bd=0)
fr_res.pack(fill=tk.X, padx=14, pady=6)

_kw = dict(bg=C_DARK, fg=C_TEXT, font=("Courier", 9), anchor="w")
lbl_dist    = tk.Label(fr_res, text="  Distancia:  —",    **_kw)
lbl_tiempo  = tk.Label(fr_res, text="  Tiempo est: —",    **_kw)
lbl_clima   = tk.Label(fr_res, text="  Clima:  —",        **_kw)
lbl_trafico = tk.Label(fr_res, text="  Tráfico:  —",      **_kw)
for w in (lbl_dist, lbl_tiempo, lbl_clima, lbl_trafico):
    w.pack(fill=tk.X, pady=1)

lbl_alerta = tk.Label(tab1, text="Ingrese origen y destino para calcular",
    bg=C_PANEL, fg=C_MUTED, font=("Arial", 9, "bold"),
    wraplength=340, justify="center")
lbl_alerta.pack(pady=8, padx=14)

tk.Frame(tab1, height=1, bg=C_ENTRY).pack(fill=tk.X, padx=10, pady=4)

tk.Label(tab1, text="Historial de despachos:", bg=C_PANEL, fg="#bdc3c7",
         font=("Arial", 9, "bold")).pack(anchor="w", padx=14)

scr_hist = tk.Scrollbar(tab1, orient="vertical")
lb_historial = tk.Listbox(tab1, yscrollcommand=scr_hist.set, height=5,
    bg=C_DARK, fg="#8899aa", font=("Courier", 7),
    relief="flat", bd=0, selectbackground=C_BTN, activestyle="none")
scr_hist.config(command=lb_historial.yview)
lb_historial.pack(fill=tk.X, padx=(14, 0), pady=(2, 10))
scr_hist.pack_forget()   # scrollbar dentro; usamos el widget mismo como scrollable


# ── Tab 2 · Alertas GCBA ──────────────────────────────────────────────────
tab2 = ttk.Frame(notebook, style="TFrame")
notebook.add(tab2, text="  Alertas GCBA  ")

tk.Label(tab2, text="Alertas de Servicio en Tiempo Real",
         bg=C_PANEL, fg=C_TEXT, font=("Arial", 10, "bold")).pack(pady=(12, 2))
tk.Label(tab2, text="Fuente: API Transporte — Ciudad de Buenos Aires",
         bg=C_PANEL, fg=C_MUTED, font=("Arial", 8)).pack()

btn_gcba = tk.Button(tab2, text="Actualizar alertas GCBA",
    bg=C_GREEN, fg="white", font=("Arial", 9, "bold"),
    relief="flat", cursor="hand2", pady=5, command=cargar_alertas)
btn_gcba.pack(fill=tk.X, padx=14, pady=10)

fr_lb = tk.Frame(tab2, bg=C_PANEL)
fr_lb.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 10))

scr_a = tk.Scrollbar(fr_lb)
scr_a.pack(side=tk.RIGHT, fill=tk.Y)
lb_alertas = tk.Listbox(fr_lb, yscrollcommand=scr_a.set,
    bg=C_DARK, fg=C_TEXT, font=("Arial", 8),
    relief="flat", bd=0, selectbackground=C_BTN, activestyle="none")
lb_alertas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
scr_a.config(command=lb_alertas.yview)

lb_alertas.insert(tk.END, "")
lb_alertas.insert(tk.END, "  Presione 'Actualizar alertas GCBA' para")
lb_alertas.insert(tk.END, "  consultar las alertas en tiempo real de")
lb_alertas.insert(tk.END, "  la red de transporte de Buenos Aires.")

# ── Panel derecho · Mapa ───────────────────────────────────────────────────
fr_mapa = tk.Frame(root, bg=C_BG)
fr_mapa.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

mapa = tkintermapview.TkinterMapView(fr_mapa, corner_radius=0)
mapa.pack(fill=tk.BOTH, expand=True)
mapa.set_position(-34.6037, -58.3816)
mapa.set_zoom(12)

# ──────────────────────────────────────────────────────────────────────────
root.mainloop()
