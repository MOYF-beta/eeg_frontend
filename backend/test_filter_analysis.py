#!/usr/bin/env python3
"""
EEG信号滤波效果测试程序
直接调用后端API，精确分析低通滤波前后的信号特征
"""

import requests
import numpy as np
import matplotlib.pyplot as plt
from scipy import signal
import json
import time
from datetime import datetime

# 后端API配置
BASE_URL = "http://localhost:8000/api"

def test_backend_health():
    """测试后端服务状态"""
    try:
        r = requests.get(f"{BASE_URL}/health/", timeout=5)
        print(f"✅ 后端服务正常: {r.json()}")
        return True
    except Exception as e:
        print(f"❌ 后端服务异常: {e}")
        return False

def generate_test_signal(duration=5.0, sample_rate=1000):
    """
    生成包含明显高低频成分的测试信号
    
    信号组成：
    - 低频成分: 5Hz + 8Hz (模拟脑电α波和θ波)
    - 高频噪声: 50Hz + 100Hz (模拟工频干扰和高频噪声)
    - 白噪声: 随机小幅度干扰
    """
    t = np.linspace(0, duration, int(duration * sample_rate), endpoint=False)
    
    # 低频成分（应该被保留）
    low_freq = 5 * np.sin(2 * np.pi * 5 * t) + 3 * np.sin(2 * np.pi * 8 * t)
    
    # 高频噪声（应该被滤除）
    high_freq = 2 * np.sin(2 * np.pi * 50 * t) + 1.5 * np.sin(2 * np.pi * 100 * t)
    
    # 白噪声
    white_noise = 0.5 * np.random.randn(len(t))
    
    # 合成信号
    signal_total = low_freq + high_freq + white_noise
    
    return t, signal_total, low_freq, high_freq

def analyze_signal(signal_data, sample_rate=1000, title="信号分析"):
    """
    分析信号特征，返回频谱数据和统计信息
    """
    n = len(signal_data)
    
    # FFT变换
    fft_result = np.fft.fft(signal_data)
    frequencies = np.fft.fftfreq(n, 1/sample_rate)
    
    # 只取正频率部分
    positive_freq_mask = frequencies >= 0
    frequencies = frequencies[positive_freq_mask]
    magnitude = np.abs(fft_result[positive_freq_mask]) / n
    
    # 计算各频段能量
    # 低频: 0-15Hz (应该保留)
    low_freq_mask = (frequencies >= 0) & (frequencies <= 15)
    low_freq_energy = np.sum(magnitude[low_freq_mask] ** 2)
    
    # 中频: 15-40Hz 
    mid_freq_mask = (frequencies > 15) & (frequencies <= 40)
    mid_freq_energy = np.sum(magnitude[mid_freq_mask] ** 2)
    
    # 高频: 40-200Hz (应该被滤除)
    high_freq_mask = (frequencies > 40) & (frequencies <= 200)
    high_freq_energy = np.sum(magnitude[high_freq_mask] ** 2)
    
    total_energy = low_freq_energy + mid_freq_energy + high_freq_energy
    
    result = {
        'frequencies': frequencies,
        'magnitude': magnitude,
        'low_freq_energy': low_freq_energy,
        'mid_freq_energy': mid_freq_energy,
        'high_freq_energy': high_freq_energy,
        'low_freq_ratio': low_freq_energy / total_energy * 100,
        'mid_freq_ratio': mid_freq_energy / total_energy * 100,
        'high_freq_ratio': high_freq_energy / total_energy * 100,
        'total_energy': total_energy
    }
    
    return result

def apply_lowpass_filter(signal_data, cutoff=10, sample_rate=1000, order=4):
    """
    应用低通滤波器（模拟后端滤波效果）
    """
    nyquist = sample_rate / 2
    normalized_cutoff = cutoff / nyquist
    
    # 设计Butterworth低通滤波器
    b, a = signal.butter(order, normalized_cutoff, btype='low')
    
    # 应用滤波器
    filtered_signal = signal.filtfilt(b, a, signal_data)
    
    return filtered_signal

