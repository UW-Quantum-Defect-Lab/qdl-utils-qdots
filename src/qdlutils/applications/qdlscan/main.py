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
from qdlutils.applications.qdlscan.application_controller import ScanController
from qdlutils.applications.qdlscan.application_gui import (
    LauncherApplicationView,
    LineScanApplicationView,
    ImageScanApplicationView
)

logger = logging.getLogger(__name__)
logging.basicConfig()


CONFIG_PATH = 'qdlutils.applications.qdlscan.config_files'
DEFAULT_CONFIG_FILE = 'qdlscan_base.yaml'

# Dictionary for converting axis to an index
AXIS_INDEX = {'x': 0, 'y': 1, 'z': 2}

# Default color map
DEFAULT_COLOR_MAP = 'gray'


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
        self.max_x_range = None
        self.max_y_range = None
        self.max_z_range = None

        # Number of scan windows launched
        self.number_scans = 0
        # Most recent scan -- maybe not needed?
        self.current_scan = None
        # Dictionary of scan parameters (from control gui)
        self.scan_parameters = None
        # Dictionary of daq parameters (from control gui)
        self.daq_parameters = None

        # Last save directory
        self.last_save_directory = None

        # Load the YAML file based off of `controller_name`
        self.load_yaml_from_name(yaml_filename=default_config_filename)

        # Initialize the root tkinter widget (window housing GUI)
        self.root = tk.Tk()
        # Create the main application GUI
        self.view = LauncherApplicationView(main_window=self.root)

        # Bind the buttons
        self.view.control_panel.image_start_button.bind("<Button>", self.start_image_scan)
        self.view.control_panel.line_start_x_button.bind("<Button>", self.optimize_x_axis)
        self.view.control_panel.line_start_y_button.bind("<Button>", self.optimize_y_axis)
        self.view.control_panel.line_start_z_button.bind("<Button>", self.optimize_z_axis)
        self.view.control_panel.x_axis_set_button.bind("<Button>", self.set_x_axis)
        self.view.control_panel.y_axis_set_button.bind("<Button>", self.set_y_axis)
        self.view.control_panel.z_axis_set_button.bind("<Button>", self.set_z_axis)
        self.view.control_panel.get_position_button.bind("<Button>", self.get_coordinates)

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
        self.max_x_range = self.max_x_position - self.min_x_position

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
        self.max_y_range = self.max_y_position - self.min_y_position

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
        self.max_z_range = self.max_x_position - self.min_x_position

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
        if self.application_controller.busy:
            logger.error(f'Application controller is current busy.')
            return None
        logger.info('Optimizing X axis.')
        # Update the parameters
        try:
            self._get_scan_config()
        except Exception as e:
            logger.error(f'Scan parameters are invalid: {e}')
            return None
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
            id = str(self.number_scans).zfill(3)
        )

    def optimize_y_axis(self, tkinter_event=None):
        if self.application_controller.busy:
            logger.error(f'Application controller is current busy.')
            return None
        logger.info('Optimizing Y axis.')
        # Update the parameters
        try:
            self._get_scan_config()
        except Exception as e:
            logger.error(f'Scan parameters are invalid: {e}')
            return None
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
            id = str(self.number_scans).zfill(3)
        )

    def optimize_z_axis(self, tkinter_event=None):
        if self.application_controller.busy:
            logger.error(f'Application controller is current busy.')
            return None
        logger.info('Optimizing Z axis.')
        # Update the parameters
        try:
            self._get_scan_config()
        except Exception as e:
            logger.error(f'Scan parameters are invalid: {e}')
            return None
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
            id = str(self.number_scans).zfill(3)
        )

    def start_image_scan(self, tkinter_event=None):
        if self.application_controller.busy:
            logger.error(f'Application controller is current busy.')
            return None
        logger.info('Starting confocal image scan.')
        # Update the parameters
        try:
            self._get_scan_config()
        except Exception as e:
            logger.error(f'Scan parameters are invalid: {e}')
            return None
        # Increase the nunmber of scans launched
        self.number_scans += 1
        # Launch a image scan application
        self.current_scan = ImageScanApplication(
            parent_application = self,
            application_controller = self.application_controller,
            axis_1 = 'x',
            axis_2 = 'y',
            range = self.scan_parameters['image_range'],
            n_pixels = self.scan_parameters['image_pixels'],
            time = self.scan_parameters['image_time'],
            id = str(self.number_scans).zfill(3)
        )
    
    def set_x_axis(self, tkinter_event=None):
        try:
            self._get_daq_config()
            position = self.daq_parameters['x_position']
            self.application_controller.set_axis(axis='x', position=position)
            logger.info(f'Set x axis to {position}')
        except Exception as e:
            logger.error(f'Error with setting x axis: {e}')

    def set_y_axis(self, tkinter_event=None):
        try:
            self._get_daq_config()
            position = self.daq_parameters['y_position']
            self.application_controller.set_axis(axis='y', position=position)
            logger.info(f'Set y axis to {position}')
        except Exception as e:
            logger.error(f'Error with setting y axis: {e}')
        
    def set_z_axis(self, tkinter_event=None):
        try:
            self._get_daq_config()
            position = self.daq_parameters['z_position']
            self.application_controller.set_axis(axis='z', position=position)
            logger.info(f'Set z axis to {position}')
        except Exception as e:
            logger.error(f'Error with setting z axis: {e}')
        
    def get_coordinates(self, tkinter_event=None):
        
        x,y,z = self.application_controller.get_position()
        self.view.control_panel.x_axis_set_entry.delete(0, 'end')
        self.view.control_panel.y_axis_set_entry.delete(0, 'end')
        self.view.control_panel.z_axis_set_entry.delete(0, 'end')
        self.view.control_panel.x_axis_set_entry.insert(0, x)
        self.view.control_panel.y_axis_set_entry.insert(0, y)
        self.view.control_panel.z_axis_set_entry.insert(0, z)

    def _get_scan_config(self) -> dict:
        '''
        Get the values in the GUI validate if they are allowable
        '''
        image_range = float(self.view.control_panel.image_range_entry.get())
        image_pixels = int(self.view.control_panel.image_pixels_entry.get())
        image_time = float(self.view.control_panel.image_time_entry.get())
        line_range_xy = float(self.view.control_panel.line_range_xy_entry.get())
        line_range_z = float(self.view.control_panel.line_range_z_entry.get())
        line_pixels = int(self.view.control_panel.line_pixels_entry.get())
        line_time = float(self.view.control_panel.line_time_entry.get())

        # Check image range
        if image_range < 0.1:
            raise ValueError(f'Requested scan range {image_range} < 100 nm is too small.')
        if image_range > self.max_x_range:
            raise ValueError(f'Requested image scan range {image_range}'
                             +f' exceeds the x limit {self.max_x_range}.')
        if image_range > self.max_y_range:
            raise ValueError(f'Requested image scan range {image_range}'
                             +f' exceeds the y limit {self.max_x_range}.')
        if image_range > self.max_z_range:
            raise ValueError(f'Requested image scan range {image_range}'
                             +f' exceeds the z limit {self.max_x_range}.')
        # Check the image pixels
        if image_pixels < 1:
            raise ValueError(f'Requested image pixels {image_pixels} < 1 is too small.')
        # check the image time
        if image_time < 0.001:
            raise ValueError(f'Requested image scan time {image_time} < 1 ms is too small.')

        # Check the line xy range
        if line_range_xy < 0.1:
            raise ValueError(f'Requested scan range {line_range_xy} < 100 nm is too small.')
        if line_range_xy > self.max_x_range:
            raise ValueError(f'Requested xy scan range {line_range_xy}'
                             +f' exceeds the x limit {self.max_x_range}.')
        if line_range_xy > self.max_y_range:
            raise ValueError(f'Requested xy scan range {line_range_xy}'
                             +f' exceeds the y limit {self.max_y_range}.')
        # check the line z range
        if line_range_z < 0.1:
            raise ValueError(f'Requested scan range {line_range_z} < 100 nm is too small.')
        if line_range_z > self.max_z_range:
            raise ValueError(f'Requested z scan range {line_range_z}'
                             +f' exceeds the z limit {self.max_z_range}.')
        # Check the line pixels
        if line_pixels < 1:
            raise ValueError(f'Requested line pixels {line_pixels} < 1 is too small.')
        # check the line time
        if line_time < 0.001:
            raise ValueError(f'Requested line scan time {line_time} < 1 ms is too small.')
        if line_time > 300:
            raise ValueError(f'Requested line scan time {line_time} > 5 min is too long.')

        # Write to application memory
        self.scan_parameters = {
            'image_range': image_range,
            'image_pixels': image_pixels,
            'image_time': image_time,
            'line_range_xy': line_range_xy,
            'line_range_z': line_range_z,
            'line_pixels': line_pixels,
            'line_time': line_time,
        }

    def _get_daq_config(self):

        x_position = float(self.view.control_panel.x_axis_set_entry.get())
        y_position = float(self.view.control_panel.y_axis_set_entry.get())
        z_position = float(self.view.control_panel.z_axis_set_entry.get())

        if (x_position < self.min_x_position) or (x_position > self.max_x_position):
            raise ValueError(f'Requested x coordinate {x_position} is out of bounds.')
        if (y_position < self.min_y_position) or (y_position > self.max_y_position):
            raise ValueError(f'Requested y coordinate {y_position} is out of bounds.')
        if (z_position < self.min_z_position) or (z_position > self.max_z_position):
            raise ValueError(f'Requested z coordinate {z_position} is out of bounds.')

        # Write to application memory
        self.daq_parameters = {
            'x_position': x_position,
            'y_position': y_position,
            'z_position': z_position
        }


