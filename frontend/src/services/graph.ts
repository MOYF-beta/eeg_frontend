export type GraphNodeType =
  | 'SOURCE'
  | 'REPLAY'
  | 'FILTER'
  | 'DOWNSAMPLE'
  | 'UPSAMPLE'
  | 'SUM'
  | 'AVERAGE'
  | 'SPLIT'
  | 'MERGE'
  | 'OSC'
  | 'SPECTRUM'
  | 'SAVE'
  | 'CUSTOM_PYFUNC'
  | 'CUSTOM_CONV';

export type GraphNode = {
  id: string;
  type: GraphNodeType;
  name: string;
  x: number;
  y: number;
  params: Record<string, unknown>;
  deviceId?: string; // SOURCE/REPLAY 节点绑定的设备ID
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  sourcePort?: string;
  targetPort?: string;
};

export type GraphPayload = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  frozen: boolean;
  revision?: number;
  persistedRevision?: number;
  baseRevision?: number;
};

export type GraphSyncResponse = {
  ok: boolean;
  conflict?: boolean;
  revision: number;
  persistedRevision: number;
  graph?: GraphPayload;
  error?: string;
};

export type PythonPrototypePayload = {
  inputCount: number;
  outputCount: number;
  functionName?: string;
  inputNames?: string[] | string;
  outputNames?: string[] | string;
  editableCode?: string;
};

export type PythonPrototypeSpec = {
  code: string;
  headerCode: string;
  footerCode: string;
  editableCode: string;
  signature: string;
  functionName: string;
  inputNames: string[];
  outputNames: string[];
};

const baseUrl = '/api';

export async function fetchGraph(): Promise<GraphPayload> {
  const res = await fetch(`${baseUrl}/graph/`);
  if (!res.ok) throw new Error('Failed to load graph');
  return res.json();
}

export async function syncGraph(payload: GraphPayload, baseRevision?: number): Promise<GraphSyncResponse> {
  const body: GraphPayload = {
    ...payload,
    baseRevision: typeof baseRevision === 'number' ? baseRevision : undefined,
  };
  const res = await fetch(`${baseUrl}/graph/sync/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (res.status === 409) {
    const data = await res.json().catch(() => ({}));
    return {
      ok: false,
      conflict: true,
      revision: Number(data?.revision || 0),
      persistedRevision: Number(data?.persistedRevision || 0),
      graph: data?.graph,
      error: data?.error || 'revision conflict',
    };
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    // 检查是否是运行时错误
    if (res.status === 403) {
      throw new Error('计算图正在运行中，无法保存。请先停止运行再保存。');
    }
    throw new Error(data?.errors?.[0] || data?.detail || 'Failed to save graph');
  }
  return res.json();
}

export async function persistGraph(): Promise<{ ok: boolean; revision: number; persistedRevision: number }> {
  const res = await fetch(`${baseUrl}/graph/save/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.errors?.[0] || data?.detail || 'Failed to persist graph');
  }
  return res.json();
}

export async function setGraphFrozen(frozen: boolean) {
  const res = await fetch(`${baseUrl}/graph/freeze/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ frozen }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    // 检查是否是运行时错误
    if (res.status === 403) {
      throw new Error('计算图正在运行中，无法冻结/解冻。请先停止运行再操作。');
    }
    throw new Error(data?.errors?.[0] || data?.detail || 'Failed to update freeze');
  }
  return res.json();
}

export async function runGraph(mode: 'live' | 'offline' = 'live') {
  const res = await fetch(`${baseUrl}/graph/run/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.error || 'Failed to run graph');
  }
  return res.json();
}

export async function stopGraph() {
  const res = await fetch(`${baseUrl}/graph/run/`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to stop graph');
  return res.json();
}

export async function getGraphRuntimeState() {
  const res = await fetch(`${baseUrl}/graph/run/`, { method: 'GET' });
  if (!res.ok) throw new Error('Failed to get runtime state');
  return res.json();
}

export async function generateGraphPythonPrototype(payload: PythonPrototypePayload): Promise<PythonPrototypeSpec> {
  const res = await fetch(`${baseUrl}/graph/python/prototype/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to generate python prototype');
  return await res.json();
}

export async function fetchGraphPythonLibrary(): Promise<Record<string, string>> {
  const res = await fetch(`${baseUrl}/graph/python/library/`);
  if (!res.ok) throw new Error('Failed to load python code library');
  const data = await res.json();
  return (data?.library || {}) as Record<string, string>;
}
