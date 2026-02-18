#!/usr/bin/env python3
"""测试信号生成"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from eeg_app.graph_consumer import generate_signal_from_config
import math

# 测试方波生成
def test_square_wave():
    print("测试方波生成...")
    
    # 方波配置
    config = {
        'wave_type': 'square',
        'frequency': 10.0,  # 10Hz
        'amplitude': 100.0,
        'phase': 0.0,
        'duty_cycle': 0.5,
        'enabled': True
    }
    
    sample_rate = 1000.0
    test_times = [0.0, 0.025, 0.05, 0.075, 0.1]  # 测试不同时间点
    
    for t in test_times:
        signal = generate_signal_from_config(config, t, sample_rate)
        print(f"时间 t={t:.3f}s, 信号值={signal:.1f}")
    
    # 验证方波特性
    print("\n验证方波特性:")
    period = 1.0 / config['frequency']  # 0.1秒周期
    duty_time = period * config['duty_cycle']  # 0.05秒高电平
    
    # 测试周期内不同点
    test_points = [
        (0.0, "周期开始"),
        (duty_time/2, "高电平中间"),
        (duty_time - 0.001, "高电平结束前"),
        (duty_time + 0.001, "低电平开始"),
        (period/2, "周期中间"),
        (period - 0.001, "周期结束前")
    ]
    
    for t_offset, desc in test_points:
        signal = generate_signal_from_config(config, t_offset, sample_rate)
        expected = config['amplitude'] if t_offset < duty_time else -config['amplitude']
        print(f"{desc}: t={t_offset:.4f}s, 信号={signal:.1f}, 期望={expected:.1f}, {'✓' if abs(signal - expected) < 0.1 else '✗'}")

if __name__ == "__main__":
    test_square_wave()