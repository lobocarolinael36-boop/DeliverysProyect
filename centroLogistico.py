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
C_BG     = "#1e2a3a"
C_PANEL  = "#2c3e50"
C_DARK   = "#1a252f"
C_ENTRY  = "#34495e"
C_BTN    = "#2980b9"
C_GREEN  = "#16a085"
C_RED    = "#e74c3c"
C_ORANGE = "#e67e22"
C_VIOLET = "#8e44ad"
C_TEXT   = "#ecf0f1"
C_MUTED  = "#7f8c8d"

# ── Estado global ──────────────────────────────────────────────────────────────
despachos_log   = []
ecobici_markers = []   # marcadores activos en el mapa
ecobici_datos   = None # caché: None = aún no se descargó
ecobici_visible = False


# ══════════════════════════════════════════════════════════════════════════════
# Utilidades
# ══════════════════════════════════════════════════════════════════════════════

def _set_estado(msg):
    # Seguro desde cualquier hilo
    root.after(0, lambda: lbl_estado.config(text=f"  {msg}"))


def _factor_trafico(hora_texto):
    h = datetime.strptime(hora_texto, "%H:%M")
    d = h.hour + h.minute / 60.0
    if   7.0 <= d < 10.0:  return 2.0, "Hora pico mañana", "alto"
    elif 16.0 <= d < 19.0: return 2.5, "Hora pico tarde",  "critico"
    elif 10.0 <= d < 16.0: return 1.2, "Tráfico normal",   "medio"
    else:                   return 1.0, "Tráfico fluido",   "bajo"


# ══════════════════════════════════════════════════════════════════════════════
# Planificador de ruta
# ══════════════════════════════════════════════════════════════════════════════

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
    _set_estado("Geocodificando origen…")

    def _work():
        try:
            hdr = {"User-Agent": "LogisticaDespacho/2.0"}
            geo = "https://nominatim.openstreetmap.org/search"

            # Paso 1 – Geocodificación origen
            r = requests.get(geo,
                params={"format": "json", "q": f"{salida}, CABA, Argentina"},
                headers=hdr, timeout=10).json()
            if not r:
                raise Exception("No se encontró la dirección de salida.\n"
                                "Verificá que sea una dirección dentro de CABA.")
            ls, lo = float(r[0]["lat"]), float(r[0]["lon"])

            # Paso 2 – Geocodificación destino
            _set_estado("Geocodificando destino…")
            r = requests.get(geo,
                params={"format": "json", "q": f"{destino}, CABA, Argentina"},
                headers=hdr, timeout=10).json()
            if not r:
                raise Exception("No se encontró la dirección de destino.\n"
                                "Verificá que sea una dirección dentro de CABA.")
            ld, lo_d = float(r[0]["lat"]), float(r[0]["lon"])

            # Paso 3 – Ruta OSRM
            _set_estado("Calculando ruta (OSRM)…")
            ruta = requests.get(
                f"https://router.project-osrm.org/route/v1/driving/"
                f"{lo},{ls};{lo_d},{ld}?overview=full&geometries=geojson",
                timeout=15).json()
            if "routes" not in ruta:
                raise Exception("El servicio de rutas no devolvió un resultado válido.")
            dist_km = ruta["routes"][0]["distance"] / 1000
            dur_min = int((ruta["routes"][0]["duration"] / 60) * factor)
            coords  = ruta["routes"][0]["geometry"]["coordinates"]

            # Paso 4 – Clima Open-Meteo
            _set_estado("Consultando clima (Open-Meteo)…")
            cl = requests.get("https://api.open-meteo.com/v1/forecast",
                params={"latitude": ld, "longitude": lo_d,
                        "current": "temperature_2m,weather_code"},
                timeout=10).json()
            temp  = cl["current"]["temperature_2m"]
            wcode = cl["current"]["weather_code"]

            if   51 <= wcode <= 67: cielo, riesgo_c = "Lluvioso",  "medio"
            elif wcode >= 95:       cielo, riesgo_c = "Tormenta",  "alto"
            else:                   cielo, riesgo_c = "Despejado", "bajo"

            root.after(0, lambda: _actualizar_ui(
                dist_km, dur_min, temp, cielo,
                estado_tr, nivel_tr, ls, lo, ld, lo_d, coords, salida, destino, hora_txt))

        except requests.exceptions.ConnectionError:
            root.after(0, lambda: _error_calc(
                "Sin conexión a internet.\nVerificá tu red e intentá de nuevo."))
        except requests.exceptions.Timeout:
            root.after(0, lambda: _error_calc(
                "Tiempo de espera agotado.\nEl servidor tardó demasiado en responder."))
        except Exception as exc:
            root.after(0, lambda: _error_calc(str(exc)))

    threading.Thread(target=_work, daemon=True).start()


