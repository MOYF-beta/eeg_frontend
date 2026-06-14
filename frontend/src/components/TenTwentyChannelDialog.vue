<template>
  <v-dialog v-model="dialogModel" max-width="750px" persistent>
    <v-card>
      <v-card-title class="d-flex align-center justify-space-between">
        <span>10-20 标准导联系统 - 通道映射</span>
        <v-btn icon="mdi-close" variant="text" size="small" @click="close" />
      </v-card-title>

      <v-divider />

      <v-card-text class="pa-4">
        <!-- 被试编号输入 -->
        <div class="mb-3">
          <v-text-field
            v-model="subjectId"
            label="被试编号"
            hint="默认 0。最终格式: {被试编号}@{电极}，如 0@Cz"
            persistent-hint
            density="compact"
            variant="outlined"
            clearable
          />
        </div>

        <!-- 已映射导联列表 -->
        <div v-if="mappingList.length > 0" class="mb-3">
          <div class="text-caption text-grey mb-1">已映射 ({{ mappingList.length }}):</div>
          <div class="d-flex flex-wrap ga-1">
            <v-chip
              v-for="m in mappingList"
              :key="m.electrode"
              size="small"
              closable
              color="primary"
              @click:close="removeMapping(m.electrode)"
            >
              {{ subjectId }}@{{ m.electrode }}
              <v-icon size="x-small" class="mx-1">mdi-arrow-right</v-icon>
              {{ deviceLabel(m.deviceId) }}:{{ channelLabel(m) }}
            </v-chip>
          </div>
        </div>

        <!-- 10-20 电极位置可视化 -->
        <div class="ten-twenty-map-container">
          <div ref="mapContainer" class="ten-twenty-map"></div>
        </div>

        <!-- 操作提示 -->
        <div class="text-caption text-grey mt-2">
          点击头部地图上的电极，选择设备与通道完成映射。
        </div>

        <!-- 脑区分组信息 -->
        <v-expansion-panels variant="accordion" class="mt-3">
          <v-expansion-panel>
            <v-expansion-panel-title>
              <v-icon left size="small" class="mr-2">mdi-brain</v-icon>
              10-20 电极脑区分组
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <div v-for="region in regions" :key="region.name" class="d-flex align-center mb-2">
                <div
                  class="region-color-dot mr-2"
                  :style="{ backgroundColor: region.color }"
                />
                <span class="text-caption mr-2">{{ region.name }}:</span>
                <v-chip
                  v-for="el in region.electrodes"
                  :key="el"
                  size="x-small"
                  :color="mappedElectrodes.has(el) ? 'primary' : undefined"
                  variant="tonal"
                  class="mr-1"
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

      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn variant="text" @click="close">取消</v-btn>
        <v-btn
          color="primary"
          variant="tonal"
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
        <v-card-title class="d-flex align-center">
          <v-icon class="mr-2">mdi-map-marker</v-icon>
          映射导联: {{ subjectId }}@{{ pendingElectrode }}
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
              class="mb-3"
              :disabled="!!props.restrictToDeviceId || effectiveDevices.length <= 1"
            />

            <!-- 选择通道 -->
            <v-radio-group v-model="selectedChannelIndex" density="compact">
              <v-radio
                v-for="ch in deviceChannels"
                :key="ch.index"
                :value="ch.index"
                :label="`${ch.label}`"
                density="compact"
              />
            </v-radio-group>
          </template>
        </v-card-text>
        <v-card-actions class="pa-3">
          <v-spacer />
          <v-btn variant="text" @click="channelSelectorOpen = false">取消</v-btn>
          <v-btn
            color="primary"
            variant="tonal"
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
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue';
import * as echarts from 'echarts';
import {
  getTenTwentyPositions,
  TEN_TWENTY_REGIONS,
  type ElectrodePosition,
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

// ===== 设备+通道选择相关 =====
const pendingElectrode = ref<string | null>(null);
const channelSelectorOpen = ref(false);

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
  if (!d) return `通道 ${mapping.channelIndex}`;
  const ch = d.channels?.[mapping.channelIndex];
  return ch?.alias || ch?.name || `通道 ${mapping.channelIndex}`;
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
      label: ch?.alias || ch?.name || `通道 ${i}`,
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
    selectedChannelIndex.value = 0;
  } else {
    selectedDeviceId.value = '';
    selectedChannelIndex.value = 0;
  }

  channelSelectorOpen.value = true;
}

