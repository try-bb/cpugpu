"""
NVML 单例控制器
封装 NVIDIA NVML 库，避免重复加载和初始化
"""

import ctypes
import os
import logging
import threading

logger = logging.getLogger(__name__)


class NVMLController:
    """NVML 单例控制器，只初始化一次，复用句柄"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.nvml = None
        self.handle = None
        self._fan_count = None
        self._init_nvml()

    def _init_nvml(self):
        """初始化 NVML 库"""
        try:
            nvml_path = "C:/Windows/System32/nvml.dll"
            if not os.path.exists(nvml_path):
                logger.warning("找不到 nvml.dll")
                return

            self.nvml = ctypes.windll.LoadLibrary(nvml_path)

            # 定义函数签名
            self.nvml.nvmlInit_v2.restype = ctypes.c_int
            self.nvml.nvmlShutdown.restype = ctypes.c_int
            self.nvml.nvmlDeviceGetHandleByIndex_v2.restype = ctypes.c_int
            self.nvml.nvmlDeviceGetHandleByIndex_v2.argtypes = [
                ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p)
            ]

            # 风扇相关
            try:
                self.nvml.nvmlDeviceSetFanSpeed_v2.restype = ctypes.c_int
                self.nvml.nvmlDeviceSetFanSpeed_v2.argtypes = [
                    ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint
                ]
            except Exception:
                pass

            try:
                self.nvml.nvmlDeviceSetDefaultFanSpeed_v2.restype = ctypes.c_int
                self.nvml.nvmlDeviceSetDefaultFanSpeed_v2.argtypes = [
                    ctypes.c_void_p, ctypes.c_uint
                ]
            except Exception:
                pass

            try:
                self.nvml.nvmlDeviceGetNumFans.restype = ctypes.c_int
                self.nvml.nvmlDeviceGetNumFans.argtypes = [
                    ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)
                ]
            except Exception:
                pass

            try:
                self.nvml.nvmlDeviceGetFanSpeed_v2.restype = ctypes.c_int
                self.nvml.nvmlDeviceGetFanSpeed_v2.argtypes = [
                    ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_uint)
                ]
            except Exception:
                pass

            # 温度相关
            try:
                self.nvml.nvmlDeviceGetTemperature_v2.restype = ctypes.c_int
                self.nvml.nvmlDeviceGetTemperature_v2.argtypes = [
                    ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_uint)
                ]
            except Exception:
                pass

            # 利用率
            try:
                self.nvml.nvmlDeviceGetUtilizationRates.restype = ctypes.c_int
                class Utilization(ctypes.Structure):
                    _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]
                self.nvml.nvmlDeviceGetUtilizationRates.argtypes = [
                    ctypes.c_void_p, ctypes.POINTER(Utilization)
                ]
                self._Utilization = Utilization
            except Exception:
                self._Utilization = None

            # 功耗
            try:
                self.nvml.nvmlDeviceGetPowerUsage.restype = ctypes.c_int
                self.nvml.nvmlDeviceGetPowerUsage.argtypes = [
                    ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)
                ]
            except Exception:
                pass

            # 频率
            try:
                self.nvml.nvmlDeviceGetClockInfo.restype = ctypes.c_int
                self.nvml.nvmlDeviceGetClockInfo.argtypes = [
                    ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_uint)
                ]
            except Exception:
                pass

            # 显存
            try:
                self.nvml.nvmlDeviceGetMemoryInfo.restype = ctypes.c_int
                class MemoryInfo(ctypes.Structure):
                    _fields_ = [
                        ("total", ctypes.c_ulonglong),
                        ("free", ctypes.c_ulonglong),
                        ("used", ctypes.c_ulonglong),
                    ]
                self.nvml.nvmlDeviceGetMemoryInfo.argtypes = [
                    ctypes.c_void_p, ctypes.POINTER(MemoryInfo)
                ]
                self._MemoryInfo = MemoryInfo
            except Exception:
                self._MemoryInfo = None

            # 初始化 NVML
            ret = self.nvml.nvmlInit_v2()
            if ret != 0:
                logger.error(f"NVML 初始化失败: {ret}")
                self.nvml = None
                return

            # 获取 GPU handle
            self.handle = ctypes.c_void_p()
            ret = self.nvml.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(self.handle))
            if ret != 0:
                logger.error(f"获取 GPU handle 失败: {ret}")
                self.nvml.nvmlShutdown()
                self.nvml = None
                self.handle = None
                return

            # 获取风扇数量
            self._fan_count = self._detect_fan_count()
            logger.info(f"NVML 初始化成功, 风扇数量: {self._fan_count}")

        except Exception as e:
            logger.error(f"NVML 初始化异常: {e}")
            self.nvml = None
            self.handle = None

    def _detect_fan_count(self):
        """检测风扇数量"""
        if not self.nvml or not self.handle:
            return 0
        try:
            fan_count = ctypes.c_uint()
            ret = self.nvml.nvmlDeviceGetNumFans(self.handle, ctypes.byref(fan_count))
            if ret == 0:
                return fan_count.value
        except Exception:
            pass
        return 0

    @property
    def available(self):
        """NVML 是否可用"""
        return self.nvml is not None and self.handle is not None

    @property
    def fan_count(self):
        """风扇数量"""
        return self._fan_count or 0

    def get_fan_speed(self):
        """获取风扇平均转速，返回 0-100 或 None"""
        if not self.available:
            return None
        try:
            speeds = []
            for i in range(self.fan_count):
                speed = ctypes.c_uint()
                ret = self.nvml.nvmlDeviceGetFanSpeed_v2(self.handle, i, ctypes.byref(speed))
                if ret == 0:
                    speeds.append(speed.value)
            if speeds:
                return int(sum(speeds) / len(speeds))
        except Exception as e:
            logger.debug(f"获取风扇转速失败: {e}")
        return None

    def set_fan_speed(self, speed):
        """设置风扇转速 (0-100)"""
        if not self.available:
            return False
        try:
            success = False
            for i in range(self.fan_count):
                try:
                    ret = self.nvml.nvmlDeviceSetFanSpeed_v2(self.handle, i, speed)
                    if ret == 0:
                        logger.debug(f"风扇 {i + 1} 已设置为 {speed}%")
                        success = True
                    else:
                        logger.warning(f"风扇 {i + 1} 设置失败: {ret}")
                except Exception:
                    logger.warning(f"风扇 {i + 1} 不支持单独设置")
            return success
        except Exception as e:
            logger.error(f"设置风扇转速失败: {e}")
            return False

    def set_auto_fan(self):
        """恢复自动风扇控制"""
        if not self.available:
            return False
        try:
            success = False
            for i in range(self.fan_count):
                try:
                    ret = self.nvml.nvmlDeviceSetDefaultFanSpeed_v2(self.handle, i)
                    if ret == 0:
                        logger.debug(f"风扇 {i + 1} 恢复自动控制")
                        success = True
                except Exception:
                    pass
            if not success:
                logger.info("恢复自动控制（可能已自动）")
            return True
        except Exception as e:
            logger.error(f"恢复自动控制失败: {e}")
            return False

    def get_gpu_temp(self):
        """获取 GPU 温度（摄氏度）"""
        if not self.available:
            return None
        try:
            temp = ctypes.c_uint()
            # NVML_TEMPERATURE_GPU = 0
            ret = self.nvml.nvmlDeviceGetTemperature_v2(self.handle, 0, ctypes.byref(temp))
            if ret == 0:
                return temp.value
        except Exception:
            pass
        return None

    def get_gpu_utilization(self):
        """获取 GPU 利用率"""
        if not self.available or not hasattr(self, '_Utilization'):
            return None
        try:
            util = self._Utilization()
            ret = self.nvml.nvmlDeviceGetUtilizationRates(self.handle, ctypes.byref(util))
            if ret == 0:
                return util.gpu
        except Exception:
            pass
        return None

    def get_gpu_power(self):
        """获取 GPU 功耗（瓦特）"""
        if not self.available:
            return None
        try:
            power = ctypes.c_uint()
            ret = self.nvml.nvmlDeviceGetPowerUsage(self.handle, ctypes.byref(power))
            if ret == 0:
                return power.value / 1000.0  # mW -> W
        except Exception:
            pass
        return None

    def get_gpu_clock(self):
        """获取 GPU 核心频率（MHz）"""
        if not self.available:
            return None
        try:
            clock = ctypes.c_uint()
            # NVML_CLOCK_GRAPHICS = 0
            ret = self.nvml.nvmlDeviceGetClockInfo(self.handle, 0, ctypes.byref(clock))
            if ret == 0:
                return clock.value
        except Exception:
            pass
        return None

    def get_gpu_memory(self):
        """获取显存信息 (used_mb, total_mb)"""
        if not self.available or not hasattr(self, '_MemoryInfo'):
            return None
        try:
            mem = self._MemoryInfo()
            ret = self.nvml.nvmlDeviceGetMemoryInfo(self.handle, ctypes.byref(mem))
            if ret == 0:
                return (mem.used / (1024 * 1024), mem.total / (1024 * 1024))
        except Exception:
            pass
        return None

    def get_gpu_info(self):
        """一次性获取所有 GPU 信息"""
        # 优先使用 NVML
        if self.available:
            temp = self.get_gpu_temp()
            fan = self.get_fan_speed()
            util = self.get_gpu_utilization()
            power = self.get_gpu_power()
            clock = self.get_gpu_clock()
            mem = self.get_gpu_memory()

            if temp is not None:
                return {
                    'temp': str(temp),
                    'fan': str(fan) if fan is not None else '0',
                    'util': str(util) if util is not None else '0',
                    'power': f"{power:.1f}" if power is not None else '0',
                    'clock': str(clock) if clock is not None else '0',
                    'mem_used': f"{mem[0]:.0f}" if mem else '0',
                    'mem_total': f"{mem[1]:.0f}" if mem else '0',
                    'source': 'nvml'
                }

        # 回退到 nvidia-smi
        return self._get_gpu_info_smi()

    def _get_gpu_info_smi(self):
        """使用 nvidia-smi 获取 GPU 信息（备用方案）"""
        try:
            import subprocess
            result = subprocess.run(
                ['nvidia-smi',
                 '--query-gpu=temperature.gpu,utilization.gpu,power.draw,clocks.current.graphics,memory.used,memory.total',
                 '--format=csv,noheader,nounits'],
                capture_output=True, text=True, encoding='utf-8',
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0 and result.stdout.strip():
                data = result.stdout.strip().split(',')
                if len(data) >= 6:
                    fan_speed = self.get_fan_speed()
                    return {
                        'temp': data[0].strip(),
                        'fan': str(fan_speed) if fan_speed is not None else '0',
                        'util': data[1].strip(),
                        'power': data[2].strip(),
                        'clock': data[3].strip(),
                        'mem_used': data[4].strip(),
                        'mem_total': data[5].strip(),
                        'source': 'nvidia-smi'
                    }
        except Exception as e:
            logger.debug(f"nvidia-smi 获取失败: {e}")
        return None

    def shutdown(self):
        """关闭 NVML"""
        if self.nvml:
            try:
                self.nvml.nvmlShutdown()
            except Exception:
                pass
            self.nvml = None
            self.handle = None
            NVMLController._instance = None
            logger.info("NVML 已关闭")
