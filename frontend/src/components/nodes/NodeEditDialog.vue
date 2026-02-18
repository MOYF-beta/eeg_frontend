<template>
  <!-- 对话框模式 -->
  <v-dialog v-if="!isSidebarMode" v-model="show" max-width="600" persistent>
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon :color="iconColor" class="mr-2">{{ icon }}</v-icon>
        {{ isReadOnly ? '查看节点' : '编辑节点' }} - {{ nodeTypeName }}
        <v-spacer />
        <v-btn icon variant="text" size="small" @click="close">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      
      <v-divider />
      
      <v-card-text class="pt-4">
        <!-- 节点编辑内容 -->
        <div class="node-edit-content">
          <!-- 通用字段：名称 -->
          <v-text-field
            v-model="form.name"
            label="节点名称"
            density="compact"
            variant="outlined"
            class="mb-4"
            :readonly="isReadOnly"
            :disabled="isReadOnly"
          />
          
          <!-- 动态表单内容 -->
          <NodeEditFormContent
            :node-type="nodeType"
            :form="form"
            :is-read-only="isReadOnly"
            :selected-device-id="selectedDeviceId"
            :bound-oscilloscope-id="boundOscilloscopeId"
            :channel-names="channelNames"
            :sum-inputs="sumInputs"
            :split-outputs="splitOutputs"
            :merge-inputs="mergeInputs"
            :input-names-text="inputNamesText"
            :output-names-text="outputNamesText"
            :kernel-text="kernelText"
            :params-json="paramsJson"
            :json-error="jsonError"
            @update:selected-device-id="selectedDeviceId = $event"
            @update:bound-oscilloscope-id="boundOscilloscopeId = $event"
            @update:channel-names="channelNames = $event"
            @update:sum-inputs="sumInputs = $event"
            @update:split-outputs="splitOutputs = $event"
            @update:merge-inputs="mergeInputs = $event"
            @update:input-names-text="inputNamesText = $event"
            @update:output-names-text="outputNamesText = $event"
            @update:kernel-text="kernelText = $event"
            @update:params-json="paramsJson = $event"
            @add-channel-name="addChannelName"
            @remove-channel-name="removeChannelName"
            @add-sum-input="addSumInput"
            @remove-sum-input="removeSumInput"
            @add-split-output="addSplitOutput"
            @remove-split-output="removeSplitOutput"
            @add-merge-input="addMergeInput"
            @remove-merge-input="removeMergeInput"
            @import-python-file="importPythonFile"
          />
        </div>
      </v-card-text>
      
      <v-divider />
      
      <v-card-actions>
        <v-btn variant="text" @click="close">{{ isReadOnly ? '关闭' : '取消' }}</v-btn>
        <v-spacer />
        <v-btn v-if="!isReadOnly" color="primary" @click="save">保存</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
  
  <!-- 边栏模式 -->
  <div v-else class="node-edit-sidebar">
    <div class="sidebar-header">
      <v-icon :color="iconColor" class="mr-2">{{ icon }}</v-icon>
      <span class="sidebar-title">{{ isReadOnly ? '查看节点' : '编辑节点' }} - {{ nodeTypeName }}</span>
    </div>
    
    <v-divider />
    
    <div class="sidebar-content">
      <!-- 节点编辑内容 -->
      <div class="node-edit-content">
        <!-- 通用字段：名称 -->
        <v-text-field
          v-model="form.name"
          label="节点名称"
          density="compact"
          variant="outlined"
          class="mb-4"
          :readonly="isReadOnly"
          :disabled="isReadOnly"
        />
        
        <!-- 动态表单内容 -->
        <NodeEditFormContent
          :node-type="nodeType"
          :form="form"
          :is-read-only="isReadOnly"
          :selected-device-id="selectedDeviceId"
          :bound-oscilloscope-id="boundOscilloscopeId"
          :channel-names="channelNames"
          :sum-inputs="sumInputs"
          :split-outputs="splitOutputs"
          :merge-inputs="mergeInputs"
          :input-names-text="inputNamesText"
          :output-names-text="outputNamesText"
          :kernel-text="kernelText"
          :params-json="paramsJson"
          :json-error="jsonError"
          @update:selected-device-id="selectedDeviceId = $event"
          @update:bound-oscilloscope-id="boundOscilloscopeId = $event"
          @update:channel-names="channelNames = $event"
          @update:sum-inputs="sumInputs = $event"
          @update:split-outputs="splitOutputs = $event"
          @update:merge-inputs="mergeInputs = $event"
          @update:input-names-text="inputNamesText = $event"
          @update:output-names-text="outputNamesText = $event"
          @update:kernel-text="kernelText = $event"
          @update:params-json="paramsJson = $event"
          @add-channel-name="addChannelName"
          @remove-channel-name="removeChannelName"
          @add-sum-input="addSumInput"
          @remove-sum-input="removeSumInput"
          @add-split-output="addSplitOutput"
          @remove-split-output="removeSplitOutput"
          @add-merge-input="addMergeInput"
          @remove-merge-input="removeMergeInput"
          @import-python-file="importPythonFile"
        />
      </div>
    </div>
    
    <v-divider v-if="!isReadOnly" />
    
    <div v-if="!isReadOnly" class="sidebar-actions">
      <v-btn color="primary" @click="save" block>保存</v-btn>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue';
