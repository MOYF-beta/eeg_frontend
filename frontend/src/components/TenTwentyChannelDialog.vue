<template>
  <v-dialog v-model="dialogModel" max-width="680px" persistent scrollable>
    <v-card>
      <v-card-title class="d-flex align-center justify-space-between py-3">
        <div class="d-flex align-center">
          <v-icon class="mr-2" color="primary">mdi-head-dots-horizontal-outline</v-icon>
          <span>10-20 标准导联系统 · 通道映射</span>
        </div>
        <v-btn icon="mdi-close" variant="text" size="small" @click="close" />
      </v-card-title>

      <v-divider />

      <v-card-text class="pa-4">
        <!-- 被试编号 + 快捷操作 -->
        <div class="d-flex ga-2 align-start mb-3 flex-wrap">
          <v-text-field
            v-model="subjectId"
            label="被试编号"
            hint="通道名格式: {被试编号}@{电极}，如 0@Cz"
            persistent-hint
            density="compact"
            variant="outlined"
            style="max-width: 220px; min-width: 160px"
          />
          <div class="d-flex flex-column ga-1 flex-grow-1" style="min-width: 240px">
            <div class="d-flex ga-2 flex-wrap">
              <v-btn
                size="small"
                variant="tonal"
                color="primary"
                prepend-icon="mdi-lightning-bolt"
                :disabled="effectiveDevices.length === 0"
                @click="autoMapSequential"
              >
                顺序自动映射
              </v-btn>
              <v-btn
                size="small"
                variant="text"
                color="error"
                prepend-icon="mdi-delete-sweep"
                :disabled="mappingList.length === 0"
                @click="clearAllMappings"
              >
                清空
              </v-btn>
            </div>
            <div class="text-caption text-medium-emphasis">
              已映射 <b class="text-primary">{{ mappingList.length }}</b> / {{ positions.length }} 个导联
              <span v-if="autoMapHint" class="ml-1">· {{ autoMapHint }}</span>
            </div>
          </div>
        </div>

        <!-- 已映射导联列表 -->
        <div v-if="mappingList.length > 0" class="mapped-chips mb-3">
          <v-chip
            v-for="m in sortedMappingList"
            :key="m.electrode"
            size="small"
            closable
            color="primary"
            variant="tonal"
            class="mapped-chip"
            @click="openChannelSelector(m.electrode)"
            @click:close.stop="removeMapping(m.electrode)"
          >
            <b>{{ subjectId || '0' }}@{{ m.electrode }}</b>
            <v-icon size="x-small" class="mx-1">mdi-arrow-right</v-icon>
            {{ deviceLabel(m.deviceId) }} · {{ channelLabel(m) }}
          </v-chip>
        </div>

        <!-- 10-20 电极位置可视化 -->
        <div class="ten-twenty-map-container">
          <div ref="mapContainer" class="ten-twenty-map"></div>
          <div v-if="hoverElectrode" class="map-hover-hint">
            {{ hoverElectrode.mapped ? '重新映射' : '点击映射' }}: {{ hoverElectrode.name }}
          </div>
        </div>

        <!-- 操作提示 -->
        <div class="text-caption text-medium-emphasis mt-2 d-flex align-center">
          <v-icon size="x-small" class="mr-1">mdi-cursor-default-click</v-icon>
          点击头部地图上的电极选择设备通道；点击已映射芯片可修改映射。
        </div>

        <!-- 脑区分组信息 -->
        <v-expansion-panels variant="accordion" class="mt-3">
          <v-expansion-panel>
            <v-expansion-panel-title class="py-2">
              <v-icon size="small" class="mr-2">mdi-brain</v-icon>
              10-20 电极脑区分组
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <div v-for="region in regions" :key="region.name" class="d-flex align-center mb-2 flex-wrap">
                <div
                  class="region-color-dot mr-2"
                  :style="{ backgroundColor: region.color }"
                />
                <span class="text-caption mr-2 region-name">{{ region.name }}</span>
                <v-chip
                  v-for="el in region.electrodes"
                  :key="el"
                  size="x-small"
                  :color="mappedElectrodes.has(el) ? 'primary' : undefined"
                  variant="tonal"
                  class="mr-1 mb-1"
                  @click="openChannelSelector(el)"
                >
                  {{ el }}
                </v-chip>
              </div>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </v-card-text>

      <v-divider />

      <v-card-actions class="pa-3">
        <v-spacer />
        <v-btn variant="text" @click="close">取消</v-btn>
        <v-btn
          color="primary"
          variant="flat"
          :disabled="mappingList.length === 0"
          @click="confirm"
        >
          确认映射 ({{ mappingList.length }} 个导联)
        </v-btn>
      </v-card-actions>
    </v-card>

    <!-- 设备通道选择对话框 -->
    <v-dialog v-model="channelSelectorOpen" max-width="400px" persistent>
      <v-card>
        <v-card-title class="d-flex align-center py-3">
          <v-icon class="mr-2" color="primary">mdi-map-marker</v-icon>
          映射导联: {{ subjectId || '0' }}@{{ pendingElectrode }}
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-4">
          <v-alert v-if="effectiveDevices.length === 0" type="warning" variant="tonal" density="compact" class="mb-3">
            没有可用的设备。请先在设备管理中添加设备。
          </v-alert>

          <template v-if="effectiveDevices.length > 0">
            <!-- 选择设备 -->
            <v-select
              v-model="selectedDeviceId"
              :items="effectiveDevices"
              item-title="name"
              item-value="id"
              label="选择设备"
              density="compact"
              variant="outlined"
              class="mb-2"
              :disabled="!!props.restrictToDeviceId || effectiveDevices.length <= 1"
            />

            <!-- 选择通道 -->
            <div class="text-caption text-medium-emphasis mb-1">选择通道</div>
            <v-radio-group v-model="selectedChannelIndex" density="compact" hide-details>
              <v-radio
                v-for="ch in deviceChannels"
                :key="ch.index"
                :value="ch.index"
                density="compact"
              >
                <template #label>
                  <span>{{ ch.label }}</span>
                  <v-chip
                    v-if="channelUsedBy(ch.index)"
                    size="x-small"
                    color="warning"
                    variant="tonal"
                    class="ml-2"
                  >
                    已映射到 {{ channelUsedBy(ch.index) }}
                  </v-chip>
                </template>
              </v-radio>
            </v-radio-group>
          </template>
        </v-card-text>
        <v-card-actions class="pa-3">
          <v-spacer />
          <v-btn variant="text" @click="channelSelectorOpen = false">取消</v-btn>
          <v-btn
            color="primary"
            variant="flat"
            :disabled="!selectedDeviceId || effectiveDevices.length === 0"
            @click="confirmChannelSelection"
          >
            确认
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted, nextTick } from 'vue';
import * as echarts from 'echarts';
import {
  getTenTwentyPositions,
  TEN_TWENTY_REGIONS,
} from '../data/ten_twenty_positions';
import type {
  ElectrodeMapping,
  TenTwentyDialogResult,
} from '../data/ten_twenty_positions';

