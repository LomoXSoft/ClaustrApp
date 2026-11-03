"""Ejecución del motor en un proceso aparte (la interfaz nunca se congela).

    m = MotorEnProceso(pb, segundos=60); m.iniciar()
    m.eventos()  -> lista de eventos nuevos (dict): fase / solucion / fin (con "resultado") / error
    m.pausar(); m.reanudar(); m.parar(); m.vivo()

- multiprocessing con contexto «spawn» (igual en Windows y Linux; compatible con PyInstaller si el
  programa principal llama a multiprocessing.freeze_support()).
- Pausa / reanudación: suspensión del proceso (psutil.Process.suspend/resume). El límite de tiempo del
  motor se mide con tiempo activo, así que el tiempo en pausa no cuenta.
- Parar: evento compartido; el motor detiene la búsqueda y devuelve el mejor resultado encontrado.
"""
from __future__ import annotations
import multiprocessing as mp
import queue as _queue
import traceback

_CTX = mp.get_context("spawn")


def trabajar(pb, cola, ev_parar, opciones):
    """Función de nivel superior (requisito de «spawn»)."""
    try:
        from .cpsat import resolver
        r = resolver(pb, segundos=opciones.get("segundos", 60), hilos=opciones.get("hilos", 8),
                     informar=cola.put, parar=ev_parar, semilla=opciones.get("semilla", 0))
        cola.put({"evento": "fin", "resultado": r})
    except Exception:
        cola.put({"evento": "error", "texto": traceback.format_exc()})


class MotorEnProceso:
    def __init__(self, pb: dict, segundos=60.0, hilos=8, semilla=0):
        self.pb = pb
        self.opciones = {"segundos": segundos, "hilos": hilos, "semilla": semilla}
        self.cola = _CTX.Queue()
        self.ev_parar = _CTX.Event()
        self.proc = None
        self.pausado = False
        self.resultado = None

    def iniciar(self):
        self.proc = _CTX.Process(target=trabajar, args=(self.pb, self.cola, self.ev_parar, self.opciones), daemon=True)
        self.proc.start()

    def _ps(self):
        import psutil
        return psutil.Process(self.proc.pid)

    def pausar(self):
        if self.vivo() and not self.pausado:
            self._ps().suspend(); self.pausado = True

    def reanudar(self):
        if self.vivo() and self.pausado:
            self._ps().resume(); self.pausado = False

    def parar(self):
        if self.pausado:
            self.reanudar()
        self.ev_parar.set()

    def terminar(self):
        """Corte inmediato (cerrar la ventana): mata el proceso sin esperar resultado."""
        if self.proc is not None and self.proc.is_alive():
            if self.pausado:
                self.reanudar()
            self.proc.terminate(); self.proc.join(2)

    def vivo(self):
        return self.proc is not None and self.proc.is_alive()

    def eventos(self):
        out = []
        while True:
            try:
                e = self.cola.get_nowait()
            except _queue.Empty:
                break
            if e.get("evento") == "fin":
                self.resultado = e["resultado"]
            out.append(e)
        return out
