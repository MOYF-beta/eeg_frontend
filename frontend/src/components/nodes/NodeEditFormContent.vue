<template>
  <div class="node-edit-form-content">
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
        :readonly="isReadOnly"
        :disabled="isReadOnly"
      />

      <!-- 设备选择器 -->
      <v-select
        v-if="form.params.sourceMode !== 'replay'"
        :model-value="selectedDeviceId"
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
        :readonly="isReadOnly"
        :disabled="isReadOnly"
        @update:model-value="$emit('update:selectedDeviceId', $event)"
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
          :readonly="isReadOnly"
          :disabled="isReadOnly"
        />
        <v-checkbox
          v-model="form.params.loop"
          label="循环播放"
          density="compact"
          hide-details
          class="mb-3"
          :readonly="isReadOnly"
          :disabled="isReadOnly"
        />
      </template>
      
      <v-text-field
        v-model.number="form.params.sampleRate"
        label="采样率 (Hz)"
        type="number"
        density="compact"
        variant="outlined"
        class="mb-3"
        :readonly="isReadOnly"
        :disabled="isReadOnly"
      />
      
      <v-text-field
        v-model.number="form.params.channels"
        label="通道数"
        type="number"
        density="compact"
        variant="outlined"
        class="mb-3"
        :readonly="isReadOnly"
        :disabled="isReadOnly"
      />
      
      <!-- 通道名称编辑 -->
      <div class="mb-3">
        <div class="d-flex align-center justify-space-between mb-1">
          <span class="text-body-2">通道名称</span>
          <div class="d-flex align-center gap-2">
            <!-- 10-20标准系统开关 -->
            <v-switch
              v-if="!isReadOnly && showTenTwentySwitch"
              v-model="tenTwentyMode"
              density="compact"
              hide-details
              label="10-20标准系统"
              color="teal"
              class="ten-twenty-switch"
            />
            <v-btn
              v-if="!isReadOnly"
              size="x-small"
              variant="text"
              @click="handleAddChannelName"
            >
              添加
            </v-btn>
          </div>
        </div>
        <div v-for="(name, index) in channelNames" :key="index" class="d-flex align-center mb-1">
          <v-text-field
            :model-value="channelNames[index]"
            :label="`通道 ${index + 1}`"
            density="compact"
            variant="outlined"
            hide-details
            class="mr-2"
            :readonly="isReadOnly"
            :disabled="isReadOnly"
            @update:model-value="updateChannelName(index, $event)"
          />
          <v-btn
            v-if="!isReadOnly"
            icon
            size="x-small"
            variant="text"
            color="error"
            @click="handleRemoveChannelName(index)"
          >
            <v-icon size="small">mdi-close</v-icon>
          </v-btn>
        </div>
      </div>

      <!-- 10-20命名对话框 -->
      <TenTwentyChannelDialog
        v-model="tenTwentyDialogOpen"
        :devices="deviceListForDialog"
        :restrict-to-device-id="tenTwentyRestrictDeviceId"
        @confirm="onTenTwentyConfirm"
      />
    </template>

    <!-- 滤波器专用表单 -->
    <template v-else-if="nodeType === 'FILTER'">
      <v-select
        v-model="form.params.filterType"
        :items="[{ title: '低通', value: 'lowpass' }, { title: '高通', value: 'highpass' }, { title: '带通', value: 'bandpass' }, { title: '带阻', value: 'bandstop' }]"
        item-title="title"
        item-value="value"
        label="滤波器类型"
        density="compact"
        variant="outlined"
        class="mb-3"
        :readonly="isReadOnly"
        :disabled="isReadOnly"
      />
      
      <v-text-field
        v-model.number="form.params.cutoffFreq"
        label="截止频率 (Hz)"
        type="number"
        density="compact"
        variant="outlined"
        class="mb-3"
        :readonly="isReadOnly"
        :disabled="isReadOnly"
      />
      
      <v-text-field
        v-model.number="form.params.order"
        label="阶数"
        type="number"
        density="compact"
        variant="outlined"
        class="mb-3"
        :readonly="isReadOnly"
        :disabled="isReadOnly"
      />
    </template>

    <!-- 降采样/升采样专用表单 -->
    <template v-else-if="nodeType === 'DOWNSAMPLE' || nodeType === 'UPSAMPLE'">
      <v-text-field
        v-model.number="form.params.factor"
        :label="nodeType === 'DOWNSAMPLE' ? '降采样因子' : '升采样因子'"
        type="number"
        density="compact"
        variant="outlined"
        class="mb-3"
        :readonly="isReadOnly"
        :disabled="isReadOnly"
      />
    </template>

    <!-- 求和器专用表单 -->
    <template v-else-if="nodeType === 'SUM' || nodeType === 'AVERAGE'">
      <div class="mb-3">
        <div class="d-flex align-center justify-space-between mb-1">
          <span class="text-body-2">输入配置</span>
          <v-btn
            v-if="!isReadOnly"
            size="x-small"
            variant="text"
            @click="handleAddSumInput"
          >
            添加输入
          </v-btn>
        </div>
        <div v-for="(input, index) in sumInputs" :key="index" class="d-flex align-center mb-1">
          <v-text-field
            :model-value="input.label"
            label="标签"
            density="compact"
            variant="outlined"
            hide-details
            class="mr-2"
            style="flex: 2"
            :readonly="isReadOnly"
            :disabled="isReadOnly"
            @update:model-value="updateSumInputLabel(index, $event)"
          />
          <v-text-field
            :model-value="input.weight"
            label="权重"
            type="number"
            density="compact"
            variant="outlined"
            hide-details
            class="mr-2"
            style="flex: 1"
            :readonly="isReadOnly"
            :disabled="isReadOnly"
            @update:model-value="updateSumInputWeight(index, $event)"
          />
          <v-btn
            v-if="!isReadOnly"
            icon
            size="x-small"
            variant="text"
            color="error"
            @click="handleRemoveSumInput(index)"
          >
            <v-icon size="small">mdi-close</v-icon>
          </v-btn>
        </div>
      </div>
    </template>

    <!-- 分离器专用表单 -->
    <template v-else-if="nodeType === 'SPLIT'">
      <div class="mb-3">
        <div class="d-flex align-center justify-space-between mb-1">
          <span class="text-body-2">输出配置</span>
          <v-btn
            v-if="!isReadOnly"
            size="x-small"
            variant="text"
            @click="handleAddSplitOutput"
          >
            添加输出
          </v-btn>
        </div>
        <div v-for="(output, index) in splitOutputs" :key="index" class="d-flex align-center mb-1">
          <v-text-field
            :model-value="output.label"
            label="标签"
            density="compact"
            variant="outlined"
            hide-details
            class="mr-2"
            style="flex: 2"
            :readonly="isReadOnly"
            :disabled="isReadOnly"
            @update:model-value="updateSplitOutputLabel(index, $event)"
          />
          <v-text-field
            :model-value="output.channelIndices"
            label="通道索引 (如: 0,1,2)"
            density="compact"
            variant="outlined"
            hide-details
            class="mr-2"
            style="flex: 2"
            :readonly="isReadOnly"
            :disabled="isReadOnly"
            @update:model-value="updateSplitOutputChannelIndices(index, $event)"
          />
          <v-btn
            v-if="!isReadOnly"
            icon
            size="x-small"
            variant="text"
            color="error"
            @click="handleRemoveSplitOutput(index)"
          >
            <v-icon size="small">mdi-close</v-icon>
          </v-btn>
        </div>
      </div>
    </template>

    <!-- 合并器专用表单 -->
    <template v-else-if="nodeType === 'MERGE'">
      <v-select
        v-model="form.params.strategy"
        :items="[{ title: '交错', value: 'interleave' }, { title: '拼接', value: 'concat' }]"
        item-title="title"
        item-value="value"
        label="合并策略"
        density="compact"
        variant="outlined"
        class="mb-3"
        :readonly="isReadOnly"
        :disabled="isReadOnly"
      />
      
      <div class="mb-3">
        <div class="d-flex align-center justify-space-between mb-1">
          <span class="text-body-2">输入配置</span>
          <v-btn
            v-if="!isReadOnly"
            size="x-small"
            variant="text"
            @click="handleAddMergeInput"
          >
            添加输入
          </v-btn>
        </div>
        <div v-for="(input, index) in mergeInputs" :key="index" class="d-flex align-center mb-1">
          <v-text-field
            :model-value="input.label"
            label="标签"
            density="compact"
            variant="outlined"
            hide-details
            class="mr-2"
            style="flex: 2"
            :readonly="isReadOnly"
            :disabled="isReadOnly"
            @update:model-value="updateMergeInputLabel(index, $event)"
          />
          <v-text-field
            :model-value="input.gain"
            label="增益"
            type="number"
            density="compact"
            variant="outlined"
            hide-details
            class="mr-2"
            style="flex: 1"
            :readonly="isReadOnly"
            :disabled="isReadOnly"
            @update:model-value="updateMergeInputGain(index, $event)"
          />
          <v-btn
            v-if="!isReadOnly"
            icon
            size="x-small"
            variant="text"
            color="error"
            @click="handleRemoveMergeInput(index)"
          >
            <v-icon size="small">mdi-close</v-icon>
          </v-btn>
        </div>
      </div>
    </template>

    <!-- 示波器专用表单 -->
    <template v-else-if="nodeType === 'OSC'">
      <v-select
        :model-value="boundOscilloscopeId"
        :items="availableOscilloscopes"
        item-title="name"
        item-value="id"
        label="绑定到示波器实例"
        density="compact"
        variant="outlined"
        clearable
        :hint="boundOscilloscopeId ? '已绑定' : '未绑定'"
        persistent-hint
        :readonly="isReadOnly"
        :disabled="isReadOnly"
        @update:model-value="$emit('update:boundOscilloscopeId', $event)"
      />

      <v-divider class="my-3" />
    </template>

    <!-- 保存节点专用表单 -->
    <template v-else-if="nodeType === 'SAVE'">
      <v-text-field
        v-model="form.params.filename"
        label="文件名"
        density="compact"
        variant="outlined"
        class="mb-3"
        :readonly="isReadOnly"
        :disabled="isReadOnly"
      />
      
      <v-select
        v-model="form.params.format"
        :items="[{ title: 'CSV', value: 'CSV' }, { title: 'MAT', value: 'MAT' }, { title: 'NPY', value: 'NPY' }]"
        item-title="title"
        item-value="value"
        label="文件格式"
        density="compact"
        variant="outlined"
        class="mb-3"
        :readonly="isReadOnly"
        :disabled="isReadOnly"
      />
    </template>

    <!-- Python函数节点专用表单 -->
    <template v-else-if="nodeType === 'CUSTOM_PYFUNC'">
      <v-select
        v-model="form.params.portMode"
        :items="[{ title: '固定端口', value: 'fixed' }, { title: '动态端口', value: 'dynamic' }]"
        item-title="title"
        item-value="value"
        label="端口模式"
        density="compact"
        variant="outlined"
        class="mb-3"
        :readonly="isReadOnly"
        :disabled="isReadOnly"
      />

      <template v-if="form.params.portMode === 'fixed'">
        <v-text-field
          v-model.number="form.params.inputCount"
          label="输入端口数"
          type="number"
          density="compact"
          variant="outlined"
          class="mb-3"
          :readonly="isReadOnly"
          :disabled="isReadOnly"
        />
        
        <v-text-field
          v-model.number="form.params.outputCount"
          label="输出端口数"
          type="number"
          density="compact"
          variant="outlined"
          class="mb-3"
          :readonly="isReadOnly"
          :disabled="isReadOnly"
        />
      </template>

      <v-text-field
        v-model="form.params.functionName"
        label="函数名"
        density="compact"
        variant="outlined"
        class="mb-3"
        :readonly="isReadOnly"
        :disabled="isReadOnly"
      />

      <v-select
        v-model="form.params.windowMode"
        :items="[{ title: '按时间', value: 'seconds' }, { title: '按点数', value: 'points' }]"
        item-title="title"
        item-value="value"
        label="窗口模式"
        density="compact"
        variant="outlined"
        class="mb-3"
        :readonly="isReadOnly"
        :disabled="isReadOnly"
      />

      <template v-if="form.params.windowMode === 'seconds'">
        <v-text-field
          v-model.number="form.params.windowSeconds"
          label="窗口时间 (秒)"
          type="number"
          density="compact"
          variant="outlined"
          class="mb-3"
          :readonly="isReadOnly"
          :disabled="isReadOnly"
        />
      </template>
      <template v-else>
        <v-text-field
          v-model.number="form.params.windowPoints"
          label="窗口点数"
          type="number"
          density="compact"
          variant="outlined"
          class="mb-3"
          :readonly="isReadOnly"
          :disabled="isReadOnly"
        />
      </template>

      <v-select
        v-model="form.params.hopMode"
        :items="[{ title: '按点数', value: 'points' }, { title: '按时间', value: 'ms' }]"
        item-title="title"
        item-value="value"
        label="跳跃模式"
        density="compact"
        variant="outlined"
        class="mb-3"
        :readonly="isReadOnly"
        :disabled="isReadOnly"
      />

      <template v-if="form.params.hopMode === 'points'">
        <v-text-field
          v-model.number="form.params.hopPoints"
          label="跳跃点数"
          type="number"
          density="compact"
          variant="outlined"
          class="mb-3"
          :readonly="isReadOnly"
          :disabled="isReadOnly"
        />
      </template>
      <template v-else>
        <v-text-field
          v-model.number="form.params.hopMs"
          label="跳跃时间 (毫秒)"
          type="number"
          density="compact"
          variant="outlined"
          class="mb-3"
          :readonly="isReadOnly"
          :disabled="isReadOnly"
        />
      </template>

      <v-text-field
        v-model.number="form.params.outputSampleRate"
        label="输出采样率 (Hz)"
        type="number"
        density="compact"
        variant="outlined"
        class="mb-3"
        :readonly="isReadOnly"
        :disabled="isReadOnly"
      />

      <div class="mb-3">
        <div class="d-flex align-center justify-space-between mb-1">
          <span class="text-body-2">输入名称 (逗号分隔)</span>
        </div>
        <v-textarea
          :model-value="inputNamesText"
          rows="2"
          density="compact"
          variant="outlined"
          :readonly="isReadOnly"
          :disabled="isReadOnly"
          @update:model-value="$emit('update:inputNamesText', $event)"
        />
      </div>

      <div class="mb-3">
        <div class="d-flex align-center justify-space-between mb-1">
          <span class="text-body-2">输出名称 (逗号分隔)</span>
        </div>
        <v-textarea
          :model-value="outputNamesText"
          rows="2"
          density="compact"
          variant="outlined"
          :readonly="isReadOnly"
          :disabled="isReadOnly"
          @update:model-value="$emit('update:outputNamesText', $event)"
        />
      </div>

      <div class="mb-3">
        <div class="d-flex align-center justify-space-between mb-1">
          <span class="text-body-2">Python代码</span>
          <v-btn
            v-if="!isReadOnly"
            size="x-small"
            variant="text"
            @click="importPythonFile"
          >
            导入文件
          </v-btn>
        </div>
        <v-textarea
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
          :model-value="pythonFooterCode"
          label="自动生成（不可编辑）：输出检查 + return"
          rows="8"
          density="compact"
          variant="outlined"
          readonly
          class="mt-2"
        />
      </div>
    </template>

    <!-- 卷积节点专用表单 -->
    <template v-else-if="nodeType === 'CUSTOM_CONV'">
      <div class="mb-3">
        <div class="d-flex align-center justify-space-between mb-1">
          <span class="text-body-2">卷积核 (逗号分隔)</span>
        </div>
        <v-textarea
          :model-value="kernelText"
          rows="2"
          density="compact"
          variant="outlined"
          :readonly="isReadOnly"
          :disabled="isReadOnly"
          @update:model-value="$emit('update:kernelText', $event)"
        />
      </div>

      <div class="mb-3">
        <div class="d-flex align-center justify-space-between mb-1">
          <span class="text-body-2">Python代码</span>
          <v-btn
            v-if="!isReadOnly"
            size="x-small"
            variant="text"
            @click="importPythonFile"
          >
            导入文件
          </v-btn>
        </div>
        <div ref="codeEditorHost" class="code-editor-host" />
      </div>
    </template>

    <!-- 其他节点通用参数 -->
    <template v-else>
      <v-textarea
        :model-value="paramsJson"
        label="参数 (JSON)"
        rows="4"
        density="compact"
        variant="outlined"
        :error="!!jsonError"
        :error-messages="jsonError"
        :readonly="isReadOnly"
        :disabled="isReadOnly"
        @update:model-value="$emit('update:paramsJson', $event)"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted } from 'vue';
