import tkinter as tk

class PositionControllerApplicationView():
    '''
    Main Application GUI
    '''

    def __init__(self, main_window: tk.Tk):
        # Get the frame to pack the GUI
        frame = tk.Frame(main_window)
        frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=16, pady=16)

        # Edit here to add more movement control
        self.micros_view = TwoAxisApplicationView(root_frame=frame, title='Micros', axis_1_label='X axis', axis_2_label='Y axis')

        


class TwoAxisApplicationView():
    '''
    Application control for two-axis movement
    '''
    def __init__(self, root_frame: tk.Frame, title: str, axis_1_label: str, axis_2_label: str):
        
        # Frame to house this subwindow
        base_frame = tk.Frame(root_frame)
        base_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)


        row = 0
        tk.Label(base_frame, text=title, font='Helvetica 14').grid(row=row, column=0, pady=[0,10], columnspan=1)

        row += 1
        tk.Label(base_frame, text='Set value', font='Helvetica 12', width=10).grid(row=row, column=2, pady=[0,0], columnspan=1)
        tk.Label(base_frame, text='Step', font='Helvetica 12', width=10).grid(row=row, column=3, pady=[0,0], columnspan=1)
        tk.Label(base_frame, text='Current', font='Helvetica 12', width=10).grid(row=row, column=4, pady=[0,0], columnspan=1)

        row += 1
        tk.Label(base_frame, text=axis_1_label, font='Helvetica 12', width=10).grid(row=row, column=0, pady=[0,0], columnspan=1)
        self.axis_1_set_button = tk.Button(base_frame, text='Set position', width=10)
        self.axis_1_set_button.grid(row=row, column=1, columnspan=1, padx=0)
        self.axis_1_set_entry = tk.Entry(base_frame, width=10)
        self.axis_1_set_entry.insert(0, 0)
        self.axis_1_set_entry.grid(row=row, column=2)
        self.axis_1_step_entry = tk.Entry(base_frame, width=10)
        self.axis_1_step_entry.insert(0, 0)
        self.axis_1_step_entry.grid(row=row, column=3)
        self.axis_1_readout_entry = tk.Entry(base_frame, width=10)
        self.axis_1_readout_entry.insert(0, 0)
        self.axis_1_readout_entry.config(state='readonly')
        self.axis_1_readout_entry.grid(row=row, column=4)

        row += 1
        tk.Label(base_frame, text=axis_2_label, font='Helvetica 12', width=10).grid(row=row, column=0, pady=[0,0], columnspan=1)
        self.axis_2_set_button = tk.Button(base_frame, text='Set position', width=10)
        self.axis_2_set_button.grid(row=row, column=1, columnspan=1, padx=0)
        self.axis_2_set_entry = tk.Entry(base_frame, width=10)
        self.axis_2_set_entry.insert(0, 0)
        self.axis_2_set_entry.grid(row=row, column=2)
        self.axis_2_step_entry = tk.Entry(base_frame, width=10)
        self.axis_2_step_entry.insert(0, 0)
        self.axis_2_step_entry.grid(row=row, column=3)
        self.axis_2_readout_entry = tk.Entry(base_frame, width=10)
        self.axis_2_readout_entry.insert(0, 0)
        self.axis_2_readout_entry.config(state='readonly')
        self.axis_2_readout_entry.grid(row=row, column=4)