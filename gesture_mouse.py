"""
Gesture Mouse Controller - Pure Python Desktop App
Works system-wide regardless of active window/tab.

Requirements:
    pip install opencv-python mediapipe pyautogui numpy

Run:
    python gesture_mouse.py

Controls:
    ☝️  Index finger only   → Move cursor
    🤏  Pinch once          → Left click
    🤏🤏 Pinch twice fast   → Double click
    ✌️  Two fingers up      → Scroll (move hand up/down)
    Q / ESC                 → Quit
"""

import cv2
import mediapipe as mp
import pyautogui
import numpy as np
import time
import math
import sys

# ─── Safety ──────────────────────────────────────────────────────────────────
pyautogui.FAILSAFE = True   # Move mouse to top-left corner to emergency stop
pyautogui.PAUSE    = 0      # No artificial delay

# ─── Config ───────────────────────────────────────────────────────────────────
CAMERA_INDEX        = 0       # Change if wrong camera
FRAME_W, FRAME_H    = 640, 480

SMOOTHING           = 0.25    # Lower = smoother but more lag (0.1–0.9)
PINCH_THRESHOLD     = 0.055   # Lower = tighter pinch needed
DOUBLE_CLICK_GAP    = 0.4     # Seconds between pinches for double-click
SCROLL_SENSITIVITY  = 4       # Scroll lines per tick
SCROLL_COOLDOWN     = 0.06    # Seconds between scroll ticks

# Dead zone: finger must move this much (fraction of screen) before cursor moves
DEAD_ZONE           = 0.005

# ─── Screen info ─────────────────────────────────────────────────────────────
SCREEN_W, SCREEN_H = pyautogui.size()
print(f"Screen: {SCREEN_W}x{SCREEN_H}")

# ─── MediaPipe setup ─────────────────────────────────────────────────────────
mp_hands    = mp.solutions.hands
mp_drawing  = mp.solutions.drawing_utils
mp_styles   = mp.solutions.drawing_styles

hands_model = mp_hands.Hands(
    static_image_mode        = False,
    max_num_hands            = 1,
    model_complexity         = 1,
    min_detection_confidence = 0.7,
    min_tracking_confidence  = 0.6,
)

# ─── State ───────────────────────────────────────────────────────────────────
smooth_x        = None
smooth_y        = None
last_pinch      = False
last_click_time = 0.0
last_scroll_y   = None
last_scroll_time= 0.0
total_clicks    = 0
total_scrolls   = 0
current_gesture = "none"

# ─── Helpers ─────────────────────────────────────────────────────────────────
def lerp(a, b, t):
    return a + (b - a) * t

def dist(a, b):
    return math.sqrt((a.x - b.x)**2 + (a.y - b.y)**2)

def fingers_extended(hand):
    """Returns list of booleans [index, middle, ring, pinky] extended."""
    tips   = [8, 12, 16, 20]
    knucks = [6, 10, 14, 18]
    return [hand[tips[i]].y < hand[knucks[i]].y for i in range(4)]

def is_two_fingers_up(hand):
    """Index + middle extended, ring + pinky closed, thumb closed."""
    ext = fingers_extended(hand)
    thumb_closed = hand[4].x > hand[3].x  # mirrored
    return ext[0] and ext[1] and not ext[2] and not ext[3] and thumb_closed

def is_index_only(hand):
    """Only index finger extended."""
    ext = fingers_extended(hand)
    return ext[0] and not ext[1] and not ext[2] and not ext[3]