import { basicSetup, EditorView } from 'codemirror';
import { javascript } from '@codemirror/lang-javascript';
import { sessionStore } from '../../services/sessionStore';
import { fetchGraphPythonLibrary, generateGraphPythonPrototype } from '../../services/graph';
import NodeEditFormContent from './NodeEditFormContent.vue';

interface GraphNode {
  id: string;
  type: string;
  name: string;
  params: Record<string, any>;
  deviceId?: string;
  x?: number;
  y?: number;
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
  sourcePort?: string;
  targetPort?: string;
}

const props = defineProps<{
  modelValue: boolean;
  nodeData: GraphNode | null;
  allNodes?: GraphNode[];
  allEdges?: GraphEdge[];
  mode?: 'dialog' | 'sidebar'; // 新增：显示模式
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
  (e: 'save', data: { name: string; params: Record<string, any>; deviceId?: string | null }): void;
  (e: 'bindOscilloscope', data: { nodeId: string; oscId: string | null }): void;
}>();

// 模式检测
const isSidebarMode = computed(() => props.mode === 'sidebar');

// 在边栏模式下，始终显示内容；在对话框模式下，使用modelValue控制显示
const show = computed({
  get: () => isSidebarMode.value ? true : props.modelValue,
  set: (val) => {
    if (!isSidebarMode.value) {
      emit('update:modelValue', val);
    }
  },
});

const nodeType = computed(() => props.nodeData?.type || '');

const typeInfo: Record<string, { name: string; icon: string; color: string }> = {
  SOURCE: { name: '数据源', icon: 'mdi-database', color: 'primary' },
  REPLAY: { name: '回放', icon: 'mdi-play-circle', color: 'primary' },
  FILTER: { name: '滤波器', icon: 'mdi-filter', color: 'success' },
  SUM: { name: '求和器', icon: 'mdi-plus-circle', color: 'purple' },
  SPLIT: { name: '分离器', icon: 'mdi-call-split', color: 'warning' },
  MERGE: { name: '合并器', icon: 'mdi-call-merge', color: 'orange' },
  OSC: { name: '示波器', icon: 'mdi-chart-line', color: 'teal' },
  SPECTRUM: { name: '频谱', icon: 'mdi-chart-bar', color: 'indigo' },
  SAVE: { name: '保存', icon: 'mdi-content-save', color: 'pink' },
  CUSTOM_PYFUNC: { name: 'Python函数', icon: 'mdi-language-python', color: 'deep-purple' },
  CUSTOM_CONV: { name: '卷积节点', icon: 'mdi-waveform', color: 'cyan-darken-2' },
};

const nodeTypeName = computed(() => typeInfo[nodeType.value]?.name || '节点');
const icon = computed(() => typeInfo[nodeType.value]?.icon || 'mdi-cube');
const iconColor = computed(() => typeInfo[nodeType.value]?.color || 'grey');

const form = ref({
  name: '',
  params: {} as Record<string, any>,
});

const paramsJson = ref('{}');
const jsonError = ref('');

interface SumInputConfig {
  label: string;
  weight: number;
}

interface MergeInputConfig {
  label: string;
  gain: number;
}

