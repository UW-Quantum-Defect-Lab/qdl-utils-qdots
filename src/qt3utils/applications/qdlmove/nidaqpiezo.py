import logging
import nidaqmx
import numpy as np
import time

class NiDaqPiezoController:
    '''
    A class to control the voltage output from an NIDAQ board to control
    one axis of a voltage controlled piezo actuator.
    Any piezo actuator which operates via NIDAQ analog output voltages
    is compatable with this class.
    Note that there is currently no logic for voltage input feedback 
    as needed for position stabilization.

    This is a positioner-specialized version of the generic single analog 
    output voltage controller for NIDAQ boards.
    '''

    def __init__(self, 
                 device_name: str = 'Dev1',
                 write_channel: str = 'ao0',
                 read_channel: str = None,
                 move_settle_time: float = 0.0,
                 scale_microns_per_volt: float=8,
                 zero_microns_volt_offset: float=5,
                 min_position: float = -40.0,
                 max_position: float = 40.0,
                 invert_axis: bool = False) -> None:
        super().__init__()

        self.logger = logging.getLogger(__name__)
        self.device_name = device_name
        self.write_channel = write_channel
        self.read_channel = read_channel
        self.scale_microns_per_volt = scale_microns_per_volt
        self.zero_microns_volt_offset = zero_microns_volt_offset
        self.min_position = min_position
        self.max_position = max_position
        self.settling_time_in_seconds = move_settle_time
        self.invert_axis = invert_axis
        self.last_write_value = None

        # Invert the axis if specified
        # This just changes the `scale_microns_per_volt` and `zero_microns_volt_offset`
        if self.invert_axis:
            center_position = (self.min_position + self.max_position) / 2
            center_voltage = self._microns_to_volts(center_position)
            self.scale_microns_per_volt = -self.scale_microns_per_volt
            self.zero_microns_volt_offset = center_voltage - (center_position / self.scale_microns_per_volt)


    def _microns_to_volts(self, microns: float) -> float:
        '''
        Internal conversion from a position in microns to volts on the DAQ
        '''
        return microns / self.scale_microns_per_volt + self.zero_microns_volt_offset

    def _volts_to_microns(self, volts: float) -> float:
        '''
        Internal conversion from volts on the DAQ to position in microns
        '''
        return self.scale_microns_per_volt * (volts - self.zero_microns_volt_offset)



    def configure(self, config_dict: dict) -> None:
        '''
        This method is used to configure the data controller.
        '''
        self.device_name = config_dict.get('device_name', self.device_name)
        self.write_channel = config_dict.get('write_channel', self.write_channel)
        self.read_channel = config_dict.get('read_channel', self.read_channel)
        self.scale_microns_per_volt = config_dict.get('scale_microns_per_volt', self.scale_microns_per_volt)
        self.zero_microns_volt_offset = config_dict.get('zero_microns_volt_offset', self.zero_microns_volt_offset)
        self.min_position = config_dict.get('min_position', self.min_position)
        self.max_position = config_dict.get('max_position', self.max_position)
        self.settling_time_in_seconds = config_dict.get('move_settle_time', self.settling_time_in_seconds)
        self.invert_axis = config_dict.get('invert_axis', self.invert_axis)

        # Invert the axis if specified
        if self.invert_axis:
            center_position = (self.min_position + self.max_position) / 2
            center_voltage = self._microns_to_volts(center_position)
            self.scale_microns_per_volt = -self.scale_microns_per_volt
            self.zero_microns_volt_offset = center_voltage - (center_position / self.scale_microns_per_volt)

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
        return self._volts_to_microns(output)


    def _validate_value(self, position: float) -> None:
        '''
        Check if the supplied `position` argument is valid.
        '''
        position = float(position)
        if type(position) not in [type(1.0), type(1)]:
            raise TypeError(f'value {position} is not a valid type.')
        if position < self.min_position:
            raise ValueError(f'value {position} is less than {self.min_position: .3f}.')
        if position > self.max_position:
            raise ValueError(f'value {position} is greater than {self.max_position: .3f}.')


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
                task.write(self._microns_to_volts(position))
                self.last_write_value = position
            debug_string.append(f'position: {position:.2f}')
        self.logger.debug(f'Go to position {" ".join(debug_string)}')
        # Wait at new position if desired
        if self.settling_time_in_seconds > 0:
            time.sleep(self.settling_time_in_seconds)
        self.logger.debug(f'Last write: {self.last_write_value}')


    def step_position(self, dx: float=None) -> None:
        '''
        Steps the position of the piezo by dx (can be positive or negative)
        '''
        if self.last_write_value is not None:
            try:
                self.go_to_position(position=self.last_write_value + dx)
            except Exception as e:
                self.logger.warning(e)
        else:
            # Eventually would like to include a step to read in the position
            # at this point if read-in was implemented.
            # For now just raise an error.
            raise Exception('No last write error provided, cannot step')
