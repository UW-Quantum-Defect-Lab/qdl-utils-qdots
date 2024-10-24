import importlib
import importlib.resources
import logging
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

import qdlutils
from qdlutils.hardware.nidaq.counters.nidaqedgecounter import QT3PleNIDAQEdgeCounterController

matplotlib.use('Agg')

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

CONFIG_PATH = 'qdlutils.applications.qdlple.config_files'
DEFAULT_CONFIG_FILE = 'qdlple_base.yaml'


class DataViewport:
    '''
    This class handles the GUI image of the PLE scan

    Currently it is hard coded for the standard image plot in a PLE scan.

    TODO: Handle internal logic for writing image vs. integrated data to the screen
    '''

    def __init__(self, mplcolormap='Blues') -> None:
        self.fig = plt.figure()
        self.ax = plt.gca()
        self.cbar = None
        self.cmap = mplcolormap
        self.cid = self.fig.canvas.mpl_connect('button_press_event', self.onclick)
        self.log_data = False


    def update_image_and_plot(self, model) -> None:
        '''
        Updates the ScanImage GUI element
        '''
        for ax in self.fig.axes:
            self.fig.delaxes(ax)
        num_readers = len(model.readers)
        grid = plt.GridSpec(1, num_readers)
        self.update_image(model, grid)

    def update_image(self, model, grid) -> None:
        '''
        Updates image data in the ScanImage GUI element
        '''
        # Quick fix to get it to run
        img_data = np.array([[]])

        # Look for the single DAQ reader and get the image data
        for reader in model.readers:
            if isinstance(model.readers[reader], QT3PleNIDAQEdgeCounterController):
                img_data = np.array([output[reader] for output in model.outputs])

        # Calculate the axis extent
        # Want to assign y axis values 0 -> 1 on the upscan, then 1 -> y_max on
        # the downscan. Because imshow scales all samples uniformly, we need
        # (y_max - 1) / 1 = n_pixels_down / n_pixels_up
        y_max = 1 + model.n_pixels_down / model.n_pixels_up

        # Plot the scan
        ax = self.fig.add_subplot()
        artist = ax.imshow(
                        img_data.T,
                        cmap=self.cmap, 
                        extent=[0.5,
                                img_data.shape[0]+0.5,
                                0,
                                y_max],
                        interpolation='none',
                        aspect='auto',
                        origin='lower')
        cbar = self.fig.colorbar(artist, ax=ax)

        # Set the xtick labels
        # We set up some logic to make it readable
        n_scans = img_data.shape[0]
        if n_scans < 11:
            # Set the xticks on integer values for 1-10
            ax.set_xticks( np.arange(1,n_scans+1,1) )
        else:
            # Set on every 5 if more than 10 scans long
            ax.set_xticks( np.arange(5,n_scans+1,5) )
        # Set the ytick labels
        y_ticks = ax.get_yticks()
        ax.set_yticks( y_ticks, self.calculate_ytick_labels(y_ticks, model.min, model.max, y_max) ) # Set the yticks to match scan
        # Reset the extent
        ax.set_ylim(0,y_max)
        # Set the labels
        ax.set_xlabel('Scan number', fontsize=14)
        ax.set_ylabel('Voltage (V)', fontsize=14)
        cbar.ax.set_ylabel('Counts/sec', fontsize=14, rotation=270, labelpad=15)
        # Set the grid
        ax.grid(alpha=0.3, axis='y', linewidth=1, color='k')#, dashes=(5,5))

    def calculate_ytick_labels(self, y, y_min, y_max, max_tick):
        '''
        Method to compute the ytick labels
        '''
        return np.round(np.where(y > 1, (y_min-y_max)*(y-max_tick)/(max_tick-1)+y_min, (y_max-y_min)*y+y_min), decimals=3)

    def update_plot(self, model, grid) -> None:
        '''
        Updates 2-d line plots, currently not in use.
        '''

        for ii, reader in enumerate(model.readers):
            y_data = model.outputs[model.current_frame-1][reader]
            x_control = model.scanned_control[model.current_frame-1]
            ax = self.fig.add_subplot(grid[1, ii])
            ax.plot(x_control, y_data, color='k', linewidth=1.5)

    def reset(self) -> None:
        self.ax.cla()

    def set_onclick_callback(self, f) -> None:
        self.onclick_callback = f

    def onclick(self, event) -> None:
        pass