interface SplitOutputConfig {
  label: string;
  channelIndices: string;
}

const sumInputs = ref<SumInputConfig[]>([]);
const mergeInputs = ref<MergeInputConfig[]>([]);
const splitOutputs = ref<SplitOutputConfig[]>([]);
const pythonCode = ref('');
const pythonHeaderCode = ref('');
const pythonFooterCode = ref('');
const defaultCodeLibrary = ref<Record<string, string>>({});
const pythonFileInput = ref<HTMLInputElement | null>(null);
const codeEditorHost = ref<HTMLDivElement | null>(null);
let codeEditor: EditorView | null = null;
const kernelText = ref('0.25,0.5,0.25');
const inputNamesText = ref('');
const outputNamesText = ref('');

// 通道相关
const channelNames = ref<string[]>(['CH1', 'CH2', 'CH3', 'CH4', 'CH5', 'CH6', 'CH7', 'CH8']);
const selectedChannels = ref<number[]>([0, 1, 2, 3, 4, 5, 6, 7]);
const availableChannels = ref<string[]>(['CH1', 'CH2', 'CH3', 'CH4', 'CH5', 'CH6', 'CH7', 'CH8']);

// 示波器绑定
const boundOscilloscopeId = ref<string | null>(null);
const availableOscilloscopes = computed(() => {
  return sessionStore.getOscilloscopes();
});

// 设备选择
const selectedDeviceId = ref<string | null>(null);

// 可用设备列表
const availableDevices = computed(() => {
  const devices = sessionStore.getDevices();
  return devices.map(d => ({
    id: d.id,
    name: d.name,
    displayName: `${d.name} (${d.status === 'online' ? '在线' : '离线'})`,
    status: d.status,
  }));
});

// 检查设备是否已绑定到其他 SOURCE 节点
function isDeviceBoundToOtherNode(deviceId: string): boolean {
  if (!props.allNodes || !props.nodeData) return false;
  
  return props.allNodes.some(node => {
    // 跳过当前节点
    if (node.id === props.nodeData?.id) return false;
    // 只检查 SOURCE 类型节点
    if (node.type !== 'SOURCE') return false;
    // 检查是否绑定了此设备
    return node.deviceId === deviceId || node.params?.deviceId === deviceId;
  });
}

// 获取上游节点
function getUpstreamSource(nodeId: string): GraphNode | null {
  if (!props.allEdges || !props.allNodes) return null;
  
  // 找到指向当前节点的边
  const incomingEdge = props.allEdges.find(e => e.target === nodeId);
  if (!incomingEdge) return null;
  
  // 找到源节点
  const sourceNode = props.allNodes.find(n => n.id === incomingEdge.source);
  if (!sourceNode) return null;
  
  // 如果是SOURCE节点，返回它
  if (sourceNode.type === 'SOURCE') {
    return sourceNode;
  }
  
  // 否则递归查找
  return getUpstreamSource(sourceNode.id);
}

function getNodeById(nodeId: string): GraphNode | null {
  if (!props.allNodes) return null;
  return props.allNodes.find((n) => n.id === nodeId) || null;
}

function getIncomingEdge(nodeId: string): GraphEdge | null {
  if (!props.allEdges) return null;
  return props.allEdges.find((e) => e.target === nodeId) || null;
}

function parseIndices(raw: unknown): number[] {
  if (Array.isArray(raw)) {
    return raw
      .map((item) => Number(item))
      .filter((n) => Number.isInteger(n) && n >= 0);
  }
  if (typeof raw !== 'string') return [];
  return raw
    .replace(/，/g, ',')
    .split(',')
    .map((item) => Number(item.trim()))
    .filter((n) => Number.isInteger(n) && n >= 0);
}

