<template>
  <v-card class="mb-4" variant="tonal">
    <v-card-title class="d-flex align-center justify-space-between">
      <div class="d-flex align-center">
        <v-icon class="mr-2">mdi-devices</v-icon>
        设备管理
        <v-chip size="small" class="ml-2" color="primary">{{ realDeviceApi.devices.value.length }} 台设备</v-chip>
        <v-chip size="small" class="ml-1" color="secondary">{{ realDeviceApi.drivers.value.length }} 个驱动</v-chip>
      </div>
      <div class="d-flex align-center ga-2">
        <v-btn
          color="primary"
          size="small"
          @click="refreshAll"
          :loading="realDeviceApi.isLoading.value"
        >
          <v-icon left>mdi-refresh</v-icon>
          刷新
        </v-btn>
      </div>
    </v-card-title>

    <v-divider />

    <v-alert
      v-if="realDeviceApi.error.value"
      type="error"
      density="compact"
      variant="tonal"
      class="ma-2"
      closable
      @click:close="realDeviceApi.error.value = null"
    >
      <div class="d-flex align-center">
        <v-icon class="mr-2">mdi-alert</v-icon>
        <span>{{ realDeviceApi.error.value }}</span>
      </div>
    </v-alert>

    <v-card-text class="pa-2">
      <!-- 已加载驱动（可折叠） -->
      <v-expansion-panels v-model="driverPanelOpen" class="mb-2">
        <v-expansion-panel>
          <v-expansion-panel-title class="py-2">
            <div class="d-flex align-center ga-2">
              <v-icon size="small">mdi-cog-box</v-icon>
              <span class="text-body-2">已加载驱动</span>
              <v-chip size="x-small" color="secondary">{{ realDeviceApi.drivers.value.length }}</v-chip>
            </div>
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <v-table density="compact">
              <thead>
                <tr>
                  <th>类型标识</th>
                  <th>名称</th>
                  <th>描述</th>
                  <th>设备数</th>
                  <th>实现类</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="d in realDeviceApi.drivers.value" :key="d.driver_type">
                  <td><code>{{ d.driver_type }}</code></td>
                  <td>{{ d.driver_name }}</td>
                  <td class="text-caption">{{ d.driver_description || '—' }}</td>
                  <td>
                    <v-chip size="x-small" :color="d.device_count > 0 ? 'success' : 'grey'">
                      {{ d.device_count >= 0 ? d.device_count : '?' }}
                    </v-chip>
                  </td>
                  <td class="text-caption mono">{{ d.class_name }}</td>
                </tr>
                <tr v-if="realDeviceApi.drivers.value.length === 0">
                  <td colspan="5" class="text-center text-grey">暂无已加载驱动</td>
                </tr>
              </tbody>
            </v-table>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>

      <!-- 按驱动分组设备（可折叠） -->
      <v-expansion-panels v-model="openGroupsModel" multiple>
        <v-expansion-panel
          v-for="group in devicesByDriver"
          :key="group.driverType"
          :value="group.driverType"
        >
          <v-expansion-panel-title class="py-2">
            <div class="d-flex align-center ga-2">
              <v-icon size="small">
                {{ group.driverIcon }}
              </v-icon>
              <span class="text-body-2 font-weight-medium">{{ group.driverName }}</span>
              <v-chip size="x-small" color="primary">{{ group.devices.length }}</v-chip>
              <code class="text-caption text-grey">{{ group.driverType }}</code>
              <v-chip
                v-if="groupActiveCount(group) > 0"
                size="x-small"
                color="success"
              >
                {{ groupActiveCount(group) }} 采集中
              </v-chip>
            </div>
          </v-expansion-panel-title>

          <v-expansion-panel-text class="pa-0">
            <v-list density="compact" class="pa-0">
              <v-list-item
                v-for="device in group.devices"
                :key="device.id"
                class="device-row px-3"
                :class="{ 'device-active': isAcquiring(device) }"
              >
                <template v-slot:prepend>
                  <v-icon :color="statusColor(device)" size="small">
                    {{ statusIcon(device) }}
                  </v-icon>
                </template>

                <v-list-item-title class="d-flex align-center ga-2">
                  <span>{{ device.name }}</span>
                  <code class="text-caption text-grey">{{ device.device_id }}</code>
                  <v-tooltip :disabled="!deviceLastError(device)" location="top">
                    <template #activator="{ props: tipProps }">
                      <v-chip
                        v-bind="tipProps"
                        size="x-small"
                        :color="statusColor(device)"
                        :class="{ 'cursor-help': !!deviceLastError(device) }"
                      >
                        {{ statusText(device) }}
                      </v-chip>
                    </template>
                    <span>{{ deviceLastError(device) }}</span>
                  </v-tooltip>
                </v-list-item-title>

                <v-list-item-subtitle class="text-caption">
                  {{ device.sampling_rate }} Hz · {{ device.channel_count }} ch
                  <span v-if="device.connection_status?.pending_count">
                    · 缓冲 {{ device.connection_status.pending_count }} 帧
                  </span>
                </v-list-item-subtitle>
                <div
                  v-if="deviceLastError(device)"
                  class="text-caption text-error d-flex align-start mt-1 device-error-line"
                >
                  <v-icon size="x-small" class="mr-1 mt-1px">mdi-alert-circle</v-icon>
                  <span>{{ deviceLastError(device) }}</span>
                </div>

                <template v-slot:append>
                  <div class="d-flex ga-1">
                    <v-btn
                      v-if="canConnect(device)"
                      size="x-small"
                      color="primary"
                      variant="tonal"
                      icon="mdi-link"
                      @click="connectDevice(device)"
                    />
                    <v-btn
                      v-if="canStart(device)"
                      size="x-small"
                      color="success"
                      variant="tonal"
                      icon="mdi-play"
                      @click="startAcquisition(device)"
                    />
                    <v-btn
                      v-if="canStop(device)"
                      size="x-small"
                      color="warning"
                      variant="tonal"
                      icon="mdi-stop"
                      @click="stopAcquisition(device)"
                    />
                    <v-btn
                      v-if="canDisconnect(device)"
                      size="x-small"
                      color="error"
                      variant="tonal"
                      icon="mdi-link-off"
                      @click="disconnectDevice(device)"
                    />
                    <v-btn
                      size="x-small"
                      variant="tonal"
                      icon="mdi-binary"
                      title="查看原始输入"
                      @click="viewRawInputs(device)"
                    />
                  </div>
                </template>
              </v-list-item>

              <v-list-item v-if="group.devices.length === 0">
                <v-list-item-title class="text-grey text-caption">
                  该驱动当前未发现设备
                </v-list-item-title>
              </v-list-item>
            </v-list>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>

      <!-- 无设备总空态 -->
      <v-alert
        v-if="realDeviceApi.devices.value.length === 0"
        type="info"
        variant="tonal"
        density="compact"
        class="mt-2"
      >
        <div class="d-flex align-center">
          <v-icon class="mr-2">mdi-information</v-icon>
          <span>未发现任何设备。请确保驱动已正确加载，且对应物理设备或虚拟服务可用。</span>
        </div>
      </v-alert>
    </v-card-text>

    <!-- 连接参数对话框（按驱动 connect_config_schema 动态渲染） -->
    <v-dialog v-model="showConnectDialog" max-width="400">
      <v-card>
        <v-card-title>连接设备</v-card-title>
        <v-card-text>
          <p>设备: <strong>{{ selectedDevice?.name }}</strong></p>
          <p class="text-caption text-grey">{{ selectedDevice?.device_id }}</p>
          <template v-for="field in connectSchema" :key="field.key">
            <v-select
              v-if="field.type === 'select'"
              v-model="connectConfig[field.key]"
              :items="field.options"
              :label="field.label"
              class="mt-3"
            />
            <v-text-field
              v-else
              v-model="connectConfig[field.key]"
              :label="field.label"
              :type="field.type === 'int' || field.type === 'float' ? 'number' : 'text'"
              class="mt-3"
            />
          </template>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showConnectDialog = false">取消</v-btn>
          <v-btn
            color="primary"
            @click="confirmConnect"
            :loading="realDeviceApi.isLoading.value"
          >
            连接
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 原始输入查看对话框 -->
    <v-dialog v-model="showRawDialog" max-width="800" scrollable>
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon class="mr-2">mdi-binary</v-icon>
          原始输入 — {{ rawDevice?.name }}
          <v-spacer />
          <v-btn icon="mdi-refresh" size="small" variant="text" @click="fetchRawInputs" :loading="rawLoading" />
        </v-card-title>
        <v-card-subtitle>{{ rawDevice?.device_id }}</v-card-subtitle>
        <v-divider />
        <v-card-text style="max-height: 500px">
          <div v-if="rawInputs.length === 0" class="text-center text-grey py-4">
            该设备暂无原始输入数据
          </div>
          <div v-for="(chunk, idx) in rawInputs" :key="idx" class="raw-chunk mb-2">
            <div class="text-caption text-grey">{{ formatTs(chunk.timestamp) }}</div>
            <div class="raw-hex mono">{{ chunk.raw_hex || '(empty)' }}</div>
          </div>
        </v-card-text>
        <v-divider />
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showRawDialog = false">关闭</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watchEffect } from 'vue'
import { realDeviceApi, type DeviceInfo, type DriverInfo, type ConnectConfigField, type SerialRawInput } from '../services/realDeviceApi'
import { nextOpenGroups } from '../services/uiLogic'

