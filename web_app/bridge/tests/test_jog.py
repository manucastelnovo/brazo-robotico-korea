import re
import threading
import time

from conftest import FakeClock
from web_app.bridge.arm_service import HOME_COMMANDS, SETUP_COMMANDS, JogController, MockArm
from web_app.bridge.config import Settings

G1 = re.compile(r"G1 ((?:[XYZ]-?\d+\.\d+ ?)+) F(\d+)")


def make_jog(latency_s=0.0):
    clock = FakeClock()
    arm = MockArm(latency_s=latency_s)
    jog = JogController(arm, Settings(), clock=clock)
    jog.connect()
    arm.history.clear()
    return jog, arm, clock


def run_ticks(jog, clock, count, dt=0.02, keepalive=True):
    for _ in range(count):
        clock.advance(dt)
        if keepalive:
            jog.touch()
        jog.step()


def axis_total(history, axis):
    total = 0.0
    for line in history:
        for token in line.split():
            if token.startswith(axis):
                total += float(token[1:])
    return total


def test_connect_sends_setup_commands():
    arm = MockArm(latency_s=0)
    jog = JogController(arm, Settings(), clock=FakeClock())
    jog.connect()
    assert tuple(arm.history) == SETUP_COMMANDS
    assert jog.connected


def test_jog_sends_relative_g1_steps():
    jog, arm, clock = make_jog()
    jog.arm(1)
    jog.set_vector(1, 0, 0, speed=60)
    jog.step()  # first tick only sets the time base
    run_ticks(jog, clock, 50)
    assert arm.history, "no G1 was sent"
    assert all(G1.fullmatch(line) for line in arm.history)
    assert axis_total(arm.history, "X") > 0
    assert axis_total(arm.history, "Y") == 0


def test_not_armed_never_moves():
    jog, arm, clock = make_jog()
    jog.set_vector(1, 1, 1, speed=60)
    run_ticks(jog, clock, 20)
    assert arm.history == []


def test_dead_man_timeout_stops_motion():
    jog, arm, clock = make_jog()
    jog.arm(1)
    jog.set_vector(0, 1, 0, speed=100)
    jog.step()
    run_ticks(jog, clock, 20)
    sent = len(arm.history)
    assert sent > 0
    clock.advance(0.31)  # browser went silent
    jog.step()
    run_ticks(jog, clock, 20, keepalive=False)
    assert len(arm.history) == sent


def test_speed_is_capped_server_side():
    jog, arm, clock = make_jog()
    jog.arm(1)
    jog.set_vector(1, 0, 0, speed=10_000)
    assert jog.speed == Settings().max_speed_mm_s
    jog.step()
    run_ticks(jog, clock, 200)  # long enough for the ramp to settle
    last_dx = float(arm.history[-1].split()[1][1:])
    assert last_dx <= Settings().max_speed_mm_s * 0.02 + 1e-6


def test_vector_is_clamped():
    jog, _, _ = make_jog()
    jog.set_vector(5, -5, "bad")
    assert jog._target == (1.0, -1.0, 0.0)


def test_stop_zeroes_motion_immediately():
    jog, arm, clock = make_jog()
    jog.arm(1)
    jog.set_vector(1, 1, 0, speed=100)
    jog.step()
    run_ticks(jog, clock, 20)
    jog.stop()
    sent = len(arm.history)
    run_ticks(jog, clock, 20)  # still connected and alive, but no vector
    assert len(arm.history) == sent


def test_disarm_last_client_stops():
    jog, arm, clock = make_jog()
    jog.arm(1)
    jog.set_vector(1, 0, 0, speed=100)
    jog.step()
    run_ticks(jog, clock, 10)
    jog.disarm(1)
    sent = len(arm.history)
    run_ticks(jog, clock, 10)
    assert len(arm.history) == sent


def test_home_sequence_matches_gamepad_script():
    jog, arm, clock = make_jog()
    jog.arm(1)
    jog.home()
    clock.advance(0.02)
    assert jog.step() == "HOME"
    assert arm.history == [line for line, _ in HOME_COMMANDS]
    assert arm.history == ["G90", "M1008 A5", "M400", "G91"]


def test_feed_rate_lets_each_step_finish_in_time():
    jog, arm, clock = make_jog()
    jog.arm(1)
    jog.set_vector(1, 0, 0, speed=150)
    jog.step()
    run_ticks(jog, clock, 200)
    match = G1.fullmatch(arm.history[-1])
    dx = float(match.group(1).strip()[1:])
    feed_mm_s = int(match.group(2)) / 60.0
    assert dx / feed_mm_s <= 0.02  # the step takes no longer than one tick


def test_real_loop_keeps_one_command_in_flight():
    arm = MockArm(latency_s=0.005)
    jog = JogController(arm, Settings())
    jog.start()
    try:
        jog.arm(1)

        def spam_vectors():  # a browser sending far faster than the arm can move
            stop = time.monotonic() + 0.5
            while time.monotonic() < stop:
                jog.set_vector(1, -1, 0.5, speed=150)

        spammers = [threading.Thread(target=spam_vectors) for _ in range(3)]
        for thread in spammers:
            thread.start()
        for thread in spammers:
            thread.join()
        jog.home()
        time.sleep(0.1)
    finally:
        jog.close()
    assert any(line.startswith("G1 ") for line in arm.history)
    assert arm.max_in_flight == 1