function confirmChannelSelection() {
  if (!pendingElectrode.value || !selectedDeviceId.value) return;
  const el = pendingElectrode.value;

  // 移除旧的映射 (同一电极)
  const idx = mappingList.value.findIndex(m => m.electrode === el);
  if (idx >= 0) mappingList.value.splice(idx, 1);

  const ch = deviceChannels.value[selectedChannelIndex.value];
  mappingList.value.push({
    electrode: el,
    deviceId: selectedDeviceId.value,
    channelIndex: selectedChannelIndex.value,
    channelLabel: ch?.label || `通道 ${selectedChannelIndex.value}`,
  });

  channelSelectorOpen.value = false;
  pendingElectrode.value = null;
}

function removeMapping(electrodeName: string) {
  const idx = mappingList.value.findIndex(m => m.electrode === electrodeName);
  if (idx >= 0) mappingList.value.splice(idx, 1);
}

const mapContainer = ref<HTMLElement | null>(null);

const positions = getTenTwentyPositions();
const regions = TEN_TWENTY_REGIONS;

function close() {
  dialogModel.value = false;
}

function confirm() {
  emit('confirm', {
    subjectId: subjectId.value,
    mappings: [...mappingList.value],
  });
  dialogModel.value = false;
}

// ==================== ECharts 初始化 ====================

let chartInstance: echarts.ECharts | null = null;