const showConnectDialog = ref(false)
const selectedDevice = ref<DeviceInfo | null>(null)
const connectConfig = ref<Record<string, any>>({})

const showRawDialog = ref(false)
const rawDevice = ref<DeviceInfo | null>(null)
const rawInputs = ref<SerialRawInput[]>([])
const rawLoading = ref(false)

// 面板展开状态：驱动详情默认收起，设备组默认全部展开
// openGroups 为 null 表示尚未初始化（首次计算时设为全部展开），
// 之后的空数组是用户主动全部折叠的合法状态，不得再强制展开
const driverPanelOpen = ref<number[]>([])
const openGroups = ref<string[] | null>(null)

interface DriverGroup {
  driverType: string
  driverName: string
  driverDescription: string
  driverIcon: string
  devices: DeviceInfo[]
}

// 驱动元信息映射
const driverMetaMap = computed(() =>
  new Map<string, DriverInfo>(realDeviceApi.drivers.value.map(d => [d.driver_type, d]))
)

// 按驱动分组
const devicesByDriver = computed<DriverGroup[]>(() => {
  const map = new Map<string, DeviceInfo[]>()
  for (const d of realDeviceApi.devices.value) {
    const t = d.type || 'unknown'
    if (!map.has(t)) map.set(t, [])
    map.get(t)!.push(d)
  }
  const groups: DriverGroup[] = []
  for (const [driverType, devices] of map) {
    const meta = driverMetaMap.value.get(driverType)
    groups.push({
      driverType,
      driverName: meta?.driver_name || driverType,
      driverDescription: meta?.driver_description || '',
      driverIcon: meta?.driver_icon || 'mdi-chip',
      devices,
    })
  }
  groups.sort((a, b) => a.driverType.localeCompare(b.driverType))
  return groups
})

