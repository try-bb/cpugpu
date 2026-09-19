"""
主题配色定义
"""

THEMES = {
    "深蓝": {
        "bg_color": "rgba(25, 25, 35, {})",
        "border_color": "#3a3a4a",
        "title_color": "#8fa1b3",
        "label_color": "#a0aec0",
        "temp_color": "#f56565",
        "fan_color": "#63b3ed",
        "util_color": "#48bb78",
        "power_color": "#ed8936",
        "clock_color": "#9f7aea",
        "memory_color": "#38b2ac",
        "cpu_color": "#63b3ed",
        "cpu_temp_color": "#ff9f43",
        "auto_btn_bg": "#48bb78",
        "auto_btn_hover": "#68d391",
        "manual_btn_bg": "#d69e2e",
        "manual_btn_hover": "#ecc94b",
        "slider_color": "#d69e2e",
        "mic_color": "#fc8181"
    },
    "暗灰": {
        "bg_color": "rgba(60, 60, 65, {})",
        "border_color": "#7a7a8a",
        "title_color": "#d0e0f0",
        "label_color": "#e0e8f0",
        "temp_color": "#ff8787",
        "fan_color": "#91caff",
        "util_color": "#6ee7b7",
        "power_color": "#fdba74",
        "clock_color": "#c4b5fd",
        "memory_color": "#5eead4",
        "cpu_color": "#91caff",
        "cpu_temp_color": "#ffa654",
        "auto_btn_bg": "#6ee7b7",
        "auto_btn_hover": "#a7f3d0",
        "manual_btn_bg": "#fcd34d",
        "manual_btn_hover": "#fde68a",
        "slider_color": "#fcd34d",
        "mic_color": "#fca5a5"
    },
    "黑色": {
        "bg_color": "rgba(0, 0, 0, {})",
        "border_color": "#333333",
        "title_color": "#ffffff",
        "label_color": "#cccccc",
        "temp_color": "#ff6b6b",
        "fan_color": "#60a5fa",
        "util_color": "#4ade80",
        "power_color": "#fb923c",
        "clock_color": "#a78bfa",
        "memory_color": "#2dd4bf",
        "cpu_color": "#60a5fa",
        "cpu_temp_color": "#fb923c",
        "auto_btn_bg": "#4ade80",
        "auto_btn_hover": "#86efac",
        "manual_btn_bg": "#facc15",
        "manual_btn_hover": "#fde047",
        "slider_color": "#facc15",
        "mic_color": "#f87171"
    }
}

# QSS 模板
QSS_TEMPLATES = {
    "main_frame": """
        QFrame {{
            background-color: {bg_color};
            border: 1px solid {border_color};
            border-radius: 12px;
        }}
    """,
    "progress_bar": """
        QProgressBar {{
            border: none;
            border-radius: 5px;
            background: #2d3748;
        }}
        QProgressBar::chunk {{
            background: {color};
            border-radius: 5px;
        }}
    """,
    "progress_bar_gradient": """
        QProgressBar {{
            border: none;
            border-radius: 5px;
            background: #2d3748;
        }}
        QProgressBar::chunk {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4a5568, stop:1 {color});
            border-radius: 5px;
        }}
    """,
    "slider": """
        QSlider::groove:horizontal {{
            height: 6px;
            background: #2d3748;
            border-radius: 3px;
        }}
        QSlider::sub-page:horizontal {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4a5568, stop:1 {slider_color});
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background: #e2e8f0;
            width: 16px;
            height: 16px;
            margin: -5px 0;
            border-radius: 8px;
            border: 2px solid {slider_color};
        }}
        QSlider::handle:horizontal:hover {{
            background: #ffffff;
            border: 2px solid {manual_btn_hover};
        }}
    """,
    "auto_btn": """
        QPushButton {{
            background: {auto_btn_bg};
            color: #1a202c;
            border: none;
            border-radius: 3px;
            font-weight: 500;
            font-size: 10px;
        }}
        QPushButton:hover {{
            background: {auto_btn_hover};
        }}
    """,
    "manual_btn": """
        QPushButton {{
            background: {manual_btn_bg};
            color: #1a202c;
            border: none;
            border-radius: 3px;
            font-weight: 500;
            font-size: 10px;
        }}
        QPushButton:hover {{
            background: {manual_btn_hover};
        }}
    """,
    "label_container": """
        QWidget {{
            background-color: #2d3748;
            border-radius: 6px;
        }}
    """,
    "mode_combo": """
        QComboBox {{
            background: #2d2d3a;
            color: #e2e8f0;
            border: 1px solid #4a5568;
            border-radius: 4px;
            padding: 3px;
            font-size: 11px;
        }}
        QComboBox:hover {{
            border: 1px solid #5c7a99;
        }}
        QComboBox::drop-down {{
            border: none;
            width: 20px;
        }}
        QComboBox QAbstractItemView {{
            background: #2d2d3a;
            color: #e2e8f0;
            border: 1px solid #4a5568;
            selection-background-color: #4a5568;
        }}
    """,
    "close_btn": """
        QPushButton {{
            background: #4a5568;
            color: #e2e8f0;
            border: none;
            border-radius: 4px;
            font-weight: bold;
            font-size: 12px;
        }}
        QPushButton:hover {{
            background: #c53030;
            color: white;
        }}
    """,
    "toggle_btn": """
        QPushButton {{
            background: #4a5568;
            color: #e2e8f0;
            border: none;
            border-radius: 4px;
            font-weight: bold;
            font-size: 10px;
        }}
        QPushButton:hover {{
            background: #5c7a99;
        }}
    """
}
