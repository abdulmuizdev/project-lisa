"""Read game controller input and print button/axis events to the console."""

from __future__ import annotations

import os
import time

os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")

import pygame

AXIS_DEADZONE = 0.15
AXIS_PRINT_DELTA = 0.25


def print_controller_info(joy: pygame.joystick.Joystick, index: int) -> None:
    print(f"Controller {index}: {joy.get_name()}")
    print(f"  instance_id={joy.get_instance_id()}")
    print(f"  guid={joy.get_guid()}")
    print(f"  buttons={joy.get_numbuttons()}, axes={joy.get_numaxes()}, hats={joy.get_numhats()}")


def controller_name(joysticks: list[pygame.joystick.Joystick], joy_id: int) -> str:
    if 0 <= joy_id < len(joysticks) and joysticks[joy_id].get_init():
        return joysticks[joy_id].get_name()
    return "unknown"


def main() -> None:
    pygame.init()
    pygame.joystick.init()

    joystick_count = pygame.joystick.get_count()
    if joystick_count == 0:
        print("No game controllers detected. Connect one and run again.")
        pygame.quit()
        raise SystemExit(1)

    joysticks: list[pygame.joystick.Joystick | None] = [None] * joystick_count
    last_axes: list[list[float]] = []

    print(f"Found {joystick_count} controller(s):\n")
    for index in range(joystick_count):
        joy = pygame.joystick.Joystick(index)
        joy.init()
        joysticks[index] = joy
        print_controller_info(joy, index)
        last_axes.append([0.0] * joy.get_numaxes())
        print()

    print("Press buttons, move sticks, or use the D-pad.")
    print("Use the printed button number for your capture trigger. Ctrl+C to quit.\n")

    try:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return

                if event.type == pygame.JOYDEVICEADDED:
                    device_index = event.device_index
                    joy = pygame.joystick.Joystick(device_index)
                    joy.init()
                    if device_index >= len(joysticks):
                        joysticks.extend([None] * (device_index + 1 - len(joysticks)))
                        last_axes.extend([] for _ in range(device_index + 1 - len(last_axes)))
                    joysticks[device_index] = joy
                    if device_index >= len(last_axes):
                        last_axes.append([0.0] * joy.get_numaxes())
                    else:
                        last_axes[device_index] = [0.0] * joy.get_numaxes()
                    print(f"\n[connected] Controller added at index {device_index}")
                    print_controller_info(joy, device_index)
                    print()

                elif event.type == pygame.JOYDEVICEREMOVED:
                    print(f"\n[disconnected] instance_id={event.instance_id}\n")

                elif event.type == pygame.JOYBUTTONDOWN:
                    name = controller_name(joysticks, event.joy)
                    print(
                        f"[BUTTON DOWN] controller={event.joy} ({name}) "
                        f"button={event.button}"
                    )

                elif event.type == pygame.JOYBUTTONUP:
                    name = controller_name(joysticks, event.joy)
                    print(
                        f"[BUTTON UP]   controller={event.joy} ({name}) "
                        f"button={event.button}"
                    )

                elif event.type == pygame.JOYAXISMOTION:
                    if event.joy >= len(last_axes):
                        continue

                    prev = last_axes[event.joy][event.axis]
                    curr = event.value
                    last_axes[event.joy][event.axis] = curr

                    prev_active = abs(prev) > AXIS_DEADZONE
                    curr_active = abs(curr) > AXIS_DEADZONE
                    if prev_active == curr_active and (
                        not curr_active or abs(curr - prev) < AXIS_PRINT_DELTA
                    ):
                        continue

                    name = controller_name(joysticks, event.joy)
                    print(
                        f"[AXIS]        controller={event.joy} ({name}) "
                        f"axis={event.axis} value={curr:+.3f}"
                    )

                elif event.type == pygame.JOYHATMOTION:
                    name = controller_name(joysticks, event.joy)
                    x, y = event.value
                    direction = []
                    if y == 1:
                        direction.append("up")
                    elif y == -1:
                        direction.append("down")
                    if x == 1:
                        direction.append("right")
                    elif x == -1:
                        direction.append("left")
                    label = "+".join(direction) if direction else "center"
                    print(
                        f"[HAT/D-PAD]   controller={event.joy} ({name}) "
                        f"hat={event.hat} position=({x}, {y}) [{label}]"
                    )

            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        for joy in joysticks:
            if joy is not None and joy.get_init():
                joy.quit()
        pygame.joystick.quit()
        pygame.quit()


if __name__ == "__main__":
    main()
