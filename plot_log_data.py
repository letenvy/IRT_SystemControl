#!/usr/bin/env python3
"""
Скрипт для визуализации данных из файла log_coords_and_heading.txt
В каждой строке файла три числа, которые отображаются на одном графике
"""

import matplotlib.pyplot as plt
import numpy as np

def parse_log_file(filename):
    """Парсит файл лога и извлекает три числа из каждой строки"""
    data1 = []
    data2 = []
    data3 = []
    
    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            # Разделяем строку по пробелам и извлекаем три числа
            parts = line.split()
            if len(parts) >= 3:
                try:
                    val1 = float(parts[0])
                    val2 = float(parts[1])
                    val3 = float(parts[2])
                    
                    data1.append(val1)
                    data2.append(val2)
                    data3.append(val3)
                except ValueError:
                    continue
    
    return np.array(data1), np.array(data2), np.array(data3)

def plot_data(data1, data2, data3):
    """Строит график с тремя функциями на одном графике"""
    # Создаём фигуру
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Создаём массив индексов (номер строки)
    indices = np.arange(len(data1))
    
    # Строим три линии на одном графике
    ax.plot(indices, data1, 'b-', linewidth=1.5, label='x (в метрах)', alpha=0.8)
    ax.plot(indices, data2, 'g-', linewidth=1.5, label='y (в метрах)', alpha=0.8)
    ax.plot(indices, data3/np.max(np.abs(data3)), 'r-', linewidth=1.5, label='heading (в градусах масштабированный)', alpha=0.8)

    ax.set_xlabel('Номер строки', fontsize=12)
    ax.set_ylabel('Значение', fontsize=12)
    ax.set_title('Три функции на одном графике', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend(loc='best', fontsize=10)
    
    plt.tight_layout()
    plt.show()
    
    # Выводим статистику
    print(f"\nСтатистика данных:")
    print(f"Количество точек: {len(data1)}")
    if len(data1) > 0:
        print(f"\nx: min={data1.min():.2f}, max={data1.max():.2f}, mean={data1.mean():.2f}")
        print(f"y: min={data2.min():.2f}, max={data2.max():.2f}, mean={data2.mean():.2f}")
        print(f"heading: min={data3.min():.2f}, max={data3.max():.2f}, mean={data3.mean():.2f}")

def main():
    filename = 'log_coords_and_heading.txt'
    
    print(f"Чтение данных из файла: {filename}")
    data1, data2, data3 = parse_log_file(filename)
    
    if len(data1) == 0:
        print("Ошибка: не найдено данных в файле")
        return
    
    print(f"Загружено {len(data1)} точек данных")
    
    plot_data(data1, data2, data3)

if __name__ == '__main__':
    main()