class DataViewportControlPanel():
    '''
    GUI elements to control or modify the viewport and save scans.
    '''
    def __init__(self, root, scan_settings: dict) -> None:

        base_frame = tk.Frame(root)
        base_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=16, pady=16)

        # Define command frame for active buttons/control settings
        command_frame = tk.Frame(base_frame)
        command_frame.pack(side=tk.TOP, padx=20, pady=10)
        row = 0
        tk.Label(command_frame, text="PLE scan control", font='Helvetica 14').grid(row=row, column=0, pady=[0,10], columnspan=2)
        row += 1
        self.save_scan_button = tk.Button(command_frame, text="Save Scan", width=12)
        self.save_scan_button.grid(row=row, column=0, columnspan=2, padx=0)


        # Define settings frame to view scan settings
        settings_frame = tk.Frame(base_frame)
        settings_frame.pack(side=tk.TOP, padx=20, pady=10)
        row=0
        tk.Label(settings_frame, text="Scan settings", font='Helvetica 14').grid(row=row, column=0, pady=[0,10], columnspan=2)
        # Min voltage
        row += 1
        tk.Label(settings_frame, text="Min voltage (V)").grid(row=row, column=0)
        self.voltage_start_entry = tk.Entry(settings_frame, width=10)
        self.voltage_start_entry.insert(0, scan_settings['min'])
        self.voltage_start_entry.config(state='readonly')
        self.voltage_start_entry.grid(row=row, column=1)
        # Max voltage
        row += 1
        tk.Label(settings_frame, text="Max voltage (V)").grid(row=row, column=0)
        self.voltage_end_entry = tk.Entry(settings_frame, width=10)
        self.voltage_end_entry.insert(0, scan_settings['max'])
        self.voltage_end_entry.config(state='readonly')
        self.voltage_end_entry.grid(row=row, column=1)
        # Number of pixels on upsweep
        row += 1
        tk.Label(settings_frame, text="# of pixels up").grid(row=row, column=0)
        self.num_pixels_up_entry = tk.Entry(settings_frame, width=10)
        self.num_pixels_up_entry.insert(0, scan_settings['n_pixels_up'])
        self.num_pixels_up_entry.config(state='readonly')
        self.num_pixels_up_entry.grid(row=row, column=1)
        # Number of pixels on downsweep
        row += 1
        tk.Label(settings_frame, text="# of pixels down").grid(row=row, column=0)
        self.num_pixels_down_entry = tk.Entry(settings_frame, width=10)
        self.num_pixels_down_entry.insert(0, scan_settings['n_pixels_down'])
        self.num_pixels_down_entry.config(state='readonly')
        self.num_pixels_down_entry.grid(row=row, column=1)
        # Number of scans
        row += 1
        tk.Label(settings_frame, text="# of scans").grid(row=row, column=0)
        self.scan_num_entry = tk.Entry(settings_frame, width=10)
        self.scan_num_entry.insert(0, scan_settings['n_scans'])
        self.scan_num_entry.config(state='readonly')
        self.scan_num_entry.grid(row=row, column=1, padx=10)
        # Time for the upsweep min -> max
        row += 1
        tk.Label(settings_frame, text="Upsweep time (s)").grid(row=row, column=0)
        self.upsweep_time_entry = tk.Entry(settings_frame, width=10)
        self.upsweep_time_entry.insert(0, scan_settings['time_up'])
        self.upsweep_time_entry.config(state='readonly')
        self.upsweep_time_entry.grid(row=row, column=1)
        # Time for the downsweep max -> min
        row += 1
        tk.Label(settings_frame, text="Downsweep time (s)").grid(row=row, column=0)
        self.downsweep_time_entry = tk.Entry(settings_frame, width=10)
        self.downsweep_time_entry.insert(0, scan_settings['time_down'])
        self.downsweep_time_entry.config(state='readonly')
        self.downsweep_time_entry.grid(row=row, column=1, padx=10)
        # Adding advanced settings
        row += 1
        tk.Label(settings_frame, text="Advanced settings:", font='Helvetica 10').grid(row=row, column=0, pady=[8,0], columnspan=3)
        # Number of subpixels to sample (each pixel has this number of samples)
        # Note that excessively large values will slow the scan speed down due to
        # the voltage movement overhead.
        row += 1
        tk.Label(settings_frame, text="# of sub-pixels").grid(row=row, column=0)
        self.subpixel_entry = tk.Entry(settings_frame, width=10)
        self.subpixel_entry.insert(0, scan_settings['n_subpixels'])
        self.subpixel_entry.config(state='readonly')
        self.subpixel_entry.grid(row=row, column=1)
        # Button to enable repump at start of scan?
        row += 1
        tk.Label(settings_frame, text="Reump time (ms)").grid(row=row, column=0)
        self.repump_entry = tk.Entry(settings_frame, width=10)
        self.repump_entry.insert(0, scan_settings['time_repump'])
        self.repump_entry.config(state='readonly')
        self.repump_entry.grid(row=row, column=1)


