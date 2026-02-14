<template>
  <v-dialog v-model="show" max-width="600" persistent>
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon :color="iconColor" class="mr-2">{{ icon }}</v-icon>
        编辑节点 - {{ nodeTypeName }}
        <v-spacer />
        <v-btn icon variant="text" size="small" @click="close">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      
      <v-divider />
      
      <v-card-text class="pt-4">
        <!-- 通用字段：名称 -->
        <v-text-field
          v-model="form.name"
          label="节点名称"
          density="compact"
          variant="outlined"
          class="mb-4"
        />
        
        <!-- 数据源专用表单 -->
        <template v-if="nodeType === 'SOURCE'">
          <!-- 设备选择器 -->
          <v-select
            v-model="selectedDeviceId"
            :items="availableDevices"
            item-title="displayName"
            item-value="id"
            label="选择设备"
            density="compact"
            variant="outlined"
            class="mb-3"
            clearable
            :hint="selectedDeviceId ? `已绑定设备: ${selectedDeviceId}` : '未绑定设备'"
            persistent-hint
          >
            <template #item="{ props, item }">
              <v-list-item v-bind="props">
                <template #append>
                  <v-chip
                    v-if="isDeviceBoundToOtherNode(item.raw.id)"
                    size="x-small"
                    color="warning"
                  >
                    已绑定到其他节点
                  </v-chip>
                  <v-chip
                    v-else-if="item.raw.id === selectedDeviceId"
                    size="x-small"
                    color="success"
                  >
                    当前选择
                  </v-chip>
                </template>
              </v-list-item>
            </template>
          </v-select>

          <v-divider class="my-3" />
          
          <v-text-field
            v-model.number="form.params.sampleRate"
            label="采样率 (Hz)"
            type="number"
            density="compact"
            variant="outlined"
            class="mb-3"
          />
          <v-text-field
            v-model.number="form.params.channels"
            label="通道数"
            type="number"
            density="compact"
            variant="outlined"
            class="mb-3"
          />
          
          <!-- 通道命名 -->
          <v-expansion-panels>
            <v-expansion-panel>
              <v-expansion-panel-title>通道命名</v-expansion-panel-title>
              <v-expansion-panel-text>
                <div v-for="(ch, idx) in channelNames" :key="idx" class="d-flex align-center mb-2">
                  <span class="mr-2 text-caption">CH{{ idx + 1 }}:</span>
                  <v-text-field
                    v-model="channelNames[idx]"
                    density="compact"
                    variant="outlined"
                    hide-details
                    style="width: 120px"
                  />
                </div>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </template>
        
        <!-- 示波器专用表单 -->
        <template v-else-if="nodeType === 'OSC'">
          <v-text-field
            v-model.number="form.params.timeWindow"
            label="时间窗口 (秒)"
            type="number"
            density="compact"
            variant="outlined"
            class="mb-3"
          />
          <v-select
            v-model="form.params.mode"
            :items="[{title: '扫描', value: 'scan'}, {title: '滚动', value: 'scroll'}]"
            item-title="title"
            item-value="value"
            label="显示模式"
            density="compact"
            variant="outlined"
            class="mb-3"
          />
          
          <!-- 通道选择 -->
          <v-card variant="outlined" class="mb-3">
            <v-card-title class="text-subtitle-2">通道选择</v-card-title>
            <v-card-text>
              <div class="d-flex align-center mb-2">
                <v-btn size="small" variant="text" @click="selectAllChannels">全选</v-btn>
                <v-btn size="small" variant="text" @click="clearAllChannels">清空</v-btn>
                <v-spacer />
                <span class="text-caption">已选择 {{ selectedChannels.length }} 个通道</span>
              </div>
              <v-checkbox
                v-for="(ch, idx) in availableChannels"
                :key="idx"
                v-model="selectedChannels"
                :value="idx"
                :label="ch"
                density="compact"
                hide-details
              />
              <v-alert v-if="availableChannels.length === 0" type="info" density="compact" class="mt-2">
                未连接数据源，请先连接上游节点
              </v-alert>
            </v-card-text>
          </v-card>
          
          <!-- 绑定的示波器实例 -->
          <v-card variant="outlined">
            <v-card-title class="text-subtitle-2">显示绑定</v-card-title>
            <v-card-text>
              <v-select
                v-model="boundOscilloscopeId"
                :items="availableOscilloscopes"
                item-title="name"
                item-value="id"
                label="绑定到示波器实例"
                density="compact"
                variant="outlined"
                clearable
                :hint="boundOscilloscopeId ? '已绑定' : '未绑定'"
                persistent-hint
              />
            </v-card-text>
          </v-card>
        </template>
        
        <!-- 频谱专用表单 -->
        <template v-else-if="nodeType === 'SPECTRUM'">
          <v-text-field
            v-model.number="form.params.windowSize"
            label="窗口大小 (秒)"
            type="number"
            density="compact"
            variant="outlined"
            class="mb-3"
          />
          <v-text-field
            v-model.number="form.params.fftSize"
            label="FFT点数"
            type="number"
            density="compact"
            variant="outlined"
            class="mb-3"
          />
          <v-select
            v-model="form.params.displayMode"
            :items="[{title: '通道平均', value: 'average'}, {title: '分通道', value: 'channels'}]"
            item-title="title"
            item-value="value"
            label="显示模式"
            density="compact"
            variant="outlined"
            class="mb-3"
          />
          
          <!-- 通道选择（分通道模式） -->
          <template v-if="form.params.displayMode === 'channels'">
            <v-card variant="outlined" class="mb-3">
              <v-card-title class="text-subtitle-2">通道选择</v-card-title>
              <v-card-text>
                <div class="d-flex align-center mb-2">
                  <v-btn size="small" variant="text" @click="selectAllChannels">全选</v-btn>
                  <v-btn size="small" variant="text" @click="clearAllChannels">清空</v-btn>
                </div>
                <v-checkbox
                  v-for="(ch, idx) in availableChannels"
                  :key="idx"
                  v-model="selectedChannels"
                  :value="idx"
                  :label="ch"
                  density="compact"
                  hide-details
                />
              </v-card-text>
            </v-card>
          </template>
        </template>
        
        <!-- 滤波器专用表单 -->
        <template v-else-if="nodeType === 'FILTER'">
          <v-select
            v-model="form.params.type"
            :items="['低通', '高通', '带通', '陷波']"
            label="滤波器类型"
            density="compact"
            variant="outlined"
            class="mb-3"
          />
          <v-text-field
            v-model.number="form.params.cutoff"
            label="截止频率 (Hz)"
            type="number"
            density="compact"
            variant="outlined"
            class="mb-3"
          />
          <v-slider
            v-model="form.params.order"
            :min="1"
            :max="8"
            :step="1"
            label="阶数"
            thumb-label
            class="mb-3"
          />
        </template>
        
        <!-- 回放专用表单 -->
        <template v-else-if="nodeType === 'REPLAY'">
          <v-file-input
            v-model="form.params.file"
            label="选择数据文件"
            accept=".csv,.edf,.bdf"
            density="compact"
            variant="outlined"
            class="mb-3"
          />
          <v-checkbox
            v-model="form.params.loop"
            label="循环播放"
            density="compact"
          />
        </template>
        
        <!-- 保存专用表单 -->
        <template v-else-if="nodeType === 'SAVE'">
          <v-text-field
            v-model="form.params.filename"
            label="文件名"
            density="compact"
            variant="outlined"
            class="mb-3"
            placeholder="data_YYYYMMDD.csv"
          />
          <v-select
            v-model="form.params.format"
            :items="['CSV', 'EDF', 'NPY']"
            label="保存格式"
            density="compact"
            variant="outlined"
            class="mb-3"
          />
        </template>
        
        <!-- 分离器专用表单 -->
        <template v-else-if="nodeType === 'SPLIT'">
          <v-text-field
            v-model="form.params.groups"
            label="分组规则"
            density="compact"
            variant="outlined"
            class="mb-3"
            placeholder="1-4,5-8"
          />
        </template>
        
        <!-- 其他节点通用参数 -->
        <template v-else>
          <v-textarea
            v-model="paramsJson"
            label="参数 (JSON)"
            rows="4"
            density="compact"
            variant="outlined"
            :error="!!jsonError"
            :error-messages="jsonError"
          />
        </template>
      </v-card-text>
      
      <v-divider />
      
      <v-card-actions>
        <v-btn variant="text" @click="close">取消</v-btn>
        <v-spacer />
        <v-btn color="primary" @click="save">保存</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { sessionStore } from '../../services/sessionStore';

