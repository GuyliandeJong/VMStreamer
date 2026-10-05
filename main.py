import sys
import math
import json
import os
import time
import warnings
import threading
from pathlib import Path



from PySide6.QtCore import (Qt, Signal, QObject, QTimer, QRectF, QFileInfo, QThread, QSettings, Slot, QMetaObject, QtMsgType, qInstallMessageHandler)
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QLinearGradient, QPainter, QPen

from PySide6.QtWidgets import (

    QApplication,

    QCheckBox,
    QComboBox,
    QFileIconProvider,

    QGridLayout,

    QHBoxLayout,

    QLabel,

    QLineEdit,

    QMainWindow,

    QMenu,
    QPushButton,

    QProgressBar,
    QScrollArea,

    QStyle,
    QSlider,
    QStyleOptionSlider,
    QSizePolicy,

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






# Qt can emit a harmless font warning from an internal style/font fallback
# even though the application explicitly uses a valid point-sized base font.
# Filter only this exact warning; all other Qt messages remain untouched.
def _qt_message_handler(mode, context, message):
    if message == "QFont::setPointSize: Point size <= 0 (-1), must be greater than 0":
        return
    sys.__stderr__.write(f"{message}\n")


# VoiceMeeter strip indexes

STRIPS = {

    "Mic": 0,

    "Game": 5,

    "Chat": 6,

    "Media": 7,

}

# Mixer layout dimensions — adjust these when fine-tuning the UI.
MIXER_CARD_HEIGHT = 655
CHANNEL_HEADER_HEIGHT = 58
CHANNEL_FADER_HEIGHT = 455
MIC_METER_HEIGHT = 455
FADER_TO_GAIN_GAP = 5
MIXER_BUTTON_HEIGHT = 28
ROUTING_LABEL_HEIGHT = 14
ROUTING_BUTTON_HEIGHT = 28
APPLICATION_PANEL_HEIGHT = 300

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
    mic_levels_received = Signal(float, float)





class VMObserver:

    """Receives VoiceMeeter API events."""



    def __init__(self, bridge, vm):

        self.bridge = bridge
        self.vm = vm



    @staticmethod
    def _channel_levels(raw_levels):
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
            return -200.0, -200.0
        if len(levels) == 1:
            levels.append(levels[0])
        return levels[0], levels[1]


    def on_update(self, event):

        # Read the level on VoiceMeeter's own background update thread.
        # This keeps the Qt/UI thread free from a 30 FPS COM property read,
        # which was causing the meter animation to feel laggy.
        if event == "ldirty":
            try:
                raw_levels = self.vm.strip[0].levels.prefader
                left, right = self._channel_levels(raw_levels)
                self.bridge.mic_levels_received.emit(left, right)
            except Exception as exc:
                print(
                    "Failed to read VoiceMeeter Mic levels: "
                    f"{type(exc).__name__}: {exc}"
                )

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

        self.setMinimumHeight(230)
        self.setMaximumHeight(230)



        # Vertical meters should rise from the bottom as the signal increases.
        self.setInvertedAppearance(False)
        self._display_level = float(self.minimum())
        self._target_level = float(self.minimum())
        self._last_update = time.monotonic()
        self._last_animation = self._last_update
        self._last_level_event = time.monotonic()
        self._hold_until = 0.0



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
        self._last_level_event = time.monotonic()

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

    def _apply_display_level(self):
        display_level = int(round(self._display_level))
        display_level = max(self.minimum(), min(self.maximum(), display_level))
        self.setValue(display_level)



class NumericEdit(QLineEdit):
    """Editable numeric field that selects its contents when focused."""

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.selectAll()


class CompressorControl(QWidget):
    """
    Compressor controls for the Mic strip.

    All controls map directly to mic.comp.
    """

    def __init__(self, vm):
        super().__init__()

        self.vm = vm
        self.comp = vm.strip[0].comp

        self.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        self.controls = {}

        grid = QGridLayout()
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(6)

        # VoiceMeeter compressor ranges:
        # knob       0..10
        # gainin    -24..24 dB
        # ratio       1..8
        # threshold -40..-3 dB
        # attack      0..200 ms
        # release     0..5000 ms
        # knee        0..1
        # gainout   -24..24 dB

        self.add_slider(
            grid,
            row=0,
            column=0,
            name="Amount",
            key="knob",
            minimum=0,
            maximum=100,
            scale=10,
            suffix="",
        )

        self.add_slider(
            grid,
            row=1,
            column=0,
            name="Input Gain",
            key="gainin",
            minimum=-240,
            maximum=240,
            scale=10,
            suffix=" dB",
        )

        self.add_slider(
            grid,
            row=2,
            column=0,
            name="Ratio",
            key="ratio",
            minimum=10,
            maximum=80,
            scale=10,
            suffix=":1",
        )

        self.add_slider(
            grid,
            row=3,
            column=0,
            name="Threshold",
            key="threshold",
            minimum=-400,
            maximum=-30,
            scale=10,
            suffix=" dB",
        )

        self.add_slider(
            grid,
            row=4,
            column=0,
            name="Attack",
            key="attack",
            minimum=0,
            maximum=2000,
            scale=10,
            suffix=" ms",
        )

        self.add_slider(
            grid,
            row=5,
            column=0,
            name="Release",
            key="release",
            minimum=0,
            maximum=50000,
            scale=10,
            suffix=" ms",
        )

        self.add_slider(
            grid,
            row=6,
            column=0,
            name="Knee",
            key="knee",
            minimum=0,
            maximum=100,
            scale=100,
            suffix="",
        )

        self.add_slider(
            grid,
            row=7,
            column=0,
            name="Output Gain",
            key="gainout",
            minimum=-240,
            maximum=240,
            scale=10,
            suffix=" dB",
        )

        layout.addLayout(grid)

        self.makeup_checkbox = QCheckBox("Auto Makeup")
        self.makeup_checkbox.stateChanged.connect(
            self.on_makeup_changed
        )

        layout.addWidget(
            self.makeup_checkbox,
            alignment=Qt.AlignmentFlag.AlignLeft,
        )

        self.sync_from_voicemeeter()

    def add_slider(
        self,
        grid,
        row,
        column,
        name,
        key,
        minimum,
        maximum,
        scale,
        suffix,
    ):
        container = QWidget()

        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        name_label = QLabel(name)
        name_label.setMinimumWidth(76)

        value_edit = NumericEdit()
        value_edit.setAlignment(
            Qt.AlignmentFlag.AlignRight
        )
        value_edit.setFixedWidth(74)
        value_edit.setToolTip(
            "Click and type a value, then press Enter."
        )
        value_edit.editingFinished.connect(
            lambda k=key: self.on_value_edit_finished(k)
        )

        layout.addWidget(name_label)

        slider = QSlider(
            Qt.Orientation.Horizontal
        )
        slider.setRange(
            minimum,
            maximum,
        )
        slider.setMinimumWidth(36)

        slider.valueChanged.connect(
            lambda value,
            k=key,
            s=scale,
            suf=suffix:
            self.on_slider_changed(
                k,
                value,
                s,
                suf,
            )
        )

        layout.addWidget(slider, 1)
        layout.addWidget(value_edit)

        grid.addWidget(
            container,
            row,
            column,
        )

        self.controls[key] = {
            "slider": slider,
            "edit": value_edit,
            "scale": scale,
            "suffix": suffix,
            "minimum": minimum / scale,
            "maximum": maximum / scale,
        }

    def format_actual(self, key, actual):
        suffix = self.controls[key]["suffix"]

        if key == "knob":
            return f"{actual:.1f}"

        if key == "ratio":
            return f"{actual:.1f}:1"

        if key == "knee":
            return f"{actual:.2f}"

        if key in ("gainin", "gainout"):
            return f"{actual:+.1f}{suffix}"

        if key == "threshold":
            return f"{actual:.1f}{suffix}"

        if key in ("attack", "release"):
            if actual >= 1000:
                return f"{actual / 1000:.2f} s"

            return f"{actual:.1f}{suffix}"

        return f"{actual:.1f}{suffix}"

    def format_value(self, key, value):
        scale = self.controls[key]["scale"]
        actual = value / scale
        return self.format_actual(key, actual)

    def parse_value(self, key, text):
        """
        Parse the value typed by the user.

        The displayed units are accepted as well, so for example:
        - "4" or "4:1" for ratio
        - "-18" or "-18 dB" for threshold
        - "150" or "150 ms" for release
        - "1.5 s" for release
        """

        value = text.strip().lower()

        if key == "ratio":
            value = value.replace(":1", "").strip()

        if key in ("gainin", "gainout", "threshold"):
            value = value.replace("db", "").strip()

        if key in ("attack", "release"):
            if value.endswith("ms"):
                value = value[:-2].strip()
            elif value.endswith("s"):
                value = value[:-1].strip()
                return float(value) * 1000.0

        return float(value)

    def set_parameter(self, key, actual):
        """Set a compressor parameter through the safest API path."""

        # VoiceMeeter's advanced compressor timing parameters are
        # exposed by the Remote API, but using the generic float setter
        # for these two parameters can trigger an access violation with
        # some VoiceMeeter/Python combinations.  The Remote API script
        # path uses VoiceMeeter's native parameter parser instead.
        if key in ("attack", "release"):
            parameter = key.capitalize()
            try:
                self.vm.sendtext(
                    f"Strip[0].Comp.{parameter}={actual:.6f}"
                )
            except OSError:
                # VoiceMeeter's native multi-parameter call can raise a
                # Windows access-violation exception after the command has
                # already been accepted by VoiceMeeter.  Attack/Release are
                # confirmed to use the native script path successfully, so
                # do not report this as an invalid user value.  The normal
                # pdirty event will bring the authoritative value back.
                return
            return

        setattr(
            self.comp,
            key,
            actual,
        )

    def on_value_edit_finished(self, key):
        control = self.controls[key]
        edit = control["edit"]

        try:
            actual = self.parse_value(
                key,
                edit.text(),
            )

            if not math.isfinite(actual):
                raise ValueError("Value must be finite.")

            minimum = control["minimum"]
            maximum = control["maximum"]

            if actual < minimum or actual > maximum:
                raise ValueError(
                    f"Value must be between "
                    f"{minimum:g} and {maximum:g}."
                )

            slider_value = int(
                round(actual * control["scale"])
            )

            slider = control["slider"]

            slider.blockSignals(True)
            slider.setValue(slider_value)
            slider.blockSignals(False)

            edit.setText(
                self.format_actual(
                    key,
                    actual,
                )
            )

            self.set_parameter(key, actual)

        except Exception as e:
            print(
                f"Invalid compressor {key} value: "
                f"{type(e).__name__}: {e}"
            )

            # Restore the current VoiceMeeter value instead
            # of leaving an invalid value in the field.
            try:
                actual = getattr(
                    self.comp,
                    key,
                )
                edit.setText(
                    self.format_actual(
                        key,
                        actual,
                    )
                )
            except Exception:
                pass

    def on_slider_changed(
        self,
        key,
        value,
        scale,
        suffix,
    ):
        actual = value / scale

        self.controls[key]["edit"].setText(
            self.format_actual(
                key,
                actual,
            )
        )

        try:
            self.set_parameter(key, actual)
        except Exception as e:
            print(
                f"Failed to set compressor {key}: "
                f"{type(e).__name__}: {e}"
            )

    def on_makeup_changed(self, state):
        enabled = (
            state
            == Qt.CheckState.Checked.value
        )

        try:
            self.comp.makeup = enabled
        except Exception as e:
            print(
                f"Failed to set compressor makeup: "
                f"{type(e).__name__}: {e}"
            )

    def sync_from_voicemeeter(self):
        """
        Synchronize compressor controls from VoiceMeeter.
        """

        try:
            values = {
                "knob": self.comp.knob,
                "gainin": self.comp.gainin,
                "ratio": self.comp.ratio,
                "threshold": self.comp.threshold,
                "attack": self.comp.attack,
                "release": self.comp.release,
                "knee": self.comp.knee,
                "gainout": self.comp.gainout,
            }

            for key, actual in values.items():
                control = self.controls[key]

                slider_value = int(
                    round(
                        actual
                        * control["scale"]
                    )
                )

                slider = control["slider"]

                slider.blockSignals(True)
                slider.setValue(slider_value)
                slider.blockSignals(False)

                # Do not overwrite text while the user is
                # actively typing into the field.
                if not control["edit"].hasFocus():
                    control["edit"].setText(
                        self.format_actual(
                            key,
                            actual,
                        )
                    )

            makeup = self.comp.makeup

            self.makeup_checkbox.blockSignals(
                True
            )
            self.makeup_checkbox.setChecked(
                makeup
            )
            self.makeup_checkbox.blockSignals(
                False
            )

        except Exception as e:
            print(
                f"Failed to synchronize compressor: "
                f"{type(e).__name__}: {e}"
            )


class GateControl(QWidget):
    """Editable controls for mic.gate."""
    def __init__(self, vm):
        super().__init__()
        self.vm = vm
        self.gate = vm.strip[0].gate
        self.setVisible(False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        self.controls = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(6)
        self.add_slider(grid, 0, 0, "Amount", "knob", 0, 100, 10, "")
        self.add_slider(grid, 1, 0, "Threshold", "threshold", -600, -100, 10, " dB")
        self.add_slider(grid, 2, 0, "Damping", "damping", -600, -100, 10, " dB")
        self.add_slider(grid, 3, 0, "Sidechain", "bpsidechain", 100, 4000, 1, " Hz")
        self.add_slider(grid, 4, 0, "Attack", "attack", 0, 10000, 10, " ms")
        self.add_slider(grid, 5, 0, "Hold", "hold", 0, 50000, 10, " ms")
        self.add_slider(grid, 6, 0, "Release", "release", 0, 50000, 10, " ms")
        layout.addLayout(grid)
        self.sync_from_voicemeeter()

    def add_slider(self, grid, row, column, name, key, minimum, maximum, scale, suffix):
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
        value_edit.editingFinished.connect(lambda k=key: self.on_value_edit_finished(k))
        layout.addWidget(name_label)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setMinimumWidth(36)
        slider.valueChanged.connect(lambda value, k=key, s=scale, suf=suffix: self.on_slider_changed(k, value, s, suf))
        layout.addWidget(slider, 1)
        layout.addWidget(value_edit)
        grid.addWidget(container, row, column)
        self.controls[key] = {"slider": slider, "edit": value_edit, "scale": scale, "suffix": suffix, "minimum": minimum / scale, "maximum": maximum / scale}

    def format_actual(self, key, actual):
        suffix = self.controls[key]["suffix"]
        if key == "knob":
            return f"{actual:.1f}"
        if key in ("threshold", "damping"):
            return f"{actual:.1f}{suffix}"
        if key == "bpsidechain":
            return f"{actual:.0f}{suffix}"
        if key in ("attack", "hold", "release"):
            if actual >= 1000:
                return f"{actual / 1000:.2f} s"
            return f"{actual:.1f}{suffix}"
        return f"{actual:.1f}{suffix}"

    def parse_value(self, key, text):
        value = text.strip().lower()
        if key in ("threshold", "damping"):
            value = value.replace("db", "").strip()
        if key == "bpsidechain":
            value = value.replace("hz", "").strip()
        if key in ("attack", "hold", "release"):
            if value.endswith("ms"):
                value = value[:-2].strip()
            elif value.endswith("s"):
                value = value[:-1].strip()
                return float(value) * 1000.0
        return float(value)

    def on_value_edit_finished(self, key):
        control = self.controls[key]
        edit = control["edit"]
        try:
            actual = self.parse_value(key, edit.text())
            if not math.isfinite(actual):
                raise ValueError("Value must be finite.")
            if actual < control["minimum"] or actual > control["maximum"]:
                raise ValueError(f"Value must be between {control['minimum']:g} and {control['maximum']:g}.")
            slider = control["slider"]
            slider.blockSignals(True)
            slider.setValue(int(round(actual * control["scale"])))
            slider.blockSignals(False)
            edit.setText(self.format_actual(key, actual))
            setattr(self.gate, key, actual)
        except Exception as e:
            print(f"Invalid gate {key} value: {type(e).__name__}: {e}")
            try:
                edit.setText(self.format_actual(key, getattr(self.gate, key)))
            except Exception:
                pass

    def on_slider_changed(self, key, value, scale, suffix):
        actual = value / scale
        self.controls[key]["edit"].setText(self.format_actual(key, actual))
        try:
            setattr(self.gate, key, actual)
        except Exception as e:
            print(f"Failed to set gate {key}: {type(e).__name__}: {e}")

    def sync_from_voicemeeter(self):
        try:
            values = {"knob": self.gate.knob, "threshold": self.gate.threshold, "damping": self.gate.damping, "bpsidechain": self.gate.bpsidechain, "attack": self.gate.attack, "hold": self.gate.hold, "release": self.gate.release}
            for key, actual in values.items():
                control = self.controls[key]
                slider = control["slider"]
                slider.blockSignals(True)
                slider.setValue(int(round(actual * control["scale"])))
                slider.blockSignals(False)
                if not control["edit"].hasFocus():
                    control["edit"].setText(self.format_actual(key, actual))
        except Exception as e:
            print(f"Failed to synchronize gate: {type(e).__name__}: {e}")


class DenoiserControl(QWidget):
    """Editable controls for mic.denoiser."""
    def __init__(self, vm):
        super().__init__()
        self.vm = vm
        self.denoiser = vm.strip[0].denoiser
        self.setVisible(False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        self.controls = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(6)
        self.add_slider(grid, 0, 0, "Amount", "knob", 0, 100, 10, "")
        layout.addLayout(grid)
        self.sync_from_voicemeeter()

    def add_slider(self, grid, row, column, name, key, minimum, maximum, scale, suffix):
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
        value_edit.editingFinished.connect(lambda k=key: self.on_value_edit_finished(k))
        layout.addWidget(name_label)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setMinimumWidth(36)
        slider.valueChanged.connect(lambda value, k=key, s=scale, suf=suffix: self.on_slider_changed(k, value, s, suf))
        layout.addWidget(slider, 1)
        layout.addWidget(value_edit)
        grid.addWidget(container, row, column)
        self.controls[key] = {"slider": slider, "edit": value_edit, "scale": scale, "suffix": suffix, "minimum": minimum / scale, "maximum": maximum / scale}

    def format_actual(self, key, actual):
        if key == "knob":
            return f"{actual:.1f}"
        return f"{actual:.1f}{self.controls[key]['suffix']}"

    def on_value_edit_finished(self, key):
        control = self.controls[key]
        edit = control["edit"]
        try:
            actual = float(edit.text().strip())
            if not math.isfinite(actual):
                raise ValueError("Value must be finite.")
            if actual < control["minimum"] or actual > control["maximum"]:
                raise ValueError(f"Value must be between {control['minimum']:g} and {control['maximum']:g}.")
            slider = control["slider"]
            slider.blockSignals(True)
            slider.setValue(int(round(actual * control["scale"])))
            slider.blockSignals(False)
            edit.setText(self.format_actual(key, actual))
            setattr(self.denoiser, key, actual)
        except Exception as e:
            print(f"Invalid denoiser {key} value: {type(e).__name__}: {e}")
            try:
                edit.setText(self.format_actual(key, getattr(self.denoiser, key)))
            except Exception:
                pass

    def on_slider_changed(self, key, value, scale, suffix):
        actual = value / scale
        self.controls[key]["edit"].setText(self.format_actual(key, actual))
        try:
            setattr(self.denoiser, key, actual)
        except Exception as e:
            print(f"Failed to set denoiser {key}: {type(e).__name__}: {e}")

    def sync_from_voicemeeter(self):
        try:
            for key, control in self.controls.items():
                actual = getattr(self.denoiser, key)
                slider = control["slider"]
                slider.blockSignals(True)
                slider.setValue(int(round(actual * control["scale"])))
                slider.blockSignals(False)
                if not control["edit"].hasFocus():
                    control["edit"].setText(self.format_actual(key, actual))
        except Exception as e:
            print(f"Failed to synchronize denoiser: {type(e).__name__}: {e}")


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
            "Mic": "🎙",
            "Game": "🎮",
            "Chat": "💬",
            "Media": "♫",
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
        icon_label = QLabel(source_icons.get(name, ""))
        icon_label.setStyleSheet(
            f"color: {accent}; background: transparent; border: none; "
            "font-size: 18px;"
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



        # Mic signal meter. The dB readout remains below the fader as gain.

        meter_layout = QHBoxLayout()



        self.vu_meters = [VUMeter(), VUMeter()] if name == "Mic" else []
        if self.vu_meters:
            for meter in self.vu_meters:
                meter.setFixedHeight(MIC_METER_HEIGHT)
        self.vu_meter = self.vu_meters[0] if self.vu_meters else None



        if self.vu_meter is not None:
            for meter in self.vu_meters:
                meter_layout.addWidget(meter)



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

        self.fader.setMinimumHeight(

            CHANNEL_FADER_HEIGHT

        )
        self.fader.setMaximumHeight(CHANNEL_FADER_HEIGHT)
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
            # Keep the Mic fader centered in the card so its gain readout
            # lines up with the other channel gain readouts. The two input
            # meters remain grouped to the left of the fader.
            control_layout = QGridLayout()
            control_layout.setContentsMargins(0, 0, 0, 0)
            control_layout.setHorizontalSpacing(12)
            control_layout.setVerticalSpacing(0)
            control_layout.setColumnStretch(0, 1)
            control_layout.setColumnStretch(1, 0)
            control_layout.setColumnStretch(2, 1)

            meter_container = QWidget()
            meter_container_layout = QHBoxLayout(meter_container)
            meter_container_layout.setContentsMargins(0, 0, 35, 0)
            meter_container_layout.setSpacing(meter_layout.spacing())
            while meter_layout.count():
                item = meter_layout.takeAt(0)
                if item.widget() is not None:
                    meter_container_layout.addWidget(item.widget())

            control_layout.addWidget(
                meter_container,
                0,
                0,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            )
            fader_container = QWidget()
            fader_container_layout = QHBoxLayout(fader_container)
            fader_container_layout.setContentsMargins(0, 0, 5, 0)
            fader_container_layout.addWidget(
                self.fader,
                0,
                Qt.AlignmentFlag.AlignCenter,
            )

            control_layout.addWidget(
                fader_container,
                0,
                1,
                Qt.AlignmentFlag.AlignCenter,
            )
            layout.addLayout(control_layout)
        else:
            control_layout = QHBoxLayout()
            control_layout.setContentsMargins(0, 0, 0, 0)
            control_layout.addStretch(1)
            control_layout.addWidget(
                self.fader,
                0,
                Qt.AlignmentFlag.AlignVCenter,
            )
            control_layout.addStretch(1)
            layout.addLayout(control_layout)



        # Gain readout
        layout.addSpacing(FADER_TO_GAIN_GAP)

        self.gain_label = QLabel()



        self.gain_label.setAlignment(

            Qt.AlignmentFlag.AlignCenter

        )
        if self.vu_meter is not None:
            self.gain_label.setStyleSheet(
                "color: #aebdca; font-size: 12px; margin-top: -10px;"
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
            print(
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

            print(

                f"Failed to set {self.name} gain: "

                f"{type(e).__name__}: {e}"

            )

            return



        self.update_gain_label()



    def on_mute_clicked(self, checked):

        try:

            self.strip.mute = checked

        except Exception as e:

            print(

                f"Failed to set {self.name} mute: "

                f"{type(e).__name__}: {e}"

            )



    def on_solo_clicked(self, checked):

        try:

            self.strip.solo = checked

        except Exception as e:

            print(

                f"Failed to set {self.name} solo: "

                f"{type(e).__name__}: {e}"

            )



    def on_mono_clicked(self, checked):

        try:

            self.strip.mono = checked

        except Exception as e:

            print(

                f"Failed to set {self.name} mono: "

                f"{type(e).__name__}: {e}"

            )



    def get_level(self):

        """

        Read the current pre-fader input level.



        The installed API returns a tuple containing

        individual channel levels for virtual strips.

        """



        level = self.strip.levels.prefader



        if isinstance(level, tuple):

            valid_levels = [

                value

                for value in level

                if isinstance(

                    value,

                    (int, float),

                )

            ]



            if not valid_levels:

                return -200.0



            return max(valid_levels)



        if isinstance(

            level,

            (int, float),

        ):

            return level



        return -200.0



    def get_channel_levels(self):
        """Return the Mic strip's left and right input levels in dB."""
        # VoiceMeeter displays the hardware strip's input meter before its
        # fader, so use the matching pre-fader level source here.
        raw_levels = self.strip.levels.prefader
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
            return [-200.0, -200.0]
        if len(levels) == 1:
            levels.append(levels[0])
        return levels[:2]

    def set_channel_levels(self, levels):
        """Apply already-read Mic levels to the UI without any VM I/O."""
        if self.vu_meter is None:
            return

        for meter, level in zip(self.vu_meters, levels):
            meter.set_level(level)


    def update_level(self):
        """Read and apply the current Mic input level when explicitly requested."""
        try:
            self.set_channel_levels(self.get_channel_levels())
        except Exception as e:
            print(
                f"Failed to update {self.name} level: "
                f"{type(e).__name__}: {e}"
            )


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



            self.update_level()



        except Exception as e:

            print(

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
                        })
                    except Exception:
                        continue

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
                    "volume": info["volume"],
                    "muted": info["muted"],
                    "session_count": len(info["sessions"]),
                }
                for key, info in found.items()
            ]

            self.topology_updated.emit(snapshot)
            self.update_peaks()
            self.update_states()

        except Exception as exc:
            self.error.emit(
                f"VoiceMeeter application scan failed: "
                f"{type(exc).__name__}: {exc}"
            )

    @Slot()
    def update_peaks(self):
        peaks = {}
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
            peaks[group_key] = group_peak if meter_available else None

        now = time.monotonic()
        if now - self._last_peak_emit >= (1.0 / 60.0):
            self._last_peak_emit = now
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

    hide_requested = Signal(str, bool)

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
            f"{self.display_name} — routed to {bus}"
        )

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(20, 20)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setToolTip(self.display_name)
        try:
            if executable_path and os.path.isfile(executable_path):
                app_icon = QFileIconProvider().icon(QFileInfo(executable_path))
                self.icon_label.setPixmap(app_icon.pixmap(20, 20))
        except Exception:
            pass

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

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        action = (
            menu.addAction("Show application")
            if self.is_hidden
            else menu.addAction("Hide application")
        )

        chosen = menu.exec(event.globalPos())
        if chosen is action:
            self.hide_requested.emit(self.hide_key, not self.is_hidden)

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
    shutdown_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setVisible(False)
        self.sessions = {}
        self.rows = {name: {} for name in self.BUS_NAMES}
        self._topology_signature = None
        self._closing = False
        self.show_hidden = False
        self.settings = QSettings("VMStreamer", "VMStreamer")
        self.hidden_applications = self._load_hidden_applications()

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

        self.hidden_button = QPushButton("👁")
        self.hidden_button.setCheckable(True)
        self.hidden_button.setFixedSize(32, 28)
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
            box = QWidget()
            box.setObjectName("applicationBusCard")
            box.setStyleSheet(
                "QWidget#applicationBusCard {"
                f"background: #101820; border: 1px solid {colors['border']}; "
                "border-radius: 8px; }"
            )
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
            box_layout.addWidget(title)

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

    def _load_hidden_applications(self):
        raw = self.settings.value("hidden_applications", "")
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

    def _save_hidden_applications(self):
        self.settings.setValue(
            "hidden_applications",
            json.dumps(sorted(self.hidden_applications)),
        )
        self.settings.sync()

    def toggle_hidden_visibility(self, checked):
        self.show_hidden = bool(checked)
        self.hidden_button.setToolTip(
            "Hide hidden applications"
            if self.show_hidden
            else "Show hidden applications"
        )
        self.rebuild_rows()
        self.update_status()

    def on_hide_requested(self, hide_key, hidden):
        hide_key = str(hide_key or "").casefold()
        if not hide_key:
            return

        if hidden:
            self.hidden_applications.add(hide_key)
        else:
            self.hidden_applications.discard(hide_key)

        self._save_hidden_applications()
        self.rebuild_rows()
        self.update_status()

    def update_status(self):
        visible = [
            info
            for info in self.sessions.values()
            if (
                self.show_hidden
                or info.get("hide_key", "") not in self.hidden_applications
            )
        ]

        counts = {
            bus: sum(1 for info in visible if info["bus"] == bus)
            for bus in self.BUS_NAMES
        }

        hidden_count = sum(
            1
            for info in self.sessions.values()
            if info.get("hide_key", "") in self.hidden_applications
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

    def on_worker_error(self, message):
        if not self._closing:
            self.status_label.setText(message)
        print(message)

    def on_topology_updated(self, snapshot):
        if self._closing:
            return

        self.sessions = {
            item["session_key"]: item
            for item in snapshot
        }

        signature = tuple(
            sorted(
                (key, info["bus"])
                for key, info in self.sessions.items()
            )
        )

        if signature != self._topology_signature:
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
            hide_key = info.get("hide_key", "")
            hidden = hide_key in self.hidden_applications

            if hidden and not self.show_hidden:
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
                    f"{row.display_name} — hidden application — routed to {row.bus}"
                )

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
            raw_levels = self.vm.strip[0].levels.prefader
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

        self.vm_bridge.mic_levels_received.connect(
            self.on_mic_levels_received
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
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)



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

        self.mixer_layout = QHBoxLayout()

        self.mixer_layout.setSpacing(4)
        main_layout.addLayout(self.mixer_layout, 0)



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
        lower_layout = QHBoxLayout()
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
        self.processing_panel_layout.addWidget(self.processing_tabs, 1)

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
        lower_layout.addWidget(
            self.applications_panel,
            3,
            Qt.AlignmentFlag.AlignTop,
        )
        # Keep the lower Applications / Mic Processing section anchored to
        # the bottom of the available window instead of leaving empty space
        # underneath it.
        main_layout.addStretch(1)
        main_layout.addLayout(lower_layout, 0)

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
                self.vm,

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



            print(

                "Connected to VoiceMeeter Potato"

            )

            print(

                "VoiceMeeter event observer started"

            )



            self.create_strips()

            self.create_compressor()
            self.create_gate()
            self.create_denoiser()
            self.create_applications()



        except Exception as e:

            print(

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



            widget.setFixedHeight(MIXER_CARD_HEIGHT)
            self.mixer_layout.addWidget(

                widget

            )



    def toggle_processing(self, expanded):
        """Show or hide the advanced Mic processing controls."""
        self.processing_tabs.setVisible(bool(expanded))
        self.processing_toggle.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        self.processing_panel.updateGeometry()
        self.processing_panel_layout.invalidate()


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
            QSizePolicy.Policy.Fixed,
        )
        self.application_control.setFixedHeight(APPLICATION_PANEL_HEIGHT)
        self.applications_panel_layout.addWidget(
            self.application_control,
            0,
            Qt.AlignmentFlag.AlignTop,
        )
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
            lambda message: print(message)
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
            print(
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
        """Receive Mic levels from the VoiceMeeter worker thread."""
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



            if self.compressor_control is not None:

                self.compressor_control.sync_from_voicemeeter()

            if self.gate_control is not None:
                self.gate_control.sync_from_voicemeeter()

            if self.denoiser_control is not None:
                self.denoiser_control.sync_from_voicemeeter()



        elif event == "ldirty":
            # Mic levels are delivered separately by VMObserver so the Qt
            # thread never has to query VoiceMeeter for levels.
            pass



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

                print(

                    f"Failed to stop VoiceMeeter event thread: "

                    f"{type(e).__name__}: {e}"

                )



            try:

                self.vm.logout()

            except Exception as e:

                print(

                    f"Failed to logout from VoiceMeeter: "

                    f"{type(e).__name__}: {e}"

                )



            self.vm = None

            self.connected = False



        self.window_settings.setValue("geometry_v2", self.saveGeometry())
        self.window_settings.sync()

        event.accept()





def main():

    qInstallMessageHandler(_qt_message_handler)

    app = QApplication(

        sys.argv

    )

    # Use the bundled VMStreamer icon for the application and all windows.
    # This works both from the source tree and from a PyInstaller build.
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        icon_path = Path(sys._MEIPASS) / "vmstreamer.ico"
    else:
        icon_path = Path(__file__).resolve().parent / "vmstreamer.ico"

    if icon_path.exists():
        app_icon = QIcon(str(icon_path))
        app.setWindowIcon(app_icon)
    else:
        app_icon = QIcon()

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