class ControlPanel():
    '''
    This class handles the GUI for scan parameter configuration.
    '''

    def __init__(self, root, scan_range) -> None:

        # Define frame for the side panel
        # This encompasses the entire side pannel
        base_frame = tk.Frame(root.root)
        base_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=16, pady=16)

        # Define command frame for start/stop/save buttons
        command_frame = tk.Frame(base_frame)
        command_frame.pack(side=tk.TOP, padx=20, pady=10)
        # Add buttons and text
        row = 0
        tk.Label(command_frame, text="PLE scan control", font='Helvetica 14').grid(row=row, column=0, pady=[0,10], columnspan=2)
        row += 1
        self.start_button = tk.Button(command_frame, text="Start Scan", width=12)
        self.start_button.grid(row=row, column=0, columnspan=1, padx=3)
        self.stop_button = tk.Button(command_frame, text="Stop Scan", width=12)
        self.stop_button.grid(row=row, column=1, columnspan=1, padx=3)

        # Define settings frame to set all scan settings
        settings_frame = tk.Frame(base_frame)
        settings_frame.pack(side=tk.TOP, padx=20, pady=10)
        # Min voltage
        row += 1
        tk.Label(settings_frame, text="Min voltage (V)").grid(row=row, column=0)
        self.voltage_start_entry = tk.Entry(settings_frame, width=10)
        self.voltage_start_entry.insert(10, scan_range[0])
        self.voltage_start_entry.grid(row=row, column=1)
        # Max voltage
        row += 1
        tk.Label(settings_frame, text="Max voltage (V)").grid(row=row, column=0)
        self.voltage_end_entry = tk.Entry(settings_frame, width=10)
        self.voltage_end_entry.insert(10, scan_range[1])
        self.voltage_end_entry.grid(row=row, column=1)
        # Number of pixels on upsweep
        row += 1
        tk.Label(settings_frame, text="# of pixels up").grid(row=row, column=0)
        self.num_pixels_up_entry = tk.Entry(settings_frame, width=10)
        self.num_pixels_up_entry.insert(10, 150)
        self.num_pixels_up_entry.grid(row=row, column=1)
        # Number of pixels on downsweep
        row += 1
        tk.Label(settings_frame, text="# of pixels down").grid(row=row, column=0)
        self.num_pixels_down_entry = tk.Entry(settings_frame, width=10)
        self.num_pixels_down_entry.insert(10, 10)
        self.num_pixels_down_entry.grid(row=row, column=1)
        # Number of scans
        row += 1
        tk.Label(settings_frame, text="# of scans").grid(row=row, column=0)
        self.scan_num_entry = tk.Entry(settings_frame, width=10)
        self.scan_num_entry.insert(10, 10)
        self.scan_num_entry.grid(row=row, column=1, padx=10)
        # Time for the upsweep min -> max
        row += 1
        tk.Label(settings_frame, text="Upsweep time (s)").grid(row=row, column=0)
        self.upsweep_time_entry = tk.Entry(settings_frame, width=10)
        self.upsweep_time_entry.insert(10, 3)
        self.upsweep_time_entry.grid(row=row, column=1)
        # Time for the downsweep max -> min
        row += 1
        tk.Label(settings_frame, text="Downsweep time (s)").grid(row=row, column=0)
        self.downsweep_time_entry = tk.Entry(settings_frame, width=10)
        self.downsweep_time_entry.insert(10, 1)
        self.downsweep_time_entry.grid(row=row, column=1, padx=10)
        # Adding advanced settings
        row += 1
        tk.Label(settings_frame, text="Advanced settings:", font='Helvetica 10').grid(row=row, column=0, pady=[8,0], columnspan=3)
        # Number of subpixels to sample (each pixel has this number of samples)
        # Note that excessively large values will slow the scan speed down due to
        # the voltage movement overhead.
        row += 1
        tk.Label(settings_frame, text="# of sub-pixels").grid(row=row, column=0)
        self.subpixel_entry = tk.Entry(settings_frame, width=10)
        self.subpixel_entry.insert(10, 4)
        self.subpixel_entry.grid(row=row, column=1)
        # Button to enable repump at start of scan?
        row += 1
        tk.Label(settings_frame, text="Reump time (ms)").grid(row=row, column=0)
        self.repump_entry = tk.Entry(settings_frame, width=10)
        self.repump_entry.insert(10, 0)
        self.repump_entry.grid(row=row, column=1)


        # Define control frame to modify DAQ settings
        control_frame = tk.Frame(base_frame)
        control_frame.pack(side=tk.TOP, padx=20, pady=10)
        # Label
        row += 1
        tk.Label(control_frame, text="DAQ control", font='Helvetica 14').grid(row=row, column=0, pady=[0,5], columnspan=2)
        # Setter for the voltage
        row += 1
        self.goto_button = tk.Button(control_frame, text="Set voltage (V)", width=12)
        self.goto_button.grid(row=row, column=0)
        self.voltage_entry = tk.Entry(control_frame, width=10)
        self.voltage_entry.insert(10, 0)
        self.voltage_entry.grid(row=row, column=1, padx=10)
        # Getter for the voltage (based off of the latest set value)
        row += 1
        self.get_button = tk.Button(control_frame, text="Get voltage (V)", width=12)
        self.get_button.grid(row=row, column=0)
        self.voltage_show = tk.Entry(control_frame, width=10)
        self.voltage_show.insert(10, 0)
        self.voltage_show.grid(row=row, column=1)
        self.voltage_show.config(state='readonly') # Disable the voltage show
        # Getter for the voltage (based off of the latest set value)
        row += 1
        self.repump_laser_on = tk.IntVar()
        self.repump_laser_toggle_label = tk.Label(control_frame, text='Toggle repump laser')
        self.repump_laser_toggle_label.grid(row=row, column=0, pady=[5,0])
        self.repump_laser_toggle = tk.Checkbutton ( control_frame, var=self.repump_laser_on)
        self.repump_laser_toggle.grid(row=row, column=1, pady=[5,0])

        # Define config frame to set the config file
        config_frame = tk.Frame(base_frame)
        config_frame.pack(side=tk.TOP, padx=20, pady=10)
        tk.Label(config_frame, text="Hardware Configuration", font='Helvetica 14').grid(row=row, column=0, pady=[0,5], columnspan=1)
        # Dialouge button to pick the YAML config
        row += 1
        self.hardware_config_from_yaml_button = tk.Button(config_frame, text="Load YAML Config")
        self.hardware_config_from_yaml_button.grid(row=row, column=0, columnspan=1)