interface GraphNode {
  id: string;
  type: string;
  name: string;
  params: Record<string, any>;
  x?: number;
  y?: number;
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
}

const props = defineProps<{
  modelValue: boolean;
  nodeData: GraphNode | null;
  allNodes?: GraphNode[];
  allEdges?: GraphEdge[];
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
  (e: 'save', data: { name: string; params: Record<string, any> }): void;
  (e: 'bindOscilloscope', data: { nodeId: string; oscId: string | null }): void;
}>();

const show = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
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

// 从上游节点获取通道信息
function updateChannelInfo() {
  if (!props.nodeData) return;
  
  const upstream = getUpstreamSource(props.nodeData.id);
  if (upstream) {
    const channelCount = upstream.params?.channels || 8;
    const upstreamChannelNames = upstream.params?.channelNames || [];
    
    availableChannels.value = Array.from({ length: channelCount }, (_, i) => {
      return upstreamChannelNames[i] || `CH${i + 1}`;
    });
  } else {
    availableChannels.value = ['CH1', 'CH2', 'CH3', 'CH4', 'CH5', 'CH6', 'CH7', 'CH8'];
  }
}

watch(() => props.nodeData, (data) => {
  if (data) {
    form.value.name = data.name || '';
    form.value.params = { ...data.params };
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
    
    // 检查是否已绑定示波器
    const osc = sessionStore.getOutputNodeOscilloscope(data.id);
    boundOscilloscopeId.value = osc?.id || null;
  }
}, { immediate: true });

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

const save = () => {
  if (jsonError.value) return;
  
  // 保存通道信息
  if (nodeType.value === 'SOURCE') {
    form.value.params.channelNames = channelNames.value;
    // 保存设备ID到params
    form.value.params.deviceId = selectedDeviceId.value;
  }
  
  // 保存示波器通道选择
  if (nodeType.value === 'OSC' || nodeType.value === 'SPECTRUM') {
    form.value.params.selectedChannels = selectedChannels.value;
    form.value.params.availableChannels = availableChannels.value;
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
</script>
