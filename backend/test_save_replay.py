#!/usr/bin/env python3
"""
数据保存和回放功能测试脚本
"""

import sys
import os

# 添加后端路径
sys.path.insert(0, '/home/arp/Documents/eeg_frontend/backend')
os.chdir('/home/arp/Documents/eeg_frontend/backend')

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eeg_backend.settings')

import django
django.setup()

from eeg_app.data_recorder import (
    start_recording, 
    write_sample, 
    stop_recording, 
    list_saved_files,
    is_recording,
    get_data_dir
)
from eeg_app.data_replay import (
    start_replay,
    read_next_sample,
    stop_replay,
    is_replaying,
    list_replayable_files
)


def test_data_recorder():
    """测试数据录制功能"""
    print("=" * 50)
    print("测试数据录制功能 (Data Recorder)")
    print("=" * 50)
    
    node_id = "test-save-node"
    
    # 1. 开始录制
    print("\n1. 开始录制...")
    result = start_recording(
        node_id=node_id,
        filename="test_recording.csv",
        format="CSV"
    )
    print(f"   结果: {result}")
    assert result['ok'], f"开始录制失败: {result.get('error')}"
    
    # 2. 写入数据
    print("\n2. 写入100个样本...")
    for i in range(100):
        channels = [float(i * 8 + j) for j in range(8)]
        write_sample(node_id, 1707753600000 + i * 1000, channels)
    print("   ✓ 写入完成")
    
    # 3. 检查录制状态
    print("\n3. 检查录制状态...")
    assert is_recording(node_id), "录制状态错误"
    print("   ✓ 正在录制中")
    
    # 4. 停止录制
    print("\n4. 停止录制...")
    result = stop_recording(node_id)
    print(f"   结果: {result}")
    assert result['ok'], f"停止录制失败: {result.get('error')}"
    assert result['sampleCount'] == 100, f"样本数错误: {result['sampleCount']}"
    print("   ✓ 录制成功")
    
    # 5. 列出已保存文件
    print("\n5. 列出已保存文件...")
    files = list_saved_files()
    print(f"   找到 {len(files)} 个文件")
    for f in files[:3]:
        print(f"   - {f['filename']} ({f['size']} bytes)")
    
    return files[0]['filename'] if files else None


def test_data_replay(filename):
    """测试数据回放功能"""
    print("\n" + "=" * 50)
    print("测试数据回放功能 (Data Replay)")
    print("=" * 50)
    
    if not filename:
        print("⚠️  没有可回放的文件，跳过回放测试")
        return
    
    node_id = "test-replay-node"
    
    # 1. 开始回放
    print(f"\n1. 开始回放文件: {filename}...")
    result = start_replay(
        node_id=node_id,
        filename=filename,
        loop=False
    )
    print(f"   结果: {result}")
    assert result['ok'], f"开始回放失败: {result.get('error')}"
    
    # 2. 读取样本
    print("\n2. 读取前10个样本...")
    samples = []
    for i in range(10):
        sample = read_next_sample(node_id)
        if sample:
            samples.append(sample)
            print(f"   样本{i}: timestamp={sample['timestamp']}, ch1={sample['channels'][0]:.2f}")
    
    assert len(samples) == 10, f"读取样本数错误: {len(samples)}"
    print("   ✓ 读取成功")
    
    # 3. 检查回放状态
    print("\n3. 检查回放状态...")
    assert is_replaying(node_id), "回放状态错误"
    print("   ✓ 正在回放中")
    
    # 4. 读取剩余样本
    print("\n4. 读取剩余样本...")
    count = 10
    while True:
        sample = read_next_sample(node_id)
        if sample is None:
            break
        count += 1
    print(f"   总共读取 {count} 个样本")
    
    # 5. 停止回放
    print("\n5. 停止回放...")
    result = stop_replay(node_id)
    print(f"   结果: {result}")
    assert result['ok'], f"停止回放失败: {result.get('error')}"
    print("   ✓ 回放成功")
    
    # 6. 列出可回放文件
    print("\n6. 列出可回放文件...")
    files = list_replayable_files()
    print(f"   找到 {len(files)} 个可回放文件")


def test_loop_replay(filename):
    """测试循环回放功能"""
    print("\n" + "=" * 50)
    print("测试循环回放功能 (Loop Replay)")
    print("=" * 50)
    
    if not filename:
        print("⚠️  没有可回放的文件，跳过")
        return
    
    node_id = "test-loop-node"
    
    # 开始循环回放
    print(f"\n1. 开始循环回放: {filename}...")
    result = start_replay(
        node_id=node_id,
        filename=filename,
        loop=True  # 循环播放
    )
    print(f"   结果: {result}")
    assert result['ok'], f"开始回放失败"
    
    # 读取超过文件总量的样本，验证循环
    total_samples = result['sampleCount']
    print(f"\n2. 读取 {total_samples + 20} 个样本（测试循环）...")
    
    samples = []
    for i in range(total_samples + 20):
        sample = read_next_sample(node_id)
        if sample:
            samples.append(sample)
    
    print(f"   实际读取 {len(samples)} 个样本")
    assert len(samples) == total_samples + 20, "循环回放可能有问题"
    print("   ✓ 循环回放正常工作")
    
    # 停止回放
    stop_replay(node_id)
    print("   ✓ 循环回放测试通过")


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("EEG 数据保存与回放功能测试")
    print("=" * 60)
    
    try:
        # 测试录制
        filename = test_data_recorder()
        
        # 测试回放
        test_data_replay(filename)
        
        # 测试循环回放
        test_loop_replay(filename)
        
        print("\n" + "=" * 60)
        print("✅ 所有测试通过!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
