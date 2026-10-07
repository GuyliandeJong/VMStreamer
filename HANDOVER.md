# VMStreamer — Project Handover

## Project

VMStreamer is a Windows desktop controller for VoiceMeeter Potato. It provides a compact custom UI for Mic, Game, Chat and Media instead of cloning the entire VoiceMeeter interface.

Repository: https://github.com/GuylianDeJong/VMStreamer
Current branch: `main`
Current release: `v1.0.2` (published/latest)

## Environment

- Windows
- Python 3.14.6
- Project: `C:\Users\Dutchie_\Documents\Projects\VMStreamer`
- Virtual environment: `.venv`
- PySide6 6.11.2
- voicemeeter-api 2.7.2
- pycaw
- comtypes
- psutil
- winappaudiorouter
- PyInstaller

Dependencies are listed in `requirements.txt`.
- VoiceMeeter Potato 3.1.2.2
- VS Code / PowerShell

## Development Rules

- The primary source file is always `main.py`.
- Do not create renamed variants such as `main_final.py`, `main_popup.py`, etc.
- Prefer complete files when providing code changes.
- Make incremental changes and test each logical change.
- Do not casually rewrite the working audio/threading architecture.

## VoiceMeeter Mapping

```python
STRIPS = {
    "Mic": 0,
    "Game": 5,
    "Chat": 6,
    "Media": 7,
}
```

- Strip 0 = Mic / Hardware Input 1
- Strip 5 = Game / VAIO
- Strip 6 = Chat / VAIO AUX
- Strip 7 = Media / VAIO3
- Mic hardware: Focusrite Scarlett 4i4 4th Gen + Beyerdynamic M 70 PRO X
- Hardware Inputs 2–5 and the output buses themselves are intentionally not exposed.
- Routing buttons: Mic has B1; Game, Chat and Media have A1–A3.

## Main Controls

All four strips expose:

- Gain
- Mute
- Solo
- Mono

Mic additionally exposes:

- Compressor
- Gate
- Denoiser

Microphone processing is shown in a separate popup so opening it does not resize the main window.

## VoiceMeeter API

Connection uses:

```python
voicemeeterlib.api(
    "potato",
    ratelimit=0.05,
    ldirty=True,
    pdirty=True,
)
```

Important findings:

- `vm.login()` does not start the update thread by itself.
- `vm.init_thread()` is required.
- Observer callback signature is `on_update(self, event)`.
- `pdirty=True` enables parameter dirty-state checking.
- VoiceMeeter update/event threads must be stopped before `logout()`.

Shutdown has been tested and is stable.

## Microphone Processing API

Compressor properties:

`knob`, `gainin`, `ratio`, `threshold`, `attack`, `release`, `knee`, `gainout`, `makeup`

Gate properties:

`knob`, `threshold`, `damping`, `bpsidechain`, `attack`, `hold`, `release`

Denoiser:

`knob`

Compressor Attack/Release previously caused native API access violations. A safer native setter implementation (`vm.sendtext`) fixed this, and the gate's Attack/Hold/Release use it too. Do not casually replace it.

Compressor, Gate and Denoiser share one implementation, `ProcessingPanel`. Each block is a small subclass that lists its parameters in `PARAMETERS` and names its `sendtext` parameters in `SCRIPT_KEYS`. Display and typed-value handling live in `format_parameter()` and `parse_parameter()`.

The processing controls are only synchronized while the popup is open, and once when it opens.

## Audio Meter Architecture

### Mic

Mic level sampling runs in a dedicated worker and communicates with Qt through signals. With `ldirty=True` voicemeeterlib serves levels from a cache that refreshes every `ratelimit` (50 ms), so the worker only emits when the value changed. `ldirty` events are not forwarded to the GUI thread.

### Applications

Windows application audio sessions are sampled in a dedicated Python loop rather than a GUI-thread QTimer.

Target sampling interval is approximately 10 ms; GUI delivery is approximately 60 FPS. Between two deliveries the highest sampled peak is kept. `update_peaks()` runs on the peak thread only.

This replaced an earlier architecture that produced 400–560 ms sampling stalls and GUI hangs. The dedicated loop fixed the problem.

Do not replace this with GUI-thread pycaw polling without testing.

## VU Meter

A double dB-to-fraction conversion was previously causing incorrect readings.

Correct pipeline:

```text
VoiceMeeter dB
→ target dB
→ display dB
→ QProgressBar dB
→ paint conversion
```

Range is `-60 .. 0 dB`.

Do not reintroduce the double conversion.

## Application Detection

Applications are detected through Windows audio sessions and grouped by actual VoiceMeeter routing/device.

Groups:

- Game / VAIO
- Chat / VAIO AUX
- Media / VAIO3

Multiple Windows sessions may belong to the same application. Do not collapse sessions solely by executable name.

Grouped application controls apply volume/mute to the underlying sessions. The group meter uses the highest active peak.

Friendly names include:

