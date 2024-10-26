import logging

import matplotlib
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.pyplot as plt

import numpy as np
import tkinter as tk

from qdlutils.hardware.nidaq.counters.nidaqtimedratecounter import NidaqTimedRateCounter

matplotlib.use('Agg')

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class LauncherApplicationView:

    '''
    Main application GUI view, loads SidePanel and ScanImage
    '''
    def __init__(self, main_window: tk.Tk) -> None:
        main_frame = tk.Frame(main_window)
        main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=40, pady=30)

        self.control_panel = ControlPanel(main_frame)

class ControlPanel:

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
        row += 1
        tk.Label(scan_frame, 
                 text='Confocal image', 
                 font='Helvetica 12').grid(row=row, column=0, pady=[0,5], columnspan=2)
        # Range of scan
        row += 1
        tk.Label(scan_frame, text='Range (μm)').grid(row=row, column=0, padx=5, pady=2)
        self.image_range_entry = tk.Entry(scan_frame, width=10)
        self.image_range_entry.insert(10, 80)
        self.image_range_entry.grid(row=row, column=1, padx=5, pady=2)
        # Number of pixels
        row += 1
        tk.Label(scan_frame, text='Number of pixels').grid(row=row, column=0, padx=5, pady=2)
        self.image_pixels_entry = tk.Entry(scan_frame, width=10)
        self.image_pixels_entry.insert(10, 80)
        self.image_pixels_entry.grid(row=row, column=1, padx=5, pady=2)
        # Scan speed
        row += 1
        tk.Label(scan_frame, text='Time per row (s)').grid(row=row, column=0, padx=5, pady=2)
        self.image_time_entry = tk.Entry(scan_frame, width=10)
        self.image_time_entry.insert(10, 1)
        self.image_time_entry.grid(row=row, column=1, padx=5, pady=2)
        # Start button
        row += 1
        self.image_start_button = tk.Button(scan_frame, text='Start scan', width=20)
        self.image_start_button.grid(row=row, column=0, columnspan=2, pady=5)

        # Single axis scan section
        row += 1
        tk.Label(scan_frame, 
                 text='Position optimization', 
                 font='Helvetica 12').grid(row=row, column=0, pady=[10,5], columnspan=2)
        # Range of scan
        row += 1
        tk.Label(scan_frame, text='Range XY (μm)').grid(row=row, column=0, padx=5, pady=2)
        self.line_range_xy_entry = tk.Entry(scan_frame, width=10)
        self.line_range_xy_entry.insert(10, 3)
        self.line_range_xy_entry.grid(row=row, column=1, padx=5, pady=2)
        # Number of pixels
        row += 1
        tk.Label(scan_frame, text='Range Z (μm)').grid(row=row, column=0, padx=5, pady=2)
        self.line_range_z_entry = tk.Entry(scan_frame, width=10)
        self.line_range_z_entry.insert(10, 20)
        self.line_range_z_entry.grid(row=row, column=1, padx=5, pady=2)
        # Number of pixels
        row += 1
        tk.Label(scan_frame, text='Number of pixels').grid(row=row, column=0, padx=5, pady=2)
        self.line_pixels_entry = tk.Entry(scan_frame, width=10)
        self.line_pixels_entry.insert(10, 80)
        self.line_pixels_entry.grid(row=row, column=1, padx=5, pady=2)
        # Scan speed
        row += 1
        tk.Label(scan_frame, text='Time (s)').grid(row=row, column=0, padx=5, pady=2)
        self.line_time_entry = tk.Entry(scan_frame, width=10)
        self.line_time_entry.insert(10, 1)
        self.line_time_entry.grid(row=row, column=1, padx=5, pady=2)
        # Start buttons
        row += 1
        self.line_start_x_button = tk.Button(scan_frame, text='Optimize X', width=20)
        self.line_start_x_button.grid(row=row, column=0, columnspan=2, pady=[5,1])
        row += 1
        self.line_start_y_button = tk.Button(scan_frame, text='Optimize Y', width=20)
        self.line_start_y_button.grid(row=row, column=0, columnspan=2, pady=1)
        row += 1
        self.line_start_z_button = tk.Button(scan_frame, text='Optimize Z', width=20)
        self.line_start_z_button.grid(row=row, column=0, columnspan=2, pady=[1,5])

        # Define frame for DAQ and control
        daq_frame = tk.Frame(main_frame)
        daq_frame.pack(side=tk.TOP, padx=0, pady=0)
        # Add buttons and text
        row = 0
        tk.Label(daq_frame, 
                 text='DAQ control', 
                 font='Helvetica 14').grid(row=row, column=0, pady=[15,5], columnspan=2)
        # X axis
        row += 1
        self.x_axis_set_button = tk.Button(daq_frame, text='Set X (μm)', width=10)
        self.x_axis_set_button.grid(row=row, column=0, columnspan=1, padx=5, pady=[5,1])
        self.x_axis_set_entry = tk.Entry(daq_frame, width=10)
        self.x_axis_set_entry.insert(10, 0)
        self.x_axis_set_entry.grid(row=row, column=1, padx=5, pady=[5,1])
        # Y axis
        row += 1
        self.y_axis_set_button = tk.Button(daq_frame, text='Set Y (μm)', width=10)
        self.y_axis_set_button.grid(row=row, column=0, columnspan=1, padx=5, pady=1)
        self.y_axis_set_entry = tk.Entry(daq_frame, width=10)
        self.y_axis_set_entry.insert(10, 0)
        self.y_axis_set_entry.grid(row=row, column=1, padx=5, pady=1)
        # Z axis
        row += 1
        self.z_axis_set_button = tk.Button(daq_frame, text='Set Z (μm)', width=10)
        self.z_axis_set_button.grid(row=row, column=0, columnspan=1, padx=5, pady=[1,5])
        self.z_axis_set_entry = tk.Entry(daq_frame, width=10)
        self.z_axis_set_entry.insert(10, 0)
        self.z_axis_set_entry.grid(row=row, column=1, padx=5, pady=1)
        # Get button
        row += 1
        self.get_position_button = tk.Button(daq_frame, text='Get current position', width=20)
        self.get_position_button.grid(row=row, column=0, columnspan=2, pady=[1,5])

        # Define frame for DAQ and control
        config_frame = tk.Frame(main_frame)
        config_frame.pack(side=tk.TOP, padx=0, pady=0)
        row = 0
        tk.Label(config_frame, text="Hardware Configuration", font='Helvetica 14').grid(row=row, column=0, pady=[15,5], columnspan=1)
        # Dialouge button to pick the YAML config
        row += 1
        self.hardware_config_from_yaml_button = tk.Button(config_frame, text="Load YAML Config")
        self.hardware_config_from_yaml_button.grid(row=row, column=0, columnspan=1, pady=5)



