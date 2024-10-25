import time
import logging

import numpy as np
import nidaqmx


from qdlutils.hardware.nidaq.counters.nidaqbatchedratecounter import NidaqBatchedRateCounter

logger = logging.getLogger(__name__)


class NidaqTimedRateCounter(NidaqBatchedRateCounter):
    '''
    This class implements an NIDAQ timed rate counter utilizing the edge counter 
    interface. This represents one layer of abstraction away from directly interfacing
    with the hardware since the NIDAQ API is qutie complicated.

    Specifically, this class represents a standard rate counter which is structured
    around "timed" data collection wherein the counts are readout in batches of a 
    set "sample_time" in seconds.
    
    This represents a slightly more user-friendly version of the `NidaqBatchedRateCounter`
    and inhereits most functionality from it.
    '''


    def __init__(self,
                 daq_name = 'Dev1',
                 signal_terminal = 'PFI0',
                 clock_rate = 1000000,
                 sample_time_in_seconds = 1,
                 clock_terminal = None,
                 read_write_timeout = 10,
                 signal_counter = 'ctr2',
                 trigger_terminal = None,):
        
        # Save the only new attribute
        self.sample_time_in_seconds = sample_time_in_seconds

        # Calculate the number of samples per batch upto nearest integer
        num_data_samples_per_batch = int(sample_time_in_seconds * clock_rate)

        # Run the batched rate counter init to get the remaining variables
        super().__init__(daq_name = daq_name,
                         signal_terminal = signal_terminal,
                         clock_rate = clock_rate,
                         num_data_samples_per_batch = num_data_samples_per_batch,
                         clock_terminal = clock_terminal,
                         read_write_timeout = read_write_timeout,
                         signal_counter = signal_counter,
                         trigger_terminal = trigger_terminal)

    def configure(self, config_dict) -> None:
        '''
        This overwrites the parent class configure to include the new sample time 
        parameter and calculation or relevant number of samples per batch.

        **Warning**: Using this method to update the clock parameters will not work
        if the clock task has already been started. To avoid accidentially making 
        changes like this, a separate method `configure_sample_time()` is provided 
        to adjust the sample time dynamically (and the number of samples per batch 
        respectively).

        Parameters
        ----------
        config_dict : dict
            A dictionary containing keys matching the class atributes. If a match
            is found, then the corresponding attribute is updated. Otherwise it is 
            left unchanged.
        '''

        self.daq_name = config_dict.get('daq_name', self.daq_name)
        self.signal_terminal = config_dict.get('signal_terminal', self.signal_terminal)
        self.clock_rate = config_dict.get('clock_rate', self.clock_rate)
        self.sample_time_in_seconds = config_dict.get('sample_time_in_seconds', self.sample_time_in_seconds)
        self.clock_terminal = config_dict.get('clock_terminal', self.clock_terminal)
        self.signal_counter = config_dict.get('signal_counter', self.signal_counter)
        self.read_write_timeout = config_dict.get('read_write_timeout', self.read_write_timeout)
        self.trigger_terminal = config_dict.get('trigger_terminal', self.trigger_terminal)

        # Update the number of samples per batch
        self.num_data_samples_per_batch = int(self.sample_time_in_seconds * self.clock_rate)
        # Also need to update the coutner task if it exists
        if self.edge_counter_interface and self.edge_counter_interface.counter_task:
            self.edge_counter_interface.counter_task.timing.samp_quant_samp_per_chan = self.num_data_samples_per_batch

    def configure_sample_time(self, sample_time: float) -> None:
        '''
        Configures the sample time and the number of samples per batch without adjusting
        other parameters.

        Parameters
        ----------
        sample_time : float
            Sample time in seconds to update instance to.
        '''
        # Update the sample time
        self.sample_time_in_seconds = sample_time
        # Update the number of samples per batch
        self.num_data_samples_per_batch = int(self.sample_time_in_seconds * self.clock_rate)
        # Also need to update the coutner task if it exists
        if self.edge_counter_interface and self.edge_counter_interface.counter_task:
            self.edge_counter_interface.counter_task.timing.samp_quant_samp_per_chan = self.num_data_samples_per_batch