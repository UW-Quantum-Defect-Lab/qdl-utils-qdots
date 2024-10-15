import argparse
import importlib
import importlib.resources
import logging
import pickle
from threading import Thread

import matplotlib
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.pyplot as plt
import nidaqmx
import numpy as np
import tkinter as tk
import yaml

from qt3utils.datagenerators import plescanner
from qt3utils.applications.controllers.nidaqedgecounter import QT3ScanNIDAQEdgeCounterController

matplotlib.use('Agg')

parser = argparse.ArgumentParser(description='NI DAQ (PCIx 6363) / PLE Scanner',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('-v', '--verbose', type=int, default=2, help='0 = quiet, 1 = info, 2 = debug.')
parser.add_argument('-cmap', metavar='<MPL color>', default='gray',
                    help='Set the MatplotLib colormap scale')
args = parser.parse_args()

logger = logging.getLogger(__name__)
logging.basicConfig()

if args.verbose == 0:
    logger.setLevel(logging.WARNING)
if args.verbose == 1:
    logger.setLevel(logging.INFO)
if args.verbose == 2:
    logger.setLevel(logging.DEBUG)

NIDAQ_DEVICE_NAMES = ['NIDAQ Rate Counter', "Lockin & Wavemeter"]
RANDOM_DAQ_DEVICE_NAME = 'Random Data Generator'

DEFAULT_DAQ_DEVICE_NAME = NIDAQ_DEVICE_NAMES[0]

CONTROLLER_PATH = 'qt3utils.applications.controllers'
STANDARD_CONTROLLERS = {NIDAQ_DEVICE_NAMES[0] : 'nidaq_rate_counter.yaml',
                        NIDAQ_DEVICE_NAMES[1] : 'nidaq_wm_ple.yaml'}

SCAN_OPTIONS = ["Discrete", "Batches"]

class ScanImage:
    '''
    This class handles the GUI image of the PLE scan

    Currently it appears to be more or less hard coded for the standard image plot
    in a PLE scan. However, in the long term it should probably be generalized to 
    handle other image types or as a standalone GUI element.
    '''

    def __init__(self, mplcolormap='gray') -> None:
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
            if isinstance(model.readers[reader], QT3ScanNIDAQEdgeCounterController):
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

        # Set the tick labels
        ax.set_xticks( np.arange(1,img_data.shape[0]+1,1) ) # Set the xticks on integer values
        y_ticks = ax.get_yticks()
        ax.set_yticks( y_ticks, self.calculate_ytick_labels(y_ticks, model.min, model.max, y_max) ) # Set the yticks to match scan
        # Reset the extent
        ax.set_ylim(0,y_max)
        # Set the labels
        ax.set_xlabel('Scan number', fontsize=14)
        ax.set_ylabel('Voltage (V)', fontsize=14)
        cbar.ax.set_ylabel('Counts/sec', fontsize=14, rotation=270, labelpad=15)
        # Set the grid
        ax.grid(alpha=0.3, axis='y', linewidth=1, color='w', dashes=(5,5))

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


class SidePanel():
    '''
    This class handles the GUI for scan parameter configuration.

    Future plan is to simplify it further and separte it from the image panel
    '''

    def __init__(self, root, scan_range) -> None:

        # Define frame for the side panel
        # This encompasses the entire side pannel
        base_frame = tk.Frame(root.root)
        base_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Define command frame for start/stop/save buttons
        command_frame = tk.Frame(base_frame)
        command_frame.pack(side=tk.TOP, padx=20, pady=10)
        # Add buttons and text
        row = 0
        tk.Label(command_frame, text="Scan control", font='Helvetica 14').grid(row=row, column=0, pady=[0,10], columnspan=3)
        row += 1
        self.start_button = tk.Button(command_frame, text="Start Scan", width=12)
        self.start_button.grid(row=row, column=0, columnspan=1, padx=3)
        self.stop_button = tk.Button(command_frame, text="Stop Scan", width=12)
        self.stop_button.grid(row=row, column=1, columnspan=1, padx=3)
        self.save_scan_button = tk.Button(command_frame, text="Save Scan", width=12)
        self.save_scan_button.grid(row=row, column=2, columnspan=1, padx=3)

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
        # Adding advanced settings --- probably want it to be a pop-out menu? Maybe not if the image is separated
        row += 1
        tk.Label(settings_frame, text="Advanced settings:", font='Helvetica 10').grid(row=row, column=0, pady=[5,0], columnspan=3)
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
        self.voltage_show=tk.Entry(control_frame, width=10)
        self.voltage_show.insert(10, 0)
        self.voltage_show.grid(row=row, column=1)
        self.voltage_show.config(state='readonly') # Disable the voltage show

        # Define config frame to set the config file
        config_frame = tk.Frame(base_frame)
        config_frame.pack(side=tk.TOP, padx=20, pady=10)
        tk.Label(config_frame, text="Hardware Configuration", font='Helvetica 14').grid(row=row, column=0, pady=[0,5], columnspan=1)
        # Dialouge button to pick the YAML config
        row += 1
        self.hardware_config_from_yaml_button = tk.Button(config_frame, text="Load YAML Config")
        self.hardware_config_from_yaml_button.grid(row=row, column=0, columnspan=1)



class MainApplicationView():
    '''
    Main application GUI view, loads SidePanel and ScanImage
    '''
    def __init__(self, main_frame, scan_range=[0, 2]) -> None:
        frame = tk.Frame(main_frame.root)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scan_view = ScanImage(args.cmap)
        self.sidepanel = SidePanel(main_frame, scan_range)

        self.canvas = FigureCanvasTkAgg(self.scan_view.fig, master=frame)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        toolbar = NavigationToolbar2Tk(self.canvas, frame)
        toolbar.update()
        self.canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.canvas.draw()


class MainTkApplication():
    '''
    Main application backend, launches the GUI and handles events
    '''
    def __init__(self, controller_name) -> None:
        '''
        Initializes the application.
        Args:
            controller_name (str) : name of controller used to identify the YAML config
        '''

        # Define class attributes to store data aquisition and controllers
        self.data_acquisition_models = {}
        self.controller_model = None
        self.meta_configs = None
        self.app_meta_data = None

        # Load the YAML file based off of `controller_name`
        self.load_controller_from_name(application_controller_name=controller_name)

        # Initialize the root tkinter widget (window housing GUI)
        self.root = tk.Tk()
        # Create the main application GUI and specify the controller name
        self.view = MainApplicationView(self, 
                                        scan_range=[self.application_controller.wavelength_controller.minimum_allowed_position, 
                                                    self.application_controller.wavelength_controller.maximum_allowed_position])
        self.view.controller_option = controller_name

        # Bind the GUI buttons to callback functions
        self.view.sidepanel.start_button.bind("<Button>", self.start_scan)
        self.view.sidepanel.save_scan_button.bind("<Button>", self.save_scan)
        self.view.sidepanel.stop_button.bind("<Button>", self.stop_scan)
        self.view.sidepanel.goto_button.bind("<Button>", self.go_to)
        self.view.sidepanel.get_button.bind("<Button>", self.update_voltage_show)
        self.view.sidepanel.hardware_config_from_yaml_button.bind("<Button>", lambda e: self.configure_from_yaml())

        # Set protocol for shutdown when the root tkinter widget is closed
        self.root.protocol("WM_DELETE_WINDOWwait_visibility()", self.on_closing)

    def go_to(self, event=None) -> None:
        '''
        Callback function for voltage setter `self.view.sidepanel.goto_button`

        This function is a wrapper for the `application_controller.go_to()` method
        which is itself a wrapper for the `wavelength_controller.got_to()` method.
        This structure is so that information at behavior and information can be
        handled at intermediate levels (for example, this function gets the input 
        from the GUI, the `application_controller` level handles out-of-range 
        exceptions and the lowest-level `wavelength_controller` opens a nidaq task
        to change the voltage on the hardware.)
        '''
        self.disable_buttons()
        controller_speed = self.application_controller.wavelength_controller.speed
        self.application_controller.wavelength_controller.speed = "fast"
        self.application_controller.go_to(float(self.view.sidepanel.voltage_entry.get()))
        self.application_controller.wavelength_controller.speed = controller_speed
        self.enable_buttons()

    def update_voltage_show(self, event=None) -> None:
        '''
        Callback to update the reading on the GUI voltage getter

        Obtains the last write value from the wavelength_controller level and
        then updates the result on the GUI.
        '''
        # Get the last write value from the wavelength controller
        read = self.application_controller.wavelength_controller.last_write_value
        # Update the GUI
        voltage_getter_entry = self.view.sidepanel.voltage_show
        # Need to set the tk.Entry into normal, update, then reset to readonly
        voltage_getter_entry.config(state='normal')     
        voltage_getter_entry.delete(0,'end')
        voltage_getter_entry.insert(0,read)
        voltage_getter_entry.config(state='readonly')

    def start_scan(self, event=None) -> None:
        '''
        Callback to start scan button.

        This function runs the actual scan.
        It first collects the scan settings from the GUI inputs and performs
        the calculations for the scan inputs.
        It then launches a Thread which runs the scanning function to avoid 
        locking up the GUI during the scan.
        '''
        self.disable_buttons()

        # Get the scan parameters from the GUI
        min_voltage = float(self.view.sidepanel.voltage_start_entry.get())
        max_voltage = float(self.view.sidepanel.voltage_end_entry.get())
        n_pixels_up = int(self.view.sidepanel.num_pixels_up_entry.get())
        n_pixels_down = int(self.view.sidepanel.num_pixels_down_entry.get())
        n_scans = int(self.view.sidepanel.scan_num_entry.get())
        time_up = float(self.view.sidepanel.upsweep_time_entry.get())
        time_down = float(self.view.sidepanel.downsweep_time_entry.get())
        n_subpixels = int(self.view.sidepanel.subpixel_entry.get())
        time_repump = float(self.view.sidepanel.repump_entry.get())

        # Configure the scanner
        self.application_controller.configure_scan(
                    min = min_voltage, 
                    max = max_voltage, 
                    n_pixels_up = n_pixels_up, 
                    n_pixels_down = n_pixels_down, 
                    n_subpixels = n_subpixels,
                    time_up = time_up,
                    time_down = time_down,
                    n_scans = n_scans,
                    time_repump = time_repump)

        # Launch the thread
        self.app_meta_data = args
        self.scan_thread = Thread(target=self.scan_thread_function)
        self.scan_thread.start()

    def stop_scan(self, event=None) -> None:
        '''
        Stops the scan
        '''
        self.application_controller.stop()
        self.enable_buttons()

    def scan_thread_function(self) -> None:
        '''
        Function to be called in background thread.

        Runs the scans and updates the figure.
        '''
        
        try:
            self.application_controller.start()  # starts the DAQ

            while self.application_controller.still_scanning():
                self.application_controller.scan_wavelengths()
                self.view.scan_view.update_image_and_plot(self.application_controller)
                self.view.canvas.draw()

            logger.info('Scan complete.')
            self.application_controller.stop()

        except nidaqmx.errors.DaqError as e:
            logger.info(e)
            logger.info(
                'Check for other applications using resources. If not, you may need to restart the application.')

        self.enable_buttons()

    def save_scan(self, event = None):
        myformats = [('Pickle', '*.pkl')]
        afile = tk.filedialog.asksaveasfilename(filetypes=myformats, defaultextension='.pkl')
        logger.info(afile)
        file_type = afile.split('.')[-1]
        if afile is None or afile == '':
            return # selection was canceled.
        data = {}
        data["Data"] = {}
        if self.application_controller is not None:
            for ii, scan_data in enumerate(self.application_controller.outputs):
                data["Data"][f"Scan{ii}"] = {}
                for reader in self.application_controller.readers:
                    data["Data"][f"Scan{ii}"][reader] = scan_data[reader]
        data["Metadata"] = []
        if self.meta_configs is not None:
            for meta_config in self.meta_configs:
                data["Metadata"].append(meta_config)
        if self.app_meta_data is not None:
            data["ApplicationController"] = self.app_meta_data

        if file_type == 'pkl':
            with open(afile, 'wb') as f:
                pickle.dump(data, f)

    def configure_from_yaml(self, afile=None) -> None:
        '''
        This method loads a YAML file to configure the hardware for PLE.
        If argument `afile` is provided and points to a valid YAML file,
        the file is loaded directly.

        If `afile` is not provided (default) then this method opens a GUI
        for the user to select a YAML file.
        
        The current version of this method attempts to configure the
        controller classes and instantiate the application controller.
        Future modifications will instead save the configuration to the 
        current top-level application (MainTkApplication) and then 
        instantiate classes as needed.
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
        CONFIG_FILE_APPLICATION_NAME = list(config.keys())[0]

        # Now retrieve the application controller configuration
        self.app_controller_config = config[CONFIG_FILE_APPLICATION_NAME]["ApplicationController"]

        self.app_config = self.app_controller_config["configure"]
        
        daq_readers = self.app_config["readers"]["daq_readers"]
        self.meta_configs = []
        self.data_acquisition_models = {}
        if daq_readers is not None:
            for daq_reader in daq_readers:
                daq_reader_name = daq_readers[daq_reader]
                daq_reader_config = config[CONFIG_FILE_APPLICATION_NAME][daq_reader_name]
                self.meta_configs.append(daq_reader_config)
                module = importlib.import_module(daq_reader_config['import_path'])
                logger.debug(f"loading {daq_reader_config['import_path']}")
                cls = getattr(module, daq_reader_config['class_name'])
                self.data_acquisition_models[daq_reader_name] = cls(logger.level)
                self.data_acquisition_models[daq_reader_name].configure(daq_reader_config['configure'])

        daq_controller_name = config[CONFIG_FILE_APPLICATION_NAME]['ApplicationController']['configure']['controllers']['daq_writers']['daq_writer']
        daq_controller_config = config[CONFIG_FILE_APPLICATION_NAME][daq_controller_name]
        self.meta_configs.append(daq_controller_config)
        if daq_controller_config is not None:
            module = importlib.import_module(daq_controller_config['import_path'])
            logger.debug(f"loading {daq_controller_config['import_path']}")
            cls = getattr(module, daq_controller_config['class_name'])
            self.controller_model = cls(logger.level)
            self.controller_model.configure(daq_controller_config['configure'])
        else:
           raise Exception("Yaml configuration file must have a controller for PLE scan.")
        self.application_controller = plescanner.PleScanner(self.data_acquisition_models, self.controller_model)

    def load_controller_from_name(self, application_controller_name: str) -> None:
        '''
        Loads the default yaml configuration file for the application controller.

        Should be called during instantiation of this class and should be the callback
        function for the support controller pull-down menu in the side panel
        '''
        yaml_path = importlib.resources.files(CONTROLLER_PATH).joinpath(STANDARD_CONTROLLERS[application_controller_name])
        self.configure_from_yaml(str(yaml_path))

    def disable_buttons(self):
        self.view.sidepanel.start_button['state'] = 'disabled'
        self.view.sidepanel.goto_button['state'] = 'disabled'
        self.view.sidepanel.save_scan_button.config(state=tk.DISABLED)

    def enable_buttons(self):
        self.view.sidepanel.start_button['state'] = 'normal'
        self.view.sidepanel.goto_button['state'] = 'normal'
        self.view.sidepanel.save_scan_button.config(state=tk.NORMAL)

    def run(self) -> None:
        '''
        This function launches the application itself.
        '''
        # Set the title of the app window
        self.root.title("QT3PLE: Run PLE scan")
        # Display the window (not in task bar)
        self.root.deiconify()
        # Launch the main loop
        self.root.mainloop()


    def on_closing(self) -> None:
        '''
        This function handles closing the application.
        '''
        try:
            self.stop_scan()
            self.root.quit()
            self.root.destroy()
        except Exception as e:
            logger.debug(e)
            pass



def main() -> None:
    tkapp = MainTkApplication(DEFAULT_DAQ_DEVICE_NAME)
    tkapp.run()


if __name__ == '__main__':
    main()
