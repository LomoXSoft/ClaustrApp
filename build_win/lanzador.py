"""Punto de entrada del ejecutable de Windows (PyInstaller)."""
import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()   # el motor OR-Tools se ejecuta en un proceso aparte (spawn)
    from horarios.__main__ import main
    sys.exit(main())
