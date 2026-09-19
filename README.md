# GPU 监控 + 风扇控制

NVIDIA GPU 桌面悬浮监控小工具，支持风扇曲线控制、CPU 温度监控、AI 模型监控、麦克风音量锁定。

## 功能一览

| 功能 | 说明 |
|------|------|
| GPU 监控 | 温度 / 风扇转速 / 利用率 / 功耗 / 频率 / 显存 |
| CPU 监控 | 利用率 + 温度（需 LibreHardwareMonitor 或 Core Temp） |
| 风扇控制 | 自动/手动切换，温度曲线（线性插值 + 防抖缓冲） |
| AI 监控 | LM Studio / Ollama 模型运行状态 |
| 网速显示 | 实时上传/下载速度 |
| 麦克风锁定 | 防止 Windows 自动降低麦克风音量 |
| 多主题 | 深蓝 / 暗灰 / 黑色，可调透明度 |
| 悬浮窗 | 可拖拽，可折叠/展开，始终置顶 |

## 系统要求

- **操作系统**: Windows 10/11（64位）
- **显卡**: NVIDIA GPU（风扇控制需要）
- **权限**: 需要管理员权限（风扇控制需要）
- **Python**: 3.9+

## 安装步骤

### 1. 安装 Python

如未安装 Python，从 [python.org](https://www.python.org/downloads/) 下载 3.9+ 版本，安装时勾选 **Add Python to PATH**。

### 2. 安装依赖

打开命令行（CMD 或 PowerShell），进入项目目录：

```bash
cd 你的路径\cpugpu
pip install -r requirements.txt
```

### 3. 运行

**方式一：命令行运行**
```bash
python main.py
```
程序会自动请求管理员权限。

**方式二：双击启动**
双击 `GPU启动.vbs`，会以后台方式启动（无命令行窗口）。

## CPU 温度说明

CPU 温度监控有两条路径，**无需额外安装软件**也能工作：

| 路径 | 需要安装 | 说明 |
|------|---------|------|
| LibreHardwareMonitor（内置） | ❌ 不需要 | 通过 pip 已安装，自动读取 |
| Core Temp（备选） | ✅ 需安装 | 安装 [Core Temp](https://www.alcpu.com/CoreTemp/) 并运行 |

程序会自动选择：优先用 LibreHardwareMonitor，如果失败则尝试 Core Temp 共享内存。

## 麦克风锁定说明

- 点击面板底部的 🎤 按钮开启/关闭
- 开启后每 2 秒检查一次，如果音量被 Windows 自动降低了就强制恢复到 100%
- 适合使用语音输入法的用户

## 项目结构

```
cpugpu/
├── main.py                    # 程序入口
├── requirements.txt           # 依赖列表
├── GPU启动.vbs                # VBS 后台启动脚本
├── GPU监控设置.json            # 配置文件（运行后自动生成）
│
├── core/                      # 核心模块
│   ├── hw_monitor.py          # 统一硬件监控（LibreHardwareMonitor，带缓存）
│   ├── nvml_controller.py     # NVML 单例（风扇控制专用）
│   ├── cpu_monitor.py         # CPU 温度备用方案（Core Temp 共享内存）
│   ├── config.py              # 配置管理（JSON 读写 + 深度合并）
│   ├── ai_monitor.py          # AI 服务监控（LM Studio / Ollama）
│   └── mic_locker.py          # 麦克风音量锁定
│
├── panel/                     # UI 模块
│   ├── gpu_panel.py           # 主面板（数据采集 + UI 刷新）
│   └── settings.py            # 设置对话框
│
├── themes/                    # 主题
│   └── themes.py              # 配色方案 + QSS 模板
│
├── logs/                      # 日志目录（运行后自动生成）
│
└── gpu_stress_test.py         # GPU 压力测试（独立工具）
```

## 性能参考

i5-12400F + 32GB 环境下实测：

| 指标 | 数值 |
|------|------|
| CPU 平均占用 | ~1.3%（6核12线程） |
| 内存占用 | ~87MB（其中 ~60MB 为 .NET 运行时） |
| UI 刷新延迟 | 0ms（后台线程采集 + 缓存） |

## 移植说明

将整个 `cpugpu` 文件夹复制到目标机器，然后：

1. 安装 Python 3.9+
2. `pip install -r requirements.txt`
3. `python main.py` 运行

配置文件 `GPU监控设置.json` 会在首次运行时自动生成，无需手动创建。

## 常见问题

**Q: 风扇控制不生效？**
A: 需要以管理员权限运行。程序会自动请求提权，如果被拒绝则风扇控制不可用。

**Q: CPU 温度显示 "--°C"？**
A: 确认 `PyLibreHardwareMonitor` 已正确安装（`pip install PyLibreHardwareMonitor`）。如果仍不行，可安装 Core Temp 作为备选。

**Q: 程序启动后看不到窗口？**
A: 窗口是悬浮置顶的，可能被其他全屏窗口遮挡。检查任务栏是否有程序图标。

**Q: 拖动窗口卡顿？**
A: 已优化为后台线程采集 + 缓存机制，UI 主线程零阻塞。如仍有问题，可在设置中将更新频率调大（如 3~5 秒）。