function resolveNodeOutputChannels(nodeId: string, sourcePort?: string, visited = new Set<string>()): string[] {
  if (visited.has(nodeId)) return [];
  visited.add(nodeId);

  const node = getNodeById(nodeId);
  if (!node) return [];

  if (node.type === 'SOURCE') {
    const channelCount = Number(node.params?.channels || 8);
    const names = Array.isArray(node.params?.channelNames)
      ? node.params.channelNames.map((n: unknown) => String(n))
      : [];
    if (names.length > 0) return names;
    return Array.from({ length: channelCount }, (_, i) => `CH${i + 1}`);
  }

  if (node.type === 'FILTER' || node.type === 'OSC' || node.type === 'SPECTRUM' || node.type === 'SAVE') {
    const inEdge = getIncomingEdge(node.id);
    if (!inEdge) return [];
    return resolveNodeOutputChannels(inEdge.source, inEdge.sourcePort, visited);
  }

  if (node.type === 'SUM') {
    return [node.name || 'SUM'];
  }

  if (node.type === 'MERGE') {
    const incoming = (props.allEdges || [])
      .filter((e) => e.target === node.id)
      .sort((a, b) => (a.targetPort || '').localeCompare(b.targetPort || ''));
    const merged: string[] = [];
    incoming.forEach((edge) => {
      merged.push(...resolveNodeOutputChannels(edge.source, edge.sourcePort, new Set(visited)));
    });
    return merged;
  }

  if (node.type === 'SPLIT') {
    const inEdge = getIncomingEdge(node.id);
    const upstream = inEdge ? resolveNodeOutputChannels(inEdge.source, inEdge.sourcePort, visited) : [];
    const outputs = Array.isArray(node.params?.outputs) ? node.params.outputs : [];
    const portIdx = sourcePort
      ? Math.max(0, Number((sourcePort.match(/-(\d+)$/)?.[1] || '1')) - 1)
      : 0;
    const output = outputs[portIdx] as Record<string, unknown> | undefined;
    const indices = parseIndices(output?.channelIndices);
    const selected = indices.map((idx) => upstream[idx]).filter((name): name is string => Boolean(name));
    if (selected.length > 0) return selected;
    if (typeof output?.label === 'string' && output.label.trim() !== '') return [output.label.trim()];
    return upstream;
  }

  return [];
}

// 从上游节点获取通道信息
function updateChannelInfo() {
  if (!props.nodeData) return;

  const incoming = getIncomingEdge(props.nodeData.id);
  if (incoming) {
    const names = resolveNodeOutputChannels(incoming.source, incoming.sourcePort);
    if (names.length > 0) {
      availableChannels.value = names;
      return;
    }
  }

  const upstream = getUpstreamSource(props.nodeData.id);
  if (upstream) {
    const channelCount = upstream.params?.channels || 8;
    const upstreamChannelNames = upstream.params?.channelNames || [];

    availableChannels.value = Array.from({ length: channelCount }, (_, i) => {
      return upstreamChannelNames[i] || `CH${i + 1}`;
    });
    return;
  }

  availableChannels.value = ['CH1', 'CH2', 'CH3', 'CH4', 'CH5', 'CH6', 'CH7', 'CH8'];
}

