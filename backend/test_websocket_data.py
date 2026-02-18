#!/usr/bin/env python3
"""测试WebSocket数据生成路径"""

import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from eeg_app.graph_consumer import get_device_channels
from eeg_app.device_store import get_device_config

def test_device_config():
    """测试设备配置获取"""
    print("测试设备配置获取...")
    
    # 测试获取设备配置
    device_id = "mock-1"
    config = get_device_config(device_id)
    
    if config:
        print(f"设备 {device_id} 配置获取成功")
        print(f"通道数量: {len(config.get('channels', []))}")
        
        # 检查CH1配置
        channels = config.get('channels', [])
        for channel in channels:
            if channel.get('index') == 0:
                print(f"CH1配置: {channel}")
                break
    else:
        print(f"设备 {device_id} 配置获取失败")

def test_signal_generation():
    """测试信号生成"""
    print("\n测试信号生成...")
    
    device_id = "mock-1"
    
    # 测试不同时间点的信号
    sample_rate = 1000
    test_times = [0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.1]
    
    for t in test_times:
        channels = get_device_channels(device_id, t, sample_rate)
        if channels and len(channels) > 0:
            print(f"t={t:.3f}s: CH1={channels[0]:.1f}")
        else:
            print(f"t={t:.3f}s: 无数据")

def simulate_websocket_loop():
    """模拟WebSocket数据生成循环"""
    print("\n模拟WebSocket数据生成循环...")
    
    device_id = "mock-1"
    sample_rate = 1000
    dt = 1.0 / sample_rate
    
    # 模拟生成10个样本
    t = 0.0
    for i in range(10):
        channels = get_device_channels(device_id, t, sample_rate)
        if channels and len(channels) > 0:
            # 检查是否为方波模式
            ch1_value = channels[0]
            period = 1.0 / 10  # 10Hz方波
            
            # 计算相位
            phase_rad = 2 * 3.14159 * 10 * t
            phase_mod = phase_rad % (2 * 3.14159)
            expected_positive = phase_mod < 3.14159  # 默认占空比0.5
            
            if expected_positive:
                expected = "正值 (~100)"
                is_correct = ch1_value > 50  # 考虑到噪声
            else:
                expected = "负值 (~-100)"
                is_correct = ch1_value < -50
            
            print(f"样本 {i:2d}: t={t:.4f}s, CH1={ch1_value:6.1f}, 期望={expected}, 正确={is_correct}")
        else:
            print(f"样本 {i:2d}: t={t:.4f}s, 无数据")
        
        t += dt

if __name__ == "__main__":
    print("=" * 60)
    print("WebSocket数据生成测试")
    print("=" * 60)
    
    test_device_config()
    test_signal_generation()
    simulate_websocket_loop()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)