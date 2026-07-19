/**
 * graphValidation.ts — 计算图合法性校验
 *
 * 在冻结 / 运行 / 导入前对整图做结构级校验，防止产生非法计算图：
 * - SOURCE 未绑定设备（会静默退化为后端合成方波，产生误导性数据）
 * - 多个 SOURCE 绑定同一设备（同一数据流被多处独立消费，行为未定义）
 * - REPLAY 未选择回放文件
 * - 图存在环（后端仅打印警告，拓扑序不确定）
 * - OUTPUT 作为边的源（OUTPUT 无输出端口）
 * - 边端口缺失
 */

import type { GraphEdge, GraphNode } from './graph';

export interface GraphIssue {
  nodeId?: string;
  message: string;
}

export interface GraphValidationResult {
  errors: GraphIssue[];
  warnings: GraphIssue[];
}

/** 检测有向图是否存在环（DFS 三色标记） */
export function hasCycle(nodes: GraphNode[], edges: GraphEdge[]): boolean {
  const adj = new Map<string, string[]>();
  nodes.forEach((n) => adj.set(n.id, []));
  edges.forEach((e) => {
    if (adj.has(e.source)) adj.get(e.source)!.push(e.target);
  });

  const WHITE = 0, GRAY = 1, BLACK = 2;
  const color = new Map<string, number>();
  nodes.forEach((n) => color.set(n.id, WHITE));

  const dfs = (id: string): boolean => {
    color.set(id, GRAY);
    for (const next of adj.get(id) || []) {
      const c = color.get(next);
      if (c === GRAY) return true;
      if (c === WHITE && dfs(next)) return true;
    }
    color.set(id, BLACK);
    return false;
  };

  for (const n of nodes) {
    if (color.get(n.id) === WHITE && dfs(n.id)) return true;
  }
  return false;
}

/** 整图校验。nodeLabel 用于把节点 id 转成用户可读的名称。 */
export function validateGraph(
  nodes: GraphNode[],
  edges: GraphEdge[],
  nodeLabel?: (node: GraphNode) => string,
): GraphValidationResult {
  const errors: GraphIssue[] = [];
  const warnings: GraphIssue[] = [];
  const label = (n: GraphNode) => (nodeLabel ? nodeLabel(n) : n.name || n.id);
  const byId = new Map(nodes.map((n) => [n.id, n]));

  // 1. 节点级检查
  const deviceBindCount = new Map<string, string[]>();
  for (const node of nodes) {
    if (node.type === 'SOURCE') {
      const deviceId = node.deviceId || (node.params?.deviceId as string | undefined);
      if (!deviceId) {
        warnings.push({
          nodeId: node.id,
          message: `「${label(node)}」未绑定设备：运行时将输出后端合成的测试方波而非真实数据，请绑定设备或改用 REPLAY 节点`,
        });
      } else {
        const list = deviceBindCount.get(deviceId) || [];
        list.push(node.id);
        deviceBindCount.set(deviceId, list);
      }
    }
    if (node.type === 'REPLAY') {
      const filePath = String(node.params?.filePath || '').trim();
      if (!filePath) {
        errors.push({ nodeId: node.id, message: `「${label(node)}」未选择回放文件` });
      }
    }
  }

  // 2. 多 SOURCE 绑同一设备
  for (const [deviceId, nodeIds] of deviceBindCount) {
    if (nodeIds.length > 1) {
      const names = nodeIds.map((id) => `「${label(byId.get(id)!)}」`).join('、');
      errors.push({
        nodeId: nodeIds[0],
        message: `设备 ${deviceId} 被多个节点绑定：${names}。同一设备数据流只能有一个 SOURCE`,
      });
    }
  }

  // 3. 边级检查
  for (const edge of edges) {
    const source = byId.get(edge.source);
    const target = byId.get(edge.target);
    if (!source || !target) {
      errors.push({ message: `边 ${edge.id} 引用了不存在的节点` });
      continue;
    }
    if (source.type === 'OUTPUT') {
      errors.push({
        nodeId: source.id,
        message: `「${label(source)}」是输出终端，没有输出端口，不能作为边的起点`,
      });
    }
    if (!edge.sourcePort || !edge.targetPort) {
      errors.push({ message: `「${label(source)}」→「${label(target)}」的边缺少端口信息` });
    }
  }

  // 4. 环检测
  if (hasCycle(nodes, edges)) {
    errors.push({ message: '计算图存在环路，拓扑执行顺序无法确定，请断开其中一条边' });
  }

  return { errors, warnings };
}

/** 把校验结果格式化为单行文本（用于 toast / alert） */
export function formatIssues(issues: GraphIssue[], max = 3): string {
  const head = issues.slice(0, max).map((i) => i.message).join('；');
  const more = issues.length > max ? ` 等 ${issues.length} 项` : '';
  return head + more;
}
