import sys
import math
import json
import logging
import os
import time
import warnings
import threading
from logging.handlers import RotatingFileHandler


from PySide6.QtCore import (Qt, Signal, QObject, QTimer, QRectF, QFileInfo, QThread, QSettings, Slot, QMetaObject, QByteArray, QSize, QMimeData, QPointF, qInstallMessageHandler)
from PySide6.QtGui import QBrush, QColor, QDrag, QFont, QIcon, QLinearGradient, QPainter, QPen, QPixmap

from PySide6.QtSvg import QSvgRenderer

from PySide6.QtWidgets import (

    QApplication,
    QCheckBox,
    QFileIconProvider,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,

    QMainWindow,

    QDialog,
    QMenu,
    QPushButton,

    QProgressBar,
    QScrollArea,

    QStyle,
    QSlider,
    QStyleOptionSlider,
    QSizePolicy,
    QSplitter,
    QSplitterHandle,
    QTabWidget,

    QToolButton,

    QVBoxLayout,
    QWidget,
)


import voicemeeterlib

try:
    from pycaw.pycaw import AudioUtilities
    from pycaw.constants import EDataFlow, DEVICE_STATE
    PYCAW_AVAILABLE = True
except ImportError:
    AudioUtilities = None
    PYCAW_AVAILABLE = False

# Optional: moving an application between virtual channels (drag and drop)
# uses Windows' per-app output device setting through this small package.
# VMStreamer runs without it; dropping an application then shows a hint.
try:
    import winappaudiorouter as war
    APP_ROUTING_AVAILABLE = True
except Exception:
    war = None
    APP_ROUTING_AVAILABLE = False


# Monochrome UI icons. They are embedded as SVG so the application does not
# need extra icon files at runtime or during PyInstaller packaging.


def _svg_icon(svg, size=22):
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


# The eye artwork is derived from the user-provided reference image and
# embedded here so the application remains self-contained.
EYE_ICON_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAFAAAAA4CAYAAABqtn+aAAAACXBIWXMAAA7EAAAOxAGVKw4b"
    "AAANbUlEQVR4nO1be3Bc1X3+fr9zd2VkY/CDR0wKZCCOTTKTpPUjJS1YL6+0LzkCaxpapxgc"
    "Z2imLQRoZmoyqidAM8OzjzSY4WFIIYmMLWsfV1pJtjApSU3cdKYdwBiapKQkjd9gS7J07zm/"
    "/rFa7d2XdVeScTOjb2ZHu3f3fOc73z2P3/mdK2AWs5jFLGYxiymCzreAHLq7u5cQzVlGyroK"
    "RJcQq0th9HwYLQZ8ipgOM9MH2pifkR5+PRaLvXe+NQPn0cBEf/+VSgdjonW9iHyeSF0KMQQI"
    "AEb2Lzx/yftZQHyYldpvjBlwaCT5hZaWX3y4LShU9aHAtu35WqxbiIJfgtBqQBgiKDRJPCW8"
    "8rzXc99R7q0RcfcL4TmLxr4XDoc/OEdNKMGHYmB3d98SFQzeA202AnJxQeN9I2cgF13zmk8g"
    "xe+L6Ge14zzU2rr2V9OUPinOqYG9vb0LXVPzDQhthpjawmqlQvW5IZx77y1T/LtC87zXBRgh"
    "S20bG3bub2trPDa9llTGOTGws7NTXTBv0W1k8ACAS0qr8g7V3DAkAeQwIG9BqXdIjCOkjhnj"
    "agYWQ6kgGVwrWl8L0BLAUNZoAmh86oTx1DF+I0iOQtwtw8Mnnm5vb9cz3dYZN9C291yjhZ4m"
    "oRtL562iaklOCpAUoFdBXg2H698lokqFJrA7k/kdpdX1TFZEWMWg5WKYnHnlihOg6IfGObM5"
    "Hg8dnFLDKmAmDaSkvWcTGTwMYH75KggAG5DZBzbfYRlNhMPh0elUatt2jcYFMRJsFqEGKpwk"
    "4TVUIKeJ+a8iLTc+4edG+cGMGNjZ2TmvtnbRMwCvr9gDiDREdzOb+8Phpn+fiXqLkezd+2kY"
    "+gYZWgeIKp1nBSAFgd5p3ODG1tY/ODXdOqdtYCq1bzlIvwSR6/Lxm1c4gRT9yLjuPbFY44+n"
    "W58f7E5nVlsUfAxGfr9iExUftEjf3Nxc//p06pqWganewUZo+gHELCwKdHPvj4PNvZGWxmf9"
    "DplMJjPXcdQqInWdkCwCABI6pmnszRqF/aFQaMgPj4hQuvfl22D4IYgsKNKF7Kjgk5Cx9dFo"
    "04AfznKYsoGpnoE/haZtANWUoxNCj3GdTX5jsd2pzPUBVfOXYhDNhzy51TrbYGI1BEbKOCOP"
    "xmLNr/nh7e7rW6KcwNMQaS5d/QkgnCGWOyItddv98BVjSgYm0n2bWPgJgFXJ7oHIIciW117b"
    "98jWrVtNRZJxdNr2JbUy5+8g+KOz68nXIzAGhH8eUe5d7c3Nxyero6Ojg1etqrsbzA+INoGS"
    "eZqgIe6fRaNNT07GVU5VVUin995lDB4movHVLh/QCslh0aY9Hl+7zw9XKtW/HBToh8gVlUOe"
    "nMziwBmAZb0bIB0Khep8hSbp9J4bROgHAC4v6Y3EBha+Hg3d+LAfLq8y30inB74qwn+PiVDB"
    "O2TlP0Q76+Lx0M/9cCUSmWXMahBQl+evltt5eM0r3nkQwPi1cUfr/cZ3XT09V1tmzi4CfTaX"
    "l/DUaQB9ZzTa8A9+uLwqJ4WdGfxj7chzBFKF3wgE8kPCSGs0Gj3hh6urq+viQPCi/RBZWhon"
    "ZjnzW7pyva94QcAh5tGVfpMIqVRqAdS8XdBmTUndrDSxszHS3PBdP1w8+U+AVKq/0TiyPWte"
    "cYZEJ44eeXetX/MAIFCz4EEILS29f+PGMB0D9HYw7oNltojop4T5cOG984ZLaqnhed/yW380"
    "Gj3xs7eHm8GSKElsGKPEpWdSqf6QH65Je2AqNfgpwLwK0PzCJABD2KQ+cumFbStWrHD8ik8m"
    "+z5OHHgDAit7xduz9Kgh+psLa/nxurq6M95ytm3XCNX+hWjzTUBq8mXGX4q1xtAnW1ta3vKr"
    "5cCBA4HfHBveJVqi2a2gdzHEB0ZLXTze8NOzcZy1B3Z29l8kkC6A5xcOHQFIpxVGbq7GPAAg"
    "sv681DwAoDFhWh+PNHyr2DwACIfDo5GWNQ+JuG0CjOWH9ziPdpVlgndUo2XFihUO6dM3Q3S6"
    "MBEBQGg+W2rXrl0Di87GUdHAjo4Orr0w+AKBrs1fzZlofnTk8H/fXO0+dnBw0AJRWyEfAAiE"
    "nAdj4YbkZByx2FqbFX8TVDxfAgK6qaOjw6pGUzgcHmU6c5OI7M2PrnFug6tq5vCLZ+OsaOCq"
    "VdffDe1GisMLIT5ojGrduHFjSS+ZDKdOjX4C4CtKFg7ikyND1iN+eSweewxEJyfKT7z4o59d"
    "vXpptbrC4fCo46AdrN4o1GYgRtauXHnD1yuVLWtgKtW/XFBzf/aTZwVkOkbitsXjdUerFQkA"
    "gTlzlham8LP8RMi0t9ed9ssTCoWGILqnJC4UA5bA8qloa2trPKbItIFwJKdrgpu4w7YHritX"
    "rkIP5AiAYGEYYcSIe2s02vTmVAQCgNa0sEQcAIF5p2oygifeLLghC6amDmhpqX8LbDYAYvL6"
    "CBAKGPC6cmXKGsiWJeXiLQVR5X7vG9pBdrL2zl8Epawp5OZEShMY08/OkTEBjG+S/aCsgaKd"
    "JCBOYQDLJBR8JtW/b0pDBADI4vGh7xFHDF2wUPmDCH0sv3J6G2v5jkeLkUr1LxdS2/NnBOMv"
    "Mq4ruuwCV9bASKTxEMT5a2/MBxBgZCEc7EwkBhdPRSALDhYGw5TtSI4TymQyc/3yPP98Zi6h"
    "XHYFYNFvTEVbIpFYLFC7YGRRni83t47dty7S9J/lylVchX/yk395lNhKFv7EAMZdzqx32LZd"
    "U6lsJTQ3171NjF+WbtlogaMDd/vlWbiQvgbBwpIvCO8ND584VK0u27ZrmGt3EGRZsTZh6olE"
    "Qg9VKlvRwK1bt5qhgLMBFr3tJRzfOq0xNHdntSYSkQHQVZocYADWllTPvvhkHIn0QBSw7itM"
    "NgCAgUDvrPbkzbbtGiNzdgK0pnTfLe+MBNwvjusui7PuRNqbmt7XoyNhQB8vyYQYigjPe+nA"
    "gQOBagQbd/QfAeMWcAGAMUFo3ZlM999b7sbYtl2TTA58TUF2ABIsISa4DHy7Gi0HDhwIaKn5"
    "PgSR0rMT8z5g4u1NTe+fjcPXUtOdztxgIZARoTklWzpGYvj00fXt7e1jfoWn7L3/BFF3ZGNC"
    "FPIBIMs6DNEJEfMWERkxWAridTByWcmWKxunAWyejLbUf8Wvhs7OzmDtvEU7YBCf4JkIq2gM"
    "4oRisaaXJ+Pxve6ne/feIkY9B2Oskt5o0SBcvika/UNfK2AqlVpAgYv+TVz9sdJnY/JDsjTJ"
    "WpwJGr9K9F8iwyv9ZoQGBwfnnR7WL5JQrJBXAIIrJLfGwo0v+OGqMqHat0HEehYFS2kusal/"
    "agL6C/Gmpnf9cGUyg8scVwYhuexwjqtc8hQoPunLXRPRh4lG10SjUV8Bfndf3xJ21G4SrCz8"
    "hgBAM+vbwuGm5/1weZX4Rrpnz61i+CkIxk30NIzpVwbmlni43ldKP5HJLGNdkwHoyqxn5Xrd"
    "WaQT3mPSa8PhRl+hS6JnYCVrvATQlaVnxqSJZFMk0rDdpwAAPhOqXkRaGrYL3C8DKFoICDBY"
    "osjqT9mDd3Z0dEzKHQ+FDhpXfo8D6gVMTG7FvcyL3BwlBowXxkbHftePeSJCKbt/M2u8AqCM"
    "eaKF9JerNa+SSl9I9eyNw/D3skeQRTREIkAqoM58pbm5+dd++Gy7/3MC606AogKam09weg7o"
    "mYYEJkkij0ci9fv98HZ3d1/G1rwnSKgVkKItmgCQYUDfHo2Gvu+HrxjT2jx2232fVxLcCdBl"
    "E/tvb9Za8XEyzt3hcP1z1Rysa1irtcY1ZOQjYAbA/yvkHBJn5LV4PD7sUx4lk/0biOgRAIsr"
    "NPWIKNMea5l8ta1YyVQL5tDTM3i1htoNrT+dv1p0AET8itH6rsnS4zOFdLrvMwL1KAR1Zea6"
    "nMLXmUxbJNJY9c7Fi+mnLwAkEolaUvOfINCG/EJQtHoyuxDp0uT8bes5ergokej9JKvAFgit"
    "B6Qoi+wZGSQ7tHv69tbW1vP/cJEX6d6XN4rrPo6JAyhvNbmVmg2gB0nkO0NDR5PVBODlsG3b"
    "tsBHr/p4WIxsFo3m7IF/xdniFJHcGw43PPn/6vE2L2x7zzUG6ikYrCk9KC/SzHycWFIQ3aud"
    "oVdjsdgvfTSMbNu+QiRwvYBbIBQFsLh0qBbVS/KKGL0pFlv79tRbV559xtHZ2alqaxfeCuIH"
    "IHRZ/pviHUeu0QbZvJb8BkSHQPxzZoy4rhxnAGBZALKCJOZaESwFcDlEKM9V7omG8fqIjjCZ"
    "LadPH3vmt+IRXy+6urouDsxZuEWM+SqJuaBwq1aS+UDpsPeu7Fz0+2LpRSYSjzDj20aferCa"
    "Q/9qcU4NzKGvr2/JmKPuAVm3QzA/v/+ttNedSoo+1yHlJAhPact5rHXtb/m/ORQjlUotQGDe"
    "F+HInwj0asoGeSjsmWfrZd7em3+oXMCGWPZD0Xdr2HmxaZIU1EziQzXQi66unqsDNcEYQTWB"
    "+XOiZTFEe+a1onT9xL8yCEAkYBwlyL/CuBmtJRmP+0tizDTOm4HFSCaTVygV/ISIdZUhuoTY"
    "mgvIXBgjIhiCkmGATxjt/iJAY2+Gw+H/Od+aZzGLWcxiFrOYFv4P3gbXzUDddIIAAAAASUVO"
    "RK5CYII="
)


def reference_eye_icon(size=20):
    pixmap = QPixmap()
    pixmap.loadFromData(
        QByteArray.fromBase64(EYE_ICON_PNG_B64.encode("ascii")),
        "PNG",
    )
    if pixmap.isNull():
        return mono_icon("eye", size)
    return QIcon(
        pixmap.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    )