// openGroups 为 null 时默认全部展开（不能放 computed 里，Vue 3 惰性求值下副作用不可靠）
watchEffect(() => {
  if (openGroups.value === null && devicesByDriver.value.length > 0) {
    openGroups.value = nextOpenGroups(null, devicesByDriver.value.map(g => g.driverType))
  }
})

// v-expansion-panels 的 v-model 适配层（内部状态保持 null 语义）
const openGroupsModel = computed<string[]>({
  get: () => openGroups.value ?? [],
  set: (val: string[]) => { openGroups.value = val },
})

// 当前选中设备的连接 schema
const connectSchema = computed<ConnectConfigField[]>(() => {
  if (!selectedDevice.value) return []
  return driverMetaMap.value.get(selectedDevice.value.type)?.connect_config_schema || []
})

// ---- 状态判断 ----
const deviceStatus = (d: DeviceInfo) => d.connection_status?.status || 'disconnected'
const isConnected = (d: DeviceInfo) => ['connected', 'acquiring'].includes(deviceStatus(d))
const isAcquiring = (d: DeviceInfo) => deviceStatus(d) === 'acquiring'
const isDisconnected = (d: DeviceInfo) => deviceStatus(d) === 'disconnected'

const canConnect = (d: DeviceInfo) => isDisconnected(d) || deviceStatus(d) === 'error'
const canStart = (d: DeviceInfo) => deviceStatus(d) === 'connected'
const canStop = (d: DeviceInfo) => isAcquiring(d)
const canDisconnect = (d: DeviceInfo) => isConnected(d)

