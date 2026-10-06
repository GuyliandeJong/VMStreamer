# VMStreamer — Project Handover

## Project

VMStreamer is a Windows desktop controller for VoiceMeeter Potato. It provides a compact custom UI for Mic, Game, Chat and Media instead of cloning the entire VoiceMeeter interface.

Repository: https://github.com/GuylianDeJong/VMStreamer
Current branch: `main`
Current release: `v1.0.0` (published/latest)

## Environment

- Windows
- Python 3.14.6
- Project: `C:\Users\Dutchie_\Documents\Projects\VMStreamer`
- Virtual environment: `.venv`
- PySide6 6.11.2
- voicemeeter-api 2.7.2
- pycaw
- comtypes
- PyInstaller
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
- Hardware Inputs 2–5, output buses and unnecessary routing controls are intentionally not exposed.

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

Compressor Attack/Release previously caused native API access violations. A safer native setter implementation fixed this. Do not casually replace it.

## Audio Meter Architecture

### Mic

Mic level sampling runs in a dedicated worker and communicates with Qt through signals.

### Applications

Windows application audio sessions are sampled in a dedicated Python loop rather than a GUI-thread QTimer.

Target sampling interval is approximately 10 ms; GUI delivery is approximately 60 FPS.

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

## Application Hiding

Implemented:

- Right-click → Hide application
- Eye button toggles hidden applications
- Right-click hidden application → Show application
- Hidden state persists via QSettings
- Hidden applications are excluded from normal visible counts
- Hidden applications can be shown dimmed

## Main UI

Main mixer cards:

```text
Mic | Game | Chat | Media
```

The UI is a compact dark design with monochrome Mic/Game/Chat/Media icons and the custom eye icon.

Window position and size are persisted.

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

v1.0.0 is published and marked Latest.

Release assets:

- `VMStreamer.exe`
- Source code zip
- Source code tar.gz

The EXE is approximately 245 MB.

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

A possible future feature is a vertical split between the upper mixer and lower applications area:

```text
Mixer
  ↓
draggable divider
  ↓
Applications
  ↓
Mic Processing
```

The applications section should remain three columns:

`Game | Chat | Media`

The divider position could be persisted through QSettings.

This is not implemented yet.

## Future Features

Potential roadmap:

- persistent application routing
- mixer and microphone presets
- profiles
- application icons
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
