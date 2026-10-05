# VMStreamer

A modern, lightweight control panel for **VoiceMeeter Potato**, designed for streamers and content creators.

VMStreamer provides a clean interface for managing your microphone, mixer channels, Windows application audio, and microphone processing without constantly switching back to the VoiceMeeter interface.

## Preview

![VMStreamer interface](screenshots/vmstreamer.png)

## Features

### Mixer Control

Control your main VoiceMeeter channels directly from VMStreamer:

- Microphone
- Game
- Chat
- Media
- Volume / gain control
- Mute
- Solo
- Mono
- Live audio level meters

### Application Audio

VMStreamer automatically detects Windows audio sessions and displays applications routed through VoiceMeeter.

Applications are grouped according to their VoiceMeeter output:

- **Game** — VoiceMeeter VAIO
- **Chat** — VoiceMeeter VAIO AUX
- **Media** — VoiceMeeter VAIO3

Each application provides:

- Individual volume control
- Mute control
- Live audio level indication
- Automatic session detection
- Search and refresh functionality

### Microphone Processing

VMStreamer provides direct control over VoiceMeeter's microphone processing.

#### Compressor

- Compression amount
- Input gain
- Ratio
- Threshold
- Attack
- Release
- Knee
- Output gain
- Auto makeup

#### Gate

- Gate amount
- Threshold
- Damping
- Sidechain
- Attack
- Hold
- Release

#### Denoiser

- Denoiser amount

All processing controls are synchronized directly with VoiceMeeter.

### Live Audio Meters

VMStreamer includes real-time audio monitoring for:

- Microphone input
- Game
- Chat
- Media
- Windows applications

Application audio monitoring uses a dedicated sampling loop to keep the interface responsive and prevent audio metering from blocking the graphical interface.

## Requirements

- Windows 10 / Windows 11
- VoiceMeeter Potato
- Python 3.14+ for running from source

### Python Dependencies

- PySide6
- voicemeeter-api
- pycaw
- comtypes
- psutil

## Running From Source

Clone the repository:

```powershell
git clone https://github.com/GuylianDeJong/VMStreamer.git
cd VMStreamer
```

Create a virtual environment:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the required dependencies:

```powershell
pip install PySide6 voicemeeter-api pycaw comtypes psutil
```

Run VMStreamer:

```powershell
python main.py
```

## Building the Windows EXE

VMStreamer can be packaged into a standalone Windows executable using PyInstaller.

Install PyInstaller:

```powershell
pip install pyinstaller
```

Build the application:

```powershell
pyinstaller --noconfirm --clean --onefile --windowed --name VMStreamer --icon vmstreamer.ico --add-data "vmstreamer.ico;." main.py
```

The resulting executable will be located at:

```text
dist\VMStreamer.exe
```

## Project Structure

```text
VMStreamer/
├── main.py
├── vmstreamer.ico
├── README.md
└── .gitignore
```

Build files, the Python virtual environment, and other generated files are intentionally excluded from Git.

## VoiceMeeter Configuration

VMStreamer currently works with **VoiceMeeter Potato** and uses the following channels:

| VMStreamer | VoiceMeeter | Windows Device |
| --- | --- | --- |
| Mic | Hardware Input 1 | Focusrite / microphone |
| Game | Strip 6 | VoiceMeeter VAIO |
| Chat | Strip 7 | VoiceMeeter VAIO AUX |
| Media | Strip 8 | VoiceMeeter VAIO3 |

Windows applications routed through these VoiceMeeter devices are automatically detected and displayed in the corresponding VMStreamer section.

## Application Design

VMStreamer is built with:

- Python
- PySide6 / Qt
- voicemeeter-api
- pycaw
- Windows Core Audio

The application uses separate worker threads for Windows application audio monitoring and VoiceMeeter level monitoring so that audio processing does not block the graphical interface.

## Status

VMStreamer is currently under active development.

The core mixer, microphone processing, application routing, live audio meters, and Windows application volume controls are functional.

## Future Features

VMStreamer is actively developed. The following features are planned or being considered for future releases:

### Configuration & Presets

- [ ] Persistent application routing
- [ ] Save and load mixer presets
- [ ] Save microphone processing presets
- [ ] Save application volume and mute states
- [ ] Multiple named profiles such as Gaming, Streaming, Recording, and Away
- [ ] User-configurable application sorting and layout
- [ ] Dedicated settings window

### Application Management

- [ ] Display application icons
- [ ] Remember application volume levels
- [ ] Automatically route applications based on executable
- [ ] Move applications between Game, Chat, and Media
- [ ] Improved application session detection
- [ ] Application routing rules

### VoiceMeeter Controls

- [ ] Pan / balance controls
- [ ] Additional strip controls
- [ ] A/B bus controls
- [ ] Bus volume and mute controls
- [ ] Hardware input controls
- [ ] Additional VoiceMeeter routing options

### Streamer Features

- [ ] Global hotkeys
- [ ] Global microphone mute
- [ ] Game / Chat / Media volume hotkeys
- [ ] Preset switching through hotkeys
- [ ] Push-to-talk integration
- [ ] System tray support
- [ ] Start with Windows
- [ ] Start minimized

### Integrations

- [ ] OBS Studio integration
- [ ] Stream Deck integration
- [ ] Local API for external applications and scripts
- [ ] Home Assistant integration
- [ ] Integration with other streaming tools

### User Interface

- [ ] Custom themes
- [ ] Light mode
- [ ] Custom accent colors
- [ ] Compact mode
- [ ] Improved high-DPI scaling
- [ ] Customizable mixer layout
- [ ] Additional visualization options

### Distribution

- [ ] Windows installer
- [ ] Automatic updates
- [ ] GitHub Releases
- [ ] Versioned release builds
- [ ] Release notes and changelogs

> This roadmap is subject to change as VMStreamer evolves and new ideas are explored.


## Support

If you find VMStreamer useful and would like to support its development, you can leave a tip on [Ko-fi](https://ko-fi.com/guyliandejong).

## License

## License

VMStreamer is licensed under the VMStreamer Non-Commercial License.

You are free to use, modify, fork, and redistribute VMStreamer for personal and non-commercial purposes.

Commercial use, sale, or redistribution of VMStreamer or modified versions for commercial purposes requires prior written permission from the author.

VMStreamer is an independent third-party project and is not affiliated with or endorsed by VB-Audio Software.