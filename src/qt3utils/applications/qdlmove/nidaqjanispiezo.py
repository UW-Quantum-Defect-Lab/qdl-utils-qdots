import abc
import logging
import nidaqmx
import numpy as np
import time

class NiDaqPiezoController:
    '''
    A class to control the voltage output from an NIDAQ board to control
    one axis of a Janis piezo.
    '''

    def __init__(self, 
                 device_name: str,
                 write_channel: str = 'ao0',
                 read_channel: str = None,
                 move_settle_time: float = 0.0,
                 scale_microns_per_volt: float=8,
                 zero_microns_volt_offset: float=5,
                 min_position: float = -40.0,
                 max_position: float = 40.0) -> None:
        super().__init__()

        self.logger = logging.getLogger(__name__)
        self.device_name = device_name
        self.write_channel = write_channel
        self.read_channel = read_channel
        self.scale_microns_per_volt = scale_microns_per_volt
        self.zero_microns_volt_offset = zero_microns_volt_offset
        self.minimum_allowed_position = min_position
        self.maximum_allowed_position = max_position
        self.settling_time_in_seconds = move_settle_time
        self.last_write_value = None


    def _microns_to_volts(self, microns: float) -> float:
        return microns / self.scale_microns_per_volt + self.zero_microns_volt_offset

    def _volts_to_microns(self, volts: float) -> float:
        return self.scale_microns_per_volt * (volts - self.zero_microns_volt_offset)



    def configure(self, config_dict: dict) -> None:
        '''
        This method is used to configure the data controller.
        '''
        self.device_name = config_dict.get('daq_name', self.device_name)
        self.write_channel = config_dict.get('write_channels', self.write_channel)
        self.read_channel = config_dict.get('read_channels', self.read_channel)
        self.scale_microns_per_volt = config_dict.get('scale_microns_per_volt', self.scale_microns_per_volt)
        self.zero_microns_volt_offset = config_dict.get('zero_microns_volt_offset', self.zero_microns_volt_offset)
        self.minimum_allowed_position = config_dict.get('min_position', self.minimum_allowed_position)
        self.maximum_allowed_position = config_dict.get('max_position', self.maximum_allowed_position)

    def get_current_position(self) -> float:
        '''
        Returns the position supplied to the input analog channels.
        If no input analog channels were provided when objected was created,
        returns np.nan
        '''
        output = np.nan
        if self.read_channel is not None:
            with nidaqmx.Task() as vread, nidaqmx.Task():
                vread.ai_channels.add_ai_voltage_chan(self.device_name + '/' + self.read_channel, min_val=0, max_val=10.0)
                output = vread.read()
        return output


    def _validate_value(self, position: float) -> None:
        '''
        Check if the supplied `position` argument is valid.
        '''
        position = float(position)
        if type(position) not in [type(1.0), type(1)]:
            raise TypeError(f'value {position} is not a valid type.')
        if position < self.minimum_allowed_position:
            raise ValueError(f'value {position} is less than {self.minimum_allowed_position: .3f}.')
        if position > self.maximum_allowed_position:
            raise ValueError(f'value {position} is greater than {self.maximum_allowed_position: .3f}.')


    def go_to_position(self, position: float=None) -> None:
        '''
        Sets the position
        raises ValueError if trying to set position out of bounds.
        '''
        debug_string = []
        if position is not None:
            self._validate_value(position)
            with nidaqmx.Task() as task:
                task.ao_channels.add_ao_voltage_chan(self.device_name + '/' + self.write_channel)
                task.write(position)
                self.last_write_value = position
            debug_string.append(f'positionv: {position:.2f}')
        self.logger.debug(f'go to voltage {" ".join(debug_string)}')
        # Wait at new position if desired
        if self.settling_time_in_seconds > 0:
            time.sleep(self.settling_time_in_seconds)
        self.logger.debug(f'last write: {self.last_write_value}')


    def step_position(self, dx: float=None) -> None:
        '''
        Steps the position of the piezo by dx
        '''
        if self.last_write_value is not None:
            try:
                self.go_to_position(position=self.last_write_value + dx)
            except Exception as e:
                self.logger.warning(e)
        else:
            pass # error?
