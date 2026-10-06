# VMStreamer — Project State

State date: 2026-10-06
Current release: `v1.0.0`
Branch: `main`
Repository: https://github.com/GuylianDeJong/VMStreamer

## Primary Source

`main.py` is the authoritative application source filename. Do not create renamed `main_*` variants.

## Environment

- Windows
- Python 3.14.6
- PySide6 6.11.2
- voicemeeter-api 2.7.2
- pycaw
- comtypes
- PyInstaller
- VoiceMeeter Potato 3.1.2.2

Project:

`C:\Users\Dutchie_\Documents\Projects\VMStreamer`

## VoiceMeeter

```text
Strip 0 → Mic
Strip 5 → Game
Strip 6 → Chat
Strip 7 → Media
```

Main controls:

- Gain
- Mute
- Solo
- Mono

Mic processing:

- Compressor
- Gate
- Denoiser

VoiceMeeter uses event-based bidirectional synchronization. `vm.init_thread()` is required and update threads must stop before logout.

## Audio

Mic level sampling uses a dedicated worker.

Application audio uses a dedicated Python sampling loop at roughly 10 ms with GUI updates around 60 FPS.

This architecture fixed severe stalls from the previous QTimer/GUI-thread implementation.

VU meter range:

`-60 .. 0 dB`

Do not double-convert dB values.

## Applications

Application sessions are grouped by actual VoiceMeeter routing:

```text
Game | Chat | Media
```

Grouped volume/mute control applies to underlying Windows audio sessions. Group meter uses the highest active peak.

Friendly names are used for known executables, including Microsoft Teams, Steam, Steam Client Web, SignalRGB Core, Brave Browser and Edge WebView2.

Application hiding is implemented and persisted with QSettings.

## UI

Main cards:

`Mic | Game | Chat | Media`

Applications remain split into:

`Game | Chat | Media`

Application rows contain name, volume, percentage, mute control and live meter.

Application sliders support click/drag.

Mic Processing opens in a popup.

Window position/size persists.

Icons are monochrome.

## Icon / Build

Icon:

`vmstreamer.ico`

Build script:

`build_vmstreamer.ps1`

Launcher:

`vmstreamer_launcher.py`

Required PyInstaller icon options:

```powershell
--icon $icon
--add-data "$icon;."
```

Output:

`dist\VMStreamer.exe`

`dist\` is ignored by Git.

## Release

`v1.0.0` is published and Latest.

Assets:

- `VMStreamer.exe`
- Source code zip
- Source code tar.gz

EXE size is approximately 245 MB.

The EXE is distributed as a GitHub Release asset and is not committed to Git.

## Important Stability Areas

Do not regress:

- VoiceMeeter event synchronization
- dedicated application audio loop
- dedicated mic worker
- correct dB conversion
- safe VoiceMeeter shutdown
- compressor Attack/Release setter
- application grouping
- application hiding
- QSettings persistence
- Mic Processing popup
- valid Qt base font
- `resource_path()` icon loading
- PyInstaller `--add-data`

## Build Locking

If building fails with `WinError 5` on `dist\VMStreamer.exe`, close/kill the running VMStreamer process before rebuilding:

```powershell
Get-Process VMStreamer -ErrorAction SilentlyContinue
Stop-Process -Name VMStreamer -Force
```

## Future UI

Possible future implementation:

```text
Mixer
  ↓
draggable horizontal divider
  ↓
Applications
  ↓
Mic Processing
```

Applications remain three columns: Game, Chat, Media.

Not implemented yet.

## Future Work

Potential areas:

- application routing rules
- presets/profiles
- application icons
- volume persistence
- pan/balance
- additional VoiceMeeter controls
- global hotkeys
- system tray
- OBS/Stream Deck
- local API/Home Assistant
- themes/DPI improvements
- installer
- automatic updates
- release automation

## Development Files

Known local support/debug files:

```text
diagnose_audio.py
main_meter_diagnostic.py
test_vm.py
install_vmstreamer_startup.ps1
vmstreamer_launcher.py
build_vmstreamer.ps1
```

Do not blindly commit every untracked file.

## Next Session

Keep v1.0.0 stable. Run and verify the existing application before starting a new feature. Make incremental changes and keep `main.py` as the single primary source file.