def draw_hud(frame, gesture, clicks, scrolls, fps):
    """Draw overlay info on the camera preview window."""
    h, w = frame.shape[:2]

    # Semi-transparent top bar
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 50), (15, 15, 20), -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

    # Title
    cv2.putText(frame, "GestureMouse", (10, 32),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (140, 120, 255), 2)

    # FPS
    cv2.putText(frame, f"FPS: {fps:.0f}", (w - 100, 32),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (150, 150, 160), 1)

    # Bottom bar
    overlay2 = frame.copy()
    cv2.rectangle(overlay2, (0, h - 55), (w, h), (15, 15, 20), -1)
    cv2.addWeighted(overlay2, 0.75, frame, 0.25, 0, frame)

    # Gesture label
    gesture_colors = {
        "move":         (120, 200, 120),
        "pinch":        (80,  140, 255),
        "double_click": (60,  100, 255),
        "scroll_up":    (200, 180, 80),
        "scroll_down":  (80,  200, 180),
        "none":         (100, 100, 110),
    }
    color = gesture_colors.get(gesture, (180, 180, 180))
    label = gesture.replace("_", " ").upper()
    cv2.putText(frame, label, (10, h - 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)

    # Stats
    cv2.putText(frame, f"clicks:{clicks}  scrolls:{scrolls}", (w - 200, h - 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (150, 150, 160), 1)

    # Gesture legend (right side)
    legend = [
        ("☝ index only", "move cursor"),
        ("# pinch",       "click"),
        ("## pinch fast", "dbl click"),
        ("✌ 2 fingers",  "scroll"),
        ("Q / ESC",        "quit"),
    ]
    for i, (key, val) in enumerate(legend):
        y = 75 + i * 22
        cv2.putText(frame, key, (w - 190, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (180, 160, 255), 1)
        cv2.putText(frame, f"→ {val}", (w - 95, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (140, 140, 150), 1)

    return frame

# ─── Main loop ───────────────────────────────────────────────────────────────
def main():
    global smooth_x, smooth_y, last_pinch, last_click_time
    global last_scroll_y, last_scroll_time, total_clicks, total_scrolls, current_gesture

    cap = cv2.VideoCapture(CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)
    cap.set(cv2.CAP_PROP_FPS, 30)

    if not cap.isOpened():
        print(f"ERROR: Cannot open camera {CAMERA_INDEX}")
        print("Try changing CAMERA_INDEX to 1 or 2 at the top of the script.")
        sys.exit(1)

    print("\n=== Gesture Mouse Controller ===")
    print("Camera open. Starting gesture tracking...")
    print("Move your hand in front of the camera.")
    print("Press Q or ESC in the preview window to quit.\n")

    prev_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Camera read failed, retrying...")
            time.sleep(0.1)
            continue

        # Flip for mirror effect
        frame = cv2.flip(frame, 1)
        rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results = hands_model.process(rgb)
        rgb.flags.writeable = True

        # FPS
        now      = time.time()
        fps      = 1.0 / max(now - prev_time, 1e-9)
        prev_time = now

        if results.multi_hand_landmarks:
            hand_lm = results.multi_hand_landmarks[0].landmark

            # Draw landmarks
            mp_drawing.draw_landmarks(
                frame,
                results.multi_hand_landmarks[0],
                mp_hands.HAND_CONNECTIONS,
                mp_styles.get_default_hand_landmarks_style(),
                mp_styles.get_default_hand_connections_style(),
            )

            index_tip = hand_lm[8]
            thumb_tip = hand_lm[4]
            pinch_dist = dist(index_tip, thumb_tip)
            is_pinch   = pinch_dist < PINCH_THRESHOLD
            two_up     = is_two_fingers_up(hand_lm)

            # ── SCROLL MODE ────────────────────────────────────────────────
            if two_up:
                current_gesture = "scroll_up"
                ref_y = hand_lm[9].y  # palm base for stable y reference

                if last_scroll_y is not None:
                    dy = ref_y - last_scroll_y
                    if abs(dy) > 0.003 and (now - last_scroll_time) > SCROLL_COOLDOWN:
                        direction = -1 if dy < 0 else 1  # up = negative dy
                        pyautogui.scroll(int(-direction * SCROLL_SENSITIVITY), _pause=False)
                        current_gesture = "scroll_up" if direction < 0 else "scroll_down"
                        last_scroll_time = now
                        total_scrolls += 1

                last_scroll_y = ref_y

                # Visual: draw scroll indicator
                mid_x = int(index_tip.x * FRAME_W)
                mid_y = int(index_tip.y * FRAME_H)
                cv2.circle(frame, (mid_x, mid_y), 12, (80, 200, 180), 2)

            else:
                last_scroll_y = None

                # ── MOVE + CLICK MODE ──────────────────────────────────────
                nx = index_tip.x  # already mirrored from flip
                ny = index_tip.y

                # Map to screen with slight margin so edges are reachable
                margin = 0.1
                nx_mapped = np.clip((nx - margin) / (1 - 2 * margin), 0, 1)
                ny_mapped = np.clip((ny - margin) / (1 - 2 * margin), 0, 1)

                tx = nx_mapped * SCREEN_W
                ty = ny_mapped * SCREEN_H

                if smooth_x is None:
                    smooth_x, smooth_y = tx, ty
                else:
                    smooth_x = lerp(smooth_x, tx, SMOOTHING)
                    smooth_y = lerp(smooth_y, ty, SMOOTHING)

                pyautogui.moveTo(int(smooth_x), int(smooth_y), _pause=False)
                current_gesture = "move"

                # Pinch = click
                if is_pinch and not last_pinch:
                    gap = now - last_click_time
                    if gap < DOUBLE_CLICK_GAP and last_click_time > 0:
                        pyautogui.doubleClick(_pause=False)
                        current_gesture = "double_click"
                        print(f"  Double click @ ({int(smooth_x)}, {int(smooth_y)})")
                        last_click_time = 0
                    else:
                        pyautogui.click(_pause=False)
                        current_gesture = "pinch"
                        print(f"  Click @ ({int(smooth_x)}, {int(smooth_y)})")
                        last_click_time = now
                    total_clicks += 1

                last_pinch = is_pinch

                # Draw pinch indicator
                tip_x = int(index_tip.x * FRAME_W)
                tip_y = int(index_tip.y * FRAME_H)
                color = (80, 100, 255) if is_pinch else (120, 220, 120)
                cv2.circle(frame, (tip_x, tip_y), 10, color, -1 if is_pinch else 2)

        else:
            # No hand detected
            current_gesture = "none"
            last_pinch = False
            last_scroll_y = None

        # Draw HUD
        frame = draw_hud(frame, current_gesture, total_clicks, total_scrolls, fps)

        cv2.imshow("GestureMouse  [Q to quit]", frame)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord('q'), ord('Q'), 27):  # Q or ESC
            break

    cap.release()
    cv2.destroyAllWindows()
    hands_model.close()
    print("\nGestureMouse stopped.")


if __name__ == "__main__":
    main()
