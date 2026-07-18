<template>
  <div class="fullscreen-graph-editor">
    <v-toolbar density="compact" color="surface" class="graph-toolbar">
      <v-toolbar-title>计算图编辑器</v-toolbar-title>
      <v-spacer />
      <div class="d-flex align-center ga-2">
        <!-- 运行/冻结状态 -->
        <v-chip v-if="isRunning || frozen" size="small" :color="isRunning ? 'warning' : 'info'">
          <v-icon size="small" class="mr-1">
            {{ isRunning ? 'mdi-play' : 'mdi-lock' }}
          </v-icon>
          {{ isRunning ? '运行中' : '已冻结' }}
        </v-chip>

        <!-- 同步状态 -->
        <v-chip
          size="small"
          :color="syncStatusChip.color"
          :variant="syncStatus === 'error' ? 'tonal' : 'flat'"
          :class="{ 'cursor-pointer': syncStatus === 'error' }"
          @click="syncStatus === 'error' ? retrySync() : undefined"
        >
          <v-icon size="small" class="mr-1">{{ syncStatusChip.icon }}</v-icon>
          {{ syncStatusChip.text }}
        </v-chip>

        <v-btn size="small" variant="tonal" @click="exportGraph">导出</v-btn>
        
        <div class="d-flex align-center ga-1 ml-2">
          <span class="text-caption port-legend-in">● 输入</span>
          <span class="text-caption port-legend-out">● 输出</span>
        </div>
        <v-btn 
          size="small" 
          variant="tonal" 
          @click="triggerFileLoad"
          :disabled="!canEditGraphLocal"
                    :title="!canEditGraphLocal ? '运行中不允许加载计算图' : '从文件加载计算图'"
        >
          加载
        </v-btn>
        <v-btn 
          size="small" 
          color="info" 
          @click="clear"
          :disabled="!canEditGraphLocal"
                    :title="!canEditGraphLocal ? '运行中不允许清空计算图' : '清空计算图'"
        >
          清空
        </v-btn>

        <v-divider vertical class="mx-1" />

        <v-btn
          size="small"
          variant="tonal"
          @click="openDeviceManager"
          title="管理所有设备"
        >
          <v-icon size="small" class="mr-1">mdi-devices</v-icon>
          设备管理
        </v-btn>
      </div>
    </v-toolbar>

    <div class="graph-content">

      <div class="graph-wrapper">
        <!-- 左侧节点库 -->
        <div class="palette">
          <div class="palette-title">节点库</div>

          <div class="palette-body">
          <div class="palette-group">
            <div class="group-title d-flex align-center justify-space-between">
              <span>设备集合</span>
              <v-btn size="x-small" variant="text" @click="openCreateDeviceDialog" :disabled="!canEditGraphLocal">
                新建设备
              </v-btn>
            </div>
            <div
              v-for="device in runningDevices"
              :key="device.id"
              class="palette-item"
              :class="{ 'palette-item-disabled': !canEditGraphLocal }"
              :draggable="canEditGraphLocal"
              @dragstart="onDragStartDevice($event, device.id)"
                            :title="!canEditGraphLocal ? '运行中不允许拖拽设备' : `拖拽 ${device.port || device.name} 作为数据源节点`"
            >
              <span class="item-icon" style="background: #e3f2fd; color: #1976d2;">DEV</span>
              <span class="item-name">{{ device.port || device.name }}</span>
            </div>
            <div v-if="runningDevices.length === 0" class="palette-empty">
              暂无可用设备（请启动虚拟设备服务器）
            </div>
          </div>

          <div class="palette-group">
            <div class="group-title">数据回放</div>
            <div
              v-for="node in sourceNodes"
              :key="node.type"
              class="palette-item"
              :class="{ 'palette-item-disabled': !canEditGraphLocal }"
              :draggable="canEditGraphLocal"
              @dragstart="onDragStart($event, node.type)"
              :title="!canEditGraphLocal ? `运行中不允许添加节点` : `${node.name} — ${node.desc}\n拖拽到画布添加`"
            >
              <span class="item-icon" :style="{ background: node.bg, color: node.color }">
                {{ node.icon }}
              </span>
              <span class="item-name">{{ node.name }}</span>
            </div>
          </div>

          <div class="palette-group">
            <div class="group-title">处理节点</div>
            <div
              v-for="node in processNodes"
              :key="node.type"
              class="palette-item"
              :class="{ 'palette-item-disabled': !canEditGraphLocal }"
              :draggable="canEditGraphLocal"
              @dragstart="onDragStart($event, node.type)"
              :title="!canEditGraphLocal ? `运行中不允许添加节点` : `${node.name} — ${node.desc}\n拖拽到画布添加`"
            >
              <span class="item-icon" :style="{ background: node.bg, color: node.color }">
                {{ node.icon }}
              </span>
              <span class="item-name">{{ node.name }}</span>
            </div>
          </div>

          <div class="palette-group">
            <div class="group-title">显示与保存</div>
            <div
              v-for="node in outputNodes"
              :key="node.type"
              class="palette-item"
              :class="{ 'palette-item-disabled': !canEditGraphLocal }"
              :draggable="canEditGraphLocal"
              @dragstart="onDragStart($event, node.type)"
              :title="!canEditGraphLocal ? `运行中不允许添加节点` : `${node.name} — ${node.desc}\n拖拽到画布添加`"
            >
              <span class="item-icon" :style="{ background: node.bg, color: node.color }">
                {{ node.icon }}
              </span>
              <span class="item-name">{{ node.name }}</span>
            </div>
          </div>
          </div><!-- /palette-body -->
        </div>

        <!-- 右侧画布 -->
        <div ref="container" class="graph-container">
          <div v-if="!hasNodes" class="graph-hint">
            <v-icon size="48" color="grey-lighten-2">mdi-graph-outline</v-icon>
            <div class="hint-text">从左侧拖拽节点到此处</div>
            <div class="hint-sub">双击节点可编辑参数<br>连接节点创建数据处理流程</div>
          </div>
        </div>

        <!-- 右侧编辑边栏 -->
        <div class="sidebar" :class="{ 'sidebar-collapsed': !sidebarVisible }">
          <div class="sidebar-header">
            <template v-if="sidebarVisible">
              <div class="sidebar-title-wrap">
                <v-icon :color="sidebarIconColor" class="mr-2">{{ sidebarIcon }}</v-icon>
                <div class="sidebar-title-text">
                  <div class="sidebar-title">{{ sidebarTitle }}</div>
                  <div class="sidebar-subtitle">{{ sidebarSubtitle }}</div>
                </div>
              </div>
              <v-tooltip text="折叠边栏 (点击空白画布也可折叠)" location="bottom">
                <template #activator="{ props }">
                  <v-btn
                    v-bind="props"
                    icon
                    variant="text"
                    size="small"
                    @click="closeSidebar"
                  >
                    <v-icon>mdi-chevron-right</v-icon>
                  </v-btn>
                </template>
              </v-tooltip>
            </template>
            <v-tooltip v-else text="展开节点属性面板" location="bottom">
              <template #activator="{ props }">
                <v-btn
                  v-bind="props"
                  icon
                  variant="text"
                  size="small"
                  @click="reopenSidebar"
                >
                  <v-icon>mdi-chevron-left</v-icon>
                </v-btn>
              </template>
            </v-tooltip>
          </div>

          <!-- 边栏内容 -->
          <div v-if="sidebarVisible" class="sidebar-content">
            <div v-if="!editingNode" class="sidebar-empty">
              <v-icon size="40" color="grey-lighten-1">mdi-cube-outline</v-icon>
              <div class="sidebar-empty-text">点击画布中的节点以编辑其属性</div>
            </div>
            <NodeEditDialog
              v-else
              v-model="nodeEditDialogOpen"
              :node-data="editingNode"
              :all-nodes="allNodes"
              :all-edges="allEdges"
              mode="sidebar"
              :is-read-only="!canEditGraphLocal"
              @save="handleNodeSave"
              @bindOscilloscope="handleBindOscilloscope"
              class="sidebar-node-edit"
            />
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- 节点编辑对话框 -->
  <v-dialog v-model="editDialog.open" max-width="500">
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon class="mr-2" :color="editDialog.config?.color">mdi-cog</v-icon>
        {{ frozen ? '查看节点' : '编辑节点' }}: {{ editDialog.nodeName }}
      </v-card-title>
      <v-divider />
      <v-card-text class="pt-4">
        <!-- 节点名称 -->
        <v-text-field
          v-model="editDialog.nodeName"
          label="节点名称"
          variant="outlined"
          density="compact"
          class="mb-4"
          :readonly="frozen"
          :disabled="frozen"
        />

        <!-- 动态参数表单 -->
        <div v-for="field in editDialog.fields" :key="field.key" class="mb-3">
          <!-- 数字输入 -->
          <v-text-field
            v-if="field.type === 'number'"
            v-model.number="editDialog.params[field.key]"
            :label="field.label"
            :hint="field.hint"
            type="number"
            variant="outlined"
            density="compact"
            persistent-hint
            :readonly="frozen"
            :disabled="frozen"
          />

          <!-- 文本输入 -->
          <v-text-field
            v-else-if="field.type === 'text'"
            v-model="editDialog.params[field.key]"
            :label="field.label"
            :hint="field.hint"
            variant="outlined"
            density="compact"
            persistent-hint
            :readonly="frozen"
            :disabled="frozen"
          />

          <!-- 选择器 -->
          <v-select
            v-else-if="field.type === 'select'"
            v-model="editDialog.params[field.key]"
            :label="field.label"
            :items="field.options"
            :hint="field.hint"
            variant="outlined"
            density="compact"
            persistent-hint
            :readonly="frozen"
            :disabled="frozen"
          />

          <!-- 滑块 -->
          <div v-else-if="field.type === 'slider'">
            <div class="d-flex align-center justify-space-between mb-1">
              <span class="text-body-2">{{ field.label }}</span>
              <span class="text-caption text-grey">{{ editDialog.params[field.key] }}</span>
            </div>
            <v-slider
              v-model.number="editDialog.params[field.key]"
              :min="field.min"
              :max="field.max"
              :step="field.step || 1"
              density="compact"
              hide-details
              :readonly="frozen"
              :disabled="frozen"
            />
            <div class="text-caption text-grey mt-1">{{ field.hint }}</div>
          </div>

          <!-- 开关 -->
          <v-switch
            v-else-if="field.type === 'boolean'"
            v-model="editDialog.params[field.key]"
            :label="field.label"
            :hint="field.hint"
            density="compact"
            hide-details
            :readonly="frozen"
            :disabled="frozen"
          />
        </div>
      </v-card-text>
      <v-divider />
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="editDialog.open = false">{{ frozen ? '关闭' : '取消' }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- 隐藏的文件输入用于加载计算图 -->
  <input
    id="graph-file-input"
    type="file"
    accept=".json"
    style="display: none"
    @change="loadGraphFromFile"
  />

  <v-dialog v-model="createDeviceDialogOpen" max-width="560">
    <v-card>
      <v-card-title>新建设备</v-card-title>
      <v-card-text class="pt-3">
        <v-text-field v-model="newDeviceForm.name" label="设备名称" density="compact" variant="outlined" />
        <v-select
          v-model="newDeviceForm.type"
          :items="['simulated', 'wearable_eeg']"
          label="设备类型"
          density="compact"
          variant="outlined"
        />
        <v-text-field v-model.number="newDeviceForm.sampling_rate" type="number" label="采样率" density="compact" variant="outlined" />
        <v-text-field v-model.number="newDeviceForm.channel_count" type="number" label="通道数" density="compact" variant="outlined" />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="createDeviceDialogOpen = false">取消</v-btn>
        <v-btn color="primary" @click="createDeviceFromGraphEditor">创建并加入设备集合</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog v-model="pinnedNodePanel" max-width="880">
    <v-card>
      <v-card-title class="d-flex align-center">
        <span>节点固定面板</span>
        <v-spacer />
        <v-btn icon size="small" variant="text" @click="pinnedNodePanel = false"><v-icon>mdi-close</v-icon></v-btn>
      </v-card-title>
      <v-divider />
      <v-card-text>
        <v-tabs v-model="pinnedTab" density="compact" class="mb-3">
          <v-tab value="edit">编辑</v-tab>
          <v-tab value="preview">预览</v-tab>
        </v-tabs>
        <v-window v-model="pinnedTab">
          <v-window-item value="edit">
            <NodeEditDialog
              v-model="nodeEditDialogOpen"
              :node-data="editingNode"
              :all-nodes="allNodes"
              :all-edges="allEdges"
              mode="sidebar"
              @save="handleNodeSave"
              @bindOscilloscope="handleBindOscilloscope"
            />
          </v-window-item>
          <v-window-item value="preview">
            <Oscilloscope
              v-if="editingNode && editingNode.type === 'OUTPUT'"
              :initial-node-id="editingNode.id"
            />
            <v-alert v-else type="info" variant="tonal">当前节点暂无预览视图</v-alert>
          </v-window-item>
        </v-window>
      </v-card-text>
    </v-card>
  </v-dialog>

  <!-- 设备管理弹窗 -->
  <v-dialog v-model="deviceManagerOpen" max-width="700">
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon class="mr-2">mdi-devices</v-icon>
        设备管理
        <v-spacer />
        <v-btn size="small" variant="text" color="primary" @click="deviceFormDialogOpen = true" :disabled="!canEditGraphLocal">
          <v-icon size="small" class="mr-1">mdi-plus</v-icon>
          新建设备
        </v-btn>
        <v-btn size="small" variant="text" @click="refreshManagedDevices">
          <v-icon size="small">mdi-refresh</v-icon>
        </v-btn>
        <v-btn icon size="small" variant="text" @click="deviceManagerOpen = false"><v-icon>mdi-close</v-icon></v-btn>
      </v-card-title>
      <v-divider />
      <v-card-text class="pt-4">
        <v-table density="compact">
          <thead>
            <tr>
              <th>名称</th>
              <th>类型</th>
              <th>端口</th>
              <th>采样率</th>
              <th>通道</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="dev in managedDevices" :key="dev.id">
              <td>{{ dev.name }}</td>
              <td>
                <v-chip size="x-small" :color="dev.type === 'wearable_eeg' ? 'purple' : 'blue'">
                  {{ dev.type === 'wearable_eeg' ? '真实设备' : '模拟设备' }}
                </v-chip>
              </td>
              <td class="text-caption">{{ dev.config?.port || '—' }}</td>
              <td>{{ dev.sampling_rate }}Hz</td>
              <td>{{ dev.channel_count }}</td>
              <td>
                <v-btn size="x-small" variant="text" color="error" @click="deleteManagedDevice(dev.id)" :disabled="!canEditGraphLocal">删除</v-btn>
              </td>
            </tr>
            <tr v-if="managedDevices.length === 0">
              <td colspan="6" class="text-center text-grey py-4">暂无设备，点击"新建设备"或"一键扫描"添加</td>
            </tr>
          </tbody>
        </v-table>
      </v-card-text>
      <v-divider />
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="deviceManagerOpen = false">关闭</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- 新建设备弹窗 -->
  <v-dialog v-model="deviceFormDialogOpen" max-width="500">
    <v-card>
      <v-card-title>新建设备</v-card-title>
      <v-divider />
      <v-card-text class="pt-4">
        <v-text-field v-model="deviceForm.name" label="设备名称" density="compact" variant="outlined" class="mb-3" />
        <v-select v-model="deviceForm.type" :items="['simulated', 'wearable_eeg']" label="设备类型" density="compact" variant="outlined" class="mb-3" />
        <v-text-field v-model.number="deviceForm.sampling_rate" label="采样率 (Hz)" type="number" density="compact" variant="outlined" class="mb-3" />
        <v-text-field v-model.number="deviceForm.channel_count" label="通道数" type="number" density="compact" variant="outlined" class="mb-3" />
      </v-card-text>
      <v-divider />
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="deviceFormDialogOpen = false">取消</v-btn>
        <v-btn color="primary" @click="createDevice">创建</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, nextTick, watch, computed } from 'vue';
