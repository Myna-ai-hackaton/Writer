import numpy as np
cimport numpy as cnp
from libc.math cimport exp
from libc.stdlib cimport rand, RAND_MAX

def run_metropolis_step(cnp.int8_t[:, :] lattice, double T, double J=1.0):
    cdef int rows = lattice.shape[0]
    cdef int cols = lattice.shape[1]
    cdef int i, j
    cdef double dE, beta = 1.0 / T

    for i in range(rows):
        for j in range(cols):
            spin_sum = (lattice[(i - 1 + rows) % rows, j] +
                        lattice[(i + 1) % rows, j] +
                        lattice[i, (j - 1 + cols) % cols] +
                        lattice[i, (j + 1) % cols])
            dE = 2.0 * J * lattice[i, j] * spin_sum
            if dE <= 0 or (rand() / <double>RAND_MAX) < exp(-dE * beta):
                lattice[i, j] = -lattice[i, j]
    return np.asarray(lattice)
