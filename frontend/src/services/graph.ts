export type GraphNodeType =
  | 'SOURCE'
  | 'REPLAY'
  | 'FILTER'
  | 'DOWNSAMPLE'
  | 'UPSAMPLE'
  | 'SUM'
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

const protocol = window.location.protocol;
const host = 'localhost';
const baseUrl = `${protocol}//${host}:8000/api`;

export async function fetchGraph(): Promise<GraphPayload> {
  const res = await fetch(`${baseUrl}/graph/`);
  if (!res.ok) throw new Error('Failed to load graph');
  return res.json();
}

export async function saveGraph(payload: GraphPayload) {
  const res = await fetch(`${baseUrl}/graph/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.errors?.[0] || 'Failed to save graph');
  }
  return res.json();
}

export async function setGraphFrozen(frozen: boolean) {
  const res = await fetch(`${baseUrl}/graph/freeze/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ frozen }),
  });
  if (!res.ok) throw new Error('Failed to update freeze');
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

export async function debugGraph(payload: GraphPayload) {
  const res = await fetch(`${baseUrl}/graph/debug/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to send debug payload');
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
