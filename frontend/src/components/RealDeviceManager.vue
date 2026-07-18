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
      <v-expansion-panels v-model="openGroups" multiple>
        <v-expansion-panel
          v-for="group in devicesByDriver"
          :key="group.driverType"
          :value="group.driverType"
        >
          <v-expansion-panel-title class="py-2">
            <div class="d-flex align-center ga-2">
              <v-icon size="small" :color="groupColor(group.driverType)">
                {{ groupIcon(group.driverType) }}
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
                  <v-chip size="x-small" :color="statusColor(device)">
                    {{ statusText(device) }}
                  </v-chip>
                </v-list-item-title>

                <v-list-item-subtitle class="text-caption">
                  {{ device.sampling_rate }} Hz · {{ device.channel_count }} ch
                  <span v-if="device.connection_status?.pending_count">
                    · 缓冲 {{ device.connection_status.pending_count }} 帧
                  </span>
                </v-list-item-subtitle>

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

    <!-- 连接参数对话框（仅串口类驱动需要波特率） -->
    <v-dialog v-model="showConnectDialog" max-width="400">
      <v-card>
        <v-card-title>连接设备</v-card-title>
        <v-card-text>
          <p>设备: <strong>{{ selectedDevice?.name }}</strong></p>
          <p class="text-caption text-grey">{{ selectedDevice?.device_id }}</p>
          <v-select
            v-if="isSerialDriver(selectedDevice?.type)"
            v-model="connectBaudrate"
            :items="baudrateOptions"
            label="波特率"
            class="mt-3"
          />
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
  </v-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { realDeviceApi, type DeviceInfo, type DriverInfo } from '../services/realDeviceApi'

const showConnectDialog = ref(false)
const selectedDevice = ref<DeviceInfo | null>(null)
const connectBaudrate = ref(460800)

// 面板展开状态：驱动详情默认收起，设备组默认全部展开
const driverPanelOpen = ref<number[]>([])
const openGroups = ref<string[]>([])

interface DriverGroup {
  driverType: string
  driverName: string
  driverDescription: string
  devices: DeviceInfo[]
}

// 按驱动分组
const devicesByDriver = computed<DriverGroup[]>(() => {
  const map = new Map<string, DeviceInfo[]>()
  for (const d of realDeviceApi.devices.value) {
    const t = d.type || 'unknown'
    if (!map.has(t)) map.set(t, [])
    map.get(t)!.push(d)
  }
  const driverMeta = new Map<string, DriverInfo>(
    realDeviceApi.drivers.value.map(d => [d.driver_type, d])
  )
  const groups: DriverGroup[] = []
  for (const [driverType, devices] of map) {
    const meta = driverMeta.get(driverType)
    groups.push({
      driverType,
      driverName: meta?.driver_name || driverType,
      driverDescription: meta?.driver_description || '',
      devices,
    })
  }
  groups.sort((a, b) => a.driverType.localeCompare(b.driverType))
  // 初始化时全部展开
  if (openGroups.value.length === 0) {
    openGroups.value = groups.map(g => g.driverType)
  }
  return groups
})

const baudrateOptions = computed(() =>
  realDeviceApi.getBaudrateOptions().map(rate => ({ title: String(rate), value: rate }))
)

// ---- 状态判断 ----
const deviceStatus = (d: DeviceInfo) => d.connection_status?.status || 'disconnected'
const isConnected = (d: DeviceInfo) => ['connected', 'acquiring'].includes(deviceStatus(d))
const isAcquiring = (d: DeviceInfo) => deviceStatus(d) === 'acquiring'
const isDisconnected = (d: DeviceInfo) => deviceStatus(d) === 'disconnected'
const isSerialDriver = (driverType?: string) => driverType === 'wearable_eeg'

const canConnect = (d: DeviceInfo) => isDisconnected(d) || deviceStatus(d) === 'error'
const canStart = (d: DeviceInfo) => deviceStatus(d) === 'connected'
const canStop = (d: DeviceInfo) => isAcquiring(d)
const canDisconnect = (d: DeviceInfo) => isConnected(d)

// ---- 显示辅助 ----
const statusColor = (d: DeviceInfo) => realDeviceApi.getStatusColor(deviceStatus(d))
const statusIcon = (d: DeviceInfo) => realDeviceApi.getStatusIcon(deviceStatus(d))
const statusText = (d: DeviceInfo) => realDeviceApi.getStatusText(deviceStatus(d))

const groupActiveCount = (g: DriverGroup) =>
  g.devices.filter(d => isAcquiring(d)).length

const groupIcon = (driverType: string) => {
  if (driverType === 'simulated') return 'mdi-ghost'
  if (driverType === 'wearable_eeg') return 'mdi-serial-port'
  return 'mdi-chip'
}
const groupColor = (driverType: string) => {
  if (driverType === 'simulated') return 'purple'
  if (driverType === 'wearable_eeg') return 'blue'
  return 'grey'
}

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
  if (isSerialDriver(device.type)) {
    showConnectDialog.value = true
  } else {
    doConnect(device)
  }
}

const confirmConnect = () => {
  if (!selectedDevice.value) return
  doConnect(selectedDevice.value, connectBaudrate.value)
  showConnectDialog.value = false
}

const doConnect = async (device: DeviceInfo, baudrate?: number) => {
  await realDeviceApi.connectDevice(device.device_id, baudrate ?? 460800)
}

const startAcquisition = (device: DeviceInfo) =>
  realDeviceApi.startAcquisition(device.device_id)
const stopAcquisition = (device: DeviceInfo) =>
  realDeviceApi.stopAcquisition(device.device_id)
const disconnectDevice = (device: DeviceInfo) =>
  realDeviceApi.disconnectDevice(device.device_id)

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
.device-active {
  border-left-color: rgb(var(--v-theme-success));
  background: rgba(var(--v-theme-success), 0.06);
}
</style>
