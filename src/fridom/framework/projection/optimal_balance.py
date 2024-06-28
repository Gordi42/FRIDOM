# Import external modules
from typing import TYPE_CHECKING
import numpy as np
# Import internal modules
from fridom.framework.projection.projection import Projection
# Import type information
if TYPE_CHECKING:
    from fridom.framework.modelsettings_base import ModelSettingsBase
    from fridom.framework.state_base import StateBase


class OptimalBalance(Projection):
    """
    Nonlinear balancing using the optimal balance method.

    Parameters
    ----------
    `mset` : `ModelSettings`
        The model settings.
    `base_proj` : `Projection`
        The projection onto the base point.
    `mset_backwards` : `ModelSettings`
        The model settings for the backward ramping. If None, the forward model
        settings are used.
    `ramp_period` : `float`
        The ramping period (not scaled).
    `ramp_type` : `str`
        The ramping type. Choose from "exp", "pow", "cos", "lin".
    `disable_diagnostic` : `bool`
        Whether to disable the diagnostic tendencies during the iterations.
    `update_base_point` : `bool`
        Whether to update the base point after each iteration. This has no effect
        on OB. But it matters for OBTA. Should be True for OBTA.
    `max_it` : `int`
        Maximum number of iterations.
    `stop_criterion` : `float`
        The stopping criterion.
    """
    def __init__(self, mset: 'ModelSettingsBase',
                 base_proj:Projection,
                 mset_backwards: 'ModelSettingsBase' = None,
                 ramp_period=1,
                 ramp_type="exp",
                 disable_diagnostic=True,
                 update_base_point=True,
                 max_it=3,
                 stop_criterion=1e-9,
                 return_details=False) -> None:
        super().__init__(mset)
        self.mset_backwards = mset_backwards or mset

        self.base_proj = base_proj
        self.return_details = return_details
        
        # initialize the model
        from fridom.framework.model import Model
        self.model_forward = Model(mset)
        self.model_backward = Model(mset_backwards or mset)

        if disable_diagnostic:
            self.model_forward.diagnostics.disable()
            self.model_backward.diagnostics.disable()

        # save the parameters
        self.ramp_period    = ramp_period
        self.ramp_steps     = int(ramp_period / mset.time_stepper.dt)
        self.ramp_func      = OptimalBalance.get_ramp_func(ramp_type)
        self.max_it         = max_it
        self.stop_criterion = stop_criterion
        self.update_base_point = update_base_point

        # save the rossby number
        self.rossby = float(mset.Ro)

        # prepare the balancing
        self.z_base = None
        return

    def calc_base_coord(self, z: 'StateBase') -> None:
        self.z_base = self.base_proj(z)
        return

    def forward_to_nonlinear(self, z: 'StateBase') -> 'StateBase':
        """
        Perform forward ramping from linear model to nonlinear model.
        """

        model = self.model_forward
        model.reset()
        mset = model.mset
        time_stepper = model.time_stepper

        # make sure the time step is positive
        time_stepper.dt = np.abs(time_stepper.dt)

        # initialize the model
        model.z = z.copy()

        # perform the forward ramping
        for n in range(self.ramp_steps):
            mset.Ro = self.rossby * self.ramp_func(n / self.ramp_steps)
            model.step()
        return model.z
    
    def backward_to_linear(self, z: 'StateBase') -> 'StateBase':
        """
        Perform backward ramping from nonlinear model to linear model.
        """
        model = self.model_backward
        model.reset()
        mset = model.mset

        # make sure the time step is negative
        model.time_stepper.dt = - np.abs(model.time_stepper.dt)

        # initialize the model
        model.z = z.copy()

        # perform the backward ramping
        for n in range(self.ramp_steps):
            mset.Ro = self.rossby * self.ramp_func(1 - n / self.ramp_steps)
            model.step()
        return model.z

    def forward_to_linear(self, z: 'StateBase') -> 'StateBase':
        """
        Perform forward ramping from nonlinear model to linear model.
        """
        model = self.model_forward
        model.reset()
        mset = model.mset

        # make sure the time step is positive
        model.time_stepper.dt = np.abs(model.time_stepper.dt)

        # initialize the model
        model.z = z.copy()

        # perform the forward ramping
        for n in range(self.ramp_steps):
            mset.Ro = self.rossby * self.ramp_func(n / self.ramp_steps)
            model.step()
        return model.z

    def backward_to_nonlinear(self, z: 'StateBase') -> 'StateBase':
        """
        Perform backward ramping from linear model to nonlinear model.
        """
        model = self.model_backward
        model.reset()
        mset = model.mset

        # make sure the time step is negative
        model.time_stepper.dt = - np.abs(model.time_stepper.dt)

        # initialize the model
        model.z = z.copy()

        # perform the backward ramping
        for n in range(self.ramp_steps):
            mset.Ro = self.rossby * self.ramp_func(1 - n / self.ramp_steps)
            model.step()
        return model.z

    def get_ramp_func(ramp_type):
        if ramp_type == "exp":
            def ramp_func(theta):
                t1 = 1./np.maximum(1e-32,theta )
                t2 = 1./np.maximum(1e-32,1.-theta )
                return np.exp(-t1)/(np.exp(-t1)+np.exp(-t2))  
        elif ramp_type == "pow":
            def ramp_func(theta):
                return theta**3/(theta**3+(1.-theta)**3)
        elif ramp_type == "cos":
            def ramp_func(theta):
                return 0.5*(1.-np.cos(np.pi*theta))
        elif ramp_type == "lin":
            def ramp_func(theta):
                return theta
        else:
            raise ValueError(
                "Invalid ramp type. Choose from 'exp', 'pow', 'cos', 'lin'.")
        return ramp_func
        

    def __call__(self, z: 'StateBase') -> 'StateBase':
        """
        Project a state to the balanced subspace using optimal balance.
        
        Parameters
        ----------
        `z` : `State`
            The state to project.
        
        Returns
        -------
        `State`
            The projection of the state onto the balanced subspace.
        """
        verbose = self.mset.print_verbose

        iterations = np.arange(self.max_it)
        errors     = np.ones(self.max_it)

        # save the base coordinate
        self.calc_base_coord(z)

        z_res = z.copy()

        # start the iterations
        verbose("Starting optimal balance iterations")

        for it in iterations:
            verbose(f"Starting iteration {it}")
            # backward ramping
            verbose("Performing backward ramping")
            z_lin = self.backward_to_linear(z_res)
            # project to the base point
            z_lin = self.base_proj(z_lin)
            # forward ramping
            verbose("Performing forward ramping")
            z_bal = self.forward_to_nonlinear(z_lin)
            # exchange base point coordinate
            z_new = z_bal - self.base_proj(z_bal) + self.z_base

            # calculate the error
            errors[it] = error = z_new.norm_of_diff(z_res)

            verbose(f"Difference to previous iteration: {error:.2e}")

            # update the state
            z_res = z_new

            # check the stopping criterion
            if error < self.stop_criterion:
                verbose("Stopping criterion reached.")
                break

            # check if the error is increasing
            if it > 0 and error > errors[it-1]:
                verbose("WARNING: Error is increasing. Stopping iterations.")
                break

            # recalculate the base coordinate if needed
            if self.update_base_point:
                # check if it is not the last iteration
                if it < self.max_it - 1:
                    self.calc_base_coord(z_res)

        if self.return_details:
            return z_res, (iterations, errors)
        else:
            return z_res