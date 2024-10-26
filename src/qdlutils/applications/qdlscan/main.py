import importlib
import importlib.resources
import logging
import numpy as np
import datetime

from threading import Thread
import tkinter as tk
import yaml

from qdlutils.hardware.nidaq.analogoutputs.nidaqposition import NidaqPositionController
from qdlutils.hardware.nidaq.counters.nidaqtimedratecounter import NidaqTimedRateCounter

from qdlutils.applications.qdlscan.application_controller import ScanController
from qdlutils.applications.qdlscan.application_gui import (
    LauncherApplicationView,
    LineScanApplicationView
)

logger = logging.getLogger(__name__)
logging.basicConfig()


CONFIG_PATH = 'qdlutils.applications.qdlscan.config_files'
DEFAULT_CONFIG_FILE = 'qdlscan_base.yaml'

# Dictionary for converting axis to an index
AXIS_INDEX = {'x': 0, 'y': 1, 'z': 2}


class LauncherApplication():
    '''
    This is the launcher class for the `qdlscan` application which handles the creation
    of child scan applications which themselves handle the main scanning.

    The purpose of this class is to provde a means of configuring the scan proprties,
    control the DAQ outputs and launching the scans themselves.
    '''

    def __init__(self, default_config_filename: str):
        
        # Attributes
        self.application_controller = None
        self.min_x_position = None
        self.min_y_position = None
        self.min_z_position = None
        self.max_x_position = None
        self.max_y_position = None
        self.max_z_position = None

        # Number of scan windows launched
        self.number_scans = 0
        # Most recent scan -- maybe not needed?
        self.current_scan = None
        # Dictionary of scan parameters
        self.scan_parameters = None

        # Load the YAML file based off of `controller_name`
        self.load_yaml_from_name(yaml_filename=default_config_filename)

        # Initialize the root tkinter widget (window housing GUI)
        self.root = tk.Tk()
        # Create the main application GUI
        self.view = LauncherApplicationView(main_window=self.root)

        # Bind the buttons
        self.view.control_panel.line_start_x_button.bind("<Button>", self.optimize_x_axis)
        self.view.control_panel.line_start_y_button.bind("<Button>", self.optimize_y_axis)
        self.view.control_panel.line_start_z_button.bind("<Button>", self.optimize_z_axis)

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

    def configure_from_yaml(self, afile: str) -> None:
        '''
        This method loads a YAML file to configure the qdlmove hardware
        based on yaml file indicated by argument `afile`.

        This method instantiates and configures the controllers and counters
        for the scan application, then creates the application controller.
        '''
        with open(afile, 'r') as file:
            # Log selection
            logger.info(f"Loading settings from: {afile}")
            # Get the YAML config as a nested dict
            config = yaml.safe_load(file)

        # First we get the top level application name
        APPLICATION_NAME = list(config.keys())[0]

        # Get the names of the counter and positioners
        hardware_dict = config[APPLICATION_NAME]['ApplicationController']['hardware']
        counter_name = hardware_dict['counter']
        x_axis_name = hardware_dict['x_axis_control']
        y_axis_name = hardware_dict['y_axis_control']
        z_axis_name = hardware_dict['z_axis_control']

        # Get the counter, instantiate, and configure
        import_path = config[APPLICATION_NAME][counter_name]['import_path']
        class_name = config[APPLICATION_NAME][counter_name]['class_name']
        module = importlib.import_module(import_path)
        logger.debug(f"Importing {import_path}")
        constructor = getattr(module, class_name)
        counter = constructor()
        counter.configure(config[APPLICATION_NAME][counter_name]['configure'])

        # Get the x axis instance
        import_path = config[APPLICATION_NAME][x_axis_name]['import_path']
        class_name = config[APPLICATION_NAME][x_axis_name]['class_name']
        module = importlib.import_module(import_path)
        logger.debug(f"Importing {import_path}")
        constructor = getattr(module, class_name)
        x_axis = constructor()
        x_axis.configure(config[APPLICATION_NAME][x_axis_name]['configure'])
        # Get the limits
        self.min_x_position = config[APPLICATION_NAME][x_axis_name]['configure']['min_position']
        self.max_x_position = config[APPLICATION_NAME][x_axis_name]['configure']['max_position']

        # Get the y axis instance
        import_path = config[APPLICATION_NAME][y_axis_name]['import_path']
        class_name = config[APPLICATION_NAME][y_axis_name]['class_name']
        module = importlib.import_module(import_path)
        logger.debug(f"Importing {import_path}")
        constructor = getattr(module, class_name)
        y_axis = constructor()
        y_axis.configure(config[APPLICATION_NAME][y_axis_name]['configure'])
        # Get the limits
        self.min_y_position = config[APPLICATION_NAME][y_axis_name]['configure']['min_position']
        self.max_y_position = config[APPLICATION_NAME][y_axis_name]['configure']['max_position']

        # Get the z axis instance
        import_path = config[APPLICATION_NAME][z_axis_name]['import_path']
        class_name = config[APPLICATION_NAME][z_axis_name]['class_name']
        module = importlib.import_module(import_path)
        logger.debug(f"Importing {import_path}")
        constructor = getattr(module, class_name)
        z_axis = constructor()
        z_axis.configure(config[APPLICATION_NAME][z_axis_name]['configure'])
        # Get the limits
        self.min_z_position = config[APPLICATION_NAME][z_axis_name]['configure']['min_position']
        self.max_z_position = config[APPLICATION_NAME][z_axis_name]['configure']['max_position']

        # Get the application controller constructor 
        import_path = config[APPLICATION_NAME]['ApplicationController']['import_path']
        class_name = config[APPLICATION_NAME]['ApplicationController']['class_name']
        module = importlib.import_module(import_path)
        logger.debug(f"Importing {import_path}")
        constructor = getattr(module, class_name)
        # Get the configure dictionary
        controller_config_dict = config[APPLICATION_NAME]['ApplicationController']['configure']
        # Create the application controller passing the hardware and the config dict
        # as kwargs.
        self.application_controller = constructor(
            **{'x_axis_controller': x_axis,
               'y_axis_controller': y_axis,
               'z_axis_controller': z_axis,
               'counter_controller': counter,
               **controller_config_dict}
        )

    def load_yaml_from_name(self, yaml_filename: str) -> None:
        '''
        Loads the default yaml configuration file for the application controller.

        Should be called during instantiation of this class and should be the callback
        function for the support controller pull-down menu in the side panel
        '''
        yaml_path = importlib.resources.files(CONFIG_PATH).joinpath(yaml_filename)
        self.configure_from_yaml(str(yaml_path))

    def enable_buttons(self):
        pass
    def disable_buttons(self):
        pass

    def optimize_x_axis(self, tkinter_event=None):
        logger.info('Optimizing X axis.')
        # Update the parameters
        self._get_scan_config()
        # Increase the nunmber of scans launched
        self.number_scans += 1
        # Launch a line scan application
        self.current_scan = LineScanApplication(
            parent_application = self,
            application_controller = self.application_controller,
            axis = 'x',
            range = self.scan_parameters['line_range_xy'],
            n_pixels = self.scan_parameters['line_pixels'],
            time = self.scan_parameters['line_time'],
            id = self.number_scans
        )
    def optimize_y_axis(self, tkinter_event=None):
        logger.info('Optimizing Y axis.')
        # Update the parameters
        self._get_scan_config()
        # Increase the nunmber of scans launched
        self.number_scans += 1
        # Launch a line scan application
        self.current_scan = LineScanApplication(
            parent_application = self,
            application_controller = self.application_controller,
            axis = 'y',
            range = self.scan_parameters['line_range_xy'],
            n_pixels = self.scan_parameters['line_pixels'],
            time = self.scan_parameters['line_time'],
            id = self.number_scans
        )
    def optimize_z_axis(self, tkinter_event=None):
        logger.info('Optimizing Z axis.')
        # Update the parameters
        self._get_scan_config()
        # Increase the nunmber of scans launched
        self.number_scans += 1
        # Launch a line scan application
        self.current_scan = LineScanApplication(
            parent_application = self,
            application_controller = self.application_controller,
            axis = 'z',
            range = self.scan_parameters['line_range_z'],
            n_pixels = self.scan_parameters['line_pixels'],
            time = self.scan_parameters['line_time'],
            id = self.number_scans
        )
    
    def _get_scan_config(self) -> dict:
        '''
        Get the values in the GUI
        '''
        image_range = float(self.view.control_panel.image_range_entry.get())
        image_pixels = int(self.view.control_panel.image_pixels_entry.get())
        image_time = float(self.view.control_panel.image_time_entry.get())
        line_range_xy = float(self.view.control_panel.line_range_xy_entry.get())
        line_range_z = float(self.view.control_panel.line_range_z_entry.get())
        line_pixels = int(self.view.control_panel.line_pixels_entry.get())
        line_time = float(self.view.control_panel.line_time_entry.get())

        self.scan_parameters = {
            'image_range': image_range,
            'image_pixels': image_pixels,
            'image_time': image_time,
            'line_range_xy': line_range_xy,
            'line_range_z': line_range_z,
            'line_pixels': line_pixels,
            'line_time': line_time,
        }