def _error_calc(msg):
    messagebox.showerror("Error", msg)
    btn_calcular.config(state="normal", text="Calcular Recorrido")
    _set_estado("Error al calcular")


def _actualizar_ui(dist_km, dur_min, temp, cielo,
                   estado_tr, nivel_tr, ls, lo, ld, lo_d, coords,
                   salida, destino, hora):

    lbl_dist.config(   text=f"  Distancia:  {dist_km:.2f} km")
    lbl_tiempo.config( text=f"  Tiempo est: {dur_min} min")
    lbl_clima.config(  text=f"  Clima:  {temp}°C  —  {cielo}")
    lbl_trafico.config(text=f"  Tráfico:  {estado_tr}")

    if   cielo == "Tormenta" or nivel_tr == "critico":
        color, msg = C_RED,    "RIESGO ALTO — Tormenta o tráfico crítico"
    elif cielo == "Lluvioso"  or nivel_tr == "alto":
        color, msg = C_ORANGE, "PRECAUCIÓN — Condiciones adversas"
    else:
        color, msg = C_GREEN,  "RUTA SEGURA — Condiciones favorables"
    lbl_alerta.config(text=msg, fg=color)

    # Actualizar mapa — delete_all_marker borra todo, incluyendo EcoBici
    mapa.delete_all_marker()
    mapa.delete_all_path()
    ecobici_markers.clear()  # FIX: sincronizar lista interna con el estado del mapa

    mapa.set_marker(ls, lo,   text="Salida")
    mapa.set_marker(ld, lo_d, text="Destino")
    mapa.set_path([(c[1], c[0]) for c in coords], color="deepskyblue", width=4)
    mapa.set_position((ls + ld) / 2, (lo + lo_d) / 2)
    mapa.set_zoom(13)

    # Si EcoBici estaba visible, volver a renderizarlo sobre la nueva vista
    if ecobici_visible and ecobici_datos:
        _renderizar_ecobici()

    ts = datetime.now().strftime("%H:%M:%S")
    registro = (f"[{ts}]  {salida[:20]}… → {destino[:20]}…  "
                f"|  {dist_km:.1f}km  {dur_min}min  {cielo}")
    despachos_log.insert(0, registro)
    lb_historial.insert(0, registro)

    btn_calcular.config(state="normal", text="Calcular Recorrido")
    _set_estado(f"Último cálculo: {ts}")


# ══════════════════════════════════════════════════════════════════════════════
# EcoBici (API GCBA)
# ══════════════════════════════════════════════════════════════════════════════

def _toggle_ecobici():
    global ecobici_visible

    if ecobici_visible:
        # Ocultar marcadores
        for m in ecobici_markers:
            m.delete()
        ecobici_markers.clear()
        ecobici_visible = False
        btn_ecobici.config(text="Mostrar estaciones EcoBici")
        _set_estado("Estaciones EcoBici ocultadas")
        return

    # Mostrar — si ya hay caché no vuelve a descargar
    btn_ecobici.config(state="disabled", text="Cargando EcoBici…")
    _set_estado("Consultando API EcoBici — GCBA…")

    def _fetch():
        global ecobici_datos
        try:
            params = {"client_id": GCBA_CLIENT_ID, "client_secret": GCBA_CLIENT_SECRET}

            if ecobici_datos is None:
                r_info = requests.get(
                    f"{GCBA_BASE_URL}/ecobici/gbfs/stationInformation",
                    params=params, timeout=12).json()
                r_stat = requests.get(
                    f"{GCBA_BASE_URL}/ecobici/gbfs/stationStatus",
                    params=params, timeout=12).json()

                info_map   = {s["station_id"]: s for s in r_info["data"]["stations"]}
                status_map = {s["station_id"]: s for s in r_stat["data"]["stations"]}

                ecobici_datos = [
                    {
                        "nombre": info.get("name", sid),
                        "lat":    info.get("lat"),
                        "lon":    info.get("lon"),
                        "bikes":  status_map.get(sid, {}).get("num_bikes_available", 0),
                        "docks":  status_map.get(sid, {}).get("num_docks_available", 0),
                    }
                    for sid, info in info_map.items()
                ]

            root.after(0, _renderizar_ecobici)

        except requests.exceptions.ConnectionError:
            root.after(0, lambda: _error_ecobici("Sin conexión a internet."))
        except requests.exceptions.Timeout:
            root.after(0, lambda: _error_ecobici("Tiempo de espera agotado (API GCBA EcoBici)."))
        except Exception as e:
            root.after(0, lambda: _error_ecobici(str(e)))

    threading.Thread(target=_fetch, daemon=True).start()