import { onBeforeRouteLeave } from 'vue-router';
import { Graph, Snapline } from '@antv/x6';
import {
  fetchGraph,
  type GraphNode,
  type GraphNodeType,
  type GraphPayload,
} from '../services/graph';
import { deviceApi } from '../services/deviceApi';
import { realDeviceApi, type DeviceInfo } from '../services/realDeviceApi';
import { graphRuntime, type EegPacket } from '../services/runtime';
import { useToast } from '../composables/useToast';
import { sessionStore } from '../services/sessionStore';
import { eegWebSocket } from '../services/websocket';
import { graphRuntimeStore } from '../services/graphRuntimeStore';
import { controlWebSocket } from '../services/controlWebSocket';
import { graphSyncWebSocket } from '../services/graphSyncWebSocket';
import { useTheme } from 'vuetify';
import Oscilloscope from './Oscilloscope.vue';

import NodeEditDialog from './nodes/NodeEditDialog.vue';

// 会话存储键名
const SESSION_STORAGE_KEY = 'eeg_graph_editor_state';

const container = ref<HTMLDivElement | null>(null);
const graphRef = ref<Graph | null>(null);
const hasNodes = ref(false);

// 画布网格点颜色跟随亮/暗主题
const vTheme = useTheme();
function gridDotColor() {
  return vTheme.global.current.value.dark
    ? 'rgba(228, 233, 244, 0.22)'
    : 'rgba(26, 34, 51, 0.20)';
}

// ======== 双图同步状态模型 ========
// 编辑器签名 = 当前画布内容的 hash
// 后端签名 = 服务端确认的最新版本的 hash
// 待确认签名 = 已发往服务端但尚未收到确认的 hash（'' = 无待确认）
const editorSignature = ref('');
const backendSignature = ref('');
const pendingSignature = ref('');
type SyncStatus = 'idle' | 'saving' | 'ok' | 'error';
const syncStatus = ref<SyncStatus>('idle');
const syncError = ref('');
let syncOkTimer: number | null = null;
const hasUnsavedChanges = computed(() => editorSignature.value !== backendSignature.value);

const isApplyingBackendGraph = ref(false);
const currentRevision = ref(0);
const persistedRevision = ref(0);
let realtimeSyncTimer: number | null = null;
let isNodeDragging = false;
let dragDebounceTimer: number | null = null;

type PaletteDevice = {
  id: string;
  name: string;
  status: string;
  port: string;
  type: string;
};

const paletteDevices = ref<PaletteDevice[]>([]);
const runningDevices = computed(() => paletteDevices.value);
const createDeviceDialogOpen = ref(false);
const newDeviceForm = ref({
  name: '新设备',
  type: 'simulated',
  sampling_rate: 1000,
  channel_count: 8,
});

const pinnedNodePanel = ref(false);
const pinnedTab = ref<'edit' | 'preview'>('edit');

function sortValueDeep(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => sortValueDeep(item));
  }
  if (value && typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([key, val]) => [key, sortValueDeep(val)]);
    return Object.fromEntries(entries);
  }
  return value;
}

function payloadSignature(payload: GraphPayload): string {
  const normalized: GraphPayload = {
    frozen: Boolean(payload.frozen),
    nodes: [...(payload.nodes || [])]
      .map((node) => sortValueDeep(node) as GraphNode)
      .sort((a, b) => String(a.id || '').localeCompare(String(b.id || ''))),
    edges: [...(payload.edges || [])]
      .map((edge) => sortValueDeep(edge) as typeof payload.edges[number])
      .sort((a, b) => String(a.id || '').localeCompare(String(b.id || ''))),
  };
  return JSON.stringify(normalized);
}

// ======== 双图同步模型 ========

function setSyncStatus(status: SyncStatus, errorMsg: string = '') {
  syncStatus.value = status;
  syncError.value = errorMsg;
  if (status === 'ok') {
    if (syncOkTimer) clearTimeout(syncOkTimer);
    syncOkTimer = window.setTimeout(() => {
      if (syncStatus.value === 'ok') syncStatus.value = 'idle';
    }, 3000);
  }
}

function syncUnsavedState() {
  if (isApplyingBackendGraph.value) return;
  if (isNodeDragging) return;
  if (nodeEditDialogOpen.value) return;

  const current = buildPayload();
  const sig = payloadSignature(current);
  editorSignature.value = sig;

  // 如果签名和待确认的一致（说明服务器还没处理上一次）或和后端一致，跳过
  if (sig === pendingSignature.value || sig === backendSignature.value) {
    return;
  }

  // 有变更需要同步
  scheduleRealtimeSync(current, sig);
}

function scheduleRealtimeSync(payload: GraphPayload, signature: string) {
  if (isRunning.value || isApplyingBackendGraph.value) return;
  if (realtimeSyncTimer) clearTimeout(realtimeSyncTimer);

  realtimeSyncTimer = window.setTimeout(() => {
    // 重新取当前画布签名（用户可能在 250ms 内又改了）
    const current = buildPayload();
    const sig = payloadSignature(current);
    editorSignature.value = sig;
    if (sig === backendSignature.value || sig === pendingSignature.value) return;

    try {
      pendingSignature.value = sig;
      setSyncStatus('saving');
      controlWebSocket.syncGraph(current, currentRevision.value);
    } catch (err) {
      console.warn('[GraphEditor] Sync send failed:', err);
      pendingSignature.value = '';
      setSyncStatus('error', '发送失败');
    }
  }, 250);
}

function retrySync() {
  if (syncStatus.value !== 'error') return;
  if (isRunning.value || isApplyingBackendGraph.value) return;
  if (isNodeDragging) return;
  const current = buildPayload();
  const sig = payloadSignature(current);
  editorSignature.value = sig;
  pendingSignature.value = sig;
  setSyncStatus('saving');
  try {
    controlWebSocket.syncGraph(current, currentRevision.value);
  } catch (err) {
    pendingSignature.value = '';
    setSyncStatus('error', '重试失败');
  }
}

// 服务端确认同步成功
function handleSyncConfirmed(incomingSignature: string, rev: number, persistedRev: number) {
  if (incomingSignature === pendingSignature.value) {
    backendSignature.value = pendingSignature.value;
    pendingSignature.value = '';
    setSyncStatus('ok');
  } else if (incomingSignature === backendSignature.value) {
    // 其他客户端同步了相同的状态
    pendingSignature.value = '';
    setSyncStatus('ok');
  }
  currentRevision.value = rev;
  persistedRevision.value = persistedRev;
}

// 同步冲突（服务端拒绝）
function handleSyncConflict(serverGraph: GraphPayload, rev: number, persistedRev: number) {
  pendingSignature.value = '';
  setSyncStatus('error', '同步冲突：数据已被其他客户端修改，请重试');
  currentRevision.value = rev;
  persistedRevision.value = persistedRev;
  // 不覆盖用户画布 — 用户自行决定重试
}

// 服务端推送新状态（非当前客户端触发的变更）
// 核心原则：画布是用户操作的唯一权威——服务端推送只更新元数据，永不覆盖画布
function handleServerPush(payload: GraphPayload, reason: string, rev: number, persistedRev: number) {
  const sig = payloadSignature(payload);

  // 初始加载尚未完成，跳过
  if (!backendSignature.value && (reason === 'initial' || reason === 'pull')) {
    return;
  }

  // 运行时状态变化（拓扑未变），只同步 frozen 和版本号
  if (reason === 'freeze_changed' || reason === 'runtime') {
    currentRevision.value = rev;
    persistedRevision.value = persistedRev;
    setRuntimeState({ frozen: Boolean(payload.frozen) });
    backendSignature.value = sig;
    editorSignature.value = sig;
    return;
  }

  // 服务端推送与当前后端签名一致（对 sync_graph 命令的回声确认）
  if (reason === 'connected' || reason === 'heartbeat') {
    if (sig === backendSignature.value) {
      currentRevision.value = rev;
      persistedRevision.value = persistedRev;
      return;
    }
    // 服务端状态与本地后端签名不一致（其他客户端修改了图）
    if (pendingSignature.value !== '' || editorSignature.value !== backendSignature.value) {
      // 有未同步编辑，阻止覆盖，提示用户
      console.warn('[GraphEditor] Server push blocked: user has unsaved changes. reason:', reason);
      setSyncStatus('error', '远程数据已更新但你有未同步的编辑');
      currentRevision.value = rev;
      persistedRevision.value = persistedRev;
      return;
    }
    // 无本地编辑，接受服务端新状态，更新签名但不动画布
    currentRevision.value = rev;
    persistedRevision.value = persistedRev;
    backendSignature.value = sig;
    editorSignature.value = sig;
    return;
  }

  // 未知 reason：保守处理，只更新元数据不动画布
  console.warn('[GraphEditor] Unhandled server push reason:', reason);
  currentRevision.value = rev;
  persistedRevision.value = persistedRev;
}

async function loadPaletteDevices() {
  try {
    // getDevices() 返回归一化的 camelCase 格式
    const apiDevices = await deviceApi.getDevices();
    paletteDevices.value = apiDevices.map((d: any) => ({
      id: d.id,
      name: d.name,
      status: d.status ?? 'online',
      port: String(d.config?.port || d.id || ''),
      type: String(d.type || ''),
    }));

    // 同步填充 sessionStore，避免 NodeEditFormContent 中的设备选择器无数据
    const converted: Array<{ id: string; name: string; status: 'online' | 'offline'; samplingRate: number; channelCount: number; type: 'simulated' | 'real'; config: any }> = apiDevices.map((apiDevice: any) => ({
      id: String(apiDevice.id || ''),
      name: String(apiDevice.name || apiDevice.id || ''),
      status: (apiDevice.status === 'offline' ? 'offline' : 'online') as 'online' | 'offline',
      samplingRate: Number(apiDevice.samplingRate || 1000),
      channelCount: Number(apiDevice.channelCount || 8),
      type: (apiDevice.type === 'real' ? 'real' : 'simulated') as 'simulated' | 'real',
      config: apiDevice.config || {},
    }));
    sessionStore.setDevices(converted as any);
  } catch (err) {
    console.warn('[GraphEditor] Failed to load palette devices:', err);
    paletteDevices.value = [];
  }
}

function openCreateDeviceDialog() {
  createDeviceDialogOpen.value = true;
}

async function createDeviceFromGraphEditor() {
  try {
    await deviceApi.createDevice({
      name: String(newDeviceForm.value.name || '新设备'),
      type: newDeviceForm.value.type as 'simulated' | 'physical',
      address: 'graph-editor',
      sampling_rate: Number(newDeviceForm.value.sampling_rate || 1000),
      channel_count: Number(newDeviceForm.value.channel_count || 8),
    });
    createDeviceDialogOpen.value = false;
    await loadPaletteDevices();
    await refreshManagedDevices();
  } catch (err) {
    alert('创建设备失败: ' + (err as Error).message);
  }
}

// ==================== 设备管理弹窗 ====================
const deviceManagerOpen = ref(false);
const deviceFormDialogOpen = ref(false);
const managedDevices = ref<DeviceInfo[]>([]);

const deviceForm = ref({
  name: '新设备',
  type: 'simulated',
  sampling_rate: 1000,
  channel_count: 8,
});

function openDeviceManager() {
  deviceManagerOpen.value = true;
  refreshManagedDevices();
}

async function refreshManagedDevices() {
  try {
    const apiDevices = await deviceApi.getDevices();
    managedDevices.value = (apiDevices as any[]).map((d: any) => ({
      id: d.id, name: d.name, type: d.type,
      sampling_rate: d.samplingRate ?? 1000,
      channel_count: d.channelCount ?? 8,
      config: d.config,
    })) as DeviceInfo[];
    // 同步 palette
    await loadPaletteDevices();
  } catch (err) {
    console.warn('[GraphEditor] Failed to refresh managed devices:', err);
  }
}