class LineScanApplication():
    '''
    This is the line scan application class for `qdlscan` which manages the actual
    application controllers and GUI output of a single scan. It is meant to handle
    1-d confocal scans.
    '''

    def __init__(self, 
                 parent_application: LauncherApplication,
                 application_controller: ScanController,
                 axis: str,
                 range: float,
                 n_pixels: int,
                 time: float,
                 id: str):
        
        self.parent_application = parent_application
        self.application_controller = application_controller
        self.axis = axis
        self.range = range
        self.n_pixels = n_pixels
        self.time = time

        # Time per pixel
        self.time_per_pixel = time / n_pixels

        self.id = id
        self.timestamp = datetime.datetime.now()

        # Get the limits of the position for the axis
        if axis == 'x':
            min_allowed_position = self.parent_application.min_x_position
            max_allowed_position = self.parent_application.max_x_position
        elif axis == 'y':
            min_allowed_position = self.parent_application.min_y_position
            max_allowed_position = self.parent_application.max_y_position
        elif axis == 'z':
            min_allowed_position = self.parent_application.min_z_position
            max_allowed_position = self.parent_application.max_z_position
        else:
            raise ValueError(f'Requested axis {axis} is invalid.')

        # Get the starting position
        start_position = application_controller.get_position()
        # Get the limits of the scan
        self.min_position = start_position[AXIS_INDEX[axis]] - (range/2)
        self.max_position = start_position[AXIS_INDEX[axis]] + (range/2)
        # Check if the limits exceed the range and shift range to edge
        if self.min_position < min_allowed_position:
            # Too close to minimum edge, need to shift up
            shift = min_allowed_position - self.min_position
            self.min_position += shift
            self.max_position += shift
        if self.max_position > max_allowed_position:
            # Too close to minimum edge, need to shift up
            shift = max_allowed_position - self.max_position
            self.min_position += shift
            self.max_position += shift
        # Get the scan positions (along whatever axis is being scanned)
        # We're brute forcing it here as the application controller might not sample
        # positions in the exact same way...
        self.data_x = np.linspace(start=self.min_position, 
                                  stop=self.max_position, 
                                  num=n_pixels)
        # To hold scan results
        self.data_y = np.empty(shape=n_pixels)

        # Launch the line scan GUI
        # Then initialize the GUI
        self.root = tk.Toplevel()
        self.root.title(f'Scan {id} ({self.timestamp.strftime("%Y-%m-%d %H:%M:%S")})')
        self.view = LineScanApplicationView() # Meed to add arguments...

        # Start the scan thread
        # Launch the thread
        self.scan_thread = Thread(target=self.scan_thread_function)
        self.scan_thread.start()

    def scan_thread_function(self):
        try:
            logger.info('Starting scan thread.')
            logger.info(f'Starting scan on axis {self.axis}')
            # Run the scan
            self.data_y = self.application_controller.scan_axis(
                axis = self.axis,
                start = self.min_position,
                stop = self.max_position,
                n_pixels = self.n_pixels,
                scan_time = self.time
            )
            # Update the viewport
            self.view.data_viewport.update()
            
            print(self.data_y) # DEBUG
            logger.info('Scan complete.')
        except Exception as e:
            logger.info(e)
        # Enable the buttons
        self.parent_application.enable_buttons()


class ImageScanApplication():
    '''
    This is the image scan application class for `qdlscan` which manages the actual
    application controllers and GUI output of a single scan. It is meant to handle 
    2-d confocal scans.
    '''

    def __init__(self, ):
        
        pass

    def scan_thread_function(self):
        '''
        THis is wrong but has the right structure.
        '''
        try:
            while self.application_controller.busy:
                self.current_scan.application_controller.scan_wavelengths()
                self.current_scan.view.data_viewport.update_image_and_plot(self.current_scan.application_controller)
                self.current_scan.view.canvas.draw()

            logger.info('Scan complete.')
            self.current_scan.application_controller.stop()

        except nidaqmx.errors.DaqError as e:
            logger.info(e)
            logger.info(
                'Check for other applications using resources. If not, you may need to restart the application.')

        self.enable_buttons()



def main():
    tkapp = LauncherApplication(DEFAULT_CONFIG_FILE)
    tkapp.run()


if __name__ == '__main__':
    main()
