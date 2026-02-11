export type GraphNodeType =
  | 'SOURCE'
  | 'REPLAY'
  | 'FILTER'
  | 'SUM'
  | 'SPLIT'
  | 'MERGE'
  | 'OSC'
  | 'SPECTRUM'
  | 'SAVE';

export type GraphNode = {
  id: string;
  type: GraphNodeType;
  name: string;
  x: number;
  y: number;
  params: Record<string, unknown>;
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
};

export type GraphPayload = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  frozen: boolean;
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

export async function runGraph() {
  const res = await fetch(`${baseUrl}/graph/run/`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to run graph');
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
