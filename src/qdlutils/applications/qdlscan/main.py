import importlib
import importlib.resources
import logging

import tkinter as tk
import yaml

from qdlutils.hardware.nidaq.analogoutputs.nidaqposition import NidaqPositionController
from qdlutils.hardware.nidaq.counters.nidaqtimedratecounter import NidaqTimedRateCounter

from qdlutils.applications.qdlscan.application_gui import (
    LauncherApplicationView
)

logger = logging.getLogger(__name__)
logging.basicConfig()


CONFIG_PATH = 'qdlutils.applications.qdlscan.config_files'
DEFAULT_CONFIG_FILE = 'qdlscan_base.yaml'


class LauncherApplication():
    '''
    This is the launcher class for the `qdlscan` application which handles the creation
    of child scan applications which themselves handle the main scanning.

    The purpose of this class is to provde a means of configuring the scan proprties,
    control the DAQ outputs and launching the scans themselves.
    '''

    def __init__(self, default_config_filename: str):
        
        # Load the YAML file based off of `controller_name`
        #self.load_controller_from_name(yaml_filename=default_config_filename)

        # Initialize the root tkinter widget (window housing GUI)
        self.root = tk.Tk()
        # Create the main application GUI
        self.view = LauncherApplicationView(main_window=self.root)

    def run(self) -> None:
        '''
        This function launches the application itself.
        '''
        # Set the title of the app window
        self.root.title("qdlscan")
        # Display the window (not in task bar)
        self.root.deiconify()
        # Launch the main loop
        self.root.mainloop()


class LineScanApplication():
    '''
    This is the line scan application class for `qdlscan` which manages the actual
    application controllers and GUI output of a single scan. It is meant to handle
    1-d confocal scans.
    '''

    def __init__(self, ):
        
        pass

class ImageScanApplication():
    '''
    This is the image scan application class for `qdlscan` which manages the actual
    application controllers and GUI output of a single scan. It is meant to handle 
    2-d confocal scans.
    '''

    def __init__(self, ):
        
        pass



def main():
    tkapp = LauncherApplication(DEFAULT_CONFIG_FILE)
    tkapp.run()


if __name__ == '__main__':
    main()