class ScanPopoutApplicationView():
    '''
    Scan popout application GUI view, loads DataViewport and SidePanel (new)
    '''
    def __init__(self, main_frame, scan_settings: dict) -> None:
        frame = tk.Frame(main_frame)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.data_viewport = DataViewport()
        self.control_panel = DataViewportControlPanel(main_frame, scan_settings=scan_settings)

        self.canvas = FigureCanvasTkAgg(self.data_viewport.fig, master=frame)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        toolbar = NavigationToolbar2Tk(self.canvas, frame)
        toolbar.update()
        self.canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.canvas.draw()

class ScanPopoutApplication():
    '''
    Scan popout application backend. Launches the GUI, houses the 
    application_controller, handles events for controlling the view port and
    saving data for a set of scans.
    '''
    def __init__(self, parent_application, application_controller, id: str = '') -> None:
        # Store the application controller and number identifier
        self.parent_application = parent_application
        self.application_controller = application_controller
        self.id = id
        self.timestamp = datetime.datetime.now()
        

        # First load meta/config data from the application controller
        self.min = application_controller.min
        self.max = application_controller.max
        self.n_pixels_up = application_controller.n_pixels_up
        self.n_pixels_down = application_controller.n_pixels_down
        self.n_subpixels = application_controller.n_subpixels
        self.time_up = application_controller.time_up
        self.time_down = application_controller.time_down
        self.n_scans = application_controller.n_scans
        self.time_repump = application_controller.time_repump
        self.pixel_step_size_up = application_controller.pixel_step_size_up
        self.pixel_step_size_down = application_controller.pixel_step_size_down
        self.sample_step_size_up = application_controller.sample_step_size_up
        self.sample_step_size_down = application_controller.sample_step_size_down
        self.pixel_voltages_up = application_controller.pixel_voltages_up
        self.pixel_voltages_down = application_controller.pixel_voltages_down
        self.sample_voltages_up = application_controller.sample_voltages_up
        self.sample_voltages_down = application_controller.sample_voltages_down
        self.pixel_time_up = application_controller.pixel_time_up
        self.pixel_time_down = application_controller.pixel_time_down
        self.sample_time_up = application_controller.sample_time_up
        self.sample_time_down = application_controller.sample_time_down

        # Then initialize the GUI
        self.root = tk.Toplevel()
        self.root.title(f'Scan {id} ({self.timestamp.strftime("%Y-%m-%d %H:%M:%S")})')
        self.view = ScanPopoutApplicationView(main_frame=self.root, scan_settings=self.__dict__)

        # Bind the buttons to callbacks
        self.view.control_panel.save_scan_button.bind("<Button>", self.save_data)

        # Set the behavior on clsing the window, launch main loop for window
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def save_data(self, event=None) -> None:
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
            ds.attrs['application'] = 'qdlutils.qt3ple'
            ds.attrs['qdlutils_version'] = qdlutils.__version__
            ds.attrs['scan_id'] = self.id
            ds.attrs['timestamp'] = self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            ds.attrs['original_name'] = file_name

            # Save the scan settings
            # If your implementation settings vary you should change the attrs
            ds = df.create_dataset('scan_settings/min', data=self.min)
            ds.attrs['units'] = 'Volts'
            ds.attrs['description'] = 'Minimum scan voltage'
            ds = df.create_dataset('scan_settings/max', data=self.max)
            ds.attrs['units'] = 'Volts'
            ds.attrs['description'] = 'Maximum scan voltage'
            # Pixel settings
            ds = df.create_dataset('scan_settings/n_pixels_up', data=self.n_pixels_up)
            ds.attrs['units'] = 'None'
            ds.attrs['description'] = 'Number of pixels on upsweep'
            ds = df.create_dataset('scan_settings/n_pixels_down', data=self.n_pixels_down)
            ds.attrs['units'] = 'None'
            ds.attrs['description'] = 'Number of pixels on downsweep'
            ds = df.create_dataset('scan_settings/n_subpixels', data=self.n_subpixels)
            ds.attrs['units'] = 'None'
            ds.attrs['description'] = 'Number of subpixel samples per pixel'
            ds = df.create_dataset('scan_settings/n_scans', data=self.n_scans)
            ds.attrs['units'] = 'None'
            ds.attrs['description'] = 'Number of scans requested'
            # Time settings
            ds = df.create_dataset('scan_settings/time_up', data=self.time_up)
            ds.attrs['units'] = 'Seconds'
            ds.attrs['description'] = 'Total time for upsweep'
            ds = df.create_dataset('scan_settings/time_down', data=self.time_down)
            ds.attrs['units'] = 'Seconds'
            ds.attrs['description'] = 'Total time for downsweep'
            ds = df.create_dataset('scan_settings/time_repump', data=self.time_repump)
            ds.attrs['units'] = 'Milliseconds'
            ds.attrs['description'] = 'Time for repump at start of scan'
            # Derived settings
            ds = df.create_dataset('scan_settings/pixel_step_size_up', data=self.pixel_step_size_up)
            ds.attrs['units'] = 'Volts'
            ds.attrs['description'] = 'Voltage step size between pixels on upsweep'
            ds = df.create_dataset('scan_settings/pixel_step_size_down', data=self.pixel_step_size_down)
            ds.attrs['units'] = 'Volts'
            ds.attrs['description'] = 'Voltage step size between pixels on downsweep'
            ds = df.create_dataset('scan_settings/sample_step_size_up', data=self.sample_step_size_up)
            ds.attrs['units'] = 'Volts'
            ds.attrs['description'] = 'Voltage step size between samples on upsweep'
            ds = df.create_dataset('scan_settings/sample_step_size_down', data=self.sample_step_size_down)
            ds.attrs['units'] = 'Volts'
            ds.attrs['description'] = 'Voltage step size between samples on downsweep'
            ds = df.create_dataset('scan_settings/pixel_time_up', data=self.pixel_time_up)
            ds.attrs['units'] = 'Seconds'
            ds.attrs['description'] = 'Total time per pixel on upsweep'
            ds = df.create_dataset('scan_settings/pixel_time_down', data=self.pixel_time_down)
            ds.attrs['units'] = 'Seconds'
            ds.attrs['description'] = 'Total time per pixel on downsweep'
            ds = df.create_dataset('scan_settings/sample_time_up', data=self.sample_time_up)
            ds.attrs['units'] = 'Seconds'
            ds.attrs['description'] = 'Integration time per sample on upsweep'
            ds = df.create_dataset('scan_settings/sample_time_down', data=self.sample_time_down)
            ds.attrs['units'] = 'Seconds'
            ds.attrs['description'] = 'Integration time per sample on downsweep'

            # Create the primary datasets
            ds = df.create_dataset('data/pixel_voltages_up', data=self.pixel_voltages_up)
            ds.attrs['units'] = 'Volts'
            ds.attrs['description'] = 'Voltage value at start of each pixel on upsweep'
            ds = df.create_dataset('data/pixel_voltages_down', data=self.pixel_voltages_down)
            ds.attrs['units'] = 'Volts'
            ds.attrs['description'] = 'Voltage value at start of each pixel on downsweep'
            ds = df.create_dataset('data/sample_voltages_up', data=self.sample_voltages_up)
            ds.attrs['units'] = 'Volts'
            ds.attrs['description'] = 'Voltage value at sample points on upsweep'
            ds = df.create_dataset('data/sample_voltages_down', data=self.sample_voltages_down)
            ds.attrs['units'] = 'Volts'
            ds.attrs['description'] = 'Voltage value at sample points on downsweep'

            # Get the full image data
            # Maybe can remove if we update image data at the popout window level?
            for reader in self.application_controller.readers:
                if isinstance(self.application_controller.readers[reader], QT3PleNIDAQEdgeCounterController):
                    img_data = np.array([output[reader] for output in self.application_controller.outputs])
            # Write the image data to file
            ds = df.create_dataset('data/scan_counts', data=img_data)
            ds.attrs['units'] = 'Counts/second'
            ds.attrs['description'] = ('2-d array of counts per second at each pixel of the completed scans.'
                                      +' Each row consists of one upscan and downscan pair, appended in order.'
                                      +' The scans are ordered from oldest to newest.')
            ds = df.create_dataset('data/upscan_counts', data=[scan[:self.n_pixels_up] for scan in img_data])
            ds.attrs['units'] = 'Counts/second'
            ds.attrs['description'] = '2-d array of counts per second at each pixel of the upscans only.'
            ds = df.create_dataset('data/downscan_counts', data=[scan[self.n_pixels_up:] for scan in img_data])
            ds.attrs['units'] = 'Counts/second'
            ds.attrs['description'] = '2-d array of counts per second at each pixel of the downscans only.'




    def on_closing(self) -> None:
        '''
        This function handles shutdown when window is closed.

        This should warn the user that the current scan window was closed and
        that one should check that the scan controller is not incorrectly in the
        running state.
        It then destroys the window.
        
        FYI: You shouldn't run self.root.quit() even on child processes because
        this actually kills the mainloop() instantiated in startup and closes the
        whole application outright.
        '''
        if self.application_controller.still_scanning():
            logger.warning('Scan window closed while active. Verify scanning has stopped.')
            self.parent_application.stop_scan()
        self.root.destroy()



