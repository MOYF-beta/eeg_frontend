<template>
  <v-container fluid class="py-4">
    <v-card>
      <v-card-title class="d-flex align-center ga-3">
        <v-icon>mdi-console-line</v-icon>
        串口调试输出
        <v-spacer />
        <v-select
          v-model="selectedPort"
          :items="portOptions"
          label="端口"
          variant="outlined"
          density="compact"
          style="max-width: 280px"
          clearable
        />
        <v-text-field
          v-model.number="sampleCount"
          type="number"
          label="样本数"
          variant="outlined"
          density="compact"
          style="max-width: 120px"
          min="10"
          max="2000"
        />
        <v-select
          v-model="selectedEncoding"
          :items="encodingOptions"
          label="文本编码"
          variant="outlined"
          density="compact"
          style="max-width: 160px"
        />
        <v-switch
          v-model="autoRefresh"
          label="自动刷新"
          density="compact"
          hide-details
        />
        <v-btn color="primary" :loading="loading" @click="refreshNow">刷新</v-btn>
      </v-card-title>

      <v-divider />

      <v-card-text>
        <v-alert
          v-if="realDeviceApi.error.value"
          type="error"
          variant="tonal"
          density="compact"
          class="mb-3"
        >
          {{ realDeviceApi.error.value }}
        </v-alert>

        <v-expansion-panels multiple>
          <v-expansion-panel v-for="portOutput in outputs" :key="portOutput.port">
            <v-expansion-panel-title>
              <div class="d-flex align-center ga-2">
                <v-icon>mdi-serial-port</v-icon>
                <strong>{{ portOutput.port }}</strong>
                <v-chip size="small" color="primary">{{ portOutput.count }} 帧</v-chip>
                <v-chip size="small" color="deep-purple">{{ portOutput.raw_input_count || 0 }} 原始块</v-chip>
              </div>
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <v-table density="compact">
                <thead>
                  <tr>
                    <th>时间</th>
                    <th>通道数据(前4)</th>
                    <th>RAW HEX(前64)</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(sample, idx) in portOutput.samples" :key="`${portOutput.port}-${idx}-${sample.timestamp}`">
                    <td>{{ formatTs(sample.timestamp) }}</td>
                    <td>{{ sample.channels.slice(0, 4).join(', ') }}</td>
                    <td class="mono">{{ (sample.raw_hex || '').slice(0, 64) }}</td>
                  </tr>
                </tbody>
              </v-table>

              <div class="mt-4 text-subtitle-2">原始输入（串口读取块）</div>
              <v-table density="compact" class="mt-2">
                <thead>
                  <tr>
                    <th>时间</th>
                    <th>RAW HEX(前128)</th>
                    <th>解码文本(前128)</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(raw, rIdx) in (portOutput.raw_inputs || [])" :key="`${portOutput.port}-raw-${rIdx}-${raw.timestamp}`">
                    <td>{{ formatTs(raw.timestamp) }}</td>
                    <td class="mono">{{ (raw.raw_hex || '').slice(0, 128) }}</td>
                    <td class="mono">{{ decodeRawText(raw.raw_hex || '').slice(0, 128) }}</td>
                  </tr>
                </tbody>
              </v-table>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>

        <v-alert v-if="outputs.length === 0" type="info" variant="tonal" class="mt-3">
          当前没有可显示的串口输出。请先连接设备并开始采集。
        </v-alert>
      </v-card-text>
    </v-card>
  </v-container>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { realDeviceApi, type SerialDebugPortOutput } from '../services/realDeviceApi'

const outputs = ref<SerialDebugPortOutput[]>([])
const selectedPort = ref<string | null>(null)
const sampleCount = ref(200)
const selectedEncoding = ref('utf-8')
const autoRefresh = ref(true)
const loading = ref(false)
let timer: number | null = null

const encodingOptions = [
  { title: 'UTF-8', value: 'utf-8' },
  { title: 'GBK', value: 'gbk' },
  { title: 'GB18030', value: 'gb18030' },
  { title: 'UTF-16LE', value: 'utf-16le' },
  { title: 'Latin-1', value: 'latin1' },
]

const portOptions = computed(() => {
  const ports = new Set<string>()
  // 从设备列表中获取已连接的真实设备端口
  realDeviceApi.devices.value.forEach(device => {
    if (device.type === 'wearable_eeg' && device.config.connected && device.config.port) {
      ports.add(device.config.port)
    }
  })
  outputs.value.forEach(p => ports.add(p.port))
  return [{ title: '全部端口', value: null as unknown as string }, ...Array.from(ports).map(p => ({ title: p, value: p }))]
})

const formatTs = (ts: number) => new Date(ts * 1000).toLocaleTimeString()

const decodeRawText = (hex: string) => {
  if (!hex) return ''
  try {
    const bytes = new Uint8Array((hex.match(/.{1,2}/g) || []).map(b => parseInt(b, 16)))
    return new TextDecoder(selectedEncoding.value).decode(bytes)
  } catch (err) {
    return `[decode error: ${selectedEncoding.value}]`
  }
}

const fetchData = async () => {
  loading.value = true
  const data = await realDeviceApi.getDebugOutput(selectedPort.value || undefined, Math.max(10, Math.min(2000, Number(sampleCount.value) || 200)))
  outputs.value = data.ports || []
  loading.value = false
}

const refreshNow = async () => {
  await realDeviceApi.getDevices()
  await fetchData()
}

const startTimer = () => {
  if (timer) return
  timer = window.setInterval(() => {
    if (autoRefresh.value) {
      refreshNow()
    }
  }, 1000)
}

const stopTimer = () => {
  if (!timer) return
  clearInterval(timer)
  timer = null
}

watch([selectedPort, sampleCount], () => {
  refreshNow()
})

onMounted(async () => {
  await refreshNow()
  startTimer()
})

onUnmounted(() => {
  stopTimer()
})
</script>

<style scoped>
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 12px;
}
</style>
