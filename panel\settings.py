"""
设置对话框
增加 CPU 温度监控、麦克风锁定选项
"""

import sys
import os

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import ConfigManager
from themes.themes import THEMES


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("设置")
        self.setFixedSize(320, 520)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self.setStyleSheet("""
            QDialog { background-color: #1a1a2e; }
            QLabel { color: #e2e8f0; }
            QCheckBox { color: #e2e8f0; }
            QCheckBox::indicator { width: 16px; height: 16px; }
        """)
        self.initUI()
        self.load_settings()

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 15, 20, 15)

        # 标题
        title = QLabel("⚙️ 设置")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #e2e8f0;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # === 基础设置 ===
        self.autostart_checkbox = QCheckBox("开机自启")
        self.autostart_checkbox.setStyleSheet("color: #e2e8f0; font-size: 12px;")
        layout.addWidget(self.autostart_checkbox)

        # 更新频率
        freq_layout = QHBoxLayout()
        freq_label = QLabel("更新频率:")
        freq_label.setStyleSheet("color: #a0aec0; font-size: 12px;")
        self.freq_combo = QComboBox()
        self.freq_combo.addItems(["1秒", "2秒", "5秒", "10秒"])
        self.freq_combo.setFixedWidth(80)
        self.freq_combo.setStyleSheet(self._combo_style())
        freq_layout.addWidget(freq_label)
        freq_layout.addWidget(self.freq_combo)
        freq_layout.addStretch()
        layout.addLayout(freq_layout)

        # 温度报警
        temp_layout = QHBoxLayout()
        temp_label = QLabel("温度报警阈值:")
        temp_label.setStyleSheet("color: #a0aec0; font-size: 12px;")
        self.temp_spin = QSpinBox()
        self.temp_spin.setRange(50, 100)
        self.temp_spin.setValue(75)
        self.temp_spin.setSuffix("°C")
        self.temp_spin.setFixedWidth(70)
        self.temp_spin.setStyleSheet(self._spin_style())
        temp_layout.addWidget(temp_label)
        temp_layout.addWidget(self.temp_spin)
        temp_layout.addStretch()
        layout.addLayout(temp_layout)

        # 透明度
        opacity_layout = QHBoxLayout()
        opacity_label = QLabel("透明度:")
        opacity_label.setStyleSheet("color: #a0aec0; font-size: 12px;")
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(100, 255)
        self.opacity_slider.setValue(240)
        self.opacity_value = QLabel("240")
        self.opacity_value.setStyleSheet("color: #63b3ed; font-size: 12px;")
        self.opacity_value.setFixedWidth(30)
        self.opacity_slider.valueChanged.connect(lambda v: self.opacity_value.setText(str(v)))
        opacity_layout.addWidget(opacity_label)
        opacity_layout.addWidget(self.opacity_slider)
        opacity_layout.addWidget(self.opacity_value)
        layout.addLayout(opacity_layout)

        # 默认折叠
        self.collapsed_checkbox = QCheckBox("启动时默认折叠")
        self.collapsed_checkbox.setStyleSheet("color: #e2e8f0; font-size: 12px;")
        layout.addWidget(self.collapsed_checkbox)

        # 主题色
        theme_layout = QHBoxLayout()
        theme_label = QLabel("主题色:")
        theme_label.setStyleSheet("color: #a0aec0; font-size: 12px;")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["深蓝", "暗灰", "黑色"])
        self.theme_combo.setFixedWidth(80)
        self.theme_combo.setStyleSheet(self._combo_style())
        theme_layout.addWidget(theme_label)
        theme_layout.addWidget(self.theme_combo)
        theme_layout.addStretch()
        layout.addLayout(theme_layout)

        # === 新增功能 ===
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.HLine)
        sep1.setStyleSheet("color: #4a5568;")
        layout.addWidget(sep1)

        # CPU 温度监控
        self.cpu_temp_checkbox = QCheckBox("CPU 温度监控（需安装 Core Temp）")
        self.cpu_temp_checkbox.setStyleSheet("color: #e2e8f0; font-size: 12px;")
        layout.addWidget(self.cpu_temp_checkbox)

        # 麦克风锁定
        self.mic_lock_checkbox = QCheckBox("锁定麦克风音量为 100%")
        self.mic_lock_checkbox.setStyleSheet("color: #e2e8f0; font-size: 12px;")
        layout.addWidget(self.mic_lock_checkbox)

        # === 温度曲线 ===
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("color: #4a5568;")
        layout.addWidget(sep2)

        self.curve_checkbox = QCheckBox("启用温度曲线控制")
        self.curve_checkbox.setStyleSheet("color: #e2e8f0; font-size: 12px;")
        layout.addWidget(self.curve_checkbox)

        # 曲线点编辑
        curve_widget = QWidget()
        curve_layout = QVBoxLayout(curve_widget)
        curve_layout.setContentsMargins(20, 5, 0, 5)
        curve_layout.setSpacing(5)

        curve_title = QLabel("温度-转速对应点：")
        curve_title.setStyleSheet("color: #a0aec0; font-size: 11px;")
        curve_layout.addWidget(curve_title)

        self.curve_point_inputs = []
        for i in range(6):
            pl = QHBoxLayout()
            pl.setSpacing(5)

            tl = QLabel(f"点{i+1} 温度:")
            tl.setStyleSheet("color: #718096; font-size: 10px;")
            tl.setFixedWidth(50)

            ti = QSpinBox()
            ti.setRange(20, 100)
            ti.setStyleSheet(self._spin_style_small())
            ti.setFixedWidth(50)

            sl = QLabel("转速:")
            sl.setStyleSheet("color: #718096; font-size: 10px;")
            sl.setFixedWidth(30)

            si = QSpinBox()
            si.setRange(0, 100)
            si.setStyleSheet(self._spin_style_small())
            si.setFixedWidth(50)

            ul = QLabel("%")
            ul.setStyleSheet("color: #718096; font-size: 10px;")

            pl.addWidget(tl)
            pl.addWidget(ti)
            pl.addWidget(sl)
            pl.addWidget(si)
            pl.addWidget(ul)
            pl.addStretch()
            curve_layout.addLayout(pl)
            self.curve_point_inputs.append((ti, si))

        layout.addWidget(curve_widget)

        # 缓冲设置
        buffer_widget = QWidget()
        buffer_layout = QVBoxLayout(buffer_widget)
        buffer_layout.setContentsMargins(20, 5, 0, 5)
        buffer_layout.setSpacing(5)

        buf_title = QLabel("缓冲设置（防抖保护）：")
        buf_title.setStyleSheet("color: #a0aec0; font-size: 11px;")
        buffer_layout.addWidget(buf_title)

        # 温度变化阈值
        thl = QHBoxLayout()
        thl_lbl = QLabel("温度变化阈值:")
        thl_lbl.setStyleSheet("color: #718096; font-size: 10px;")
        thl_lbl.setFixedWidth(80)
        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(1, 10)
        self.threshold_spin.setSuffix("°C")
        self.threshold_spin.setStyleSheet(self._spin_style_small())
        self.threshold_spin.setFixedWidth(60)
        thl_tip = QLabel("(小于此值不调整)")
        thl_tip.setStyleSheet("color: #4a5568; font-size: 9px;")
        thl.addWidget(thl_lbl)
        thl.addWidget(self.threshold_spin)
        thl.addWidget(thl_tip)
        thl.addStretch()
        buffer_layout.addLayout(thl)

        # 稳定等待时间
        wl = QHBoxLayout()
        wl_lbl = QLabel("稳定等待时间:")
        wl_lbl.setStyleSheet("color: #718096; font-size: 10px;")
        wl_lbl.setFixedWidth(80)
        self.wait_spin = QSpinBox()
        self.wait_spin.setRange(1, 30)
        self.wait_spin.setSuffix("秒")
        self.wait_spin.setStyleSheet(self._spin_style_small())
        self.wait_spin.setFixedWidth(60)
        wl_tip = QLabel("(温度稳定后才调整)")
        wl_tip.setStyleSheet("color: #4a5568; font-size: 9px;")
        wl.addWidget(wl_lbl)
        wl.addWidget(self.wait_spin)
        wl.addWidget(wl_tip)
        wl.addStretch()
        buffer_layout.addLayout(wl)

        # 转速最大变化
        cl = QHBoxLayout()
        cl_lbl = QLabel("转速最大变化:")
        cl_lbl.setStyleSheet("color: #718096; font-size: 10px;")
        cl_lbl.setFixedWidth(80)
        self.change_spin = QSpinBox()
        self.change_spin.setRange(5, 50)
        self.change_spin.setSuffix("%")
        self.change_spin.setStyleSheet(self._spin_style_small())
        self.change_spin.setFixedWidth(60)
        cl_tip = QLabel("(每次最多变化量)")
        cl_tip.setStyleSheet("color: #4a5568; font-size: 9px;")
        cl.addWidget(cl_lbl)
        cl.addWidget(self.change_spin)
        cl.addWidget(cl_tip)
        cl.addStretch()
        buffer_layout.addLayout(cl)

        layout.addWidget(buffer_widget)

        curve_info = QLabel("自动模式：根据温度自动调节风扇转速")
        curve_info.setStyleSheet("color: #718096; font-size: 10px;")
        curve_info.setWordWrap(True)
        layout.addWidget(curve_info)

        layout.addStretch()

        # 按钮
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.setStyleSheet("""
            QPushButton { background: #48bb78; color: #1a202c; border: none; border-radius: 4px; padding: 8px 20px; font-weight: 500; font-size: 12px; }
            QPushButton:hover { background: #68d391; }
        """)
        save_btn.clicked.connect(self.save_settings)

        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("""
            QPushButton { background: #4a5568; color: #e2e8f0; border: none; border-radius: 4px; padding: 8px 20px; font-weight: 500; font-size: 12px; }
            QPushButton:hover { background: #5c7a99; }
        """)
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _combo_style(self):
        return """
            QComboBox { background: #2d2d3a; color: #e2e8f0; border: 1px solid #4a5568; border-radius: 3px; padding: 2px; font-size: 11px; }
        """

    def _spin_style(self):
        return """
            QSpinBox { background: #2d2d3a; color: #e2e8f0; border: 1px solid #4a5568; border-radius: 3px; padding: 2px; font-size: 11px; }
        """

    def _spin_style_small(self):
        return """
            QSpinBox { background: #2d3748; color: #e2e8f0; border: 1px solid #4a5568; border-radius: 3px; padding: 2px; font-size: 10px; }
        """

    def load_settings(self):
        if self.parent and hasattr(self.parent, 'config'):
            config = self.parent.config

            self.autostart_checkbox.setChecked(config.get("开机自启", False))

            freq = config.get("更新频率", 2)
            self.freq_combo.setCurrentIndex({1: 0, 2: 1, 5: 2, 10: 3}.get(freq, 1))

            self.temp_spin.setValue(config.get("温度报警阈值", 75))

            opacity = config.get("透明度", 240)
            self.opacity_slider.setValue(opacity)
            self.opacity_value.setText(str(opacity))

            self.collapsed_checkbox.setChecked(config.get("默认折叠", True))

            theme = config.get("主题色", "深蓝")
            self.theme_combo.setCurrentIndex({"深蓝": 0, "暗灰": 1, "黑色": 2}.get(theme, 0))

            self.cpu_temp_checkbox.setChecked(config.get("CPU温度监控", True))
            self.mic_lock_checkbox.setChecked(config.get("锁定麦克风", False))

            curve = config.get("温度曲线", {})
            self.curve_checkbox.setChecked(curve.get("启用", False))

            curve_points = curve.get("曲线点", ConfigManager.DEFAULT_CONFIG["温度曲线"]["曲线点"])
            for i, (ti, si) in enumerate(self.curve_point_inputs):
                if i < len(curve_points):
                    ti.setValue(curve_points[i].get("温度", 35 + i * 10))
                    si.setValue(curve_points[i].get("转速", 20 + i * 15))

            buf = curve.get("缓冲设置", ConfigManager.DEFAULT_CONFIG["温度曲线"]["缓冲设置"])
            self.threshold_spin.setValue(buf.get("温度变化阈值", 3))
            self.wait_spin.setValue(buf.get("稳定等待时间", 5))
            self.change_spin.setValue(buf.get("转速最大变化", 15))

    def save_settings(self):
        if self.parent and hasattr(self.parent, 'config'):
            self.parent.config["开机自启"] = self.autostart_checkbox.isChecked()

            freq_map = {0: 1, 1: 2, 2: 5, 3: 10}
            self.parent.config["更新频率"] = freq_map.get(self.freq_combo.currentIndex(), 2)

            self.parent.config["温度报警阈值"] = self.temp_spin.value()
            self.parent.config["透明度"] = self.opacity_slider.value()
            self.parent.config["默认折叠"] = self.collapsed_checkbox.isChecked()

            theme_map = {0: "深蓝", 1: "暗灰", 2: "黑色"}
            self.parent.config["主题色"] = theme_map.get(self.theme_combo.currentIndex(), "深蓝")

            self.parent.config["CPU温度监控"] = self.cpu_temp_checkbox.isChecked()
            self.parent.config["锁定麦克风"] = self.mic_lock_checkbox.isChecked()

            # 温度曲线
            if "温度曲线" not in self.parent.config:
                self.parent.config["温度曲线"] = {}
            self.parent.config["温度曲线"]["启用"] = self.curve_checkbox.isChecked()

            curve_points = []
            for ti, si in self.curve_point_inputs:
                curve_points.append({"温度": ti.value(), "转速": si.value()})
            self.parent.config["温度曲线"]["曲线点"] = curve_points

            self.parent.config["温度曲线"]["缓冲设置"] = {
                "温度变化阈值": self.threshold_spin.value(),
                "稳定等待时间": self.wait_spin.value(),
                "转速最大变化": self.change_spin.value()
            }

            if self.parent.config_mgr.save():
                self.parent.apply_config()
                self.parent.timer.stop()
                self.parent.timer.start(self.parent.config["更新频率"] * 1000)

                # 麦克风锁定
                mic_enabled = self.mic_lock_checkbox.isChecked()
                self.parent.mic_locker.enabled = mic_enabled
                if mic_enabled and self.parent.mic_locker.available:
                    self.parent.mic_timer.start(2000)
                    self.parent.mic_indicator.setStyleSheet("""
                        QPushButton {
                            background: #48bb78; color: #1a202c; border: none;
                            border-radius: 3px; font-size: 11px;
                        }
                    """)
                    self.parent.mic_indicator.setToolTip("麦克风锁定：开启")
                else:
                    self.parent.mic_timer.stop()
                    self.parent.mic_indicator.setStyleSheet("""
                        QPushButton {
                            background: #4a5568; color: #718096; border: none;
                            border-radius: 3px; font-size: 11px;
                        }
                    """)
                    self.parent.mic_indicator.setToolTip("麦克风锁定：关闭")

                self.accept()
            else:
                QMessageBox.warning(self, "保存失败", "无法保存配置文件！")
