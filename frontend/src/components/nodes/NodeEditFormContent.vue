<template>
  <div class="node-edit-form-content">
    <!-- 节点类型说明（面向使用者的plain-language提示） -->
    <div v-if="typeDescription" class="node-type-desc">
      <v-icon size="small" class="desc-icon">mdi-information-outline</v-icon>
      <span>{{ typeDescription }}</span>
    </div>

    <!-- ============ 数据源 ============ -->
    <template v-if="nodeType === 'SOURCE'">
      <div class="form-section">
        <div class="form-section-title">
          <v-icon size="small">mdi-devices</v-icon>
          <span>绑定设备</span>
        </div>
        <v-select
          :model-value="selectedDeviceId"
          :items="availableDevices"
          item-title="displayName"
          item-value="id"
          label="绑定设备"
          placeholder="选择采集设备"
          density="compact"
          variant="outlined"
          clearable
          :hint="selectedDeviceHint"
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
        <v-alert
          v-if="!selectedDeviceId"
          type="warning"
          variant="tonal"
          density="compact"
          class="mt-2"
        >
          未绑定设备：运行时将输出后端合成的测试方波而非真实数据。请绑定采集设备，或使用 REPLAY 节点回放数据。
        </v-alert>
        <v-btn
          v-if="!isReadOnly && selectedDevice"
          size="x-small"
          variant="tonal"
          color="primary"
          class="mt-1"
          @click="applyDeviceParams"
        >
          按设备填入采样率/通道数
        </v-btn>
      </div>

      <div class="form-section">
        <div class="form-section-title">
          <v-icon size="small">mdi-tune</v-icon>
          <span>采样参数</span>
        </div>
        <div v-if="selectedDevice" class="field-hint-block mb-2">
          采样率与通道数由硬件定义，已随绑定设备自动填入，不可修改。
        </div>
        <div class="field-row">
          <div class="field-block">
            <div class="field-caption">采样率 (Hz)</div>
            <v-text-field
              v-model.number="form.params.sampleRate"
              label="采样率 (Hz)"
              type="number"
              density="compact"
              variant="outlined"
              hide-details
              :readonly="isReadOnly || !!selectedDevice"
              :disabled="isReadOnly || !!selectedDevice"
              :hint="selectedDevice ? '由硬件定义' : undefined"
              :persistent-hint="!!selectedDevice"
            />
          </div>
          <div class="field-block">
            <div class="field-caption">通道数</div>
            <v-text-field
              v-model.number="form.params.channels"
              label="通道数"
              type="number"
              density="compact"
              variant="outlined"
              hide-details
              :readonly="isReadOnly || !!selectedDevice"
              :disabled="isReadOnly || !!selectedDevice"
              :hint="selectedDevice ? '由硬件定义' : undefined"
              :persistent-hint="!!selectedDevice"
            />
          </div>
        </div>
      </div>

      <div class="form-section">
        <div class="form-section-title">
          <v-icon size="small">mdi-label-outline</v-icon>
          <span>通道命名</span>
          <div class="form-section-actions">
            <v-btn
              v-if="!isReadOnly && showTenTwentySwitch"
              size="x-small"
              variant="tonal"
              color="teal"
              prepend-icon="mdi-head-dots-horizontal-outline"
              @click="openTenTwentyDialog"
            >
              10-20 电极命名
            </v-btn>
            <v-btn
              v-if="!isReadOnly"
              size="x-small"
              variant="text"
              @click="handleAddChannelName"
            >
              添加通道
            </v-btn>
          </div>
        </div>
        <div class="field-hint-block">按电极位置命名（如 Fp1、C3）能让下游分析更直观</div>
        <div class="channel-grid">
          <div v-for="(name, index) in channelNames" :key="index" class="channel-cell">
            <v-text-field
              :model-value="channelNames[index]"
              :label="`CH${index + 1}`"
              :placeholder="`CH${index + 1}`"
              density="compact"
              variant="outlined"
              hide-details
              :readonly="isReadOnly"
              :disabled="isReadOnly"
              @update:model-value="updateChannelName(index, $event)"
            >
              <template #prepend-inner>
                <span class="channel-index">{{ index + 1 }}</span>
              </template>
              <template v-if="!isReadOnly && channelNames.length > 1" #append-inner>
                <v-btn
                  icon
                  size="x-small"
                  variant="text"
                  color="error"
                  @click="handleRemoveChannelName(index)"
                >
                  <v-icon size="small">mdi-close</v-icon>
                </v-btn>
              </template>
            </v-text-field>
          </div>
        </div>
      </div>

      <TenTwentyChannelDialog
        v-model="tenTwentyDialogOpen"
        :devices="deviceListForDialog"
        :restrict-to-device-id="tenTwentyRestrictDeviceId"
        @confirm="onTenTwentyConfirm"
      />
    </template>

    <!-- ============ 滤波器 ============ -->
    <template v-else-if="nodeType === 'FILTER'">
      <div class="form-section">
        <div class="form-section-title">
          <v-icon size="small">mdi-waveform</v-icon>
          <span>常用预设</span>
        </div>
        <div class="preset-chips">
          <v-chip
            v-for="preset in filterPresets"
            :key="preset.label"
            size="small"
            :color="isPresetActive(preset) ? 'primary' : undefined"
            :variant="isPresetActive(preset) ? 'flat' : 'tonal'"
            :disabled="isReadOnly"
            @click="applyFilterPreset(preset)"
          >
            {{ preset.label }}
          </v-chip>
        </div>
      </div>

      <div class="form-section">
        <div class="form-section-title">
          <v-icon size="small">mdi-tune</v-icon>
          <span>滤波参数</span>
        </div>
        <div class="field-block">
          <div class="field-caption">滤波器类型</div>
          <v-select
            v-model="form.params.filterType"
            :items="[
              { title: '低通 · 保留低频（去高频噪声）', value: 'lowpass' },
              { title: '高通 · 保留高频（去漂移/直流）', value: 'highpass' },
              { title: '带通 · 保留某一频带（提取节律）', value: 'bandpass' },
              { title: '陷波 · 衰减特定频率（去工频干扰）', value: 'notch' }
            ]"
            item-title="title"
            item-value="value"
            label="滤波器类型"
            density="compact"
            variant="outlined"
            hide-details
            :readonly="isReadOnly"
            :disabled="isReadOnly"
          />
        </div>

        <div class="field-block">
          <div class="field-caption">{{ cutoffCaption }}</div>
          <v-text-field
            v-model.number="form.params.cutoffFreq"
            :label="cutoffCaption"
            type="number"
            density="compact"
            variant="outlined"
            :hint="cutoffError || cutoffHint"
            persistent-hint
            :error="!!cutoffError"
            :readonly="isReadOnly"
            :disabled="isReadOnly"
          />
        </div>

        <div class="field-block">
          <div class="field-caption">滤波器阶数</div>
          <v-text-field
            v-model.number="form.params.order"
            label="滤波器阶数"
            type="number"
            density="compact"
            variant="outlined"
            hint="阶数越高衰减越陡峭，但相位失真越大；EEG 常用 2–4 阶"
            persistent-hint
            :readonly="isReadOnly"
            :disabled="isReadOnly"
          />
        </div>
      </div>
    </template>

    <!-- ============ 降采样/升采样 ============ -->
    <template v-else-if="nodeType === 'DOWNSAMPLE' || nodeType === 'UPSAMPLE'">
      <div class="form-section">
        <div class="form-section-title">
          <v-icon size="small">mdi-tune</v-icon>
          <span>{{ nodeType === 'DOWNSAMPLE' ? '降采样设置' : '升采样设置' }}</span>
        </div>
        <div class="field-block">
          <div class="field-caption">设置方式</div>
          <v-select
            v-model="form.params.mode"
            :items="[{ title: '按目标采样率', value: 'targetRate' }, { title: '按倍率', value: 'factor' }]"
            item-title="title"
            item-value="value"
            label="设置方式"
            density="compact"
            variant="outlined"
            hide-details
            :readonly="isReadOnly"
            :disabled="isReadOnly"
          />
        </div>

        <div v-if="form.params.mode === 'targetRate'" class="field-block">
          <div class="field-caption">目标采样率 (Hz)</div>
          <v-text-field
            v-model.number="form.params.targetRate"
            label="目标采样率 (Hz)"
            type="number"
            density="compact"
            variant="outlined"
            :hint="nodeType === 'DOWNSAMPLE' ? '需低于上游采样率' : '需高于上游采样率'"
            persistent-hint
            :readonly="isReadOnly"
            :disabled="isReadOnly"
          />
        </div>
        <div v-else class="field-block">
          <div class="field-caption">倍率</div>
          <v-text-field
            v-model.number="form.params.factor"
            label="倍率"
            type="number"
            density="compact"
            variant="outlined"
            :hint="nodeType === 'DOWNSAMPLE' ? '输出 = 输入 ÷ 倍率（如 2 表示采样率减半）' : '输出 = 输入 × 倍率（如 2 表示采样率翻倍）'"
            persistent-hint
            :readonly="isReadOnly"
            :disabled="isReadOnly"
          />
        </div>
      </div>
    </template>

    <!-- ============ 求和器/平均器 ============ -->
    <template v-else-if="nodeType === 'SUM' || nodeType === 'AVERAGE'">
      <div class="form-section">
        <div class="form-section-title">
          <v-icon size="small">mdi-swap-horizontal</v-icon>
          <span>输入配置</span>
          <div class="form-section-actions">
            <v-btn
              v-if="!isReadOnly"
              size="x-small"
              variant="text"
              @click="handleAddSumInput"
            >
              添加输入
            </v-btn>
          </div>
        </div>
        <div class="field-hint-block">
          {{ nodeType === 'AVERAGE' ? '每个输入端口对应一路信号，按权重逐通道平均' : '每个输入端口对应一路信号，按权重逐通道相加；权重取负值可实现差分（双极导联）' }}
        </div>
        <div class="list-header">
          <span class="list-header-label" style="flex: 2">标签</span>
          <span class="list-header-label" style="flex: 1">权重</span>
          <span v-if="!isReadOnly" class="list-header-action" />
        </div>
        <div v-for="(input, index) in sumInputs" :key="index" class="d-flex align-center mb-1">
          <v-text-field
            :model-value="input.label"
            label="标签"
            :placeholder="`输入${index + 1}`"
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
            :disabled="sumInputs.length <= 1"
            @click="handleRemoveSumInput(index)"
          >
            <v-icon size="small">mdi-close</v-icon>
          </v-btn>
        </div>
      </div>
    </template>

    <!-- ============ 分离器 ============ -->
    <template v-else-if="nodeType === 'SPLIT'">
      <div class="form-section">
        <div class="form-section-title">
          <v-icon size="small">mdi-call-split</v-icon>
          <span>输出配置</span>
          <div class="form-section-actions">
            <v-btn
              v-if="!isReadOnly"
              size="x-small"
              variant="text"
              @click="handleAddSplitOutput"
            >
              添加输出
            </v-btn>
          </div>
        </div>
        <div class="field-hint-block">每个输出端口取走指定通道；通道索引从 0 开始，逗号分隔</div>
        <div v-if="availableChannels.length > 0" class="ref-chips">
          <v-chip
            v-for="(ch, idx) in availableChannels"
            :key="idx"
            size="x-small"
            variant="tonal"
          >
            {{ idx }}: {{ ch }}
          </v-chip>
        </div>
        <div class="list-header">
          <span class="list-header-label" style="flex: 2">输出标签</span>
          <span class="list-header-label" style="flex: 2">通道索引</span>
          <span v-if="!isReadOnly" class="list-header-action" />
        </div>
        <div v-for="(output, index) in splitOutputs" :key="index" class="d-flex align-center mb-1">
          <v-text-field
            :model-value="output.label"
            label="标签"
            placeholder="如: 运动区"
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
            label="通道索引"
            placeholder="如: 0,1,2"
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
            :disabled="splitOutputs.length <= 1"
            @click="handleRemoveSplitOutput(index)"
          >
            <v-icon size="small">mdi-close</v-icon>
          </v-btn>
        </div>
      </div>
    </template>

    <!-- ============ 合并器 ============ -->
    <template v-else-if="nodeType === 'MERGE'">
      <div class="form-section">
        <div class="form-section-title">
          <v-icon size="small">mdi-call-merge</v-icon>
          <span>合并设置</span>
        </div>
        <div class="field-block">
          <div class="field-caption">合并策略</div>
          <v-select
            v-model="form.params.strategy"
            :items="[{ title: '顺序拼接（先 A 后 B）', value: 'concat' }, { title: '交错拼接（A1、B1、A2、B2…）', value: 'interleave' }]"
            item-title="title"
            item-value="value"
            label="合并策略"
            density="compact"
            variant="outlined"
            hide-details
            :readonly="isReadOnly"
            :disabled="isReadOnly"
          />
        </div>

        <div class="form-section-title mt-2">
          <v-icon size="small">mdi-swap-horizontal</v-icon>
          <span>输入配置</span>
          <div class="form-section-actions">
            <v-btn
              v-if="!isReadOnly"
              size="x-small"
              variant="text"
              @click="handleAddMergeInput"
            >
              添加输入
            </v-btn>
          </div>
        </div>
        <div class="list-header">
          <span class="list-header-label" style="flex: 2">标签</span>
          <span class="list-header-label" style="flex: 1">增益</span>
          <span v-if="!isReadOnly" class="list-header-action" />
        </div>
        <div v-for="(input, index) in mergeInputs" :key="index" class="d-flex align-center mb-1">
          <v-text-field
            :model-value="input.label"
            label="标签"
            :placeholder="`输入${index + 1}`"
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
            :disabled="mergeInputs.length <= 1"
            @click="handleRemoveMergeInput(index)"
          >
            <v-icon size="small">mdi-close</v-icon>
          </v-btn>
        </div>
      </div>
    </template>

    <!-- ============ 输出节点（显示与录制） ============ -->
    <template v-else-if="nodeType === 'OUTPUT'">
      <div class="form-section">
        <div class="form-section-title">
          <v-icon size="small">mdi-monitor</v-icon>
          <span>显示</span>
        </div>
        <v-alert
          type="info"
          variant="tonal"
          density="compact"
          class="mb-2"
        >
          在「可视化」页面为示波器/频谱卡片选择该节点作为信号源。
        </v-alert>
        <div class="field-block">
          <div class="field-caption">频谱分析 (FFT 点数)</div>
          <v-select
            v-model="form.params.fftSize"
            :items="[
              { title: '256 点 · 更新快，频率分辨率低', value: 256 },
              { title: '512 点 · 均衡（推荐）', value: 512 },
              { title: '1024 点 · 频率分辨率高', value: 1024 },
              { title: '2048 点 · 分辨率最高，更新慢', value: 2048 }
            ]"
            item-title="title"
            item-value="value"
            label="频谱分析 (FFT 点数)"
            density="compact"
            variant="outlined"
            hint="点数越多，频谱频率轴越精细"
            persistent-hint
            :readonly="isReadOnly"
            :disabled="isReadOnly"
          />
        </div>
      </div>

      <div class="form-section">
        <div class="record-card" :class="{ 'record-card-on': form.params.saveEnabled }">
          <v-switch
            v-model="form.params.saveEnabled"
            label="录制数据到文件"
            density="compact"
            hide-details
            inset
            color="success"
            :readonly="isReadOnly"
            :disabled="isReadOnly"
          />
          <template v-if="form.params.saveEnabled">
            <div class="field-block mt-3">
              <div class="field-caption">文件名</div>
              <v-text-field
                v-model="form.params.filename"
                label="文件名"
                placeholder="留空自动生成"
                density="compact"
                variant="outlined"
                hide-details
                :readonly="isReadOnly"
                :disabled="isReadOnly"
              />
            </div>
            <div class="field-block mb-0">
              <div class="field-caption">文件格式</div>
              <v-select
                v-model="form.params.format"
                :items="[
                  { title: 'CSV · 通用表格，Excel 可读', value: 'CSV' },
                  { title: 'MAT · MATLAB 格式', value: 'MAT' },
                  { title: 'NPY · Python NumPy 格式', value: 'NPY' }
                ]"
                item-title="title"
                item-value="value"
                label="文件格式"
                density="compact"
                variant="outlined"
                hide-details
                :readonly="isReadOnly"
                :disabled="isReadOnly"
              />
            </div>
          </template>
        </div>
      </div>
    </template>

    <!-- ============ Python函数节点 ============ -->
    <template v-else-if="nodeType === 'CUSTOM_PYFUNC'">
      <div class="form-section">
        <div class="form-section-title">
          <v-icon size="small">mdi-swap-horizontal</v-icon>
          <span>端口设置</span>
        </div>
        <div class="field-block">
          <div class="field-caption">端口模式</div>
          <v-select
            v-model="form.params.portMode"
            :items="[{ title: '固定端口数', value: 'fixed' }, { title: '自适应（按输入输出名称自动确定）', value: 'adaptive' }]"
            item-title="title"
            item-value="value"
            label="端口模式"
            density="compact"
            variant="outlined"
            hide-details
            :readonly="isReadOnly"
            :disabled="isReadOnly"
          />
        </div>

        <div v-if="form.params.portMode === 'fixed'" class="field-row">
          <div class="field-block">
            <div class="field-caption">输入端口数</div>
            <v-text-field
              v-model.number="form.params.inputCount"
              label="输入端口数"
              type="number"
              density="compact"
              variant="outlined"
              hide-details
              :readonly="isReadOnly"
              :disabled="isReadOnly"
            />
          </div>
          <div class="field-block">
            <div class="field-caption">输出端口数</div>
            <v-text-field
              v-model.number="form.params.outputCount"
              label="输出端口数"
              type="number"
              density="compact"
              variant="outlined"
              hide-details
              :readonly="isReadOnly"
              :disabled="isReadOnly"
            />
          </div>
        </div>

        <div class="field-block">
          <div class="field-caption">函数名</div>
          <v-text-field
            v-model="form.params.functionName"
            label="函数名"
            density="compact"
            variant="outlined"
            hint="生成代码中的入口函数名"
            persistent-hint
            :readonly="isReadOnly"
            :disabled="isReadOnly"
          />
        </div>
      </div>

      <div class="form-section">
        <div class="form-section-title">
          <v-icon size="small">mdi-clock-outline</v-icon>
          <span>窗口与步进</span>
        </div>
        <div class="field-hint-block">数据按窗口分批送入函数处理；步进决定相邻窗口的间隔</div>
        <div class="field-row">
          <div class="field-block">
            <div class="field-caption">窗口长度单位</div>
            <v-select
              v-model="form.params.windowMode"
              :items="[{ title: '按秒', value: 'seconds' }, { title: '按采样点', value: 'points' }]"
              item-title="title"
              item-value="value"
              label="窗口长度单位"
              density="compact"
              variant="outlined"
              hide-details
              :readonly="isReadOnly"
              :disabled="isReadOnly"
            />
          </div>
          <div class="field-block">
            <div class="field-caption">{{ form.params.windowMode === 'seconds' ? '窗口长度 (秒)' : '窗口长度 (点数)' }}</div>
            <v-text-field
              v-if="form.params.windowMode === 'seconds'"
              v-model.number="form.params.windowSeconds"
              label="窗口长度 (秒)"
              type="number"
              density="compact"
              variant="outlined"
              hide-details
              :readonly="isReadOnly"
              :disabled="isReadOnly"
            />
            <v-text-field
              v-else
              v-model.number="form.params.windowPoints"
              label="窗口长度 (点数)"
              type="number"
              density="compact"
              variant="outlined"
              hide-details
              :readonly="isReadOnly"
              :disabled="isReadOnly"
            />
          </div>
        </div>

        <div class="field-row">
          <div class="field-block">
            <div class="field-caption">步进单位</div>
            <v-select
              v-model="form.params.hopMode"
              :items="[{ title: '按采样点', value: 'points' }, { title: '按毫秒', value: 'ms' }]"
              item-title="title"
              item-value="value"
              label="步进单位"
              density="compact"
              variant="outlined"
              hide-details
              :readonly="isReadOnly"
              :disabled="isReadOnly"
            />
          </div>
          <div class="field-block">
            <div class="field-caption">{{ form.params.hopMode === 'points' ? '步进点数' : '步进时间 (毫秒)' }}</div>
            <v-text-field
              v-if="form.params.hopMode === 'points'"
              v-model.number="form.params.hopPoints"
              label="步进点数"
              type="number"
              density="compact"
              variant="outlined"
              hide-details
              :readonly="isReadOnly"
              :disabled="isReadOnly"
            />
            <v-text-field
              v-else
              v-model.number="form.params.hopMs"
              label="步进时间 (毫秒)"
              type="number"
              density="compact"
              variant="outlined"
              hide-details
              :readonly="isReadOnly"
              :disabled="isReadOnly"
            />
          </div>
        </div>

        <div class="field-block">
          <div class="field-caption">输出采样率 (Hz)</div>
          <v-text-field
            v-model.number="form.params.outputSampleRate"
            label="输出采样率 (Hz)"
            type="number"
            density="compact"
            variant="outlined"
            hint="处理结果的采样率"
            persistent-hint
            :readonly="isReadOnly"
            :disabled="isReadOnly"
          />
        </div>
      </div>

      <div class="form-section">
        <div class="form-section-title">
          <v-icon size="small">mdi-tag-text-outline</v-icon>
          <span>输入输出命名</span>
        </div>
        <div class="field-block">
          <div class="field-caption">输入名称（逗号分隔）</div>
          <v-textarea
            :model-value="inputNamesText"
            label="输入名称"
            placeholder="如: raw, ref"
            rows="2"
            density="compact"
            variant="outlined"
            hide-details
            :readonly="isReadOnly"
            :disabled="isReadOnly"
            @update:model-value="$emit('update:inputNamesText', $event)"
          />
        </div>
        <div class="field-block">
          <div class="field-caption">输出名称（逗号分隔）</div>
          <v-textarea
            :model-value="outputNamesText"
            label="输出名称"
            placeholder="如: envelope"
            rows="2"
            density="compact"
            variant="outlined"
            hide-details
            :readonly="isReadOnly"
            :disabled="isReadOnly"
            @update:model-value="$emit('update:outputNamesText', $event)"
          />
        </div>
      </div>

      <div class="form-section">
        <div class="form-section-title">
          <v-icon size="small">mdi-language-python</v-icon>
          <span>Python 代码</span>
          <div class="form-section-actions">
            <v-btn
              v-if="!isReadOnly"
              size="x-small"
              variant="text"
              @click="handleImportPythonFile"
            >
              导入文件
            </v-btn>
          </div>
        </div>
        <div class="field-block">
          <div class="field-caption">自动生成（只读）：声明 + 参数读取</div>
          <v-textarea
            :model-value="pythonHeaderCode"
            label="自动生成：声明与参数读取"
            rows="4"
            density="compact"
            variant="outlined"
            hide-details
            readonly
          />
        </div>

        <div ref="codeEditorHost" class="code-editor-host" />

        <div class="field-block mt-2">
          <div class="field-caption">自动生成（只读）：输出检查 + return</div>
          <v-textarea
            :model-value="pythonFooterCode"
            label="自动生成：输出检查与返回"
            rows="4"
            density="compact"
            variant="outlined"
            hide-details
            readonly
          />
        </div>
      </div>
    </template>

    <!-- ============ 卷积节点 ============ -->
    <template v-else-if="nodeType === 'CUSTOM_CONV'">
      <div class="form-section">
        <div class="form-section-title">
          <v-icon size="small">mdi-waveform</v-icon>
          <span>卷积核</span>
        </div>
        <div class="preset-chips">
          <v-chip
            v-for="preset in kernelPresets"
            :key="preset.label"
            size="small"
            variant="tonal"
            :disabled="isReadOnly"
            @click="applyKernelPreset(preset)"
          >
            {{ preset.label }}
          </v-chip>
        </div>
        <div class="field-block">
          <div class="field-caption">卷积核（逗号分隔）</div>
          <v-textarea
            :model-value="kernelText"
            label="卷积核"
            placeholder="如: 0.25, 0.5, 0.25"
            rows="2"
            density="compact"
            variant="outlined"
            hint="核在时间上滑动加权平均；平滑核的权重和通常为 1"
            persistent-hint
            :readonly="isReadOnly"
            :disabled="isReadOnly"
            @update:model-value="$emit('update:kernelText', $event)"
          />
        </div>
      </div>

      <div class="form-section">
        <div class="form-section-title">
          <v-icon size="small">mdi-language-python</v-icon>
          <span>Python 代码</span>
          <div class="form-section-actions">
            <v-btn
              v-if="!isReadOnly"
              size="x-small"
              variant="text"
              @click="handleImportPythonFile"
            >
              导入文件
            </v-btn>
          </div>
        </div>
        <div ref="codeEditorHost" class="code-editor-host" />
      </div>
    </template>

    <!-- ============ 文件回放节点 ============ -->
    <template v-else-if="nodeType === 'REPLAY'">
      <div class="form-section">
        <div class="form-section-title">
          <v-icon size="small">mdi-file-music-outline</v-icon>
          <span>回放文件</span>
          <div class="form-section-actions">
            <v-btn
              icon
              size="x-small"
              variant="text"
              :loading="replayFilesLoading"
              title="刷新文件列表"
              @click="fetchReplayFiles"
            >
              <v-icon size="small">mdi-refresh</v-icon>
            </v-btn>
          </div>
        </div>
        <div class="field-block">
          <div class="field-caption">选择 saved_data 中的 CSV 文件</div>
          <v-combobox
            v-model="form.params.filePath"
            :items="replayFiles"
            label="回放文件"
            placeholder="选择或输入文件名"
            density="compact"
            variant="outlined"
            :hint="form.params.filePath ? `将回放: ${form.params.filePath}` : '从已录制文件中选择，或手动输入文件名'"
            persistent-hint
            :readonly="isReadOnly"
            :disabled="isReadOnly"
          />
        </div>
        <v-switch
          v-model="form.params.loop"
          label="循环播放"
          density="compact"
          hide-details
          inset
          color="primary"
          :readonly="isReadOnly"
          :disabled="isReadOnly"
        />
      </div>

      <div class="form-section">
        <div class="form-section-title">
          <v-icon size="small">mdi-tune</v-icon>
          <span>数据参数</span>
        </div>
        <div class="field-row">
          <div class="field-block">
            <div class="field-caption">采样率 (Hz)</div>
            <v-text-field
              v-model.number="form.params.sampleRate"
              label="采样率 (Hz)"
              type="number"
              density="compact"
              variant="outlined"
              hint="录制时的原始采样率"
              persistent-hint
              :readonly="isReadOnly"
              :disabled="isReadOnly"
            />
          </div>
          <div class="field-block">
            <div class="field-caption">通道数</div>
            <v-text-field
              v-model.number="form.params.channels"
              label="通道数"
              type="number"
              density="compact"
              variant="outlined"
              hide-details
              :readonly="isReadOnly"
              :disabled="isReadOnly"
            />
          </div>
        </div>
      </div>
    </template>

    <!-- ============ 其他节点：JSON 参数 ============ -->
    <template v-else>
      <div class="form-section">
        <div class="form-section-title">
          <v-icon size="small">mdi-code-json</v-icon>
          <span>参数 (JSON)</span>
        </div>
        <v-textarea
          :model-value="paramsJson"
          label="参数 (JSON)"
          rows="6"
          density="compact"
          variant="outlined"
          :error="!!jsonError"
          :error-messages="jsonError"
          :readonly="isReadOnly"
          :disabled="isReadOnly"
          @update:model-value="$emit('update:paramsJson', $event)"
        />
      </div>
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
  channelNames: string[];
  sumInputs: any[];
  splitOutputs: any[];
  mergeInputs: any[];
  inputNamesText: string;
  outputNamesText: string;
  kernelText: string;
  paramsJson: string;
  jsonError: string | null;
  availableChannels?: string[];
  pythonHeaderCode?: string;
  pythonFooterCode?: string;
}>();

