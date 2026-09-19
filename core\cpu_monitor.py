"""
CPU 温度监控模块
通过 Core Temp 共享内存读取 CPU 温度
支持3种方案自动选择：共享内存 / coretemp库 / WMI
"""

import ctypes
import ctypes.wintypes
import logging

logger = logging.getLogger(__name__)

# Windows API 函数签名设置
_kernel32 = ctypes.windll.kernel32
_kernel32.OpenFileMappingW.restype = ctypes.wintypes.HANDLE
_kernel32.OpenFileMappingW.argtypes = [ctypes.wintypes.DWORD, ctypes.wintypes.BOOL, ctypes.wintypes.LPCWSTR]
_kernel32.MapViewOfFile.restype = ctypes.wintypes.LPVOID
_kernel32.MapViewOfFile.argtypes = [ctypes.wintypes.HANDLE, ctypes.wintypes.DWORD, ctypes.wintypes.DWORD, ctypes.wintypes.DWORD, ctypes.c_size_t]
_kernel32.UnmapViewOfFile.argtypes = [ctypes.wintypes.LPVOID]
_kernel32.UnmapViewOfFile.restype = ctypes.wintypes.BOOL
_kernel32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]
_kernel32.CloseHandle.restype = ctypes.wintypes.BOOL


class CPUMonitor:
    """CPU 温度监控器（共享内存保持映射，避免重复 Open/Close）"""

    def __init__(self):
        self._available = False
        self._method = None
        # 共享内存持久句柄
        self._shm_handle = None
        self._shm_ptr = None
        self._check_methods()

    def _check_methods(self):
        """按优先级检测可用方案"""
        # 方案1: Core Temp 共享内存（最稳定）
        if self._try_shared_memory():
            return

        # 方案2: coretemp Python 库
        if self._try_coretemp_lib():
            return

        # 方案3: WMI (OpenHardwareMonitor)
        if self._try_wmi_ohm():
            return

        logger.warning("CPU 温度监控: 无可用方案，请确保 Core Temp 正在运行")

    def _try_shared_memory(self):
        """尝试 Core Temp 共享内存（保持映射）"""
        try:
            handle = _kernel32.OpenFileMappingW(0x0004, False, "CoreTempMappingObject")
            if not handle:
                logger.debug("Core Temp 共享内存未找到（Core Temp 可能未运行或未开启共享内存）")
                return False

            ptr = _kernel32.MapViewOfFile(handle, 0x0004, 0, 0, ctypes.c_size_t(8192))
            if not ptr:
                err = _kernel32.GetLastError()
                logger.debug(f"Core Temp MapViewOfFile 失败, 错误码: {err}")
                _kernel32.CloseHandle(handle)
                return False

            # 验证数据合理性
            core_count = ctypes.c_uint.from_address(ptr + 1536).value
            if 0 < core_count < 128:
                first_temp = ctypes.c_float.from_address(ptr + 1544).value
                if 0 < first_temp < 150:
                    # 保持映射，不释放
                    self._shm_handle = handle
                    self._shm_ptr = ptr
                    self._available = True
                    self._method = 'shared_memory'
                    logger.info(f"CPU 温度监控: 使用 Core Temp 共享内存 ({core_count}核)")
                    return True

            _kernel32.UnmapViewOfFile(ptr)
            _kernel32.CloseHandle(handle)
            logger.debug("Core Temp 共享内存数据异常")

        except Exception as e:
            logger.debug(f"Core Temp 共享内存检测失败: {e}")

        return False

    def _try_coretemp_lib(self):
        """尝试 coretemp Python 库"""
        try:
            from coretemp import CoreTemp
            ct = CoreTemp()
            temps = ct.get_temp()
            if temps and len(temps) > 0:
                self._available = True
                self._method = 'coretemp_lib'
                logger.info("CPU 温度监控: 使用 coretemp 库")
                return True
        except ImportError:
            logger.debug("coretemp 库未安装")
        except Exception as e:
            logger.debug(f"coretemp 库初始化失败: {e}")
        return False

    def _try_wmi_ohm(self):
        """尝试 WMI (OpenHardwareMonitor)"""
        try:
            import wmi
            w = wmi.WMI(namespace=r"root\OpenHardwareMonitor")
            for s in w.Sensor():
                if s.SensorType == 'Temperature' and 'CPU' in s.Name:
                    self._available = True
                    self._method = 'wmi_ohm'
                    logger.info("CPU 温度监控: 使用 OpenHardwareMonitor WMI")
                    return True
        except ImportError:
            logger.debug("wmi 库未安装")
        except Exception:
            pass
        return False

    @property
    def available(self):
        return self._available

    def get_cpu_temp(self):
        """获取 CPU 温度（摄氏度），返回平均温度或 None"""
        if not self._available:
            return None
        try:
            if self._method == 'shared_memory':
                return self._read_shared_memory()
            elif self._method == 'coretemp_lib':
                return self._read_coretemp_lib()
            elif self._method == 'wmi_ohm':
                return self._read_wmi_ohm()
        except Exception as e:
            logger.debug(f"获取 CPU 温度失败: {e}")
        return None

    def _read_shared_memory(self):
        """从 Core Temp 共享内存读取温度（直接读保持的映射，无需重复 Open/Map）"""
        try:
            ptr = self._shm_ptr
            if not ptr:
                # 映射丢失，尝试重新打开
                return self._reopen_shared_memory()

            core_count = ctypes.c_uint.from_address(ptr + 1536).value
            if core_count == 0 or core_count > 128:
                return self._reopen_shared_memory()

            temps = []
            for i in range(min(core_count, 128)):
                temp = ctypes.c_float.from_address(ptr + 1544 + i * 4).value
                if temp is not None and 0 < temp < 150:
                    temps.append(temp)

            if temps:
                return round(sum(temps) / len(temps))

        except Exception as e:
            logger.debug(f"共享内存读取失败: {e}")
            return self._reopen_shared_memory()
        return None

    def _reopen_shared_memory(self):
        """重新打开共享内存（Core Temp 可能重启过）"""
        # 先清理旧映射
        if self._shm_ptr:
            try:
                _kernel32.UnmapViewOfFile(self._shm_ptr)
            except Exception:
                pass
            self._shm_ptr = None
        if self._shm_handle:
            try:
                _kernel32.CloseHandle(self._shm_handle)
            except Exception:
                pass
            self._shm_handle = None

        try:
            handle = _kernel32.OpenFileMappingW(0x0004, False, "CoreTempMappingObject")
            if not handle:
                return None
            ptr = _kernel32.MapViewOfFile(handle, 0x0004, 0, 0, ctypes.c_size_t(8192))
            if not ptr:
                _kernel32.CloseHandle(handle)
                return None

            self._shm_handle = handle
            self._shm_ptr = ptr

            core_count = ctypes.c_uint.from_address(ptr + 1536).value
            if core_count == 0 or core_count > 128:
                return None

            temps = []
            for i in range(min(core_count, 128)):
                temp = ctypes.c_float.from_address(ptr + 1544 + i * 4).value
                if temp is not None and 0 < temp < 150:
                    temps.append(temp)
            if temps:
                return round(sum(temps) / len(temps))
        except Exception as e:
            logger.debug(f"共享内存重新打开失败: {e}")
        return None

    def _read_coretemp_lib(self):
        """使用 coretemp 库读取"""
        try:
            from coretemp import CoreTemp
            ct = CoreTemp()
            temps = ct.get_temp()
            valid = [t for t in temps if t is not None and t > 0]
            if valid:
                return round(sum(valid) / len(valid))
        except Exception as e:
            logger.debug(f"coretemp 库读取失败: {e}")
        return None

    def _read_wmi_ohm(self):
        """使用 WMI 读取"""
        try:
            import wmi
            w = wmi.WMI(namespace=r"root\OpenHardwareMonitor")
            temps = []
            for s in w.Sensor():
                if s.SensorType == 'Temperature' and 'CPU' in s.Name:
                    if s.Value is not None:
                        temps.append(s.Value)
            if temps:
                return round(sum(temps) / len(temps))
        except Exception as e:
            logger.debug(f"WMI 读取失败: {e}")
        return None

    def shutdown(self):
        """释放共享内存映射"""
        if self._shm_ptr:
            try:
                _kernel32.UnmapViewOfFile(self._shm_ptr)
            except Exception:
                pass
            self._shm_ptr = None
        if self._shm_handle:
            try:
                _kernel32.CloseHandle(self._shm_handle)
            except Exception:
                pass
            self._shm_handle = None
        logger.info("CPUMonitor 已关闭")