import { sessionStore } from '../../services/sessionStore';
import { deviceApi } from '../../services/deviceApi';
import TenTwentyChannelDialog from '../TenTwentyChannelDialog.vue';

// 从父组件传递的props
const props = defineProps<{
  nodeType: string;
  form: any;
  isReadOnly: boolean;
  selectedDeviceId: string | null;
  boundOscilloscopeId: string | null;
  channelNames: string[];
  sumInputs: any[];
  splitOutputs: any[];
  mergeInputs: any[];
  inputNamesText: string;
  outputNamesText: string;
  kernelText: string;
  paramsJson: string;
  jsonError: string | null;
}>();

// 从父组件传递的方法
const emit = defineEmits<{
  (e: 'update:selectedDeviceId', value: string | null): void;
  (e: 'update:boundOscilloscopeId', value: string | null): void;
  (e: 'update:channelNames', value: string[]): void;
  (e: 'update:sumInputs', value: any[]): void;
  (e: 'update:splitOutputs', value: any[]): void;
  (e: 'update:mergeInputs', value: any[]): void;
  (e: 'update:inputNamesText', value: string): void;
  (e: 'update:outputNamesText', value: string): void;
  (e: 'update:kernelText', value: string): void;
  (e: 'update:paramsJson', value: string): void;
  (e: 'addChannelName'): void;
  (e: 'removeChannelName', index: number): void;
  (e: 'addSumInput'): void;
  (e: 'removeSumInput', index: number): void;
  (e: 'addSplitOutput'): void;
  (e: 'removeSplitOutput', index: number): void;
  (e: 'addMergeInput'): void;
  (e: 'removeMergeInput', index: number): void;
  (e: 'importPythonFile'): void;
}>();

