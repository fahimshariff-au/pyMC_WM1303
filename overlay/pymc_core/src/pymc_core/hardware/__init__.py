"""
Hardware abstraction layer for PyMC_Core
"""

from .base import LoRaRadio

# Conditional import for WsRadio (requires websockets)
try:
    from .wsradio import WsRadio

    _WS_AVAILABLE = True
except ImportError:
    _WS_AVAILABLE = False
    WsRadio = None

# Conditional import for SX1262Radio (requires spidev)
try:
    from .sx1262_wrapper import SX1262Radio

    _SX1262_AVAILABLE = True
except ImportError:
    _SX1262_AVAILABLE = False
    SX1262Radio = None

# Conditional import for KissSerialWrapper (requires pyserial)
try:
    from .kiss_serial_wrapper import KissSerialWrapper

    _KISS_SERIAL_AVAILABLE = True
except ImportError:
    _KISS_SERIAL_AVAILABLE = False
    KissSerialWrapper = None

# Conditional import for KissModemWrapper (requires pyserial)
try:
    from .kiss_modem_wrapper import KissModemWrapper

    _KISS_MODEM_AVAILABLE = True
except ImportError:
    _KISS_MODEM_AVAILABLE = False
    KissModemWrapper = None

# Conditional import for WM1303Backend
try:
    from .wm1303_backend import WM1303Backend
    _WM1303_AVAILABLE = True
except ImportError:
    _WM1303_AVAILABLE = False
    WM1303Backend = None

# Conditional import for VirtualLoRaRadio
try:
    from .virtual_radio import VirtualLoRaRadio
    _VIRTUAL_AVAILABLE = True
except ImportError:
    _VIRTUAL_AVAILABLE = False
    VirtualLoRaRadio = None


__all__ = ["LoRaRadio"]

# Add WsRadio to exports if available
if _WS_AVAILABLE:
    __all__.append("WsRadio")

# Add SX1262Radio to exports if available
if _SX1262_AVAILABLE:
    __all__.append("SX1262Radio")

# Add KissSerialWrapper to exports if available
if _KISS_SERIAL_AVAILABLE:
    __all__.append("KissSerialWrapper")

# Add KissModemWrapper to exports if available
if _KISS_MODEM_AVAILABLE:
    __all__.append("KissModemWrapper")

# Add WM1303Backend to exports if available
if _WM1303_AVAILABLE:
    __all__.append("WM1303Backend")

# Add VirtualLoRaRadio to exports if available
if _VIRTUAL_AVAILABLE:
    __all__.append("VirtualLoRaRadio")
