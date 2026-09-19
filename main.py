"""
GPU 监控 + 风扇控制 主入口
"""

import sys
import os
import ctypes
import logging

# 配置日志
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'gpu_monitor.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import ConfigManager
from panel.gpu_panel import GPUPanel


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def main():
    # 检查管理员权限
    if not is_admin():
        logger.info("非管理员运行，请求提升权限...")
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(sys.argv), None, 1
        )
        sys.exit()

    logger.info("GPU 监控程序启动")

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # 高 DPI 支持
    app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    config_mgr = ConfigManager()
    window = GPUPanel(config_mgr)
    window.show()

    exit_code = app.exec_()

    logger.info("GPU 监控程序退出")
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
