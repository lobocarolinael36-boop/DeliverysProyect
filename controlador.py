# controlador.py
import threading
from datetime import datetime
import tkinter as tk
from tkinter import messagebox

from modelo import LogisticaModelo
from vista import LogisticaVista, C_RED, C_ORANGE, C_GREEN

class LogisticaControlador:
    def __init__(self, modelo, vista):
        self.modelo = modelo
        self.vista = vista

        # Vincular botones a los comandos del controlador
        self.vista.btn_calcular.config(command=self.manejador_calcular_recorrido)
        self.vista.btn_gcba.config(command=self.manejador_cargar_alertas)

        # Mensaje inicial de alertas
        self.vista.lb_alertas.insert(tk.END, "  Presione 'Actualizar alertas GCBA' para comenzar.")

    def manejador_calcular_recorrido(self):
        salida = self.vista.entrada_salida.get().strip()
        destino = self.vista.entrada_destino.get().strip()
        hora_txt = self.vista.entrada_hora.get().strip()

        if not salida or not destino or not hora_txt:
            messagebox.showwarning("Datos incompletos", "Complete todos los campos.")
            return

        try:
            # Validación rápida de hora antes de lanzar el hilo
            self.modelo.obtener_factor_trafico(hora_txt)
        except ValueError:
            messagebox.showwarning("Formato inválido", "Ingrese la hora como HH:MM (ej: 08:30).")
            return

        self.vista.btn_calcular.config(state="disabled", text="Calculando…")
        self.vista.set_estado("Calculando ruta…")

        def _async_worker():
            try:
                res = self.modelo.calcular_ruta_completa(salida, destino, hora_txt)
                # Volver al hilo de UI para pintar resultados
                self.vista.after(0, lambda: self._actualizar_ui_recorrido(res, salida, destino, hora_txt))
            except Exception as e:
                self.vista.after(0, lambda: self._error_recorrido(str(e)))

        threading.Thread(target=_async_worker, daemon=True).start()

    def _actualizar_ui_recorrido(self, res, salida, destino, hora):
        v = self.vista
        v.lbl_dist.config(text=f"  Distancia:  {res['dist_km']:.2f} km")
        v.lbl_tiempo.config(text=f"  Tiempo est: {res['dur_min']} min")
        v.lbl_clima.config(text=f"  Clima:  {res['temp']}°C  —  {res['cielo']}")
        v.lbl_trafico.config(text=f"  Tráfico:  {res['estado_tr']}")

        if res['cielo'] == "Tormenta" or res['nivel_tr'] == "critico":
            color, msg = C_RED, "RIESGO ALTO — Tormenta o tráfico crítico"
        elif res['cielo'] == "Lluvioso" or res['nivel_tr'] == "alto":
            color, msg = C_ORANGE, "PRECAUCIÓN — Condiciones adversas"
        else:
            color, msg = C_GREEN, "RUTA SEGURA — Condiciones favorables"

        v.lbl_alerta.config(text=msg, fg=color)

        # Dibujar en mapa
        v.mapa.delete_all_marker()
        v.mapa.delete_all_path()
        v.mapa.set_marker(res['ls'], res['lo'], text="Salida")
        v.mapa.set_marker(res['ld'], res['lo_d'], text="Destino")
        v.mapa.set_path([(c[1], c[0]) for c in res['coords']], color="deepskyblue", width=4)
        v.mapa.set_position((res['ls'] + res['ld']) / 2, (res['lo'] + res['lo_d']) / 2)
        v.mapa.set_zoom(13)

        # Historial
        ts = datetime.now().strftime("%H:%M:%S")
        entrada = f"[{ts}]  {salida[:22]}… → {destino[:22]}…  |  {res['dist_km']:.1f}km  {res['dur_min']}min"
        v.lb_historial.insert(0, entrada)

        v.btn_calcular.config(state="normal", text="Calcular Recorrido")
        v.set_estado(f"Último cálculo: {ts}")

    def _error_recorrido(self, error_msg):
        messagebox.showerror("Error de conexión", error_msg)
        self.vista.btn_calcular.config(state="normal", text="Calcular Recorrido")
        self.vista.set_estado("Error al calcular")

    def manejador_cargar_alertas(self):
        self.vista.btn_gcba.config(state="disabled", text="Consultando…")
        self.vista.lb_alertas.delete(0, tk.END)
        self.vista.lb_alertas.insert(tk.END, "Conectando con la API de Transporte GCBA…")
        self.vista.set_estado("Consultando API GCBA…")

        def _async_worker():
            try:
                data = self.modelo.consultar_alertas_gcba()
                self.vista.after(0, lambda: self._mostrar_alertas_ui(data))
            except Exception as e:
                self.vista.after(0, lambda: self._mostrar_alertas_ui({"_conn_error": str(e)}))

        threading.Thread(target=_async_worker, daemon=True).start()

    def _mostrar_alertas_ui(self, data):
        v = self.vista
        v.lb_alertas.delete(0, tk.END)
        v.btn_gcba.config(state="normal", text="Actualizar alertas GCBA")

        if "_conn_error" in data:
            v.lb_alertas.insert(tk.END, f"Sin conexión / Error: {data['_conn_error']}")
            v.set_estado("Error de conexión con GCBA")
            return

        entidades = data.get("entity", [])
        if not entidades:
            v.lb_alertas.insert(tk.END, "  Sin alertas activas en este momento.")
            v.set_estado("GCBA: sin alertas activas")
            return

        for count, ent in enumerate(entidades, 1):
            alerta = ent.get("alert", {})
            traducciones = alerta.get("header_text", {}).get("translation", [])
            header = traducciones[0].get("text", "Sin descripción") if traducciones else "Sin descripción"

            desc_tr = alerta.get("description_text", {}).get("translation", [])
            desc = desc_tr[0].get("text", "") if desc_tr else ""

            afectados = alerta.get("informed_entity", [])
            lineas = list({str(a.get("route_id", "")) for a in afectados if a.get("route_id")})

            lineas_str = f"  [Líneas: {', '.join(lineas[:4])}]" if lineas else ""
            v.lb_alertas.insert(tk.END, f"  ALERTA: {header}{lineas_str}")
            if desc and desc.strip() != header.strip():
                v.lb_alertas.insert(tk.END, f"    ↳ {desc[:90]}…")
            v.lb_alertas.insert(tk.END, "")

        v.set_estado(f"GCBA: {len(entidades)} alerta(s) cargadas")


# Punto de Entrada de la Aplicación 
if __name__ == "__main__":
    modelo_app = LogisticaModelo()
    vista_app = LogisticaVista()
    controlador_app = LogisticaControlador(modelo_app, vista_app)
    
    vista_app.mainloop()