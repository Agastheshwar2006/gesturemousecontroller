# Gesture Mouse Controller

Control your OS mouse entirely with hand gestures via your webcam.

## Gestures

| Gesture | Action |
|---|---|
| ☝️ Index finger | Move cursor |
| 🤏 Pinch once | Left click |
| 🤏🤏 Pinch twice fast | Double click |
| ✌️ Two fingers up + move | Scroll up / down |

---

## Setup

### 1. Install Python dependencies

```bash
cd backend
pip install -r requirements.txt
```

> On Linux you may also need:
> ```bash
> sudo apt-get install python3-tk python3-dev scrot
> ```

### 2. Start the backend

```bash
cd backend
python main.py
```

The server starts at `http://localhost:8000`

### 3. Open the frontend

Open your browser and go to:
```
http://localhost:8000
```

Or open `frontend/index.html` directly — but note camera + WebSocket work best when served via the backend URL.

### 4. Allow camera access

When prompted by your browser, click **Allow** for camera access.

---

## Settings (in the UI)

| Setting | Description |
|---|---|
| Smoothing | Higher = smoother but slower cursor |
| Pinch threshold | Lower = tighter pinch required to click |
| Scroll sensitivity | Higher = faster scrolling |

---

## Troubleshooting

- **Cursor not moving on screen**: Make sure the backend is running and the badge shows "connected"
- **Camera blocked**: Check browser site settings and allow camera for localhost
- **Jittery cursor**: Increase the Smoothing slider
- **Accidental clicks**: Lower the Pinch threshold slider
- **Linux display error**: Set `DISPLAY=:0` before running: `DISPLAY=:0 python main.py`
- **macOS accessibility**: Go to System Preferences → Security & Privacy → Accessibility → add Terminal/Python

---

## Project Structure

```
gesture-mouse/
├── backend/
│   ├── main.py          # FastAPI + WebSocket server + pyautogui
│   └── requirements.txt
└── frontend/
    └── index.html       # UI, MediaPipe hand tracking, gesture logic
```