async function deleteManagedDevice(deviceId: string) {
  if (!confirm('确定要删除此设备吗？')) return;
  try {
    await deviceApi.deleteDevice(deviceId);
    await refreshManagedDevices();
  } catch (err) {
    alert('删除失败: ' + (err as Error).message);
  }
}

async function createDevice() {
  try {
    await deviceApi.createDevice({
      name: String(deviceForm.value.name || '新设备'),
      type: deviceForm.value.type as 'simulated' | 'physical',
      address: '',
      sampling_rate: Number(deviceForm.value.sampling_rate || 1000),
      channel_count: Number(deviceForm.value.channel_count || 8),
    });
    deviceFormDialogOpen.value = false;
    await refreshManagedDevices();
  } catch (err) {
    alert('创建设备失败: ' + (err as Error).message);
  }
}

// ==================== 自动设备扫描与连接（即插即用）====================
let autoScanTimer: number | null = null;

async function refreshDeviceList() {
  // 仅刷新设备列表（不自动创建/连接设备），设备发现由后端驱动管理
  try {
    await loadPaletteDevices();
  } catch (err) {
    console.warn('[GraphEditor] Device refresh failed:', err);
  }
}

function startAutoScan() {
  stopAutoScan();
  // 立即执行一次
  refreshDeviceList();
  // 每 15 秒刷新一次设备列表
  autoScanTimer = window.setInterval(refreshDeviceList, 15000);
}

function stopAutoScan() {
  if (autoScanTimer !== null) {
    clearInterval(autoScanTimer);
    autoScanTimer = null;
  }
}
// ==================== 自动设备扫描 END ====================

// 从全局状态管理获取状态
const {
  isRunning,
  runtimeMode,
  frozen,
  offlineProgress,
  processingDelayMs,
  nonRealtime,
  runtimeWarning,
  canEditGraph,
  canRunGraph
} = graphRuntimeStore;

// 同步状态芯片
const syncStatusChip = computed(() => {
  switch (syncStatus.value) {
    case 'saving': return { icon: 'mdi-cloud-upload', text: '同步中…', color: 'primary' };
    case 'ok': return { icon: 'mdi-check-circle', text: '已同步', color: 'success' };
    case 'error': return { icon: 'mdi-alert-circle', text: syncError.value || '同步失败，点击重试', color: 'error' };
    default: return { icon: 'mdi-pencil', text: '编辑中', color: 'default' };
  }
});

// 监听冻结状态变化，启动/停止自动扫描
watch(frozen, (isFrozen) => {
  if (isFrozen) {
    stopAutoScan();
  } else {
    startAutoScan();
  }
}, { immediate: true });

// 组件卸载时清除自动扫描定时器
onUnmounted(() => {
  stopAutoScan();
});

const setRuntimeState = (patch: Record<string, unknown>) => {
  graphRuntimeStore.updateState(patch as any);
};

async function pollRuntimeState() {
  await graphRuntimeStore.pollRuntimeState();
}

function startRuntimeStatePolling() {
  graphRuntimeStore.startPolling();
}

function stopRuntimeStatePolling() {
  graphRuntimeStore.stopPolling();
}

// 右侧边栏可见性 — 选中节点时展开，单击空白时折叠
const sidebarVisible = ref(false);

// 边栏标题与图标计算属性
const sidebarIconColor = computed(() => {
  if (!editingNode.value) return 'grey';
  const meta = nodeMetaMap[editingNode.value.type];
  return meta?.color || 'grey';
});

const sidebarIcon = computed(() => {
  if (!editingNode.value) return 'mdi-cube-outline';
  const meta = nodeMetaMap[editingNode.value.type];
  return meta?.icon || 'mdi-cube-outline';
});

const sidebarTitle = computed(() => {
  if (!editingNode.value) return '节点属性';
  const meta = nodeMetaMap[editingNode.value.type];
  const typeName = meta?.name || editingNode.value.type;
  const nodeName = editingNode.value.name || '未命名';
  // 名称与类型相同时不重复显示
  return nodeName === typeName ? nodeName : `${typeName} · ${nodeName}`;
});

const sidebarSubtitle = computed(() => {
  if (frozen.value) return '查看节点（计算图已锁定）';
  if (isRunning.value) return '查看节点（运行中）';
  return '编辑节点 · 自动保存';
});

// 边栏切换后刷新画布尺寸
watch(sidebarVisible, () => {
  nextTick(() => {
    const graph = graphRef.value;
    if (graph) {
      setTimeout(() => {
        graph.resize();
        graph.centerContent();
      }, 350);
    }
  });
});

// 选中的节点 ID（用于其他功能，如高亮）
const selectedNodeId = ref<string | null>(null);

// 计算属性：检查是否允许编辑计算图（结合全局状态和会话状态）
const canEditGraphLocal = computed(() => {
  return sessionStore.canEditGraph() && !isRunning.value;
});

let edgeAnimationTimer: number | null = null;
const edgeAnimationStates = ref<Map<string, { active: boolean; progress: number }>>(new Map());

// 边动画管理
function startEdgeAnimations() {
  if (edgeAnimationTimer) return;
  
  edgeAnimationTimer = window.setInterval(() => {
    const graph = graphRef.value;
    if (!graph || !isRunning.value) return;
    
    // 更新所有边的动画状态
    graph.getEdges().forEach((edge) => {
      const edgeId = edge.id;
      const currentState = edgeAnimationStates.value.get(edgeId) || { active: false, progress: 0 };
      
      // 根据运行状态决定动画类型
      const shouldBeActive = isRunning.value;
      const isLiveMode = runtimeMode.value === 'live';
      
      if (shouldBeActive !== currentState.active) {
        currentState.active = shouldBeActive;
        currentState.progress = 0;
        edgeAnimationStates.value.set(edgeId, currentState);
      }
      
      if (currentState.active) {
        // 更新动画进度
        currentState.progress = (currentState.progress + (isLiveMode ? 0.05 : 0.02)) % 1;
        edgeAnimationStates.value.set(edgeId, currentState);
        
        // 应用动画效果
        if (isLiveMode) {
          applyLiveEdgeAnimation(edge, currentState.progress);
        } else {
          applyOfflineEdgeAnimation(edge, currentState.progress);
        }
      } else {
        // 清除动画效果
        clearEdgeAnimation(edge);
      }
    });
  }, 50); // 20fps 动画
}

function stopEdgeAnimations() {
  if (edgeAnimationTimer) {
    clearInterval(edgeAnimationTimer);
    edgeAnimationTimer = null;
  }
  
  // 清除所有边的动画效果
  const graph = graphRef.value;
  if (graph) {
    graph.getEdges().forEach((edge) => {
      clearEdgeAnimation(edge);
    });
  }
  
  edgeAnimationStates.value.clear();
}

function applyLiveEdgeAnimation(edge: import('@antv/x6').Edge, progress: number) {
  // Live模式：快速流动动画效果
  const strokeDasharray = '10, 5';
  const strokeDashoffset = -progress * 15; // 流动效果
  
  edge.attr({
    line: {
      strokeDasharray,
      strokeDashoffset,
      stroke: '#5F95FF',
      strokeWidth: 2,
      style: {
        animation: 'none',
      },
    },
    sourceMarker: {
      fill: '#5F95FF',
      stroke: '#5F95FF',
    },
    targetMarker: {
      fill: '#5F95FF',
      stroke: '#5F95FF',
    },
  });
  
  // 添加发光效果
  edge.addTools({
    name: 'segments',
    args: {
      snapRadius: 20,
      attrs: {
        fill: '#5F95FF',
        stroke: '#5F95FF',
        'stroke-width': 4,
        opacity: 0.3,
      },
    },
  });
}

function applyOfflineEdgeAnimation(edge: import('@antv/x6').Edge, progress: number) {
  // 离线模式：缓慢脉冲动画效果
  const pulseIntensity = 0.5 + 0.5 * Math.sin(progress * Math.PI * 2);
  const strokeWidth = 1 + pulseIntensity; // 1-2px 脉动
  
  edge.attr({
    line: {
      stroke: '#9C27B0', // 紫色表示离线处理
      strokeWidth,
      strokeDasharray: '5, 3',
      strokeDashoffset: -progress * 8,
    },
    sourceMarker: {
      fill: '#9C27B0',
      stroke: '#9C27B0',
    },
    targetMarker: {
      fill: '#9C27B0',
      stroke: '#9C27B0',
    },
  });
  
  // 添加脉冲效果
  edge.addTools({
    name: 'segments',
    args: {
      snapRadius: 20,
      attrs: {
        fill: '#9C27B0',
        stroke: '#9C27B0',
        'stroke-width': 2 + pulseIntensity * 2,
        opacity: 0.2 + pulseIntensity * 0.2,
      },
    },
  });
}

function clearEdgeAnimation(edge: import('@antv/x6').Edge) {
  edge.attr({
    line: {
      strokeDasharray: '',
      strokeDashoffset: 0,
      stroke: '#5F95FF',
      strokeWidth: 2,
    },
    sourceMarker: {
      fill: '#5F95FF',
      stroke: '#5F95FF',
    },
    targetMarker: {
      fill: '#5F95FF',
      stroke: '#5F95FF',
    },
  });
  
  // 移除工具
  edge.removeTools();
}

// 停止运行函数（用于边动画管理）
async function stopRunLocal() {
  try {
    graphRuntime.stop();
    
    // 停止边动画
    stopEdgeAnimations();
    
    
    // 保存状态到会话存储
    saveStateToSessionStorage();
  } catch (err) {
    console.error('[GraphEditor] Failed to stop graph locally:', err);
  }
}

// 存储 sessionStore 取消订阅函数
let unsubscribeSessionStore: (() => void) | null = null;
let unsubscribeGraphSync: (() => void) | null = null;
let unsubscribeCmdResult: (() => void) | null = null;

function onSaveHotkey(event: KeyboardEvent) {
  // Ctrl+S — 手动触发即时同步（跳过 debounce）
  if (!(event.ctrlKey || event.metaKey)) return;
  if (event.key.toLowerCase() !== 's') return;
  event.preventDefault();
  if (!canEditGraphLocal.value) return;
  if (hasUnsavedChanges.value) {
    const current = buildPayload();
    scheduleRealtimeSync(current, payloadSignature(current));
  }
}

function onBeforeUnload(event: BeforeUnloadEvent) {
  if (!hasUnsavedChanges.value) return;
  event.preventDefault();
  event.returnValue = '';
}

onBeforeRouteLeave((_to, _from, next) => {
  if (!hasUnsavedChanges.value) {
    next();
    return;
  }
  const confirmed = window.confirm('当前计算图有未保存更改，离开后将丢失。是否继续离开？');
  next(confirmed);
});

// 新增：NodeEditDialog 相关状态
const nodeEditDialogOpen = ref(false);
const editingNode = ref<GraphNode | null>(null);
const allNodes = ref<GraphNode[]>([]);
const allEdges = ref<Array<{id: string; source: string; target: string; sourcePort?: string; targetPort?: string}>>([]);

// 节点编辑对话框状态
const editDialog = ref({
  open: false,
  nodeId: '',
  nodeName: '',
  nodeType: '' as GraphNodeType | '',
  params: {} as Record<string, unknown>,
  config: null as { color: string; bg: string } | null,
  fields: [] as ParamField[],
});

// 监听冻结状态变化
let isInitializing = true;
watch(frozen, (newVal, oldVal) => {
  if (newVal !== oldVal) {
    
    // 初始化时不自动触发冻结操作
    if (!isInitializing) {
      applyFrozen();
    }
  }
});

// 在计算图加载完成后设置初始化完成
onMounted(() => {
  // 延迟设置，确保计算图已加载
  setTimeout(() => {
    isInitializing = false;
  }, 1000);
});

// 保存节点编辑（旧版，保留兼容性）
function saveNodeEdit() {
  // 冻结状态下禁止编辑
  if (frozen.value) {
    return;
  }
  
  const graph = graphRef.value;
  if (!graph || !editDialog.value.nodeId) return;

  const node = graph.getCellById(editDialog.value.nodeId);
  if (!node || !node.isNode()) return;

  // 更新节点数据
  const data = node.getData() as GraphNode;
  data.name = editDialog.value.nodeName;
  data.params = { ...editDialog.value.params };
  node.setData(data);

  // 更新节点标签显示
  const labelText = generateNodeLabel(data.type, data.name, data.params, editDialog.value.nodeId);
  node.attr('label/text', labelText);

  editDialog.value.open = false;
}

// 防抖保存函数（用于旧版对话框）
let debounceSaveTimeout: number | null = null;
const debouncedSaveNodeEdit = () => {
  if (debounceSaveTimeout) {
    clearTimeout(debounceSaveTimeout);
  }
  debounceSaveTimeout = setTimeout(() => {
    if (editDialog.value.open && editDialog.value.nodeId && !frozen.value) {
      saveNodeEdit();
    }
  }, 500); // 500ms防抖
};

// 监听编辑对话框变化，自动保存
watch(() => editDialog.value, (newVal, oldVal) => {
  if (!newVal.open || frozen.value) return;
  
  // 检查是否有实际变化
  const hasNameChanged = newVal.nodeName !== oldVal?.nodeName;
  const hasParamsChanged = JSON.stringify(newVal.params) !== JSON.stringify(oldVal?.params);
  
  if (hasNameChanged || hasParamsChanged) {
    debouncedSaveNodeEdit();
  }
}, { deep: true });

// 参数字段定义
interface ParamField {
  key: string;
  label: string;
  type: 'number' | 'text' | 'select' | 'slider' | 'boolean';
  hint?: string;
  min?: number;
  max?: number;
  step?: number;
  options?: string[];
  default?: unknown;
}

