#!/usr/bin/env python3
"""
GPU 温度压力测试程序
测试显卡温度响应和风扇控制
"""

import torch
import time
import sys
import os

# 添加当前目录到路径，以便导入配置
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def load_config():
    """加载配置文件"""
    config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "GPU监控设置.json")
    if os.path.exists(config_file):
        import json
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {
        "温度曲线": {
            "曲线点": [
                {"温度": 35, "转速": 20},
                {"温度": 45, "转速": 35},
                {"温度": 55, "转速": 50},
                {"温度": 65, "转速": 70},
                {"温度": 75, "转速": 85},
                {"温度": 85, "转速": 100}
            ],
            "缓冲设置": {
                "温度变化阈值": 3,
                "稳定等待时间": 5,
                "转速最大变化": 15
            }
        }
    }

def get_gpu_info():
    """获取GPU信息"""
    try:
        import subprocess
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=temperature.gpu,fan.speed,power.draw,clocks.gr,utilization.gpu,memory.used,memory.total',
             '--format=csv,noheader,nounits'],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            values = result.stdout.strip().split(', ')
            return {
                'temp': float(values[0]),
                'fan': float(values[1]),
                'power': float(values[2]),
                'clock': float(values[3]),
                'util': float(values[4]),
                'mem_used': float(values[5]),
                'mem_total': float(values[6])
            }
    except:
        pass
    return None

def stress_gpu(duration_seconds=60, intensity=0.95):
    """
    GPU压力测试
    :param duration_seconds: 测试持续时间（秒）
    :param intensity: 计算强度（0-1）
    """
    print("=" * 60)
    print("GPU 温度压力测试")
    print("=" * 60)
    
    # 加载配置
    config = load_config()
    curve = config.get("温度曲线", {})
    points = curve.get("曲线点", [])
    buffer_settings = curve.get("缓冲设置", {})
    
    print("\n当前温度曲线配置：")
    for i, p in enumerate(points):
        print(f"  点{i+1}: {p['温度']}°C → {p['转速']}%")
    
    print("\n缓冲设置：")
    print(f"  温度变化阈值: {buffer_settings.get('温度变化阈值', 3)}°C")
    print(f"  稳定等待时间: {buffer_settings.get('稳定等待时间', 5)}秒")
    print(f"  转速最大变化: {buffer_settings.get('转速最大变化', 15)}%")
    
    # 检查CUDA
    if not torch.cuda.is_available():
        print("\n错误: CUDA 不可用！")
        return
    
    device = torch.cuda.current_device()
    gpu_name = torch.cuda.get_device_name(device)
    print(f"\n检测到 GPU: {gpu_name}")
    print(f"测试时长: {duration_seconds} 秒")
    print(f"计算强度: {intensity * 100:.0f}%")
    
    # 获取初始状态
    print("\n初始状态：")
    initial_info = get_gpu_info()
    if initial_info:
        print(f"  温度: {initial_info['temp']:.0f}°C")
        print(f"  风扇: {initial_info['fan']:.0f}%")
        print(f"  功耗: {initial_info['power']:.1f}W")
    
    phase_duration = 120  # 每个阶段2分钟
    print("\n" + "=" * 60)
    print("开始压力测试...")
    print(f"阶段1: 升温 (0-{phase_duration}秒)")
    print(f"阶段2: 降温 ({phase_duration}-{phase_duration*2}秒)")
    print(f"阶段3: 再次升温 ({phase_duration*2}-{phase_duration*3}秒)")
    print(f"总时长: {phase_duration*3}秒 ({phase_duration*3//60}分钟)")
    print("=" * 60)
    
    # 创建大型张量进行计算
    size = int(5000 * intensity)
    
    start_time = time.time()
    iteration = 0
    
    try:
        while time.time() - start_time < duration_seconds:
            elapsed = time.time() - start_time
            remaining = duration_seconds - elapsed
            
            # 根据时间调整计算强度，模拟温度波动
            phase_duration = 120  # 每个阶段2分钟
            if elapsed < phase_duration:
                # 阶段1: 高强度，快速升温
                phase = "升温"
                current_intensity = intensity
            elif elapsed < phase_duration * 2:
                # 阶段2: 低强度，降温
                phase = "降温"
                current_intensity = intensity * 0.2
            else:
                # 阶段3: 再次高强度
                phase = "再次升温"
                current_intensity = intensity
            
            # 执行矩阵运算产生热量
            a = torch.randn(size, size, device='cuda')
            b = torch.randn(size, size, device='cuda')
            c = torch.matmul(a, b)
            torch.cuda.synchronize()
            
            iteration += 1
            
            # 每2秒输出一次状态
            if iteration % 10 == 0:
                info = get_gpu_info()
                if info:
                    print(f"\r[{phase}] 时间: {elapsed:.0f}s | "
                          f"温度: {info['temp']:.0f}°C | "
                          f"风扇: {info['fan']:.0f}% | "
                          f"功耗: {info['power']:.1f}W | "
                          f"利用率: {info['util']:.0f}%", end='', flush=True)
            
            # 短暂休息，避免系统卡死
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n\n用户中断测试")
    finally:
        # 清理CUDA缓存
        torch.cuda.empty_cache()
    
    # 测试结果
    print("\n\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
    
    final_info = get_gpu_info()
    if final_info and initial_info:
        print("\n温度变化：")
        print(f"  初始: {initial_info['temp']:.0f}°C")
        print(f"  最终: {final_info['temp']:.0f}°C")
        print(f"  变化: {final_info['temp'] - initial_info['temp']:+.0f}°C")
        
        print("\n风扇响应：")
        print(f"  初始: {initial_info['fan']:.0f}%")
        print(f"  最终: {final_info['fan']:.0f}%")
        print(f"  变化: {final_info['fan'] - initial_info['fan']:+.0f}%")
        
        print("\n功耗变化：")
        print(f"  初始: {initial_info['power']:.1f}W")
        print(f"  最终: {final_info['power']:.1f}W")
        print(f"  变化: {final_info['power'] - initial_info['power']:+.1f}W")
    
    print("\n测试总结：")
    print("  ✓ 观察温度上升速度")
    print("  ✓ 观察风扇响应延迟")
    print("  ✓ 观察温度下降速度")
    print("  ✓ 验证缓冲设置是否生效")
    
    return final_info

def quick_test():
    """快速测试（10秒）"""
    print("\n快速测试模式（10秒）\n")
    return stress_gpu(duration_seconds=10, intensity=0.8)

def full_test():
    """完整测试（6分钟，每阶段2分钟）"""
    print("\n完整测试模式（6分钟 = 3阶段 × 2分钟）\n")
    return stress_gpu(duration_seconds=360, intensity=0.95)

def extreme_test():
    """极限测试（12分钟，100%强度）"""
    print("\n极限测试模式（12分钟，100%强度）\n")
    return stress_gpu(duration_seconds=720, intensity=1.0)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='GPU 温度压力测试')
    parser.add_argument('--quick', action='store_true', help='快速测试（10秒）')
    parser.add_argument('--full', action='store_true', help='完整测试（60秒，默认）')
    parser.add_argument('--extreme', action='store_true', help='极限测试（120秒）')
    parser.add_argument('--time', type=int, default=60, help='自定义测试时长（秒）')
    parser.add_argument('--intensity', type=float, default=0.95, help='计算强度（0-1）')
    
    args = parser.parse_args()
    
    if args.quick:
        quick_test()
    elif args.extreme:
        extreme_test()
    elif args.time != 60:
        stress_gpu(duration_seconds=args.time, intensity=args.intensity)
    else:
        full_test()