class LineScanApplication:
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
        self.start_position_vector = application_controller.get_position()
        self.start_position_axis = self.start_position_vector[AXIS_INDEX[axis]]
        self.final_position_axis = None
        # Get the limits of the scan
        self.min_position = self.start_position_axis - (range/2)
        self.max_position = self.start_position_axis + (range/2)
        # Check if the limits exceed the range and shift range to edge
        if self.min_position < min_allowed_position:
            # Too close to minimum edge, need to shift up
            logger.warning('Start position too close to edge, shifting.')
            shift = min_allowed_position - self.min_position
            self.min_position += shift
            self.max_position += shift
            #self.start_position_axis += shift
        if self.max_position > max_allowed_position:
            # Too close to minimum edge, need to shift up
            logger.warning('Start position too close to edge, shifting.')
            shift = max_allowed_position - self.max_position
            self.min_position += shift
            self.max_position += shift
            #self.start_position_axis += shift
        # Get the scan positions (along whatever axis is being scanned)
        # We're brute forcing it here as the application controller might not sample
        # positions in the exact same way...
        self.data_x = np.linspace(start=self.min_position, 
                                  stop=self.max_position, 
                                  num=n_pixels)
        # To hold scan results
        self.data_y = np.empty(shape=n_pixels)
        self.data_y[:] = np.nan

        # Launch the line scan GUI
        # Then initialize the GUI
        self.root = tk.Toplevel()
        self.root.title(f'Scan {id} ({self.timestamp.strftime("%Y-%m-%d %H:%M:%S")})')
        self.view = LineScanApplicationView(window=self.root, 
                                            application=self,
                                            settings_dict=parent_application.scan_parameters)

        # Bind the buttons
        self.view.control_panel.save_button.bind("<Button>", self.save_scan)


        # Launch the thread
        self.scan_thread = Thread(target=self.scan_thread_function)
        self.scan_thread.start()

    def scan_thread_function(self):
        try:
            logger.info('Starting scan thread.')
            logger.info(f'Starting scan on axis {self.axis}')
            # Run the scan (returns raw counts)
            self.data_y = self.application_controller.scan_axis(
                axis = self.axis,
                start = self.min_position,
                stop = self.max_position,
                n_pixels = self.n_pixels,
                scan_time = self.time
            )
            # Normalize to counts per second
            self.data_y = self.data_y / self.time_per_pixel
            # Optimize the position
            self.optimize_position()
            # Update the viewport
            self.view.update_figure()

            logger.info('Scan complete.')
        except Exception as e:
            logger.info(e)
        # Enable the buttons
        self.parent_application.enable_buttons()

    def optimize_position(self):

        '''
        Here need to implement something to move the axes to optimize the signal
        '''

        # For now just set the final position to the start position
        self.final_position_axis = self.start_position_axis

        # Move to optmial position
        self.application_controller.set_axis(axis=self.axis, position=self.final_position_axis)

    def save_scan(self, tkinter_event=None):
        '''
        Method to save the data, you can add more logic later for other filetypes.
        The event input is to catch the tkinter event that is supplied but not used.
        '''
        allowed_formats = [('Image with dataset', '*.png'), ('Dataset', '*.hdf5')]

        # Default filename
        default_name = f'scan{self.id}_{self.timestamp.strftime("%Y%m%d")}'
            
        # Get the savefile name
        afile = tk.filedialog.asksaveasfilename(filetypes=allowed_formats, 
                                                initialfile=default_name+'.png',
                                                initialdir = self.parent_application.last_save_directory)
        # Handle if file was not chosen
        if afile is None or afile == '':
            logger.warning('File not saved!')
            return # selection was canceled.

        # Get the path
        file_path = '/'.join(afile.split('/')[:-1])  + '/'
        self.parent_application.last_save_directory = file_path # Save the last used file path
        logger.info(f'Saving files to directory: {file_path}')
        # Get the name with extension (will be overwritten)
        file_name = afile.split('/')[-1]
        # Get the filetype
        file_type = file_name.split('.')[-1]
        # Get the filename without extension
        file_name = '.'.join(file_name.split('.')[:-1]) # Gets everything but the extension

        # If the file type is .png, want to save image and hdf5
        if file_type == 'png':
            logger.info(f'Saving the PNG as {file_name}.png')
            fig = self.view.data_viewport.fig
            fig.savefig(file_path+file_name+'.png', dpi=300, bbox_inches=None, pad_inches=0)

        # Save as hdf5
        with h5py.File(file_path+file_name+'.hdf5', 'w') as df:
            
            logger.info(f'Saving the HDF5 as {file_name}.hdf5')
            
            # Save the file metadata
            ds = df.create_dataset('file_metadata', 
                                   data=np.array(['application', 
                                                  'qdlutils_version', 
                                                  'scan_id', 
                                                  'timestamp', 
                                                  'original_name'], dtype='S'))
            ds.attrs['application'] = 'qdlutils.qdlscan.LineScanApplication'
            ds.attrs['qdlutils_version'] = qdlutils.__version__
            ds.attrs['scan_id'] = self.id
            ds.attrs['timestamp'] = self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            ds.attrs['original_name'] = file_name

            # Save the scan settings
            # If your implementation settings vary you should change the attrs
            ds = df.create_dataset('scan_settings/axis', data=self.axis)
            ds.attrs['units'] = 'None'
            ds.attrs['description'] = 'Axis of the scan.'
            ds = df.create_dataset('scan_settings/range', data=self.range)
            ds.attrs['units'] = 'Micrometers'
            ds.attrs['description'] = 'Length of the scan.'
            ds = df.create_dataset('scan_settings/n_pixels', data=self.n_pixels)
            ds.attrs['units'] = 'None'
            ds.attrs['description'] = 'Number of pixels in the scan.'
            ds = df.create_dataset('scan_settings/time', data=self.time)
            ds.attrs['units'] = 'Seconds'
            ds.attrs['description'] = 'Length of time for the scan.'
            ds = df.create_dataset('scan_settings/time_per_pixel', data=self.time_per_pixel)
            ds.attrs['units'] = 'Seconds'
            ds.attrs['description'] = 'Time integrated per pixel.'

            ds = df.create_dataset('scan_settings/start_position_vector', data=self.start_position_vector)
            ds.attrs['units'] = 'Micrometers'
            ds.attrs['description'] = 'Intial position of the scan.'
            ds = df.create_dataset('scan_settings/start_position_axis', data=self.start_position_axis)
            ds.attrs['units'] = 'Micrometers'
            ds.attrs['description'] = 'Initial position on the scan axis.'
            ds = df.create_dataset('scan_settings/final_position_axis', data=self.final_position_axis)
            ds.attrs['units'] = 'Micrometers'
            ds.attrs['description'] = 'Final position on the scan axis.'
            ds = df.create_dataset('scan_settings/min_position', data=self.min_position)
            ds.attrs['units'] = 'Micrometers'
            ds.attrs['description'] = 'Minimum axis position of the scan.'
            ds = df.create_dataset('scan_settings/max_position', data=self.max_position)
            ds.attrs['units'] = 'Micrometers'
            ds.attrs['description'] = 'Maximum axis position of the scan.'

            # Data
            ds = df.create_dataset('data/positions', data=self.data_x)
            ds.attrs['units'] = 'Micrometers'
            ds.attrs['description'] = 'Positions of the scan (along axis).'
            ds = df.create_dataset('data/count_rates', data=self.data_y)
            ds.attrs['units'] = 'Counts per second'
            ds.attrs['description'] = 'Count rates measured over scan.'
            ds = df.create_dataset('data/counts', data=(self.data_y*self.time_per_pixel).astype(int))
            ds.attrs['units'] = 'Counts'
            ds.attrs['description'] = 'Counts measured over scan.'