// 计算属性
const availableDevices = computed(() => {
  return sessionStore.getDevices().map(device => ({
    ...device,
    displayName: device.name || device.id
  }));
});

const availableOscilloscopes = computed(() => {
  return sessionStore.getOscilloscopes().map(osc => ({
    ...osc,
    displayName: osc.name || osc.id
  }));
});

// 10-20标准系统
const tenTwentyMode = ref(false);
const tenTwentyDialogOpen = ref(false);

/** 10-20 对话框可用的设备列表 - 含重试机制 */
const availableDevicesForTenTwenty = computed(() => {
  const devices = sessionStore.getDevices();
  return devices.map(d => ({
    id: d.id,
    name: d.name,
    channelCount: d.channelCount,
    channels: (d.config?.channels || []).length > 0
      ? (d.config?.channels || []).map((ch: any) => ({
          index: ch.index ?? ch.channel ?? 0,
          name: ch.name || `CH${(ch.index ?? 0) + 1}`,
          alias: ch.alias || '',
        }))
      : Array.from({ length: d.channelCount || 8 }, (_, i) => ({
          index: i,
          name: `CH${i + 1}`,
          alias: '',
        })),
  }));
});

/** 手动拉取的设备列表（当 sessionStore 为空时备用） */
const fallbackDevices = ref<Array<{ id: string; name: string; channelCount: number; channels: Array<{ index: number; name: string }> }>>([]);

