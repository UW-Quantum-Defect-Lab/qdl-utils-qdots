import logging

import matplotlib
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.pyplot as plt

import tkinter as tk

matplotlib.use('Agg')

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class ScopeApplicationView:

    '''
    Main application GUI view, loads SidePanel and ScanImage
    '''
    def __init__(self, main_window: tk.Tk) -> None:
        main_frame = tk.Frame(main_window)
        main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=40, pady=30)

        self.control_panel = ScopeControlPanel(main_frame)
        self.data_viewport = ScopeDataViewport(main_frame)

class ScopeControlPanel:

    def __init__(self, main_frame: tk.Frame):

        # Define frame for scan configuration and control
        scan_frame = tk.Frame(main_frame)
        scan_frame.pack(side=tk.TOP, padx=0, pady=0)
        # Add buttons and text
        row = 0
        tk.Label(scan_frame, 
                 text='Scan control', 
                 font='Helvetica 14').grid(row=row, column=0, pady=[0,5], columnspan=2)
        # Confocal image section

class ScopeDataViewport:

    def __init__(self, main_frame: tk.Frame):

        # Define frame for scan configuration and control
        scan_frame = tk.Frame(main_frame)
        scan_frame.pack(side=tk.TOP, padx=0, pady=0)
        # Add buttons and text
        row = 0
        tk.Label(scan_frame, 
                 text='Scan control', 
                 font='Helvetica 14').grid(row=row, column=0, pady=[0,5], columnspan=2)
        # Confocal image section