// 从父组件传递的方法
const emit = defineEmits<{
  (e: 'update:selectedDeviceId', value: string | null): void;
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

/** 每种节点类型的一句话说明（面向神经科学用户） */
const typeDescriptions: Record<string, string> = {
  SOURCE: '从采集设备读取实时脑电信号，是整个流程的起点。',
  REPLAY: '回放之前录制的数据文件，便于离线调试处理流程。',
  FILTER: '按频率筛选信号。常用：0.5Hz 高通去漂移、50Hz 陷波去工频、带通提取脑电节律。',
  DOWNSAMPLE: '降低采样率以减小数据量，让后续处理更快。',
  UPSAMPLE: '通过插值提高采样率。',
  SUM: '将多路输入按权重逐通道相加。',
  AVERAGE: '将多路输入按权重逐通道平均，常用于平均参考。',
  SPLIT: '把输入信号的部分通道拆分到不同输出端口，便于按脑区分别处理。',
  MERGE: '把多路信号合并为一路多通道信号。',
  OUTPUT: '把信号送到示波器/频谱显示，并可同步录制到文件。',
  CUSTOM_PYFUNC: '用 Python 编写自定义处理函数，按窗口处理数据。',
  CUSTOM_CONV: '用自定义卷积核对信号做滑动加权（如平滑）。',
};

const typeDescription = computed(() => typeDescriptions[props.nodeType] || '');

// 计算属性
const availableDevices = computed(() => {
  return sessionStore.getDevices().map(device => ({
    ...device,
    displayName: device.name
      ? `${device.name} · ${device.samplingRate}Hz/${device.channelCount}ch`
      : device.id,
  }));
});

/** 当前选中的设备对象 */
const selectedDevice = computed(() => {
  if (!props.selectedDeviceId) return null;
  return sessionStore.getDevices().find(d => d.id === props.selectedDeviceId) || null;
});

const selectedDeviceHint = computed(() => {
  if (!props.selectedDeviceId) return '选择一个采集设备作为信号来源';
  const d = selectedDevice.value;
  if (!d) return `已绑定: ${props.selectedDeviceId}`;
  return `${d.name || d.id} · 采样率 ${d.samplingRate}Hz · ${d.channelCount} 通道`;
});

/** 按设备参数填入采样率/通道数 */
const applyDeviceParams = () => {
  const d = selectedDevice.value;
  if (!d) return;
  props.form.params.sampleRate = Number(d.samplingRate) || props.form.params.sampleRate;
  props.form.params.channels = Number(d.channelCount) || props.form.params.channels;
};

/** 滤波器预设（后端仅支持单一截止/中心频率） */
interface FilterPreset { label: string; type: string; cutoff: number }
const filterPresets: FilterPreset[] = [
  { label: '去漂移 · 高通 0.5Hz', type: 'highpass', cutoff: 0.5 },
  { label: '平滑 · 低通 30Hz', type: 'lowpass', cutoff: 30 },
  { label: 'δ 波 · 2Hz', type: 'bandpass', cutoff: 2 },
  { label: 'θ 波 · 6Hz', type: 'bandpass', cutoff: 6 },
  { label: 'α 波 · 10Hz', type: 'bandpass', cutoff: 10 },
  { label: 'β 波 · 20Hz', type: 'bandpass', cutoff: 20 },
  { label: 'γ 波 · 35Hz', type: 'bandpass', cutoff: 35 },
  { label: '工频陷波 · 50Hz', type: 'notch', cutoff: 50 },
];

const applyFilterPreset = (preset: FilterPreset) => {
  if (props.isReadOnly) return;
  props.form.params.filterType = preset.type;
  props.form.params.cutoffFreq = preset.cutoff;
};

const isPresetActive = (preset: FilterPreset) => {
  return props.form.params.filterType === preset.type
    && Number(props.form.params.cutoffFreq) === preset.cutoff;
};

const cutoffCaption = computed(() => {
  const t = props.form.params.filterType;
  return (t === 'bandpass' || t === 'notch') ? '中心频率 (Hz)' : '截止频率 (Hz)';
});

const cutoffHint = computed(() => {
  const t = props.form.params.filterType;
  switch (t) {
    case 'highpass': return '保留高于该频率的成分（如 0.5Hz 去除慢漂移）';
    case 'bandpass': return '保留以该频率为中心的频带（如 10Hz 提取 α 节律）';
    case 'notch': return '衰减该频率附近的成分（如 50Hz 工频干扰）';
    default: return '保留低于该频率的成分（如 30Hz 平滑）';
  }
});

/** 奈奎斯特校验：截止频率不可超过上游采样率的一半，否则是无意义的滤波 */
const cutoffError = computed(() => {
  const sr = Number(props.form.upstreamSampleRate || 0);
  const cutoff = Number(props.form.params.cutoffFreq || 0);
  if (sr > 0 && cutoff > 0 && cutoff >= sr / 2) {
    return `截止频率 ${cutoff}Hz 已达到/超过奈奎斯特频率 ${sr / 2}Hz（上游采样率 ${sr}Hz 的一半），滤波无效`;
  }
  return '';
});

/** 卷积核预设 */
interface KernelPreset { label: string; kernel: number[] }
const kernelPresets: KernelPreset[] = [
  { label: '轻度平滑', kernel: [0.25, 0.5, 0.25] },
  { label: '中度平滑', kernel: [0.1, 0.2, 0.4, 0.2, 0.1] },
  { label: '强平滑', kernel: [0.0625, 0.25, 0.375, 0.25, 0.0625] },
];

const applyKernelPreset = (preset: KernelPreset) => {
  if (props.isReadOnly) return;
  emit('update:kernelText', preset.kernel.join(', '));
};

/** 可回放文件列表 */
const replayFiles = ref<string[]>([]);
const replayFilesLoading = ref(false);

async function fetchReplayFiles() {
  replayFilesLoading.value = true;
  try {
    const resp = await fetch('/api/replayable-files/');
    const data = await resp.json();
    if (data?.ok && Array.isArray(data.files)) {
      replayFiles.value = data.files
        .map((f: any) => String(f?.filename || ''))
        .filter(Boolean);
    }
  } catch (err) {
    console.warn('[NodeEditFormContent] Failed to fetch replayable files:', err);
  } finally {
    replayFilesLoading.value = false;
  }
}

watch(() => props.nodeType, (type) => {
  if (type === 'REPLAY') {
    fetchReplayFiles();
  }
}, { immediate: true });

// 10-20标准系统
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

// 只在SOURCE节点显示 10-20 入口
const showTenTwentySwitch = computed(() => {
  return props.nodeType === 'SOURCE';
});

const openTenTwentyDialog = () => {
  fetchDevicesFallback(); // 确保设备列表已加载
  tenTwentyDialogOpen.value = true;
};

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
  tenTwentyDialogOpen.value = false;
};

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

