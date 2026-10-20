# Barracuda IP Removal Agent

A Windows-friendly desktop app that submits IP addresses to Barracuda Central's removal-request form and records the responses. It uses a visible Microsoft Edge or Google Chrome window; no API key or browser-driver download is required.

Only submit requests for IP addresses you are authorized to manage, and provide accurate contact details and request information. Barracuda decides whether a request is accepted.

## Requirements

- Windows 10/11 (the packaged executable is built for the operating system on which it is built).
- Python 3.10 or later with Tkinter to run from source.
- Microsoft Edge or Google Chrome installed.

The application itself uses Python's standard library. PyInstaller is needed only to build the executable.

## Run from source

1. Install Python and ensure its Tkinter component is available.
2. Open PowerShell in the project folder.
3. Start the app:

   ```powershell
   python main.py
   ```

On first launch, fill out and save the profile used for submissions. The app then opens its main window.

## Use

Choose an input mode:

- **Single** — submit one IP address.
- **Range** — submit an inclusive range of IPv4 or IPv6 addresses (up to 4,096); ranges of 50 or more require confirmation.
- **Random** — paste IP addresses separated by spaces, commas, semicolons, or new lines. Invalid entries and duplicates are recorded but not submitted.

Select **Start** to process the list. The browser is visible while the app fills and submits the form. Use **Pause**, **Resume**, or **Stop** to control a batch. Results show whether an IP was listed, not listed, duplicated, invalid, or encountered an error. Use **View Logs** to search past runs and **Export Results** to save a CSV.

## Configuration and saved data

Use **Edit Profile** in the app to update the contact details and reason submitted to Barracuda. The initial contact fields are blank; enter your own accurate details.

Optional environment variables:

- `BARRACUDA_BROWSER` — full path to a specific Edge or Chrome executable if automatic discovery does not find it.
- `BARRACUDA_REMOVAL_URL` — override the default Barracuda removal-request URL.

PowerShell example:

```powershell
$env:BARRACUDA_BROWSER = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
python main.py
```

When running from source, the app stores its profile in `config\profile.json`, its SQLite log in `data\agent_logs.db`, and CSV results in `output\`. The browser uses a temporary profile rather than your regular browser profile.

The packaged executable stores these files in `BarracudaData` beside the executable. If that location is not writable, it uses `%LOCALAPPDATA%\BarracudaIPAgent`.

## Build a standalone executable

Run these commands on the target operating system; PyInstaller does not cross-compile:

```powershell
python -m pip install -r requirements-build.txt
python build_exe.py
```

The executable is written to `dist\BarracudaIPAgent.exe` on Windows. It does not include a browser, so the target computer still needs Edge or Chrome. `build_exe.py` can install the build dependency if it is missing.

## Project structure

| Path | Purpose |
| --- | --- |
| `main.py` | Application entry point |
| `ui\` | Tkinter profile, input, and results windows |
| `browser\` | Edge/Chrome discovery and browser form automation |
| `services\` | IP parsing, response classification, and batch processing |
| `storage\` | SQLite logging and CSV export |
| `config\settings.py` | Runtime paths, limits, and timing settings |
| `assets\` | Application icons |
| `build_exe.py`, `BarracudaIPAgent.spec` | PyInstaller build configuration |
| `requirements-build.txt` | Build-only dependency |