const props = defineProps<{
  modelValue: boolean;
  /** 可用的设备列表 (含通道信息) */
  devices?: Array<{
    id: string;
    name: string;
    channelCount: number;
    channels?: Array<{ index: number; name: string; alias?: string }>;
  }>;
  /** 限制只能选择指定的设备 (节点编辑场景) */
  restrictToDeviceId?: string | null;
  /** 初始映射 */
  initialMappings?: ElectrodeMapping[];
  initialSubjectId?: string;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
  (e: 'confirm', result: TenTwentyDialogResult): void;
}>();

const dialogModel = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
});

const subjectId = ref(props.initialSubjectId || '0');
const mappingList = ref<ElectrodeMapping[]>(props.initialMappings || []);
const autoMapHint = ref('');

/** 电极名 → ElectrodeMapping 快速查找 */
const mappingByElectrode = computed(() => {
  const map = new Map<string, ElectrodeMapping>();
  for (const m of mappingList.value) {
    map.set(m.electrode, m);
  }
  return map;
});

/** 已映射的电极名集合 */
const mappedElectrodes = computed(() => new Set(mappingList.value.map(m => m.electrode)));

/** 按电极顺序排列的映射列表（与头部地图顺序一致，便于阅读） */
const sortedMappingList = computed(() => {
  const order = new Map(positions.map((p, i) => [p.name, i]));
  return [...mappingList.value].sort(
    (a, b) => (order.get(a.electrode) ?? 999) - (order.get(b.electrode) ?? 999),
  );
});

