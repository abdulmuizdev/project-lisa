import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")
import pygame

CAPTURE_KEY = ord("s")
PRINT_KEY = ord("m")
QUIT_KEYS = {ord("q"), 27}
CAMERA_INDEX = 0
CAPTURE_CONTROLLER = 0
CAPTURE_BUTTON = 0
COIN_BUTTON = 9
CONFIRM_BUTTON = 1
OUTPUT_DIR = Path("captures")
FRAME_PATH = Path(__file__).resolve().parent / "Frame.png"
WINDOW_NAME = "Photo Booth"
DISPLAY_WIDTH = 1080
DISPLAY_HEIGHT = 1920

COLOR_GOLD = (0, 215, 255)
COLOR_GREEN = (0, 220, 100)
COLOR_BLUE = (255, 180, 0)
COLOR_DARK = (30, 30, 30)
COLOR_RED = (80, 80, 255)
COLOR_WHITE = (255, 255, 255)
COLOR_DIM = (180, 180, 180)

FLASH_DURATION = 30
PRINT_FLASH_DURATION = 45


@dataclass
class BoothState:
    coins: int = 0
    pending_path: Optional[Path] = None
    pending_frame: Optional[np.ndarray] = None
    coin_flash_frames: int = 0
    print_flash_frames: int = 0
    print_flash_text: str = ""
    error_flash_frames: int = 0
    error_flash_text: str = ""
    capture_flash_frames: int = 0
    frame_counter: int = 0
    preview_mode: bool = False