- `ms-teams.exe` → Microsoft Teams
- `msedgewebview2.exe` → Microsoft Edge WebView2
- `steam.exe` → Steam
- `steamwebhelper.exe` → Steam Client Web
- `signalrgbcore.exe` → SignalRGB Core
- `brave.exe` → Brave Browser

## Application UI

Three application columns remain separated by virtual channel:

```text
Game | Chat | Media
```

Rows provide:

- application name
- volume
- percentage
- mute/speaker control
- live green meter

Volume bars support click/drag and scroll-wheel fine adjustment.

Rows are not rebuilt while a row is being dragged or a volume slider is held. Application icons are cached per executable.

## Moving Applications

Dragging a row onto another column sets the per-app output device in Windows through `winappaudiorouter`. Windows re-binds the audio when the app next starts playback, so the row is marked as moving and the session list is scanned every second for a while.

## Application Hiding

Implemented:

- Hiding is per virtual channel, or on all channels at once
- Right-click → Hide on <channel> / Hide on all channels (and the matching Unhide entries)
- Eye button per column, plus one for all channels, toggles hidden applications
- Hidden state persists via QSettings key `hidden_applications_v2`
- The hide key is the executable path, so an application that installs into a versioned folder gets a new key after an update (known limitation)
- Hidden applications are excluded from normal visible counts
- Hidden applications can be shown dimmed

## Main UI

Main mixer cards:

```text
Mic | Game | Chat | Media
```

The UI is a compact dark design with monochrome Mic/Game/Chat/Media icons and the custom eye icon.

Window position and size are persisted. A draggable splitter separates the mixer from the Applications / Mic Processing panels; its position is persisted under `splitter_v1`.

## Logging

Errors go through the `vmstreamer` logger, not `print()`: the packaged build is windowed and has no console. `setup_logging()` writes a rotating log to `%LOCALAPPDATA%\VMStreamer\vmstreamer.log` and installs hooks so uncaught exceptions are logged too.

## Icon / Packaging

Icon:

`vmstreamer.ico`

`main.py` uses a resource helper for source and PyInstaller execution:

```python
def resource_path(filename):
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, filename)
```

The icon is assigned to the QApplication and MainWindow.

Build script:

`build_vmstreamer.ps1`

Launcher:

`vmstreamer_launcher.py`

PyInstaller must retain both:

```powershell
--icon $icon
--add-data "$icon;."
```

The first sets the Windows EXE icon; the second embeds the ICO so `main.py` can load it from `_MEIPASS`.

Do not add `--collect-all PySide6`: it bundles every Qt module and makes the EXE about 245 MB. PyInstaller's own PySide6 hooks collect what `main.py` imports.

Output:

`dist\VMStreamer.exe`

`dist\` is intentionally ignored by Git.

## Build Notes

If PyInstaller reports:

```text
PermissionError: [WinError 5]
```

against `dist\VMStreamer.exe`, the old executable is usually still running/locked.

Check:

```powershell
Get-Process VMStreamer -ErrorAction SilentlyContinue
```

If necessary:

```powershell
Stop-Process -Name VMStreamer -Force
```

Then rebuild.

## GitHub Release

v1.0.2 is the latest tag.

Release assets:

- `VMStreamer.exe`
- Source code zip
- Source code tar.gz

The EXE is a GitHub Release asset, not a Git-tracked file.

## Known Development Files

Local development has included:

```text
diagnose_audio.py
main_meter_diagnostic.py
test_vm.py
install_vmstreamer_startup.ps1
vmstreamer_launcher.py
build_vmstreamer.ps1
```

Do not blindly `git add .`; only commit files that belong in the repository.

## Known Historical Bugs

- Naive VoiceMeeter polling caused slider values to reset; event-based synchronization fixed it.
- `levels.postfader` can return tuples; scalar handling must account for this.
- A Qt font warning (`QFont::setPointSize: Point size <= 0`) was addressed by explicitly setting a valid Segoe UI 9pt application font.
- Worker/timer shutdown previously produced cross-thread Qt timer errors; safe thread cleanup fixed this.
- Application QTimer sampling caused large stalls; the dedicated Python sampling loop fixed it.

## Future UI Direction

The draggable divider between the mixer and the lower panels is implemented (see Main UI). The applications section should remain three columns:

`Game | Chat | Media`

## Future Features

Potential roadmap:

- mixer and microphone presets
- profiles
- executable-based routing rules
- pan/balance and additional VoiceMeeter controls
- global hotkeys
- system tray
- start with Windows/minimized
- OBS / Stream Deck integration
- local API / Home Assistant integration
- themes and DPI improvements
- Windows installer
- automatic updates
- release automation

## Recommended Next Session

1. Run the current `main.py`.
2. Verify VoiceMeeter connection.
3. Verify Mic and application meters.
4. Verify mixer controls.
5. Verify Mic Processing popup.
6. Verify application hiding/persistence.
7. Verify window persistence.
8. Only then begin the next feature.

Keep the current audio/threading architecture intact unless there is a demonstrated reason to change it.