/** 设备通道已被哪个电极占用 */
function channelUsedBy(channelIndex: number): string | null {
  const m = mappingList.value.find(
    x => x.deviceId === selectedDeviceId.value && x.channelIndex === channelIndex,
  );
  if (!m || m.electrode === pendingElectrode.value) return null;
  return m.electrode;
}

// ===== 设备+通道选择相关 =====
const pendingElectrode = ref<string | null>(null);
const channelSelectorOpen = ref(false);
const hoverElectrode = ref<{ name: string; mapped: boolean } | null>(null);

/** 根据 props 计算可选的设备列表 */
const effectiveDevices = computed(() => {
  let list = props.devices || [];
  if (props.restrictToDeviceId && list.length > 0) {
    list = list.filter(d => d.id === props.restrictToDeviceId);
  }
  return list;
});

/** 获取设备名称 */
function deviceLabel(deviceId: string): string {
  const d = effectiveDevices.value.find(x => x.id === deviceId);
  return d ? d.name : deviceId;
}

/** 获取通道标签 */
function channelLabel(mapping: ElectrodeMapping): string {
  const d = effectiveDevices.value.find(x => x.id === mapping.deviceId);
  if (!d) return `CH${mapping.channelIndex + 1}`;
  const ch = d.channels?.[mapping.channelIndex];
  return ch?.alias || ch?.name || `CH${mapping.channelIndex + 1}`;
}

const selectedDeviceId = ref('');
const selectedChannelIndex = ref(0);

const deviceChannels = computed(() => {
  const d = effectiveDevices.value.find(x => x.id === selectedDeviceId.value);
  if (!d) return [];
  const count = d.channelCount || d.channels?.length || 8;
  return Array.from({ length: count }, (_, i) => {
    const ch = d.channels?.[i];
    return {
      index: i,
      label: ch?.alias || ch?.name || `CH${i + 1}`,
    };
  });
});

function openChannelSelector(electrodeName: string) {
  pendingElectrode.value = electrodeName;

  // 如果已经有映射, 预填
  const existing = mappingByElectrode.value.get(electrodeName);
  if (existing && effectiveDevices.value.find(d => d.id === existing.deviceId)) {
    selectedDeviceId.value = existing.deviceId;
    selectedChannelIndex.value = existing.channelIndex;
  } else if (effectiveDevices.value.length > 0) {
    selectedDeviceId.value = effectiveDevices.value[0].id;
    // 默认选第一个未被占用的通道
    const dev = effectiveDevices.value[0];
    const used = new Set(
      mappingList.value.filter(m => m.deviceId === dev.id).map(m => m.channelIndex),
    );
    const chCount = dev.channelCount || 8;
    let first = 0;
    while (used.has(first) && first < chCount - 1) first++;
    selectedChannelIndex.value = first;
  } else {
    selectedDeviceId.value = '';
    selectedChannelIndex.value = 0;
  }

  channelSelectorOpen.value = true;
}

function confirmChannelSelection() {
  if (!pendingElectrode.value || !selectedDeviceId.value) return;
  const el = pendingElectrode.value;

  // 一个通道只能映射一个电极：移除占用该通道的其他电极映射
  const conflictIdx = mappingList.value.findIndex(
    m => m.deviceId === selectedDeviceId.value
      && m.channelIndex === selectedChannelIndex.value
      && m.electrode !== el,
  );
  if (conflictIdx >= 0) mappingList.value.splice(conflictIdx, 1);

  // 移除旧的映射 (同一电极)
  const idx = mappingList.value.findIndex(m => m.electrode === el);
  if (idx >= 0) mappingList.value.splice(idx, 1);

  const ch = deviceChannels.value[selectedChannelIndex.value];
  mappingList.value.push({
    electrode: el,
    deviceId: selectedDeviceId.value,
    channelIndex: selectedChannelIndex.value,
    channelLabel: ch?.label || `CH${selectedChannelIndex.value + 1}`,
  });

  channelSelectorOpen.value = false;
  pendingElectrode.value = null;
}