def fit_to_display(frame: np.ndarray) -> np.ndarray:
    """Scale and center-crop to portrait 1080x1920."""
    h, w = frame.shape[:2]
    scale = max(DISPLAY_WIDTH / w, DISPLAY_HEIGHT / h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    x = (new_w - DISPLAY_WIDTH) // 2
    y = (new_h - DISPLAY_HEIGHT) // 2
    return resized[y : y + DISPLAY_HEIGHT, x : x + DISPLAY_WIDTH]


def load_frame_overlay() -> np.ndarray:
    overlay = cv2.imread(str(FRAME_PATH), cv2.IMREAD_UNCHANGED)
    if overlay is None:
        raise SystemExit(f"Could not load frame overlay: {FRAME_PATH}")

    oh, ow = overlay.shape[:2]
    if ow > oh and DISPLAY_HEIGHT > DISPLAY_WIDTH:
        overlay = cv2.rotate(overlay, cv2.ROTATE_90_CLOCKWISE)

    if overlay.shape[0] != DISPLAY_HEIGHT or overlay.shape[1] != DISPLAY_WIDTH:
        overlay = cv2.resize(
            overlay,
            (DISPLAY_WIDTH, DISPLAY_HEIGHT),
            interpolation=cv2.INTER_LINEAR,
        )
    return overlay


def apply_frame_overlay(photo: np.ndarray, overlay: np.ndarray) -> np.ndarray:
    if overlay.shape[:2] != photo.shape[:2]:
        overlay = cv2.resize(
            overlay,
            (photo.shape[1], photo.shape[0]),
            interpolation=cv2.INTER_LINEAR,
        )

    if overlay.shape[2] == 4:
        overlay_bgr = overlay[:, :, :3].astype(np.float32)
        alpha = overlay[:, :, 3:4].astype(np.float32) / 255.0
    else:
        overlay_bgr = overlay.astype(np.float32)
        alpha = np.ones((overlay.shape[0], overlay.shape[1], 1), dtype=np.float32)

    base = photo.astype(np.float32)
    blended = base * (1.0 - alpha) + overlay_bgr * alpha
    return blended.astype(np.uint8)


def save_capture(frame) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    filename = OUTPUT_DIR / f"capture_{datetime.now():%Y%m%d_%H%M%S}.jpg"
    cv2.imwrite(str(filename), frame)
    return filename


def _default_cups_printer() -> str:
    try:
        result = subprocess.run(
            ["lpstat", "-d"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return "default"

    if result.returncode != 0 or ":" not in result.stdout:
        return "default"

    return result.stdout.split(":", 1)[1].strip() or "default"


def print_image_windows(path: Path) -> None:
    try:
        import win32con
        import win32print
        import win32ui
        from PIL import Image, ImageWin
    except ImportError as exc:
        print(f"Could not load printing libraries: {exc}")
        return

    try:
        printer_name = win32print.GetDefaultPrinter()
        image = Image.open(path)
        if image.mode != "RGB":
            image = image.convert("RGB")

        hDC = win32ui.CreateDC()
        hDC.CreatePrinterDC(printer_name)

        printable_width = hDC.GetDeviceCaps(win32con.HORZRES)
        printable_height = hDC.GetDeviceCaps(win32con.VERTRES)

        img_width, img_height = image.size
        scale = min(printable_width / img_width, printable_height / img_height)
        draw_width = int(img_width * scale)
        draw_height = int(img_height * scale)
        x = (printable_width - draw_width) // 2
        y = (printable_height - draw_height) // 2

        hDC.StartDoc(str(path))
        hDC.StartPage()
        dib = ImageWin.Dib(image)
        dib.draw(hDC.GetHandleOutput(), (x, y, x + draw_width, y + draw_height))
        hDC.EndPage()
        hDC.EndDoc()
        hDC.DeleteDC()

        print(f"Printing {path} to {printer_name}...")
    except Exception as exc:
        print(f"Could not print {path}: {exc}")


def print_image_linux(path: Path) -> None:
    printer_name = _default_cups_printer()
    try:
        subprocess.run(
            ["lp", "-o", "fit-to-page", str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
        print(f"Printing {path} to {printer_name}...")
    except FileNotFoundError:
        print("Could not print: 'lp' not found. Install CUPS (e.g. apt install cups).")
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        print(f"Could not print {path}: {detail}")


def print_image(path: Path) -> None:
    if sys.platform == "win32":
        print_image_windows(path)
    elif sys.platform == "linux":
        print_image_linux(path)
    else:
        print(f"Printing skipped on {sys.platform} (Windows and Linux only).")


def insert_coin(state: BoothState) -> None:
    state.coins += 1
    state.coin_flash_frames = FLASH_DURATION
    print(f"Coin inserted! Credits: {state.coins}")


def handle_capture(state: BoothState, frame: np.ndarray, frame_overlay: np.ndarray) -> None:
    fitted = fit_to_display(frame)
    framed = apply_frame_overlay(fitted, frame_overlay)
    path = save_capture(framed)
    state.pending_path = path
    state.pending_frame = framed.copy()
    state.preview_mode = True
    state.capture_flash_frames = FLASH_DURATION
    print(f"Captured {path} ({DISPLAY_WIDTH}x{DISPLAY_HEIGHT}) — preview mode")


def handle_print(state: BoothState) -> None:
    if state.coins < 1:
        state.error_flash_frames = FLASH_DURATION
        state.error_flash_text = "INSERT COIN TO PRINT"
        return
    if state.pending_path is None:
        state.error_flash_frames = FLASH_DURATION
        state.error_flash_text = "CAPTURE A PHOTO FIRST"
        return

    state.print_flash_frames = PRINT_FLASH_DURATION
    state.print_flash_text = "PRINTING..."
    print_image(state.pending_path)
    state.coins -= 1
    state.print_flash_text = "PRINTED!"
    state.preview_mode = False
    print(f"Printed {state.pending_path}. Credits remaining: {state.coins}")


def draw_panel(
    img: np.ndarray, x: int, y: int, w: int, h: int, alpha: float = 0.65
) -> None:
    overlay = img.copy()
    cv2.rectangle(overlay, (x, y), (x + w, y + h), COLOR_DARK, -1)
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)


def draw_centered_text(
    img: np.ndarray,
    text: str,
    y: int,
    scale: float,
    color: Tuple[int, int, int],
    thickness: int = 2,
) -> None:
    font = cv2.FONT_HERSHEY_DUPLEX
    (text_w, text_h), _ = cv2.getTextSize(text, font, scale, thickness)
    x = (img.shape[1] - text_w) // 2
    cv2.putText(img, text, (x, y), font, scale, color, thickness, cv2.LINE_AA)


def draw_coin_badge(img: np.ndarray, coins: int) -> None:
    badge_w, badge_h = 120, 50
    x = img.shape[1] - badge_w - 20
    y = 55
    draw_panel(img, x, y, badge_w, badge_h, 0.75)
    cv2.circle(img, (x + 28, y + 25), 16, COLOR_GOLD, -1, cv2.LINE_AA)
    cv2.circle(img, (x + 28, y + 25), 16, (0, 170, 220), 2, cv2.LINE_AA)
    label = f"x{coins}"
    cv2.putText(
        img,
        label,
        (x + 52, y + 33),
        cv2.FONT_HERSHEY_DUPLEX,
        0.9,
        COLOR_GOLD,
        2,
        cv2.LINE_AA,
    )


def draw_banner(img: np.ndarray, text: str, color: Tuple[int, int, int]) -> None:
    bar_h = 60
    y = img.shape[0] // 2 - bar_h // 2
    draw_panel(img, 0, y, img.shape[1], bar_h, 0.85)
    cv2.rectangle(img, (0, y), (img.shape[1], y + bar_h), color, 3)
    draw_centered_text(img, text, y + 42, 1.1, COLOR_WHITE, 2)


def draw_idle_overlay(img: np.ndarray, state: BoothState) -> None:
    h, w = img.shape[:2]
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.55, img, 0.45, 0, img)

    pulse = state.frame_counter % 30 < 15
    main_scale = 2.2 if pulse else 2.0
    main_color = COLOR_GOLD if pulse else (0, 170, 220)
    draw_centered_text(img, "INSERT COIN", h // 2 - 20, main_scale, main_color, 3)
    draw_centered_text(img, "Press COIN button on gamepad", h // 2 + 50, 0.7, COLOR_DIM, 1)

    badge_y = h // 2 + 100
    badge_w, badge_h = 220, 40
    badge_x = (w - badge_w) // 2
    draw_panel(img, badge_x, badge_y, badge_w, badge_h, 0.8)
    cv2.putText(
        img,
        "CAPTURE LOCKED",
        (badge_x + 28, badge_y + 28),
        cv2.FONT_HERSHEY_DUPLEX,
        0.75,
        COLOR_RED,
        2,
        cv2.LINE_AA,
    )


def draw_active_overlay(img: np.ndarray, state: BoothState) -> None:
    h, w = img.shape[:2]

    draw_panel(img, 0, 0, w, 48, 0.8)
    cv2.putText(
        img,
        "PHOTO BOOTH",
        (20, 34),
        cv2.FONT_HERSHEY_DUPLEX,
        1.0,
        COLOR_WHITE,
        2,
        cv2.LINE_AA,
    )
    draw_coin_badge(img, state.coins)

    bar_h = 72
    bar_y = h - bar_h
    draw_panel(img, 0, bar_y, w, bar_h, 0.8)

    capture_color = COLOR_GREEN
    cv2.putText(
        img,
        "[ BTN 0 / S ]  CAPTURE",
        (20, bar_y + 30),
        cv2.FONT_HERSHEY_DUPLEX,
        0.65,
        capture_color,
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        img,
        "Capture freezes preview for print confirm",
        (20, bar_y + 58),
        cv2.FONT_HERSHEY_DUPLEX,
        0.5,
        COLOR_DIM,
        1,
        cv2.LINE_AA,
    )


def draw_preview_overlay(img: np.ndarray, state: BoothState) -> None:
    h, w = img.shape[:2]

    draw_panel(img, 0, 0, w, 48, 0.8)
    cv2.putText(
        img,
        "PHOTO BOOTH  —  PREVIEW",
        (20, 34),
        cv2.FONT_HERSHEY_DUPLEX,
        0.85,
        COLOR_WHITE,
        2,
        cv2.LINE_AA,
    )
    draw_coin_badge(img, state.coins)

    bar_h = 72
    bar_y = h - bar_h
    draw_panel(img, 0, bar_y, w, bar_h, 0.85)

    pulse = state.frame_counter % 30 < 15
    confirm_color = COLOR_BLUE if pulse else (200, 140, 0)
    cv2.putText(
        img,
        "[ BTN 1 ]  CONFIRM PRINT  (1 coin)",
        (20, bar_y + 38),
        cv2.FONT_HERSHEY_DUPLEX,
        0.75,
        confirm_color,
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        img,
        "Live camera paused",
        (20, bar_y + 62),
        cv2.FONT_HERSHEY_DUPLEX,
        0.5,
        COLOR_DIM,
        1,
        cv2.LINE_AA,
    )

    border_color = COLOR_GOLD if pulse else COLOR_BLUE
    cv2.rectangle(img, (8, 56), (w - 8, bar_y - 8), border_color, 3, cv2.LINE_AA)


def draw_overlay(frame: np.ndarray, state: BoothState) -> np.ndarray:
    state.frame_counter += 1

    if state.preview_mode and state.pending_frame is not None:
        display = state.pending_frame.copy()
        draw_preview_overlay(display, state)
    else:
        display = frame.copy()
        if state.coins == 0:
            draw_idle_overlay(display, state)
        else:
            draw_active_overlay(display, state)

    if state.coin_flash_frames > 0:
        draw_banner(display, "CREDIT ADDED!", COLOR_GOLD)
        state.coin_flash_frames -= 1

    if state.capture_flash_frames > 0:
        draw_banner(display, "CAPTURED!", COLOR_GREEN)
        state.capture_flash_frames -= 1

    if state.print_flash_frames > 0:
        draw_banner(display, state.print_flash_text, COLOR_BLUE)
        state.print_flash_frames -= 1

    if state.error_flash_frames > 0:
        draw_banner(display, state.error_flash_text, COLOR_RED)
        state.error_flash_frames -= 1

    return display


def init_controller() -> Optional[pygame.joystick.Joystick]:
    pygame.init()
    pygame.joystick.init()

    if pygame.joystick.get_count() <= CAPTURE_CONTROLLER:
        print("No game controller found. Connect your USB Gamepad.")
        return None

    joy = pygame.joystick.Joystick(CAPTURE_CONTROLLER)
    joy.init()
    print(
        f"Controller ready: {joy.get_name()} "
        f"(button {COIN_BUTTON}=coin, button {CAPTURE_BUTTON}=capture, "
        f"button {CONFIRM_BUTTON}=confirm print)"
    )
    return joy


def poll_controller_events() -> Tuple[bool, bool, bool]:
    coin_pressed = False
    capture_pressed = False
    confirm_pressed = False
    for event in pygame.event.get():
        if event.type == pygame.JOYBUTTONDOWN and event.joy == CAPTURE_CONTROLLER:
            if event.button == COIN_BUTTON:
                coin_pressed = True
            elif event.button == CAPTURE_BUTTON:
                capture_pressed = True
            elif event.button == CONFIRM_BUTTON:
                confirm_pressed = True
    return coin_pressed, capture_pressed, confirm_pressed


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    state = BoothState()
    controller = init_controller()
    frame_overlay = load_frame_overlay()

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        raise SystemExit(
            f"Could not open camera at index {CAMERA_INDEX}. "
            "Check permissions or try a different CAMERA_INDEX."
        )

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, DISPLAY_WIDTH, DISPLAY_HEIGHT)

    print(
        "Insert coin (btn 9), capture (btn 0 / s), confirm print (btn 1), quit (q / ESC)."
    )

    try:
        while True:
            coin_pressed, capture_pressed, confirm_pressed = poll_controller_events()
            key = cv2.waitKey(1) & 0xFF

            if coin_pressed:
                insert_coin(state)

            if key in QUIT_KEYS:
                break

            if state.preview_mode:
                if confirm_pressed or key == PRINT_KEY:
                    handle_print(state)
                display = draw_overlay(state.pending_frame, state)
            else:
                ret, frame = cap.read()
                if not ret:
                    continue
                frame = fit_to_display(cv2.flip(frame, 1))

                if key == CAPTURE_KEY or capture_pressed:
                    if state.coins > 0:
                        handle_capture(state, frame, frame_overlay)
                    else:
                        state.error_flash_frames = FLASH_DURATION
                        state.error_flash_text = "INSERT COIN FIRST"

                display = draw_overlay(frame, state)

            cv2.imshow(WINDOW_NAME, display)
    finally:
        cap.release()
        cv2.destroyAllWindows()
        if controller is not None and controller.get_init():
            controller.quit()
        pygame.joystick.quit()
        pygame.quit()


if __name__ == "__main__":
    main()
