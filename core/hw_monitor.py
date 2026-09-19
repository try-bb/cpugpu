"""
统一硬件监控模块
优先使用 LibreHardwareMonitor 读取所有硬件信息
备用：NVML (GPU) / Core Temp 共享内存 (CPU)
优化：缓存机制 + 后台刷新，避免 .NET 桥接阻塞 UI
"""

import time
import logging
import threading

logger = logging.getLogger(__name__)


class HWMonitor:
    """统一硬件监控器（单例 + 缓存）"""

    _instance = None
    _lock = threading.Lock()

    # 缓存有效期（秒）
    CACHE_TTL = 1.5
    # 哨兵：区分"缓存无条目"和"缓存值为 None"
    _MISSING = object()

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
        self._lhm = None
        self._available = False
        self._init_lhm()

        # 缓存
        self._cache = {}          # 键 -> (值, 时间戳)
        self._cache_lock = threading.Lock()

    def _init_lhm(self):
        """初始化 LibreHardwareMonitor"""
        try:
            from PyLibreHardwareMonitor import Computer
            self._lhm = Computer()
            # 测试能否获取数据
            if self._lhm.cpu or self._lhm.gpu:
                self._available = True
                logger.info("LibreHardwareMonitor 初始化成功")
            else:
                logger.warning("LibreHardwareMonitor 未获取到硬件数据")
        except ImportError:
            logger.warning("PyLibreHardwareMonitor 未安装，硬件监控功能受限")
        except Exception as e:
            logger.warning(f"LibreHardwareMonitor 初始化失败: {e}")

    @property
    def available(self):
        return self._available

    def _get_cached(self, key):
        """读取缓存，过期或不存在返回 _MISSING"""
        with self._cache_lock:
            entry = self._cache.get(key)
            if entry is None:
                return self._MISSING
            value, ts = entry
            if time.monotonic() - ts > self.CACHE_TTL:
                return self._MISSING
            return value

    def _set_cached(self, key, value):
        """写入缓存"""
        with self._cache_lock:
            self._cache[key] = (value, time.monotonic())

    def refresh(self):
        """强制刷新所有缓存（由后台线程调用）"""
        if not self._available:
            return
        # 一次性读取所有数据并缓存
        self._refresh_all_sensors()

    def _refresh_all_sensors(self):
        """一次性读取所有传感器，更新缓存"""
        now = time.monotonic()
        with self._cache_lock:
            # CPU 传感器
            if self._lhm.cpu:
                for name, data in self._lhm.cpu.items():
                    temps = data.get('Temperature', {})
                    if 'CPU Package' in temps:
                        self._cache['cpu_temp'] = (round(temps['CPU Package']), now)
                    elif 'Core Average' in temps:
                        self._cache['cpu_temp'] = (round(temps['Core Average']), now)
                    elif 'Core Max' in temps:
                        self._cache['cpu_temp'] = (round(temps['Core Max']), now)
                    else:
                        core_temps = [v for k, v in temps.items()
                                      if k.startswith('CPU Core #') and 'TjMax' not in k]
                        if core_temps:
                            self._cache['cpu_temp'] = (round(sum(core_temps) / len(core_temps)), now)

                    loads = data.get('Load', {})
                    if 'CPU Total' in loads:
                        self._cache['cpu_load'] = (round(loads['CPU Total']), now)

                    power = data.get('Power', {})
                    if 'CPU Package' in power:
                        self._cache['cpu_power'] = (round(power['CPU Package'], 1), now)

                    clocks = data.get('Clock', {})
                    core_clocks = [v for k, v in clocks.items() if k.startswith('CPU Core #')]
                    if core_clocks:
                        self._cache['cpu_clock'] = (round(sum(core_clocks) / len(core_clocks)), now)

            # GPU 传感器
            if self._lhm.gpu:
                for name, data in self._lhm.gpu.items():
                    temps = data.get('Temperature', {})
                    if 'GPU Core' in temps:
                        self._cache['gpu_temp'] = (round(temps['GPU Core']), now)

                    loads = data.get('Load', {})
                    if 'GPU Core' in loads:
                        self._cache['gpu_load'] = (round(loads['GPU Core']), now)

                    power = data.get('Power', {})
                    if 'GPU Package' in power:
                        self._cache['gpu_power'] = (round(power['GPU Package'], 1), now)

                    clocks = data.get('Clock', {})
                    if 'GPU Core' in clocks:
                        self._cache['gpu_clock'] = (round(clocks['GPU Core']), now)

                    small = data.get('SmallData', {})
                    if 'GPU Memory Used' in small and 'GPU Memory Total' in small:
                        self._cache['gpu_memory'] = ((small['GPU Memory Used'], small['GPU Memory Total']), now)

                    control = data.get('Control', {})
                    fans = [v for k, v in control.items() if 'Fan' in k]
                    if fans:
                        self._cache['gpu_fan'] = (round(sum(fans) / len(fans)), now)

    # ==================== CPU 信息（走缓存） ====================

    def get_cpu_temp(self):
        """获取 CPU 温度（摄氏度）"""
        cached = self._get_cached('cpu_temp')
        if cached is not self._MISSING:
            return cached
        if not self._available or not self._lhm.cpu:
            return None
        # 缓存未命中，实时读取
        try:
            for name, data in self._lhm.cpu.items():
                temps = data.get('Temperature', {})
                for key in ('CPU Package', 'Core Average', 'Core Max'):
                    if key in temps:
                        val = round(temps[key])
                        self._set_cached('cpu_temp', val)
                        return val
                core_temps = [v for k, v in temps.items()
                              if k.startswith('CPU Core #') and 'TjMax' not in k]
                if core_temps:
                    val = round(sum(core_temps) / len(core_temps))
                    self._set_cached('cpu_temp', val)
                    return val
        except Exception as e:
            logger.debug(f"获取 CPU 温度失败: {e}")
        return None

    def get_cpu_load(self):
        """获取 CPU 总利用率 (%)"""
        cached = self._get_cached('cpu_load')
        if cached is not self._MISSING:
            return cached
        if not self._available or not self._lhm.cpu:
            return None
        try:
            for name, data in self._lhm.cpu.items():
                loads = data.get('Load', {})
                if 'CPU Total' in loads:
                    val = round(loads['CPU Total'])
                    self._set_cached('cpu_load', val)
                    return val
        except Exception as e:
            logger.debug(f"获取 CPU 利用率失败: {e}")
        return None

    def get_cpu_power(self):
        """获取 CPU 功耗 (W)"""
        cached = self._get_cached('cpu_power')
        if cached is not self._MISSING:
            return cached
        if not self._available or not self._lhm.cpu:
            return None
        try:
            for name, data in self._lhm.cpu.items():
                power = data.get('Power', {})
                if 'CPU Package' in power:
                    val = round(power['CPU Package'], 1)
                    self._set_cached('cpu_power', val)
                    return val
        except Exception as e:
            logger.debug(f"获取 CPU 功耗失败: {e}")
        return None

    def get_cpu_clock(self):
        """获取 CPU 平均频率 (MHz)"""
        cached = self._get_cached('cpu_clock')
        if cached is not self._MISSING:
            return cached
        if not self._available or not self._lhm.cpu:
            return None
        try:
            for name, data in self._lhm.cpu.items():
                clocks = data.get('Clock', {})
                core_clocks = [v for k, v in clocks.items() if k.startswith('CPU Core #')]
                if core_clocks:
                    val = round(sum(core_clocks) / len(core_clocks))
                    self._set_cached('cpu_clock', val)
                    return val
        except Exception as e:
            logger.debug(f"获取 CPU 频率失败: {e}")
        return None

    # ==================== GPU 信息（走缓存） ====================

    def get_gpu_temp(self):
        """获取 GPU 核心温度（摄氏度）"""
        cached = self._get_cached('gpu_temp')
        if cached is not self._MISSING:
            return cached
        if not self._available or not self._lhm.gpu:
            return None
        try:
            for name, data in self._lhm.gpu.items():
                temps = data.get('Temperature', {})
                if 'GPU Core' in temps:
                    val = round(temps['GPU Core'])
                    self._set_cached('gpu_temp', val)
                    return val
        except Exception as e:
            logger.debug(f"获取 GPU 温度失败: {e}")
        return None

    def get_gpu_load(self):
        """获取 GPU 核心利用率 (%)"""
        cached = self._get_cached('gpu_load')
        if cached is not self._MISSING:
            return cached
        if not self._available or not self._lhm.gpu:
            return None
        try:
            for name, data in self._lhm.gpu.items():
                loads = data.get('Load', {})
                if 'GPU Core' in loads:
                    val = round(loads['GPU Core'])
                    self._set_cached('gpu_load', val)
                    return val
        except Exception as e:
            logger.debug(f"获取 GPU 利用率失败: {e}")
        return None

    def get_gpu_power(self):
        """获取 GPU 功耗 (W)"""
        cached = self._get_cached('gpu_power')
        if cached is not self._MISSING:
            return cached
        if not self._available or not self._lhm.gpu:
            return None
        try:
            for name, data in self._lhm.gpu.items():
                power = data.get('Power', {})
                if 'GPU Package' in power:
                    val = round(power['GPU Package'], 1)
                    self._set_cached('gpu_power', val)
                    return val
        except Exception as e:
            logger.debug(f"获取 GPU 功耗失败: {e}")
        return None

    def get_gpu_clock(self):
        """获取 GPU 核心频率 (MHz)"""
        cached = self._get_cached('gpu_clock')
        if cached is not self._MISSING:
            return cached
        if not self._available or not self._lhm.gpu:
            return None
        try:
            for name, data in self._lhm.gpu.items():
                clocks = data.get('Clock', {})
                if 'GPU Core' in clocks:
                    val = round(clocks['GPU Core'])
                    self._set_cached('gpu_clock', val)
                    return val
        except Exception as e:
            logger.debug(f"获取 GPU 频率失败: {e}")
        return None

    def get_gpu_memory(self):
        """获取显存信息 (used_mb, total_mb)"""
        cached = self._get_cached('gpu_memory')
        if cached is not self._MISSING:
            return cached
        if not self._available or not self._lhm.gpu:
            return None
        try:
            for name, data in self._lhm.gpu.items():
                small = data.get('SmallData', {})
                if 'GPU Memory Used' in small and 'GPU Memory Total' in small:
                    val = (small['GPU Memory Used'], small['GPU Memory Total'])
                    self._set_cached('gpu_memory', val)
                    return val
        except Exception as e:
            logger.debug(f"获取显存信息失败: {e}")
        return None

    def get_gpu_fan_speed(self):
        """获取 GPU 风扇控制转速 (%)"""
        cached = self._get_cached('gpu_fan')
        if cached is not self._MISSING:
            return cached
        if not self._available or not self._lhm.gpu:
            return None
        try:
            for name, data in self._lhm.gpu.items():
                control = data.get('Control', {})
                fans = [v for k, v in control.items() if 'Fan' in k]
                if fans:
                    val = round(sum(fans) / len(fans))
                    self._set_cached('gpu_fan', val)
                    return val
        except Exception as e:
            logger.debug(f"获取 GPU 风扇转速失败: {e}")
        return None

    def get_gpu_info(self):
        """一次性获取所有 GPU 信息（兼容旧接口，走缓存）"""
        if not self._available:
            return None

        # 优先从缓存取（避免访问 self._lhm.gpu 触发 .NET 桥接）
        temp = self._get_cached('gpu_temp')
        if temp is not self._MISSING:
            fan = self._get_cached('gpu_fan')
            util = self._get_cached('gpu_load')
            power = self._get_cached('gpu_power')
            clock = self._get_cached('gpu_clock')
            mem = self._get_cached('gpu_memory')

            return {
                'temp': str(temp) if temp is not None else '0',
                'fan': str(fan) if fan is not None and fan is not self._MISSING else '0',
                'util': str(util) if util is not None and util is not self._MISSING else '0',
                'power': f"{power:.1f}" if power is not None and power is not self._MISSING else '0',
                'clock': str(clock) if clock is not None and clock is not self._MISSING else '0',
                'mem_used': f"{mem[0]:.0f}" if mem is not None and mem is not self._MISSING else '0',
                'mem_total': f"{mem[1]:.0f}" if mem is not None and mem is not self._MISSING else '0',
                'source': 'librehardwaremonitor'
            }

        # 缓存未命中，实时读取
        if self._lhm.gpu:
            temp = self.get_gpu_temp()
            if temp is not None:
                fan = self.get_gpu_fan_speed()
                util = self.get_gpu_load()
                power = self.get_gpu_power()
                clock = self.get_gpu_clock()
                mem = self.get_gpu_memory()

                return {
                    'temp': str(temp),
                    'fan': str(fan) if fan is not None else '0',
                    'util': str(util) if util is not None else '0',
                    'power': f"{power:.1f}" if power is not None else '0',
                    'clock': str(clock) if clock is not None else '0',
                    'mem_used': f"{mem[0]:.0f}" if mem else '0',
                    'mem_total': f"{mem[1]:.0f}" if mem else '0',
                    'source': 'librehardwaremonitor'
                }

        # 备用：NVML / nvidia-smi（由 nvml_controller 提供）
        return None

    def shutdown(self):
        """关闭监控"""
        with self._cache_lock:
            self._cache.clear()
        self._lhm = None
        self._available = False
        HWMonitor._instance = None
        logger.info("HWMonitor 已关闭")