def _renderizar_ecobici():
    global ecobici_visible

    for est in ecobici_datos:
        if est["lat"] is None or est["lon"] is None:
            continue
        bikes = est["bikes"]
        if   bikes >= 4: c_in, c_out = "#27ae60", "#1e8449"
        elif bikes >= 1: c_in, c_out = "#e67e22", "#d35400"
        else:            c_in, c_out = "#e74c3c", "#c0392b"

        texto = f"{est['nombre']} ({bikes} {'bicis' if bikes != 1 else 'bici'})"
        m = mapa.set_marker(est["lat"], est["lon"], text=texto,
                            marker_color_circle=c_in,
                            marker_color_outside=c_out)
        ecobici_markers.append(m)

    ecobici_visible = True
    btn_ecobici.config(state="normal", text="Ocultar estaciones EcoBici")
    _set_estado(f"EcoBici: {len(ecobici_markers)} estaciones activas en el mapa")


def _error_ecobici(msg):
    messagebox.showerror("Error EcoBici", msg)
    btn_ecobici.config(state="normal", text="Mostrar estaciones EcoBici")
    _set_estado("Error al cargar EcoBici")


# ══════════════════════════════════════════════════════════════════════════════
# Alertas GCBA (Subtes)
# ══════════════════════════════════════════════════════════════════════════════

def cargar_alertas():
    btn_gcba.config(state="disabled", text="Consultando…")
    lb_alertas.delete(0, tk.END)
    lb_alertas.insert(tk.END, "Conectando con la API de Transporte GCBA…")
    _set_estado("Consultando alertas de subtes — API GCBA…")

    def _fetch():
        try:
            resp = requests.get(
                f"{GCBA_BASE_URL}/subtes/serviceAlerts",
                params={"client_id": GCBA_CLIENT_ID,
                        "client_secret": GCBA_CLIENT_SECRET,
                        "json": 1},
                timeout=12)
            resp.raise_for_status()
            root.after(0, lambda: _mostrar_alertas(resp.json()))
        except requests.exceptions.HTTPError as e:
            root.after(0, lambda: _mostrar_alertas({"_error": f"Error HTTP {e.response.status_code}"}))
        except requests.exceptions.ConnectionError:
            root.after(0, lambda: _mostrar_alertas({"_error": "Sin conexión a internet."}))
        except requests.exceptions.Timeout:
            root.after(0, lambda: _mostrar_alertas({"_error": "Tiempo de espera agotado."}))
        except Exception as e:
            root.after(0, lambda: _mostrar_alertas({"_error": str(e)}))

    threading.Thread(target=_fetch, daemon=True).start()


def _mostrar_alertas(data):
    lb_alertas.delete(0, tk.END)
    btn_gcba.config(state="normal", text="Actualizar alertas GCBA")

    if "_error" in data:
        lb_alertas.insert(tk.END, f"  {data['_error']}")
        _set_estado(f"Error GCBA: {data['_error'][:50]}")
        return

    entidades = data.get("entity", [])
    if not entidades:
        lb_alertas.insert(tk.END, "  Sin alertas activas en este momento.")
        _set_estado("GCBA: sin alertas activas")
        return

    count = 0
    for ent in entidades:
        al    = ent.get("alert", {})
        trad  = al.get("header_text", {}).get("translation", [])
        hdr   = trad[0].get("text", "Sin descripción") if trad else "Sin descripción"
        d_tr  = al.get("description_text", {}).get("translation", [])
        desc  = d_tr[0].get("text", "") if d_tr else ""
        afect = al.get("informed_entity", [])
        lineas = list({str(a["route_id"]) for a in afect if a.get("route_id")})

        sufijo = f"  [Líneas: {', '.join(lineas[:4])}]" if lineas else ""
        lb_alertas.insert(tk.END, f"  {hdr}{sufijo}")
        if desc and desc.strip() != hdr.strip():
            lb_alertas.insert(tk.END, f"    {desc[:90]}{'…' if len(desc) > 90 else ''}")
        lb_alertas.insert(tk.END, "")
        count += 1

    _set_estado(f"GCBA: {count} alerta(s) activa(s)")


# ══════════════════════════════════════════════════════════════════════════════
# Construcción de la interfaz
# ══════════════════════════════════════════════════════════════════════════════

root = tk.Tk()
root.title("Sistema de Monitoreo y Gestión Logística de Despacho Seguro — CABA")
root.geometry("1140x700")
root.minsize(900, 580)
root.configure(bg=C_BG)

style = ttk.Style()
style.theme_use("clam")
style.configure("TNotebook",     background=C_PANEL, borderwidth=0, tabmargins=0)
style.configure("TNotebook.Tab", background=C_DARK,  foreground=C_MUTED,
                padding=[12, 5], font=("Arial", 9))
style.map("TNotebook.Tab",
          background=[("selected", C_BTN)],
          foreground=[("selected", "white")])
