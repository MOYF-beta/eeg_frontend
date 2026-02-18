"""数据保存管理器 - 实现SAVE节点的数据文件保存功能"""

import csv
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# 数据保存目录
DATA_DIR = Path(os.path.dirname(__file__)).parent / 'saved_data'
DATA_DIR.mkdir(exist_ok=True)

# 当前打开的文件句柄
_active_writers: Dict[str, Dict] = {}


def get_data_dir() -> Path:
    """获取数据保存目录"""
    return DATA_DIR


def start_recording(node_id: str, filename: Optional[str] = None, format: str = 'CSV') -> Dict:
    """开始录制数据
    
    Args:
        node_id: SAVE节点ID
        filename: 文件名（可选，默认自动生成）
        format: 文件格式 (CSV, EDF, NPY)
        
    Returns:
        录制会话信息
    """
    global _active_writers
    
    # 如果已经在录制，先停止
    if node_id in _active_writers:
        stop_recording(node_id)
    
    # 生成文件名
    if not filename:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"eeg_data_{timestamp}.csv"
    
    # 确保扩展名正确
    if format == 'CSV' and not filename.endswith('.csv'):
        filename += '.csv'
    elif format == 'EDF' and not filename.endswith('.edf'):
        filename += '.edf'
    elif format == 'NPY' and not filename.endswith('.npy'):
        filename += '.npy'
    
    filepath = DATA_DIR / filename
    
    try:
        if format == 'CSV':
            f = open(filepath, 'w', newline='', encoding='utf-8')
            writer = csv.writer(f)

            _active_writers[node_id] = {
                'file': f,
                'writer': writer,
                'format': 'CSV',
                'filepath': str(filepath),
                'start_time': time.time(),
                'sample_count': 0,
                'channel_count': None,
                'header_written': False,
            }
        else:
            # TODO: 实现EDF和NPY格式
            return {'ok': False, 'error': f'Format {format} not yet implemented'}
        
        print(f'[DataRecorder] Started recording to {filepath}')
        return {
            'ok': True,
            'filepath': str(filepath),
            'format': format,
            'nodeId': node_id,
        }
        
    except Exception as e:
        print(f'[DataRecorder] Failed to start recording: {e}')
        return {'ok': False, 'error': str(e)}


def write_sample(node_id: str, timestamp: float, channels: List[float]) -> bool:
    """写入一个样本到文件
    
    Args:
        node_id: SAVE节点ID
        timestamp: 时间戳（毫秒）
        channels: 通道数据列表
        
    Returns:
        是否成功
    """
    global _active_writers
    
    if node_id not in _active_writers:
        return False
    
    writer_info = _active_writers[node_id]
    
    try:
        if writer_info['format'] == 'CSV':
            if not writer_info.get('header_written'):
                channel_count = len(channels)
                writer_info['channel_count'] = channel_count
                writer_info['writer'].writerow(['timestamp', 'sample_idx'] + [f'ch{i+1}' for i in range(channel_count)])
                writer_info['header_written'] = True

            writer_info['writer'].writerow([
                int(timestamp),
                writer_info['sample_count'],
            ] + [round(ch, 6) for ch in channels])
            writer_info['sample_count'] += 1
            
            # 每100个样本刷新一次
            if writer_info['sample_count'] % 100 == 0:
                writer_info['file'].flush()
        
        return True
        
    except Exception as e:
        print(f'[DataRecorder] Write error: {e}')
        return False


def stop_recording(node_id: str) -> Dict:
    """停止录制
    
    Args:
        node_id: SAVE节点ID
        
    Returns:
        录制结果统计
    """
    global _active_writers
    
    if node_id not in _active_writers:
        return {'ok': False, 'error': 'Not recording'}
    
    writer_info = _active_writers[node_id]
    
    try:
        writer_info['file'].close()
        duration = time.time() - writer_info['start_time']
        
        result = {
            'ok': True,
            'filepath': writer_info['filepath'],
            'format': writer_info['format'],
            'sampleCount': writer_info['sample_count'],
            'duration': round(duration, 2),
            'sampleRate': round(writer_info['sample_count'] / duration, 2) if duration > 0 else 0,
        }
        
        del _active_writers[node_id]
        print(f'[DataRecorder] Stopped recording: {result}')
        return result
        
    except Exception as e:
        print(f'[DataRecorder] Error stopping recording: {e}')
        return {'ok': False, 'error': str(e)}


def is_recording(node_id: str) -> bool:
    """检查是否正在录制"""
    return node_id in _active_writers


def get_active_recordings() -> List[Dict]:
    """获取所有活跃的录制会话"""
    return [
        {
            'nodeId': node_id,
            'filepath': info['filepath'],
            'format': info['format'],
            'sampleCount': info['sample_count'],
            'duration': round(time.time() - info['start_time'], 2),
        }
        for node_id, info in _active_writers.items()
    ]


def list_saved_files() -> List[Dict]:
    """列出所有已保存的数据文件"""
    files = []
    try:
        for filepath in sorted(DATA_DIR.glob('*.csv'), key=lambda p: p.stat().st_mtime, reverse=True):
            stat = filepath.stat()
            files.append({
                'filename': filepath.name,
                'size': stat.st_size,
                'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
    except Exception as e:
        print(f'[DataRecorder] Error listing files: {e}')
    return files


def get_file_path(filename: str) -> Optional[Path]:
    """获取文件的完整路径"""
    filepath = DATA_DIR / filename
    if filepath.exists():
        return filepath
    return None