.node-edit-form-content {
  max-height: 70vh;
  overflow-y: auto;
  padding-right: 4px;
}

/* 节点类型说明 */
.node-type-desc {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(var(--v-theme-primary), 0.07);
  color: rgba(var(--v-theme-on-surface), 0.78);
  font-size: 12px;
  line-height: 1.5;
  margin-bottom: 14px;
}

.node-type-desc .desc-icon {
  color: rgb(var(--v-theme-primary));
  margin-top: 1px;
  flex-shrink: 0;
}

/* 表单分区 */
.form-section {
  margin-bottom: 16px;
}

.form-section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: rgba(var(--v-theme-on-surface), 0.85);
  margin-bottom: 6px;
}

.form-section-title .v-icon {
  color: rgb(var(--v-theme-primary));
}

.form-section-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 4px;
}

/* 字段标题（替代被裁切的浮动标签） */
.field-caption {
  font-size: 12px;
  font-weight: 500;
  color: rgba(var(--v-theme-on-surface), 0.65);
  margin-bottom: 2px;
}

.field-block {
  margin-bottom: 10px;
  min-width: 0;
}

.field-row {
  display: flex;
  gap: 8px;
}

.field-row .field-block {
  flex: 1;
}

.field-hint-block {
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.55);
  margin-bottom: 8px;
  line-height: 1.4;
}

