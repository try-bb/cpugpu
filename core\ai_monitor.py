"""
AI 服务监控模块
监控 LM Studio 等 AI 推理服务的运行状态
"""

import logging
import requests

logger = logging.getLogger(__name__)


class AIMonitor:
    """AI 服务监控器"""

    def __init__(self):
        self.lmstudio_running = False

    def check_lmstudio(self):
        """检查 LM Studio 是否运行"""
        try:
            response = requests.get('http://localhost:1234/v1/models', timeout=0.5)
            is_running = response.status_code == 200
            if is_running != self.lmstudio_running:
                self.lmstudio_running = is_running
                logger.info(f"LM Studio 状态变化: {'运行' if is_running else '停止'}")
            return is_running
        except requests.Timeout:
            logger.debug("LM Studio 连接超时")
        except requests.ConnectionError:
            pass  # 服务未启动，正常情况
        except requests.RequestException as e:
            logger.debug(f"LM Studio 请求异常: {e}")
        except Exception as e:
            logger.debug(f"LM Studio 检测异常: {e}")

        self.lmstudio_running = False
        return False

    def get_lmstudio_models(self):
        """获取 LM Studio 当前加载的模型"""
        try:
            response = requests.get('http://localhost:1234/v1/models', timeout=0.5)
            if response.status_code != 200:
                return []

            data = response.json()
            models = []
            for model in data.get('data', []):
                model_id = model.get('id', 'Unknown')
                name_parts = model_id.split('/')
                display_name = name_parts[-1] if name_parts else model_id
                models.append({
                    'name': display_name,
                    'size': '-',
                    'mem_gb': 0,
                    'processor': 'GPU',
                    'context': '-',
                    'until': '运行中',
                    'source': 'LM Studio'
                })
            return models

        except requests.Timeout:
            pass
        except requests.ConnectionError:
            pass
        except requests.RequestException:
            pass
        except Exception as e:
            logger.debug(f"获取 LM Studio 模型失败: {e}")

        self.lmstudio_running = False
        return []

    @staticmethod
    def simplify_until(until_str):
        """简化剩余时间显示"""
        if not until_str:
            return "-"
        until_str = until_str.lower()
        import re
        numbers = re.findall(r'\d+', until_str)
        if not numbers:
            return "-"
        num = numbers[0]
        if 'minute' in until_str:
            return f"{num}分"
        elif 'hour' in until_str:
            return f"{num}时"
        elif 'second' in until_str:
            return f"{num}秒"
        elif 'day' in until_str:
            return f"{num}天"
        return f"{num}分"