function buildChartOption(): echarts.EChartsOption {
  // 头部轮廓点
  const headPoints: [number, number][] = [];
  const headRadius = 1.0;
  const steps = 100;
  for (let i = 0; i <= steps; i++) {
    const angle = (i / steps) * Math.PI * 2;
    headPoints.push([headRadius * Math.cos(angle), headRadius * Math.sin(angle)]);
  }
  // 鼻子 (三角形)
  const noseY = 0.12;
  const noseW = 0.06;

  // 耳朵标记
  const earPoints: Array<{ type: string; coords: [number, number][]; color: string }> = [
    {
      type: 'left_ear',
      coords: [[-1.0, -0.08], [-1.08, -0.04], [-1.08, 0.02], [-1.0, 0.06]],
      color: '#999',
    },
    {
      type: 'right_ear',
      coords: [[1.0, -0.08], [1.08, -0.04], [1.08, 0.02], [1.0, 0.06]],
      color: '#999',
    },
  ];

  const posMap = new Map(positions.map((p) => [p.name, p]));

  // 根据是否已映射决定颜色
  const scatterData = positions.map((p) => {
    const mapped = mappingByElectrode.value.get(p.name);
    return {
      name: p.name,
      value: [p.x, p.y],
      symbolSize: 14,
      itemStyle: {
        color: mapped ? '#2196F3' : '#78909C',
        borderColor: mapped ? '#1565C0' : '#546E7A',
        borderWidth: 2,
        shadowBlur: mapped ? 8 : 0,
        shadowColor: '#2196F3',
      },
      label: {
        show: true,
        position: 'bottom' as const,
        distance: 8,
        fontSize: 11,
        fontWeight: mapped ? 'bold' : 'normal',
        color: mapped ? '#1565C0' : '#78909C',
        formatter: () => p.name,
      },
    };
  });

  // 鼻子轮廓
  const noseShape: echarts.CustomSeriesOption = {
    type: 'custom',
    name: 'nose',
    z: 1,
    renderItem: (_params: any, api: any) => {
      const cx = api.coord([0, 0])[0];
      const cy = api.coord([0, 0])[1];
      const headR = api.size([headRadius, 0])[0];
      const nY = headR + noseY * headR;
      const nW = noseW * headR;
      return {
        type: 'polygon',
        shape: {
          points: [
            [cx, cy - headR],
            [cx + nW, cy - headR - nY * 0.8],
            [cx + nW * 0.8, cy - headR - nY],
            [cx - nW * 0.8, cy - headR - nY],
            [cx - nW, cy - headR - nY * 0.8],
          ],
        },
        style: { fill: '#B0BEC5', stroke: '#78909C', lineWidth: 1 },
      };
    },
  };

  return {
    backgroundColor: 'transparent',
    grid: {
      left: 0,
      right: 0,
      top: 0,
      bottom: 0,
    },
    xAxis: {
      type: 'value',
      min: -1.25,
      max: 1.25,
      show: false,
    },
    yAxis: {
      type: 'value',
      min: -1.25,
      max: 1.25,
      show: false,
    },
    series: [
      // 头部轮廓
      {
        type: 'custom',
        name: 'head_outline',
        z: 1,
        renderItem: (_params: any, api: any) => {
          const cx = api.coord([0, 0])[0];
          const cy = api.coord([0, 0])[1];
          const r = api.size([headRadius, 0])[0];
          return {
            type: 'circle',
            shape: { cx, cy, r },
            style: { fill: '#ECEFF1', stroke: '#78909C', lineWidth: 2 },
          };
        },
      },
      // 耳朵
      ...earPoints.map((ear, i) => ({
        type: 'custom' as const,
        name: `ear_${i}`,
        z: 2,
        renderItem: (_params: any, api: any) => {
          const points = ear.coords.map(([ex, ey]) => {
            const px = api.coord([ex, ey])[0];
            const py = api.coord([ex, ey])[1];
            return [px, py];
          });
          return {
            type: 'polygon',
            shape: { points },
            style: { fill: '#BDBDBD', stroke: '#9E9E9E', lineWidth: 1 },
          };
        },
      })) as echarts.SeriesOption[],
      // 鼻子
      noseShape,
      // 中线
      {
        type: 'custom',
        name: 'midline',
        z: 1,
        renderItem: (_params: any, api: any) => {
          const cx = api.coord([0, 0])[0];
          const cy = api.coord([0, 0])[1];
          const r = api.size([headRadius, 0])[0];
          return {
            type: 'line',
            shape: { x1: cx, y1: cy - r, x2: cx, y2: cy + r },
            style: { stroke: '#B0BEC5', lineWidth: 1, lineDash: [4, 4] },
          };
        },
      },
      // 电极点
      {
        type: 'scatter',
        name: 'electrodes',
        z: 10,
        data: scatterData,
        emphasis: {
          scale: 1.5,
          itemStyle: { shadowBlur: 12 },
        },
      },
    ],
  };
}

function initChart() {
  if (!mapContainer.value) return;
  if (chartInstance) {
    chartInstance.dispose();
  }
  chartInstance = echarts.init(mapContainer.value, undefined, {
    width: mapContainer.value.clientWidth,
    height: mapContainer.value.clientHeight,
  });
  chartInstance.setOption(buildChartOption());

  // 点击电极 → 打开设备通道选择器
  chartInstance.on('click', (params: any) => {
    if (params.seriesName === 'electrodes' && params.name) {
      openChannelSelector(params.name);
    }
  });
}

function resizeChart() {
  const el = mapContainer.value;
  if (!el || !chartInstance) return;
  chartInstance.resize({ width: el.clientWidth, height: el.clientHeight });
}

let resizeObserver: ResizeObserver | null = null;

onMounted(async () => {
  await nextTick();
  initChart();
  if (mapContainer.value) {
    resizeObserver = new ResizeObserver(() => resizeChart());
    resizeObserver.observe(mapContainer.value);
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
    await nextTick();
    if (!chartInstance && mapContainer.value) {
      initChart();
    }
    resizeChart();
  }
});
</script>

<style scoped>
.ten-twenty-map-container {
  width: 100%;
  aspect-ratio: 4 / 3;
  max-height: 400px;
  border: 1px solid #E0E0E0;
  border-radius: 8px;
  overflow: hidden;
  background: #FAFAFA;
}

.ten-twenty-map {
  width: 100%;
  height: 100%;
}

.region-color-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
}
</style>