async function fetchDevicesFallback() {
  if (sessionStore.getDevices().length > 0) return; // 已有数据，跳过
  try {
    const devices = await deviceApi.getDevices();
    fallbackDevices.value = devices.map((d: any) => ({
      id: d.id,
      name: d.name,
      channelCount: d.channel_count || 8,
      channels: (d.config?.channels || []).length > 0
        ? d.config.channels.map((ch: any) => ({
            index: ch.index ?? ch.channel ?? 0,
            name: ch.name || `CH${(ch.index ?? 0) + 1}`,
            alias: ch.alias || '',
          }))
        : Array.from({ length: d.channel_count || 8 }, (_, i) => ({
            index: i,
            name: `CH${i + 1}`,
            alias: '',
          })),
    }));
  } catch (err) {
    console.warn('[NodeEditFormContent] Failed to fetch fallback devices:', err);
  }
}

/** 最终传递给对话框的设备列表（合并 sessionStore + fallback） */
const deviceListForDialog = computed(() => {
  const fromStore = availableDevicesForTenTwenty.value;
  if (fromStore.length > 0) return fromStore;
  return fallbackDevices.value;
});

/** 节点编辑模式: 限制只能选择当前设备 */
const tenTwentyRestrictDeviceId = computed(() => {
  return props.selectedDeviceId || null;
});

