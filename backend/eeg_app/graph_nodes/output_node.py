from __future__ import annotations

from typing import Any, Dict

from .base import GraphNode, NodeExecutionContext, NodeInputs, NodeOutputs, pick_signal_by_port


class OutputNode(GraphNode):
    """统一的输出节点：可绑定示波器、频谱仪、录制文件。

    计算逻辑为透传输入信号。
    功能开关（saveEnabled 等）由 graph_consumer_v2.py 在运行时根据 node.params 处理。
    """

    node_type = 'OUTPUT'

    def compute(self, node: Dict[str, Any], inputs: NodeInputs, context: NodeExecutionContext) -> NodeOutputs:
        return {'in': pick_signal_by_port(inputs, 'in')}
