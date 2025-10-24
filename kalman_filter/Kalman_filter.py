import numpy as np


def fx(x0, x_sat):
    """
    Вектор функциональной связи между наблюдениями и координатами объекта
    :param x0:
    :param x_sat:
    :return:
    """

    return np.array(list(map(lambda x: np.linalg.norm(x - x0), x_sat)))


def Hx(x_prev, x_sat):
    """
    Градиентная матрица
    :param x_prev:
    :param x_sat:
    :return:
    """

    return np.array(list(
        map(lambda x: -(x - x_prev) / np.linalg.norm(x - x_prev) if np.linalg.norm(x - x_prev) != 0 else np.zeros(
            x_prev.shape), x_sat)))


def EKF3(y, x_est_prev, D_x_prev, D_n_mat, x_sat, T_sample, list_keys):
    D_ksi = np.array([[1e-2, 0, 0],
                      [0, 1e-2, 0],
                      [0, 0, 1e-2]])

    d = 0.9

    F = np.array([[1, 0, 0, T_sample, 0, 0],
                  [0, 1, 0, 0, T_sample, 0],
                  [0, 0, 1, 0, 0, T_sample],
                  [0, 0, 0, 1, 0, 0],
                  [0, 0, 0, 0, 1, 0],
                  [0, 0, 0, 0, 0, 1]])

    G = np.array([[0, 0, 0],
                  [0, 0, 0],
                  [0, 0, 0],
                  [T_sample, 0, 0],
                  [0, T_sample, 0],
                  [0, 0, T_sample]])

    # Уравнения Калмановской фильтрации
    # Шаг экстраполяции
    x_ext = np.dot(F, x_est_prev)
    D_x_ext = np.dot(np.dot(F, D_x_prev), F.T) + np.dot(np.dot(G, D_ksi), G.T)
    # Шаг коррекции
    dS = np.concatenate((Hx(x_ext[:3], x_sat), np.zeros((D_n_mat.shape[0], int(x_est_prev.shape[0] - 3)))), axis=1)
    temp_matrix = np.dot(np.dot(dS.T, np.linalg.inv(D_n_mat)), dS)
    D_x = np.linalg.inv(np.linalg.inv(D_x_ext) + temp_matrix)
    K = np.dot(np.dot(D_x, dS.T), np.linalg.inv(D_n_mat))
    y_new = []
    if len(y) != D_n_mat.shape[0]:
        j = 0
        for key in list_keys:
            if key in y.keys():
                y_new.append(y[key])
            else:
                y_new.append(fx(x_ext[:3], x_sat)[j])
                # y_new.append(0)
            j += 1
        y_new = np.array(y_new)
    else:
        for key in list_keys:
            if key in y.keys():
                y_new.append(y[key])
        y_new = np.array(y_new)

    x_est = x_ext + np.dot(K, (y_new - fx(x_ext[:3], x_sat)))
    return x_est, D_x