function removeMapping(electrodeName: string) {
  const idx = mappingList.value.findIndex(m => m.electrode === electrodeName);
  if (idx >= 0) mappingList.value.splice(idx, 1);
}

function clearAllMappings() {
  mappingList.value = [];
  autoMapHint.value = '';
}

/** 顺序自动映射：按设备通道顺序为电极分配通道 */
function autoMapSequential() {
  if (effectiveDevices.value.length === 0) return;
  const device = effectiveDevices.value.find(d => d.id === selectedDeviceId.value)
    || effectiveDevices.value[0];
  const chCount = device.channelCount || device.channels?.length || 8;

  // 移除该设备的旧映射，其余设备的映射保留
  const others = mappingList.value.filter(m => m.deviceId !== device.id);
  const target = positions.slice(0, chCount);
  const newMappings: ElectrodeMapping[] = target.map((p, i) => ({
    electrode: p.name,
    deviceId: device.id,
    channelIndex: i,
    channelLabel: device.channels?.[i]?.alias || device.channels?.[i]?.name || `CH${i + 1}`,
  }));
  mappingList.value = [...others, ...newMappings];
  autoMapHint.value = `已按顺序将前 ${target.length} 个电极映射到「${device.name}」`;
}

const mapContainer = ref<HTMLElement | null>(null);

const positions = getTenTwentyPositions();
const regions = TEN_TWENTY_REGIONS;

function close() {
  dialogModel.value = false;
}

function confirm() {
  emit('confirm', {
    subjectId: subjectId.value || '0',
    mappings: [...mappingList.value],
  });
  dialogModel.value = false;
}

// ==================== ECharts 初始化 ====================

let chartInstance: echarts.ECharts | null = null;

function buildChartOption(): echarts.EChartsOption {
  const headRadius = 1.0;

  const earCoords: Array<[number, number][]> = [
    [[-1.0, -0.08], [-1.08, -0.04], [-1.08, 0.02], [-1.0, 0.06]],
    [[1.0, -0.08], [1.08, -0.04], [1.08, 0.02], [1.0, 0.06]],
  ];

  // 根据是否已映射决定颜色
  const scatterData = positions.map((p) => {
    const mapped = mappingByElectrode.value.get(p.name);
    return {
      name: p.name,
      value: [p.x, p.y],
      symbolSize: 16,
      itemStyle: {
        color: mapped ? '#2196F3' : '#90A4AE',
        borderColor: mapped ? '#1565C0' : '#607D8B',
        borderWidth: 1.5,
        shadowBlur: mapped ? 8 : 0,
        shadowColor: '#2196F3',
      },
      label: {
        show: true,
        position: 'bottom' as const,
        distance: 6,
        fontSize: 11,
        fontWeight: mapped ? 'bold' : 'normal',
        color: mapped ? '#42A5F5' : '#78909C',
        formatter: () => p.name,
      },
    };
  });

  return {
    backgroundColor: 'transparent',
    grid: { left: 0, right: 0, top: 0, bottom: 0 },
    xAxis: { type: 'value', min: -1.2, max: 1.2, show: false },
    yAxis: { type: 'value', min: -1.15, max: 1.25, show: false },
    series: [
      // 头部轮廓（散点连线，避免 custom series 因空 data 不渲染）
      {
        type: 'scatter',
        name: 'head_outline',
        z: 1,
        silent: true,
        symbolSize: 4,
        itemStyle: { color: '#78909C' },
        data: Array.from({ length: 121 }, (_, i) => {
          const angle = (i / 120) * Math.PI * 2;
          return [headRadius * Math.cos(angle), headRadius * Math.sin(angle)];
        }),
      },
      // 内圈填充（浅色点阵衬托电极）
      {
        type: 'scatter',
        name: 'head_fill',
        z: 0,
        silent: true,
        symbolSize: 2,
        itemStyle: { color: 'rgba(120, 144, 156, 0.25)' },
        data: (() => {
          const pts: [number, number][] = [];
          for (let r = 0.15; r < 0.98; r += 0.12) {
            const n = Math.max(6, Math.round(r * 36));
            for (let i = 0; i < n; i++) {
              const angle = (i / n) * Math.PI * 2;
              pts.push([r * Math.cos(angle), r * Math.sin(angle)]);
            }
          }
          return pts;
        })(),
      },
      // 耳朵
      ...earCoords.map((coords, i) => ({
        type: 'scatter' as const,
        name: `ear_${i}`,
        z: 1,
        silent: true,
        symbolSize: 4,
        itemStyle: { color: '#78909C' },
        data: coords,
      })),
      // 鼻子（三角形标记，指向头顶方向）
      {
        type: 'scatter',
        name: 'nose',
        z: 1,
        silent: true,
        symbol: 'triangle',
        symbolSize: 16,
        itemStyle: { color: '#78909C' },
        data: [[0, 1.09]],
      },
      // 中线
      {
        type: 'scatter',
        name: 'midline',
        z: 1,
        silent: true,
        symbolSize: 2,
        itemStyle: { color: 'rgba(120, 144, 156, 0.4)' },
        data: Array.from({ length: 40 }, (_, i) => [0, -1 + (i / 39) * 2] as [number, number]),
      },
      // 电极点
      {
        type: 'scatter',
        name: 'electrodes',
        z: 10,
        data: scatterData,
        emphasis: {
          scale: 1.4,
          itemStyle: { shadowBlur: 12, shadowColor: '#2196F3' },
        },
      },
    ],
  };
}