// 各节点类型的参数配置
const nodeParamConfigs: Record<GraphNodeType, ParamField[]> = {
  SOURCE: [
    { key: 'sampleRate', label: '采样率', type: 'number', hint: 'Hz', default: 1000 },
    { key: 'channels', label: '通道数', type: 'slider', min: 1, max: 32, hint: '通道数量', default: 8 },
  ],
  REPLAY: [
    { key: 'filePath', label: '数据文件', type: 'text', hint: '回放文件路径', default: '' },
    { key: 'loop', label: '循环播放', type: 'boolean', hint: '是否循环', default: false },
  ],
  FILTER: [
    { key: 'type', label: '滤波器类型', type: 'select', options: ['lowpass', 'highpass', 'bandpass', 'notch'], hint: '滤波类型', default: 'lowpass' },
    { key: 'cutoff', label: '截止频率', type: 'number', hint: 'Hz', default: 50 },
    { key: 'order', label: '阶数', type: 'slider', min: 1, max: 8, hint: '滤波器阶数', default: 4 },
  ],
  DOWNSAMPLE: [
    { key: 'mode', label: '模式', type: 'select', options: ['targetRate', 'factor'], hint: '目标频率或倍率', default: 'targetRate' },
    { key: 'targetRate', label: '目标频率', type: 'number', hint: 'Hz', default: 250 },
    { key: 'factor', label: '降采样倍率', type: 'number', hint: 'factor>=1', default: 2 },
  ],
  UPSAMPLE: [
    { key: 'mode', label: '模式', type: 'select', options: ['targetRate', 'factor'], hint: '目标频率或倍率', default: 'targetRate' },
    { key: 'targetRate', label: '目标频率', type: 'number', hint: 'Hz', default: 1000 },
    { key: 'factor', label: '升采样倍率', type: 'number', hint: 'factor>=1', default: 2 },
  ],
  SUM: [
    { key: 'inputs', label: '输入配置', type: 'text', hint: '每个输入独立权重', default: [{ label: '输入1', weight: 1 }, { label: '输入2', weight: 1 }] },
  ],
  AVERAGE: [
    { key: 'inputs', label: '输入配置', type: 'text', hint: '每个输入独立权重', default: [{ label: '输入1', weight: 1 }, { label: '输入2', weight: 1 }] },
  ],
  SPLIT: [
    { key: 'outputs', label: '输出配置', type: 'text', hint: '每个输出独立通道配置', default: [{ label: '输出1', channelIndices: '0,1,2,3' }] },
  ],
  MERGE: [
    { key: 'inputs', label: '输入配置', type: 'text', hint: '每个输入独立增益', default: [{ label: '输入1', gain: 1 }, { label: '输入2', gain: 1 }] },
    { key: 'strategy', label: '合并策略', type: 'select', options: ['concat', 'interleave'], hint: '数据合并方式', default: 'concat' },
  ],
  OUTPUT: [
    { key: 'fftSize', label: 'FFT大小', type: 'select', options: ['256', '512', '1024', '2048'], hint: '频谱分析精度', default: 512 },
    { key: 'saveEnabled', label: '启用录制', type: 'boolean', hint: '是否保存数据到文件', default: false },
    { key: 'filename', label: '文件名', type: 'text', hint: '录制文件名', default: '' },
    { key: 'format', label: '文件格式', type: 'select', options: ['CSV', 'MAT', 'NPY'], hint: '录制文件格式', default: 'CSV' },
  ],
  CUSTOM_PYFUNC: [
    { key: 'portMode', label: '端口模式', type: 'select', options: ['fixed', 'adaptive'], hint: 'fixed=固定数量，adaptive=自适应', default: 'fixed' },
    { key: 'inputCount', label: '输入数量', type: 'number', hint: '固定模式生效', default: 2 },
    { key: 'outputCount', label: '输出数量', type: 'number', hint: '固定模式生效', default: 1 },
    { key: 'hopMode', label: '滑动间隔模式', type: 'select', options: ['points', 'milliseconds', 'targetRate'], hint: '决定输出频率', default: 'points' },
    { key: 'hopPoints', label: '滑动点数', type: 'number', hint: 'points模式', default: 1 },
    { key: 'hopMs', label: '滑动毫秒', type: 'number', hint: 'milliseconds模式', default: 10 },
    { key: 'outputSampleRate', label: '目标输出频率', type: 'number', hint: 'targetRate模式', default: 100 },
  ],
  CUSTOM_CONV: [
    { key: 'kernel', label: '卷积核', type: 'text', hint: '例如: 0.25,0.5,0.25', default: '0.25,0.5,0.25' },
  ],
};

// 节点类型配置
const nodeTypes: Record<GraphNodeType, { name: string; color: string; bg: string; icon: string; hasInput: boolean; hasOutput: boolean }> = {
  SOURCE: { name: '数据源', color: '#1976D2', bg: '#E3F2FD', icon: 'SRC', hasInput: false, hasOutput: true },
  REPLAY: { name: '回放', color: '#1976D2', bg: '#E3F2FD', icon: 'RPL', hasInput: false, hasOutput: true },
  FILTER: { name: '滤波器', color: '#388E3C', bg: '#E8F5E9', icon: 'FIL', hasInput: true, hasOutput: true },
  DOWNSAMPLE: { name: '降采样', color: '#6D4C41', bg: '#EFEBE9', icon: 'DS', hasInput: true, hasOutput: true },
  UPSAMPLE: { name: '升采样', color: '#455A64', bg: '#ECEFF1', icon: 'US', hasInput: true, hasOutput: true },
  SUM: { name: '求和器', color: '#7B1FA2', bg: '#F3E5F5', icon: 'SUM', hasInput: true, hasOutput: true },
  AVERAGE: { name: '平均器', color: '#6A1B9A', bg: '#F3E5F5', icon: 'AVG', hasInput: true, hasOutput: true },
  SPLIT: { name: '分离器', color: '#F9A825', bg: '#FFF8E1', icon: 'SPT', hasInput: true, hasOutput: true },
  MERGE: { name: '合并器', color: '#EF6C00', bg: '#FFF3E0', icon: 'MRG', hasInput: true, hasOutput: true },
  OUTPUT: { name: '显示与录制', color: '#00796B', bg: '#E0F2F1', icon: 'OUT', hasInput: true, hasOutput: false },
  CUSTOM_PYFUNC: { name: 'Python函数', color: '#5E35B1', bg: '#EDE7F6', icon: 'PY', hasInput: true, hasOutput: true },
  CUSTOM_CONV: { name: '卷积节点', color: '#00897B', bg: '#E0F2F1', icon: 'CNV', hasInput: true, hasOutput: true },
};

// 节点元信息映射（用于边栏图标/标题，使用 mdi 图标更直观）
const nodeMetaMap: Record<string, { name: string; icon: string; color: string }> = {
  SOURCE: { name: '数据源', icon: 'mdi-database', color: 'primary' },
  REPLAY: { name: '回放', icon: 'mdi-play-circle', color: 'primary' },
  FILTER: { name: '滤波器', icon: 'mdi-filter', color: 'success' },
  DOWNSAMPLE: { name: '降采样', icon: 'mdi-arrow-collapse-down', color: 'brown' },
  UPSAMPLE: { name: '升采样', icon: 'mdi-arrow-expand-up', color: 'blue-grey' },
  SUM: { name: '求和器', icon: 'mdi-plus-circle', color: 'purple' },
  AVERAGE: { name: '平均器', icon: 'mdi-format-vertical-align-center', color: 'purple' },
  SPLIT: { name: '分离器', icon: 'mdi-call-split', color: 'warning' },
  MERGE: { name: '合并器', icon: 'mdi-call-merge', color: 'orange' },
  OUTPUT: { name: '显示与录制', icon: 'mdi-chart-line', color: 'teal' },
  CUSTOM_PYFUNC: { name: 'Python函数', icon: 'mdi-language-python', color: 'deep-purple' },
  CUSTOM_CONV: { name: '卷积节点', icon: 'mdi-waveform', color: 'cyan-darken-2' },
};

const sourceNodes = [
  { type: 'REPLAY' as GraphNodeType, name: '文件回放', icon: 'RPL', color: '#1976D2', bg: '#E3F2FD', desc: '回放 saved_data 中已录制的 CSV 数据' },
];

const processNodes = [
  { type: 'FILTER' as GraphNodeType, name: '滤波器', icon: 'FIL', color: '#388E3C', bg: '#E8F5E9', desc: '按频率筛选信号：去漂移、去工频干扰或提取脑电节律' },
  { type: 'DOWNSAMPLE' as GraphNodeType, name: '降采样', icon: 'DS', color: '#6D4C41', bg: '#EFEBE9', desc: '降低采样率，减小数据量' },
  { type: 'UPSAMPLE' as GraphNodeType, name: '升采样', icon: 'US', color: '#455A64', bg: '#ECEFF1', desc: '插值提高采样率' },
  { type: 'SUM' as GraphNodeType, name: '求和器', icon: 'SUM', color: '#7B1FA2', bg: '#F3E5F5', desc: '多路信号按权重逐通道相加' },
  { type: 'AVERAGE' as GraphNodeType, name: '平均器', icon: 'AVG', color: '#6A1B9A', bg: '#F3E5F5', desc: '多路信号按权重逐通道平均' },
  { type: 'SPLIT' as GraphNodeType, name: '分离器', icon: 'SPT', color: '#F9A825', bg: '#FFF8E1', desc: '把部分通道拆分成独立输出（如按脑区）' },
  { type: 'MERGE' as GraphNodeType, name: '合并器', icon: 'MRG', color: '#EF6C00', bg: '#FFF3E0', desc: '把多路信号合并为一路多通道信号' },
  { type: 'CUSTOM_PYFUNC' as GraphNodeType, name: 'Python函数', icon: 'PY', color: '#5E35B1', bg: '#EDE7F6', desc: '用 Python 编写自定义处理逻辑' },
  { type: 'CUSTOM_CONV' as GraphNodeType, name: '卷积节点', icon: 'CNV', color: '#00897B', bg: '#E0F2F1', desc: '自定义卷积核做滑动滤波（如平滑）' },
];

const outputNodes = [
  { type: 'OUTPUT' as GraphNodeType, name: '显示与录制', icon: 'OUT', color: '#00796B', bg: '#E0F2F1', desc: '连接示波器查看波形/频谱，并可录制到文件' },
];

// 选择节点并在右侧边栏显示
function selectNode(nodeId: string) {
  selectedNodeId.value = nodeId;
  sidebarVisible.value = true;
  openNodeEditDialog(nodeId);
}

// 折叠边栏（保留选中状态，便于重新展开）
function closeSidebar() {
  sidebarVisible.value = false;
}

// 重新展开边栏
function reopenSidebar() {
  sidebarVisible.value = true;
}

// 打开节点编辑对话框
function openNodeEditDialog(nodeId: string) {
  const graph = graphRef.value;
  if (!graph) return;

  const node = graph.getCellById(nodeId);
  if (!node || !node.isNode()) return;

  const data = node.getData() as GraphNode;
  const { x, y } = node.position();

  // 更新所有节点和边的信息
  allNodes.value = graph.getNodes().map((n) => {
    const nodeData = n.getData() as GraphNode;
    const pos = n.position();
    return { ...nodeData, id: n.id, x: pos.x, y: pos.y };
  });
  allEdges.value = graph.getEdges().map((e) => ({
    id: e.id,
    source: e.getSourceCellId() || '',
    target: e.getTargetCellId() || '',
    sourcePort: e.getSourcePortId() || undefined,
    targetPort: e.getTargetPortId() || undefined,
  }));

  // 更新编辑节点数据
  editingNode.value = { ...data, id: nodeId, x, y };
  // 传递冻结状态给对话框
  editingNode.value.frozen = frozen.value;
  // 在右侧边栏中显示节点编辑内容
  // nodeEditDialogOpen.value = true; // 不再需要，因为内容直接显示在边栏中
}

// 处理节点保存
async function handleNodeSave({ name, params, deviceId }: { name: string; params: Record<string, unknown>; deviceId?: string | null }) {
  // 检查编辑权限
  if (!canEditGraphLocal.value) {
    useToast().show('运行中不允许保存节点', 'warning');
    return;
  }
  
  const graph = graphRef.value;
  if (!graph || !editingNode.value) return;

  const node = graph.getCellById(editingNode.value.id);
  if (!node || !node.isNode()) return;

  // 更新节点数据
  const data = node.getData() as GraphNode;
  data.name = name;
  data.params = normalizeNodeParams(data.type, { ...params });
  if (deviceId !== undefined) {
    data.deviceId = deviceId || undefined;
  }
  node.setData(data);

  // 根据配置刷新动态端口
  syncNodePorts(node, data.type, data.params);

  // 参数变化后刷新边标签
  updateAllEdgeLabels();

  // 更新节点标签显示
  const labelText = generateNodeLabel(data.type, data.name, data.params, editingNode.value?.id);
  node.attr('label/text', labelText);

  syncUnsavedState();
}

// 处理示波器绑定
function handleBindOscilloscope({ nodeId, oscId }: { nodeId: string; oscId: string | null }) {
  // 冻结状态下禁止绑定/解绑
  if (frozen.value) {
    return;
  }
  
  if (oscId) {
    sessionStore.bindOutputNode(nodeId, oscId);
  } else {
    sessionStore.unbindOutputNode(nodeId);
  }
}

// 创建节点 HTML - 使用 X6 HTML 节点需要的特殊结构
function createNodeHtml(type: GraphNodeType, name: string) {
  const config = nodeTypes[type];
  return `
    <div class="x6-node" style="width: 100%; height: 100%;">
      <div style="
        width: 180px;
        height: 70px;
        background: rgb(var(--v-theme-surface));
        border: 2px solid ${config.color};
        border-radius: 8px;
        display: flex;
        align-items: center;
        padding: 12px;
        gap: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        box-sizing: border-box;
      ">
        <div style="
          width: 36px;
          height: 36px;
          background: ${config.bg};
          color: ${config.color};
          border-radius: 6px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 12px;
          font-weight: 600;
          flex-shrink: 0;
        ">${config.icon}</div>
        <div style="flex: 1; min-width: 0; overflow: hidden;">
          <div style="font-size: 14px; font-weight: 500; color: rgb(var(--v-theme-on-surface)); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${name}</div>
          <div style="font-size: 11px; color: rgba(var(--v-theme-on-surface), 0.5); margin-top: 2px;">${type}</div>
        </div>
      </div>
    </div>
  `;
}