/* 隐藏 Vuetify 浮动标签（当前版本渲染被裁切），由 field-caption 取代。
   label 属性仍保留在控件上以保证可访问性与测试定位。 */
.node-edit-form-content :deep(.v-field-label) {
  display: none !important;
}

/* 开关轨道提高不透明度，关态也清晰可辨 */
.node-edit-form-content :deep(.v-switch__track) {
  opacity: 0.9;
}

/* 通道命名网格 */
.channel-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px 8px;
}

.channel-cell {
  min-width: 0;
}

.channel-index {
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.45);
  min-width: 16px;
  text-align: right;
}

/* 预设 chips */
.preset-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

/* 参考通道 chips */
.ref-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 8px;
  max-height: 96px;
  overflow-y: auto;
}

/* 列表表头 */
.list-header {
  display: flex;
  align-items: center;
  margin-bottom: 2px;
}

.list-header-label {
  font-size: 11px;
  font-weight: 500;
  color: rgba(var(--v-theme-on-surface), 0.5);
  margin-right: 8px;
}

.list-header-action {
  width: 28px;
  flex-shrink: 0;
}

/* 录制卡片 */
.record-card {
  border: 1px solid rgba(var(--v-theme-on-surface), 0.14);
  border-radius: 10px;
  padding: 10px 12px;
  transition: border-color 0.2s, background 0.2s;
}

.record-card-on {
  border-color: rgba(var(--v-theme-success), 0.55);
  background: rgba(var(--v-theme-success), 0.05);
}

.code-editor-host {
  min-height: 260px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.14);
  border-radius: 8px;
  overflow: hidden;
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
