import pytest
import fridom.nonhydro as nh
import numpy as np

@pytest.mark.parametrize("runlen", [1, 6, 24])  # in hours
def test_linear_model(backend, runlen):
    ncp = nh.config.ncp
    f0 = 1e-4
    N2 = (50 * f0) ** 2
    N = tuple([16] * 3)
    L = (10_000, 10_000, 100)

    grid = nh.grid.cartesian.Grid(N=N, L=L)
    mset = nh.ModelSettings(grid, f0=f0, N2=N2)
    mset.time_stepper.dt = np.timedelta64(2, 'm')
    mset.tendencies.advection.disable()
    mset.setup()

    X, Y, Z = grid.X
    Lx, Ly, Lz = grid.L

    z = nh.State(mset)
    z.u[:] = ncp.exp(-(Y - Ly/2)**2 / (0.2*Ly)**2) * ncp.exp(-(Z - Lz/2)**2 / (0.2*Lz)**2)
    z.sync()

    initial_total_energy = z.etot.int()

    model = nh.Model(mset)
    model.z = z
    model.run(runlen=np.timedelta64(runlen, 'h'))

    final_total_energy = model.z.etot.int()

    assert ncp.abs(1 - final_total_energy / initial_total_energy) < 1e-3

@pytest.mark.parametrize("periodic_bounds",
    [
        (True, True, True),
        (False, True, True),
        (True, False, True),
        (True, True, False),
        (False, False, False),
    ])
def test_boundary_conditions(backend, periodic_bounds):
    ncp = nh.config.ncp
    f0 = 1e-4
    N2 = (50 * f0) ** 2
    N = tuple([16] * 3)
    L = (10_000, 10_000, 100)

    grid = nh.grid.cartesian.Grid(N=N, L=L, periodic_bounds=periodic_bounds)
    mset = nh.ModelSettings(grid, f0=f0, N2=N2)
    mset.time_stepper.dt = np.timedelta64(20, 's')
    mset.tendencies.advection.disable()
    mset.setup()

    X, Y, Z = grid.X
    Lx, Ly, Lz = grid.L

    z = nh.State(mset)
    width = 0.05
    z.b[:] = 0.1 * ncp.exp(-(Y - 3*Ly/4)**2 / (width*Ly)**2) * \
                   ncp.exp(-(Z - 1*Lz/4)**2 / (width*Lz)**2) * \
                   ncp.exp(-(X - 1*Lx/4)**2 / (width*Lx)**2)

    z.sync()

    initial_total_energy = z.etot.int()

    model = nh.Model(mset)
    model.z = z
    model.run(runlen=np.timedelta64(6, 'h'))

    final_total_energy = model.z.etot.int()

    assert ncp.abs(1 - final_total_energy / initial_total_energy) < 1e-2
