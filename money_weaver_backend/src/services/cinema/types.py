from enum import Enum


class ShotScale(str, Enum):
    ECU = "ecu"
    CU = "cu"
    MCU = "mcu"
    MS = "ms"
    MLS = "mls"
    LS = "ls"
    ELS = "els"
    ABSTRACT = "abstract"


class CameraMove(str, Enum):
    STATIC = "static"
    PAN = "pan"
    TILT = "tilt"
    DOLLY_IN = "dolly_in"
    DOLLY_OUT = "dolly_out"
    TRACK = "track"
    HANDHELD = "handheld"
    DRONE = "drone"
    CRANE = "crane"
    ZOOM = "zoom"


class ShotFunction(str, Enum):
    ESTABLISH = "establish"
    CONTEXT = "context"
    DETAIL = "detail"
    REACTION = "reaction"
    SYMBOL = "symbol"
    TRANSITION = "transition"
    PAYOFF = "payoff"


class MontageMode(str, Enum):
    METRIC = "metric"
    RHYTHMIC = "rhythmic"
    TONAL = "tonal"
    OVERTONAL = "overtonal"
    INTELLECTUAL = "intellectual"