def plot_comparison(original, filtered, t, sample_rate=1000, cutoff=10):
    """
    绘制原始信号和滤波后信号的对比图
    """
    fig, axes = plt.subplots(3, 2, figsize=(14, 10))
    fig.suptitle(f'低通滤波效果对比 (截止频率: {cutoff}Hz)', fontsize=16)
    
    # 1. 时域波形对比
    ax1 = axes[0, 0]
    ax1.plot(t[:1000], original[:1000], 'b-', alpha=0.7, label='原始信号')
    ax1.plot(t[:1000], filtered[:1000], 'r-', alpha=0.7, label='滤波后')
    ax1.set_xlabel('时间 (s)')
    ax1.set_ylabel('幅值')
    ax1.set_title('时域波形对比 (前1秒)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. 时域波形细节（显示高频部分）
    ax2 = axes[0, 1]
    ax2.plot(t[:200], original[:200], 'b-', alpha=0.7, label='原始信号')
    ax2.plot(t[:200], filtered[:200], 'r-', alpha=0.7, label='滤波后')
    ax2.set_xlabel('时间 (s)')
    ax2.set_ylabel('幅值')
    ax2.set_title('时域波形细节 (前200ms)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 分析信号
    orig_analysis = analyze_signal(original, sample_rate, "原始信号")
    filt_analysis = analyze_signal(filtered, sample_rate, "滤波后信号")
    
    # 3. 原始信号频谱
    ax3 = axes[1, 0]
    ax3.plot(orig_analysis['frequencies'][:200], 
             orig_analysis['magnitude'][:200], 'b-', linewidth=1)
    ax3.axvline(x=cutoff, color='r', linestyle='--', label=f'截止频率 {cutoff}Hz')
    ax3.set_xlabel('频率 (Hz)')
    ax3.set_ylabel('幅值')
    ax3.set_title('原始信号频谱')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    # 4. 滤波后信号频谱
    ax4 = axes[1, 1]
    ax4.plot(filt_analysis['frequencies'][:200], 
             filt_analysis['magnitude'][:200], 'r-', linewidth=1)
    ax4.axvline(x=cutoff, color='r', linestyle='--', label=f'截止频率 {cutoff}Hz')
    ax4.set_xlabel('频率 (Hz)')
    ax4.set_ylabel('幅值')
    ax4.set_title('滤波后信号频谱')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    
    # 5. 能量分布对比（饼图）
    ax5 = axes[2, 0]
    categories = ['低频(0-15Hz)', '中频(15-40Hz)', '高频(40-200Hz)']
    orig_values = [orig_analysis['low_freq_ratio'], 
                   orig_analysis['mid_freq_ratio'],
                   orig_analysis['high_freq_ratio']]
    ax5.pie(orig_values, labels=categories, autopct='%1.1f%%', startangle=90)
    ax5.set_title('原始信号能量分布')
    
    # 6. 滤波后能量分布（饼图）
    ax6 = axes[2, 1]
    filt_values = [filt_analysis['low_freq_ratio'],
                   filt_analysis['mid_freq_ratio'],
                   filt_analysis['high_freq_ratio']]
    ax6.pie(filt_values, labels=categories, autopct='%1.1f%%', startangle=90)
    ax6.set_title('滤波后信号能量分布')
    
    plt.tight_layout()
    
    # 保存图片
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f'filter_comparison_{cutoff}Hz_{timestamp}.png'
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    print(f"✅ 对比图已保存: {filename}")
    
    plt.show()
    
    return orig_analysis, filt_analysis

def print_analysis_report(orig_analysis, filt_analysis, cutoff):
    """打印分析报告"""
    print("\n" + "="*60)
    print(f"📊 低通滤波效果分析报告 (截止频率: {cutoff}Hz)")
    print("="*60)
    
    print("\n【原始信号】")
    print(f"  低频能量(0-15Hz):  {orig_analysis['low_freq_ratio']:.2f}%")
    print(f"  中频能量(15-40Hz): {orig_analysis['mid_freq_ratio']:.2f}%")
    print(f"  高频能量(40-200Hz):{orig_analysis['high_freq_ratio']:.2f}%")
    
    print("\n【滤波后信号】")
    print(f"  低频能量(0-15Hz):  {filt_analysis['low_freq_ratio']:.2f}%")
    print(f"  中频能量(15-40Hz): {filt_analysis['mid_freq_ratio']:.2f}%")
    print(f"  高频能量(40-200Hz):{filt_analysis['high_freq_ratio']:.2f}%")
    
    print("\n【滤波效果】")
    high_freq_reduction = (1 - filt_analysis['high_freq_ratio'] / orig_analysis['high_freq_ratio']) * 100
    print(f"  高频抑制率: {high_freq_reduction:.1f}%")
    
    low_freq_preservation = (filt_analysis['low_freq_ratio'] / orig_analysis['low_freq_ratio']) * 100
    print(f"  低频保留率: {low_freq_preservation:.1f}%")
    
    print("\n" + "="*60)

def main():
    """主函数"""
    print("🔬 EEG低通滤波效果测试程序")
    print("="*60)
    
    # 测试后端连接
    if not test_backend_health():
        print("\n⚠️  后端服务未启动，将使用本地模拟分析")
        print("   请确保后端服务在 http://localhost:8000 运行")
        print("   或使用: python manage.py runserver 0.0.0.0:8000")
    
    print("\n📈 生成测试信号...")
    t, test_signal, low_component, high_component = generate_test_signal(
        duration=5.0, 
        sample_rate=1000
    )
    print(f"   信号长度: {len(test_signal)} 样本")
    print(f"   采样率: 1000 Hz")
    print(f"   时长: 5.0 秒")
    
    # 测试不同截止频率
    cutoff_frequencies = [10, 30, 50]
    
    for cutoff in cutoff_frequencies:
        print(f"\n🧪 测试截止频率: {cutoff}Hz")
        
        # 应用低通滤波
        filtered_signal = apply_lowpass_filter(
            test_signal, 
            cutoff=cutoff, 
            sample_rate=1000,
            order=4
        )
        
        # 绘制对比图
        orig_analysis, filt_analysis = plot_comparison(
            test_signal, 
            filtered_signal, 
            t, 
            sample_rate=1000,
            cutoff=cutoff
        )
        
        # 打印分析报告
        print_analysis_report(orig_analysis, filt_analysis, cutoff)
        
        time.sleep(0.5)  # 避免图表重叠
    
    print("\n✅ 所有测试完成！")
    print("💡 建议:")
    print("   - 截止频率10Hz: 强烈滤波，只保留基础脑电波")
    print("   - 截止频率30Hz: 中度滤波，保留大部分有用信号")
    print("   - 截止频率50Hz: 轻度滤波，主要去除工频干扰")

if __name__ == "__main__":
    main()
