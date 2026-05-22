"""
Solar Monitor - Ana Giris Noktasi
=================================
Streamlit multipage uygulamasinin giris noktasi.

Calistirma:
    streamlit run 1_PANEL.py

Not: Bu dosya Streamlit'in multipage yapisi icin
ana dizinde bulunmaktadir. Asil panel 1_PANEL.py'dir.
Dogrudan calistirmak icin:
    streamlit run 1_PANEL.py
"""

# 1_PANEL.py Streamlit'in ana giris noktasi.
# Bu dosya yalnizca uyumluluk icin vardir.

import os
import subprocess
import sys


if __name__ == "__main__":
    import os, sys, subprocess
    # Eger betik dogrudan 'python Izleme_Paneli.py' olarak cagirilirsa calistir:
    if "streamlit" not in sys.argv[0]:
        panel_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "1_PANEL.py")
        subprocess.run([sys.executable, "-m", "streamlit", "run", panel_path])
