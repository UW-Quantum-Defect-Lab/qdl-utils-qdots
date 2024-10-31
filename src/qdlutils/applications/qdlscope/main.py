import importlib
import importlib.resources
import logging
import numpy as np
import datetime
import h5py

from threading import Thread
import tkinter as tk
import yaml

import qdlutils
from qdlutils.applications.qdlscope.application_controller import ScopeController
from qdlutils.applications.qdlscope.application_gui import ScopeApplicationView

logger = logging.getLogger(__name__)
logging.basicConfig()


CONFIG_PATH = 'qdlutils.applications.qdlscope.config_files'
DEFAULT_CONFIG_FILE = 'qdlscope_base.yaml'


class ScopeApplication:

    def __init__(self, default_config_filename: str):
        
        self.application_controller = None

        # Data
        self.x_data = []
        self.y_data = []

        # Plotting parameters
        self.max_samples_to_plot = 500
        self.sample_time = None
        self.batch_time = None

        # Last save directory
        self.last_save_directory = None

        # Load the YAML file
        self.load_yaml_from_name(yaml_filename=default_config_filename)

        # Initialize the root tkinter widget (window housing GUI)
        self.root = tk.Tk()
        # Create the main application GUI
        self.view = ScopeApplicationView(main_window=self.root)

        # Bind the buttons


    def start(self, tkinter_event: tk.Event = None):
        
        pass


    def sample_continuous_thread_function(self) -> None:
        try:
            logger.info('Starting continuous sampling thread.')

            for sample in self.application_controller.read_counts_continuous(
                                self.sample_time, 
                                self.get_rate):
                
                # Save the data
                self.y_data.append(sample)

                # Update the viewport
                self.view.update_figure()

            logger.info('Sampling complete.')
        except Exception as e:
            logger.info(e)
        # Enable the buttons
        self.parent_application.enable_buttons()