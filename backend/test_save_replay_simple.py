#!/usr/bin/env python3
"""
数据保存和回放功能独立测试（不依赖Django）
"""

import sys
import os
import csv
import time
from pathlib import Path
from datetime import datetime

# 数据保存目录
DATA_DIR = Path('/tmp/eeg_test_data')
DATA_DIR.mkdir(exist_ok=True)


class SimpleRecorder:
    """简化版数据录制器"""
    
    def __init__(self):
        self._active = {}
    
    def start(self, node_id, filename=None):
        if not filename:
            filename = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        if not filename.endswith('.csv'):
            filename += '.csv'
        
        filepath = DATA_DIR / filename
        f = open(filepath, 'w', newline='', encoding='utf-8')
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'sample_idx'] + [f'ch{i+1}' for i in range(8)])
        
        self._active[node_id] = {
            'file': f,
            'writer': writer,
            'filepath': str(filepath),
            'start_time': time.time(),
            'count': 0,
        }
        return {'ok': True, 'filepath': str(filepath)}
    
    def write(self, node_id, timestamp, channels):
        if node_id not in self._active:
            return False
        info = self._active[node_id]
        info['writer'].writerow([int(timestamp), info['count']] + [round(ch, 6) for ch in channels])
        info['count'] += 1
        if info['count'] % 100 == 0:
            info['file'].flush()
        return True
    
    def stop(self, node_id):
        if node_id not in self._active:
            return {'ok': False, 'error': 'Not recording'}
        info = self._active[node_id]
        info['file'].close()
        duration = time.time() - info['start_time']
        result = {
            'ok': True,
            'filepath': info['filepath'],
            'sampleCount': info['count'],
            'duration': round(duration, 2),
        }
        del self._active[node_id]
        return result


class SimpleReplayer:
    """简化版数据回放器"""
    
    def __init__(self):
        self._active = {}
    
    def start(self, node_id, filename, loop=False):
        filepath = DATA_DIR / filename
        if not filepath.exists():
            return {'ok': False, 'error': f'File not found: {filename}'}
        
        # 统计样本数
        sample_count = 0
        with open(filepath, 'r') as f:
            reader = csv.reader(f)
            next(reader, None)  # 跳过表头
            for _ in reader:
                sample_count += 1
        
        f = open(filepath, 'r', encoding='utf-8')
        reader = csv.reader(f)
        next(reader, None)  # 跳过表头
        
        self._active[node_id] = {
            'file': f,
            'reader': reader,
            'filepath': str(filepath),
            'loop': loop,
            'sample_count': sample_count,
            'current': 0,
        }
        return {'ok': True, 'sampleCount': sample_count}
    
    def read(self, node_id):
        if node_id not in self._active:
            return None
        info = self._active[node_id]
        
        row = next(info['reader'], None)
        if row is None:
            if info['loop']:
                info['file'].close()
                info['file'] = open(info['filepath'], 'r', encoding='utf-8')
                info['reader'] = csv.reader(info['file'])
                next(info['reader'], None)
                info['current'] = 0
                row = next(info['reader'], None)
            else:
                return None
        
        if row:
            info['current'] += 1
            return {
                'timestamp': int(row[0]),
                'channels': [float(v) for v in row[2:]],
            }
        return None
    
    def stop(self, node_id):
        if node_id not in self._active:
            return {'ok': False, 'error': 'Not replaying'}
        info = self._active[node_id]
        info['file'].close()
        result = {
            'ok': True,
            'samplesPlayed': info['current'],
        }
        del self._active[node_id]
        return result


def test_recorder():
    print("=" * 50)
    print("测试数据录制功能")
    print("=" * 50)
    
    recorder = SimpleRecorder()
    node_id = "test-save"
    
    print("\n1. 开始录制...")
    result = recorder.start(node_id, "demo.csv")
    print(f"   ✓ {result}")
    
    print("\n2. 写入100个样本...")
    for i in range(100):
        channels = [i * 1.5 + j for j in range(8)]
        recorder.write(node_id, 1707753600000 + i * 1000, channels)
    print("   ✓ 写入完成")
    
    print("\n3. 停止录制...")
    result = recorder.stop(node_id)
    print(f"   ✓ {result}")
    
    return "demo.csv"


def test_replayer(filename):
    print("\n" + "=" * 50)
    print("测试数据回放功能")
    print("=" * 50)
    
    replayer = SimpleReplayer()
    node_id = "test-replay"
    
    print(f"\n1. 开始回放: {filename}...")
    result = replayer.start(node_id, filename, loop=False)
    print(f"   ✓ {result}")
    
    print("\n2. 读取前5个样本...")
    for i in range(5):
        sample = replayer.read(node_id)
        if sample:
            print(f"   样本{i}: ts={sample['timestamp']}, ch1={sample['channels'][0]:.2f}")
    
    print("\n3. 读取剩余样本...")
    count = 5
    while True:
        sample = replayer.read(node_id)
        if sample is None:
            break
        count += 1
    print(f"   ✓ 总共读取 {count} 个样本")
    
    print("\n4. 停止回放...")
    result = replayer.stop(node_id)
    print(f"   ✓ {result}")


def test_loop(filename):
    print("\n" + "=" * 50)
    print("测试循环回放功能")
    print("=" * 50)
    
    replayer = SimpleReplayer()
    node_id = "test-loop"
    
    print("\n1. 开始循环回放...")
    result = replayer.start(node_id, filename, loop=True)
    print(f"   ✓ {result}")
    
    print("\n2. 读取120个样本（测试循环）...")
    for i in range(120):
        sample = replayer.read(node_id)
        if i < 3 or i >= 117:
            print(f"   样本{i}: ts={sample['timestamp']}, ch1={sample['channels'][0]:.2f}")
    print("   ✓ 循环回放正常工作（读取超过文件总量的样本）")
    
    replayer.stop(node_id)


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("EEG 数据保存与回放功能独立测试")
    print("=" * 60)
    
    try:
        filename = test_recorder()
        test_replayer(filename)
        test_loop(filename)
        
        print("\n" + "=" * 60)
        print("✅ 所有测试通过!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
