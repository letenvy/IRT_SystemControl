#!/usr/bin/env python3
"""
Альфа-фильтр для двух координат (векторный фильтр)
Использует экспоненциальное скользящее среднее с отдельными альфа-коэффициентами для x и y
"""


class AlphaBlendFilter:
    """
    Альфа-фильтр для фильтрации вектора из двух координат.
    
    Использует формулу экспоненциального скользящего среднего:
    filtered_value = alpha * new_value + (1 - alpha) * previous_value
    
    Параметры:
        alpha (float): Коэффициент фильтрации для x-координаты (0.0 - 1.0)
        x_init (float, optional): Начальное значение x-координаты
        y_init (float, optional): Начальное значение y-координаты
    """
    
    def __init__(self, alpha=0.6, x_init=0.0, y_init=0.0):
        """
        Инициализация альфа-фильтра.
        
        Args:
            alpha: Коэффициент фильтрации для x (0 = только старое значение, 1 = только новое)
            x_init: Начальное значение x
            y_init: Начальное значение y
        """
        if not (0.0 <= alpha <= 1.0):
            raise ValueError(f"alpha_x должен быть в диапазоне [0.0, 1.0], получено {alpha}")
        
        self.alpha = alpha
        
        # Текущие отфильтрованные значения
        self.x_filtered = float(x_init)
        self.y_filtered = float(y_init)
    
    def update(self, x, y):
        """
        Обновляет фильтр новыми значениями координат.
        
        Args:
            x (float): Новое значение x-координаты
            y (float): Новое значение y-координаты
            
        Returns:
            tuple: (x_filtered, y_filtered) - отфильтрованные значения
        """
        # Экспоненциальное скользящее среднее
        self.x_filtered = self.alpha * self.x_filtered + (1.0 - self.alpha) * x
        self.y_filtered = self.alpha * self.y_filtered + (1.0 - self.alpha) * y
        
        return self.get_filtered()
    
    def get_filtered(self):
        """
        Возвращает текущие отфильтрованные значения.
        
        Returns:
            tuple: (x_filtered, y_filtered)
        """
        return (self.x_filtered, self.y_filtered)
