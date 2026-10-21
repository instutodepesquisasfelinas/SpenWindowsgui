# S Pen Bridge

S Pen Bridge is a Windows desktop application that connects a Samsung Galaxy tablet over Android Debug Bridge (ADB), reads S Pen input, and can send pen input to Windows.

> **Status:** Prototype in active development. Test device compatibility and the Windows pen experience on your hardware before relying on it.

## Current features

- Wireless ADB pairing, connection, disconnection, and device status.
- S Pen event-device discovery from Android `getevent -i` output.
- Live display of normalized position, pressure, distance, tilt, and pen buttons.
- Optional Windows synthetic-pen input, including hover and contact.
- A Samsung-blue hover indicator that follows the pen cursor.
- Calibration for orientation, X0/X1/Y0/Y1 bounds, scale, offsets, and axis direction.
- Local calibration and profile data stored in `profiles.json`.

The button-mapping page, automated device event mapping, and packaged release are not available yet. Do not treat pending items as working features.

## Requirements

- Windows 10 version 1809 or later for the synthetic pen API.
- Python with the PySide6 version listed in `requirements.txt`.
- Android SDK Platform-Tools (`adb.exe`) available on `PATH`.
- A Samsung Galaxy tablet with Developer options and Wireless debugging enabled.
- The PC and tablet must be able to communicate over the same network for wireless ADB.

Android may restrict access to `/dev/input/eventN`. S Pen events are read only when the device permits the ADB shell to open the discovered event node. The app reports an access error when Android denies it; discovering a node does not by itself prove that it can be read.

## Run from source

From PowerShell, in the project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

Install Android SDK Platform-Tools separately if `adb` is not already available on `PATH`.

## Connect and use the pen

1. On the tablet, open **Developer options > Wireless debugging**.
2. To pair, choose **Pair device with pairing code** and enter its IP, pairing port, and code in S Pen Bridge.
3. Connect using the IP and main port shown on the Wireless debugging screen. Refresh the device list and select the authorized tablet.
4. Before starting, enable **Control Windows with the S Pen** if Windows pen input is desired. Leave it disabled to inspect events without moving the Windows cursor.
5. Select **Start reading** and move the S Pen. Events appear in the live panel. Select **Stop** to end the stream.

The S Pen must be in range for hover updates. Touching the tablet surface reports contact and pressure. Windows cursor injection and the custom hover indicator require the injection option to be enabled.

## Calibrate

Keep the event stream running while calibrating. In **Calibration**, move the S Pen to each edge and select **Capture position** for:

- **X0:** left edge.
- **X1:** right edge.
- **Y0:** top edge.
- **Y1:** bottom edge.

Choose portrait or the matching landscape rotation, then save. X1 must be greater than X0, and Y1 must be greater than Y0. Stop and restart the stream to apply the saved calibration. Calibration values are stored locally in `profiles.json`.

## Troubleshooting

- **ADB not found:** install Android SDK Platform-Tools and add its directory to `PATH`.
- **No authorized device:** keep Wireless debugging enabled, pair again if needed, connect using the main port, and accept any authorization prompt on the tablet.
- **No S Pen events:** select the connected device, start reading, and move the pen over the screen.
- **Permission denied:** Android is refusing access to the event node. S Pen Bridge does not assume root access or bypass Android permissions.
- **Cursor does not move:** verify that Windows pen control is enabled and that the selected device is authorized. Synthetic pen input requires Windows 10 version 1809 or later.
- **Position or orientation is wrong:** capture all four bounds again and confirm the selected orientation.

When reporting an issue, include the Windows version, CPU architecture, tablet model, steps to reproduce, and the visible error. Remove device serials, IP addresses, pairing codes, and other private information from logs.

## Project layout

- `main.py` starts the PySide6 application.
- `ui/` contains the connection and calibration pages and the custom cursor indicator.
- `adb_connection.py` contains ADB pairing and connection operations.
- `pen_reader.py` discovers the S Pen event device, parses events, and streams them outside the UI thread.
- `windows_pen.py` maps pen states to the Windows synthetic pointer API.
- `calibration.py` loads and saves local calibration settings.
- `profiles.json` stores local settings and button profiles.

## Beta builds

The private GitHub Releases page contains **Beta 0.01** builds for Windows x64 and ARM64. The x64 executable was started successfully on the development PC. The ARM64 executable was compiled on a native Windows ARM64 runner, but still needs runtime testing on an ARM64 PC.

There is no x86 executable: the current PySide6 dependencies do not publish Windows 32-bit wheels. Packaging uses a native runner for each target architecture; PyInstaller is not a cross-compiler. ADB is not bundled, so install Android SDK Platform-Tools and make `adb.exe` available on `PATH`.

## License and affiliation

No project license has been selected. Do not assume permission to redistribute or reuse this project's code until a license is added. S Pen Bridge is an independent project and is not affiliated with or endorsed by Samsung, Microsoft, or Google.