style.configure("TFrame", background=C_PANEL)

# ── Barra de estado (primero en pack → queda abajo) ────────────────────────
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
notebook.pack(fill=tk.BOTH, expand=True, padx=6)

# ── Tab 1 · Planificador ───────────────────────────────────────────────────
tab1 = ttk.Frame(notebook, style="TFrame")
notebook.add(tab1, text="  Planificador  ")


def _lbl(p, texto):
    tk.Label(p, text=texto, bg=C_PANEL, fg="#bdc3c7",
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
fr_res = tk.Frame(tab1, bg=C_DARK)
fr_res.pack(fill=tk.X, padx=14, pady=6)
_kw = dict(bg=C_DARK, fg=C_TEXT, font=("Courier", 9), anchor="w")
lbl_dist    = tk.Label(fr_res, text="  Distancia:  —", **_kw)
lbl_tiempo  = tk.Label(fr_res, text="  Tiempo est: —", **_kw)
lbl_clima   = tk.Label(fr_res, text="  Clima:  —",     **_kw)
lbl_trafico = tk.Label(fr_res, text="  Tráfico:  —",   **_kw)
for w in (lbl_dist, lbl_tiempo, lbl_clima, lbl_trafico):
    w.pack(fill=tk.X, pady=1)

lbl_alerta = tk.Label(tab1, text="Ingrese origen y destino para calcular",
    bg=C_PANEL, fg=C_MUTED, font=("Arial", 9, "bold"),
    wraplength=340, justify="center")
lbl_alerta.pack(pady=8, padx=14)

tk.Frame(tab1, height=1, bg=C_ENTRY).pack(fill=tk.X, padx=10, pady=4)

tk.Label(tab1, text="Historial de despachos:", bg=C_PANEL, fg="#bdc3c7",
         font=("Arial", 9, "bold")).pack(anchor="w", padx=14)

# FIX: scrollbar correctamente empacado dentro de un frame contenedor
fr_hist = tk.Frame(tab1, bg=C_PANEL)
fr_hist.pack(fill=tk.X, padx=14, pady=(2, 10))
scr_hist = tk.Scrollbar(fr_hist, orient="vertical")
scr_hist.pack(side=tk.RIGHT, fill=tk.Y)
lb_historial = tk.Listbox(fr_hist, yscrollcommand=scr_hist.set, height=5,
    bg=C_DARK, fg="#8899aa", font=("Courier", 7),
    relief="flat", bd=0, selectbackground=C_BTN, activestyle="none")
lb_historial.pack(side=tk.LEFT, fill=tk.X, expand=True)
scr_hist.config(command=lb_historial.yview)

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
lb_alertas.insert(tk.END, "  Presione 'Actualizar alertas GCBA' para consultar")
lb_alertas.insert(tk.END, "  las alertas activas de la red de subtes de CABA.")

# ── Panel derecho · Mapa ───────────────────────────────────────────────────
fr_der = tk.Frame(root, bg=C_BG)
fr_der.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

# Barra de controles sobre el mapa
fr_ctrl = tk.Frame(fr_der, bg=C_DARK, height=36)
fr_ctrl.pack(side=tk.TOP, fill=tk.X)
fr_ctrl.pack_propagate(False)

tk.Label(fr_ctrl, text="  MAPA EN VIVO", bg=C_DARK, fg=C_MUTED,
         font=("Arial", 8, "bold")).pack(side=tk.LEFT, padx=(10, 20))

btn_ecobici = tk.Button(fr_ctrl, text="Mostrar estaciones EcoBici",
    bg=C_VIOLET, fg="white", font=("Arial", 8, "bold"),
    relief="flat", cursor="hand2", padx=10, command=_toggle_ecobici)
btn_ecobici.pack(side=tk.LEFT, pady=5)

# Leyenda de colores EcoBici
fr_ley = tk.Frame(fr_ctrl, bg=C_DARK)
fr_ley.pack(side=tk.LEFT, padx=16)
for color, texto in [("#27ae60", "4+ bicis"), ("#e67e22", "1–3 bicis"), ("#e74c3c", "Sin bicis")]:
    tk.Label(fr_ley, text="■", bg=C_DARK, fg=color, font=("Arial", 11)).pack(side=tk.LEFT)
    tk.Label(fr_ley, text=f" {texto}   ", bg=C_DARK, fg=C_MUTED, font=("Arial", 7)).pack(side=tk.LEFT)

# Mapa interactivo
mapa = tkintermapview.TkinterMapView(fr_der, corner_radius=0)
mapa.pack(fill=tk.BOTH, expand=True)
mapa.set_position(-34.6037, -58.3816)
mapa.set_zoom(12)

# ──────────────────────────────────────────────────────────────────────────────
root.mainloop()
