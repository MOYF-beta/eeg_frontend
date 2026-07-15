import logging
logger = logging.getLogger(__name__)
"""数据回放管理器 - 实现REPLAY节点的数据文件回放功能"""

import csv
import time
from pathlib import Path
from typing import Dict, Iterator, List, Optional

from .data_recorder import get_data_dir

# 当前活跃的回放会话
_active_replays: Dict[str, Dict] = {}


def start_replay(node_id: str, filename: str, loop: bool = False, speed: float = 1.0) -> Dict:
    """开始回放数据
    
    Args:
        node_id: REPLAY节点ID
        filename: 数据文件名
        loop: 是否循环播放
        speed: 播放速度倍率 (1.0 = 正常速度)
        
    Returns:
        回放会话信息
    """
    global _active_replays
    
    # 如果已经在回放，先停止
    if node_id in _active_replays:
        stop_replay(node_id)
    
    # 查找文件
    filepath = get_data_dir() / filename
    if not filepath.exists():
        # 尝试其他路径
        filepath = Path(filename)
        if not filepath.exists():
            return {'ok': False, 'error': f'File not found: {filename}'}
    
    try:
        # 读取文件头信息
        sample_count = 0
        channels = 8
        
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header:
                # 统计通道数 (减去timestamp和sample_idx列)
                channels = len(header) - 2
            # 统计样本数
            for _ in reader:
                sample_count += 1
        
        _active_replays[node_id] = {
            'filepath': str(filepath),
            'filename': filepath.name,
            'loop': loop,
            'speed': speed,
            'sample_count': sample_count,
            'channels': channels,
            'current_idx': 0,
            'start_time': time.time(),
            'file_handle': None,
            'reader': None,
            'last_timestamp': None,
        }
        
        # 打开文件准备读取
        _active_replays[node_id]['file_handle'] = open(filepath, 'r', encoding='utf-8')
        _active_replays[node_id]['reader'] = csv.reader(_active_replays[node_id]['file_handle'])
        # 跳过表头
        next(_active_replays[node_id]['reader'], None)
        
        logger.debug(f'[DataReplay] Started replay from {filepath} ({sample_count} samples, {channels} channels)')
        return {
            'ok': True,
            'filename': filepath.name,
            'sampleCount': sample_count,
            'channels': channels,
            'nodeId': node_id,
        }
        
    except Exception as e:
        logger.debug(f'[DataReplay] Failed to start replay: {e}')
        return {'ok': False, 'error': str(e)}


def read_next_sample(node_id: str) -> Optional[Dict]:
    """读取下一个样本
    
    Args:
        node_id: REPLAY节点ID
        
    Returns:
        样本数据字典，包含timestamp和channels
        如果回放结束返回None
    """
    global _active_replays
    
    if node_id not in _active_replays:
        return None
    
    replay_info = _active_replays[node_id]
    
    try:
        row = next(replay_info['reader'], None)
        
        # 文件结束
        if row is None:
            if replay_info['loop']:
                # 循环播放：重新开始
                replay_info['file_handle'].close()
                replay_info['file_handle'] = open(replay_info['filepath'], 'r', encoding='utf-8')
                replay_info['reader'] = csv.reader(replay_info['file_handle'])
                next(replay_info['reader'], None)  # 跳过表头
                replay_info['current_idx'] = 0
                row = next(replay_info['reader'], None)
                if row is None:
                    return None
            else:
                return None
        
        # 解析数据
        # CSV格式: timestamp, sample_idx, ch1, ch2, ch3, ...
        timestamp = int(row[0])
        channels = [float(v) for v in row[2:]]
        
        replay_info['current_idx'] += 1
        replay_info['last_timestamp'] = timestamp
        
        return {
            'timestamp': timestamp,
            'channels': channels,
            'sampleIdx': replay_info['current_idx'],
        }
        
    except Exception as e:
        logger.debug(f'[DataReplay] Read error: {e}')
        return None


def get_replay_status(node_id: str) -> Optional[Dict]:
    """获取回放状态"""
    global _active_replays
    
    if node_id not in _active_replays:
        return None
    
    info = _active_replays[node_id]
    return {
        'filename': info['filename'],
        'currentIdx': info['current_idx'],
        'sampleCount': info['sample_count'],
        'progress': round(info['current_idx'] / info['sample_count'] * 100, 1) if info['sample_count'] > 0 else 0,
        'loop': info['loop'],
        'speed': info['speed'],
    }


def stop_replay(node_id: str) -> Dict:
    """停止回放
    
    Args:
        node_id: REPLAY节点ID
        
    Returns:
        回放结果
    """
    global _active_replays
    
    if node_id not in _active_replays:
        return {'ok': False, 'error': 'Not replaying'}
    
    replay_info = _active_replays[node_id]
    
    try:
        if replay_info['file_handle']:
            replay_info['file_handle'].close()
        
        result = {
            'ok': True,
            'filename': replay_info['filename'],
            'samplesPlayed': replay_info['current_idx'],
            'progress': round(replay_info['current_idx'] / replay_info['sample_count'] * 100, 1) if replay_info['sample_count'] > 0 else 0,
        }
        
        del _active_replays[node_id]
        logger.debug(f'[DataReplay] Stopped replay: {result}')
        return result
        
    except Exception as e:
        logger.debug(f'[DataReplay] Error stopping replay: {e}')
        return {'ok': False, 'error': str(e)}


def is_replaying(node_id: str) -> bool:
    """检查是否正在回放"""
    return node_id in _active_replays


def list_replayable_files() -> List[Dict]:
    """列出可回放的文件列表"""
    from .data_recorder import list_saved_files
    return list_saved_files()