// 只在SOURCE节点的 channel names 区域显示 10-20 入口
const showTenTwentySwitch = computed(() => {
  return props.nodeType === 'SOURCE';
});

const onTenTwentyConfirm = (result: { subjectId: string; mappings: Array<{ electrode: string; deviceId: string; channelIndex: number }> }) => {
  if (result.mappings.length > 0) {
    // 找到本设备的最大通道数, 扩展 channelNames 列表
    const maxChIdx = Math.max(...result.mappings.map(m => m.channelIndex));
    const newNames = [...props.channelNames];
    while (newNames.length <= maxChIdx) {
      newNames.push(`CH${newNames.length + 1}`);
    }
    // 为每个映射的通道重命名: {subjectId}@{electrode}
    for (const m of result.mappings) {
      newNames[m.channelIndex] = `${result.subjectId}@${m.electrode}`;
    }
    emit('update:channelNames', newNames);
  }
  tenTwentyMode.value = false;
};

// 监听开关切换以打开对话框
watch(tenTwentyMode, (val) => {
  if (val) {
    fetchDevicesFallback(); // 确保设备列表已加载
    tenTwentyDialogOpen.value = true;
  }
});

// 对话框关闭时同步关闭开关
watch(tenTwentyDialogOpen, (val) => {
  if (!val) {
    tenTwentyMode.value = false;
  }
});

