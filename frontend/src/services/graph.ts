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
  | 'OUTPUT'
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
