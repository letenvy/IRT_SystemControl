from collections import namedtuple
import numpy as np


class KalmanFilter:

    def __init__(self, vector_size, delta_time, noise_dispersion, data_dispersion, f, g, h, initial_state,
                 reset_threshold):

        self.vector_size = vector_size
        self.delta_time = delta_time
        self.d_n = noise_dispersion
        self.d_ksi = data_dispersion
        matrices = namedtuple('Matrices', 'f g h')
        self.matrices = matrices(f, g, h)
        self.x_prev = initial_state
        self.initial_state = initial_state
        self.x_est = self.x_prev
        self.d_x_prev = np.diag(np.ones(vector_size))
        self.blind_cnt = 0
        self.reset_threshold = reset_threshold

    def __call__(self, *args):
        if len(args) > 1:
            return TypeError(f"__call__() takes 2 positional arguments but {len(args) + 1} were given")
        if self.blind_cnt >= self.reset_threshold:
            #self.x_prev = self.initial_state
            #self.d_x_prev = np.diag(np.ones(self.vector_size))
            #self.x_est = self.x_prev
            self.blind_cnt = 0
        x_ext = self.matrices.f @ self.x_est
        d_x = self.matrices.f @ self.d_x_prev @ self.matrices.f.T + self.matrices.g @ self.d_ksi @ self.matrices.g.T
        self.x_est = x_ext
        if len(args) == 1:
            self.blind_cnt = 0
            d_x = np.linalg.inv(np.linalg.inv(d_x) + self.matrices.h.T @ np.linalg.inv(self.d_n) @ self.matrices.h)
            k = d_x @ self.matrices.h.T @ np.linalg.inv(self.d_n)
            self.x_est += k @ (args[0] - self.matrices.h @ x_ext)
            self.d_x_prev = d_x
        else:
            self.blind_cnt += 1

        return self.x_est
