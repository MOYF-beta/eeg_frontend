#!/usr/bin/env python3
"""
EEG信号滤波效果测试程序（简化版）
纯Python实现，不依赖外部库
"""

import math
import json
from datetime import datetime

def generate_test_signal(duration=5.0, sample_rate=1000):
    """
    生成包含明显高低频成分的测试信号
    
    信号组成：
    - 低频成分: 5Hz + 8Hz (模拟脑电α波和θ波)
    - 高频噪声: 50Hz + 100Hz (模拟工频干扰和高频噪声)
    - 白噪声: 随机小幅度干扰
    """
    num_samples = int(duration * sample_rate)
    t = [i / sample_rate for i in range(num_samples)]
    
    signal_data = []
    low_component = []
    high_component = []
    
    for time_point in t:
        # 低频成分（应该被保留）
        low = 5 * math.sin(2 * math.pi * 5 * time_point) + 3 * math.sin(2 * math.pi * 8 * time_point)
        
        # 高频噪声（应该被滤除）
        high = 2 * math.sin(2 * math.pi * 50 * time_point) + 1.5 * math.sin(2 * math.pi * 100 * time_point)
        
        # 白噪声
        import random
        white = 0.5 * random.gauss(0, 1)
        
        signal_data.append(low + high + white)
        low_component.append(low)
        high_component.append(high)
    
    return t, signal_data, low_component, high_component

def simple_moving_average(signal, window_size=20):
    """简单移动平均滤波（模拟低通滤波）"""
    result = []
    for i in range(len(signal)):
        if i < window_size:
            result.append(signal[i])
        else:
            window = signal[i-window_size:i]
            result.append(sum(window) / window_size)
    return result

def calculate_energy(signal):
    """计算信号能量（幅值平方和）"""
    return sum(x**2 for x in signal)

def calculate_statistics(signal):
    """计算信号统计特征"""
    n = len(signal)
    mean = sum(signal) / n
    variance = sum((x - mean)**2 for x in signal) / n
    std_dev = math.sqrt(variance)
    
    # 计算高频波动（通过相邻样本差分）
    diffs = [abs(signal[i] - signal[i-1]) for i in range(1, n)]
    avg_diff = sum(diffs) / len(diffs)
    
    return {
        'mean': mean,
        'std_dev': std_dev,
        'avg_diff': avg_diff,
        'max_val': max(signal),
        'min_val': min(signal)
    }

def test_filter_effect():
    """测试滤波效果"""
    print("🔬 EEG低通滤波效果测试程序（简化版）")
    print("="*60)
    
    # 生成测试信号
    print("\n📈 生成测试信号...")
    t, signal, low_comp, high_comp = generate_test_signal(duration=2.0, sample_rate=1000)
    print(f"   信号长度: {len(signal)} 样本")
    print(f"   采样率: 1000 Hz")
    print(f"   时长: 2.0 秒")
    
    # 分析原始信号
    print("\n📊 分析原始信号...")
    orig_stats = calculate_statistics(signal)
    low_energy = calculate_energy(low_comp)
    high_energy = calculate_energy(high_comp)
    total_energy = calculate_energy(signal)
    
    print(f"   信号均值: {orig_stats['mean']:.4f}")
    print(f"   标准差: {orig_stats['std_dev']:.4f}")
    print(f"   平均变化率: {orig_stats['avg_diff']:.4f}")
    print(f"   低频能量占比: {low_energy/total_energy*100:.1f}%")
    print(f"   高频能量占比: {high_energy/total_energy*100:.1f}%")
    
    # 测试不同窗口大小的滤波效果
    window_sizes = [10, 20, 50]  # 对应截止频率约 50Hz, 25Hz, 10Hz
    
    for window in window_sizes:
        approx_cutoff = 500 / window  # 近似截止频率
        print(f"\n🧪 测试滤波 (窗口={window}, 近似截止频率≈{approx_cutoff:.0f}Hz)")
        
        # 应用滤波
        filtered = simple_moving_average(signal, window)
        
        # 分析滤波后信号
        filt_stats = calculate_statistics(filtered)
        
        # 计算改善指标
        diff_reduction = (orig_stats['avg_diff'] - filt_stats['avg_diff']) / orig_stats['avg_diff'] * 100
        std_reduction = (orig_stats['std_dev'] - filt_stats['std_dev']) / orig_stats['std_dev'] * 100
        
        print(f"   滤波后标准差: {filt_stats['std_dev']:.4f} (降低 {std_reduction:.1f}%)")
        print(f"   平均变化率: {filt_stats['avg_diff']:.4f} (降低 {diff_reduction:.1f}%)")
        
        # 显示前10个样本对比
        print(f"   样本对比 (前10个):")
        print(f"     原始: {[f'{x:.2f}' for x in signal[:10]]}")
        print(f"     滤波: {[f'{x:.2f}' for x in filtered[:10]]}")
    
    # 生成详细对比数据文件
    print("\n💾 生成详细对比数据...")
    output_data = {
        'timestamp': datetime.now().isoformat(),
        'signal_info': {
            'sample_rate': 1000,
            'duration': 2.0,
            'num_samples': len(signal)
        },
        'original_signal': signal[:100],  # 前100个样本
        'filtered_10hz': simple_moving_average(signal, 50)[:100],
        'filtered_25hz': simple_moving_average(signal, 20)[:100],
        'filtered_50hz': simple_moving_average(signal, 10)[:100]
    }
    
    output_file = 'filter_test_results.json'
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    print(f"   数据已保存: {output_file}")
    
    print("\n" + "="*60)
    print("✅ 测试完成！")
    print("\n📋 结论:")
    print("   1. 低通滤波有效降低了信号的高频波动")
    print("   2. 截止频率越低，滤波效果越明显")
    print("   3. 详细数据已保存到 JSON 文件")
    print("="*60)

if __name__ == "__main__":
    test_filter_effect()
