"""
GPU 监控主面板
保持原有界面风格，增加 CPU 温度和麦克风锁定功能
"""

import sys
import os
import time
import ctypes
import logging
import threading
import psutil

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.nvml_controller import NVMLController
from core.config import ConfigManager
from core.ai_monitor import AIMonitor
from core.hw_monitor import HWMonitor
from core.cpu_monitor import CPUMonitor
from core.mic_locker import MicLocker
from themes.themes import THEMES, QSS_TEMPLATES

logger = logging.getLogger(__name__)


def is_admin():
    """检查管理员权限"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


class GPUPanel(QWidget):
    def __init__(self, config_manager=None):
        super().__init__()
        self.fan_mode = "auto"
        self.config_mgr = config_manager or ConfigManager()
        self.config = self.config_mgr.config

        # 核心模块
        self.nvml = NVMLController()   # 风扇控制专用
        self.hw = HWMonitor()           # 硬件信息读取（优先）
        self.ai_monitor = AIMonitor()
        self.cpu_monitor = CPUMonitor() # CPU 温度备用
        self.mic_locker = MicLocker()

        # 温度曲线变量
        self.temp_history = []
        self.last_fan_speed = None
        self.last_temp_change_time = 0
        self.stable_temp = 0

        # 网速
        self.last_net_stats = psutil.net_io_counters()
        self.last_net_time = time.time()

        # AI 状态
        self.lmstudio_running = False

        # 当前主题
        self.current_theme = THEMES.get(self.config.get("主题色", "深蓝"), THEMES["深蓝"])

        self.initUI()
        self.apply_config()

        # GPU 信息刷新定时器
        self.timer = QTimer()
        self.timer.timeout.connect(self._on_timer_tick)
        self.timer.start(self.config.get("更新频率", 2) * 1000)

        # 后台数据采集线程
        self._data_lock = threading.Lock()
        self._latest_data = None       # 后台采集的最新数据
        self._data_ready = False       # 是否有新数据待更新

        # LM Studio 监控定时器
        self.lmstudio_timer = QTimer()
        self.lmstudio_timer.timeout.connect(self.update_lmstudio_info)

        # 服务检测定时器（30秒）
        self.service_check_timer = QTimer()
        self.service_check_timer.timeout.connect(self.check_ai_services)
        self.service_check_timer.start(30000)

        # 麦克风锁定定时器（2秒）
        self.mic_timer = QTimer()
        self.mic_timer.timeout.connect(self._mic_tick)
        if self.config.get("锁定麦克风", False) and self.mic_locker.available:
            self.mic_locker.enabled = True
            self.mic_timer.start(2000)

        # 管理员权限警告
        if not is_admin():
            QTimer.singleShot(3000, self.show_admin_warning)

    def show_admin_warning(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("权限提示")
        msg.setText("风扇控制需要管理员权限！\n请以管理员身份运行本程序。")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()

    def initUI(self):
        self.setWindowTitle("GPU监控+风扇控制")
        self.is_expanded = False
        self.collapsed_height = 180
        self.expanded_height = 360
        self.setFixedSize(300, self.collapsed_height)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 主框架
        main_frame = QFrame()
        self.main_frame = main_frame
        main_frame.setStyleSheet(QSS_TEMPLATES["main_frame"].format(
            bg_color=self.current_theme['bg_color'].format(240),
            border_color=self.current_theme['border_color']
        ))

        layout = QVBoxLayout(main_frame)
        layout.setSpacing(6)
        layout.setContentsMargins(12, 8, 12, 12)

        # === 标题栏 ===
        title_bar = QWidget()
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(0, 0, 0, 0)

        self.network_label = QLabel("↑0KB ↓0KB")
        self.network_label.setStyleSheet(
            f"color: {self.current_theme['title_color']}; font-weight: bold; font-size: 12px; letter-spacing: 0.5px;"
        )

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["标准", "风扇监控", "简洁", "────────", "设置"])
        self.mode_combo.setFixedWidth(70)
        self.mode_combo.setStyleSheet(QSS_TEMPLATES["mode_combo"])
        self.mode_combo.currentTextChanged.connect(self.on_mode_changed)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(22, 22)
        close_btn.setStyleSheet(QSS_TEMPLATES["close_btn"])
        close_btn.clicked.connect(self.close)

        self.toggle_btn = QPushButton("▼")
        self.toggle_btn.setFixedSize(24, 22)
        self.toggle_btn.setStyleSheet(QSS_TEMPLATES["toggle_btn"])
        self.toggle_btn.clicked.connect(self.toggle_expand)

        title_layout.addWidget(self.network_label)
        title_layout.addStretch()
        title_layout.addWidget(self.toggle_btn)
        title_layout.addWidget(self.mode_combo)
        title_layout.addWidget(close_btn)

        layout.addWidget(title_bar)

        # === 信息区域 ===
        self.info_widgets = {}

        # 温度行
        temp_row = QWidget()
        temp_layout = QHBoxLayout(temp_row)
        temp_layout.setContentsMargins(0, 0, 0, 0)

        temp_label = QLabel("🌡️ 温度")
        temp_label.setStyleSheet(f"color: {self.current_theme['label_color']}; font-size: 12px;")
        temp_label.setFixedWidth(40)

        self.temp_bar = QProgressBar()
        self.temp_bar.setFixedHeight(10)
        self.temp_bar.setTextVisible(False)
        self.temp_bar.setStyleSheet(QSS_TEMPLATES["progress_bar"].format(color=self.current_theme['temp_color']))

        self.temp_value = QLabel("0°C")
        self.temp_value.setStyleSheet(f"color: {self.current_theme['temp_color']}; font-size: 13px; font-weight: bold;")
        self.temp_value.setFixedWidth(45)
        self.temp_value.setAlignment(Qt.AlignCenter)

        temp_layout.addWidget(temp_label)
        temp_layout.addWidget(self.temp_bar)
        temp_layout.addWidget(self.temp_value)
        layout.addWidget(temp_row)

        # 风扇行
        fan_row = QWidget()
        fan_layout = QHBoxLayout(fan_row)
        fan_layout.setContentsMargins(0, 0, 0, 0)

        fan_label = QLabel("🌬️ 风扇")
        fan_label.setStyleSheet(f"color: {self.current_theme['label_color']}; font-size: 12px;")
        fan_label.setFixedWidth(40)

        self.fan_bar = QProgressBar()
        self.fan_bar.setFixedHeight(10)
        self.fan_bar.setTextVisible(False)
        self.fan_bar.setStyleSheet(QSS_TEMPLATES["progress_bar_gradient"].format(color=self.current_theme['fan_color']))

        self.fan_value = QLabel("0%")
        self.fan_value.setStyleSheet(f"color: {self.current_theme['fan_color']}; font-size: 12px; font-weight: bold;")
        self.fan_value.setFixedWidth(40)
        self.fan_value.setAlignment(Qt.AlignCenter)

        fan_layout.addWidget(fan_label)
        fan_layout.addWidget(self.fan_bar)
        fan_layout.addWidget(self.fan_value)
        layout.addWidget(fan_row)

        # === 可折叠区域 ===
        self.expandable_widget = QWidget()
        expandable_layout = QVBoxLayout(self.expandable_widget)
        expandable_layout.setSpacing(6)
        expandable_layout.setContentsMargins(0, 0, 0, 0)

        # 利用率
        self.info_widgets['util'] = self.create_info_row("利用率", "0%", self.current_theme['util_color'])
        expandable_layout.addWidget(self.info_widgets['util']['widget'])

        # 功耗
        self.info_widgets['power'] = self.create_info_row("功耗", "0W", self.current_theme['power_color'])
        expandable_layout.addWidget(self.info_widgets['power']['widget'])

        # 频率
        self.info_widgets['clock'] = self.create_info_row("频率", "0MHz", self.current_theme['clock_color'])
        expandable_layout.addWidget(self.info_widgets['clock']['widget'])

        # 显存
        self.info_widgets['memory'] = self.create_info_row("显存", "0/0MB", self.current_theme['memory_color'])
        expandable_layout.addWidget(self.info_widgets['memory']['widget'])

        # CPU 行（利用率+温度合并）
        cpu_widget = QWidget()
        cpu_layout = QHBoxLayout(cpu_widget)
        cpu_layout.setContentsMargins(0, 0, 0, 0)
        cpu_layout.setSpacing(8)

        cpu_lbl_container = QWidget()
        cpu_lbl_container.setStyleSheet(QSS_TEMPLATES["label_container"])
        cpu_lbl_layout = QHBoxLayout(cpu_lbl_container)
        cpu_lbl_layout.setContentsMargins(6, 2, 6, 2)
        cpu_lbl_layout.setSpacing(0)
        cpu_label = QLabel("CPU")
        cpu_label.setStyleSheet(f"color: {self.current_theme['label_color']}; font-size: 12px;")
        cpu_lbl_layout.addWidget(cpu_label)
        cpu_lbl_container.setFixedWidth(55)

        self.cpu_bar = QProgressBar()
        self.cpu_bar.setFixedHeight(10)
        self.cpu_bar.setTextVisible(False)
        self.cpu_bar.setStyleSheet(QSS_TEMPLATES["progress_bar_gradient"].format(color=self.current_theme['cpu_color']))

        cpu_val_container = QWidget()
        cpu_val_container.setStyleSheet(QSS_TEMPLATES["label_container"])
        cpu_val_layout = QHBoxLayout(cpu_val_container)
        cpu_val_layout.setContentsMargins(4, 2, 4, 2)
        cpu_val_layout.setSpacing(0)
        self.cpu_value = QLabel("0%")
        self.cpu_value.setStyleSheet(f"color: {self.current_theme['cpu_color']}; font-size: 12px; font-weight: bold;")
        self.cpu_value.setAlignment(Qt.AlignCenter)
        cpu_val_layout.addWidget(self.cpu_value)
        cpu_val_container.setFixedWidth(55)

        cpu_layout.addWidget(cpu_lbl_container)
        cpu_layout.addWidget(self.cpu_bar)
        cpu_layout.addWidget(cpu_val_container)
        expandable_layout.addWidget(cpu_widget)

        # CPU 温度行（新增）
        self.cpu_temp_row = QWidget()
        cpu_temp_layout = QHBoxLayout(self.cpu_temp_row)
        cpu_temp_layout.setContentsMargins(0, 0, 0, 0)
        cpu_temp_layout.setSpacing(8)

        cpu_temp_lbl_container = QWidget()
        cpu_temp_lbl_container.setStyleSheet(QSS_TEMPLATES["label_container"])
        cpu_temp_lbl_l = QHBoxLayout(cpu_temp_lbl_container)
        cpu_temp_lbl_l.setContentsMargins(6, 2, 6, 2)
        cpu_temp_lbl_l.setSpacing(0)
        cpu_temp_label = QLabel("CPU℃")
        cpu_temp_label.setStyleSheet(f"color: {self.current_theme['label_color']}; font-size: 12px;")
        cpu_temp_lbl_l.addWidget(cpu_temp_label)
        cpu_temp_lbl_container.setFixedWidth(55)

        self.cpu_temp_bar = QProgressBar()
        self.cpu_temp_bar.setFixedHeight(10)
        self.cpu_temp_bar.setTextVisible(False)
        self.cpu_temp_bar.setStyleSheet(QSS_TEMPLATES["progress_bar"].format(color=self.current_theme['cpu_temp_color']))

        cpu_temp_val_container = QWidget()
        cpu_temp_val_container.setStyleSheet(QSS_TEMPLATES["label_container"])
        cpu_temp_val_l = QHBoxLayout(cpu_temp_val_container)
        cpu_temp_val_l.setContentsMargins(4, 2, 4, 2)
        cpu_temp_val_l.setSpacing(0)
        self.cpu_temp_value = QLabel("--°C")
        self.cpu_temp_value.setStyleSheet(f"color: {self.current_theme['cpu_temp_color']}; font-size: 12px; font-weight: bold;")
        self.cpu_temp_value.setAlignment(Qt.AlignCenter)
        cpu_temp_val_l.addWidget(self.cpu_temp_value)
        cpu_temp_val_container.setFixedWidth(55)

        cpu_temp_layout.addWidget(cpu_temp_lbl_container)
        cpu_temp_layout.addWidget(self.cpu_temp_bar)
        cpu_temp_layout.addWidget(cpu_temp_val_container)
        expandable_layout.addWidget(self.cpu_temp_row)

        # 根据 CPU 温度是否可用决定显示
        if not self.cpu_monitor.available and not self.hw.get_cpu_temp():
            self.cpu_temp_row.setVisible(False)

        # === AI 模型监控区域 ===
        self.ai_separator = QFrame()
        self.ai_separator.setFrameShape(QFrame.HLine)
        self.ai_separator.setStyleSheet("color: #4a5568;")
        self.ai_separator.setFixedHeight(2)
        expandable_layout.addWidget(self.ai_separator)

        self.ai_container = QWidget()
        self.ai_grid = QGridLayout(self.ai_container)
        self.ai_grid.setSpacing(4)
        self.ai_grid.setContentsMargins(0, 0, 0, 0)
        for i in range(5):
            self.ai_grid.setColumnStretch(i, 0)
        self.ai_grid.setHorizontalSpacing(8)
        expandable_layout.addWidget(self.ai_container)

        self.ai_model_widgets = []

        # 默认隐藏可折叠区域
        self.expandable_widget.setVisible(False)
        layout.addWidget(self.expandable_widget)

        # === 风扇控制滑块 ===
        control_widget = QWidget()
        control_layout = QHBoxLayout(control_widget)
        control_layout.setContentsMargins(0, 4, 0, 4)
        control_layout.setSpacing(8)

        self.fan_mode_btn = QPushButton("自动")
        self.fan_mode_btn.setFixedSize(34, 20)
        self.fan_mode_btn.setStyleSheet(QSS_TEMPLATES["auto_btn"].format(**self.current_theme))
        self.fan_mode_btn.clicked.connect(self.toggle_fan_mode)

        self.fan_slider = QSlider(Qt.Horizontal)
        self.fan_slider.setRange(0, 100)
        self.fan_slider.setValue(50)
        self.fan_slider.setEnabled(False)
        self.fan_slider.setStyleSheet(QSS_TEMPLATES["slider"].format(**self.current_theme))
        self.fan_slider.valueChanged.connect(self.on_slider_change)

        self.slider_value = QLabel("50%")
        self.slider_value.setStyleSheet(f"color: {self.current_theme['slider_color']}; font-size: 12px; font-weight: bold;")
        self.slider_value.setFixedWidth(40)
        self.slider_value.setAlignment(Qt.AlignCenter)

        # 麦克风锁定指示器
        self.mic_indicator = QPushButton("🎤")
        self.mic_indicator.setFixedSize(24, 20)
        self.mic_indicator.setToolTip("麦克风锁定：关闭")
        self.mic_indicator.setStyleSheet("""
            QPushButton {
                background: #4a5568;
                color: #718096;
                border: none;
                border-radius: 3px;
                font-size: 11px;
            }
        """)
        self.mic_indicator.clicked.connect(self.toggle_mic_lock)

        control_layout.addWidget(self.fan_mode_btn)
        control_layout.addWidget(self.fan_slider)
        control_layout.addWidget(self.slider_value)
        control_layout.addWidget(self.mic_indicator)

        layout.addWidget(control_widget)

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.addWidget(main_frame)

        # 拖动
        self.drag_pos = None
        title_bar.mousePressEvent = self.mousePressEvent
        title_bar.mouseMoveEvent = self.mouseMoveEvent

        # 初始更新（后台采集，下1个定时器周期刷新 UI）
        threading.Thread(target=self._collect_data, daemon=True).start()

    def create_info_row(self, label, default_value, color):
        widget = QWidget()
        row_layout = QHBoxLayout(widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        lbl_container = QWidget()
        lbl_container.setStyleSheet(QSS_TEMPLATES["label_container"])
        lbl_l = QHBoxLayout(lbl_container)
        lbl_l.setContentsMargins(6, 2, 6, 2)
        lbl_l.setSpacing(0)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {self.current_theme['label_color']}; font-size: 13px;")
        lbl_l.addWidget(lbl)
        lbl_container.setFixedWidth(55)

        bar = QProgressBar()
        bar.setFixedHeight(10)
        bar.setTextVisible(False)
        bar.setStyleSheet(QSS_TEMPLATES["progress_bar"].format(color=color))

        val_container = QWidget()
        val_container.setStyleSheet(QSS_TEMPLATES["label_container"])
        val_l = QHBoxLayout(val_container)
        val_l.setContentsMargins(4, 2, 4, 2)
        val_l.setSpacing(0)
        value = QLabel(default_value)
        value.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: bold;")
        value.setAlignment(Qt.AlignCenter)
        val_l.addWidget(value)
        val_container.setFixedWidth(55)

        row_layout.addWidget(lbl_container)
        row_layout.addWidget(bar)
        row_layout.addWidget(val_container)

        return {'widget': widget, 'bar': bar, 'value': value, 'label': lbl}

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_pos:
            self.move(event.globalPos() - self.drag_pos)

    def toggle_expand(self):
        self.is_expanded = not self.is_expanded
        if self.is_expanded:
            self.setFixedSize(300, self.expanded_height)
            self.expandable_widget.setVisible(True)
            self.toggle_btn.setText("▲")
        else:
            self.setFixedSize(300, self.collapsed_height)
            self.expandable_widget.setVisible(False)
            self.toggle_btn.setText("▼")

    def toggle_fan_mode(self):
        if self.fan_mode == "auto":
            self.fan_mode = "manual"
            self.fan_mode_btn.setText("手动")
            self.fan_mode_btn.setStyleSheet(QSS_TEMPLATES["manual_btn"].format(**self.current_theme))
            self.fan_slider.setEnabled(True)
            self.set_fan_speed(self.fan_slider.value())
        else:
            self.fan_mode = "auto"
            self.fan_mode_btn.setText("自动")
            self.fan_mode_btn.setStyleSheet(QSS_TEMPLATES["auto_btn"].format(**self.current_theme))
            self.fan_slider.setEnabled(False)
            self.nvml.set_auto_fan()

    def _mic_tick(self):
        """麦克风定时检查：锁定音量 + 更新图标状态"""
        self.mic_locker.check_and_lock()
        # 根据实际可用性更新图标
        if self.mic_locker.enabled:
            if self.mic_locker.available:
                self.mic_indicator.setStyleSheet("""
                    QPushButton {
                        background: #48bb78;
                        color: #1a202c;
                        border: none;
                        border-radius: 3px;
                        font-size: 11px;
                    }
                """)
                self.mic_indicator.setToolTip("麦克风锁定：开启")
            else:
                self.mic_indicator.setStyleSheet("""
                    QPushButton {
                        background: #e53e3e;
                        color: #fff;
                        border: none;
                        border-radius: 3px;
                        font-size: 11px;
                    }
                """)
                self.mic_indicator.setToolTip("麦克风锁定：设备异常（等待恢复）")

    def toggle_mic_lock(self):
        """切换麦克风锁定"""
        if not self.mic_locker.available:
            # 尝试重新初始化（设备可能刚恢复）
            self.mic_locker._init_audio()
            if not self.mic_locker.available:
                self.mic_indicator.setToolTip("麦克风锁定：设备不可用（驱动异常？）")
                return

        new_state = not self.mic_locker.enabled
        self.mic_locker.enabled = new_state
        self.config["锁定麦克风"] = new_state
        self.config_mgr.save()

        if new_state:
            self.mic_timer.start(2000)
            self.mic_indicator.setStyleSheet("""
                QPushButton {
                    background: #48bb78;
                    color: #1a202c;
                    border: none;
                    border-radius: 3px;
                    font-size: 11px;
                }
            """)
            self.mic_indicator.setToolTip("麦克风锁定：开启")
        else:
            self.mic_timer.stop()
            self.mic_indicator.setStyleSheet("""
                QPushButton {
                    background: #4a5568;
                    color: #718096;
                    border: none;
                    border-radius: 3px;
                    font-size: 11px;
                }
            """)
            self.mic_indicator.setToolTip("麦克风锁定：关闭")

    def on_slider_change(self, value):
        self.slider_value.setText(f"{value}%")
        if self.fan_mode == "manual":
            self.set_fan_speed(value)

    def on_mode_changed(self, text):
        if text == "设置":
            self.open_settings()
            self.mode_combo.setCurrentIndex(0)
        elif text != "────────":
            # 切换模式时立即触发采集
            threading.Thread(target=self._collect_data, daemon=True).start()

    def set_fan_speed(self, speed):
        self.nvml.set_fan_speed(speed)

    def get_smoothed_temp(self, current_temp):
        self.temp_history.append(current_temp)
        if len(self.temp_history) > 5:
            self.temp_history.pop(0)
        return sum(self.temp_history) / len(self.temp_history)

    def calculate_fan_speed_from_curve(self, temp):
        curve = self.config.get("温度曲线", {})
        if not curve.get("启用", False):
            return None
        points = curve.get("曲线点", [])
        if not points:
            return None
        points = sorted(points, key=lambda x: x["温度"])
        for i in range(len(points) - 1):
            p1, p2 = points[i], points[i + 1]
            if p1["温度"] <= temp <= p2["温度"]:
                if p2["温度"] == p1["温度"]:
                    return p1["转速"]
                ratio = (temp - p1["温度"]) / (p2["温度"] - p1["温度"])
                return int(p1["转速"] + ratio * (p2["转速"] - p1["转速"]))
        if temp < points[0]["温度"]:
            return points[0]["转速"]
        return points[-1]["转速"]

    def should_update_fan_speed(self, current_temp, target_speed):
        curve = self.config.get("温度曲线", {})
        buffer_settings = curve.get("缓冲设置", {
            "温度变化阈值": 3, "稳定等待时间": 5, "转速最大变化": 15
        })
        temp_threshold = buffer_settings.get("温度变化阈值", 3)
        wait_time = buffer_settings.get("稳定等待时间", 5)
        max_change = buffer_settings.get("转速最大变化", 15)

        if abs(current_temp - self.stable_temp) < temp_threshold:
            return False
        current_time = time.time()
        if current_time - self.last_temp_change_time < wait_time:
            return False
        if self.last_fan_speed is not None:
            if abs(target_speed - self.last_fan_speed) > max_change:
                if target_speed > self.last_fan_speed:
                    target_speed = min(100, self.last_fan_speed + max_change)
                else:
                    target_speed = max(0, self.last_fan_speed - max_change)

        self.stable_temp = current_temp
        self.last_temp_change_time = current_time
        self.last_fan_speed = target_speed
        return True

    def _on_timer_tick(self):
        """定时器回调：启动后台采集 + 刷新 UI（如有新数据）"""
        # 在后台线程采集数据
        threading.Thread(target=self._collect_data, daemon=True).start()
        # 如果有已准备好的数据，刷新 UI
        if self._data_ready:
            with self._data_lock:
                data = self._latest_data
                self._data_ready = False
            if data:
                self._apply_data_to_ui(data)

    def _collect_data(self):
        """后台线程：采集所有硬件数据（不阻塞 UI）"""
        try:
            # 先让 HWMonitor 刷新缓存
            self.hw.refresh()

            # GPU 信息
            info = self.hw.get_gpu_info()
            if info is None:
                info = self.nvml.get_gpu_info()

            # CPU 利用率
            cpu_percent = self.hw.get_cpu_load()
            if cpu_percent is None:
                cpu_percent = psutil.cpu_percent()

            # CPU 温度
            cpu_temp = self.hw.get_cpu_temp()
            if cpu_temp is None:
                cpu_temp = self.cpu_monitor.get_cpu_temp()

            # 网速
            net_info = self._collect_network_speed()

            data = {
                'info': info,
                'cpu_percent': cpu_percent,
                'cpu_temp': cpu_temp,
                'net': net_info,
            }

            with self._data_lock:
                self._latest_data = data
                self._data_ready = True

        except Exception as e:
            logger.error(f"后台采集数据错误: {e}")

    def _collect_network_speed(self):
        """采集网速数据"""
        try:
            current_stats = psutil.net_io_counters()
            current_time = time.time()
            time_diff = current_time - self.last_net_time
            if time_diff < 0.5:
                return None

            upload_speed = (current_stats.bytes_sent - self.last_net_stats.bytes_sent) / time_diff
            download_speed = (current_stats.bytes_recv - self.last_net_stats.bytes_recv) / time_diff

            self.last_net_stats = current_stats
            self.last_net_time = current_time

            return (upload_speed, download_speed)
        except Exception:
            return None

    def _apply_data_to_ui(self, data):
        """将采集的数据应用到 UI（在主线程调用）"""
        info = data.get('info')
        cpu_percent = data.get('cpu_percent')
        cpu_temp = data.get('cpu_temp')
        net_info = data.get('net')

        if not info:
            return

        mode = self.mode_combo.currentText()
        try:
            temp_val = int(float(info['temp']))
            fan_val = int(float(info['fan']))
            util_val = int(float(info['util']))
            power_val = float(info['power'])
            clock_val = int(float(info['clock']))
            mem_used = float(info['mem_used'])
            mem_total = float(info['mem_total'])
            mem_percent = (mem_used / mem_total) * 100 if mem_total > 0 else 0

            # 温度曲线控制（风扇控制不变，通过 NVML）
            if self.fan_mode == "auto":
                curve = self.config.get("温度曲线", {})
                if curve.get("启用", False):
                    smoothed_temp = self.get_smoothed_temp(temp_val)
                    target_speed = self.calculate_fan_speed_from_curve(smoothed_temp)
                    if target_speed is not None and self.should_update_fan_speed(smoothed_temp, target_speed):
                        self.set_fan_speed(self.last_fan_speed)

            # 温度
            self.temp_bar.setMaximum(100)
            self.temp_bar.setValue(temp_val)
            self.temp_value.setText(f"{temp_val}°C")

            # 风扇
            self.fan_bar.setMaximum(100)
            self.fan_bar.setValue(fan_val)
            self.fan_value.setText(f"{fan_val}%")

            # 模式显示
            if mode == "标准":
                self.update_row('util', util_val, f"{util_val}%", 100)
                self.update_row('power', int(power_val * 2), f"{power_val:.1f}W", 100)
                self.update_row('clock', int(clock_val / 10), f"{clock_val}MHz", 100)
                self.update_row('memory', int(mem_percent), f"{mem_percent:.0f}%", 100)
            elif mode == "风扇监控":
                self.update_row('util', util_val, f"{util_val}%", 100)
                self.update_row('power', 0, "", 0, hide=True)
                self.update_row('clock', 0, "", 0, hide=True)
                self.update_row('memory', 0, "", 0, hide=True)
            elif mode == "简洁":
                self.update_row('util', 0, "", 0, hide=True)
                self.update_row('power', 0, "", 0, hide=True)
                self.update_row('clock', 0, "", 0, hide=True)
                self.update_row('memory', 0, "", 0, hide=True)

            # CPU 利用率
            self.cpu_bar.setValue(int(cpu_percent))
            self.cpu_value.setText(f"{cpu_percent:.0f}%")

            # CPU 温度
            if cpu_temp is not None:
                self.cpu_temp_row.setVisible(True)
                self.cpu_temp_bar.setValue(min(cpu_temp, 100))
                self.cpu_temp_value.setText(f"{cpu_temp}°C")
            else:
                self.cpu_temp_value.setText("--°C")

            # 网速
            if net_info:
                upload_speed, download_speed = net_info
                upload_str = self._format_speed(upload_speed)
                download_str = self._format_speed(download_speed)
                self.network_label.setText(f"↑{upload_str} ↓{download_str}")

        except Exception as e:
            logger.error(f"更新 UI 错误: {e}")

    def update_row(self, key, bar_value, text_value, max_value, hide=False):
        if key in self.info_widgets:
            w = self.info_widgets[key]
            if hide:
                w['widget'].hide()
            else:
                w['widget'].show()
                w['bar'].setMaximum(max_value)
                w['bar'].setValue(min(bar_value, max_value))
                w['value'].setText(text_value)

    def update_network_speed(self):
        """保留兼容接口，实际由后台线程处理"""
        pass

    @staticmethod
    def _format_speed(speed):
        if speed >= 1024 * 1024:
            return f"{speed / (1024 * 1024):.1f}MB"
        elif speed >= 1024:
            return f"{speed / 1024:.0f}KB"
        return f"{speed:.0f}B"

    def check_ai_services(self):
        lmstudio_running = self.ai_monitor.check_lmstudio()
        if lmstudio_running != self.lmstudio_running:
            self.lmstudio_running = lmstudio_running
            if lmstudio_running:
                self.lmstudio_timer.start(3000)
            else:
                self.lmstudio_timer.stop()
                self.hide_ai_section()

    def update_lmstudio_info(self):
        models = self.ai_monitor.get_lmstudio_models()
        if not models:
            self.lmstudio_timer.stop()
            self.lmstudio_running = False
            self.hide_ai_section()
            return
        self.update_ai_display(models)

    def update_ai_display(self, models):
        if not models:
            self.hide_ai_section()
            return

        self.ai_separator.setVisible(True)
        self.ai_container.setVisible(True)

        # 清理旧行
        for w_info in self.ai_model_widgets:
            for key in ['name', 'size', 'gpu', 'context', 'until']:
                if key in w_info:
                    w_info[key].deleteLater()
        self.ai_model_widgets = []

        for row_idx, model in enumerate(models):
            source = model.get('source', 'LM Studio')
            model_color = "#a78bfa" if source == 'Ollama' else "#fbbf24"

            name_label = QLabel(model['name'][:10])
            name_label.setStyleSheet(f"color: {model_color}; font-size: 10px; font-weight: bold;")
            name_label.setFixedWidth(70)
            self.ai_grid.addWidget(name_label, row_idx, 0)

            import re
            size_num = re.findall(r'\d+', model['size'])[0] if re.findall(r'\d+', model['size']) else '-'
            size_label = QLabel(size_num)
            size_label.setStyleSheet(f"color: {self.current_theme['label_color']}; font-size: 11px;")
            size_label.setFixedWidth(22)
            self.ai_grid.addWidget(size_label, row_idx, 1)

            gpu_text = model['processor']
            percents = re.findall(r'(\d+)%', gpu_text)
            if len(percents) >= 2:
                gpu_cpu_text = f"{percents[0]}%{percents[1]}%"
            elif len(percents) == 1:
                gpu_cpu_text = f"{percents[0]}%"
            else:
                gpu_cpu_text = gpu_text
            gpu_label = QLabel(gpu_cpu_text)
            gpu_label.setStyleSheet(f"color: {self.current_theme['label_color']}; font-size: 11px;")
            gpu_label.setFixedWidth(44)
            self.ai_grid.addWidget(gpu_label, row_idx, 2)

            context_label = QLabel(model['context'])
            context_label.setStyleSheet(f"color: {self.current_theme['label_color']}; font-size: 11px;")
            context_label.setFixedWidth(40)
            self.ai_grid.addWidget(context_label, row_idx, 3)

            until_text = AIMonitor.simplify_until(model['until'])
            until_label = QLabel(until_text)
            until_label.setStyleSheet(f"color: {self.current_theme['label_color']}; font-size: 11px;")
            until_label.setFixedWidth(32)
            self.ai_grid.addWidget(until_label, row_idx, 4)

            self.ai_model_widgets.append({
                'name': name_label, 'size': size_label,
                'gpu': gpu_label, 'context': context_label, 'until': until_label
            })

        self.adjust_expanded_height()

    def hide_ai_section(self):
        self.ai_separator.setVisible(False)
        self.ai_container.setVisible(False)
        self.adjust_expanded_height()

    def adjust_expanded_height(self):
        # 使用缓存的 CPU 温度状态，避免重复跨 .NET 桥接读取
        has_cpu_temp = self.cpu_monitor.available or self.hw.available
        base_height = 360 if has_cpu_temp else 340
        if self.ai_container.isVisible():
            extra = len(self.ai_model_widgets) * 20
            self.expanded_height = base_height + extra
        else:
            self.expanded_height = base_height
        if self.is_expanded:
            self.setFixedSize(300, self.expanded_height)

    def open_settings(self):
        from panel.settings import SettingsDialog
        dialog = SettingsDialog(self)
        dialog.exec_()

    def apply_config(self):
        opacity = self.config.get("透明度", 240)
        self.update_opacity(opacity)
        self.apply_theme()
        if not self.config.get("默认折叠", True):
            self.is_expanded = True
            self.setFixedSize(300, self.expanded_height)
            self.expandable_widget.setVisible(True)
            self.toggle_btn.setText("▲")

    def update_opacity(self, opacity):
        self.current_opacity = opacity
        self.apply_theme()

    def apply_theme(self):
        theme_name = self.config.get("主题色", "深蓝")
        theme = THEMES.get(theme_name, THEMES["深蓝"])
        opacity = getattr(self, 'current_opacity', self.config.get("透明度", 240))
        self.current_theme = theme

        # 主框架
        self.main_frame.setStyleSheet(QSS_TEMPLATES["main_frame"].format(
            bg_color=theme['bg_color'].format(opacity),
            border_color=theme['border_color']
        ))

        # 标题
        self.network_label.setStyleSheet(f"color: {theme['title_color']}; font-weight: bold; font-size: 12px; letter-spacing: 0.5px;")

        # 进度条
        self.temp_bar.setStyleSheet(QSS_TEMPLATES["progress_bar"].format(color=theme['temp_color']))
        self.fan_bar.setStyleSheet(QSS_TEMPLATES["progress_bar_gradient"].format(color=theme['fan_color']))
        self.cpu_bar.setStyleSheet(QSS_TEMPLATES["progress_bar_gradient"].format(color=theme['cpu_color']))
        self.cpu_temp_bar.setStyleSheet(QSS_TEMPLATES["progress_bar"].format(color=theme['cpu_temp_color']))

        # 数值颜色
        self.temp_value.setStyleSheet(f"color: {theme['temp_color']}; font-size: 12px; font-weight: bold;")
        self.fan_value.setStyleSheet(f"color: {theme['fan_color']}; font-size: 12px; font-weight: bold;")
        self.cpu_value.setStyleSheet(f"color: {theme['cpu_color']}; font-size: 12px; font-weight: bold;")
        self.cpu_temp_value.setStyleSheet(f"color: {theme['cpu_temp_color']}; font-size: 12px; font-weight: bold;")
        self.slider_value.setStyleSheet(f"color: {theme['slider_color']}; font-size: 12px; font-weight: bold;")

        # 信息行
        for key, color_key in [('util', 'util_color'), ('power', 'power_color'), ('clock', 'clock_color'), ('memory', 'memory_color')]:
            if key in self.info_widgets:
                w = self.info_widgets[key]
                w['bar'].setStyleSheet(QSS_TEMPLATES["progress_bar"].format(color=theme[color_key]))
                w['value'].setStyleSheet(f"color: {theme[color_key]}; font-size: 12px; font-weight: bold;")

        # 标签颜色
        for child in self.findChildren(QLabel):
            text = child.text()
            if text in ["🌡️ 温度", "🌬️ 风扇"]:
                child.setStyleSheet(f"color: {theme['label_color']}; font-size: 12px;")
            elif text in ["利用率", "功耗", "频率", "显存", "CPU", "CPU℃"]:
                child.setStyleSheet(f"color: {theme['label_color']}; font-size: 12px;")

        # 滑块
        self.fan_slider.setStyleSheet(QSS_TEMPLATES["slider"].format(**theme))

        # 按钮
        if self.fan_mode == "auto":
            self.fan_mode_btn.setStyleSheet(QSS_TEMPLATES["auto_btn"].format(**theme))
        else:
            self.fan_mode_btn.setStyleSheet(QSS_TEMPLATES["manual_btn"].format(**theme))

    def closeEvent(self, event):
        """关闭时清理资源"""
        self.timer.stop()
        self.mic_timer.stop()
        self.hw.shutdown()
        self.nvml.shutdown()
        self.cpu_monitor.shutdown()
        event.accept()