MONO_ICONS = {
    "eye": """
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"
             viewBox="0 0 24 24">
          <path d="M2.2 12s3.7-6.1 9.8-6.1S21.8 12 21.8 12
                   18.1 18.1 12 18.1 2.2 12 2.2 12Z"
                fill="none" stroke="#d7e1eb" stroke-width="1.8"
                stroke-linecap="round" stroke-linejoin="round"/>
          <circle cx="12" cy="12" r="3.2"
                  fill="none" stroke="#d7e1eb" stroke-width="1.8"/>
        </svg>
    """,
    "mic": """
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"
             viewBox="0 0 24 24">
          <rect x="8.2" y="3.2" width="7.6" height="11.6" rx="3.8"
                fill="none" stroke="#d7e1eb" stroke-width="1.8"/>
          <path d="M5.5 11.5v1.1a6.5 6.5 0 0 0 13 0v-1.1
                   M12 19.1v2.1 M8.5 21.2h7"
                fill="none" stroke="#d7e1eb" stroke-width="1.8"
                stroke-linecap="round"/>
        </svg>
    """,
    "game": """
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"
             viewBox="0 0 24 24">
          <path d="M7.1 8h9.8c2.1 0 3.6 1.5 4.2 3.5l1.1 4.1
                   c.5 1.9-.6 3.3-2.2 3.3-1 0-1.7-.5-2.4-1.4l-1.5-2H7.9l-1.5 2
                   c-.7.9-1.4 1.4-2.4 1.4-1.6 0-2.7-1.4-2.2-3.3l1.1-4.1
                   C3.5 9.5 5 8 7.1 8Z"
                fill="none" stroke="#d7e1eb" stroke-width="1.7"
                stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M7 11v4 M5 13h4 M15.8 12.2h.1 M18.1 14.3h.1"
                fill="none" stroke="#d7e1eb" stroke-width="1.8"
                stroke-linecap="round"/>
        </svg>
    """,
    "chat": """
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"
             viewBox="0 0 24 24">
          <path d="M4.2 5.2h15.6c1 0 1.8.8 1.8 1.8v8.1c0 1-.8 1.8-1.8 1.8H11l-4.2 3v-3H4.2
                   c-1 0-1.8-.8-1.8-1.8V7c0-1 .8-1.8 1.8-1.8Z"
                fill="none" stroke="#d7e1eb" stroke-width="1.7"
                stroke-linejoin="round"/>
          <path d="M7 10.5h10 M7 13.5h7"
                fill="none" stroke="#d7e1eb" stroke-width="1.6"
                stroke-linecap="round"/>
        </svg>
    """,
    "media": """
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"
             viewBox="0 0 24 24">
          <path d="M9 18.1V6.2l10-2.1v11.9"
                fill="none" stroke="#d7e1eb" stroke-width="1.8"
                stroke-linecap="round" stroke-linejoin="round"/>
          <circle cx="6.4" cy="18.3" r="2.8"
                  fill="none" stroke="#d7e1eb" stroke-width="1.8"/>
          <circle cx="16.4" cy="16.2" r="2.8"
                  fill="none" stroke="#d7e1eb" stroke-width="1.8"/>
        </svg>
    """,
}


def mono_icon(name, size=22):
    return _svg_icon(MONO_ICONS[name], size)


# Qt can emit a harmless font warning from an internal style/font fallback
# even though the application explicitly uses a valid point-sized base font.
# Filter only this exact warning; all other Qt messages remain untouched.
def _qt_message_handler(mode, context, message):
    if message == "QFont::setPointSize: Point size <= 0 (-1), must be greater than 0":
        return
    log.warning(f"Qt: {message}")


log = logging.getLogger("vmstreamer")


def log_file_path():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "VMStreamer", "vmstreamer.log")


