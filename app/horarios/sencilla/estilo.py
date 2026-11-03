"""Hoja de estilo de la versión sencilla (paleta del prototipo)."""
AZUL, LAV, MOR, TXT, FONDO = "#5b8def", "#e9e6fb", "#6c4fc9", "#33354a", "#f7f6fd"

CSS = f"""
QWidget#sencilla {{ background: {FONDO}; color: {TXT}; font-size: 10.5pt; }}
QLabel#titulo {{ font-size: 17pt; font-weight: 600; color: {TXT}; }}
QLabel#ayuda {{ color: #6b6d80; }}
QFrame#tarjeta {{ background: white; border: 1px solid #dcd8f3; border-radius: 10px; }}
QListWidget#pasos {{ background: {LAV}; border: none; font-size: 11pt; padding: 6px; }}
QListWidget#pasos::item {{ padding: 9px 8px; border-radius: 6px; color: {TXT}; }}
QListWidget#pasos::item:selected {{ background: {MOR}; color: white; }}
QPushButton {{ background: white; border: 1px solid #c9c3ef; border-radius: 6px; padding: 6px 14px; color: {TXT}; }}
QPushButton:hover {{ background: {LAV}; }}
QPushButton#primario {{ background: {AZUL}; color: white; border: none; font-weight: 600; }}
QPushButton#primario:disabled {{ background: #aebfe6; }}
QPushButton#enlace {{ border: none; background: transparent; color: {MOR}; text-decoration: underline; }}
QTableWidget {{ background: white; gridline-color: #e6e3f6; border: 1px solid #dcd8f3; border-radius: 6px; }}
QHeaderView::section {{ background: {LAV}; border: none; padding: 5px; font-weight: 600; }}
QProgressBar {{ border: 1px solid #c9c3ef; border-radius: 6px; text-align: center; background: white; height: 22px; }}
QProgressBar::chunk {{ background: {AZUL}; border-radius: 6px; }}
"""
