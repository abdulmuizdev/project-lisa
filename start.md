# Photo Booth

## First-time setup

```powershell
cd D:\project-lisa
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run

**Windows (PowerShell)** — use the venv Python directly (no activation needed):

```powershell
cd D:\project-lisa
.\.venv\Scripts\python.exe webcam_capture.py
```

If `Activate.ps1` is blocked by execution policy, this command still works.

**macOS / Linux:**

```bash
cd /path/to/project-lisa
source .venv/bin/activate
python webcam_capture.py
```

**Controls:**

| Input | Action |
|-------|--------|
| Gamepad **button 9** | Insert coin (+1 print credit) |
| Gamepad **button 0** or `s` | Capture photo (requires coin) |
| Gamepad **button 1** | Confirm print (uses 1 coin) |
| `q` or ESC | Quit |

## How it works

1. On start, the screen shows **INSERT COIN** — capture is locked until a coin is inserted.
2. Press gamepad **button 9** to add credits. Each coin allows one print.
3. Capture a photo with **button 0** or `s` — the live camera pauses and your photo is shown full-screen.
4. Press gamepad **button 1** to confirm and print. One coin is consumed per print.
5. After printing, the live camera resumes. When credits reach zero, the idle screen returns.

To find button numbers for other controllers:

```powershell
.\.venv\Scripts\python.exe controller_input.py
```
