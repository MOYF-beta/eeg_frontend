"""graph_nodes 内置节点 compute 逻辑单元测试。

直接构造输入 Signal 调用各节点 compute()，验证数据变换正确性。
此前 9 种节点（FILTER/DOWNSAMPLE/UPSAMPLE/SUM/AVERAGE/SPLIT/MERGE/PASSTHROUGH）
在 pytest 层零覆盖，仅经 e2e 间接验证。

运行：
    pytest backend/eeg_app/tests/test_graph_nodes_compute.py -v
"""
import math

import pytest

from eeg_app.graph_nodes.base import NodeExecutionContext
from eeg_app.graph_nodes.filter_node import FilterNode
from eeg_app.graph_nodes.downsample_node import DownsampleNode
from eeg_app.graph_nodes.upsample_node import UpsampleNode
from eeg_app.graph_nodes.sum_node import SumNode
from eeg_app.graph_nodes.average_node import AverageNode
from eeg_app.graph_nodes.split_node import SplitNode
from eeg_app.graph_nodes.merge_node import MergeNode
from eeg_app.graph_nodes.passthrough_node import PassthroughNode


def make_ctx(sample_rate: int = 250, state: dict | None = None) -> NodeExecutionContext:
    return NodeExecutionContext(node_state=state if state is not None else {}, sample_rate=sample_rate, wall_time_ms=0)


def sig(channels, names=None, rate=250.0, utc=1000):
    return {
        'channels': list(channels),
        'channelNames': list(names) if names else [f'CH{i + 1}' for i in range(len(channels))],
        'utcFirstFrameMs': utc,
        'sampleRate': rate,
    }


def rms(values):
    return math.sqrt(sum(v * v for v in values) / len(values)) if values else 0.0


# ═══════════════════════════════════════════════════════════════ #
#  FILTER
# ═══════════════════════════════════════════════════════════════ #

class TestFilterNode:
    def _run_filter(self, samples, ftype, cutoff, order=2, rate=250):
        """逐样本驱动滤波器，返回输出序列。"""
        node = FilterNode()
        ctx = make_ctx(rate)
        n = {'params': {'type': ftype, 'cutoff': cutoff, 'order': order}}
        out = []
        for x in samples:
            res = node.compute(n, {'in': [sig([x], rate=rate)]}, ctx)
            out.append(res['out']['channels'][0])
        return out

    def test_lowpass_attenuates_high_frequency(self):
        """低通 5Hz 应大幅衰减 50Hz 高频正弦。"""
        rate = 250
        n_samples = 500
        samples = [math.sin(2 * math.pi * 50 * i / rate) for i in range(n_samples)]
        out = self._run_filter(samples, 'lowpass', cutoff=5, order=2, rate=rate)
        # 稳态段（跳过暂态）RMS 必须远小于输入
        assert rms(out[250:]) < rms(samples[250:]) * 0.3

    def test_lowpass_preserves_low_frequency(self):
        """低通 50Hz 应基本保留 5Hz 低频正弦。"""
        rate = 250
        n_samples = 1000
        samples = [math.sin(2 * math.pi * 5 * i / rate) for i in range(n_samples)]
        out = self._run_filter(samples, 'lowpass', cutoff=50, order=2, rate=rate)
        # 5Hz 远低于截止，稳态幅值应保留 >70%
        assert rms(out[500:]) > rms(samples[500:]) * 0.7

    def test_highpass_attenuates_low_frequency(self):
        """高通 30Hz 应衰减 5Hz 低频。"""
        rate = 250
        samples = [math.sin(2 * math.pi * 5 * i / rate) for i in range(500)]
        out = self._run_filter(samples, 'highpass', cutoff=30, order=2, rate=rate)
        assert rms(out[250:]) < rms(samples[250:]) * 0.3

    def test_filter_is_stateful_across_calls(self):
        """同一 context（node_state）连续调用应携带滤波器记忆，输出不是逐样本独立。"""
        node = FilterNode()
        ctx = make_ctx(250)
        n = {'params': {'type': 'lowpass', 'cutoff': 5, 'order': 2}}
        # 先灌入一段零信号建立状态
        for _ in range(20):
            node.compute(n, {'in': [sig([0.0])]}, ctx)
        # 状态字典应被填充滤波器系数与延迟单元
        assert ctx.node_state.get('_coeff_key')
        assert ctx.node_state.get('_num_sections', 0) >= 1

    def test_empty_channels_returns_input(self):
        node = FilterNode()
        res = node.compute({'params': {'type': 'lowpass', 'cutoff': 5}}, {'in': [sig([])]}, make_ctx())
        assert res['out']['channels'] == []


# ═══════════════════════════════════════════════════════════════ #
#  DOWNSAMPLE
# ═══════════════════════════════════════════════════════════════ #