function parseLegacyNumberList(raw: unknown): number[] {
  if (typeof raw !== 'string') return [];
  return raw
    .split(',')
    .map((item) => Number(item.trim()))
    .filter((n) => !Number.isNaN(n));
}

function normalizeNodeParams(type: GraphNodeType, params: Record<string, unknown>) {
  const normalized = { ...params } as Record<string, unknown>;

  if (type === 'SOURCE') {
    normalized.sampleRate = Math.max(1, Number(normalized.sampleRate || 1000));
    normalized.channels = Math.max(1, Number(normalized.channels || 8));
    // 保留端口号作为设备标识
    if (normalized.port !== undefined) {
      normalized.port = String(normalized.port || '');
    }
    // 清理已废弃的 replay 相关字段
    delete normalized.sourceMode;
    delete normalized.filePath;
    delete normalized.loop;
  }

  if (type === 'FILTER') {
    // 前端表单使用 filterType/cutoffFreq，后端使用 type/cutoff
    // filterType/cutoffFreq 优先（用户刚编辑的值），不存在时回退到 type/cutoff
    if (normalized.filterType !== undefined) {
      normalized.type = String(normalized.filterType);
    }
    if (normalized.cutoffFreq !== undefined) {
      normalized.cutoff = Number(normalized.cutoffFreq);
    }
    // 确保默认值
    normalized.type = String(normalized.type || 'lowpass');
    normalized.cutoff = Number(normalized.cutoff ?? 50);
    normalized.order = Math.max(1, Number(normalized.order || 4));
    // 清理前端专用键
    delete normalized.filterType;
    delete normalized.cutoffFreq;
  }

  if (type === 'OUTPUT') {
    normalized.fftSize = Number(normalized.fftSize || 512);
    if (![256, 512, 1024, 2048].includes(normalized.fftSize)) {
      normalized.fftSize = 512;
    }
    normalized.saveEnabled = Boolean(normalized.saveEnabled || false);
    normalized.filename = String(normalized.filename || '');
    normalized.format = String(normalized.format || 'CSV');
  }

  if (type === 'SUM' || type === 'AVERAGE') {
    const existingInputs = Array.isArray(normalized.inputs) ? normalized.inputs as Array<Record<string, unknown>> : [];
    const legacyWeights = parseLegacyNumberList(normalized.weights);
    const inputs = existingInputs.length > 0
      ? existingInputs
      : (legacyWeights.length > 0
        ? legacyWeights.map((weight, idx) => ({ label: `输入${idx + 1}`, weight }))
        : [{ label: '输入1', weight: 1 }, { label: '输入2', weight: 1 }]);
    normalized.inputs = inputs.map((item, idx) => ({
      label: String(item.label || `输入${idx + 1}`),
      weight: Number(item.weight ?? 1),
    }));
    delete normalized.weights;
  }

  if (type === 'MERGE') {
    const existingInputs = Array.isArray(normalized.inputs) ? normalized.inputs as Array<Record<string, unknown>> : [];
    normalized.inputs = (existingInputs.length > 0 ? existingInputs : [{ label: '输入1', gain: 1 }, { label: '输入2', gain: 1 }])
      .map((item, idx) => ({
        label: String(item.label || `输入${idx + 1}`),
        gain: Number(item.gain ?? 1),
      }));
    normalized.strategy = String(normalized.strategy || 'concat');
  }

  if (type === 'SPLIT') {
    const existingOutputs = Array.isArray(normalized.outputs) ? normalized.outputs as Array<Record<string, unknown>> : [];
    const legacyChannelIndices = typeof normalized.channelIndices === 'string' ? normalized.channelIndices : '0,1,2,3';
    normalized.outputs = (existingOutputs.length > 0 ? existingOutputs : [{ label: '输出1', channelIndices: legacyChannelIndices }])
      .map((item, idx) => ({
        label: String(item.label || `输出${idx + 1}`),
        channelIndices: String(item.channelIndices || ''),
      }));
    delete normalized.channelIndices;
  }

  if (type === 'CUSTOM_PYFUNC') {
    normalized.portMode = String(normalized.portMode || 'fixed');
    normalized.inputCount = Math.max(1, Number(normalized.inputCount || 2));
    normalized.outputCount = Math.max(1, Number(normalized.outputCount || 1));
    normalized.functionName = String(normalized.functionName || 'process_generated');
    normalized.windowMode = String(normalized.windowMode || 'seconds');
    normalized.windowSeconds = Math.max(0.01, Number(normalized.windowSeconds || 1));
    normalized.windowPoints = Math.max(1, Number(normalized.windowPoints || 256));
    normalized.hopMode = String(normalized.hopMode || 'points');
    normalized.hopPoints = Math.max(1, Number(normalized.hopPoints || 1));
    normalized.hopMs = Math.max(1, Number(normalized.hopMs || 10));
    normalized.outputSampleRate = Math.max(1, Number(normalized.outputSampleRate || 100));
    normalized.inputNames = Array.isArray(normalized.inputNames) ? normalized.inputNames : [];
    normalized.outputNames = Array.isArray(normalized.outputNames) ? normalized.outputNames : [];
    normalized.pythonEditableCode = String(normalized.pythonEditableCode || '');
    normalized.pythonCode = String(normalized.pythonCode || '');
  }

  if (type === 'DOWNSAMPLE' || type === 'UPSAMPLE') {
    normalized.mode = String(normalized.mode || 'targetRate');
    normalized.targetRate = Math.max(1, Number(normalized.targetRate || (type === 'DOWNSAMPLE' ? 250 : 1000)));
    normalized.factor = Math.max(1, Number(normalized.factor || 2));
  }

  if (type === 'CUSTOM_CONV') {
    const rawKernel = normalized.kernel;
    if (Array.isArray(rawKernel)) {
      normalized.kernel = rawKernel;
    } else if (typeof rawKernel === 'string') {
      normalized.kernel = rawKernel
        .split(',')
        .map((token) => Number(token.trim()))
        .filter((v) => Number.isFinite(v));
    } else {
      normalized.kernel = [0.25, 0.5, 0.25];
    }
  }

  return normalized;
}

function safePortCount(raw: unknown, fallback = 1): number {
  const parsed = Number(raw);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(1, Math.floor(parsed));
}

function getInputPortIds(type: GraphNodeType, params: Record<string, unknown>): string[] {
  if (type === 'SUM' || type === 'AVERAGE' || type === 'MERGE') {
    const inputs = Array.isArray(params.inputs) ? params.inputs : [];
    const count = Math.max(1, inputs.length || 1);
    return Array.from({ length: count }, (_, idx) => `in-${idx + 1}`);
  }
  const mode = String(params.portMode || 'fixed').toLowerCase();
  if (mode === 'adaptive') return nodeTypes[type].hasInput ? ['in'] : [];
  const count = safePortCount(params.inputCount, 1);
  if (count > 1 && nodeTypes[type].hasInput) {
    return Array.from({ length: count }, (_, idx) => `in-${idx + 1}`);
  }
  return nodeTypes[type].hasInput ? ['in'] : [];
}

function getOutputPortIds(type: GraphNodeType, params: Record<string, unknown>): string[] {
  if (type === 'SPLIT') {
    const outputs = Array.isArray(params.outputs) ? params.outputs : [];
    const count = Math.max(1, outputs.length || 1);
    return Array.from({ length: count }, (_, idx) => `out-${idx + 1}`);
  }
  const mode = String(params.portMode || 'fixed').toLowerCase();
  if (mode === 'adaptive') return nodeTypes[type].hasOutput ? ['out'] : [];
  const count = safePortCount(params.outputCount, 1);
  if (count > 1 && nodeTypes[type].hasOutput) {
    return Array.from({ length: count }, (_, idx) => `out-${idx + 1}`);
  }
  return nodeTypes[type].hasOutput ? ['out'] : [];
}

// 创建端口
function createPorts(type: GraphNodeType, params: Record<string, unknown>) {
  const config = nodeTypes[type];
  const inputPortIds = getInputPortIds(type, params);
  const outputPortIds = getOutputPortIds(type, params);
  const items = [
    ...inputPortIds.map((id) => ({ id, group: 'in' })),
    ...outputPortIds.map((id) => ({ id, group: 'out' })),
  ];
  return {
    groups: {
      in: {
        position: 'left',
        attrs: {
          circle: {
            r: 5,
            magnet: true,
            stroke: '#E53935',
            strokeWidth: 2,
            fill: '#FFCDD2',
            style: { visibility: 'hidden' },
          },
          text: {
            fontSize: 0,
            refX: -8,
            refY: 2,
            textAnchor: 'end',
            fill: '#999',
            text: '',
          },
        },
      },
      out: {
        position: { name: 'right', args: { dx: -5 } },
        attrs: {
          circle: {
            r: 5,
            magnet: true,
            stroke: '#43A047',
            strokeWidth: 2,
            fill: '#C8E6C9',
            style: { visibility: 'hidden' },
          },
          text: {
            fontSize: 0,
            refX: 8,
            refY: 2,
            textAnchor: 'start',
            fill: '#999',
            text: '',
          },
        },
      },
    },
    items,
  };
}

function syncNodePorts(node: import('@antv/x6').Node, type: GraphNodeType, params: Record<string, unknown>) {
  const graph = graphRef.value;
  if (!graph) return;

  const ports = createPorts(type, params);
  const dynamicNode = node as unknown as {
    setPorts?: (ports: unknown) => void;
    prop: (path: string, value: unknown) => void;
  };

  // 不同 X6 版本 API 有差异：优先调用 setPorts，不存在时回退到 prop('ports', ...)
  if (typeof dynamicNode.setPorts === 'function') {
    dynamicNode.setPorts(ports);
  } else {
    dynamicNode.prop('ports', ports);
  }

  const validInputPorts = new Set(getInputPortIds(type, params));
  const validOutputPorts = new Set(getOutputPortIds(type, params));

  graph.getConnectedEdges(node).forEach((edge) => {
    const sourceCellId = edge.getSourceCellId();
    const targetCellId = edge.getTargetCellId();
    const sourcePortId = edge.getSourcePortId();
    const targetPortId = edge.getTargetPortId();

    const invalidSourcePort = sourceCellId === node.id && sourcePortId && !validOutputPorts.has(sourcePortId);
    const invalidTargetPort = targetCellId === node.id && targetPortId && !validInputPorts.has(targetPortId);
    if (invalidSourcePort || invalidTargetPort) {
      edge.remove();
    }
  });
}

function getDefaultNodeInputPort(nodeId: string): string {
  const graph = graphRef.value;
  if (!graph) return 'in';
  const node = graph.getCellById(nodeId);
  if (!node || !node.isNode()) return 'in';
  const data = node.getData() as GraphNode;
  const params = (data?.params || {}) as Record<string, unknown>;
  return getInputPortIds(data.type, params)[0] || 'in';
}

function getDefaultNodeOutputPort(nodeId: string): string {
  const graph = graphRef.value;
  if (!graph) return 'out';
  const node = graph.getCellById(nodeId);
  if (!node || !node.isNode()) return 'out';
  const data = node.getData() as GraphNode;
  const params = (data?.params || {}) as Record<string, unknown>;
  return getOutputPortIds(data.type, params)[0] || 'out';
}

function formatEdgeChannelLabel(channelNames: string[], sampleRate?: number | null) {
  const rateText = Number.isFinite(sampleRate) && (sampleRate || 0) > 0
    ? `\n${Math.round(sampleRate || 0)} sps`
    : '';
  if (channelNames.length === 0) return '无通道';
  return `${channelNames.length}ch${rateText}`;
}

function getEdgeTooltipText(channelNames: string[]): string {
  if (channelNames.length === 0) return '无通道';
  if (channelNames.length <= 8) return channelNames.join('\n');
  return `${channelNames.slice(0, 8).join('\n')}\n... (共${channelNames.length}个通道)`;
}

