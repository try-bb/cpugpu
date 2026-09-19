"""
配置管理模块
负责加载、保存、合并配置
"""

import os
import json
import logging

logger = logging.getLogger(__name__)


class ConfigManager:
    """配置管理器"""

    DEFAULT_CONFIG = {
        "开机自启": False,
        "更新频率": 2,
        "温度报警阈值": 75,
        "透明度": 240,
        "默认折叠": True,
        "主题色": "深蓝",
        "锁定麦克风": False,
        "CPU温度监控": True,
        "温度曲线": {
            "启用": False,
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

    def __init__(self, config_file=None):
        if config_file is None:
            config_file = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "GPU监控设置.json"
            )
        self.config_file = config_file
        self.config = self.load()

    def load(self):
        """加载配置，合并默认值"""
        config = self.DEFAULT_CONFIG.copy()

        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                config = self._deep_merge(config, loaded)
            except Exception as e:
                logger.warning(f"加载配置失败，使用默认值: {e}")

        return config

    def save(self, config=None):
        """保存配置到文件"""
        if config is not None:
            self.config = config
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False

    def get(self, key, default=None):
        """获取配置值"""
        return self.config.get(key, default)

    def set(self, key, value):
        """设置配置值"""
        self.config[key] = value

    def _deep_merge(self, base, override):
        """深度合并字典，override 覆盖 base"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
