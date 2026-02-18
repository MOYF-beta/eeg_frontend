#!/usr/bin/env python3
"""详细测试方波生成"""

import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from eeg_app.graph_consumer import get_device_channels

def test_full_period():
    """测试完整周期"""
    print("测试10Hz方波完整周期（0.1秒）...")
    
    device_id = "mock-1"
    sample_rate = 1000
    period = 1.0 / 10  # 0.1秒
    
    # 测试一个完整周期的20个点
    num_samples = 20
    print(f"周期: {period:.3f}秒, 采样数: {num_samples}")
    print("-" * 60)
    
    for i in range(num_samples):
        t = i * period / num_samples
        channels = get_device_channels(device_id, t, sample_rate)
        
        if channels and len(channels) > 0:
            ch1_value = channels[0]
            
            # 计算理论值
            phase_rad = 2 * 3.14159 * 10 * t
            phase_mod = phase_rad % (2 * 3.14159)
            in_positive_half = phase_mod < 3.14159  # 前半个周期
            
            # 检查是否匹配
            if in_positive_half:
                expected_sign = "正"
                is_correct = ch1_value > 0
            else:
                expected_sign = "负"
                is_correct = ch1_value < 0
            
            print(f"样本 {i:2d}: t={t:.4f}s, 相位={phase_mod:.3f}rad, CH1={ch1_value:7.1f}, 期望={expected_sign}, 正确={is_correct}")
        else:
            print(f"样本 {i:2d}: t={t:.4f}s, 无数据")

def test_multiple_periods():
    """测试多个周期"""
    print("\n\n测试多个周期...")
    
    device_id = "mock-1"
    sample_rate = 1000
    period = 0.1
    
    # 测试3个周期的关键点
    test_points = [
        (0.000, "周期开始"),
        (0.025, "1/4周期"),
        (0.049, "接近半周期"),
        (0.050, "半周期"),
        (0.051, "刚过半周期"),
        (0.075, "3/4周期"),
        (0.099, "接近周期结束"),
        (0.100, "周期结束/下一个开始"),
        (0.125, "1.25周期"),
        (0.150, "1.5周期"),
        (0.175, "1.75周期"),
        (0.200, "2.0周期"),
    ]
    
    print("时间点测试:")
    print("-" * 60)
    
    for t, desc in test_points:
        channels = get_device_channels(device_id, t, sample_rate)
        
        if channels and len(channels) > 0:
            ch1_value = channels[0]
            
            # 计算在哪个半周期
            phase_rad = 2 * 3.14159 * 10 * t
            phase_mod = phase_rad % (2 * 3.14159)
            in_positive_half = phase_mod < 3.14159
            
            if in_positive_half:
                expected_range = "90-110"
                is_in_range = 90 <= ch1_value <= 110
            else:
                expected_range = "-110 - -90"
                is_in_range = -110 <= ch1_value <= -90
            
            print(f"t={t:.3f}s ({desc:10s}): CH1={ch1_value:7.1f}, 相位={phase_mod:.3f}rad, 期望范围={expected_range}, 在范围内={is_in_range}")
        else:
            print(f"t={t:.3f}s ({desc:10s}): 无数据")

if __name__ == "__main__":
    print("=" * 60)
    print("方波生成详细测试")
    print("=" * 60)
    
    test_full_period()
    test_multiple_periods()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)