function parsePortIndex(portId: string | undefined, fallback = 0) {
  if (!portId) return fallback;
  const match = portId.match(/-(\d+)$/);
  if (!match) return fallback;
  const parsed = Number(match[1]);
  return Number.isFinite(parsed) ? Math.max(0, parsed - 1) : fallback;
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

function defaultChannelNames(count: number) {
  return Array.from({ length: Math.max(0, count) }, (_, idx) => `CH${idx + 1}`);
}

function inferNodeOutputChannels(nodeId: string, sourcePort?: string, visited = new Set<string>()): string[] {
  const graph = graphRef.value;
  if (!graph) return [];
  if (visited.has(nodeId)) return [];
  visited.add(nodeId);

  const node = graph.getCellById(nodeId);
  if (!node || !node.isNode()) return [];
  const data = node.getData() as GraphNode;
  const params = (data.params || {}) as Record<string, unknown>;

  const incomingEdges = (graph.getIncomingEdges(node) || [])
    .slice()
    .sort((a, b) => (a.getTargetPortId() || '').localeCompare(b.getTargetPortId() || ''));

  if (data.type === 'SOURCE') {
    const names = Array.isArray(params.channelNames) ? params.channelNames.map((n) => String(n)) : [];
    if (names.length > 0) return names;
    const channels = Number(params.channels || 8);
    return defaultChannelNames(Number.isFinite(channels) ? channels : 8);
  }

  if (data.type === 'REPLAY') {
    const names = Array.isArray(params.channelNames) ? params.channelNames.map((n) => String(n)) : [];
    return names.length > 0 ? names : defaultChannelNames(8);
  }

  const upstreamEdge = incomingEdges[0];
  const upstreamNodeId = upstreamEdge?.getSourceCellId();
  const upstreamPortId = upstreamEdge?.getSourcePortId() || undefined;
  const upstreamChannels = upstreamNodeId ? inferNodeOutputChannels(upstreamNodeId, upstreamPortId, visited) : [];

  if (data.type === 'FILTER') {
    return upstreamChannels;
  }

  if (data.type === 'SUM' || data.type === 'AVERAGE') {
    return [data.name || data.type];
  }

  if (data.type === 'MERGE') {
    const merged: string[] = [];
    incomingEdges.forEach((edge) => {
      const sourceId = edge.getSourceCellId();
      if (!sourceId) return;
      const sourceNames = inferNodeOutputChannels(sourceId, edge.getSourcePortId() || undefined, new Set(visited));
      merged.push(...sourceNames);
    });
    return merged;
  }

  if (data.type === 'SPLIT') {
    const paramsOutputs = Array.isArray(params.outputs) ? params.outputs as Array<Record<string, unknown>> : [];
    const outputIdx = parsePortIndex(sourcePort, 0);
    const outputCfg = paramsOutputs[outputIdx] || paramsOutputs[0];
    const indices = parseIndices(outputCfg?.channelIndices);
    const selected = indices.map((idx) => upstreamChannels[idx]).filter((name): name is string => Boolean(name));
    if (selected.length > 0) return selected;
    if (typeof outputCfg?.label === 'string' && outputCfg.label.trim() !== '') {
      return [outputCfg.label.trim()];
    }
    return upstreamChannels;
  }

  return upstreamChannels;
}

function inferNodeOutputSampleRate(nodeId: string, sourcePort?: string, visited = new Set<string>()): number | null {
  const graph = graphRef.value;
  if (!graph) return null;
  if (visited.has(nodeId)) return null;
  visited.add(nodeId);

  const node = graph.getCellById(nodeId);
  if (!node || !node.isNode()) return null;
  const data = node.getData() as GraphNode;
  const params = (data.params || {}) as Record<string, unknown>;

  const incomingEdges = (graph.getIncomingEdges(node) || [])
    .slice()
    .sort((a, b) => (a.getTargetPortId() || '').localeCompare(b.getTargetPortId() || ''));

  if (data.type === 'SOURCE' || data.type === 'REPLAY') {
    const sr = Number(params.sampleRate || 1000);
    return Number.isFinite(sr) && sr > 0 ? sr : 1000;
  }

  const upstreamEdge = incomingEdges[0];
  const upstreamNodeId = upstreamEdge?.getSourceCellId();
  const upstreamPortId = upstreamEdge?.getSourcePortId() || undefined;
  const upstreamRate = upstreamNodeId ? inferNodeOutputSampleRate(upstreamNodeId, upstreamPortId, visited) : null;

  if (data.type === 'DOWNSAMPLE') {
    const inRate = upstreamRate || 1000;
    const mode = String(params.mode || 'targetRate').toLowerCase();
    if (mode === 'factor') {
      const factor = Math.max(1, Number(params.factor || 2));
      return inRate / factor;
    }
    const targetRate = Math.max(1, Number(params.targetRate || inRate / 2));
    return Math.min(inRate, targetRate);
  }

  if (data.type === 'UPSAMPLE') {
    const inRate = upstreamRate || 1000;
    const mode = String(params.mode || 'targetRate').toLowerCase();
    if (mode === 'factor') {
      const factor = Math.max(1, Number(params.factor || 2));
      return inRate * factor;
    }
    return Math.max(1, Number(params.targetRate || inRate));
  }

  if (data.type === 'CUSTOM_PYFUNC') {
    const inRate = upstreamRate || 1000;
    const hopMode = String(params.hopMode || 'points').toLowerCase();
    if (hopMode === 'targetRate') {
      return Math.max(1, Number(params.outputSampleRate || inRate));
    }
    if (hopMode === 'milliseconds') {
      const hopMs = Math.max(1, Number(params.hopMs || 10));
      return 1000 / hopMs;
    }
    const hopPoints = Math.max(1, Number(params.hopPoints || 1));
    return inRate / hopPoints;
  }

  return upstreamRate;
}

function inferEdgeChannelNames(edge: import('@antv/x6').Edge): string[] {
  const graph = graphRef.value;
  if (!graph) return [];

  const sourceNodeId = edge.getSourceCellId();
  if (!sourceNodeId) return [];
  const sourceNode = graph.getCellById(sourceNodeId);
  if (!sourceNode || !sourceNode.isNode()) return [];

  const sourceData = sourceNode.getData() as GraphNode;
  const sourcePort = edge.getSourcePortId() || 'out';

  if (sourceData.type === 'SPLIT') {
    const params = (sourceData.params || {}) as Record<string, unknown>;
    const outputs = Array.isArray(params.outputs) ? params.outputs as Array<Record<string, unknown>> : [];
    const outputIdx = parsePortIndex(sourcePort, 0);
    const outputCfg = outputs[outputIdx] || outputs[0];

    const incomingEdges = graph.getIncomingEdges(sourceNode) || [];
    const inputEdge = incomingEdges[0];
    const upstreamId = inputEdge?.getSourceCellId();
    const upstreamNames = upstreamId ? inferNodeOutputChannels(upstreamId) : [];
    const indices = parseIndices(outputCfg?.channelIndices);
    const selected = indices.map((idx) => upstreamNames[idx]).filter((name): name is string => Boolean(name));
    if (selected.length > 0) return selected;
    if (typeof outputCfg?.label === 'string' && outputCfg.label.trim() !== '') {
      return [outputCfg.label.trim()];
    }
    return [];
  }

  if (sourceData.type === 'SUM' || sourceData.type === 'AVERAGE') {
    return [sourceData.name || sourceData.type];
  }

  return inferNodeOutputChannels(sourceNodeId, sourcePort);
}

function applyEdgeLabel(edge: import('@antv/x6').Edge) {
  const channelNames = inferEdgeChannelNames(edge);
  const sourceNodeId = edge.getSourceCellId();
  const sourcePort = edge.getSourcePortId() || undefined;
  const sampleRate = sourceNodeId ? inferNodeOutputSampleRate(sourceNodeId, sourcePort) : null;
  const label = formatEdgeChannelLabel(channelNames, sampleRate);
  const tooltipText = getEdgeTooltipText(channelNames);
  
  edge.setLabels([
    {
      position: {
        distance: 0.5,
        options: {
          keepGradient: true,
          ensureLegibility: true,
        },
      },
      attrs: {
        label: {
          text: label,
          fill: '#546E7A',
          fontSize: 11,
          textAnchor: 'middle',
          textVerticalAnchor: 'middle',
          cursor: 'help',
        },
        rect: {
          fill: '#ffffff',
          stroke: '#CFD8DC',
          strokeWidth: 1,
          rx: 8,
          ry: 8,
          refWidth: '120%',
          refHeight: '140%',
          refX: '-10%',
          refY: '-20%',
          cursor: 'help',
        },
      },
    },
  ]);
  
  // 添加tooltip
  edge.setAttrByPath('label/title', tooltipText);
  edge.setAttrByPath('labelContainer/title', tooltipText);
}

function updateAllEdgeLabels() {
  const graph = graphRef.value;
  if (!graph) return;
  graph.getEdges().forEach((edge) => applyEdgeLabel(edge));
}

// 添加节点 - 使用 rect 形状配合 attrs
function addNode(type: GraphNodeType, x: number, y: number, name?: string, params?: Record<string, unknown>, existingId?: string, boundDeviceId?: string) {
  const graph = graphRef.value;
  if (!graph) return null;

  const config = nodeTypes[type];
  // 优先使用传入的ID（从后端加载时），确保ID有效
  const nodeId = existingId && existingId.trim() !== '' 
    ? existingId 
    : `node-${Date.now()}-${Math.floor(Math.random() * 1000)}`;

  // 初始化默认参数
  const paramConfig = nodeParamConfigs[type];
  const defaultParams: Record<string, unknown> = {};
  paramConfig.forEach((field) => {
    defaultParams[field.key] = field.default;
  });

  // 合并传入的参数
  const nodeParams = normalizeNodeParams(type, { ...defaultParams, ...params });

  // 生成带属性的标签文本
  const labelText = generateNodeLabel(type, name || config.name, nodeParams, nodeId);

  const node = graph.addNode({
    id: nodeId,
    shape: 'rect',
    x,
    y,
    width: 180,
    height: 70,
    attrs: {
      body: {
        fill: '#fff',
        stroke: config.color,
        strokeWidth: 2,
        rx: 8,
        ry: 8,
      },
      label: {
        text: labelText,
        fill: '#333',
        fontSize: 12,
        fontWeight: 500,
        refY: 0.5,
        textVerticalAnchor: 'middle',
      },
    },
    ports: createPorts(type, nodeParams),
    data: { type, name: name || config.name, params: nodeParams, deviceId: boundDeviceId },
  });

  hasNodes.value = true;
  return node;
}

// 生成节点标签（显示名称+关键属性+绑定状态）
function generateNodeLabel(type: GraphNodeType, name: string, params: Record<string, unknown>, nodeId?: string): string {
  const keyParam = getKeyParamDisplay(type, params);
  // 检查节点是否被示波器视图绑定
  const isBound = nodeId ? sessionStore.isNodeBoundByView(nodeId) : false;
  const boundIndicator = isBound ? '🔗 ' : '';
  
  if (keyParam) {
    return `${boundIndicator}${name}\n${keyParam}`;
  }
  return `${boundIndicator}${name}`;
}

// 获取节点关键属性显示文本
function getKeyParamDisplay(type: GraphNodeType, params: Record<string, unknown>): string {
  switch (type) {
    case 'FILTER':
      const filterType = params['type'] || 'lowpass';
      const cutoff = params['cutoff'] || 50;
      return `${filterType} ${cutoff}Hz`;
    case 'DOWNSAMPLE': {
      const mode = String(params['mode'] || 'targetRate');
      if (mode === 'factor') return `/${Math.max(1, Number(params['factor'] || 2))}`;
      return `→${Math.max(1, Number(params['targetRate'] || 250))}Hz`;
    }
    case 'UPSAMPLE': {
      const mode = String(params['mode'] || 'targetRate');
      if (mode === 'factor') return `x${Math.max(1, Number(params['factor'] || 2))}`;
      return `→${Math.max(1, Number(params['targetRate'] || 1000))}Hz`;
    }
    case 'OUTPUT': {
      const fft = params['fftSize']
        ? `FFT${params['fftSize']} `
        : '';
      const save = params['saveEnabled'] ? '📝' : '';
      return `${fft}${save}`.trim() || '显示';
    }
    case 'SOURCE': {
      const sampleRate = params['sampleRate'] || 1000;
      const channels = params['channels'] || 8;
      const port = params['port'];
      const portDesc = port ? ` ${port}` : '';
      return `${sampleRate}Hz ${channels}ch${portDesc}`;
    }
    case 'SUM': {
      const inputs = Array.isArray(params['inputs']) ? params['inputs'] : [];
      return `${inputs.length || 0}路输入`;
    }
    case 'AVERAGE': {
      const inputs = Array.isArray(params['inputs']) ? params['inputs'] : [];
      return `${inputs.length || 0}路输入`;
    }
    case 'SPLIT': {
      const outputs = Array.isArray(params['outputs']) ? params['outputs'] : [];
      return `${outputs.length || 0}路输出`;
    }
    case 'MERGE': {
      const inputs = Array.isArray(params['inputs']) ? params['inputs'] : [];
      const strategy = params['strategy'] || 'concat';
      return `${inputs.length || 0}→1 ${strategy}`;
    }
    case 'CUSTOM_PYFUNC': {
      const mode = params['portMode'] || 'fixed';
      const inputCount = Number(params['inputCount'] || 2);
      const outputCount = Number(params['outputCount'] || 1);
      const hopMode = String(params['hopMode'] || 'points');
      const hopDesc = hopMode === 'targetRate'
        ? `${Math.max(1, Number(params['outputSampleRate'] || 100))}Hz`
        : (hopMode === 'milliseconds' ? `${Math.max(1, Number(params['hopMs'] || 10))}ms` : `${Math.max(1, Number(params['hopPoints'] || 1))}pt`);
      if (String(mode) === 'adaptive') return 'I/O 自适应';
      return `${inputCount}→${outputCount} @${hopDesc}`;
    }
    case 'CUSTOM_CONV': {
      const kernel = Array.isArray(params['kernel']) ? params['kernel'] : [];
      return `kernel=${kernel.length || 0}`;
    }
    default:
      return '';
  }
}

// 拖拽开始
function onDragStart(e: DragEvent, type: GraphNodeType) {
  // 检查编辑权限
  if (!canEditGraphLocal.value) {
    e.preventDefault();
    useToast().show('运行中不允许添加节点', 'warning');
    return;
  }
  
  e.dataTransfer?.setData('node-type', type);
  e.dataTransfer!.effectAllowed = 'copy';
}

function onDragStartDevice(e: DragEvent, deviceId: string) {
  if (!canEditGraphLocal.value) {
    e.preventDefault();
    return;
  }
  e.dataTransfer?.setData('device-id', deviceId);
  e.dataTransfer!.effectAllowed = 'copy';
}

// 从后端加载数据
async function loadFromBackend() {
  try {
    const backendPayload = await fetchGraph();
    currentRevision.value = Number(backendPayload.revision || 0);
    persistedRevision.value = Number(backendPayload.persistedRevision || 0);

    try {
      await pollRuntimeState();
    } catch (e) {
      console.warn('[GraphEditor] Failed to poll runtime state on load:', e);
    }

    applyPayloadToCanvas(backendPayload, { fromBackend: true, reason: 'initial' });
  } catch (err) {
    console.error('Failed to load graph:', err);
    hasNodes.value = false;
  }
}

function applyPayloadToCanvas(payload: GraphPayload, options?: { fromBackend?: boolean; reason?: string }) {
  const graph = graphRef.value;
  if (!graph) return;

  isApplyingBackendGraph.value = true;
  try {
    const safePayload: GraphPayload = {
      nodes: Array.isArray(payload.nodes) ? payload.nodes : [],
      edges: Array.isArray(payload.edges) ? payload.edges : [],
      frozen: Boolean(payload.frozen),
    };

    setRuntimeState({ frozen: safePayload.frozen });

    // 先断开所有边，再清理节点，确保 X6 内部状态完全重置
    graph.getEdges().forEach((e) => e.remove());
    graph.clearCells();

    safePayload.nodes.forEach((node: GraphNode) => {
      if (!node.id) {
        node.id = `node-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
      }
      addNode(node.type, node.x, node.y, node.name, node.params, node.id);
    });

    safePayload.edges.forEach((edge) => {
      const sourceNode = graph.getCellById(edge.source);
      const targetNode = graph.getCellById(edge.target);
      if (!sourceNode || !targetNode) return;
      graph.addEdge({
        id: edge.id,
        source: { cell: edge.source, port: edge.sourcePort || getDefaultNodeOutputPort(edge.source) },
        target: { cell: edge.target, port: edge.targetPort || getDefaultNodeInputPort(edge.target) },
        attrs: { line: { stroke: '#5F95FF', strokeWidth: 2, targetMarker: 'block' } },
      });
    });

    hasNodes.value = graph.getNodes().length > 0;
    updateAllEdgeLabels();
    setGraphInteracting(graph, !frozen.value);

    if (options?.fromBackend) {
      editorSignature.value = payloadSignature(safePayload);
      backendSignature.value = editorSignature.value;
    }
  } finally {
    isApplyingBackendGraph.value = false;
  }
}

function setGraphInteracting(graph: Graph, enabled: boolean) {
  // X6 2.x: 使用 options 配置交互状态
  if (graph) {
    // 简化逻辑：直接使用传入的enabled参数
    // 不再额外检查canEditGraphLocal，因为调用者已经考虑了状态
    graph.options.interacting = enabled ? {
      nodeMovable: true,
      edgeMovable: true,
      edgeLabelMovable: true,
      arrowheadMovable: true,
      vertexMovable: true,
      vertexAddable: true,
      vertexDeletable: true,
    } : false;
    
    // 更新界面提示
    if (!enabled) {
    } else {
    }
  }
}

async function applyFrozen() {
  const graph = graphRef.value;
  if (!graph) {
    console.warn('[GraphEditor] applyFrozen: graph ref is null');
    return;
  }


  // 更新图形编辑权限：只有在未冻结且未运行时才允许编辑
  const canEdit = !frozen.value && !isRunning.value;
  if (graph) {
    setGraphInteracting(graph, canEdit);
  }
  
  if (frozen.value) {
    
    // 如果计算图正在运行，自动建立WebSocket连接
    if (isRunning.value) {
      await connectWebSocket();
    }
  } else {
    
    // 如果计算图未运行，断开WebSocket连接
    if (!isRunning.value) {
      disconnectWebSocket();
    }
  }
}

function buildPayload(): GraphPayload {
  const graph = graphRef.value;
  if (!graph) return { nodes: [], edges: [], frozen: frozen.value };

  const nodes: GraphNode[] = graph.getNodes().map((node) => {
    const data = node.getData() as GraphNode;
    const { x, y } = node.position();
    return { ...data, id: node.id, x, y };
  });

  const edges = graph.getEdges().map((edge) => ({
    id: edge.id,
    source: edge.getSourceCellId() || '',
    target: edge.getTargetCellId() || '',
    sourcePort: edge.getSourcePortId() || undefined,
    targetPort: edge.getTargetPortId() || undefined,
  }));

  return { nodes, edges, frozen: frozen.value };
}

// 保存状态到会话存储
function saveStateToSessionStorage() {
  try {
    const graph = graphRef.value;
    if (!graph) return;

    const payload = buildPayload();
    
    // 只保存有效的状态（有节点或计算图正在运行）
    const isValidState = payload.nodes.length > 0 || isRunning.value;
    if (!isValidState) {
      return;
    }
    
    const state = {
      payload,
      isRunning: isRunning.value,
      runtimeMode: runtimeMode.value,
      timestamp: Date.now()
    };
    
    sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(state));
  } catch (err) {
    console.error('[GraphEditor] Failed to save state to session storage:', err);
  }
}

// 从会话存储恢复状态到画布
function restoreStateFromSessionStorage(): boolean {
  try {
    const graph = graphRef.value;
    if (!graph) return false;

    const stateJson = sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (!stateJson) return false;

    const state = JSON.parse(stateJson);
    if (!state.payload || !state.payload.nodes || state.payload.nodes.length === 0) {
      return false;
    }

    // 清空画布
    graph.clearCells();

    // 恢复节点
    state.payload.nodes.forEach((node: GraphNode) => {
      if (!node.id) {
        console.warn('Node without id:', node);
        node.id = `node-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
      }
      addNode(node.type, node.x, node.y, node.name, node.params, node.id);
    });

    // 恢复边
    state.payload.edges.forEach((edge: any) => {
      const sourceNode = graph.getCellById(edge.source);
      const targetNode = graph.getCellById(edge.target);
      if (sourceNode && targetNode) {
        graph.addEdge({
          id: edge.id,
          source: { cell: edge.source, port: edge.sourcePort || getDefaultNodeOutputPort(edge.source) },
          target: { cell: edge.target, port: edge.targetPort || getDefaultNodeInputPort(edge.target) },
          attrs: { line: { stroke: '#5F95FF', strokeWidth: 2, targetMarker: 'block' } },
        });
      } else {
        console.warn('Skipping edge with missing nodes:', edge);
      }
    });

    // 恢复状态
    setRuntimeState({ frozen: state.payload.frozen });
    if (state.isRunning) {
      setRuntimeState({
        isRunning: state.isRunning,
        runtimeMode: state.runtimeMode,
      });
    }

    const finalNodeCount = graph.getNodes().length;
    const finalEdgeCount = graph.getEdges().length;
    hasNodes.value = finalNodeCount > 0;
    
    updateAllEdgeLabels();
    setGraphInteracting(graph, !frozen.value);
    
    return true;
  } catch (err) {
    console.error('[GraphEditor] Failed to restore state from session storage:', err);
    return false;
  }
}

// 从会话存储加载状态
function loadStateFromSessionStorage(): boolean {
  try {
    const stateJson = sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (!stateJson) return false;

    const state = JSON.parse(stateJson);
    
    // 检查状态是否过期（超过5分钟）
    const isExpired = Date.now() - state.timestamp > 5 * 60 * 1000;
    if (isExpired) {
      sessionStorage.removeItem(SESSION_STORAGE_KEY);
      return false;
    }
    
    return true;
  } catch (err) {
    console.error('[GraphEditor] Failed to load state from session storage:', err);
    return false;
  }
}

// 清除会话存储状态
function clearSessionStorage() {
  sessionStorage.removeItem(SESSION_STORAGE_KEY);
}

// 导出计算图为 JSON 文件
function exportGraph() {
  const payload = buildPayload();
  const json = JSON.stringify(payload, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  
  const a = document.createElement('a');
  a.href = url;
  a.download = `eeg-graph-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  
}

// 触发文件选择
function triggerFileLoad() {
  const input = document.getElementById('graph-file-input') as HTMLInputElement;
  if (input) {
    input.click();
  }
}

// 从文件加载计算图
async function loadGraphFromFile(event: Event) {
  // 检查编辑权限
  if (!canEditGraph.value) {
    useToast().show('运行中不允许加载计算图', 'warning');
    // 清空input以便可以再次选择同一文件
    const input = event.target as HTMLInputElement;
    input.value = '';
    return;
  }
  
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;

  try {
    const text = await file.text();
    const payload = JSON.parse(text) as GraphPayload;
    
    // 验证数据结构
    if (!payload.nodes || !Array.isArray(payload.nodes) || !payload.edges || !Array.isArray(payload.edges)) {
      alert('无效的计算图文件格式');
      return;
    }

    const graph = graphRef.value;
    if (!graph) return;

    // 清空当前画布
    graph.clearCells();

    // 加载节点
    payload.nodes.forEach((node: GraphNode) => {
      if (!node.id) {
        console.warn('Node without id:', node);
        node.id = `node-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
      }
      addNode(node.type, node.x, node.y, node.name, node.params, node.id);
    });

    // 加载边
    payload.edges.forEach((edge) => {
      const sourceNode = graph.getCellById(edge.source);
      const targetNode = graph.getCellById(edge.target);
      if (sourceNode && targetNode) {
        graph.addEdge({
          id: edge.id,
          source: { cell: edge.source, port: edge.sourcePort || getDefaultNodeOutputPort(edge.source) },
          target: { cell: edge.target, port: edge.targetPort || getDefaultNodeInputPort(edge.target) },
          attrs: { line: { stroke: '#5F95FF', strokeWidth: 2, targetMarker: 'block' } },
        });
      } else {
        console.warn('Skipping edge with missing nodes:', edge);
      }
    });

    hasNodes.value = graph.getNodes().length > 0;
    setRuntimeState({ frozen: payload.frozen || false });
    updateAllEdgeLabels();
    syncUnsavedState();
    
    alert('计算图加载成功，请点击保存应用到后端。');
  } catch (err) {
    console.error('[GraphEditor] Failed to load graph from file:', err);
    alert('加载失败: ' + (err as Error).message);
  } finally {
    // 清空 input 以便可以再次选择同一文件
    input.value = '';
  }
}

