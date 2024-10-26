import importlib
import importlib.resources
import logging

import tkinter as tk
import yaml

from qdlutils.hardware.nidaq.analogoutputs.nidaqposition import NidaqPositionController
from qdlutils.hardware.nidaq.counters.nidaqtimedratecounter import NidaqTimedRateCounter

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
        
        pass


class LineScanApplication():
    '''
    This is the line scan application class for `qdlscan` which manages the actual
    application controllers and GUI output of a single scan. It is meant to handle
    1-d confocal scans.
    '''

    def __init__(self, default_config_filename: str):
        
        pass

class ImageScanApplication():
    '''
    This is the image scan application class for `qdlscan` which manages the actual
    application controllers and GUI output of a single scan. It is meant to handle 
    2-d confocal scans.
    '''

    def __init__(self, default_config_filename: str):
        
        pass
