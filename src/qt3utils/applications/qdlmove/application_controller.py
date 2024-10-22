import logging
import time

import numpy as np

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class MovementController:

    def __init__(self, positioners: dict = {}):

        self.positioners = positioners # dictionary of the controller instantiations
        self.step_sizes = {}


    def move_axis(self, axis_controller_name: str, position: float):
        # Move the axis specified by the axis_controller_name
        self.positioners[axis_controller_name].go_to_position(position)

    def step_axis(self, axis_controller_name: str, dx: float):
        # Step the axis specified by the axis_controller_name
        self.positioners[axis_controller_name].step_position(dx)