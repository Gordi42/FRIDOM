"""
utils
===
Contains utility functions.

Functions
---------
`print_bar(char='=')`
    Print a bar to the stdout.
`print_job_init_info()`
    Print the job starting time and the number of MPI processes.
"""
from . import config
from .config import logger
from mpi4py import MPI
import time

def print_bar(char='='):
    """
    Print a bar to the log file.

    Parameters
    char: str
        Character to use for the bar.
    """
    if MPI.COMM_WORLD.Get_rank() == 0:
        print(char*80, flush=True)

def print_job_init_info():
    """
    Print the job starting time and the number of MPI processes.
    """
    print_bar("#")
    logger.info("FRIDOM: Framework for Idealized Ocean Models")
    # get system time
    from datetime import datetime

    # Get the current system time
    current_time = datetime.now()

    # Format the time according to the given format
    formatted_time = current_time.strftime(" > Job starting on %Y.%m.%d at %I:%M:%S %p")

    logger.info(formatted_time)

    # get the number of MPI processes
    size = MPI.COMM_WORLD.Get_size()
    logger.info(f" > Running on {size} MPI processes.")
    logger.info(f" > Backend: {config.backend}")
    print_bar("#")
    [print_bar(" ") for _ in range(3)]

def humanize_number(value, unit):
    if unit == "meters":
        if value < 1e-2:
            return f"{value*1e3:.2f} mm"
        elif value < 1:
            return f"{value*1e2:.2f} cm"
        elif value < 1e3:
            return f"{value:.2f} m"
        else:
            return f"{value/1e3:.2f} km"
    else:
        raise NotImplementedError(f"Unit '{unit}' not implemented.")

def chdir_to_submit_dir():
    """
    Change the current working directory to the directory where the job was submitted.
    """
    import os
    logger.info("Changing working directory")
    logger.info(f"Old working directory: {os.getcwd()}")
    submit_dir = os.getenv('SLURM_SUBMIT_DIR')
    os.chdir(submit_dir)
    logger.info(f"New working directory: {os.getcwd()}")
    return

def stdout_is_file():
    import os, sys
    # check if the output is not a file
    if os.isatty(sys.stdout.fileno()):
        res = False  # output is a terminal
    else:
        res = True   # output is a file

    # check if the output is ipython
    from IPython import get_ipython
    if get_ipython() is not None:
        res = False  # output is ipython
    return res

class ProgressBar:
    """
    Progress bar class.
    
    Description
    -----------
    The progress bar class is a wrapper around the tqdm progress bar. It
    has a custom format and handles the output to the stdout when the
    stdout is a file.
    
    Parameters
    ----------
    `disable` : `bool`
        Whether to disable the progress bar.
    
    Methods
    -------
    `update(value: float, postfix: str)`
        Updates the progress bar.
    `close()`
        Close the progress bar.
    """
    def __init__(self, disable: bool = False) -> None:
        # only rank 0 should print the progress bar
        if MPI.COMM_WORLD.Get_rank() != 0:
            disable = True
        # ----------------------------------------------------------------
        #  Set the progress bar format
        # ----------------------------------------------------------------
        bar_format = "{percentage:3.2f}%|{bar}| "
        bar_format += "[{elapsed}<{remaining}]{postfix}"

        # ----------------------------------------------------------------
        #  Check if the stdout is a file
        # ----------------------------------------------------------------
        file_output = stdout_is_file()
        if file_output:
            # if the stdout is a file, tqdm would print to the stderr by default
            # we could instead print to the stdout, but this would mess up
            # the look of the progress bar due to "\r" characters
            # so we create a StringIO object to capture the output
            # and adjust the progress bar accordingly
            import io
            output = io.StringIO()
        else:
            import sys
            output = sys.stdout

        # ----------------------------------------------------------------
        #  Create the progress bar
        # ----------------------------------------------------------------
        from tqdm import tqdm
        pbar = tqdm(
            total=100, 
            disable=disable, 
            bar_format=bar_format, 
            unit="%", 
            file=output)
        
        # ----------------------------------------------------------------
        #  Set the attributes
        # ----------------------------------------------------------------
        self.disable = disable
        # private attributes
        self._pbar = pbar
        self._file_output = file_output
        self._output = output
        self._last_call = time.time()
        return

    def update(self, value: float, postfix: str = "") -> None:
        """
        Updates the progress bar.
        
        Parameters
        ----------
        `value` : `float`
            A value between 0 and 100, representing the progress.
        `postfix` : `str`
            A string to append to the progress bar.
        """
        if self.disable:
            return

        # get the time between the last call (in milliseconds)
        now = time.time()
        elapsed = now - self._last_call
        self._last_call = now
        elapsed = f"{int(elapsed*1e3)} ms/it"

        # update the progress bar
        self._pbar.n = value
        self._pbar.set_postfix_str(f"{elapsed}  at {postfix}")
        self._pbar.refresh()

        if not self._file_output:
            return

        # print the progress to the stdout
        config.logger.info(self._output.getvalue().split("\r")[1])

        # clear the output string
        self._output.seek(0)
        return

    def close(self) -> None:
        """Close the progress bar."""
        self._pbar.close()
        return