// 方法
const updateChannelName = (index: number, value: string) => {
  const newChannelNames = [...props.channelNames];
  newChannelNames[index] = value;
  emit('update:channelNames', newChannelNames);
};

const updateSumInputLabel = (index: number, value: string) => {
  const newSumInputs = [...props.sumInputs];
  newSumInputs[index] = { ...newSumInputs[index], label: value };
  emit('update:sumInputs', newSumInputs);
};

const updateSumInputWeight = (index: number, value: number) => {
  const newSumInputs = [...props.sumInputs];
  newSumInputs[index] = { ...newSumInputs[index], weight: value };
  emit('update:sumInputs', newSumInputs);
};

const updateSplitOutputLabel = (index: number, value: string) => {
  const newSplitOutputs = [...props.splitOutputs];
  newSplitOutputs[index] = { ...newSplitOutputs[index], label: value };
  emit('update:splitOutputs', newSplitOutputs);
};

const updateSplitOutputChannelIndices = (index: number, value: string) => {
  const newSplitOutputs = [...props.splitOutputs];
  newSplitOutputs[index] = { ...newSplitOutputs[index], channelIndices: value };
  emit('update:splitOutputs', newSplitOutputs);
};

const updateMergeInputLabel = (index: number, value: string) => {
  const newMergeInputs = [...props.mergeInputs];
  newMergeInputs[index] = { ...newMergeInputs[index], label: value };
  emit('update:mergeInputs', newMergeInputs);
};