def setup_logging():
    """Log to a small rotating file and, when there is one, the console.

    The packaged build is windowed: it has no console, so print() output and
    uncaught exceptions would otherwise be lost.
    """
    log.setLevel(logging.INFO)
    handlers = []
    try:
        path = log_file_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        handlers.append(
            RotatingFileHandler(
                path, maxBytes=512_000, backupCount=2, encoding="utf-8"
            )
        )
    except OSError:
        pass
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    for handler in handlers:
        handler.setFormatter(formatter)
        log.addHandler(handler)

    def log_uncaught(exc_type, exc_value, exc_traceback):
        log.critical(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    def log_uncaught_in_thread(args):
        log.critical(
            f"Uncaught exception in thread {getattr(args.thread, 'name', '?')}",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = log_uncaught
    threading.excepthook = log_uncaught_in_thread


# VoiceMeeter strip indexes

STRIPS = {
    "Mic": 0,
    "Game": 5,
    "Chat": 6,
    "Media": 7,
}

# The Mic strip is the only strip with processing controls and a VU meter.
MIC_STRIP = STRIPS["Mic"]

# Hide/unhide scope meaning "every virtual channel".
ALL_CHANNELS = "*"

# Drag and drop of an application between channel columns.
DRAG_MIME = "application/x-vmstreamer-application"

# Mic strip: meters sit to the left of the (centered) fader.
MIC_METER_GAP = 47      # pixels between the meters and the fader
MIC_METER_SPACING = 6   # pixels between the two meters

# Mixer layout dimensions — adjust these when fine-tuning the UI.
# The mixer and the lower panels share the window height through a
# draggable splitter, so these are minimums and starting sizes, not fixed sizes.
MIXER_CARD_MIN_HEIGHT = 340
DEFAULT_MIXER_PANE_HEIGHT = 655
CHANNEL_HEADER_HEIGHT = 58
CHANNEL_FADER_MIN_HEIGHT = 100
FADER_TO_GAIN_GAP = 5
MIXER_BUTTON_HEIGHT = 28
ROUTING_LABEL_HEIGHT = 14
ROUTING_BUTTON_HEIGHT = 28
APPLICATION_PANEL_HEIGHT = 300
APPLICATION_PANEL_MIN_HEIGHT = 140

STRIP_COLORS = {
    "Mic": {"accent": "#35c8ff", "border": "#24566b", "header": "#102b38"},
    "Game": {"accent": "#ff626b", "border": "#69353c", "header": "#321c22"},
    "Chat": {"accent": "#a68aff", "border": "#504273", "header": "#241e37"},
    "Media": {"accent": "#24d6a0", "border": "#236450", "header": "#102a24"},
}


class VMEventBridge(QObject):

    """
    Bridges VoiceMeeter's background event thread
    to Qt's main thread.
    """

    event_received = Signal(str)


class VMObserver:
    """Receives VoiceMeeter API events."""

    def __init__(self, bridge):
        self.bridge = bridge

    def on_update(self, event):
        # Mic levels are sampled by MicLevelWorker, so level events are not
        # forwarded to the GUI thread at all. Never read levels here: this
        # runs on VoiceMeeter's own update thread.
        if event != "ldirty":
            self.bridge.event_received.emit(event)


class VUMeter(QProgressBar):

    """Simple vertical VU meter."""

    def __init__(self):
        super().__init__()


        self.setOrientation(Qt.Orientation.Vertical)

        # Keep the progress-bar value itself in dBFS. 0 dBFS is the top.
        # The previous build used -60..12 and then normalized the dB value
        # into that range a second time, which made the visual position wrong.
        self.setRange(-60, 0)

        self.setValue(-60)


        self.setTextVisible(False)

        self.setMinimumWidth(28)
        self.setMaximumWidth(28)

        # Height is flexible: the Mic meters follow the fader length.
        self.setMinimumHeight(40)


        # Vertical meters should rise from the bottom as the signal increases.
        self.setInvertedAppearance(False)
        self._display_level = float(self.minimum())
        self._target_level = float(self.minimum())
        self._last_animation = time.monotonic()


    def paintEvent(self, event):
        """Draw a bottom-up meter with color thresholds fixed to dB scale."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        outer = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(QColor("#303a45"), 1))
        painter.setBrush(QColor("#111820"))
        painter.drawRoundedRect(outer, 5, 5)

        inner = outer.adjusted(2, 2, -2, -2)
        span = max(1, self.maximum() - self.minimum())
        fraction = max(0.0, min(1.0, (self.value() - self.minimum()) / span))
        filled_height = inner.height() * fraction
        if filled_height <= 0:
            painter.end()
            return

        gradient = QLinearGradient(0, inner.bottom(), 0, inner.top())
        # Anchor the warning colors to dBFS values rather than normalized
        # bar height, so 0 dBFS remains the red/clipping threshold.
        def db_position(db):
            return max(0.0, min(1.0, (db - self.minimum()) / span))

        gradient.setColorAt(db_position(-60), QColor("#27c76f"))
        gradient.setColorAt(db_position(-18), QColor("#54db39"))
        gradient.setColorAt(db_position(-10.8), QColor("#a5e52b"))
        gradient.setColorAt(db_position(-6), QColor("#f5df27"))
        gradient.setColorAt(db_position(-2.4), QColor("#ff9637"))
        gradient.setColorAt(db_position(0), QColor("#ff514b"))
        gradient.setColorAt(1.00, QColor("#ff514b"))

        fill = QRectF(
            inner.left(),
            inner.bottom() - filled_height,
            inner.width(),
            filled_height,
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.fillRect(fill, QBrush(gradient))
        painter.end()


    def set_level(self, level):
        """Set the latest target level from the audio worker."""
        try:
            level = float(level)
        except (TypeError, ValueError):
            level = float(self.minimum())

        minimum = float(self.minimum())

        if level <= -199.0:
            target = minimum
            self.setToolTip("-∞ dB")
        else:
            target = max(minimum, min(0.0, level))
            self.setToolTip(f"{level:.1f} dB")

        self._target_level = target

    def _update_visual_level(self, display):
        """Apply the current animated dB level to the meter widget."""
        minimum = float(self.minimum())
        display = max(minimum, min(0.0, float(display)))
        self._display_level = display

        # The widget range is already dBFS, so do not normalize and then
        # convert back into the progress-bar range. Write the displayed dB
        # directly. paintEvent() converts that dB value to a fill fraction.
        self.setValue(int(round(display)))

    def animate_level(self):
        """Smoothly animate the displayed level toward the latest sample."""
        now = time.monotonic()
        elapsed = min(now - self._last_animation, 0.05)
        self._last_animation = now

        minimum = float(self.minimum())
        display = float(self._display_level)
        target = float(self._target_level)

        # Fast attack so short mic taps are visible immediately without
        # stepping from one 33 ms sample directly to another.
        if target > display:
            attack_speed = 500.0
            display += attack_speed * elapsed
            if display > target:
                display = target

        # Controlled release. A continuous worker sample means we no longer
        # need an event-timeout to force the meter down.
        elif target < display:
            release_speed = 110.0
            display -= release_speed * elapsed
            if display < target:
                display = target

        if display < minimum:
            display = minimum
        elif display > 0.0:
            display = 0.0

        self._display_level = display
        self._update_visual_level(display)

class NumericEdit(QLineEdit):
    """Editable numeric field that selects its contents when focused."""

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.selectAll()


# How each kind of Mic processing value is shown next to its slider.
# "time" values switch between ms and s, see format_parameter().
PARAMETER_FORMATS = {
    "plain": "{:.1f}",
    "fine": "{:.2f}",
    "ratio": "{:.1f}:1",
    "gain": "{:+.1f} dB",
    "db": "{:.1f} dB",
    "hz": "{:.0f} Hz",
}


def format_parameter(kind, actual):
    """Return the display text for a processing value in VoiceMeeter units."""
    if kind == "time":
        if actual >= 1000:
            return f"{actual / 1000:.2f} s"
        return f"{actual:.1f} ms"
    return PARAMETER_FORMATS[kind].format(actual)


def parse_parameter(kind, text):
    """Return the value the user typed, in VoiceMeeter units (time in ms)."""
    # The displayed units are accepted as well as a bare number, for example
    # "4:1", "-18 dB", "500 Hz", "150 ms" or "1.5 s".
    value = text.strip().lower()
    if kind == "ratio":
        value = value.replace(":1", "").strip()
    elif kind in ("gain", "db"):
        value = value.replace("db", "").strip()
    elif kind == "hz":
        value = value.replace("hz", "").strip()
    elif kind == "time":
        if value.endswith("ms"):
            value = value[:-2].strip()
        elif value.endswith("s"):
            return float(value[:-1].strip()) * 1000.0
    return float(value)


class ProcessingPanel(QWidget):
    """Sliders with editable value fields for one Mic processing block.

    Subclasses describe their block. Every control maps directly to the
    matching VoiceMeeter parameter of the Mic strip.
    """

    LABEL = ""        # name used in log messages
    ATTRIBUTE = ""    # voicemeeterlib attribute on the strip
    SCRIPT_NAME = ""  # VoiceMeeter script name, used for SCRIPT_KEYS
    # (label, key, slider minimum, slider maximum, scale, kind)
    PARAMETERS = ()
    # Timing parameters. The generic float setter can trigger a native access
    # violation for these with some VoiceMeeter/Python combinations, so they
    # are sent through VoiceMeeter's own script parser. Do not replace this.
    SCRIPT_KEYS = ()

    def __init__(self, vm):
        super().__init__()
        self.vm = vm
        self.target = getattr(vm.strip[MIC_STRIP], self.ATTRIBUTE)
        self.setVisible(False)
        self.controls = {}

        self.panel_layout = QVBoxLayout(self)
        self.panel_layout.setContentsMargins(6, 6, 6, 6)
        grid = QGridLayout()
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(6)
        for row, parameter in enumerate(self.PARAMETERS):
            self.add_slider(grid, row, *parameter)
        self.panel_layout.addLayout(grid)

        self.build_extras()
        self.sync_from_voicemeeter()

    def build_extras(self):
        """Add controls that are not sliders. Nothing by default."""

    def sync_extras(self):
        """Synchronize the controls added by build_extras()."""

    def add_slider(self, grid, row, name, key, minimum, maximum, scale, kind):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        name_label = QLabel(name)
        name_label.setMinimumWidth(76)

        value_edit = NumericEdit()
        value_edit.setAlignment(Qt.AlignmentFlag.AlignRight)
        value_edit.setFixedWidth(74)
        value_edit.setToolTip("Click and type a value, then press Enter.")
        value_edit.editingFinished.connect(
            lambda k=key: self.on_value_edit_finished(k)
        )

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setMinimumWidth(36)
        slider.valueChanged.connect(
            lambda value, k=key: self.on_slider_changed(k, value)
        )

        layout.addWidget(name_label)
        layout.addWidget(slider, 1)
        layout.addWidget(value_edit)
        grid.addWidget(container, row, 0)

        self.controls[key] = {
            "slider": slider,
            "edit": value_edit,
            "scale": scale,
            "kind": kind,
            "minimum": minimum / scale,
            "maximum": maximum / scale,
        }

    def format_actual(self, key, actual):
        return format_parameter(self.controls[key]["kind"], actual)

    def set_parameter(self, key, actual):
        """Set a parameter through the safest API path."""
        if key in self.SCRIPT_KEYS:
            try:
                self.vm.sendtext(
                    f"Strip[{MIC_STRIP}].{self.SCRIPT_NAME}."
                    f"{key.capitalize()}={actual:.6f}"
                )
            except OSError:
                # VoiceMeeter's native call can raise a Windows
                # access-violation exception after the command has already
                # been accepted, so this is not an invalid user value. The
                # next pdirty event brings the authoritative value back.
                pass
            return

        setattr(self.target, key, actual)

    def _set_slider(self, key, actual):
        control = self.controls[key]
        slider = control["slider"]
        slider.blockSignals(True)
        slider.setValue(int(round(actual * control["scale"])))
        slider.blockSignals(False)

    def on_value_edit_finished(self, key):
        control = self.controls[key]
        edit = control["edit"]
        try:
            actual = parse_parameter(control["kind"], edit.text())
            if not math.isfinite(actual):
                raise ValueError("Value must be finite.")
            if actual < control["minimum"] or actual > control["maximum"]:
                raise ValueError(
                    f"Value must be between {control['minimum']:g} "
                    f"and {control['maximum']:g}."
                )
            self._set_slider(key, actual)
            edit.setText(self.format_actual(key, actual))
            self.set_parameter(key, actual)
        except Exception as e:
            log.error(
                f"Invalid {self.LABEL} {key} value: {type(e).__name__}: {e}"
            )
            # Restore the current VoiceMeeter value instead of leaving an
            # invalid value in the field.
            try:
                edit.setText(
                    self.format_actual(key, getattr(self.target, key))
                )
            except Exception:
                pass

    def on_slider_changed(self, key, value):
        actual = value / self.controls[key]["scale"]
        self.controls[key]["edit"].setText(self.format_actual(key, actual))
        try:
            self.set_parameter(key, actual)
        except Exception as e:
            log.error(
                f"Failed to set {self.LABEL} {key}: {type(e).__name__}: {e}"
            )

    def sync_from_voicemeeter(self):
        """Synchronize every control from VoiceMeeter."""
        try:
            values = {
                key: getattr(self.target, key)
                for key in self.controls
            }
            for key, actual in values.items():
                self._set_slider(key, actual)
                # Do not overwrite text while the user is typing in the field.
                edit = self.controls[key]["edit"]
                if not edit.hasFocus():
                    edit.setText(self.format_actual(key, actual))
            self.sync_extras()
        except Exception as e:
            log.error(
                f"Failed to synchronize {self.LABEL}: {type(e).__name__}: {e}"
            )


class CompressorControl(ProcessingPanel):
    """Compressor controls for the Mic strip (mic.comp)."""

    LABEL = "compressor"
    ATTRIBUTE = "comp"
    SCRIPT_NAME = "Comp"
    # VoiceMeeter ranges: knob 0..10, gains -24..24 dB, ratio 1..8,
    # threshold -40..-3 dB, attack 0..200 ms, release 0..5000 ms, knee 0..1.
    PARAMETERS = (
        ("Amount", "knob", 0, 100, 10, "plain"),
        ("Input Gain", "gainin", -240, 240, 10, "gain"),
        ("Ratio", "ratio", 10, 80, 10, "ratio"),
        ("Threshold", "threshold", -400, -30, 10, "db"),
        ("Attack", "attack", 0, 2000, 10, "time"),
        ("Release", "release", 0, 50000, 10, "time"),
        ("Knee", "knee", 0, 100, 100, "fine"),
        ("Output Gain", "gainout", -240, 240, 10, "gain"),
    )
    SCRIPT_KEYS = ("attack", "release")

    def build_extras(self):
        self.makeup_checkbox = QCheckBox("Auto Makeup")
        self.makeup_checkbox.stateChanged.connect(self.on_makeup_changed)
        self.panel_layout.addWidget(
            self.makeup_checkbox,
            alignment=Qt.AlignmentFlag.AlignLeft,
        )

    def sync_extras(self):
        makeup = self.target.makeup
        self.makeup_checkbox.blockSignals(True)
        self.makeup_checkbox.setChecked(makeup)
        self.makeup_checkbox.blockSignals(False)

    def on_makeup_changed(self, state):
        enabled = state == Qt.CheckState.Checked.value
        try:
            self.target.makeup = enabled
        except Exception as e:
            log.error(
                f"Failed to set compressor makeup: {type(e).__name__}: {e}"
            )


class GateControl(ProcessingPanel):
    """Gate controls for the Mic strip (mic.gate)."""

    LABEL = "gate"
    ATTRIBUTE = "gate"
    SCRIPT_NAME = "Gate"
    PARAMETERS = (
        ("Amount", "knob", 0, 100, 10, "plain"),
        ("Threshold", "threshold", -600, -100, 10, "db"),
        ("Damping", "damping", -600, -100, 10, "db"),
        ("Sidechain", "bpsidechain", 100, 4000, 1, "hz"),
        ("Attack", "attack", 0, 10000, 10, "time"),
        ("Hold", "hold", 0, 50000, 10, "time"),
        ("Release", "release", 0, 50000, 10, "time"),
    )
    SCRIPT_KEYS = ("attack", "hold", "release")


class DenoiserControl(ProcessingPanel):
    """Denoiser control for the Mic strip (mic.denoiser)."""

    LABEL = "denoiser"
    ATTRIBUTE = "denoiser"
    PARAMETERS = (
        ("Amount", "knob", 0, 100, 10, "plain"),
    )


class FineControlSlider(QSlider):
    """Slider with predictable, one-step-per-wheel-notch adjustments."""

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self._wheel_remainder = 0

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if not delta:
            event.ignore()
            return

        self._wheel_remainder += delta
        notches = int(self._wheel_remainder / 120)
        if notches:
            self._wheel_remainder -= notches * 120
            self.setValue(self.value() + notches * self.singleStep())
        event.accept()


class MicFaderArea(QWidget):
    """Mic fader and meters.

    The fader is centered with the same stretch layout the other strips use,
    so it lines up exactly with the gain readout and the other faders. The two
    input meters are positioned relative to the fader instead of being part of
    the layout, so they can never push the fader off center.
    """

    def __init__(self, fader, meters):
        super().__init__()
        self.fader = fader
        self.meters = list(meters)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addStretch(1)
        row.addWidget(fader)
        row.addStretch(1)

        for meter in self.meters:
            meter.setParent(self)

        self.setMinimumHeight(CHANNEL_FADER_MIN_HEIGHT)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place_meters()

    def showEvent(self, event):
        super().showEvent(event)
        self._place_meters()

    def _place_meters(self):
        if not self.meters:
            return
        self.layout().activate()
        widths = [meter.maximumWidth() for meter in self.meters]
        total = sum(widths) + MIC_METER_SPACING * (len(widths) - 1)
        x = max(0, self.fader.x() - MIC_METER_GAP - total)
        y = self.fader.y()
        height = self.fader.height()
        for meter, width in zip(self.meters, widths):
            meter.setGeometry(x, y, width, height)
            meter.show()
            x += width + MIC_METER_SPACING


class StripWidget(QWidget):

    def __init__(
        self,
        name,
        vm,
        strip_index,
    ):
        super().__init__()

        self.vm = vm
        self.name = name

        self.strip_index = strip_index

        # VoiceMeeter can emit pdirty with the previous value while a fader
        # write is still being applied. Briefly keep the user's local edit
        # visible instead of snapping the fader back during that round trip.
        self._last_local_gain_change = 0.0

        self.strip = vm.strip[strip_index]


        colors = STRIP_COLORS.get(name, STRIP_COLORS["Mic"])
        accent = colors["accent"]
        border = colors["border"]
        header_color = colors["header"]
        self.setObjectName("mixerStripCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "QWidget#mixerStripCard {"
            f"background-color: #111923; border: 1px solid {border}; "
            "border-radius: 8px; }"
        )

        self.setMinimumWidth(0)


        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(1)


        # Two-line source header, following VoiceMeeter's input cards.
        source_names = {
            "Mic": "Stereo Input 1",
            "Game": "VAIO",
            "Chat": "VAIO AUX",
            "Media": "VAIO3",
        }
        source_icons = {
            "Mic": "mic",
            "Game": "game",
            "Chat": "chat",
            "Media": "media",
        }
        strip_header = QWidget()
        strip_header.setStyleSheet(
            f"background: {header_color}; border: 1px solid {border}; "
            "border-radius: 6px;"
        )
        strip_header_layout = QHBoxLayout(strip_header)
        strip_header_layout.setContentsMargins(6, 2, 6, 2)
        strip_header_layout.setSpacing(5)
        strip_header_layout.addStretch(1)
        icon_label = QLabel()
        icon_label.setFixedSize(24, 24)
        icon_label.setPixmap(
            mono_icon(source_icons.get(name, "mic"), 22).pixmap(22, 22)
        )
        icon_label.setStyleSheet(
            "background: transparent; border: none;"
        )
        strip_header_layout.addWidget(icon_label)
        title_stack = QVBoxLayout()
        title_stack.setContentsMargins(0, 0, 0, 0)
        title_stack.setSpacing(0)
        self.name_label = QLabel(name)
        self.name_label.setStyleSheet(
            f"color: {accent}; background: transparent; border: none; "
            "font-size: 14px; font-weight: bold;"
        )
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        source_label = QLabel(source_names.get(name, ""))
        source_label.setStyleSheet(
            "color: #9bb0c3; background: transparent; border: none; "
            "font-size: 10px;"
        )
        source_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_stack.addWidget(self.name_label)
        title_stack.addWidget(source_label)
        strip_header_layout.addLayout(title_stack)
        strip_header_layout.addStretch(1)
        strip_header.setFixedHeight(CHANNEL_HEADER_HEIGHT)
        layout.addWidget(strip_header)
        layout.addSpacing(8)


        # Mic signal meters. They are placed relative to the fader (see
        # MicFaderArea) so they can never push the fader off center.
        self.vu_meters = [VUMeter(), VUMeter()] if name == "Mic" else []
        self.vu_meter = self.vu_meters[0] if self.vu_meters else None

        # Fader

        self.fader = FineControlSlider(
            Qt.Orientation.Vertical
        )
        self.fader.setRange(
            -6000,

            1200,

        )
        # VoiceMeeter accepts fractional dB values. Keep the fader's fine
        # keyboard/wheel increment at 0.01 dB, with Page Up/Down at 0.10 dB.
        self.fader.setSingleStep(1)
        self.fader.setPageStep(10)
        self.fader.setToolTip(
            "Fine adjustment: use the arrow keys or mouse wheel (0.01 dB). "
            "Page Up/Down changes 0.10 dB."
        )

        self.fader.setMinimumHeight(CHANNEL_FADER_MIN_HEIGHT)
        self.fader.setStyleSheet(
            "QSlider::groove:vertical { background: #30363d; width: 8px; "
            "border-radius: 4px; }"
            f"QSlider::handle:vertical {{ background: {accent}; height: 22px; "
            "margin: 0 -7px; border-radius: 5px; }"
        )

        self.fader.setValue(

            int(
                self.strip.gain
                * 100
            )
        )

        self.fader.valueChanged.connect(
            self.on_fader_changed

        )


        if self.vu_meter is not None:
            # The fader is centered in the card exactly like the other
            # strips; the two input meters sit to its left.
            layout.addWidget(MicFaderArea(self.fader, self.vu_meters), 1)
        else:
            control_layout = QHBoxLayout()
            control_layout.setContentsMargins(0, 0, 0, 0)
            control_layout.addStretch(1)
            control_layout.addWidget(self.fader)
            control_layout.addStretch(1)
            layout.addLayout(control_layout, 1)


        # Gain readout
        layout.addSpacing(FADER_TO_GAIN_GAP)

        self.gain_label = QLabel()


        self.gain_label.setAlignment(

            Qt.AlignmentFlag.AlignCenter

        )
        if self.vu_meter is not None:
            self.gain_label.setStyleSheet(
                "color: #aebdca; font-size: 12px;"
            )
        else:
            self.gain_label.setStyleSheet(
                "color: #aebdca; font-size: 12px;"
            )


        self.update_gain_label()


        layout.addWidget(
            self.gain_label
        )


        # Buttons

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(5)


        self.mute_button = QPushButton(

            "MUTE"

        )
        self.mute_button.setFixedHeight(MIXER_BUTTON_HEIGHT)

        self.solo_button = QPushButton(

            "SOLO"

        )
        self.solo_button.setFixedHeight(MIXER_BUTTON_HEIGHT)

        self.mono_button = QPushButton(

            "MONO"

        )
        self.mono_button.setFixedHeight(MIXER_BUTTON_HEIGHT)

        self.mute_button.setCheckable(
            True
        )
        self.solo_button.setCheckable(
            True
        )
        self.mono_button.setCheckable(
            True
        )

        self.mute_button.clicked.connect(
            self.on_mute_clicked
        )
        self.solo_button.clicked.connect(
            self.on_solo_clicked
        )
        self.mono_button.clicked.connect(
            self.on_mono_clicked
        )

        button_layout.addWidget(
            self.mute_button
        )
        button_layout.addWidget(
            self.solo_button
        )
        button_layout.addWidget(
            self.mono_button
        )

        layout.addLayout(
            button_layout
        )

        layout.addSpacing(8)

        routing_title = QLabel("ROUTING")
        routing_title.setFixedHeight(ROUTING_LABEL_HEIGHT)
        routing_title.setStyleSheet(
            "color: #8ba0b5; font-size: 11px; font-weight: bold;"
        )
        layout.addWidget(routing_title)
        layout.addSpacing(2)
        routing_layout = QGridLayout()
        routing_layout.setContentsMargins(0, 0, 0, 0)
        routing_layout.setHorizontalSpacing(5)
        routing_layout.setVerticalSpacing(2)
        self.route_buttons = {}
        if self.name == "Mic":
            self._add_route_button(routing_layout, "B1", 0, 0, accent)
        else:
            for column, output in enumerate(("A1", "A2", "A3")):
                self._add_route_button(routing_layout, output, 0, column, accent)
        layout.addLayout(routing_layout)


        # Initial synchronization

        self.sync_from_voicemeeter()

    def _add_route_button(self, layout, output, row, column, accent):
        button = QPushButton(output)
        button.setCheckable(True)
        button.setFixedHeight(ROUTING_BUTTON_HEIGHT)
        button.setStyleSheet(
            f"QPushButton:checked {{ background: #102b25; color: {accent}; "
            f"border: 2px solid {accent}; font-weight: bold; }}"
        )
        button.clicked.connect(
            lambda checked, name=output: self.on_route_clicked(name, checked)
        )
        layout.addWidget(button, row, column)
        self.route_buttons[output] = button

    def on_route_clicked(self, output, checked):
        try:
            setattr(self.strip, output, bool(checked))
        except Exception as exc:
            log.error(
                f"Failed to set {self.name} route {output}: "
                f"{type(exc).__name__}: {exc}"
            )
            self.sync_routes()

    def sync_routes(self):
        for output, button in self.route_buttons.items():
            try:
                button.blockSignals(True)
                button.setChecked(bool(getattr(self.strip, output)))
            except Exception:
                pass
            finally:
                button.blockSignals(False)


    def update_gain_label(self):

        gain = self.fader.value() / 100

        self.gain_label.setText(
            f"{gain:+.2f} dB"
        )

    def on_fader_changed(self, value):
        gain = value / 100
        self._last_local_gain_change = time.monotonic()

        try:
            self.strip.gain = gain
        except Exception as e:
            log.error(
                f"Failed to set {self.name} gain: "
                f"{type(e).__name__}: {e}"
            )
            return

        self.update_gain_label()

    def on_mute_clicked(self, checked):
        try:
            self.strip.mute = checked
        except Exception as e:
            log.error(
                f"Failed to set {self.name} mute: "
                f"{type(e).__name__}: {e}"
            )

    def on_solo_clicked(self, checked):
        try:
            self.strip.solo = checked
        except Exception as e:
            log.error(
                f"Failed to set {self.name} solo: "
                f"{type(e).__name__}: {e}"
            )

    def on_mono_clicked(self, checked):
        try:
            self.strip.mono = checked
        except Exception as e:
            log.error(
                f"Failed to set {self.name} mono: "
                f"{type(e).__name__}: {e}"

            )


    def set_channel_levels(self, levels):
        """Apply already-read Mic levels to the UI without any VM I/O."""
        if self.vu_meter is None:
            return

        for meter, level in zip(self.vu_meters, levels):
            meter.set_level(level)


    def animate_level(self):
        """Advance the Mic meter animation without VoiceMeeter I/O."""
        if self.vu_meter is not None:
            for meter in self.vu_meters:
                meter.animate_level()


    def sync_from_voicemeeter(self):

        """
        Synchronize all strip parameters from VoiceMeeter.
        """

        try:

            gain = self.strip.gain


            # The event observer may report a stale value immediately after a
            # local wheel/drag update. Ignore that gain echo briefly; later
            # events still reconcile external VoiceMeeter changes normally.
            if time.monotonic() - self._last_local_gain_change >= 0.5:
                self.fader.blockSignals(True)
                self.fader.setValue(int(round(gain * 100)))
                self.fader.blockSignals(False)


            self.update_gain_label()


            mute = self.strip.mute
            solo = self.strip.solo
            mono = self.strip.mono

            self.mute_button.blockSignals(
                True
            )
            self.mute_button.setChecked(
                mute
            )
            self.mute_button.blockSignals(
                False
            )

            self.solo_button.blockSignals(
                True
            )
            self.solo_button.setChecked(
                solo
            )
            self.solo_button.blockSignals(
                False
            )

            self.mono_button.blockSignals(
                True
            )
            self.mono_button.setChecked(
                mono
            )
            self.mono_button.blockSignals(
                False
            )
            self.sync_routes()

        except Exception as e:
            log.error(
                f"Failed to synchronize {self.name}: "
                f"{type(e).__name__}: {e}"
            )


class LiveVolumeSlider(FineControlSlider):
    """Volume slider with the live session peak drawn on its track.

    Clicking or dragging anywhere on the track directly sets the volume,
    rather than requiring the user to grab the small thumb first.
    """

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self._audio_level = 0.0

    def _set_value_from_position(self, x):
        margin = 8
        usable_width = max(1, self.width() - (margin * 2))
        position = max(0, min(usable_width, int(x) - margin))
        value = QStyle.sliderValueFromPosition(
            self.minimum(),
            self.maximum(),
            position,
            usable_width,
            False,
        )
        self.setValue(value)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._set_value_from_position(event.position().x())
            self.setSliderDown(True)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.isSliderDown() and event.buttons() & Qt.MouseButton.LeftButton:
            self._set_value_from_position(event.position().x())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.isSliderDown():
            self._set_value_from_position(event.position().x())
            self.setSliderDown(False)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def set_audio_level(self, level):
        self._audio_level = max(0.0, min(1.0, float(level)))
        self.update()

    def paintEvent(self, event):
        option = QStyleOptionSlider()
        self.initStyleOption(option)
        style = self.style()
        groove = style.subControlRect(
            QStyle.ComplexControl.CC_Slider,
            option,
            QStyle.SubControl.SC_SliderGroove,
            self,
        )
        handle = style.subControlRect(
            QStyle.ComplexControl.CC_Slider,
            option,
            QStyle.SubControl.SC_SliderHandle,
            self,
        )

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QRectF(
            groove.left() + 8,
            handle.center().y() - 3,
            max(1, groove.width() - 16),
            6,
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#30363d"))
        painter.drawRoundedRect(track, 3, 3)

        if self._audio_level > 0.0:
            live_track = QRectF(
                track.left(),
                track.top(),
                max(1.0, track.width() * self._audio_level),
                track.height(),
            )
            painter.setBrush(QColor("#3fb950"))
            painter.drawRoundedRect(live_track, 3, 3)

        # Draw the volume thumb on the exact same centerline as the meter.
        handle_width = max(14, handle.width())
        handle_height = 14
        thumb = QRectF(
            handle.center().x() - handle_width / 2,
            track.center().y() - handle_height / 2,
            handle_width,
            handle_height,
        )
        thumb_color = "#79c0ff" if self.isSliderDown() else "#58a6ff"
        painter.setBrush(QColor(thumb_color))
        painter.drawRoundedRect(thumb, 4, 4)
        painter.end()


class ApplicationAudioWorker(QObject):
    """Own all pycaw/COM work on a dedicated worker thread.

    Windows can expose multiple audio sessions for one application. VMStreamer
    groups those sessions by application and VoiceMeeter bus so the UI shows
    one row per application while volume, mute, and live metering still apply
    to every underlying session.
    """

    topology_updated = Signal(object)
    peaks_updated = Signal(object)
    states_updated = Signal(object)
    route_finished = Signal(str)
    error = Signal(str)
    finished = Signal()

    FRIENDLY_NAMES = {
        "steam.exe": "Steam",
        "steamwebhelper.exe": "Steam Client Web",
        "discord.exe": "Discord",
        "signalrgb.exe": "SignalRGB",
        "signalrgbcore.exe": "SignalRGB Core",
        "brave.exe": "Brave Browser",
        "chatgpt.exe": "ChatGPT",
        "ms-teams.exe": "Microsoft Teams",
        "msteams.exe": "Microsoft Teams",
        "teams.exe": "Microsoft Teams",
        "msedgewebview2.exe": "Microsoft Edge WebView2",
        "msedge.exe": "Microsoft Edge",
        "chrome.exe": "Google Chrome",
        "firefox.exe": "Mozilla Firefox",
        "obs64.exe": "OBS Studio",
        "obs32.exe": "OBS Studio",
        "spotify.exe": "Spotify",
        "vlc.exe": "VLC media player",
        "explorer.exe": "Windows Explorer",
        "code.exe": "Visual Studio Code",
        "devenv.exe": "Visual Studio",
        "notepad.exe": "Notepad",
        "discordptb.exe": "Discord PTB",
        "discordcanary.exe": "Discord Canary",
    }

    def __init__(self):
        super().__init__()
        self.sessions = {}
        self.refresh_timer = None
        self.state_timer = None
        self._peak_thread = None
        self._peak_stop = threading.Event()
        self._session_lock = threading.RLock()
        self._com_initialized = False
        self._last_peak_emit = 0.0
        self._held_peaks = {}
        # Applications just moved to another channel, waiting for Windows to
        # re-bind their audio: {(exe name, exe path): {target, deadline, name}}
        self._pending_moves = {}
        self._fast_timer = None
        self._fast_scans_left = 0

    @staticmethod
    def friendly_name(app_name, display_name=""):
        """Return a stable human-friendly application name.

        Prefer a known executable mapping. If the executable is unknown, use
        a meaningful Windows session display name when available, otherwise
        turn the executable filename into a readable name rather than exposing
        a raw .exe filename.
        """
        raw = (app_name or "").strip()
        key = raw.casefold()
        mapped = ApplicationAudioWorker.FRIENDLY_NAMES.get(key)
        if mapped:
            return mapped

        session_name = (display_name or "").strip()
        if session_name and session_name.casefold() not in {key, f"{key}.exe"}:
            return session_name.removesuffix(".exe")

        base = os.path.splitext(raw)[0].replace("_", " ").replace("-", " ")
        base = " ".join(base.split())
        if not base:
            return "Unknown Application"
        return base.title()

    @Slot()
    def start(self):
        if not PYCAW_AVAILABLE:
            return

        try:
            import comtypes
            comtypes.CoInitialize()
            self._com_initialized = True
        except Exception as exc:
            self.error.emit(
                f"Audio worker COM initialization failed: "
                f"{type(exc).__name__}: {exc}"
            )
            return

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(2000)
        self.refresh_timer.timeout.connect(self.refresh_sessions)
        self.refresh_timer.start()

        self._peak_stop.clear()
        self._peak_thread = threading.Thread(
            target=self._peak_loop,
            name="VMStreamer-AppPeakSampler",
            daemon=True,
        )
        self._peak_thread.start()

        self.state_timer = QTimer(self)
        self.state_timer.setInterval(500)
        self.state_timer.timeout.connect(self.update_states)
        self.state_timer.start()

        self.refresh_sessions()

    def _peak_loop(self):
        """Sample application peaks using a dedicated monotonic sleep loop."""
        next_sample = time.monotonic()
        interval = 0.010

        while not self._peak_stop.is_set():
            now = time.monotonic()
            if now < next_sample:
                self._peak_stop.wait(next_sample - now)
                continue

            self.update_peaks()
            next_sample += interval

            if next_sample < time.monotonic() - interval:
                next_sample = time.monotonic() + interval

    @Slot()
    def refresh_now(self):
        self.refresh_sessions()

    @staticmethod
    def bus_for_device(friendly_name):
        return ApplicationControl.bus_for_device(friendly_name)

    @staticmethod
    def _get_device_sessions(device):
        result = []
        try:
            manager = device.AudioSessionManager
            enumerator = manager.GetSessionEnumerator()
            count = enumerator.GetCount()
            for index in range(count):
                control = enumerator.GetSession(index)
                if control is None:
                    continue
                try:
                    from pycaw.pycaw import AudioSession
                    from pycaw.api.audiopolicy import IAudioSessionControl2
                    from pycaw.api.endpointvolume import IAudioMeterInformation

                    control2 = control.QueryInterface(IAudioSessionControl2)
                    session = AudioSession(control2)

                    meter = None
                    for meter_source in (control, control2):
                        try:
                            meter = meter_source.QueryInterface(
                                IAudioMeterInformation
                            )
                            if meter is not None:
                                break
                        except Exception:
                            continue

                    result.append((session, meter))
                except Exception:
                    continue
        except Exception:
            return []
        return result

    @staticmethod
    def _session_key(bus, device, session, process):
        instance_id = getattr(session, "InstanceIdentifier", "") or ""
        endpoint_id = str(getattr(device, "id", "") or "")
        if instance_id:
            return (bus, instance_id)
        return (
            bus,
            endpoint_id,
            getattr(process, "pid", None),
            getattr(session, "Identifier", "") or "",
            getattr(session, "DisplayName", "") or "",
        )

    @staticmethod
    def _group_key(bus, app_name, executable_path):
        path = (executable_path or "").strip().casefold()
        if path:
            return (bus, app_name.casefold(), path)
        return (bus, app_name.casefold())

    @staticmethod
    def _find_bus_device(bus):
        """Return the active VoiceMeeter output device for a channel."""
        for device in war.list_output_devices():
            if ApplicationAudioWorker.bus_for_device(device.name) == bus:
                return device
        return None

    @staticmethod
    def _session_pid(session):
        try:
            pid = int(getattr(session, "ProcessId", 0) or 0)
            if pid:
                return pid
        except Exception:
            pass
        try:
            return int(session.Process.pid)
        except Exception:
            return 0

    @Slot(object, str)
    def route_application(self, session_key, target_bus):
        """Move an application's audio to another VoiceMeeter input.

        This sets Windows' per-app output device (the same setting as
        Settings > Sound > Volume mixer), so it persists until changed again.
        """
        with self._session_lock:
            info = self.sessions.get(session_key)
        if info is None or info["bus"] == target_bus:
            return
        name = info["display_name"]
        app_id = (
            info["app_name"],
            (info.get("executable_path") or "").casefold(),
        )
        if not APP_ROUTING_AVAILABLE:
            self.route_finished.emit(
                "Moving applications needs the winappaudiorouter package: "
                "pip install winappaudiorouter"
            )
            return
        try:
            device = self._find_bus_device(target_bus)
            if device is None:
                self.route_finished.emit(
                    f"Could not find the {target_bus} VoiceMeeter input device."
                )
                return
            pids = sorted({
                pid
                for pid in (
                    self._session_pid(member["session"])
                    for member in info.get("sessions", [])
                )
                if pid
            })
            if not pids:
                self.route_finished.emit(
                    f"{name} is no longer running, so it cannot be moved."
                )
                return
            moved = 0
            last_error = ""
            for pid in pids:
                try:
                    war.set_app_output_device(
                        process_id=pid,
                        device=device.id,
                    )
                    moved += 1
                except Exception as exc:
                    last_error = f"{type(exc).__name__}: {exc}"
            if moved:
                self._pending_moves[app_id] = {
                    "target": target_bus,
                    "deadline": time.monotonic() + 300.0,
                    "name": name,
                }
                self.route_finished.emit(
                    f"Moving {name} to {target_bus}. Windows switches it when "
                    "the app next starts playback; its audio is not interrupted."
                )
            else:
                self.route_finished.emit(
                    f"Could not move {name} to {target_bus}: {last_error}"
                )
        except Exception as exc:
            self.route_finished.emit(
                f"Could not move {name} to {target_bus}: "
                f"{type(exc).__name__}: {exc}"
            )
        finally:
            # Apps re-bind their audio on their own schedule, so keep
            # scanning for a while and update the moment it happens.
            self._start_fast_scans()

    def _drop_stale_sessions(self, found):
        """Resolve an application that shows on two channels after a move.

        Windows keeps an application's old session on the previous channel
        until the app next starts playback on the new one, so right after a
        move the same application can appear twice. A channel entry that is
        not playing is dropped when the same application is playing on, or
        was just moved to, another channel. An application that is still
        playing on its old channel stays visible there (that is where its
        audio really is) and is marked as moving until Windows switches it.
        """
        now = time.monotonic()
        pending = self._pending_moves
        for app_id in [k for k, v in pending.items() if v["deadline"] < now]:
            del pending[app_id]

        by_app = {}
        for group_key, info in found.items():
            app_id = (
                info["app_name"],
                (info.get("executable_path") or "").casefold(),
            )
            by_app.setdefault(app_id, []).append(group_key)

        for app_id, keys in by_app.items():
            move = pending.get(app_id)
            target = move["target"] if move else None

            if len(keys) > 1:
                active = [
                    k for k in keys
                    if any(m.get("state") == 1 for m in found[k]["sessions"])
                ]
                if len(active) == 1:
                    keep = set(active)
                elif not active and any(found[k]["bus"] == target for k in keys):
                    keep = {k for k in keys if found[k]["bus"] == target}
                else:
                    # Playing on several channels, or nothing to go on.
                    keep = set(keys)
                for k in keys:
                    if k not in keep:
                        del found[k]
                keys = [k for k in keys if k in keep]

            if move is None:
                continue
            if {found[k]["bus"] for k in keys} == {target}:
                self.route_finished.emit(f"{move['name']} is now on {target}.")
                del pending[app_id]
            else:
                for k in keys:
                    if found[k]["bus"] != target:
                        found[k]["moving_to"] = target

    def _start_fast_scans(self, count=90, interval_ms=1000):
        """Scan every second for a while after a move, then go back to normal.

        Scanning only reads the Windows session list; it never touches audio.
        """
        self._fast_scans_left = count
        if self._fast_timer is None:
            self._fast_timer = QTimer(self)
            self._fast_timer.timeout.connect(self._fast_scan)
        self._fast_timer.setInterval(interval_ms)
        self._fast_timer.start()
        QTimer.singleShot(300, self.refresh_sessions)

    def _fast_scan(self):
        self._fast_scans_left -= 1
        if self._fast_scans_left <= 0 or not self._pending_moves:
            self._fast_timer.stop()
        self.refresh_sessions()

    @staticmethod
    def _read_state(session):
        try:
            volume = float(session.SimpleAudioVolume.GetMasterVolume())
            muted = bool(session.SimpleAudioVolume.GetMute())
            return {
                "volume": max(0.0, min(1.0, volume)),
                "muted": muted,
            }
        except Exception:
            return None

    @staticmethod
    def _read_peak(meter):
        if meter is None:
            return None

        try:
            peak = meter.GetPeakValue()
            if isinstance(peak, tuple):
                peak = peak[0]
            return max(0.0, min(1.0, float(peak)))
        except Exception:
            return None

    @Slot()
    def refresh_sessions(self):
        if not PYCAW_AVAILABLE:
            return

        try:
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message=r"COMError attempting to get property .*",
                    category=UserWarning,
                    module=r"pycaw\.utils",
                )
                devices = AudioUtilities.GetAllDevices(
                    data_flow=EDataFlow.eAll.value,
                    device_state=DEVICE_STATE.MASK_ALL.value,
                )

            found = {}
            seen_sessions = set()

            for device in devices:
                try:
                    data_flow = AudioUtilities.GetEndpointDataFlow(
                        device.id, outputType=1
                    )
                except Exception:
                    data_flow = EDataFlow.eRender.value

                if data_flow != EDataFlow.eRender.value:
                    continue

                friendly_device_name = getattr(device, "FriendlyName", None) or ""
                bus = self.bus_for_device(friendly_device_name)
                if bus is None:
                    continue

                for session, meter in self._get_device_sessions(device):
                    try:
                        process = session.Process
                        if process is None:
                            continue

                        name = process.name()
                        if not name:
                            continue

                        app_name = name.lower()
                        if app_name == "vmstreamer.exe":
                            continue
                        if getattr(session, "State", 1) == 2:
                            continue

                        session_key = self._session_key(
                            bus, device, session, process
                        )
                        if session_key in seen_sessions:
                            continue
                        seen_sessions.add(session_key)

                        try:
                            executable_path = process.exe() or ""
                        except Exception:
                            executable_path = ""

                        group_key = self._group_key(
                            bus,
                            app_name,
                            executable_path,
                        )

                        state = self._read_state(session) or {
                            "volume": 1.0,
                            "muted": False,
                        }

                        if group_key not in found:
                            display_name = self.friendly_name(
                                app_name,
                                getattr(session, "DisplayName", "") or "",
                            )
                            found[group_key] = {
                                "session_key": group_key,
                                "app_name": app_name,
                                "display_name": display_name,
                                "bus": bus,
                                "executable_path": executable_path,
                                "hide_key": (executable_path or app_name).strip().casefold(),
                                "sessions": [],
                                "volume": state["volume"],
                                "muted": state["muted"],
                            }

                        found[group_key]["sessions"].append({
                            "session_key": session_key,
                            "session": session,
                            "meter": meter,
                            "volume": state["volume"],
                            "muted": state["muted"],
                            "pid": self._session_pid(session),
                            "state": getattr(session, "State", 1),
                        })
                    except Exception:
                        continue

            self._drop_stale_sessions(found)
            # Keep one stable application entry per executable + VoiceMeeter bus.
            # The individual Windows sessions remain available underneath it.
            for info in found.values():
                members = info["sessions"]
                if members:
                    info["volume"] = float(members[0]["volume"])
                    info["muted"] = all(
                        bool(member["muted"])
                        for member in members
                    )

            with self._session_lock:
                self.sessions = found

            snapshot = [
                {
                    "session_key": key,
                    "app_name": info["app_name"],
                    "display_name": info["display_name"],
                    "bus": info["bus"],
                    "executable_path": info["executable_path"],
                    "hide_key": info["hide_key"],
                    "moving_to": info.get("moving_to", ""),
                    "volume": info["volume"],
                    "muted": info["muted"],
                    "session_count": len(info["sessions"]),
                }
                for key, info in found.items()
            ]

            self.topology_updated.emit(snapshot)
            self.update_states()

        except Exception as exc:
            self.error.emit(
                f"VoiceMeeter application scan failed: "
                f"{type(exc).__name__}: {exc}"
            )

    @Slot()
    def update_peaks(self):
        """Sample every application meter. Runs on the peak thread only."""
        peaks = self._held_peaks
        with self._session_lock:
            session_items = list(self.sessions.items())

        for group_key, info in session_items:
            group_peak = 0.0
            meter_available = False
            for member in info.get("sessions", []):
                peak = self._read_peak(member.get("meter"))
                if peak is None:
                    continue
                meter_available = True
                group_peak = max(group_peak, peak)
            # Sampling is faster than GUI delivery, so keep the highest peak
            # seen since the last emit instead of only the latest sample.
            held = peaks.get(group_key)
            if not meter_available:
                peaks.setdefault(group_key, None)
            elif held is None or group_peak > held:
                peaks[group_key] = group_peak

        now = time.monotonic()
        if now - self._last_peak_emit >= (1.0 / 60.0):
            self._last_peak_emit = now
            self._held_peaks = {}
            self.peaks_updated.emit(peaks)

    @Slot()
    def update_states(self):
        states = {}
        with self._session_lock:
            session_items = list(self.sessions.items())

        for group_key, info in session_items:
            members = info.get("sessions", [])
            if not members:
                continue

            member_states = []
            for member in members:
                state = self._read_state(member["session"])
                if state is None:
                    continue
                member["volume"] = state["volume"]
                member["muted"] = state["muted"]
                member_states.append(state)

            if not member_states:
                continue

            info["volume"] = float(member_states[0]["volume"])
            info["muted"] = all(
                bool(state["muted"])
                for state in member_states
            )
            states[group_key] = {
                "volume": info["volume"],
                "muted": info["muted"],
            }

        if states:
            self.states_updated.emit(states)

    @Slot(object, str, float)
    def set_volume(self, session_key, bus, volume):
        info = self.sessions.get(session_key)
        if not info or info["bus"] != bus:
            return

        try:
            volume = max(0.0, min(1.0, float(volume)))
            successful = 0
            for member in info.get("sessions", []):
                try:
                    member["session"].SimpleAudioVolume.SetMasterVolume(
                        volume,
                        None,
                    )
                    member["volume"] = volume
                    successful += 1
                except Exception:
                    continue

            if successful:
                info["volume"] = volume
                self.states_updated.emit({
                    session_key: {
                        "volume": volume,
                        "muted": bool(info["muted"]),
                    }
                })
        except Exception as exc:
            self.error.emit(
                f"Failed to set {info['display_name']} volume on {bus}: "
                f"{type(exc).__name__}: {exc}"
            )

    @Slot(object, str, bool)
    def set_mute(self, session_key, bus, muted):
        info = self.sessions.get(session_key)
        if not info or info["bus"] != bus:
            return

        try:
            successful = 0
            for member in info.get("sessions", []):
                try:
                    member["session"].SimpleAudioVolume.SetMute(
                        1 if muted else 0,
                        None,
                    )
                    member["muted"] = bool(muted)
                    successful += 1
                except Exception:
                    continue

            if successful:
                info["muted"] = bool(muted)
                self.states_updated.emit({
                    session_key: {
                        "volume": float(info["volume"]),
                        "muted": bool(muted),
                    }
                })
        except Exception as exc:
            self.error.emit(
                f"Failed to mute {info['display_name']} on {bus}: "
                f"{type(exc).__name__}: {exc}"
            )

    @Slot()
    def shutdown(self):
        if self.refresh_timer is not None:
            self.refresh_timer.stop()
        if self.state_timer is not None:
            self.state_timer.stop()
        if self._fast_timer is not None:
            self._fast_timer.stop()

        self._peak_stop.set()
        peak_thread = self._peak_thread
        if peak_thread is not None and peak_thread.is_alive():
            peak_thread.join(timeout=0.25)
        self._peak_thread = None

        with self._session_lock:
            self.sessions.clear()

        if self._com_initialized:
            try:
                import comtypes
                comtypes.CoUninitialize()
            except Exception:
                pass
            self._com_initialized = False

        self.finished.emit()


class ApplicationRow(QWidget):
    """One automatically detected Windows application group."""

    hide_requested = Signal(str, str, bool)

    # Rows are rebuilt whenever the session list changes; reading an icon
    # from its executable touches the disk, so do that once per application.
    _icon_cache = {}

    @classmethod
    def icon_pixmap(cls, executable_path):
        if executable_path not in cls._icon_cache:
            pixmap = None
            try:
                if executable_path and os.path.isfile(executable_path):
                    app_icon = QFileIconProvider().icon(
                        QFileInfo(executable_path)
                    )
                    pixmap = app_icon.pixmap(20, 20)
            except Exception:
                pixmap = None
            cls._icon_cache[executable_path] = pixmap
        return cls._icon_cache[executable_path]

    def __init__(
        self, session_key, app_name, display_name, bus, controller,
        executable_path="", volume=1.0, muted=False, hide_key="", hidden=False,
    ):
        super().__init__()
        self.session_key = session_key
        self.app_name = app_name
        self.display_name = ApplicationAudioWorker.friendly_name(
            self.app_name,
            display_name,
        )
        self.bus = bus
        self.controller = controller
        self.hide_key = hide_key or self.app_name.casefold()
        self.is_hidden = bool(hidden)
        self._drag_start = None
        self._syncing = False
        self._display_peak = 0.0
        self._peak_hold_until = 0.0
        self._last_meter_update = time.monotonic()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 1, 2, 1)
        layout.setSpacing(1)
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        self.setMaximumHeight(44)

        self.name_label = QLabel(self.display_name)
        self.name_label.setToolTip(
            f"{self.display_name} — routed to {bus} • drag to another channel to move it"
        )

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(20, 20)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setToolTip(self.display_name)
        pixmap = self.icon_pixmap(executable_path)
        if pixmap is not None:
            self.icon_label.setPixmap(pixmap)

        self.volume_slider = LiveVolumeSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setMinimumWidth(0)
        self.volume_slider.setFixedHeight(19)
        self.volume_slider.setToolTip(
            "Scroll for 1% volume steps. Blue handle sets app volume; "
            "green fill shows live audio level."
        )
        self.volume_slider.setStyleSheet(
            "QSlider::groove:horizontal { background: transparent; height: 6px; }"
            "QSlider::handle:horizontal { background: #58a6ff; width: 16px; "
            "margin: -5px 0; border-radius: 4px; }"
        )
        self.volume_slider.valueChanged.connect(self.on_volume_changed)

        self.volume_percent = QLabel("100%")
        self.volume_percent.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.volume_percent.setFixedWidth(34)
        self.volume_percent.setStyleSheet("color: #d6e2ef; font-size: 10px;")

        self.mute_button = QPushButton("🔊")
        self.mute_button.setCheckable(True)
        self.mute_button.setFixedSize(28, 24)
        self.mute_button.setStyleSheet(
            "QPushButton { background: #18232e; border: 1px solid #314558; "
            "border-radius: 6px; font-size: 14px; padding: 1px; }"
            "QPushButton:checked { background: #54262c; border-color: #a8434f; }"
        )
        self.mute_button.setToolTip("Mute this application")
        self.mute_button.clicked.connect(self.on_mute_clicked)

        heading = QHBoxLayout()
        heading.setContentsMargins(0, 0, 0, 0)
        heading.setSpacing(4)
        heading.addWidget(self.icon_label)
        heading.addWidget(self.name_label, 1)
        heading.addWidget(self.mute_button)

        volume_row = QHBoxLayout()
        volume_row.setContentsMargins(0, 0, 0, 0)
        volume_row.setSpacing(0)
        volume_row.addWidget(self.volume_slider, 1)
        volume_row.addWidget(self.volume_percent)

        layout.setContentsMargins(3, 2, 3, 2)
        layout.setSpacing(2)
        layout.addLayout(heading)
        layout.addLayout(volume_row)

        self.apply_state({"volume": volume, "muted": muted})

    # Drag an application onto another channel column to move its audio there.
    # Only presses on the name/icon area start a drag; the volume slider and
    # the mute button keep their own mouse handling.
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._drag_start is not None
            and event.buttons() & Qt.MouseButton.LeftButton
            and (event.position().toPoint() - self._drag_start).manhattanLength()
            >= QApplication.startDragDistance()
        ):
            hot_spot = self._drag_start
            self._drag_start = None
            self._start_drag(hot_spot)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_start = None
        super().mouseReleaseEvent(event)

    def _start_drag(self, hot_spot):
        payload = json.dumps({"key": list(self.session_key), "bus": self.bus})
        mime = QMimeData()
        mime.setData(DRAG_MIME, QByteArray(payload.encode("utf-8")))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.setHotSpot(hot_spot)
        self.controller.drag_started()
        try:
            drag.exec(Qt.DropAction.MoveAction)
        finally:
            self.controller.drag_finished()

    def set_moving(self, target):
        """Mark this row as waiting for Windows to move it to another channel."""
        self.name_label.setStyleSheet("color: #d29922; font-style: italic;")
        self.name_label.setToolTip(
            f"{self.display_name} — moving to {target}. Windows switches it "
            "when the app next starts playback; pausing and resuming it "
            "speeds this up. Its audio is not interrupted."
        )

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        if self.is_hidden:
            this_action = menu.addAction(f"Unhide on {self.bus}")
            all_action = menu.addAction("Unhide on all channels")
            hide = False
        else:
            this_action = menu.addAction(f"Hide on {self.bus}")
            all_action = menu.addAction("Hide on all channels")
            hide = True

        chosen = menu.exec(event.globalPos())
        if chosen is this_action:
            self.hide_requested.emit(self.hide_key, self.bus, hide)
        elif chosen is all_action:
            self.hide_requested.emit(self.hide_key, ALL_CHANNELS, hide)

    def on_volume_changed(self, value):
        self.volume_percent.setText(f"{value}%")
        self.volume_slider.setToolTip(
            f"App volume: {value}% • scroll for 1% steps"
        )
        if not self._syncing:
            self.controller.set_app_volume(
                self.session_key,
                self.bus,
                value / 100.0,
            )

    def on_mute_clicked(self, checked):
        self.mute_button.setText("🔇" if checked else "🔊")
        if not self._syncing:
            self.controller.set_app_mute(
                self.session_key,
                self.bus,
                checked,
            )

    def apply_state(self, state):
        if state is None:
            return
        self._syncing = True
        try:
            value = int(round(state["volume"] * 100))
            self.volume_slider.setValue(value)
            self.volume_percent.setText(f"{value}%")
            self.mute_button.setChecked(state["muted"])
            self.mute_button.setText("🔇" if state["muted"] else "🔊")
        finally:
            self._syncing = False

    def set_audio_level(self, peak):
        peak = 0.0 if peak is None else max(0.0, min(1.0, float(peak)))
        now = time.monotonic()
        elapsed = max(0.0, min(0.10, now - self._last_meter_update))
        self._last_meter_update = now

        if peak >= self._display_peak:
            self._display_peak = peak
            if peak > 0.001:
                self._peak_hold_until = now + 0.045
        elif now >= self._peak_hold_until:
            self._display_peak = max(
                peak,
                self._display_peak * math.exp(-elapsed / 0.12),
            )

        level_db = -60.0 if self._display_peak <= 0.001 else 20.0 * math.log10(self._display_peak)
        level_db = max(-60.0, min(0.0, level_db))
        self.volume_slider.set_audio_level(
            (level_db + 60.0) / 60.0
        )


class ApplicationDropColumn(QWidget):
    """One channel column; accepts applications dragged from another channel."""

    application_dropped = Signal(object, str, str)  # key, source bus, target bus

    def __init__(self, bus, colors):
        super().__init__()
        self.bus = bus
        self.setObjectName("applicationBusCard")
        self._normal_style = (
            "QWidget#applicationBusCard {"
            f"background: #101820; border: 1px solid {colors['border']}; "
            "border-radius: 8px; }"
        )
        self._highlight_style = (
            "QWidget#applicationBusCard {"
            f"background: {colors['header']}; border: 1px solid {colors['accent']}; "
            "border-radius: 8px; }"
        )
        self.setStyleSheet(self._normal_style)
        self.setAcceptDrops(True)

    @staticmethod
    def _payload(mime):
        """Return (session_key, source_bus) from a dragged application."""
        if not mime.hasFormat(DRAG_MIME):
            return None
        try:
            data = json.loads(bytes(mime.data(DRAG_MIME)).decode("utf-8"))
            return tuple(data["key"]), str(data["bus"])
        except Exception:
            return None

    def _accepts(self, event):
        payload = self._payload(event.mimeData())
        return payload is not None and payload[1] != self.bus

    def dragEnterEvent(self, event):
        if self._accepts(event):
            self.setStyleSheet(self._highlight_style)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self._accepts(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet(self._normal_style)
        event.accept()

    def dropEvent(self, event):
        self.setStyleSheet(self._normal_style)
        payload = self._payload(event.mimeData())
        if payload is None or payload[1] == self.bus:
            event.ignore()
            return
        event.acceptProposedAction()
        self.application_dropped.emit(payload[0], payload[1], self.bus)


class ApplicationControl(QWidget):
    """Detect VoiceMeeter application sessions without blocking the Qt thread."""

    BUS_NAMES = ("Game", "Chat", "Media")

    DEVICE_PATTERNS = {
        "Game": (
            "voicemeeter input",
            "game (vb-audio voicemeeter vaio)",
        ),
        "Chat": (
            "voicemeeter aux input",
            "chat (vb-audio voicemeeter vaio)",
        ),
        "Media": (
            "voicemeeter vaio3 input",
            "media (vb-audio voicemeeter vaio)",
        ),
    }

    refresh_requested = Signal()
    volume_requested = Signal(object, str, float)
    mute_requested = Signal(object, str, bool)
    route_requested = Signal(object, str)
    shutdown_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setVisible(False)
        self.sessions = {}
        self.rows = {name: {} for name in self.BUS_NAMES}
        self._topology_signature = None
        self._closing = False
        # Hiding is per virtual channel: the same application can be hidden
        # on Game but still visible on Chat. "Show hidden" is per channel too.
        self.show_hidden = {bus: False for bus in self.BUS_NAMES}
        self.bus_hidden_buttons = {}
        self._drag_active = False
        self._notice_text = ""
        self._notice_until = 0.0
        self.settings = QSettings("VMStreamer", "VMStreamer")
        self.hidden_applications = self._load_hidden_applications()
        if self.settings.value("hidden_applications_v2", None) is None:
            # First launch of the per-channel format: store the migrated list.
            self._save_hidden_applications()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 4, 5, 5)
        layout.setSpacing(4)

        if not PYCAW_AVAILABLE:
            missing = QLabel(
                "Application controls require pycaw. Install it with: pip install pycaw"
            )
            missing.setStyleSheet("color: #f0883e;")
            layout.addWidget(missing)
            self.worker_thread = None
            self.worker = None
            return

        toolbar = QHBoxLayout()
        self.status_label = QLabel("Scanning VoiceMeeter audio sessions...")
        self.status_label.setStyleSheet("color: #8b949e;")
        refresh_button = QPushButton("REFRESH")
        refresh_button.clicked.connect(self.request_refresh)

        self.hidden_button = QPushButton()
        self.hidden_button.setCheckable(True)
        self.hidden_button.setFixedSize(32, 28)
        self.hidden_button.setIcon(reference_eye_icon(20))
        self.hidden_button.setIconSize(QSize(20, 20))
        self.hidden_button.setToolTip("Show hidden applications")
        self.hidden_button.clicked.connect(self.toggle_hidden_visibility)
        self.hidden_button.setStyleSheet(
            "QPushButton { background: #18232e; border: 1px solid #314558; "
            "border-radius: 6px; font-size: 15px; padding: 0; }"
            "QPushButton:checked { background: #243b52; border-color: #58a6ff; }"
        )

        toolbar.addWidget(self.status_label, 1)
        toolbar.addWidget(self.hidden_button)
        toolbar.addWidget(refresh_button)
        layout.addLayout(toolbar)

        columns = QHBoxLayout()
        columns.setSpacing(4)
        self.bus_layouts = {}
        self.bus_containers = {}

        for bus in self.BUS_NAMES:
            colors = STRIP_COLORS[bus]
            box = ApplicationDropColumn(bus, colors)
            box.application_dropped.connect(self.on_application_dropped)
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(3, 3, 3, 3)
            box_layout.setSpacing(1)

            endpoint_label = {
                "Game": "APPLICATIONS (VAIO)",
                "Chat": "APPLICATIONS (VAIO AUX)",
                "Media": "APPLICATIONS (VAIO3)",
            }[bus]
            title = QLabel(endpoint_label)
            title.setStyleSheet(
                f"color: {colors['accent']}; background: {colors['header']}; "
                f"border: 1px solid {colors['border']}; border-radius: 5px; "
                "padding: 3px 5px; font-weight: bold;"
            )
            header_row = QHBoxLayout()
            header_row.setContentsMargins(0, 0, 0, 0)
            header_row.setSpacing(3)
            header_row.addWidget(title, 1)

            bus_eye = QPushButton()
            bus_eye.setCheckable(True)
            bus_eye.setFixedSize(30, 26)
            bus_eye.setIcon(reference_eye_icon(18))
            bus_eye.setIconSize(QSize(18, 18))
            bus_eye.setToolTip(f"Show hidden applications on {bus}")
            bus_eye.setStyleSheet(
                "QPushButton { background: #18232e; border: 1px solid #314558; "
                "border-radius: 6px; padding: 0; }"
                "QPushButton:checked { background: #243b52; border-color: #58a6ff; }"
            )
            bus_eye.clicked.connect(
                lambda checked, b=bus: self.set_show_hidden(b, checked)
            )
            header_row.addWidget(bus_eye)
            self.bus_hidden_buttons[bus] = bus_eye

            box_layout.addLayout(header_row)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll.setFrameShape(QScrollArea.Shape.NoFrame)

            container = QWidget()
            container.setStyleSheet("background: transparent; border: none;")
            bus_layout = QVBoxLayout(container)
            bus_layout.setContentsMargins(0, 0, 0, 0)
            bus_layout.setSpacing(1)
            bus_layout.addStretch()
            scroll.setWidget(container)

            box_layout.addWidget(scroll, 1)
            columns.addWidget(box, 1)
            self.bus_layouts[bus] = bus_layout
            self.bus_containers[bus] = container

        layout.addLayout(columns, 1)

        self.worker_thread = QThread(self)
        self.worker = ApplicationAudioWorker()
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.start)
        self.refresh_requested.connect(self.worker.refresh_now)
        self.volume_requested.connect(self.worker.set_volume)
        self.mute_requested.connect(self.worker.set_mute)
        self.route_requested.connect(self.worker.route_application)
        self.worker.route_finished.connect(self.on_route_finished)
        self.shutdown_requested.connect(self.worker.shutdown)

        self.worker.topology_updated.connect(self.on_topology_updated)
        self.worker.peaks_updated.connect(self.on_peaks_updated)
        self.worker.states_updated.connect(self.on_states_updated)
        self.worker.error.connect(self.on_worker_error)
        self.worker.finished.connect(self.worker_thread.quit)

        self.worker_thread.start()

    @classmethod
    def bus_for_device(cls, friendly_name):
        name = (friendly_name or "").lower()
        normalized = " ".join(name.split())
        for bus in ("Media", "Chat", "Game"):
            for pattern in cls.DEVICE_PATTERNS[bus]:
                if pattern in normalized:
                    return bus
        return None

    @staticmethod
    def _parse_hidden_setting(raw):
        if isinstance(raw, str):
            try:
                values = json.loads(raw) if raw else []
            except Exception:
                values = []
        elif isinstance(raw, (list, tuple, set)):
            values = list(raw)
        else:
            values = []

        return {
            str(value).casefold()
            for value in values
            if str(value).strip()
        }

    @staticmethod
    def _hide_id(bus, hide_key):
        """Identifier for one application on one virtual channel."""
        return f"{bus}|{(hide_key or '').strip()}".casefold()

    def _is_hidden(self, info):
        base = info.get("hide_key", "") or info.get("app_name", "")
        return self._hide_id(info["bus"], base) in self.hidden_applications

    def _load_hidden_applications(self):
        raw = self.settings.value("hidden_applications_v2", None)
        if raw is not None:
            return self._parse_hidden_setting(raw)

        # Migrate the older global list. Previously a hidden application was
        # hidden on every channel, so keep exactly that behaviour once.
        legacy = self._parse_hidden_setting(
            self.settings.value("hidden_applications", "")
        )
        return {
            self._hide_id(bus, key)
            for key in legacy
            for bus in self.BUS_NAMES
        }

    def _save_hidden_applications(self):
        self.settings.setValue(
            "hidden_applications_v2",
            json.dumps(sorted(self.hidden_applications)),
        )
        self.settings.sync()

    def toggle_hidden_visibility(self, checked):
        """Master eye button: show or hide hidden applications everywhere."""
        self.set_show_hidden(None, checked)

    def set_show_hidden(self, bus, checked):
        """Show hidden applications on one channel (or all when bus is None)."""
        buses = self.BUS_NAMES if bus is None else (bus,)
        for name in buses:
            self.show_hidden[name] = bool(checked)
        self._sync_hidden_buttons()
        self.rebuild_rows()
        self.update_status()

    def _sync_hidden_buttons(self):
        for name, button in self.bus_hidden_buttons.items():
            shown = self.show_hidden[name]
            button.setChecked(shown)
            button.setToolTip(
                f"Hide hidden applications on {name}"
                if shown
                else f"Show hidden applications on {name}"
            )

        all_shown = all(self.show_hidden.values())
        self.hidden_button.setChecked(all_shown)
        self.hidden_button.setToolTip(
            "Hide hidden applications on all channels"
            if all_shown
            else "Show hidden applications on all channels"
        )

    def on_hide_requested(self, hide_key, scope, hidden):
        """Hide or unhide an application on one channel or on all channels.

        "All channels" covers every channel, including ones the application
        is not routed to right now, so it stays hidden if its routing changes.
        """
        hide_key = str(hide_key or "").strip()
        if not hide_key:
            return

        buses = self.BUS_NAMES if scope == ALL_CHANNELS else (scope,)
        for bus in buses:
            if bus not in self.BUS_NAMES:
                continue
            hide_id = self._hide_id(bus, hide_key)
            if hidden:
                self.hidden_applications.add(hide_id)
            else:
                self.hidden_applications.discard(hide_id)

        self._save_hidden_applications()
        self.rebuild_rows()
        self.update_status()

    def update_status(self):
        if time.monotonic() < self._notice_until:
            self.status_label.setText(self._notice_text)
            return
        visible = [
            info
            for info in self.sessions.values()
            if (
                self.show_hidden[info["bus"]]
                or not self._is_hidden(info)
            )
        ]

        counts = {
            bus: sum(1 for info in visible if info["bus"] == bus)
            for bus in self.BUS_NAMES
        }

        hidden_count = sum(
            1
            for info in self.sessions.values()
            if self._is_hidden(info)
        )

        total = len(visible)
        suffix = f" • {hidden_count} hidden" if hidden_count else ""

        self.status_label.setText(
            f"{total} applications routed through VoiceMeeter"
            f" • Game {counts['Game']}"
            f" • Chat {counts['Chat']}"
            f" • Media {counts['Media']}"
            f"{suffix}"
        )

    def request_refresh(self):
        if not self._closing and self.worker_thread is not None:
            self.status_label.setText("Scanning VoiceMeeter applications...")
            self.refresh_requested.emit()

    def drag_started(self):
        self._drag_active = True

    def drag_finished(self):
        self._drag_active = False

    def _volume_slider_in_use(self):
        return any(
            row.volume_slider.isSliderDown()
            for rows in self.rows.values()
            for row in rows.values()
        )

    def _show_notice(self, text, seconds=8.0):
        """Show a short message in the status line, ahead of the counts."""
        self._notice_text = text
        self._notice_until = time.monotonic() + seconds
        self.status_label.setText(text)

    def on_application_dropped(self, session_key, source_bus, target_bus):
        """An application row was dropped on another channel's column."""
        if self._closing or self.worker_thread is None:
            return
        info = self.sessions.get(session_key)
        if info is None or info["bus"] != source_bus or source_bus == target_bus:
            return
        if not APP_ROUTING_AVAILABLE:
            self._show_notice(
                "Moving applications needs the winappaudiorouter package: "
                "pip install winappaudiorouter"
            )
            return
        self._show_notice(f"Moving {info['display_name']} to {target_bus}...")
        self.route_requested.emit(session_key, target_bus)

    def on_route_finished(self, message):
        if not self._closing:
            self._show_notice(message)

    def on_worker_error(self, message):
        if not self._closing:
            self.status_label.setText(message)
        log.error(message)

    def on_topology_updated(self, snapshot):
        if self._closing:
            return

        self.sessions = {
            item["session_key"]: item
            for item in snapshot
        }

        signature = tuple(
            sorted(
                (key, info["bus"], info.get("moving_to") or "")
                for key, info in self.sessions.items()
            )
        )

        if signature != self._topology_signature:
            if self._drag_active or self._volume_slider_in_use():
                # Never rebuild rows while one is being dragged or its
                # volume slider is held; the next scan applies the change.
                self.update_status()
                return
            self._topology_signature = signature
            self.rebuild_rows()
        else:
            self.sync_rows()

        self.update_status()

    def on_peaks_updated(self, peaks):
        if self._closing or not self.isVisible():
            return
        for bus in self.BUS_NAMES:
            for session_key, row in self.rows[bus].items():
                row.set_audio_level(peaks.get(session_key))

    def on_states_updated(self, states):
        if self._closing:
            return
        for session_key, state in states.items():
            info = self.sessions.get(session_key)
            if info is not None:
                info["volume"] = state["volume"]
                info["muted"] = state["muted"]
            for bus in self.BUS_NAMES:
                row = self.rows[bus].get(session_key)
                if row is not None:
                    row.apply_state(state)
                    break

    def rebuild_rows(self):
        for bus in self.BUS_NAMES:
            self.clear_layout(self.bus_layouts[bus])
            self.rows[bus].clear()

        for session_key, info in sorted(
            self.sessions.items(),
            key=lambda item: (
                item[1]["display_name"].lower(),
                repr(item[0]),
            ),
        ):
            hide_key = info.get("hide_key", "") or info["app_name"]
            hidden = (
                self._hide_id(info["bus"], hide_key) in self.hidden_applications
            )

            if hidden and not self.show_hidden[info["bus"]]:
                continue

            row = ApplicationRow(
                session_key,
                info["app_name"],
                info["display_name"],
                info["bus"],
                self,
                info.get("executable_path", ""),
                info.get("volume", 1.0),
                info.get("muted", False),
                hide_key,
                hidden,
            )
            row.hide_requested.connect(self.on_hide_requested)

            if hidden:
                row.name_label.setStyleSheet(
                    "color: #8b949e; font-style: italic;"
                )
                row.name_label.setToolTip(
                    f"{row.display_name} — hidden application — routed to {row.bus} • drag to move"
                )

            if info.get("moving_to"):
                row.set_moving(info["moving_to"])
            bus = info["bus"]
            self.bus_layouts[bus].insertWidget(
                self.bus_layouts[bus].count() - 1,
                row,
            )
            self.rows[bus][session_key] = row

    def clear_layout(self, layout):
        while layout.count() > 1:
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def get_app_state(self, session_key, bus):
        info = self.sessions.get(session_key)
        if not info or info["bus"] != bus:
            return None
        return {
            "volume": float(info.get("volume", 1.0)),
            "muted": bool(info.get("muted", False)),
        }

    def set_app_volume(self, session_key, bus, volume):
        if self.worker_thread is not None and not self._closing:
            self.volume_requested.emit(session_key, bus, float(volume))

    def set_app_mute(self, session_key, bus, muted):
        if self.worker_thread is not None and not self._closing:
            self.mute_requested.emit(session_key, bus, bool(muted))

    def sync_rows(self):
        for bus in self.BUS_NAMES:
            for row in self.rows[bus].values():
                row.apply_state(self.get_app_state(row.session_key, bus))

    def close(self):
        if self._closing:
            return
        self._closing = True

        thread = self.worker_thread
        worker = self.worker
        if thread is None or worker is None:
            self.worker = None
            self.worker_thread = None
            return

        try:
            # Execute shutdown inside the worker thread and wait only for the
            # actual cleanup call to return. This avoids the old pattern of
            # waiting up to two seconds for a queued shutdown request.
            QMetaObject.invokeMethod(
                worker,
                "shutdown",
                Qt.ConnectionType.BlockingQueuedConnection,
            )
        except Exception:
            # If the worker has already stopped, simply make sure its event
            # loop is asked to exit.
            pass

        thread.quit()
        thread.wait(300)

        self.worker = None
        self.worker_thread = None


class MicLevelWorker(QObject):
    """Read the Mic strip level on a dedicated worker thread."""

    levels_received = Signal(float, float)
    error = Signal(str)
    finished = Signal()

    def __init__(self, vm):
        super().__init__()
        self.vm = vm
        self.timer = None
        self._last_levels = None

    @Slot()
    def start(self):
        self.timer = QTimer(self)
        self.timer.setInterval(10)
        self.timer.timeout.connect(self.read_level)
        self.timer.start()
        self.read_level()

    @Slot()
    def read_level(self):
        try:
            raw_levels = self.vm.strip[MIC_STRIP].levels.prefader
            if isinstance(raw_levels, (tuple, list)):
                levels = [
                    float(value)
                    for value in raw_levels
                    if isinstance(value, (int, float))
                ]
            elif isinstance(raw_levels, (int, float)):
                levels = [float(raw_levels)]
            else:
                levels = []

            if not levels:
                left = right = -200.0
            elif len(levels) == 1:
                left = right = levels[0]
            else:
                left, right = levels[:2]

            # VoiceMeeter's level cache refreshes more slowly than this
            # timer, so most reads repeat the previous one.
            if (left, right) != self._last_levels:
                self._last_levels = (left, right)
                self.levels_received.emit(left, right)
        except Exception as exc:
            self.error.emit(
                f"Mic level worker read failed: {type(exc).__name__}: {exc}"
            )

    @Slot()
    def stop(self):
        if self.timer is not None:
            self.timer.stop()
            self.timer = None
        self.finished.emit()


class GripSplitterHandle(QSplitterHandle):
    """Splitter handle with a visible grip, so it is obviously draggable."""

    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self._hover = False
        self._pressed = False
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setToolTip("Drag to resize • double-click to reset")

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self._pressed = True
        self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._pressed = False
        self.update()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        splitter = self.splitter()
        if hasattr(splitter, "reset_sizes"):
            splitter.reset_sizes()
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bar = QRectF(self.rect()).adjusted(0, 3, 0, -3)
        active = self._hover or self._pressed
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#243b52" if active else "#18232e"))
        painter.drawRoundedRect(bar, 3, 3)
        painter.setBrush(QColor("#58a6ff" if active else "#4b6179"))
        center = bar.center()
        for offset in (-14, 0, 14):
            painter.drawEllipse(QPointF(center.x() + offset, center.y()), 2.0, 2.0)


class GripSplitter(QSplitter):
    """Splitter that uses the grip handle and can return to default sizes."""

    def __init__(self, orientation, default_sizes, parent=None):
        super().__init__(orientation, parent)
        self._default_sizes = list(default_sizes)
        self.setHandleWidth(14)
        self.setChildrenCollapsible(False)
        self.setOpaqueResize(True)

    def createHandle(self):
        return GripSplitterHandle(self.orientation(), self)

    def reset_sizes(self):
        self.setSizes(self._default_sizes)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.vm = None
        self.connected = False
        self.strips = {}
        self.window_settings = QSettings("VMStreamer", "VMStreamer")


        # Qt bridge for VoiceMeeter's background event thread.

        self.vm_bridge = VMEventBridge()
        self.mic_level_thread = None
        self.mic_level_worker = None


        self.vm_bridge.event_received.connect(

            self.on_vm_event

        )

        # Keep the visual VU meters updating independently of VoiceMeeter's
        # ldirty event cadence. The event path still gives immediate updates,
        # while this timer lets the existing meter decay smoothly to silence.
        self.level_timer = QTimer(self)
        self.level_timer.setInterval(16)
        self.level_timer.timeout.connect(self.update_mixer_levels)
        self.level_timer.start()


        self.setWindowTitle(

            "VMStreamer"

        )

        # Compact default size fits the open desktop area beside monitoring
        # tools while keeping the window resizable. Restore the last saved
        # geometry when available.
        self.setMinimumSize(900, 760)
        saved_geometry = self.window_settings.value("geometry_v2")
        if saved_geometry is not None:
            try:
                if not self.restoreGeometry(saved_geometry):
                    self.resize(960, 900)
            except Exception:
                self.resize(960, 900)
        else:
            self.resize(960, 900)


        self.setStyleSheet(

            """
            QMainWindow {
                background: #0d1117;
                color: #e6edf3;
            }

            QWidget {
                color: #e6edf3;
                font-family: "Segoe UI";
                font-size: 9pt;
            }

            QPushButton {
                background: #21262d;
                border: 1px solid #30363d;
                border-radius: 5px;
                padding: 7px;
            }

            QPushButton:hover {
                background: #30363d;
            }

            QPushButton:checked {
                background: #b42318;
                border-color: #d92d20;
            }

            QSlider::groove:horizontal {
                background: #30363d;
                height: 6px;
                border-radius: 3px;
            }

            QSlider::handle:horizontal {
                background: #58a6ff;
                width: 16px;
                margin: -5px 0;
                border-radius: 4px;
            }

            QSlider::groove:vertical {
                background: #30363d;
                width: 8px;
                border-radius: 4px;
            }

            QSlider::handle:vertical {
                background: #58a6ff;
                height: 22px;
                margin: 0 -7px;
                border-radius: 5px;
            }

            QCheckBox {
                spacing: 8px;
            }

            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }

            QToolButton {
                background: #161b22;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 8px;
                text-align: left;
                font-size: 15px;
                font-weight: bold;
            }

            QToolButton:hover {
                background: #21262d;
            }
            """
        )

        central = QWidget()
        self.setCentralWidget(
            central
        )

        main_layout = QVBoxLayout(

            central

        )
        main_layout.setContentsMargins(9, 9, 9, 9)
        main_layout.setSpacing(4)


        # Header

        header = QHBoxLayout()


        voice_logo = QLabel("VOICE")
        voice_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        voice_logo.setStyleSheet(
            "color: white; background: #f43119; border: none; "
            "font-size: 12px; font-weight: 900; padding: 2px 5px;"
        )
        voice_logo.setFixedSize(50, 23)
        voice_logo.setToolTip("VoiceMeeter")

        meeter_logo = QLabel("MEETER")
        meeter_logo.setStyleSheet(
            "color: #e6edf3; font-size: 14px; font-weight: 800;"
        )

        potato = QLabel("Potato")
        potato.setStyleSheet(
            "color: #d5b477; font-size: 18px; font-style: italic; "
            "font-weight: bold;"
        )


        self.status_label = QLabel(

            "● Disconnected"
        )
        self.status_label.setStyleSheet(
            "color: #f85149; font-weight: bold;"

        )


        header.addWidget(voice_logo)
        header.addWidget(meeter_logo)
        header.addWidget(potato)

        header.addStretch()

        header.addWidget(
            self.status_label
        )

        main_layout.addLayout(
            header
        )


        # Mixer

        # The mixer (top) and the Applications / Mic Processing panels
        # (bottom) share the window height through a draggable splitter, so
        # resizing the window never leaves an empty gap between them.
        self.main_splitter = GripSplitter(
            Qt.Orientation.Vertical,
            (DEFAULT_MIXER_PANE_HEIGHT, APPLICATION_PANEL_HEIGHT + 40),
        )
        self.mixer_container = QWidget()
        self.mixer_layout = QHBoxLayout(self.mixer_container)
        self.mixer_layout.setContentsMargins(0, 0, 0, 0)
        self.mixer_layout.setSpacing(4)
        self.main_splitter.addWidget(self.mixer_container)
        main_layout.addWidget(self.main_splitter, 1)


        # Mic processing section. Keep it collapsed by default so the main
        # mixer remains the visual focus, while advanced processing stays one click away.
        self.processing_toggle = QToolButton()
        self.processing_toggle.setText("MIC PROCESSING")
        self.processing_toggle.setCheckable(True)
        self.processing_toggle.setChecked(False)
        self.processing_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.processing_toggle.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.processing_toggle.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.processing_toggle.setStyleSheet(
            "QToolButton { background: #18232e; border: 1px solid #24566b; "
            "border-radius: 6px; padding: 8px; font-size: 15px; "
            "font-weight: bold; text-align: left; }"
            "QToolButton:hover { background: #1d2b38; }"
            "QToolButton:checked { background: #1b2f3b; border-color: #35a7ff; }"
        )
        self.processing_toggle.clicked.connect(self.toggle_processing)


        self.compressor_control = None
        self.gate_control = None
        self.denoiser_control = None
        self.application_control = None

        # Lower panels align with the mixer: mic processing beneath Mic,
        # application sessions beneath the three virtual input strips.
        self.lower_container = QWidget()
        lower_layout = QHBoxLayout(self.lower_container)
        lower_layout.setContentsMargins(0, 0, 0, 0)
        lower_layout.setSpacing(4)

        self.processing_panel = QWidget()
        self.processing_panel.setObjectName("processingPanel")
        self.processing_panel.setStyleSheet(
            "QWidget#processingPanel { background: #101820; "
            "border: 1px solid #24566b; border-radius: 8px; }"
        )
        self.processing_panel_layout = QVBoxLayout(self.processing_panel)
        self.processing_panel_layout.setContentsMargins(5, 5, 5, 5)
        self.processing_panel_layout.setSpacing(4)
        self.processing_panel_layout.addWidget(self.processing_toggle)
        self.processing_tabs = QTabWidget()
        self.processing_tabs.setDocumentMode(True)
        self.processing_tabs.setVisible(False)
        self.processing_tabs.tabBar().setExpanding(True)
        self.processing_tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #30363d; "
            "border-radius: 6px; background: #0d141b; }"
            "QTabBar::tab { background: #18232e; color: #aebdca; "
            "border: 1px solid #30363d; padding: 7px 10px; "
            "min-width: 72px; }"
            "QTabBar::tab:selected { background: #1769aa; color: #ffffff; "
            "border-color: #35a7ff; }"
        )
        self.processing_dialog = None

        self.applications_panel = QWidget()
        self.applications_panel.setObjectName("applicationsPanel")
        self.applications_panel.setStyleSheet(
            "QWidget#applicationsPanel { background: transparent; "
            "border: none; }"
        )
        self.applications_panel_layout = QVBoxLayout(self.applications_panel)
        self.applications_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.applications_panel_layout.setSpacing(3)

        processing_wrapper = QWidget()
        processing_wrapper_layout = QVBoxLayout(processing_wrapper)
        processing_wrapper_layout.setContentsMargins(0, 35, 0, 0)
        processing_wrapper_layout.setSpacing(0)
        processing_wrapper_layout.addWidget(
            self.processing_panel,
            0,
            Qt.AlignmentFlag.AlignTop,
        )

        lower_layout.addWidget(
            processing_wrapper,
            1,
            Qt.AlignmentFlag.AlignTop,
        )
        lower_layout.addWidget(self.applications_panel, 3)
        self.main_splitter.addWidget(self.lower_container)
        # Extra window height goes to the mixer; the lower panels keep the
        # size the user dragged them to.
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 0)
        restored = False
        saved_split = self.window_settings.value("splitter_v1")
        if saved_split is not None:
            try:
                restored = bool(self.main_splitter.restoreState(saved_split))
            except Exception:
                restored = False
        if not restored:
            self.main_splitter.reset_sizes()

        # Connect to VoiceMeeter
        self.connect_vm()


    def connect_vm(self):
        try:
            self.vm = voicemeeterlib.api(
                "potato",
                ratelimit=0.05,
                ldirty=True,
                pdirty=True,
            )

            self.vm.login()

            self.vm_observer = VMObserver(
                self.vm_bridge,
            )

            self.vm.observer.add(
                self.vm_observer
            )

            self.vm.init_thread()
            self.start_mic_level_worker()

            self.connected = True

            self.status_label.setText(
                "● Connected to VoiceMeeter Potato"
            )
            self.status_label.setStyleSheet(
                "color: #3fb950; font-weight: bold;"
            )

            log.info(
                "Connected to VoiceMeeter Potato"
            )
            log.info(
                "VoiceMeeter event observer started"
            )


            self.create_strips()

            self.create_compressor()
            self.create_gate()
            self.create_denoiser()
            self.create_applications()


        except Exception as e:

            log.error(
                f"VoiceMeeter connection failed: "
                f"{type(e).__name__}: {e}"
            )

            self.vm = None
            self.connected = False

            self.status_label.setText(
                "● Disconnected"
            )
            self.status_label.setStyleSheet(
                "color: #f85149; font-weight: bold;"
            )

    def create_strips(self):
        if self.strips:
            return

        for name, index in STRIPS.items():
            widget = StripWidget(
                name,
                self.vm,
                index,
            )


            self.strips[name] = widget


            widget.setMinimumHeight(MIXER_CARD_MIN_HEIGHT)
            widget.setSizePolicy(
                QSizePolicy.Policy.Preferred,
                QSizePolicy.Policy.Expanding,
            )
            self.mixer_layout.addWidget(

                widget

            )


    def toggle_processing(self, expanded):
        """Open or close Mic Processing in a separate popup dialog."""
        if expanded:
            if self.processing_dialog is None:
                self.processing_dialog = QDialog(self)
                self.processing_dialog.setWindowTitle("VMStreamer — Mic Processing")
                self.processing_dialog.setWindowIcon(self.windowIcon())
                self.processing_dialog.setModal(False)
                self.processing_dialog.setWindowFlag(
                    Qt.WindowType.WindowContextHelpButtonHint, False
                )
                self.processing_dialog.setMinimumSize(560, 430)
                self.processing_dialog.resize(620, 500)

                dialog_layout = QVBoxLayout(self.processing_dialog)
                dialog_layout.setContentsMargins(8, 8, 8, 8)
                dialog_layout.setSpacing(6)

                title = QLabel("MIC PROCESSING")
                title.setStyleSheet(
                    "color: #d7e1eb; font-size: 15px; font-weight: bold; "
                    "padding: 3px 4px;"
                )
                dialog_layout.addWidget(title)

                self.processing_tabs.setVisible(True)
                dialog_layout.addWidget(self.processing_tabs, 1)

                self.processing_dialog.finished.connect(
                    self._processing_dialog_closed
                )

            self.processing_tabs.setVisible(True)

            # The controls normally exist already (see connect_vm). They are
            # not kept in sync while the popup is closed, so refresh them now.
            self.create_compressor()
            self.create_gate()
            self.create_denoiser()
            self.sync_processing_controls()

            self.processing_dialog.adjustSize()
            self.processing_dialog.resize(
                max(560, self.processing_dialog.width()),
                max(430, self.processing_dialog.height()),
            )

            # Center the popup over the main window without resizing it.
            center = self.frameGeometry().center()
            rect = self.processing_dialog.frameGeometry()
            rect.moveCenter(center)
            self.processing_dialog.move(rect.topLeft())

            self.processing_dialog.show()
            self.processing_dialog.raise_()
            self.processing_dialog.activateWindow()
            self.processing_toggle.setArrowType(Qt.ArrowType.DownArrow)
        else:
            if self.processing_dialog is not None:
                self.processing_dialog.close()
            self.processing_toggle.setArrowType(Qt.ArrowType.RightArrow)

    def _processing_dialog_closed(self, _result):
        self.processing_toggle.blockSignals(True)
        self.processing_toggle.setChecked(False)
        self.processing_toggle.blockSignals(False)
        self.processing_toggle.setArrowType(Qt.ArrowType.RightArrow)

    def create_compressor(self):
        if self.compressor_control is not None:
            return

        self.compressor_control = CompressorControl(self.vm)
        self.processing_tabs.addTab(self.compressor_control, "COMPRESSOR")

    def create_gate(self):
        if self.gate_control is not None:
            return

        self.gate_control = GateControl(self.vm)
        self.processing_tabs.addTab(self.gate_control, "GATE")

    def create_denoiser(self):
        if self.denoiser_control is not None:
            return

        self.denoiser_control = DenoiserControl(self.vm)
        self.processing_tabs.addTab(self.denoiser_control, "DENOISER")

    def create_applications(self):
        if self.application_control is not None:
            return

        self.application_control = ApplicationControl()
        self.application_control.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.application_control.setMinimumHeight(APPLICATION_PANEL_MIN_HEIGHT)
        self.applications_panel_layout.addWidget(self.application_control, 1)
        self.application_control.setVisible(True)

    def start_mic_level_worker(self):
        """Start continuous Mic level reads away from the Qt GUI thread."""
        if self.vm is None or self.mic_level_thread is not None:
            return

        self.mic_level_thread = QThread(self)
        self.mic_level_worker = MicLevelWorker(self.vm)
        self.mic_level_worker.moveToThread(self.mic_level_thread)

        self.mic_level_thread.started.connect(self.mic_level_worker.start)
        self.mic_level_worker.levels_received.connect(
            self.on_mic_levels_received
        )
        self.mic_level_worker.error.connect(
            lambda message: log.error(message)
        )
        self.mic_level_worker.finished.connect(
            self.mic_level_thread.quit
        )

        self.mic_level_thread.start()

    def stop_mic_level_worker(self):
        """Stop the Mic level worker on its own Qt thread."""
        if self.mic_level_worker is None or self.mic_level_thread is None:
            return

        thread = self.mic_level_thread
        worker = self.mic_level_worker

        try:
            # Run stop() directly on the worker thread and wait for that
            # method to finish. This avoids a queued stop request getting
            # stuck behind shutdown processing and removes the old 2-second
            # wait from the normal close path.
            QMetaObject.invokeMethod(
                worker,
                "stop",
                Qt.ConnectionType.BlockingQueuedConnection,
            )
            thread.quit()
            thread.wait(300)
        except Exception as exc:
            log.error(
                f"Failed to stop Mic level worker: "
                f"{type(exc).__name__}: {exc}"
            )
            thread.quit()
            thread.wait(300)
        finally:
            self.mic_level_worker = None
            self.mic_level_thread = None

    def update_mixer_levels(self):
        """Refresh the visual mixer VU meters on a steady Qt timer."""

        if not self.connected:
            return

        for widget in self.strips.values():
            widget.animate_level()


    def on_mic_levels_received(self, left, right):
        """Receive Mic levels from MicLevelWorker."""
        mic = self.strips.get("Mic")
        if mic is not None:
            mic.set_channel_levels((left, right))


    def on_vm_event(self, event):

        """
        Handle VoiceMeeter events on Qt's main thread.
        """

        if event == "pdirty":
            for widget in self.strips.values():
                widget.sync_from_voicemeeter()

            # The processing controls are only read while their popup is
            # open; opening it synchronizes them (see toggle_processing).
            if (
                self.processing_dialog is not None
                and self.processing_dialog.isVisible()
            ):
                self.sync_processing_controls()

    def sync_processing_controls(self):
        for control in (
            self.compressor_control,
            self.gate_control,
            self.denoiser_control,
        ):
            if control is not None:
                control.sync_from_voicemeeter()

    def closeEvent(self, event):

        """
        Shut down the VoiceMeeter event threads before
        logging out of the VoiceMeeter API.

        The event thread must no longer be making C API
        calls when the VoiceMeeter connection is closed.
        """


        if self.application_control is not None:
            self.application_control.close()

        if hasattr(self, "level_timer"):
            self.level_timer.stop()

        self.stop_mic_level_worker()
        if self.vm is not None:
            try:
                self.vm.observer.remove(
                    self.vm_observer
                )
            except Exception:
                pass

            try:
                # IMPORTANT:
                # Stop and join the updater/producer
                # threads BEFORE logging out.
                self.vm.end_thread()
            except Exception as e:
                log.error(
                    f"Failed to stop VoiceMeeter event thread: "
                    f"{type(e).__name__}: {e}"
                )

            try:
                self.vm.logout()
            except Exception as e:
                log.error(
                    f"Failed to logout from VoiceMeeter: "
                    f"{type(e).__name__}: {e}"
                )

            self.vm = None

            self.connected = False


        self.window_settings.setValue("geometry_v2", self.saveGeometry())
        self.window_settings.setValue("splitter_v1", self.main_splitter.saveState())
        self.window_settings.sync()

        event.accept()


def resource_path(filename):
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, filename)

def main():
    setup_logging()
    log.info("VMStreamer starting")
    qInstallMessageHandler(_qt_message_handler)
    app = QApplication(
        sys.argv

    )

    # Use the bundled VMStreamer icon for the application and all windows.
    # This works both from the source tree and from a PyInstaller build.
    icon_path = resource_path("vmstreamer.ico")
    app_icon = QIcon(icon_path)

    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    # Some Windows Qt styles expose an inherited font with pointSize() == -1
    # (pixel-sized/default font). Give the app a valid point-sized base font.
    base_font = QFont("Segoe UI")
    base_font.setPointSize(9)
    app.setFont(base_font)


    window = MainWindow()

    if not app_icon.isNull():
        window.setWindowIcon(app_icon)
    window.show()

    sys.exit(
        app.exec()
    )


if __name__ == "__main__":
    main()
