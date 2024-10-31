import importlib
import importlib.resources
import logging
import numpy as np
import datetime
import h5py
import time

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
    '''
    
    Due to the implementation of the continuous scanning there is a slight overhead
    associated to each data sample which results in an increased time between samples.

    Based off of the current implementation and testing with the time module, it seems
    like the majority of the overhead is due to the updating of the figure (about 50 ms
    at 500 samples per view). The actual overhead associated with the sampling appears
    to be quite miniminal for the desired data (< 1 ms in all cases).

    This discrepancy can be problematic if the scope data is desired to be accurate.

    There are a few ways of remedying this:
        1.  One could simply generate the timestamp for each sample via `time.time()`
            and then append this to the `self.data_x`.
        2.  Change the plotting funciton to reduce the overhead further
        3.  
    '''

    def __init__(self, default_config_filename: str):
        
        self.application_controller = None

        # Data
        self.data_x = None
        self.data_y = []

        # Plotting parameters
        self.max_samples_to_plot = 500
        self.daq_parameters = None

        # Last save directory
        self.last_save_directory = None

        # Load the YAML file
        self.load_yaml_from_name(yaml_filename=default_config_filename)

        # Initialize the root tkinter widget (window housing GUI)
        self.root = tk.Tk()
        # Create the main application GUI
        self.view = ScopeApplicationView(main_window=self.root, application=self)

        # Bind the buttons
        self.view.control_panel.start_button.bind("<Button>", self.start_continuous_sampling)
        self.view.control_panel.pause_button.bind("<Button>", self.stop_sampling)
        self.view.control_panel.reset_button.bind("<Button>", self.reset_data)
        #self.view.control_panel.save_button.bind("<Button>", self.save_scan)

    def run(self) -> None:
        '''
        This function launches the application including the GUI
        '''
        # Set the title of the app window
        self.root.title("qdlscope")
        # Display the window (not in task bar)
        self.root.deiconify()
        # Launch the main loop
        self.root.mainloop()

    def enable_buttons(self):
        pass

    def disable_buttons(self):
        pass

    def start_continuous_sampling(self, tkinter_event: tk.Event = None):
        
        logger.info('Starting continuous sampling.')

        # Disable the buttons
        self.disable_buttons()

        # Get the data
        self._get_daq_config()

        # Launch the thread
        self.scan_thread = Thread(target=self.sample_continuous_thread_function)
        self.scan_thread.start()


    def sample_continuous_thread_function(self) -> None:
        #try:
        logger.info('Starting continuous sampling thread.')

        current_time =time.time()
        past_time = time.time()
        for sample in self.application_controller.read_counts_continuous(
                            sample_time = self.daq_parameters['sample_time'], 
                            get_rate = self.daq_parameters['get_rate']):
            
            current_time = time.time()
            print(current_time - past_time)

            # Save the data
            self.data_y.append(sample)

            #print(self.data_y)

            # Update the viewport
            self.view.update_figure()

            past_time = time.time()

            

        # Get the x data vector
        self.data_x = np.arange(len(self.data_y)) * self.daq_parameters['sample_time']

        logger.info('Sampling complete.')
        try:
            pass
        except Exception as e:
            logger.info(e)
        # Enable the buttons
        self.enable_buttons()


    def stop_sampling(self, tkinter_event: tk.Event = None):

        logger.info('Stopping sampling.')

        # Set the running flag to false to stop after the next sample
        self.application_controller.running = False


    def reset_data(self, tkinter_event: tk.Event = None):

        logger.info('Resetting data.')

        # Reset the data variables
        self.data_x = None
        self.data_y = []


    def configure_from_yaml(self, afile: str) -> None:
        '''
        This method loads a YAML file to configure the qdlmove hardware
        based on yaml file indicated by argument `afile`.

        This method instantiates and configures the counters and application
        controller.

        Parameters
        ----------
        afile: str
            Full-path filename of the YAML config file.
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

        # Get the counter, instantiate, and configure
        import_path = config[APPLICATION_NAME][counter_name]['import_path']
        class_name = config[APPLICATION_NAME][counter_name]['class_name']
        module = importlib.import_module(import_path)
        logger.debug(f"Importing {import_path}")
        constructor = getattr(module, class_name)
        counter = constructor()
        counter.configure(config[APPLICATION_NAME][counter_name]['configure'])

        # Get the application controller constructor 
        import_path = config[APPLICATION_NAME]['ApplicationController']['import_path']
        class_name = config[APPLICATION_NAME]['ApplicationController']['class_name']
        module = importlib.import_module(import_path)
        logger.debug(f"Importing {import_path}")
        constructor = getattr(module, class_name)

        # Create the application controller passing the hardware as kwargs.
        self.application_controller = constructor(
            **{'counter_controller': counter}
        )

    def load_yaml_from_name(self, yaml_filename: str) -> None:
        '''
        Loads the yaml configuration file from name.

        Should be called during instantiation of this class and should be the callback
        function for loading of other standard yaml files while running.

        Parameters
        ----------
        yaml_filename: str
            Filename of the .yaml file in the qdlscan/config_files path.
        '''
        yaml_path = importlib.resources.files(CONFIG_PATH).joinpath(yaml_filename)
        self.configure_from_yaml(str(yaml_path))


    def _get_daq_config(self) -> None:
        '''
        Gets the position parameters in the GUI and validates if they are allowable. 
        Then saves the GUI input to the launcher application if valid.
        '''

        sample_time = float(self.view.control_panel.sample_time_entry.get())
        get_rate = not(bool(self.view.control_panel.raw_counts_toggle.get()))
        
        # Check if the sample time is too long or too short
        if (sample_time < 0.001) or (sample_time > 60):
            raise ValueError(f'Requested sample time {sample_time} is out of bounds (< 1 ms or > 60 s).')

        # Write to data memory
        self.daq_parameters = {
            'sample_time': sample_time,
            'get_rate': get_rate,
        }





def main():
    tkapp = ScopeApplication(DEFAULT_CONFIG_FILE)
    tkapp.run()


if __name__ == '__main__':
    main()