const updateMergeInputGain = (index: number, value: number) => {
  const newMergeInputs = [...props.mergeInputs];
  newMergeInputs[index] = { ...newMergeInputs[index], gain: value };
  emit('update:mergeInputs', newMergeInputs);
};

const isDeviceBoundToOtherNode = (deviceId: string) => {
  const nodes = props.form.allNodes || [];
  return nodes.some((node: any) => {
    if (node.id === props.form.nodeData?.id) return false;
    return node.deviceId === deviceId;
  });
};

// 事件处理
const handleSelectedDeviceIdChange = (value: string | null) => {
  emit('update:selectedDeviceId', value);
};

const handleBoundOscilloscopeIdChange = (value: string | null) => {
  emit('update:boundOscilloscopeId', value);
};

const handleChannelNamesChange = (value: string[]) => {
  emit('update:channelNames', value);
};

const handleSumInputsChange = (value: any[]) => {
  emit('update:sumInputs', value);
};

const handleSplitOutputsChange = (value: any[]) => {
  emit('update:splitOutputs', value);
};

const handleMergeInputsChange = (value: any[]) => {
  emit('update:mergeInputs', value);
};

const handleInputNamesTextChange = (value: string) => {
  emit('update:inputNamesText', value);
};

const handleOutputNamesTextChange = (value: string) => {
  emit('update:outputNamesText', value);
};

const handleKernelTextChange = (value: string) => {
  emit('update:kernelText', value);
};

const handleParamsJsonChange = (value: string) => {
  emit('update:paramsJson', value);
};

const handleAddChannelName = () => {
  emit('addChannelName');
};

const handleRemoveChannelName = (index: number) => {
  emit('removeChannelName', index);
};

const handleAddSumInput = () => {
  emit('addSumInput');
};

const handleRemoveSumInput = (index: number) => {
  emit('removeSumInput', index);
};

const handleAddSplitOutput = () => {
  emit('addSplitOutput');
};

const handleRemoveSplitOutput = (index: number) => {
  emit('removeSplitOutput', index);
};

const handleAddMergeInput = () => {
  emit('addMergeInput');
};

const handleRemoveMergeInput = (index: number) => {
  emit('removeMergeInput', index);
};

const handleImportPythonFile = () => {
  emit('importPythonFile');
};
</script>

<style scoped>
.gap-2 {
  gap: 8px;
}

.ten-twenty-switch {
  font-size: 11px;
  height: 28px;
}

.node-edit-form-content {
  max-height: 70vh;
  overflow-y: auto;
  padding-right: 4px;
}

.node-edit-form-content::-webkit-scrollbar {
  width: 6px;
}

.node-edit-form-content::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.node-edit-form-content::-webkit-scrollbar-thumb {
  background: #888;
  border-radius: 3px;
}

.node-edit-form-content::-webkit-scrollbar-thumb:hover {
  background: #555;
}
</style>