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
          <v-select
            v-model="form.params.sourceMode"
            :items="[{ title: '实时', value: 'live' }, { title: '回放', value: 'replay' }]"
            item-title="title"
            item-value="value"
            label="输入模式"
            density="compact"
            variant="outlined"
            class="mb-3"
          />

          <!-- 设备选择器 -->
          <v-select
            v-if="form.params.sourceMode !== 'replay'"
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

          <template v-if="form.params.sourceMode === 'replay'">
            <v-text-field
              v-model="form.params.filePath"
              label="回放文件名/路径"
              density="compact"
              variant="outlined"
              class="mb-3"
            />
            <v-checkbox
              v-model="form.params.loop"
              label="循环播放"
              density="compact"
              hide-details
              class="mb-3"
            />
          </template>
          
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
            <v-card-title class="text-subtitle-2">通道来源（自动）</v-card-title>
            <v-card-text>
              <div class="d-flex align-center mb-2">
                <v-icon size="small" class="mr-2" color="info">mdi-source-branch</v-icon>
                <span class="text-caption">通道由输入连接自动决定，共 {{ availableChannels.length }} 路</span>
              </div>
              <div class="d-flex flex-wrap ga-1">
                <v-chip
                  v-for="(ch, idx) in availableChannels"
                  :key="idx"
                  size="small"
                  variant="tonal"
                  color="primary"
                >
                  {{ ch }}
                </v-chip>
              </div>
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

              <v-divider class="my-3" />

              <v-checkbox
                v-model="form.params.saveEnabled"
                label="同时保存到文件"
                density="compact"
                hide-details
                class="mb-2"
              />
              <v-text-field
                v-if="form.params.saveEnabled"
                v-model="form.params.filename"
                label="输出文件名"
                density="compact"
                variant="outlined"
                class="mb-2"
                placeholder="eeg_output.csv"
              />
              <v-select
                v-if="form.params.saveEnabled"
                v-model="form.params.format"
                :items="['CSV', 'EDF', 'NPY']"
                label="保存格式"
                density="compact"
                variant="outlined"
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

        <!-- 求和器专用表单 -->
        <template v-else-if="nodeType === 'SUM'">
          <v-card variant="outlined" class="mb-3">
            <v-card-title class="text-subtitle-2 d-flex align-center">
              输入配置
              <v-spacer />
              <v-btn size="small" variant="text" @click="addSumInput">新增输入</v-btn>
            </v-card-title>
            <v-card-text>
              <div
                v-for="(input, idx) in sumInputs"
                :key="`sum-${idx}`"
                class="d-flex align-center ga-2 mb-2"
              >
                <v-text-field
                  v-model="input.label"
                  :label="`输入 ${idx + 1} 标签`"
                  density="compact"
                  variant="outlined"
                  hide-details
                />
                <v-text-field
                  v-model.number="input.weight"
                  label="权重"
                  type="number"
                  density="compact"
                  variant="outlined"
                  hide-details
                  style="max-width: 120px"
                />
                <v-btn
                  icon="mdi-delete"
                  size="small"
                  variant="text"
                  :disabled="sumInputs.length <= 1"
                  @click="removeSumInput(idx)"
                />
              </div>
            </v-card-text>
          </v-card>
        </template>

        <!-- 合并器专用表单 -->
        <template v-else-if="nodeType === 'MERGE'">
          <v-card variant="outlined" class="mb-3">
            <v-card-title class="text-subtitle-2 d-flex align-center">
              输入配置
              <v-spacer />
              <v-btn size="small" variant="text" @click="addMergeInput">新增输入</v-btn>
            </v-card-title>
            <v-card-text>
              <div
                v-for="(input, idx) in mergeInputs"
                :key="`merge-${idx}`"
                class="d-flex align-center ga-2 mb-2"
              >
                <v-text-field
                  v-model="input.label"
                  :label="`输入 ${idx + 1} 标签`"
                  density="compact"
                  variant="outlined"
                  hide-details
                />
                <v-text-field
                  v-model.number="input.gain"
                  label="增益"
                  type="number"
                  density="compact"
                  variant="outlined"
                  hide-details
                  style="max-width: 120px"
                />
                <v-btn
                  icon="mdi-delete"
                  size="small"
                  variant="text"
                  :disabled="mergeInputs.length <= 1"
                  @click="removeMergeInput(idx)"
                />
              </div>
            </v-card-text>
          </v-card>
          <v-select
            v-model="form.params.strategy"
            :items="['interleave', 'concatenate']"
            label="合并策略"
            density="compact"
            variant="outlined"
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
          <v-card variant="outlined" class="mb-3">
            <v-card-title class="text-subtitle-2 d-flex align-center">
              输出配置
              <v-spacer />
              <v-btn size="small" variant="text" @click="addSplitOutput">新增输出</v-btn>
            </v-card-title>
            <v-card-text>
              <div
                v-for="(output, idx) in splitOutputs"
                :key="`split-${idx}`"
                class="d-flex align-center ga-2 mb-2"
              >
                <v-text-field
                  v-model="output.label"
                  :label="`输出 ${idx + 1} 标签`"
                  density="compact"
                  variant="outlined"
                  hide-details
                />
                <v-text-field
                  v-model="output.channelIndices"
                  label="通道索引"
                  density="compact"
                  variant="outlined"
                  hide-details
                  placeholder="0,1,2"
                />
                <v-btn
                  icon="mdi-delete"
                  size="small"
                  variant="text"
                  :disabled="splitOutputs.length <= 1"
                  @click="removeSplitOutput(idx)"
                />
              </div>
            </v-card-text>
          </v-card>
        </template>

        <!-- 自定义 Python 节点 -->
        <template v-else-if="nodeType === 'CUSTOM_PYFUNC' || nodeType === 'CUSTOM_CONV'">
          <v-card variant="outlined" class="mb-3" v-if="nodeType === 'CUSTOM_PYFUNC'">
            <v-card-title class="text-subtitle-2">输入输出配置</v-card-title>
            <v-card-text>
              <v-select
                v-model="form.params.portMode"
                :items="['fixed', 'adaptive']"
                label="端口模式"
                density="compact"
                variant="outlined"
                class="mb-3"
              />
              <v-row>
                <v-col cols="6">
                  <v-text-field
                    v-model.number="form.params.inputCount"
                    label="输入数量"
                    type="number"
                    density="compact"
                    variant="outlined"
                    :disabled="form.params.portMode === 'adaptive'"
                  />
                </v-col>
                <v-col cols="6">
                  <v-text-field
                    v-model.number="form.params.outputCount"
                    label="输出数量"
                    type="number"
                    density="compact"
                    variant="outlined"
                    :disabled="form.params.portMode === 'adaptive'"
                  />
                </v-col>
              </v-row>

              <v-row>
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model="form.params.functionName"
                    label="函数名（自动签名）"
                    density="compact"
                    variant="outlined"
                    hint="仅支持字母数字下划线"
                    persistent-hint
                  />
                </v-col>
                <v-col cols="12" md="6">
                  <v-select
                    v-model="form.params.windowMode"
                    :items="[{title: '秒', value: 'seconds'}, {title: '数据点', value: 'points'}]"
                    item-title="title"
                    item-value="value"
                    label="滑动窗口单位"
                    density="compact"
                    variant="outlined"
                  />
                </v-col>
                <v-col cols="12" md="6">
                  <v-select
                    v-model="form.params.hopMode"
                    :items="[
                      { title: '滑动点数', value: 'points' },
                      { title: '滑动毫秒', value: 'milliseconds' },
                      { title: '目标输出频率', value: 'targetRate' }
                    ]"
                    item-title="title"
                    item-value="value"
                    label="滑动间隔模式"
                    density="compact"
                    variant="outlined"
                  />
                </v-col>
                <v-col cols="12" md="6" v-if="form.params.windowMode !== 'points'">
                  <v-text-field
                    v-model.number="form.params.windowSeconds"
                    label="窗口秒数"
                    type="number"
                    min="0.01"
                    step="0.1"
                    density="compact"
                    variant="outlined"
                  />
                </v-col>
                <v-col cols="12" md="6" v-else>
                  <v-text-field
                    v-model.number="form.params.windowPoints"
                    label="窗口数据点"
                    type="number"
                    min="1"
                    step="1"
                    density="compact"
                    variant="outlined"
                  />
                </v-col>
                <v-col cols="12" md="6" v-if="form.params.hopMode === 'points'">
                  <v-text-field
                    v-model.number="form.params.hopPoints"
                    label="滑动间隔点数"
                    type="number"
                    min="1"
                    step="1"
                    density="compact"
                    variant="outlined"
                  />
                </v-col>
                <v-col cols="12" md="6" v-else-if="form.params.hopMode === 'milliseconds'">
                  <v-text-field
                    v-model.number="form.params.hopMs"
                    label="滑动间隔毫秒"
                    type="number"
                    min="1"
                    step="1"
                    density="compact"
                    variant="outlined"
                  />
                </v-col>
                <v-col cols="12" md="6" v-else>
                  <v-text-field
                    v-model.number="form.params.outputSampleRate"
                    label="目标输出频率 (Hz)"
                    type="number"
                    min="1"
                    step="1"
                    density="compact"
                    variant="outlined"
                  />
                </v-col>
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model="inputNamesText"
                    label="输入变量名（逗号分隔）"
                    density="compact"
                    variant="outlined"
                    hint="顺序对应前端输入连接桩"
                    persistent-hint
                  />
                </v-col>
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model="outputNamesText"
                    label="输出变量名（逗号分隔）"
                    density="compact"
                    variant="outlined"
                    hint="顺序对应前端输出连接桩"
                    persistent-hint
                  />
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>

          <v-card variant="outlined" class="mb-3" v-if="nodeType === 'CUSTOM_CONV'">
            <v-card-title class="text-subtitle-2">卷积配置</v-card-title>
            <v-card-text>
              <v-text-field
                v-model="kernelText"
                label="卷积核 (逗号分隔)"
                density="compact"
                variant="outlined"
                hint="示例: 0.25,0.5,0.25"
                persistent-hint
              />
            </v-card-text>
          </v-card>

          <v-card variant="outlined">
            <v-card-title class="text-subtitle-2 d-flex align-center">
              Python 代码
              <v-spacer />
              <v-btn size="small" variant="text" @click="generatePrototype" v-if="nodeType === 'CUSTOM_PYFUNC'">后端生成原型</v-btn>
              <v-btn size="small" variant="text" @click="resetPythonCode">恢复默认</v-btn>
              <v-btn size="small" variant="text" @click="triggerPythonImport">导入 .py</v-btn>
              <v-btn size="small" variant="text" @click="exportPythonCode">导出 .py</v-btn>
            </v-card-title>
            <v-card-text>
              <v-textarea
                v-if="nodeType === 'CUSTOM_PYFUNC'"
                :model-value="pythonHeaderCode"
                label="自动生成（不可编辑）：声明 + 参数读取"
                rows="8"
                density="compact"
                variant="outlined"
                readonly
                class="mb-2"
              />

              <div ref="codeEditorHost" class="code-editor-host" />

              <v-textarea
                v-if="nodeType === 'CUSTOM_PYFUNC'"
                :model-value="pythonFooterCode"
                label="自动生成（不可编辑）：输出检查 + return"
                rows="8"
                density="compact"
                variant="outlined"
                readonly
                class="mt-2"
              />
            </v-card-text>
          </v-card>
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

  <input
    ref="pythonFileInput"
    type="file"
    accept=".py,text/x-python"
    style="display: none"
    @change="importPythonFile"
  />
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue';
import { basicSetup, EditorView } from 'codemirror';
import { javascript } from '@codemirror/lang-javascript';
import { sessionStore } from '../../services/sessionStore';
import { fetchGraphPythonLibrary, generateGraphPythonPrototype } from '../../services/graph';

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
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
  (e: 'save', data: { name: string; params: Record<string, any>; deviceId?: string | null }): void;
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
