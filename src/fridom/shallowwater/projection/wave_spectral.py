from fridom.shallowwater.grid import Grid
from fridom.framework.projection \
    .wave_spectral import WaveSpectralBase

class WaveSpectral(WaveSpectralBase):
    def __init__(self, grid: Grid) -> None:
        from fridom.shallowwater.eigenvectors import VecP, VecQ
        super().__init__(grid, VecQ, VecP)

# remove symbols from the namespace
del Grid, WaveSpectralBase