class TestDownsampleNode:
    def test_factor_emits_every_nth(self):
        """factor=5 时 25 个输入只应产出 5 个非空输出。"""
        node = DownsampleNode()
        ctx = make_ctx(250)
        n = {'params': {'mode': 'factor', 'factor': 5}}
        emitted = 0
        for i in range(25):
            res = node.compute(n, {'in': [sig([float(i)])]}, ctx)
            if res['out']['channels']:
                emitted += 1
        assert emitted == 5

    def test_factor_sets_output_sample_rate(self):
        """factor=5 @250Hz 输出 sampleRate 应为 50。"""
        node = DownsampleNode()
        ctx = make_ctx(250)
        n = {'params': {'mode': 'factor', 'factor': 5}}
        res = node.compute(n, {'in': [sig([1.0], rate=250.0)]}, ctx)
        assert res['out']['sampleRate'] == pytest.approx(50.0)

    def test_target_rate_computes_factor(self):
        """targetRate=50 @250Hz → factor=5，25 输入产 5 输出。"""
        node = DownsampleNode()
        ctx = make_ctx(250)
        n = {'params': {'mode': 'targetRate', 'targetRate': 50}}
        emitted = sum(
            1 for i in range(25)
            if node.compute(n, {'in': [sig([float(i)])]}, ctx)['out']['channels']
        )
        assert emitted == 5

    def test_factor_one_passes_all(self):
        """factor=1 每个输入都透传。"""
        node = DownsampleNode()
        ctx = make_ctx(250)
        n = {'params': {'mode': 'factor', 'factor': 1}}
        for i in range(5):
            res = node.compute(n, {'in': [sig([float(i)])]}, ctx)
            assert res['out']['channels'] == [float(i)]


# ═══════════════════════════════════════════════════════════════ #
#  UPSAMPLE
# ═══════════════════════════════════════════════════════════════ #

class TestUpsampleNode:
    def test_factor_sets_output_sample_rate(self):
        node = UpsampleNode()
        n = {'params': {'mode': 'factor', 'factor': 2}}
        res = node.compute(n, {'in': [sig([1.0, 2.0], rate=250.0)]}, make_ctx())
        assert res['out']['sampleRate'] == pytest.approx(500.0)

    def test_empty_input_repeats_last_frame(self):
        """空输入时重复上一帧（零阶保持），实现升采样。"""
        node = UpsampleNode()
        ctx = make_ctx(250)
        n = {'params': {'mode': 'factor', 'factor': 2}}
        node.compute(n, {'in': [sig([3.0, 4.0])]}, ctx)
        # 空输入应重复 [3,4]
        res = node.compute(n, {'in': [sig([])]}, ctx)
        assert res['out']['channels'] == [3.0, 4.0]

    def test_empty_input_without_history_returns_empty(self):
        node = UpsampleNode()
        res = node.compute({'params': {'mode': 'factor', 'factor': 2}}, {'in': [sig([])]}, make_ctx())
        assert res['out']['channels'] == []


# ═══════════════════════════════════════════════════════════════ #
#  SUM / AVERAGE
# ═══════════════════════════════════════════════════════════════ #

class TestSumNode:
    def test_two_sources_sum_channels(self):
        node = SumNode()
        inputs = {'in-1': [sig([1.0, 2.0])], 'in-2': [sig([10.0, 20.0])]}
        res = node.compute({'params': {}}, inputs, make_ctx())
        assert res['out']['channels'] == [11.0, 22.0]

    def test_weight_applied(self):
        node = SumNode()
        params = {'inputs': [{'weight': 2.0}, {'weight': 1.0}]}
        inputs = {'in-1': [sig([1.0])], 'in-2': [sig([10.0])]}
        res = node.compute({'params': params}, inputs, make_ctx())
        assert res['out']['channels'] == [12.0]

    def test_mismatched_channel_count_zero_padded(self):
        """通道数不一致时按最大通道数对齐，缺通道按 0。"""
        node = SumNode()
        inputs = {'in-1': [sig([1.0, 2.0, 3.0])], 'in-2': [sig([10.0])]}
        res = node.compute({'params': {}}, inputs, make_ctx())
        assert res['out']['channels'] == [11.0, 2.0, 3.0]

    def test_no_inputs_returns_empty(self):
        node = SumNode()
        res = node.compute({'params': {}}, {}, make_ctx())
        assert res['out']['channels'] == []