// ---- 显示辅助 ----
const statusColor = (d: DeviceInfo) => realDeviceApi.getStatusColor(deviceStatus(d))
const statusIcon = (d: DeviceInfo) => realDeviceApi.getStatusIcon(deviceStatus(d))
const statusText = (d: DeviceInfo) => realDeviceApi.getStatusText(deviceStatus(d))
const deviceLastError = (d: DeviceInfo): string | null =>
  d.connection_status?.last_error || null

const groupActiveCount = (g: DriverGroup) =>
  g.devices.filter(d => isAcquiring(d)).length

const formatTs = (ts: number) => new Date(ts * 1000).toLocaleTimeString()

// ---- 操作 ----
const refreshAll = async () => {
  await Promise.all([
    realDeviceApi.getDrivers(),
    realDeviceApi.getDevices(),
    realDeviceApi.scanPorts(),
  ])
}

const connectDevice = (device: DeviceInfo) => {
  selectedDevice.value = device
  const schema = driverMetaMap.value.get(device.type)?.connect_config_schema || []
  if (schema.length > 0) {
    // 用驱动的默认值初始化表单
    const cfg: Record<string, any> = {}
    for (const f of schema) cfg[f.key] = f.default
    connectConfig.value = cfg
    showConnectDialog.value = true
  } else {
    doConnect(device, {})
  }
}

const confirmConnect = () => {
  if (!selectedDevice.value) return
  doConnect(selectedDevice.value, connectConfig.value)
  showConnectDialog.value = false
}

const doConnect = async (device: DeviceInfo, config: Record<string, any>) => {
  await realDeviceApi.connectDevice(device.device_id, config)
}

const startAcquisition = (device: DeviceInfo) =>
  realDeviceApi.startAcquisition(device.device_id)
const stopAcquisition = (device: DeviceInfo) =>
  realDeviceApi.stopAcquisition(device.device_id)
const disconnectDevice = (device: DeviceInfo) =>
  realDeviceApi.disconnectDevice(device.device_id)

// ---- 原始输入查看 ----
const viewRawInputs = async (device: DeviceInfo) => {
  rawDevice.value = device
  showRawDialog.value = true
  await fetchRawInputs()
}

const fetchRawInputs = async () => {
  if (!rawDevice.value) return
  rawLoading.value = true
  try {
    const data = await realDeviceApi.getDebugOutput(rawDevice.value.device_id, 50)
    const port = data.ports.find(p => p.port === rawDevice.value!.device_id)
    rawInputs.value = port?.raw_inputs || []
  } finally {
    rawLoading.value = false
  }
}

onMounted(refreshAll)
</script>

<style scoped>
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 12px;
}
.device-row {
  border-left: 3px solid transparent;
  min-height: 48px !important;
}
.cursor-help {
  cursor: help;
}
.device-error-line {
  line-height: 1.3;
  word-break: break-all;
}
.mt-1px {
  margin-top: 1px;
}
.device-active {
  border-left-color: rgb(var(--v-theme-success));
  background: rgba(var(--v-theme-success), 0.06);
}
.raw-chunk {
  border-left: 2px solid rgba(var(--v-theme-primary), 0.4);
  padding-left: 8px;
}
.raw-hex {
  word-break: break-all;
  font-size: 11px;
  line-height: 1.5;
  color: rgb(var(--v-theme-on-surface));
}
</style>
