"""Motor de horarios (CP-SAT de OR-Tools).

problema.py  -> traduce un Proyecto (.xghc) a un problema de datos puros (serializable, sin Qt).
cpsat.py     -> construye y resuelve el modelo CP-SAT.
proceso.py   -> ejecuta el motor en un proceso aparte con cola de progreso, parar y pausa.
"""