class ImageScanApplication():
    '''
    This is the image scan application class for `qdlscan` which manages the actual
    application controllers and GUI output of a single scan. It is meant to handle 
    2-d confocal scans.
    '''

    def __init__(self,
                 parent_application: LauncherApplication,
                 application_controller: ScanController,
                 axis_1: str,
                 axis_2: str,
                 range: float,
                 n_pixels: int,
                 time: float,
                 id: str):
        
        
        self.parent_application = parent_application
        self.application_controller = application_controller
        self.axis_1 = axis_1
        self.axis_2 = axis_2
        self.range = range
        self.n_pixels = n_pixels
        self.time = time

        # Time per pixel
        self.time_per_pixel = time / n_pixels

        # Cmap for plotting
        self.cmap = DEFAULT_COLOR_MAP

        self.id = id
        self.timestamp = datetime.datetime.now()

        # Get the limits of the position for the axis
        if axis_1 == 'x':
            min_allowed_position_1 = self.parent_application.min_x_position
            max_allowed_position_1 = self.parent_application.max_x_position
        elif axis_1 == 'y':
            min_allowed_position_1 = self.parent_application.min_y_position
            max_allowed_position_1 = self.parent_application.max_y_position
        elif axis_1 == 'z':
            min_allowed_position_1 = self.parent_application.min_z_position
            max_allowed_position_1 = self.parent_application.max_z_position
        else:
            raise ValueError(f'Requested axis_1 {axis_1} is invalid.')
        if axis_2 == 'x':
            min_allowed_position_2 = self.parent_application.min_x_position
            max_allowed_position_2 = self.parent_application.max_x_position
        elif axis_2 == 'y':
            min_allowed_position_2 = self.parent_application.min_y_position
            max_allowed_position_2 = self.parent_application.max_y_position
        elif axis_2 == 'z':
            min_allowed_position_2 = self.parent_application.min_z_position
            max_allowed_position_2 = self.parent_application.max_z_position
        else:
            raise ValueError(f'Requested axis_2 {axis_2} is invalid.')

        # Get the starting position
        self.start_position_vector = application_controller.get_position()
        self.start_position_axis_1 = self.start_position_vector[AXIS_INDEX[axis_1]]
        self.start_position_axis_2 = self.start_position_vector[AXIS_INDEX[axis_2]]

        # Get the limits of the scan on axis 1
        self.min_position_1 = self.start_position_axis_1 - (range/2)
        self.max_position_1 = self.start_position_axis_1 + (range/2)
        # Check if the limits exceed the range and shift range to edge
        if self.min_position_1 < min_allowed_position_1:
            # Too close to minimum edge, need to shift up
            shift = min_allowed_position_1 - self.min_position_1
            self.min_position_1 += shift
            self.max_position_1 += shift
            self.start_position_axis_1 += shift
        if self.max_position_1 > max_allowed_position_1:
            # Too close to minimum edge, need to shift up
            shift = max_allowed_position_1 - self.max_position_1
            self.min_position_1 += shift
            self.max_position_1 += shift
            self.start_position_axis_1 += shift
        # Get the limits of the scan on axis 2
        self.min_position_2 = self.start_position_axis_2 - (range/2)
        self.max_position_2 = self.start_position_axis_2 + (range/2)
        # Check if the limits exceed the range and shift range to edge
        if self.min_position_2 < min_allowed_position_2:
            # Too close to minimum edge, need to shift up
            shift = min_allowed_position_2 - self.min_position_2
            self.min_position_2 += shift
            self.max_position_2 += shift
            self.start_position_axis_2 += shift
        if self.max_position_2 > max_allowed_position_2:
            # Too close to minimum edge, need to shift up
            shift = max_allowed_position_2 - self.max_position_2
            self.min_position_2 += shift
            self.max_position_2 += shift
            self.start_position_axis_2 += shift

        # Get the scan positions
        self.data_x = np.linspace(start=self.min_position_1, 
                                  stop=self.max_position_1, 
                                  num=n_pixels)
        self.data_y = np.linspace(start=self.min_position_2, 
                                  stop=self.max_position_2, 
                                  num=n_pixels)
        # To hold scan results
        self.data_z = np.empty(shape=(n_pixels, n_pixels))
        self.data_z[:,:] = np.nan

        # Launch the line scan GUI
        # Then initialize the GUI
        self.root = tk.Toplevel()
        self.root.title(f'Scan {id} ({self.timestamp.strftime("%Y-%m-%d %H:%M:%S")})')
        self.view = ImageScanApplicationView(window=self.root, 
                                            application=self,
                                            settings_dict=parent_application.scan_parameters)
        
        # Bind the buttons
        self.view.control_panel.pause_button.bind("<Button>", self.pause_scan)
        self.view.control_panel.continue_button.bind("<Button>", self.continue_scan)
        self.view.control_panel.save_button.bind("<Button>", self.save_scan)

        # Launch the thread
        self.scan_thread = Thread(target=self.start_scan_thread_function)
        self.scan_thread.start()

    def continue_scan(self, tkinter_event=None):
        # Don't do anything if busy
        if self.application_controller.busy:
            logger.error('Controller is busy; cannot continue scan.')
        if self.current_scan_index == self.n_pixels:
            logger.error('Scan already completed.')
            return None
        # Start the scan thread to continue
        self.scan_thread = Thread(target=self.continue_scan_thread_function)
        self.scan_thread.start()
    
    def pause_scan(self, tkinter_event=None):
        '''
        Tell the scanner to pause scanning
        '''
        if self.application_controller.stop_scan is True:
            logger.info('Already waiting to pause.')
            return None
        if self.current_scan_index == self.n_pixels:
            logger.error('Scan already completed.')
            return None

        if self.application_controller.busy:
            logger.info('Pausing the scan...')
            # Query the controller to stop
            self.application_controller.stop_scan = True

    def save_scan(self, tkinter_event=None):
        '''
        Method to save the data, you can add more logic later for other filetypes.
        The event input is to catch the tkinter event that is supplied but not used.
        '''
        allowed_formats = [('Image with dataset', '*.png'), ('Dataset', '*.hdf5')]

        # Default filename
        default_name = f'scan{self.id}_{self.timestamp.strftime("%Y%m%d")}'
            
        # Get the savefile name
        afile = tk.filedialog.asksaveasfilename(filetypes=allowed_formats, 
                                                initialfile=default_name+'.png',
                                                initialdir = self.parent_application.last_save_directory)
        # Handle if file was not chosen
        if afile is None or afile == '':
            logger.warning('File not saved!')
            return # selection was canceled.

        # Get the path
        file_path = '/'.join(afile.split('/')[:-1])  + '/'
        self.parent_application.last_save_directory = file_path # Save the last used file path
        logger.info(f'Saving files to directory: {file_path}')
        # Get the name with extension (will be overwritten)
        file_name = afile.split('/')[-1]
        # Get the filetype
        file_type = file_name.split('.')[-1]
        # Get the filename without extension
        file_name = '.'.join(file_name.split('.')[:-1]) # Gets everything but the extension

        # If the file type is .png, want to save image and hdf5
        if file_type == 'png':
            logger.info(f'Saving the PNG as {file_name}.png')
            fig = self.view.data_viewport.fig
            fig.savefig(file_path+file_name+'.png', dpi=300, bbox_inches=None, pad_inches=0)

        # Save as hdf5
        with h5py.File(file_path+file_name+'.hdf5', 'w') as df:
            
            logger.info(f'Saving the HDF5 as {file_name}.hdf5')
            
            # Save the file metadata
            ds = df.create_dataset('file_metadata', 
                                   data=np.array(['application', 
                                                  'qdlutils_version', 
                                                  'scan_id', 
                                                  'timestamp', 
                                                  'original_name'], dtype='S'))
            ds.attrs['application'] = 'qdlutils.qdlscan.ImageScanApplication'
            ds.attrs['qdlutils_version'] = qdlutils.__version__
            ds.attrs['scan_id'] = self.id
            ds.attrs['timestamp'] = self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            ds.attrs['original_name'] = file_name

            # Save the scan settings
            # If your implementation settings vary you should change the attrs
            ds = df.create_dataset('scan_settings/axis_1', data=self.axis_1)
            ds.attrs['units'] = 'None'
            ds.attrs['description'] = 'First axis of the scan (which is scanned quickly).'
            ds = df.create_dataset('scan_settings/axis_2', data=self.axis_2)
            ds.attrs['units'] = 'None'
            ds.attrs['description'] = 'Second axis of the scan (which is scanned slowly).'
            ds = df.create_dataset('scan_settings/range', data=self.range)
            ds.attrs['units'] = 'Micrometers'
            ds.attrs['description'] = 'Length of the scan.'
            ds = df.create_dataset('scan_settings/n_pixels', data=self.n_pixels)
            ds.attrs['units'] = 'None'
            ds.attrs['description'] = 'Number of pixels in the scan.'
            ds = df.create_dataset('scan_settings/time', data=self.time)
            ds.attrs['units'] = 'Seconds'
            ds.attrs['description'] = 'Length of time for the scan along axis 1.'
            ds = df.create_dataset('scan_settings/time_per_pixel', data=self.time_per_pixel)
            ds.attrs['units'] = 'Seconds'
            ds.attrs['description'] = 'Time integrated per pixel.'

            ds = df.create_dataset('scan_settings/start_position_vector', data=self.start_position_vector)
            ds.attrs['units'] = 'Micrometers'
            ds.attrs['description'] = 'Intial position of the scan.'
            ds = df.create_dataset('scan_settings/start_position_axis_1', data=self.start_position_axis_1)
            ds.attrs['units'] = 'Micrometers'
            ds.attrs['description'] = 'Initial position on the scan axis 1.'
            ds = df.create_dataset('scan_settings/start_position_axis_2', data=self.start_position_axis_2)
            ds.attrs['units'] = 'Micrometers'
            ds.attrs['description'] = 'Initial position on the scan axis 2.'
            ds = df.create_dataset('scan_settings/min_position_1', data=self.min_position_1)
            ds.attrs['units'] = 'Micrometers'
            ds.attrs['description'] = 'Minimum axis 1 position of the scan.'
            ds = df.create_dataset('scan_settings/min_position_2', data=self.min_position_2)
            ds.attrs['units'] = 'Micrometers'
            ds.attrs['description'] = 'Minimum axis 2 position of the scan.'
            ds = df.create_dataset('scan_settings/max_position_1', data=self.max_position_1)
            ds.attrs['units'] = 'Micrometers'
            ds.attrs['description'] = 'Maximum axis 1 position of the scan.'
            ds = df.create_dataset('scan_settings/max_position_2', data=self.max_position_2)
            ds.attrs['units'] = 'Micrometers'
            ds.attrs['description'] = 'Maximum axis 2 position of the scan.'

            # Data
            ds = df.create_dataset('data/positions_axis_1', data=self.data_x)
            ds.attrs['units'] = 'Micrometers'
            ds.attrs['description'] = 'Positions of the scan (along axis 1).'
            ds = df.create_dataset('data/positions_axis_2', data=self.data_y)
            ds.attrs['units'] = 'Micrometers'
            ds.attrs['description'] = 'Positions of the scan (along axis 2).'
            ds = df.create_dataset('data/count_rates', data=self.data_z)
            ds.attrs['units'] = 'Counts per second'
            ds.attrs['description'] = 'Count rates measured over 2-d scan.'
            ds = df.create_dataset('data/counts', data=(self.data_z*self.time_per_pixel).astype(int))
            ds.attrs['units'] = 'Counts'
            ds.attrs['description'] = 'Counts measured over 2-d scan.'

    def start_scan_thread_function(self):
        '''
        This is the thread scan function for starting a scan
        '''
        try:
            self.current_scan_index = 0
            for line in self.application_controller.scan_image(
                            axis_1=self.axis_1,
                            start_1=self.min_position_1,
                            stop_1=self.max_position_1,
                            n_pixels_1=self.n_pixels,
                            axis_2=self.axis_2,
                            start_2=self.min_position_2,
                            stop_2=self.max_position_2,
                            n_pixels_2=self.n_pixels,
                            scan_time=self.time):
                # Set the data to the recently calculated line (in counts/second)
                self.data_z[self.current_scan_index] = line / self.time_per_pixel
                # Update the figure
                self.view.update_figure()
                # Increase the current scan index
                self.current_scan_index += 1

                logger.debug('Row complete.')

            self.home_position()
            logger.info('Scan complete.')

        except Exception as e:
            logger.info(e)
        # Enable the buttons
        self.parent_application.enable_buttons()

    def continue_scan_thread_function(self):
        '''
        This is is the thread function to continue the scan from the middle.

        It would probably be the same as the start scan thread function if the 
        current_scan_index was set to begin with.
        '''
        try:
            for line in self.application_controller.scan_image(
                            axis_1=self.axis_1,
                            start_1=self.min_position_1,
                            stop_1=self.max_position_1,
                            n_pixels_1=self.n_pixels,
                            axis_2=self.axis_2,
                            start_2= self.data_y[self.current_scan_index], # Start at the index of the next queued scan
                            stop_2=self.max_position_2,
                            n_pixels_2=(self.n_pixels - self.current_scan_index), # Do the remaining pixels
                            scan_time=self.time):
                # Set the data to the recently calculated line (in counts/second)
                self.data_z[self.current_scan_index] = line / self.time_per_pixel
                # Update the figure
                self.view.update_figure()
                # Increase the current scan index
                self.current_scan_index += 1

                logger.debug('Row complete.')

            self.home_position()
            logger.info('Scan complete.')

        except Exception as e:
            logger.info(e)
        # Enable the buttons
        self.parent_application.enable_buttons()

    def home_position(self):

        '''
        Go to the center of the scan
        '''
        # Move to optmial position
        self.application_controller.set_axis(axis=self.axis_1, position=self.start_position_axis_1)
        # Move to optmial position
        self.application_controller.set_axis(axis=self.axis_2, position=self.start_position_axis_2)


def main():
    tkapp = LauncherApplication(DEFAULT_CONFIG_FILE)
    tkapp.run()


if __name__ == '__main__':
    main()