function ensureVisualParamDefaults(type: string, params: Record<string, any>) {
  if (type === 'SOURCE') {
    params.sourceMode = params.sourceMode || 'live';
    params.filePath = String(params.filePath || '');
    params.loop = Boolean(params.loop || false);
    params.sampleRate = Math.max(1, Number(params.sampleRate || 1000));
    params.channels = Math.max(1, Number(params.channels || 8));
  }

  if (type === 'OSC') {
    params.saveEnabled = Boolean(params.saveEnabled || false);
    params.filename = String(params.filename || '');
    params.format = String(params.format || 'CSV');
  }

  if (type === 'SUM') {
    const legacyWeights = typeof params.weights === 'string'
      ? params.weights.split(',').map((w: string) => Number(w.trim())).filter((v: number) => !Number.isNaN(v))
      : [];
    const inputs = Array.isArray(params.inputs) ? params.inputs : [];
    const normalized = inputs.length > 0
      ? inputs.map((item: any, idx: number) => ({
          label: String(item?.label || `输入${idx + 1}`),
          weight: Number(item?.weight ?? 1),
        }))
      : (legacyWeights.length > 0
        ? legacyWeights.map((w: number, idx: number) => ({ label: `输入${idx + 1}`, weight: w }))
        : [{ label: '输入1', weight: 1 }, { label: '输入2', weight: 1 }]);
    sumInputs.value = normalized;
    params.inputs = normalized;
    delete params.weights;
  }

  if (type === 'MERGE') {
    const inputs = Array.isArray(params.inputs) ? params.inputs : [];
    const normalized = inputs.length > 0
      ? inputs.map((item: any, idx: number) => ({
          label: String(item?.label || `输入${idx + 1}`),
          gain: Number(item?.gain ?? 1),
        }))
      : [{ label: '输入1', gain: 1 }, { label: '输入2', gain: 1 }];
    mergeInputs.value = normalized;
    params.inputs = normalized;
    params.strategy = params.strategy || 'interleave';
  }

  if (type === 'SPLIT') {
    const outputs = Array.isArray(params.outputs) ? params.outputs : [];
    const legacy = typeof params.channelIndices === 'string' ? params.channelIndices : '';
    const normalized = outputs.length > 0
      ? outputs.map((item: any, idx: number) => ({
          label: String(item?.label || `输出${idx + 1}`),
          channelIndices: String(item?.channelIndices || ''),
        }))
      : [{ label: '输出1', channelIndices: legacy || '0,1,2,3' }];
    splitOutputs.value = normalized;
    params.outputs = normalized;
    delete params.channelIndices;
  }

  if (type === 'CUSTOM_PYFUNC') {
    params.portMode = params.portMode || 'fixed';
    params.inputCount = Math.max(1, Number(params.inputCount || 2));
    params.outputCount = Math.max(1, Number(params.outputCount || 1));
    params.functionName = String(params.functionName || 'process_generated');
    params.windowMode = params.windowMode || 'seconds';
    params.windowSeconds = Math.max(0.01, Number(params.windowSeconds || 1));
    params.windowPoints = Math.max(1, Number(params.windowPoints || 256));
    params.hopMode = params.hopMode || 'points';
    params.hopPoints = Math.max(1, Number(params.hopPoints || 1));
    params.hopMs = Math.max(1, Number(params.hopMs || 10));
    params.outputSampleRate = Math.max(1, Number(params.outputSampleRate || 100));
    if (!Array.isArray(params.inputNames)) {
      params.inputNames = [];
    }
    if (!Array.isArray(params.outputNames)) {
      params.outputNames = [];
    }
    params.pythonEditableCode = String(params.pythonEditableCode || '');
    params.pythonCode = String(params.pythonCode || '');
  }

  if (type === 'CUSTOM_CONV') {
    const kernel = Array.isArray(params.kernel) ? params.kernel : [0.25, 0.5, 0.25];
    params.kernel = kernel;
    params.pythonCode = String(params.pythonCode || '');
    kernelText.value = kernel.join(',');
  }
}

function destroyCodeEditor() {
  codeEditor?.destroy();
  codeEditor = null;
}

function createCodeEditor() {
  if (!codeEditorHost.value) return;
  destroyCodeEditor();
  codeEditor = new EditorView({
    doc: pythonCode.value || 'pass\n',
    extensions: [
      basicSetup,
      javascript(),
      EditorView.updateListener.of((update) => {
        if (update.docChanged) {
          pythonCode.value = update.state.doc.toString();
          if (nodeType.value === 'CUSTOM_PYFUNC') {
            form.value.params.pythonEditableCode = pythonCode.value;
          } else {
            form.value.params.pythonCode = pythonCode.value;
          }
        }
      }),
    ],
    parent: codeEditorHost.value,
  });
}

function syncEditorDoc(newDoc: string) {
  if (!codeEditor) return;
  const current = codeEditor.state.doc.toString();
  if (current === newDoc) return;
  codeEditor.dispatch({
    changes: { from: 0, to: current.length, insert: newDoc },
  });
}

async function ensureDefaultLibraryLoaded() {
  if (Object.keys(defaultCodeLibrary.value).length > 0) return;
  try {
    defaultCodeLibrary.value = await fetchGraphPythonLibrary();
  } catch (e) {
    console.warn('[NodeEditDialog] Failed to load default code library:', e);
    defaultCodeLibrary.value = {};
  }
}

function parseNameList(raw: unknown): string[] {
  if (Array.isArray(raw)) {
    return raw.map((item) => String(item).trim()).filter(Boolean);
  }
  if (typeof raw === 'string') {
    return raw.split(',').map((item) => item.trim()).filter(Boolean);
  }
  return [];
}

function toNameText(raw: unknown): string {
  return parseNameList(raw).join(', ');
}

