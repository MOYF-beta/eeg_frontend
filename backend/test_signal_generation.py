#!/usr/bin/env python3
"""测试信号生成函数"""

import math
import random
import json
import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from eeg_app.graph_consumer import generate_signal_from_config

def test_square_wave():
    """测试方波生成"""
    print("测试方波生成...")
    
    # CH1的配置（来自device_data.json）
    ch1_config = {
        "index": 0,
        "wave_type": "square",
        "frequency": 10,
        "amplitude": 100,
        "phase": 0,
        "sine_components": [
            {
                "frequency": 10,
                "amplitude": 100,
                "phase": 0
            }
        ],
        "noise_type": "white",
        "noise_amplitude": 5,
        "enabled": True
    }
    
    # 测试不同时间点的信号值
    sample_rate = 1000
    period = 1.0 / 10  # 10Hz的周期是0.1秒
    
    test_times = [
        0.0,           # 周期开始
        period * 0.25, # 1/4周期
        period * 0.49, # 接近一半但还在占空比内（默认0.5）
        period * 0.51, # 超过一半，应该为负值
        period * 0.75, # 3/4周期
        period * 0.99, # 接近周期结束
        period,        # 一个完整周期
        period * 1.25, # 1.25个周期
    ]
    
    print(f"频率: 10Hz, 周期: {period:.3f}秒")
    print(f"振幅: 100, 默认占空比: 0.5")
    print("\n时间点测试:")
    print("-" * 50)
    
    for t in test_times:
        signal = generate_signal_from_config(ch1_config, t, sample_rate)
        phase_rad = 2 * math.pi * 10 * t
        phase_mod = phase_rad % (2 * math.pi)
        in_duty_cycle = phase_mod < 2 * math.pi * 0.5
        
        print(f"t={t:.4f}s, 相位={phase_mod:.3f}rad, 占空比内={in_duty_cycle}, 信号值={signal:.1f}")
    
    # 测试一个完整周期的采样
    print("\n完整周期采样（10个点）:")
    print("-" * 50)
    samples_per_period = 10
    for i in range(samples_per_period):
        t = i * period / samples_per_period
        signal = generate_signal_from_config(ch1_config, t, sample_rate)
        print(f"采样点 {i:2d}: t={t:.4f}s, 信号值={signal:.1f}")

def test_with_duty_cycle():
    """测试带占空比方波"""
    print("\n\n测试带占空比方波（duty_cycle=0.3）...")
    
    config = {
        "wave_type": "square",
        "frequency": 10,
        "amplitude": 100,
        "phase": 0,
        "duty_cycle": 0.3,  # 30%占空比
        "enabled": True
    }
    
    period = 1.0 / 10
    test_times = [0.0, period * 0.2, period * 0.4, period * 0.6, period * 0.8]
    
    for t in test_times:
        signal = generate_signal_from_config(config, t, 1000)
        phase_rad = 2 * math.pi * 10 * t
        phase_mod = phase_rad % (2 * math.pi)
        in_duty_cycle = phase_mod < 2 * math.pi * 0.3
        
        print(f"t={t:.4f}s, 相位={phase_mod:.3f}rad, 占空比内={in_duty_cycle}, 信号值={signal:.1f}")

def test_sine_wave():
    """测试正弦波作为对比"""
    print("\n\n测试正弦波作为对比...")
    
    config = {
        "wave_type": "sine",
        "frequency": 10,
        "amplitude": 100,
        "phase": 0,
        "enabled": True
    }
    
    period = 1.0 / 10
    test_times = [0.0, period * 0.25, period * 0.5, period * 0.75, period]
    
    for t in test_times:
        signal = generate_signal_from_config(config, t, 1000)
        expected = 100 * math.sin(2 * math.pi * 10 * t)
        print(f"t={t:.4f}s, 信号值={signal:.1f}, 期望值={expected:.1f}, 匹配={abs(signal-expected) < 0.1}")

if __name__ == "__main__":
    print("=" * 60)
    print("信号生成函数测试")
    print("=" * 60)
    
    test_square_wave()
    test_with_duty_cycle()
    test_sine_wave()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)