function initChart() {
  if (!mapContainer.value) return;
  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }
  chartInstance = echarts.init(mapContainer.value);
  chartInstance.setOption(buildChartOption());

  // 点击电极 → 打开设备通道选择器
  chartInstance.on('click', (params: any) => {
    if (params.seriesName === 'electrodes' && params.name) {
      openChannelSelector(params.name);
    }
  });

  // hover 提示
  chartInstance.on('mouseover', (params: any) => {
    if (params.seriesName === 'electrodes' && params.name) {
      hoverElectrode.value = {
        name: params.name,
        mapped: mappedElectrodes.value.has(params.name),
      };
    }
  });
  chartInstance.on('mouseout', (params: any) => {
    if (params.seriesName === 'electrodes') {
      hoverElectrode.value = null;
    }
  });
  chartInstance.getZr().on('mouseout', (e: any) => {
    if (!e.target) hoverElectrode.value = null;
  });
}

function resizeChart() {
  const el = mapContainer.value;
  if (!el || !chartInstance) return;
  chartInstance.resize({ width: el.clientWidth, height: el.clientHeight });
}

let resizeObserver: ResizeObserver | null = null;

// 当映射变化时更新图表
watch(mappingList, () => {
  if (chartInstance) {
    chartInstance.setOption(buildChartOption());
  }
}, { deep: true });

watch(dialogModel, async (val) => {
  if (val) {
    subjectId.value = props.initialSubjectId || '0';
    mappingList.value = props.initialMappings ? [...props.initialMappings] : [];
    autoMapHint.value = '';
    await nextTick();
    // 对话框是懒挂载的，打开时才初始化图表
    if (mapContainer.value) {
      initChart();
      resizeChart();
      if (!resizeObserver) {
        resizeObserver = new ResizeObserver(() => resizeChart());
        resizeObserver.observe(mapContainer.value);
      }
    }
  }
});

onUnmounted(() => {
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }
});
</script>

<style scoped>
.ten-twenty-map-container {
  position: relative;
  width: 100%;
  height: 320px;
  flex-shrink: 0;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 8px;
  overflow: hidden;
  background: rgba(var(--v-theme-on-surface), 0.02);
}

.ten-twenty-map {
  width: 100%;
  height: 100%;
  cursor: pointer;
}

.map-hover-hint {
  position: absolute;
  top: 8px;
  left: 50%;
  transform: translateX(-50%);
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  background: rgba(var(--v-theme-surface), 0.95);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.15);
  color: rgb(var(--v-theme-on-surface));
  pointer-events: none;
}

.mapped-chips {
  max-height: 68px;
  overflow-y: auto;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 2px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  border-radius: 6px;
}

.mapped-chip {
  cursor: pointer;
}

.region-color-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
}

.region-name {
  min-width: 70px;
}
</style>