class MainApplicationView():
    '''
    Main application GUI view, loads SidePanel and ScanImage
    '''
    def __init__(self, main_frame, scan_range=[0, 2]) -> None:
        frame = tk.Frame(main_frame.root)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.control_panel = ControlPanel(main_frame, scan_range)



class MainTkApplication():
    '''
    Main application backend, launches the GUI and handles events
    '''
    def __init__(self, default_config_filename) -> None:
        '''
        Initializes the application.
        Args:
            controller_name (str) : name of controller used to identify the YAML config
        '''

        # Define class attributes to store data aquisition and controllers
        self.wavelength_controller_model = None
        self.data_acquisition_models = {}
        self.auxiliary_control_models = {}
        self.application_controller_constructor = None
        self.scan_thread = None

        # List to keep track of child scan windows
        self.scan_windows = []
        self.current_scan = None
        self.number_scans_on_session = 0 # The number of scans performed
        self.last_save_directory = 'C:/Users/Fu Lab NV PC/Documents' # Modify this for your system

        # Load the YAML file based off of `controller_name`
        self.load_controller_from_name(yaml_filename=default_config_filename)

        # Initialize the root tkinter widget (window housing GUI)
        self.root = tk.Tk()
        # Create the main application GUI and specify the controller name
        self.view = MainApplicationView(self, 
                                        scan_range=[self.wavelength_controller_model.minimum_allowed_position, 
                                                    self.wavelength_controller_model.maximum_allowed_position])
        
        # Bind the GUI buttons to callback functions
        self.view.control_panel.start_button.bind("<Button>", self.start_scan)
        self.view.control_panel.stop_button.bind("<Button>", self.stop_scan)
        self.view.control_panel.goto_button.bind("<Button>", self.go_to)
        self.view.control_panel.get_button.bind("<Button>", self.update_voltage_show)
        self.view.control_panel.hardware_config_from_yaml_button.bind("<Button>", lambda e: self.configure_from_yaml())
        self.view.control_panel.repump_laser_toggle.config(command=self.toggle_repump_laser)

        # Turn off the repump laser at startup
        self.toggle_repump_laser(cmd=False)

        # Set protocol for shutdown when the root tkinter widget is closed
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def go_to(self, event=None) -> None:
        '''
        Callback function for voltage setter `self.view.control_panel.goto_button`

        This function is a wrapper for the `application_controller.go_to()` method
        which is itself a wrapper for the `wavelength_controller.got_to()` method.
        This structure is so that information at behavior and information can be
        handled at intermediate levels (for example, this function gets the input 
        from the GUI, the `application_controller` level handles out-of-range 
        exceptions and the lowest-level `wavelength_controller` opens a nidaq task
        to change the voltage on the hardware.)
        '''
        self.disable_buttons()
        self.wavelength_controller_model.go_to(float(self.view.control_panel.voltage_entry.get()))
        self.enable_buttons()

    def update_voltage_show(self, event=None) -> None:
        '''
        Callback to update the reading on the GUI voltage getter

        Obtains the last write value from the wavelength_controller level and
        then updates the result on the GUI.
        '''
        # Get the last write value from the wavelength controller
        read = self.wavelength_controller_model.last_write_value
        # Update the GUI
        voltage_getter_entry = self.view.control_panel.voltage_show
        # Need to set the tk.Entry into normal, update, then reset to readonly
        voltage_getter_entry.config(state='normal')     
        voltage_getter_entry.delete(0,'end')
        voltage_getter_entry.insert(0,read)
        voltage_getter_entry.config(state='readonly')

    def toggle_repump_laser(self, cmd:bool=None) -> None:
        '''
        Callback to toggle the repump laser.
        Also functions as a directly callable function in the code 
        by passing the boolean `on` variable.
        '''
        # Check if the application has a repump controller
        if 'RepumpController' in self.auxiliary_control_models:

            # If the GUI toggle is on and no direct command `cmd` given
            # OR if the direct command is True then turn on the laser
            if ((self.view.control_panel.repump_laser_on.get() == 1) and cmd is None) or (cmd is True):
                logger.info('Turning repump laser on.')
                self.disable_buttons()
                self.auxiliary_control_models['RepumpController'].go_to(
                    v=self.auxiliary_control_models['RepumpController'].maximum_allowed_voltage)
                self.enable_buttons()
            # Else if the GUI toggle is off and no direct command is given
            # OR if the direct command is False then turn off the laser
            elif ((self.view.control_panel.repump_laser_on.get() == 0) and cmd is None) or (cmd is False):
                logger.info('Turning repump laser off.')
                self.disable_buttons()
                self.auxiliary_control_models['RepumpController'].go_to(
                    v=self.auxiliary_control_models['RepumpController'].minimum_allowed_voltage)
                self.enable_buttons()

    def start_scan(self, event=None) -> None:
        '''
        Callback to start scan button.

        This function runs the actual scan.
        It first collects the scan settings from the GUI inputs and performs
        the calculations for the scan inputs.
        It then launches a Thread which runs the scanning function to avoid 
        locking up the GUI during the scan.
        '''
        if self.current_scan is not None and self.current_scan.application_controller.running:
            return # Catch accidential trigger during scan?
        
        # Turn off the repump laser
        self.toggle_repump_laser(cmd=False)

        # Get the scan parameters from the GUI
        min_voltage = float(self.view.control_panel.voltage_start_entry.get())
        max_voltage = float(self.view.control_panel.voltage_end_entry.get())
        n_pixels_up = int(self.view.control_panel.num_pixels_up_entry.get())
        n_pixels_down = int(self.view.control_panel.num_pixels_down_entry.get())
        n_scans = int(self.view.control_panel.scan_num_entry.get())
        time_up = float(self.view.control_panel.upsweep_time_entry.get())
        time_down = float(self.view.control_panel.downsweep_time_entry.get())
        n_subpixels = int(self.view.control_panel.subpixel_entry.get())
        time_repump = float(self.view.control_panel.repump_entry.get())

        # Create an application controller
        application_controller = self.application_controller_constructor(
                    readers = self.data_acquisition_models, 
                    wavelength_controller = self.wavelength_controller_model,
                    auxiliary_controllers = self.auxiliary_control_models)

        # Configure the scanner
        application_controller.configure_scan(
                    min = min_voltage, 
                    max = max_voltage, 
                    n_pixels_up = n_pixels_up, 
                    n_pixels_down = n_pixels_down, 
                    n_subpixels = n_subpixels,
                    time_up = time_up,
                    time_down = time_down,
                    n_scans = n_scans,
                    time_repump = time_repump)
        
        # Launch new child scan window
        self.number_scans_on_session += 1
        self.current_scan = ScanPopoutApplication(parent_application=self,
                                                  application_controller=application_controller, 
                                                  id=str(self.number_scans_on_session).zfill(3))
        self.scan_windows.append( self.current_scan )
        logger.info(f'Creating new scan window number {self.number_scans_on_session}')

        # Disable the buttons
        self.disable_buttons()

        # Launch the thread
        self.scan_thread = Thread(target=self.scan_thread_function)
        self.scan_thread.start()

    def stop_scan(self, event=None) -> None:
        '''
        Stops the scan
        '''
        self.current_scan.application_controller.stop()
        self.enable_buttons()

    def scan_thread_function(self) -> None:
        '''
        Function to be called in background thread.

        Runs the scans and updates the figure.
        '''
        
        try:
            self.current_scan.application_controller.start()  # starts the DAQ

            while self.current_scan.application_controller.still_scanning():
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

    def configure_from_yaml(self, afile=None) -> None:
        '''
        This method loads a YAML file to configure the hardware for PLE.
        If argument `afile` is provided and points to a valid YAML file,
        the file is loaded directly.

        If `afile` is not provided (default) then this method opens a GUI
        for the user to select a YAML file.
        
        This method configures the wavelength controller and the readers
        based off of the YAML file data, and then generates a class 
        consctrutor for the main application controller.
        '''
        # Specify the allowed filetypes (.yaml)
        filetypes = (
            ('YAML', '*.yaml'),
        )
        # If a file is not supplied...
        if not afile:
            # Open a GUI to get the file from the user
            afile = tk.filedialog.askopenfile(filetypes=filetypes, defaultextension='.yaml')
            if afile is None:
                return  # selection was canceled.
            # Log selection
            logger.info(f"Loading settings from: {afile}")
            # Retrieve the file in a dictionary `config`
            config = yaml.safe_load(afile)
            afile.close()
        else:
            # Else, open the provided file and load the YAML
            # Currently there is no protection against invalid YAML configs
            with open(afile, 'r') as file:
                # Log selection
                logger.info(f"Loading settings from: {afile}")
                config = yaml.safe_load(file)

        # At this point the `config` variable is a dictionary of 
        # nested dictionaries corresponding to each indent level in the YAML.
        # First we get the top level application name, e.g. "QT3PLE"
        APPLICATION_NAME = list(config.keys())[0]

        # Get the import path and class name for the application controller
        # We will use this to instantiate the application controller later on
        appl_ctrl_import_path = config[APPLICATION_NAME]['ApplicationController']['import_path']
        appl_ctrl_class_name = config[APPLICATION_NAME]['ApplicationController']['class_name']
        # Now we create a constructor for the aplication controller class
        # Import the application controller module
        module = importlib.import_module(appl_ctrl_import_path)
        logger.debug(f"Importing {appl_ctrl_import_path}")
        # Get the class constructor and write it to main
        self.application_controller_constructor = getattr(module, appl_ctrl_class_name)
        

        # The import paths and class names for the controllers and readers
        # are stored in the same YAML file at the same level as ['ApplicationController']
        # However, at this point we do not know how they are used by the
        # application controller. This information is referenced in the 
        # ['ApplicationController']['configure'] level.

        # There are three classes to configure, (1) controllers, (2) readers,
        # and (3) auxiliary controllers.
        # There can only be one controller for this application, we retrieve it by
        controller_name = config[APPLICATION_NAME]['ApplicationController']['configure']['controller']
        # There can be multiple readers. We can retrieve them by getting the
        # values of the readers dict (in no particular order)
        # In the future this step, and the YAML format should be modified to
        # handle the case of a single principal reader (which dictates the timing)
        # and multiple auxiliary readers which depend off of it.
        # This can be implemented by utilizing the keys of the ['configure']['readers']
        # dictionary, or by separating out ['configure']['readers'] into a 
        # singular ['configure']['principal_reader'] and ['configure']['aux_readers']
        # For now we just take all readers simultaneously in no particular order.
        reader_names = config[APPLICATION_NAME]['ApplicationController']['configure']['readers'].values()
        # Finally we can get the auxiliary controllers in the same way
        # We don't really care about the order here since we will use their names
        # as a way to reference them within the code itself.
        aux_ctrl_names = config[APPLICATION_NAME]['ApplicationController']['configure']['auxiliary_controllers'].values()

        # Now that we have their names we can retrieve their import paths
        # and class names from the YAML, along with their configurations.
        # We then can instantiate the controllers and readers and store them
        # within the application instance.
        # First get the dictionary containing the controller configuration
        controller_model_yaml_dict = config[APPLICATION_NAME][controller_name]

        # Import the controller model module
        module = importlib.import_module(controller_model_yaml_dict['import_path'])
        logger.debug(f"Importing {controller_model_yaml_dict['import_path']}")
        # Get the class generator
        controller_class = getattr(module, controller_model_yaml_dict['class_name'])
        # Instantiate the class 
        self.wavelength_controller_model = controller_class(logger.level)
        # Configure using the YAML config
        self.wavelength_controller_model.configure(controller_model_yaml_dict['configure'])

        # Repeat for each of the readers, store in MainTkApplication.data_acquisition_models
        for reader in reader_names:
            # First get the dictionary containing the controller configuration
            reader_model_yaml_dict = config[APPLICATION_NAME][reader]
            # Import the controller model module
            module = importlib.import_module(reader_model_yaml_dict['import_path'])
            logger.debug(f"Importing {reader_model_yaml_dict['import_path']}")
            # Get the class generator
            reader_class = getattr(module, reader_model_yaml_dict['class_name'])
            # Instantiate the class 
            reader_model = reader_class(logger.level)
            # Configure using the YAML config
            reader_model.configure(reader_model_yaml_dict['configure'])
            # Save to data_acquisition_models
            self.data_acquisition_models[reader] = reader_model

        # Repeat for each of the auxiliary controllers, store in MainTkApplication.auxiliary_control_models
        # Repeat for each of the readers
        for aux_ctrl in aux_ctrl_names:
            # First get the dictionary containing the controller configuration
            aux_ctrl_model_yaml_dict = config[APPLICATION_NAME][aux_ctrl]
            # Import the controller model module
            module = importlib.import_module(aux_ctrl_model_yaml_dict['import_path'])
            logger.debug(f"Importing {aux_ctrl_model_yaml_dict['import_path']}")
            # Get the class generator
            aux_ctrl_class = getattr(module, aux_ctrl_model_yaml_dict['class_name'])
            # Instantiate the class 
            aux_ctrl_model = aux_ctrl_class(logger.level)
            # Configure using the YAML config
            aux_ctrl_model.configure(aux_ctrl_model_yaml_dict['configure'])
            # Save to auxiliary_control_models
            self.auxiliary_control_models[aux_ctrl] = aux_ctrl_model


    def load_controller_from_name(self, yaml_filename: str) -> None:
        '''
        Loads the default yaml configuration file for the application controller.

        Should be called during instantiation of this class and should be the callback
        function for the support controller pull-down menu in the side panel
        '''
        yaml_path = importlib.resources.files(CONFIG_PATH).joinpath(yaml_filename)
        self.configure_from_yaml(str(yaml_path))

    def disable_buttons(self):
        self.view.control_panel.start_button['state'] = 'disabled'
        self.view.control_panel.goto_button['state'] = 'disabled'
        try:
            self.current_scan.view.control_panel.save_scan_button.config(state=tk.DISABLED)
        except Exception as e:
            if self.current_scan is not None:
                logger.debug('Exception caught disabling buttons')
                logger.debug(e)
                pass

    def enable_buttons(self):
        self.view.control_panel.start_button['state'] = 'normal'
        self.view.control_panel.goto_button['state'] = 'normal'
        try:
            self.current_scan.view.control_panel.save_scan_button.config(state=tk.NORMAL)
        except Exception as e:
            if self.current_scan is not None:
                logger.debug('Exception caught enabling buttons')
                logger.debug(e)
                pass


    def run(self) -> None:
        '''
        This function launches the application itself.
        '''
        # Set the title of the app window
        self.root.title("qdlple")
        # Display the window (not in task bar)
        self.root.deiconify()
        # Launch the main loop
        self.root.mainloop()


    def on_closing(self) -> None:
        '''
        This function handles closing the application.
        '''
        if (self.scan_thread is not None) and (self.scan_thread.is_alive()):
            if tk.messagebox.askokcancel(
                    'Warning', 
                    'Scan is currently running and may not close properly.'
                    +'\nAre you sure you want to force quit?'):
                logger.warning('Forcing application closure.')

                # Close the application out
                self.toggle_repump_laser(cmd=True) # Turn the repump laser back on
                self.root.destroy()
                self.root.quit()
        else:
            self.toggle_repump_laser(cmd=True)
            self.root.destroy()
            self.root.quit()
        
        logger.info('Exited application.')
        


def main() -> None:
    tkapp = MainTkApplication(DEFAULT_CONFIG_FILE)
    tkapp.run()


if __name__ == '__main__':
    main()
