import argparse
import importlib
import importlib.resources
import logging
import pickle
import datetime
import h5py
from threading import Thread

import matplotlib
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.pyplot as plt
import nidaqmx
import numpy as np
import tkinter as tk
import yaml

import qt3utils
from qt3utils.datagenerators import plescanner
from qt3utils.applications.controllers.nidaqedgecounter import QT3PleNIDAQEdgeCounterController

from qt3utils.applications.qdlmove.application_gui import PositionControllerApplicationView


matplotlib.use('Agg')


logger = logging.getLogger(__name__)
logging.basicConfig()

CONFIG_PATH = 'qt3utils.applications.controllers'
DEFAULT_CONFIG_FILE = 'NIDAQ Rate Counter'


class PositionControllerApplication():

    def __init__(self, default_config_filename: str):
        
        self.positioners = {}
        self.application_controller = None

        self.configure_from_yaml(afile=default_config_filename)

        # Start application
        self.root = tk.Tk()
        # Launch the GUI
        self.view = PositionControllerApplicationView(main_window = self.root)


    def configure_from_yaml(self, afile=None) -> None:
        pass


    def run(self) -> None:
        '''
        This function launches the application itself.
        '''
        # Set the title of the app window
        self.root.title("qdlmove")
        # Display the window (not in task bar)
        self.root.deiconify()
        # Launch the main loop
        self.root.mainloop()



class TwoAxisApplicationControl():

    def __init__(self,
                 parent: PositionControllerApplication,
                 axis_1_controller_name: str,
                 axis_2_controller_name: str):
        
        self.parent = parent
        self.axis_1_controller_name = axis_1_controller_name
        self.axis_2_controller_name = axis_2_controller_name
        self.active = False # To enable/disable movement by keystrokes?


    # Call back functions for setting x,y positions and 
    def set_axis_1(self):
        # Get the position from the GUI element
        position = None
        # Set the axis
        self.parent.application_controller.move_axis(axis_controller_name=self.axis_1_controller_name, position=position)
        # Update the reader?
    
    def set_axis_2(self):
        # Get the position from the GUI element
        position = None
        # Set the axis
        self.parent.application_controller.move_axis(axis_controller_name=self.axis_2_controller_name, position=position)
        # Update the reader?

    def step_axis_1(self):
        # Get the position from the GUI element
        position = None
        # Set the axis
        self.parent.application_controller.step_axis(axis_controller_name=self.axis_1_controller_name, position=position)
        # Update the reader?
    
    def step_axis_2(self):
        # Get the position from the GUI element
        position = None
        # Set the axis
        self.parent.application_controller.step_axis(axis_controller_name=self.axis_2_controller_name, position=position)
        # Update the reader?



def main():
    tkapp = PositionControllerApplication(DEFAULT_CONFIG_FILE)
    tkapp.run()


if __name__ == '__main__':
    main()