class TestAverageNode:
    def test_two_sources_averaged(self):
        node = AverageNode()
        inputs = {'in-1': [sig([1.0, 2.0])], 'in-2': [sig([3.0, 4.0])]}
        res = node.compute({'params': {}}, inputs, make_ctx())
        assert res['out']['channels'] == [2.0, 3.0]

    def test_single_source_unchanged(self):
        """单输入时（count=1 不除以数量）输出等于输入。"""
        node = AverageNode()
        res = node.compute({'params': {}}, {'in-1': [sig([5.0, 6.0])]}, make_ctx())
        assert res['out']['channels'] == [5.0, 6.0]

    def test_average_leq_max_source(self):
        """平均值 RMS 不应超过最大源 RMS。"""
        node = AverageNode()
        inputs = {'in-1': [sig([100.0, 100.0])], 'in-2': [sig([10.0, 10.0])]}
        res = node.compute({'params': {}}, inputs, make_ctx())
        assert res['out']['channels'][0] == pytest.approx(55.0)


# ═══════════════════════════════════════════════════════════════ #
#  SPLIT
# ═══════════════════════════════════════════════════════════════ #

class TestSplitNode:
    def test_split_by_channel_indices(self):
        """按 channelIndices 拆分通道到不同输出端口。"""
        node = SplitNode()
        params = {'outputs': [
            {'label': 'lo', 'channelIndices': '0,1'},
            {'label': 'hi', 'channelIndices': '2,3'},
        ]}
        res = node.compute({'params': params}, {'in': [sig([1.0, 2.0, 3.0, 4.0])]}, make_ctx())
        assert res['out-1']['channels'] == [1.0, 2.0]
        assert res['out-2']['channels'] == [3.0, 4.0]

    def test_out_of_range_indices_skip_port(self):
        """索引全越界的端口不产生输出。"""
        node = SplitNode()
        params = {'outputs': [{'label': 'bad', 'channelIndices': '5,6,7'}]}
        res = node.compute({'params': params}, {'in': [sig([1.0, 2.0])]}, make_ctx())
        assert 'out-1' not in res

    def test_default_all_channels(self):
        """无 outputs 配置时默认透传全部通道到 out-1。"""
        node = SplitNode()
        res = node.compute({'params': {}}, {'in': [sig([1.0, 2.0, 3.0])]}, make_ctx())
        assert res['out-1']['channels'] == [1.0, 2.0, 3.0]

    def test_label_applied_to_single_channel(self):
        node = SplitNode()
        params = {'outputs': [{'label': 'Fp1', 'channelIndices': '0'}]}
        res = node.compute({'params': params}, {'in': [sig([9.0, 8.0])]}, make_ctx())
        assert res['out-1']['channelNames'] == ['Fp1']


# ═══════════════════════════════════════════════════════════════ #
#  MERGE
# ═══════════════════════════════════════════════════════════════ #

class TestMergeNode:
    def test_concat_strategy(self):
        """concat（默认）拼接所有输入通道。"""
        node = MergeNode()
        inputs = {'in-1': [sig([1.0, 2.0])], 'in-2': [sig([3.0, 4.0, 5.0, 6.0])]}
        res = node.compute({'params': {'strategy': 'concat'}}, inputs, make_ctx())
        assert res['out']['channels'] == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]

    def test_interleave_strategy(self):
        """interleave 按通道序号交错：CH1_in1, CH1_in2, CH2_in1, CH2_in2。"""
        node = MergeNode()
        inputs = {'in-1': [sig([1.0, 2.0])], 'in-2': [sig([10.0, 20.0])]}
        res = node.compute({'params': {'strategy': 'interleave'}}, inputs, make_ctx())
        assert res['out']['channels'] == [1.0, 10.0, 2.0, 20.0]

    def test_gain_applied(self):
        node = MergeNode()
        params = {'strategy': 'concat', 'inputs': [{'gain': 2.0}, {'gain': 1.0}]}
        inputs = {'in-1': [sig([1.0])], 'in-2': [sig([5.0])]}
        res = node.compute({'params': params}, inputs, make_ctx())
        assert res['out']['channels'] == [2.0, 5.0]

    def test_channel_count_is_sum_of_inputs(self):
        """MERGE 输出通道数 = 输入通道数之和（2+4=6）。"""
        node = MergeNode()
        inputs = {'in-1': [sig([1.0, 2.0])], 'in-2': [sig([1.0, 2.0, 3.0, 4.0])]}
        res = node.compute({'params': {}}, inputs, make_ctx())
        assert len(res['out']['channels']) == 6


# ═══════════════════════════════════════════════════════════════ #
#  PASSTHROUGH
# ═══════════════════════════════════════════════════════════════ #

class TestPassthroughNode:
    def test_identity(self):
        """输入原样透传到 out。"""
        node = PassthroughNode()
        src = sig([1.0, 2.0, 3.0], names=['A', 'B', 'C'], utc=1234)
        res = node.compute({'params': {}}, {'in': [src]}, make_ctx())
        assert res['out']['channels'] == [1.0, 2.0, 3.0]
        assert res['out']['channelNames'] == ['A', 'B', 'C']
        assert res['out']['utcFirstFrameMs'] == 1234