async function run(mode: 'live' | 'offline' = 'live') {
  
  // 检查计算图是否已经在运行
  if (isRunning.value) {
    return;
  }
  
  // 启动 runtime（会验证冻结状态并连接 WebSocket）
  const success = await graphRuntime.start();
  if (!success) {
    console.error('[GraphEditor] Failed to start runtime:', graphRuntime.state.error);
    useToast().show(`启动失败: ${graphRuntime.state.error}`, 'error');
    return;
  }
  
  // 调用后端API
  try {
    await graphRuntimeStore.runByMode(mode);
    {
      setRuntimeState({
        isRunning: true,
        runtimeMode: mode,
        offlineProgress: 0,
      });
      startRuntimeStatePolling();
      
      // 启动边动画（live和offline模式都有动画，但效果不同）
      startEdgeAnimations();
      
      // 调试：记录当前画布状态
      const graph = graphRef.value;
      if (graph) {
        const nodeCount = graph.getNodes().length;
        const edgeCount = graph.getEdges().length;
      }
      
      // 保存状态到会话存储
      saveStateToSessionStorage();
    }
  } catch (err) {
    console.error('[GraphEditor] Failed to run graph:', err);
    alert('运行失败: ' + (err as Error).message);
    return;
  }
  
  // 监听WebSocket连接状态变化
  // WebSocket 连接检查已由 graphRuntimeStore 统一管理
}

// 在 setup 顶层注册 WebSocket 状态监听（vs 在 run() 函数中注册，确保生命周期正确）
let _unsubscribeWsStatus: (() => void) | null = null;
// 延迟初始化，在 onMounted 中注册
// 注意：实际的 WebSocket 状态监听已由 graphRuntimeStore 统一管理，
// 此处仅保留检查逻辑，onUnmounted 中已通过 unsubscribeGraphSync 等清理。

function clear() {
  // 检查编辑权限
  if (!canEditGraph.value) {
    alert('运行中不允许清空计算图');
    return;
  }
  
  if (!confirm('确定要清空计算图吗？所有节点和边将被删除。')) return;
  
  const graph = graphRef.value;
  if (!graph) return;
  
  // 停止运行时
  graphRuntime.stop();
  stopRuntimeStatePolling();
  stopEdgeAnimations();
  setRuntimeState({
    isRunning: false,
    offlineProgress: 0,
    processingDelayMs: 0,
    nonRealtime: false,
    runtimeWarning: null,
  });
  
  graph.clearCells();
  hasNodes.value = false;
  
  // 清除会话存储
  clearSessionStorage();
}