function extractEditableCodeFromFull(code: string): string {
  const start = '"""以下为可以编辑的部分"""';
  const end = '"""以上为可以编辑的部分"""';
  const startIdx = code.indexOf(start);
  const endIdx = code.indexOf(end);
  if (startIdx < 0 || endIdx < 0 || endIdx <= startIdx) {
    return code.trim();
  }
  return code.slice(startIdx + start.length, endIdx).trim();
}

function currentPrototypePayload() {
  const inputCount = Math.max(1, Number(form.value.params.inputCount || 1));
  const outputCount = Math.max(1, Number(form.value.params.outputCount || 1));
  return {
    inputCount,
    outputCount,
    functionName: String(form.value.params.functionName || 'process_generated'),
    inputNames: parseNameList(inputNamesText.value),
    outputNames: parseNameList(outputNamesText.value),
    editableCode: pythonCode.value,
  };
}

async function refreshPythonPrototypeShell(overwriteEditable = false) {
  if (nodeType.value !== 'CUSTOM_PYFUNC') return;
  try {
    const spec = await generateGraphPythonPrototype(currentPrototypePayload());
    pythonHeaderCode.value = String(spec?.headerCode || '');
    pythonFooterCode.value = String(spec?.footerCode || '');
    form.value.params.functionName = String(spec?.functionName || form.value.params.functionName || 'process_generated');
    inputNamesText.value = Array.isArray(spec?.inputNames) ? spec.inputNames.join(', ') : inputNamesText.value;
    outputNamesText.value = Array.isArray(spec?.outputNames) ? spec.outputNames.join(', ') : outputNamesText.value;

    if (overwriteEditable || !pythonCode.value.trim()) {
      const editable = String(spec?.editableCode || '').trim();
      pythonCode.value = editable;
      syncEditorDoc(editable);
    }

    form.value.params.inputNames = parseNameList(inputNamesText.value);
    form.value.params.outputNames = parseNameList(outputNamesText.value);
    form.value.params.pythonEditableCode = pythonCode.value;
    form.value.params.pythonCode = String(spec?.code || '');
  } catch (e) {
    console.error('[NodeEditDialog] refresh prototype shell failed:', e);
  }
}

async function generatePrototype() {
  await refreshPythonPrototypeShell(true);
}

async function resetPythonCode() {
  await ensureDefaultLibraryLoaded();
  const byType = defaultCodeLibrary.value[nodeType.value];
  const code = String(byType || '');
  const editable = extractEditableCodeFromFull(code);
  pythonCode.value = editable;
  syncEditorDoc(editable);
  form.value.params.pythonEditableCode = editable;
  await refreshPythonPrototypeShell(false);
}

function triggerPythonImport() {
  pythonFileInput.value?.click();
}

async function importPythonFile(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  const content = await file.text();
  const editable = extractEditableCodeFromFull(content);
  pythonCode.value = editable;
  syncEditorDoc(editable);
  form.value.params.pythonEditableCode = editable;
  await refreshPythonPrototypeShell(false);
  input.value = '';
}

