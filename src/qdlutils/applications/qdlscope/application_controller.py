import logging
import time

import numpy as np

from qdlutils.hardware.nidaq.counters.nidaqtimedratecounter import NidaqTimedRateCounter
from qdlutils.hardware.nidaq.analogoutputs.nidaqposition import NidaqPositionController

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class ScopeController:
    '''
    This is the main class which coordinates the collection of data.
    '''

    def __init__(self,
                 counter_controller: NidaqTimedRateCounter):
        
        self.counter_controller = counter_controller

        # Flag to check if running
        self.running = False

    def read_counts_continuous(self, 
                               sample_time: float, 
                               get_rate: bool = True):
        '''
        This method reads out the counts quasi-continuously. 
        
        Parameters
        ----------
        sample_time : float
            The time in seconds per sample on the DAQ board. The DAQ will be progrmamed
            to sample the counter for sample_time seconds. Note that the actual time
            between samples will be slightly larger due to computational overhead; see
            the Notes section below.
        get_rate : bool
            If `True` (default behavior), the return value will be the count rate
            (determined by the sample_time input -- not the DAQ timing! See the Notes).
            On the other hand, if `False` then the counts over each samples are instead
            returned.

        Yields
        ------
        float
            The count rate (or raw number of counts) measured over `sample_time` seconds,
            repeating until the internal `self.running` flag is set to `False`.
        
        Notes
        -----
        The specific timing of the samples will vary slightly from the predicted rate of
        1/sample_time as there is some computational overhead involved with the sampling
        itself (computations before/after the actual sampling, etc.) As a result, this
        method may return slightly incorrectly timed data, especially over long periods
        of time where the small errors (likely < 0.1%) can accumulate.

        To deal with this issue, we provide a class attribute `self.readout_time`, which
        measures (in seconds using the python `time` module) the length of time between
        the start and end of the sampling. While this in and of itself may be slightly
        inaccurate, you can use this to correct for the accumulated errors over long time
        periods. Such correction is not implemented directly into this method, however.

        Also note that the normalization of the counts (to get the count rate) uses the
        provided `sample_time` parameter and does not use the DAQ "num_samples" output.
        As a consequence, the actual DAQ sample time might vary slightly due to dropped 
        samples (see the documentation for 
            qdlutils.hardware.nidaq.coutners.NidaqBatchedRateCounter
        for more information), however dropped samples are rare and typically do not 
        correspond to any meaningful time difference (< 10 μs).
        '''
        # Set the running flag
        self.running = True

        # Configure the DAQ sampling time
        self.counter_controller.configure_sample_time(sample_time=sample_time)

        # Set the scaling factor (equals 1 for getting counts explicitly or 1/sample_time
        # if returning the count rate). We do this out front so that each yield call does
        # not need to check if we must compute the rate.
        if get_rate:
            scale = 1/sample_time
        else:
            scale = 1

        # Start up the counter
        self.counter_controller.start()

        while self.running:

            # While the counter is running, yield the counts, scaled by `scale`
            yield (self.counter_controller.sample_batch_counts() / scale)

        # Stop the counter
        self.counter_controller.stop()

    def read_counts_batches(self,
                            sample_time: float,
                            batch_time: float,
                            get_rate: bool = True):
        '''
        This method reads out counts in discrete batches of length `batch_time` in
        seconds.
        '''
        # Set the running flag
        self.running = True

        # Configure the DAQ sampling time
        self.counter_controller.configure_sample_time(sample_time=sample_time)

        # Set the scaling factor (equals 1 for getting counts explicitly or 1/sample_time
        # if returning the count rate). We do this out front so that each yield call does
        # not need to check if we must compute the rate.
        if get_rate:
            scale = 1/sample_time
        else:
            scale = 1

        # Compute the number of samples to record per batch. There will be some slight
        # truncation error if the `sample_time` is not a factor of `batch_time`.
        n_samples = int(batch_time / sample_time)
        # Note that the terminology of samples and batches used here is distinct from the
        # low-level definition of samples and batches. At the low level, data is read out
        # once per clock cycle where each readout is referred to as a "sample". The sum
        # of clock cycle "samples" over `sample_time` is called at this level a "batch".
        # In this application, each low-level "batch" is a sample and we take `n_samples`
        # of these batched readout samples per yield (the "batch" at this level).
        # If attempting to modify this method, DO NOT modify the low level hardware code!

        # Start up the counter
        self.counter_controller.start()

        while self.running:

            # While the counter is running, yield the counts, scaled by `scale`
            yield (self.counter_controller.sample_nbatches_counts(n_batches=n_samples) / scale)

        # Stop the counter
        self.counter_controller.stop()