onMounted(async () => {
  if (!container.value) return;

  window.addEventListener('keydown', onSaveHotkey);
  window.addEventListener('beforeunload', onBeforeUnload);

  // 创建画布
  const graph = new Graph({
    container: container.value,
    grid: {
      size: 10,
      visible: true,
      type: 'dot',
      args: [{ color: gridDotColor(), thickness: 1 }],
    },
    background: { color: 'rgb(var(--v-theme-background))' },
    panning: { enabled: true, eventTypes: ['leftMouseDown'] },
    mousewheel: { enabled: true, modifiers: ['ctrl', 'meta'] },
    connecting: {
      snap: { radius: 20 },
      allowBlank: false,
      allowLoop: false,
      allowEdge: false,
      highlight: true,
      router: {
        name: 'metro',
        args: {
          startDirections: ['top', 'right', 'bottom', 'left'],
          endDirections: ['top', 'right', 'bottom', 'left'],
          padding: 10,
          step: 10,
        },
      },
      createEdge() {
        return graph.createEdge({
          attrs: { line: { stroke: '#5F95FF', strokeWidth: 2, targetMarker: 'block' } },
        });
      },
      validateConnection({ sourceMagnet, targetMagnet }) {
        if (!sourceMagnet || sourceMagnet.getAttribute('port-group') === 'in') return false;
        if (!targetMagnet || targetMagnet.getAttribute('port-group') !== 'in') return false;

        const targetPort = targetMagnet.getAttribute('port');
        const targetCellId = targetMagnet.getAttribute('data-cell-id');
        if (targetCellId && targetPort) {
          const hasIncoming = graph.getEdges().some((edge) => {
            return edge.getTargetCellId() === targetCellId && edge.getTargetPortId() === targetPort;
          });
          if (hasIncoming) return false;
        }
        return true;
      },
    },
    highlighting: {
      magnetAdsorbed: {
        name: 'stroke',
        args: { attrs: { fill: '#43A047', stroke: '#43A047' } },
      },
    },
  });

  graphRef.value = graph;

  // 主题切换时重绘网格点（网格颜色烘焙在 data-URI 中，需显式重绘）
  watch(() => vTheme.global.name.value, () => {
    const g = graphRef.value;
    if (!g) return;
    g.drawGrid({ args: { color: gridDotColor(), thickness: 1 } });
  });

  unsubscribeGraphSync = graphSyncWebSocket.onGraph(({ graph: backendGraph, reason }) => {
    const rev = Number((backendGraph as GraphPayload).revision || 0);
    const prev = Number((backendGraph as GraphPayload).persistedRevision || 0);

    // 'synced' 和 'sync_graph' 都是对 sync_graph 命令的回声确认
    if (reason === 'synced' || reason === 'sync_graph') {
      handleSyncConfirmed(payloadSignature(backendGraph), rev, prev);
      return;
    }

    // 其他 reason：服务端主动推送（connected/heartbeat/freeze_changed/runtime 等）
    handleServerPush(backendGraph, reason, rev, prev);
  });

  // 注意：connect() 移到 loadFromBackend() 之后，避免 WebSocket initial 推送与 HTTP 加载竞争

  // 添加对齐线
  graph.use(new Snapline({ enabled: true }));

  // 拖拽放置处理（使用具名函数以便在 onUnmounted 中移除）
  const onDragOver = (e: DragEvent) => {
    e.preventDefault();
    e.dataTransfer!.dropEffect = 'copy';
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    const deviceId = e.dataTransfer?.getData('device-id');
    if (deviceId && container.value) {
      const rect = container.value.getBoundingClientRect();
      const x = e.clientX - rect.left - 90;
      const y = e.clientY - rect.top - 35;
      // 用端口号作为设备节点的统一标识，前后端一致
      const device = paletteDevices.value.find((d) => d.id === deviceId);
      const port = device?.port || '';
      const deviceLabel = port ? `${port}` : (device?.name || deviceId);
      const nodeName = device?.name ? `${device.name.split('(')[0].trim()} (${deviceLabel})` : `设备源 (${deviceLabel})`;
      addNode('SOURCE', x, y, nodeName, { port }, undefined, deviceId);
      return;
    }

    const type = e.dataTransfer?.getData('node-type') as GraphNodeType;
    if (!type || !container.value) return;

    const rect = container.value.getBoundingClientRect();
    const x = e.clientX - rect.left - 90;
    const y = e.clientY - rect.top - 35;

    addNode(type, x, y);
  };

  container.value.addEventListener('dragover', onDragOver);
  container.value.addEventListener('drop', onDrop);

  // 节点悬停显示端口
  graph.on('node:mouseenter', ({ node }) => {
    node.getPorts().forEach((port) => {
      node.setPortProp(port.id!, 'attrs/circle/style/visibility', 'visible');
      // 保持方向颜色：输入=红系，输出=绿系
      const group = port.group || (port.id?.startsWith('in') ? 'in' : 'out');
      if (group === 'in') {
        node.setPortProp(port.id!, 'attrs/circle/stroke', '#E53935');
        node.setPortProp(port.id!, 'attrs/circle/fill', '#FFCDD2');
      } else {
        node.setPortProp(port.id!, 'attrs/circle/stroke', '#43A047');
        node.setPortProp(port.id!, 'attrs/circle/fill', '#C8E6C9');
      }
    });
  });

  graph.on('node:mouseleave', ({ node }) => {
    node.getPorts().forEach((port) => {
      const edges = graph.getConnectedEdges(node);
      const isConnected = edges.some((e) =>
        e.getSourcePortId() === port.id || e.getTargetPortId() === port.id
      );
      node.setPortProp(port.id!, 'attrs/circle/style/visibility', isConnected ? 'visible' : 'hidden');
      // 已连接的端口保持鲜艳颜色
      const group = port.group || (port.id?.startsWith('in') ? 'in' : 'out');
      if (isConnected) {
        if (group === 'in') {
          node.setPortProp(port.id!, 'attrs/circle/fill', '#E53935');
          node.setPortProp(port.id!, 'attrs/circle/stroke', '#C62828');
        } else {
          node.setPortProp(port.id!, 'attrs/circle/fill', '#43A047');
          node.setPortProp(port.id!, 'attrs/circle/stroke', '#2E7D32');
        }
      }
    });
  });

  // 边悬停显示删除按钮（仅在可编辑时显示）
  graph.on('edge:mouseenter', ({ edge }) => {
    if (canEditGraphLocal.value) {
      edge.addTools({ name: 'button-remove', args: { distance: -40 } });
    }
  });

  graph.on('edge:mouseleave', ({ edge }) => {
    edge.removeTools();
  });

  // 节点悬停显示删除按钮（仅在可编辑时显示）
  graph.on('node:mouseenter', ({ node }) => {
    if (canEditGraphLocal.value) {
      node.addTools({
        name: 'button-remove',
        args: {
          x: '100%',
          y: 0,
          offset: { x: -10, y: 10 },
          onClick({ cell }: { cell: any }) {
            if (canEditGraphLocal.value) {
              graph.removeCell(cell);
            } else {
              alert('运行中不允许删除节点');
            }
          }
        }
      });
    }
  });

  graph.on('node:mouseleave', ({ node }) => {
    node.removeTools();
  });

  // 连接成功高亮（使用方向颜色）
  graph.on('edge:connected', ({ edge, currentCell, currentPort }) => {
    if (currentCell && currentPort) {
      // 判断端口方向
      const portInfo = currentCell.getPorts().find((p: any) => p.id === currentPort);
      const group = portInfo?.group || (currentPort?.startsWith('in') ? 'in' : 'out');
      if (group === 'in') {
        currentCell.setPortProp(currentPort, 'attrs/circle/fill', '#E53935');
        currentCell.setPortProp(currentPort, 'attrs/circle/stroke', '#C62828');
      } else {
        currentCell.setPortProp(currentPort, 'attrs/circle/fill', '#43A047');
        currentCell.setPortProp(currentPort, 'attrs/circle/stroke', '#2E7D32');
      }
      currentCell.setPortProp(currentPort, 'attrs/circle/style/visibility', 'visible');
    }
    // 更新连接桩标签
    if (edge) applyEdgeLabel(edge);
  });

  graph.on('edge:removed', () => {
    updateAllEdgeLabels();
  });

  graph.on('edge:change:source', ({ edge }) => {
    if (edge) applyEdgeLabel(edge);
  });

  graph.on('edge:change:target', ({ edge }) => {
    if (edge) applyEdgeLabel(edge);
  });

  graph.on('node:change:position', () => {
    if (!isNodeDragging) {
      isNodeDragging = true;
    }
    // 清除之前的防抖计时器
    if (dragDebounceTimer) {
      clearTimeout(dragDebounceTimer);
    }
    // 拖拽结束后同步状态
    dragDebounceTimer = window.setTimeout(() => {
      isNodeDragging = false;
      dragDebounceTimer = null;
      syncUnsavedState();
    }, 300);
  });

  graph.on('node:added', () => {
    syncUnsavedState();
  });

  graph.on('node:removed', () => {
    hasNodes.value = graph.getNodes().length > 0;
    syncUnsavedState();
  });

  graph.on('edge:added', () => {
    syncUnsavedState();
  });

  graph.on('edge:removed', () => {
    hasNodes.value = graph.getNodes().length > 0;
    syncUnsavedState();
  });

  // 节点单击：选择节点
  graph.on('node:click', ({ node }) => {
    selectNode(node.id);
  });

  // 节点双击：选择节点
  graph.on('node:dblclick', ({ node }) => {
    selectNode(node.id);
  });

  // 单击空白区域取消选中并折叠边栏
  graph.on('blank:click', () => {
    selectedNodeId.value = null;
    sidebarVisible.value = false;
    // 注意：保留 editingNode，以便用户重新展开边栏时仍可看到上次编辑的节点
  });

  // 订阅 sessionStore 变化，更新节点绑定状态显示
  unsubscribeSessionStore = sessionStore.subscribe((state) => {
    // 当视图绑定变化时，更新所有 OUTPUT 节点的标签
    graph.getNodes().forEach((node) => {
      const data = node.getData() as GraphNode;
      if (data && data.type === 'OUTPUT') {
        const labelText = generateNodeLabel(data.type, data.name, data.params, node.id);
        node.attr('label/text', labelText);
      }
    });
  });

  // 加载数据
  await nextTick();
  await loadFromBackend();
  await loadPaletteDevices();
  
  // 初始加载完成后再连接 WebSocket，避免 initial 推送与 loadFromBackend 竞争导致 clearCells 双重重绘
  graphSyncWebSocket.connect();

  // 订阅命令结果，处理 sync_graph 冲突
  unsubscribeCmdResult = controlWebSocket.onCmdResult((result) => {
    if (result.command === 'sync_graph') {
      const rev = Number(result.revision || 0);
      const prev = Number(result.persistedRevision || 0);
      if (result.conflict && result.graph) {
        handleSyncConflict(result.graph as GraphPayload, rev, prev);
      } else if (!result.ok) {
        setSyncStatus('error', result.error || '同步失败');
        pendingSignature.value = '';
      }
    }
  });

  // 启动运行时状态轮询
  startRuntimeStatePolling();
});

onUnmounted(() => {
  window.removeEventListener('keydown', onSaveHotkey);
  window.removeEventListener('beforeunload', onBeforeUnload);

  // 移除拖拽事件监听器
  if (container.value) {
    container.value.removeEventListener('dragover', onDragOver);
    container.value.removeEventListener('drop', onDrop);
  }

  stopRuntimeStatePolling();
  stopEdgeAnimations();
  
  // 保存当前状态到会话存储
  saveStateToSessionStorage();
  
  graphRef.value?.dispose();
  // 取消订阅
  unsubscribeSessionStore?.();
  unsubscribeGraphSync?.();
  unsubscribeCmdResult?.();
  graphSyncWebSocket.disconnect();
  if (realtimeSyncTimer) {
    clearTimeout(realtimeSyncTimer);
    realtimeSyncTimer = null;
  }
  if (syncOkTimer) {
    clearTimeout(syncOkTimer);
    syncOkTimer = null;
  }
});
</script>

<style scoped>
.fullscreen-graph-editor {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: rgb(var(--v-theme-background));
  min-height: 0;
  overflow: hidden;
}

.port-legend-in {
  color: #E53935;
}
.port-legend-out {
  color: #43A047;
}

.graph-toolbar {
  flex-shrink: 0;
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.palette-empty {
  color: #90a4ae;
  font-size: 12px;
  padding: 8px 4px;
}

.graph-content {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.graph-wrapper {
  display: flex;
  flex: 1;
  min-height: 0; /* 确保flex容器可以收缩 */
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 8px;
  overflow: hidden;
  background: rgb(var(--v-theme-surface));
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  position: relative;
}

.palette {
  width: 220px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  background: rgb(var(--v-theme-surface));
  overflow: hidden;
  min-height: 0;
}

.palette-body {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  min-height: 0;
}

.palette-title {
  padding: 16px;
  font-weight: 600;
  font-size: 14px;
  color: rgb(var(--v-theme-on-surface));
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.palette-group {
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.group-title {
  padding: 12px 16px;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.6);
  background: rgba(var(--v-theme-on-surface), 0.03);
  font-weight: 500;
}

.palette-item {
  padding: 12px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: grab;
  transition: background 0.2s;
  border-bottom: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * 0.6));
}

.palette-item:hover {
  background: rgba(var(--v-theme-on-surface), 0.05);
}

.palette-item:active {
  cursor: grabbing;
}

.palette-item-disabled {
  opacity: 0.5;
  cursor: not-allowed !important;
  background: rgba(var(--v-theme-on-surface), 0.02) !important;
}

.palette-item-disabled:hover {
  background: rgba(var(--v-theme-on-surface), 0.02) !important;
}

.item-icon {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.item-name {
  font-size: 14px;
  color: rgb(var(--v-theme-on-surface));
}

.graph-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: rgb(var(--v-theme-background));
  position: relative;
  overflow: hidden;
}

.graph-hint {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  color: rgba(var(--v-theme-on-surface), 0.35);
  pointer-events: none;
}

.hint-text {
  font-size: 16px;
  margin-top: 8px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.hint-sub {
  font-size: 13px;
  margin-top: 4px;
}

/* 右侧边栏样式 */
.sidebar {
  width: 400px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-left: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  background: rgb(var(--v-theme-surface));
  transition: width 0.3s ease;
  overflow: hidden;
  min-height: 0;
}

.sidebar-collapsed {
  width: 40px;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  background: rgba(var(--v-theme-on-surface), 0.03);
  min-height: 56px;
}

.sidebar-title-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  min-width: 0;
}

.sidebar-title-text {
  min-width: 0;
}

.sidebar-title {
  font-weight: 600;
  font-size: 14px;
  color: rgb(var(--v-theme-on-surface));
  display: flex;
  align-items: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar-subtitle {
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.5);
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar-empty {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: rgba(var(--v-theme-on-surface), 0.4);
  text-align: center;
  padding: 24px;
}

.sidebar-empty-text {
  margin-top: 12px;
  font-size: 13px;
}

.sidebar-content {
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

.sidebar-node-edit {
  height: 100%;
}

/* NodeEditDialog 边栏模式样式 */
.node-edit-sidebar {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.node-edit-sidebar .sidebar-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.node-edit-sidebar .sidebar-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  min-height: 0;
}

.node-edit-content {
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* 确保表单内容可滚动 */
.node-edit-content .v-card-text {
  flex: 1;
  overflow-y: auto;
  padding: 16px !important;
}

/* 调整画布容器宽度 */
.graph-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0; /* 确保flex容器可以收缩 */
  background: rgb(var(--v-theme-background));
  position: relative;
  overflow: hidden; /* 隐藏溢出，避免残影 */
}

/* 确保X6画布充分利用空间 */
.x6-graph {
  flex: 1;
  min-height: 0;
  width: 100%;
  height: 100%;
}

.x6-graph-scroller {
  width: 100% !important;
  height: 100% !important;
  overflow: auto !important;
}

.x6-graph-background {
  width: 100% !important;
  height: 100% !important;
}

.x6-graph-svg {
  width: 100% !important;
  height: 100% !important;
}

/* 响应式调整 */
@media (max-width: 1200px) {
  .sidebar {
    width: 350px;
  }
  
  .sidebar-collapsed {
    width: 40px;
  }
}

@media (max-width: 960px) {
  .sidebar {
    width: 300px;
  }
  
  .sidebar-collapsed {
    width: 40px;
  }
  
  .palette {
    width: 180px;
  }
}
</style>