async function exportPythonCode() {
  if (nodeType.value === 'CUSTOM_PYFUNC') {
    await refreshPythonPrototypeShell(false);
  }
  const content = String(form.value.params.pythonCode || '');
  const blob = new Blob([content], { type: 'text/x-python' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${form.value.name || nodeTypeName.value || 'node'}.py`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function addSumInput() {
  sumInputs.value.push({ label: `输入${sumInputs.value.length + 1}`, weight: 1 });
}

function removeSumInput(index: number) {
  if (sumInputs.value.length <= 1) return;
  sumInputs.value.splice(index, 1);
}

function addMergeInput() {
  mergeInputs.value.push({ label: `输入${mergeInputs.value.length + 1}`, gain: 1 });
}

function removeMergeInput(index: number) {
  if (mergeInputs.value.length <= 1) return;
  mergeInputs.value.splice(index, 1);
}

function addSplitOutput() {
  splitOutputs.value.push({ label: `输出${splitOutputs.value.length + 1}`, channelIndices: '' });
}

function removeSplitOutput(index: number) {
  if (splitOutputs.value.length <= 1) return;
  splitOutputs.value.splice(index, 1);
}

watch(() => props.nodeData, (data) => {
  if (data) {
    form.value.name = data.name || '';
    form.value.params = { ...data.params };
    ensureVisualParamDefaults(data.type, form.value.params);
    paramsJson.value = JSON.stringify(data.params || {}, null, 2);
    jsonError.value = '';
    
    // 加载设备选择
    selectedDeviceId.value = data.deviceId || data.params?.deviceId || null;
    
    // 加载通道命名
    if (data.params?.channelNames) {
      channelNames.value = data.params.channelNames;
    }
    
    // 加载通道选择
    if (data.params?.selectedChannels) {
      selectedChannels.value = data.params.selectedChannels;
    } else {
      selectedChannels.value = [0, 1, 2, 3, 4, 5, 6, 7];
    }
    
    // 更新上游通道信息
    updateChannelInfo();

    if (data.type === 'CUSTOM_PYFUNC') {
      const editable = String(form.value.params.pythonEditableCode || '').trim()
        || extractEditableCodeFromFull(String(form.value.params.pythonCode || ''));
      pythonCode.value = editable;
      form.value.params.pythonEditableCode = editable;
      inputNamesText.value = toNameText(form.value.params.inputNames);
      outputNamesText.value = toNameText(form.value.params.outputNames);
      pythonHeaderCode.value = '';
      pythonFooterCode.value = '';
    } else {
      pythonCode.value = String(form.value.params.pythonCode || '');
      pythonHeaderCode.value = '';
      pythonFooterCode.value = '';
    }

    if (data.type === 'CUSTOM_CONV') {
      const kernel = Array.isArray(form.value.params.kernel) ? form.value.params.kernel : [0.25, 0.5, 0.25];
      kernelText.value = kernel.join(',');
    }
    
    // 检查是否已绑定示波器
    const osc = sessionStore.getOutputNodeOscilloscope(data.id);
    boundOscilloscopeId.value = osc?.id || null;
  }
}, { immediate: true });

watch([show, nodeType], async ([dialogOpen, type]) => {
  if (!dialogOpen || (type !== 'CUSTOM_PYFUNC' && type !== 'CUSTOM_CONV')) {
    destroyCodeEditor();
    return;
  }
  await ensureDefaultLibraryLoaded();
  if (!pythonCode.value && defaultCodeLibrary.value[type]) {
    if (type === 'CUSTOM_PYFUNC') {
      pythonCode.value = extractEditableCodeFromFull(String(defaultCodeLibrary.value[type] || ''));
      form.value.params.pythonEditableCode = pythonCode.value;
    } else {
      pythonCode.value = String(defaultCodeLibrary.value[type] || '');
      form.value.params.pythonCode = pythonCode.value;
    }
  }
  if (type === 'CUSTOM_PYFUNC') {
    await refreshPythonPrototypeShell(false);
  }
  await nextTick();
  createCodeEditor();
});

watch(
  [
    () => form.value.params.inputCount,
    () => form.value.params.outputCount,
    () => form.value.params.functionName,
    () => form.value.params.portMode,
    () => form.value.params.windowMode,
    () => form.value.params.windowSeconds,
    () => form.value.params.windowPoints,
    () => form.value.params.hopMode,
    () => form.value.params.hopPoints,
    () => form.value.params.hopMs,
    () => form.value.params.outputSampleRate,
    inputNamesText,
    outputNamesText,
  ],
  async () => {
    if (!show.value || nodeType.value !== 'CUSTOM_PYFUNC') return;
    await refreshPythonPrototypeShell(false);
  }
);

watch(kernelText, (value) => {
  if (nodeType.value !== 'CUSTOM_CONV') return;
  const kernel = String(value)
    .split(',')
    .map((token) => Number(token.trim()))
    .filter((num) => Number.isFinite(num));
  form.value.params.kernel = kernel.length > 0 ? kernel : [1];
});

watch(paramsJson, (val) => {
  try {
    form.value.params = JSON.parse(val);
    jsonError.value = '';
  } catch (e) {
    jsonError.value = 'JSON 格式错误';
  }
});

const selectAllChannels = () => {
  selectedChannels.value = availableChannels.value.map((_, i) => i);
};

const clearAllChannels = () => {
  selectedChannels.value = [];
};

const close = () => {
  show.value = false;
};

const save = async () => {
  // 只读模式下禁止保存
  if (isReadOnly.value) {
    console.log('[NodeEditDialog] 只读模式下禁止保存');
    return;
  }
  
  if (jsonError.value) return;

  if (nodeType.value === 'SUM') {
    form.value.params.inputs = sumInputs.value.map((item) => ({
      label: item.label || '输入',
      weight: Number(item.weight ?? 1),
    }));
  }

  if (nodeType.value === 'MERGE') {
    form.value.params.inputs = mergeInputs.value.map((item) => ({
      label: item.label || '输入',
      gain: Number(item.gain ?? 1),
    }));
    form.value.params.strategy = form.value.params.strategy || 'interleave';
  }

  if (nodeType.value === 'SPLIT') {
    form.value.params.outputs = splitOutputs.value.map((item) => ({
      label: item.label || '输出',
      channelIndices: String(item.channelIndices || ''),
    }));
  }
  
  // 保存通道信息
  if (nodeType.value === 'SOURCE') {
    form.value.params.sourceMode = form.value.params.sourceMode || 'live';
    form.value.params.filePath = String(form.value.params.filePath || '');
    form.value.params.loop = Boolean(form.value.params.loop || false);
    form.value.params.channelNames = channelNames.value;
    // 保存设备ID到params
    form.value.params.deviceId = form.value.params.sourceMode === 'replay' ? null : selectedDeviceId.value;
  }
  
  // 保存示波器通道选择
  if (nodeType.value === 'OSC') {
    form.value.params.selectedChannels = availableChannels.value.map((_, i) => i);
    form.value.params.availableChannels = availableChannels.value;
    form.value.params.saveEnabled = Boolean(form.value.params.saveEnabled || false);
    form.value.params.filename = String(form.value.params.filename || '');
    form.value.params.format = String(form.value.params.format || 'CSV');
  }

  if (nodeType.value === 'SPECTRUM') {
    form.value.params.selectedChannels = selectedChannels.value;
    form.value.params.availableChannels = availableChannels.value;
  }

  if (nodeType.value === 'CUSTOM_PYFUNC') {
    form.value.params.portMode = form.value.params.portMode || 'fixed';
    form.value.params.inputCount = Math.max(1, Number(form.value.params.inputCount || 1));
    form.value.params.outputCount = Math.max(1, Number(form.value.params.outputCount || 1));
    form.value.params.functionName = String(form.value.params.functionName || 'process_generated');
    form.value.params.windowMode = form.value.params.windowMode || 'seconds';
    form.value.params.windowSeconds = Math.max(0.01, Number(form.value.params.windowSeconds || 1));
    form.value.params.windowPoints = Math.max(1, Number(form.value.params.windowPoints || 256));
    form.value.params.hopMode = form.value.params.hopMode || 'points';
    form.value.params.hopPoints = Math.max(1, Number(form.value.params.hopPoints || 1));
    form.value.params.hopMs = Math.max(1, Number(form.value.params.hopMs || 10));
    form.value.params.outputSampleRate = Math.max(1, Number(form.value.params.outputSampleRate || 100));
    form.value.params.inputNames = parseNameList(inputNamesText.value);
    form.value.params.outputNames = parseNameList(outputNamesText.value);
    form.value.params.pythonEditableCode = pythonCode.value;
    await refreshPythonPrototypeShell(false);
  }

  if (nodeType.value === 'CUSTOM_CONV') {
    form.value.params.pythonCode = pythonCode.value;
    form.value.params.kernel = Array.isArray(form.value.params.kernel) ? form.value.params.kernel : [0.25, 0.5, 0.25];
  }
  
  emit('save', {
    name: form.value.name,
    params: form.value.params,
    deviceId: nodeType.value === 'SOURCE' ? selectedDeviceId.value : undefined,
  });
  
  // 处理示波器绑定
  if (nodeType.value === 'OSC' && props.nodeData) {
    emit('bindOscilloscope', {
      nodeId: props.nodeData.id,
      oscId: boundOscilloscopeId.value,
    });
  }
  
  close();
};

onMounted(() => {
  ensureDefaultLibraryLoaded();
});

onUnmounted(() => {
  destroyCodeEditor();
});
</script>

<style scoped>
.code-editor-host {
  min-height: 260px;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 8px;
  overflow: hidden;
}

:deep(.cm-editor) {
  min-height: 260px;
}
</style>
