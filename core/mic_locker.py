"""
麦克风音量锁定模块
防止 Windows 自动调节麦克风音量
"""

import logging

logger = logging.getLogger(__name__)


class MicLocker:
    """麦克风音量锁定器"""

    def __init__(self):
        self._enabled = False
        self._volume_interface = None
        self._init_audio()

    def _init_audio(self):
        """初始化音频接口"""
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from comtypes import CLSCTX_ALL

            # 方式1: 使用 GetMicrophone()
            try:
                devices = AudioUtilities.GetMicrophone()
                if devices:
                    self._volume_interface = devices.Activate(
                        IAudioEndpointVolume._iid_, CLSCTX_ALL, None
                    )
                    logger.info("麦克风音频接口初始化成功 (GetMicrophone)")
                    return
            except Exception as e:
                logger.debug(f"GetMicrophone 方式失败: {e}")

            # 方式2: 通过设备枚举器直接枚举录音设备 (eCapture=1)
            try:
                enumerator = AudioUtilities.GetDeviceEnumerator()
                # eCapture=1 表示录音/输入设备, DEVICE_STATE_ACTIVE=0x1
                collection = enumerator.EnumAudioEndpoints(1, 0x1)
                count = collection.GetCount()
                logger.info(f"枚举录音设备: 找到 {count} 个活动设备")
                for i in range(count):
                    try:
                        device = collection.Item(i)
                        # 获取设备名称
                        dev_name = f"设备#{i}"
                        try:
                            props = device.OpenPropertyStore(0)
                            if props:
                                from pycaw.pycaw import PROPERTYKEY
                                name_prop = props.GetValue(PROPERTYKEY(
                                    PROPERTYKEY.DEVPKEY_Device_FriendlyName
                                ))
                                if name_prop:
                                    dev_name = str(name_prop)
                        except Exception:
                            pass

                        interface = device.Activate(
                            IAudioEndpointVolume._iid_, CLSCTX_ALL, None
                        )
                        if interface:
                            self._volume_interface = interface
                            logger.info(f"麦克风音频接口初始化成功 ({dev_name})")
                            return
                    except Exception as e:
                        logger.debug(f"设备#{i} 激活失败: {e}")
            except Exception as e:
                logger.debug(f"枚举录音设备方式失败: {e}")

            logger.warning("未找到可用的麦克风设备")
        except ImportError:
            logger.warning("pycaw 库未安装，麦克风锁定功能不可用")
        except Exception as e:
            logger.warning(f"麦克风音频接口初始化失败: {e}")

    @property
    def available(self):
        """麦克风锁定是否可用"""
        return self._volume_interface is not None

    @property
    def enabled(self):
        """是否启用锁定"""
        return self._enabled

    @enabled.setter
    def enabled(self, value):
        """设置是否启用锁定"""
        self._enabled = value
        if value:
            self.lock_volume()

    def get_volume(self):
        """获取当前麦克风音量 (0.0 ~ 1.0)"""
        if not self.available:
            return None
        try:
            from pycaw.pycaw import IAudioEndpointVolume
            volume = self._volume_interface.QueryInterface(IAudioEndpointVolume)
            return volume.GetMasterVolumeLevelScalar()
        except Exception as e:
            logger.debug(f"获取麦克风音量失败: {e}")
            return None

    def set_volume(self, level=1.0):
        """设置麦克风音量 (0.0 ~ 1.0)"""
        if not self.available:
            return False
        try:
            from pycaw.pycaw import IAudioEndpointVolume
            volume = self._volume_interface.QueryInterface(IAudioEndpointVolume)
            volume.SetMasterVolumeLevelScalar(level, None)
            return True
        except Exception as e:
            logger.debug(f"设置麦克风音量失败: {e}")
            return False

    def lock_volume(self):
        """锁定麦克风音量到100%"""
        if not self._enabled or not self.available:
            return
        current = self.get_volume()
        if current is not None and current < 0.99:
            self.set_volume(1.0)
            logger.debug(f"麦克风音量已锁定: {current:.2f} -> 1.0")

    def check_and_lock(self):
        """检查并锁定音量（定时调用）"""
        if not self._enabled:
            return
        # 检测 COM 对象是否失效，失效则重新初始化
        if not self._is_interface_alive():
            self._init_audio()
            if not self.available:
                return
        self.lock_volume()

    def _is_interface_alive(self):
        """检测 COM 接口是否仍然有效"""
        if self._volume_interface is None:
            return False
        try:
            from pycaw.pycaw import IAudioEndpointVolume
            volume = self._volume_interface.QueryInterface(IAudioEndpointVolume)
            _ = volume.GetMasterVolumeLevelScalar()
            return True
        except Exception:
            self._volume_interface = None
            return False
