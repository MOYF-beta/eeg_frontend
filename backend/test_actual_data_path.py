#!/usr/bin/env python3
"""测试实际WebSocket数据路径"""

import sys
import os
import json

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 模拟WebSocket消费者的数据生成逻辑
def simulate_data_generation():
    """模拟WebSocket数据生成逻辑"""
    print("模拟WebSocket数据生成逻辑...")
    
    # 加载计算图数据
    graph_file = "eeg_app/graph_data.json"
    with open(graph_file, 'r', encoding='utf-8') as f:
        graph = json.load(f)
    
    nodes = graph.get('nodes', [])
    
    # 查找SOURCE节点
    source_nodes = [node for node in nodes if node.get('type') == 'SOURCE']
    print(f"找到 {len(source_nodes)} 个SOURCE节点")
    
    if source_nodes:
        source_node = source_nodes[0]
        device_id = source_node.get('params', {}).get('deviceId')
        print(f"SOURCE节点设备ID: {device_id}")
        
        if device_id:
            print(f"将使用设备配置生成信号: {device_id}")
        else:
            print("警告: SOURCE节点没有deviceId参数")
            print(f"节点参数: {source_node.get('params', {})}")
    else:
        print("警告: 没有找到SOURCE节点")
    
    # 检查节点数据
    print("\n计算图节点信息:")
    for node in nodes:
        if node.get('type') in ['SOURCE', 'OSC']:
            print(f"  类型: {node.get('type')}, ID: {node.get('id')}, 名称: {node.get('name')}")
            if node.get('type') == 'SOURCE':
                print(f"    参数: {node.get('params', {})}")

if __name__ == "__main__":
    print("=" * 60)
    print("WebSocket数据路径测试")
    print("=" * 60)
    
    simulate_data_generation()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)