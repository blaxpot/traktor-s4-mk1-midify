#!/usr/bin/env python3

# TODO: allow user specified event code mappings via CLI option

import argparse
import csv
import evdev
import os
import rtmidi
import subprocess
import time


# Indicies are snd-usb-caiaq event codes, values are MIDI control change (CC) codes/channels.
def load_midi_map_mixer_effect(filename=os.path.join(os.path.dirname(__file__), "midi-evcode-map-mixer-effect.csv")):
    mapping = [None for _ in range(350)]

    with open(filename, newline="") as csvfile:
        reader = csv.reader(csvfile, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL)

        for line in reader:
            mapping[int(line[0])] = [
                [int(line[1], 16), int(line[2], 16)],
                [int(line[3], 16), int(line[4], 16)],
            ]

    return mapping


MIDI_MAP_MIXER_EFFECT = load_midi_map_mixer_effect()


# Indicies are snd-usb-caiaq event codes, values are MIDI control change (CC) codes/channels.
# Decks are affected by the shift modifier key and the deck toggle buttons, so we need to send different MIDI data based
# on the state of these modifiers.
def load_midi_map_deck(filename=os.path.join(os.path.dirname(__file__), "midi-evcode-map-deck.csv")):
    mapping = [None for _ in range(320)]

    with open(filename, newline="") as csvfile:
        reader = csv.reader(csvfile, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL)

        for line in reader:
            mapping[int(line[0])] = [
                [int(line[1], 16), int(line[2], 16)],
                [int(line[3], 16), int(line[4], 16)],
                [int(line[5], 16), int(line[6], 16)],
                [int(line[7], 16), int(line[8], 16)],
            ]

    return mapping


MIDI_MAP_DECK = load_midi_map_deck()


def load_evcode_type_map(filename=os.path.join(os.path.dirname(__file__), "evcode-type-map.csv")):
    mapping = [None for _ in range(350)]

    with open(filename, newline="") as csvfile:
        reader = csv.reader(csvfile, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL)

        for line in reader:
            mapping[int(line[0])] = line[1]

    return mapping


EVCODE_TYPE_MAP = load_evcode_type_map()

# TODO: load ALSA control map from file
# Keys are MIDI control codes, values are an array of ALSA numeric control IDs indexed on the MIDI channel.
ALSA_CONTROL_MAP = {
    0x01: [74, 118, 74, 118],  # Load [BTN]
    0x08: [79, 123, 79, 123],  # Sync [BTN]
    0x09: [80, 124, 80, 124],  # Cue [BTN]
    0x0B: [66, 110, 66, 110],  # Cue 1 [BTN]
    0x0C: [68, 112, 68, 112],  # Cue 2 [BTN]
    0x0D: [70, 114, 70, 114],  # Cue 3 [BTN]
    0x0E: [72, 116, 72, 116],  # Cue 4 [BTN]
    0x0A: [81, 125, 81, 125],  # Play [BTN]
    0x46: [  # Vu meters
        [*range(16, 23, 1)],
        [*range(29, 36, 1)],
        [*range(42, 49, 1)],
        [*range(55, 62, 1)],
    ],
}

ALSA_DEV = subprocess.getoutput('aplay -l | grep "Traktor Kontrol S4" | cut -d " " -f 2').replace(":", "")

BTN_CCS = [
    0x01,
    0x05,
    0x06,
    0x08,
    0x09,
    0x0A,
    0x0B,
    0x0C,
    0x0D,
    0x0E,
    0x0F,
    0x10,
    0x11,
    0x12,
    0x13,
    0x15,
    0x17,
    0x18,
]


def select_controller_device():
    print("List of your devices:")
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]

    for i, device in enumerate(devices):
        print(f"[{i}]\t{device.path}\t{device.name}\t{device.phys}")

    device_id = int(input("Which of these is the controller? "))
    controller = devices.pop(device_id)

    for device in devices:
        device.close()

    return controller


def detect_controller_device():
    for path in evdev.list_devices():
        device = evdev.InputDevice(path)

        if device.name.__contains__("Traktor Kontrol S4"):
            print("Detected evdev:")
            print(f"{device.name}\t{device.path}\t{device.phys}")
            return device
        else:
            device.close()

    print("Couldn't find your controller. Do you see it in the output of lsusb?")
    quit()


def detect_alsa_device():
    if ALSA_DEV:
        print("Detected ALSA device: ")
        print(subprocess.getoutput('aplay -l | grep "Traktor Kontrol S4"'))
    else:
        print("Couldn't find your controller with aplay. Do you have snd-usb-caiaq installed / enabled?")
        quit()


def evcode_to_midi(evcode, shift_a, shift_b, toggle_ac, toggle_bd):
    if MIDI_MAP_MIXER_EFFECT[evcode] is not None:
        if shift_a or shift_b:
            return MIDI_MAP_MIXER_EFFECT[evcode][1]
        else:
            return MIDI_MAP_MIXER_EFFECT[evcode][0]
    elif MIDI_MAP_DECK[evcode] is not None:
        # Decks B/D use 0xB1/0xB3
        if MIDI_MAP_DECK[evcode][1][1] & 1 == 1:
            if toggle_bd:
                if shift_b:
                    return MIDI_MAP_DECK[evcode][3]
                else:
                    return MIDI_MAP_DECK[evcode][2]
            else:
                if shift_b:
                    return MIDI_MAP_DECK[evcode][1]
                else:
                    return MIDI_MAP_DECK[evcode][0]
        # Decks A/C use 0xB0/0xB2
        else:
            if toggle_ac:
                if shift_a:
                    return MIDI_MAP_DECK[evcode][3]
                else:
                    return MIDI_MAP_DECK[evcode][2]
            else:
                if shift_a:
                    return MIDI_MAP_DECK[evcode][1]
                else:
                    return MIDI_MAP_DECK[evcode][0]
    else:
        return None


def midi_to_alsa_control(midi_bytes):
    # Bitwise & to get the lower 4 bytes of the MIDI CC
    channel = midi_bytes[0] & 0x4F
    cc = midi_bytes[1]

    if cc not in ALSA_CONTROL_MAP:
        return None

    if channel < len(ALSA_CONTROL_MAP[cc]):
        return ALSA_CONTROL_MAP[cc][channel]
    else:
        return None


# We have 7 volume indicators per channel, one of which indicates clipping, which can be set at 31 brightness levels.
# 18 (brightness levels) * 7 (LEDs) = 126, which is one off the max value Mixxx will send in a MIDI message to indicate
# Volume (0x7F). Subtract 1 from this value and use this value to set the right number of LEDs at the right brightness.
#
# We can skip a few brightness levels as we scale up so that we more or less linearly increase brightness.
def set_vu_meter(controls, value):
    light = value - 1  # ensure we stay <= 126
    full_brightness = light // 18

    if value:
        full_brightness = light // 18
        partial = light % 18

        for i in range(full_brightness):
            set_led(controls[i], 31)

        if partial:
            alsa_values = [
                2,
                4,
                5,
                7,
                9,
                10,
                12,
                14,
                15,
                17,
                19,
                21,
                22,
                24,
                26,
                28,
                29,
                31,
            ]
            set_led(controls[full_brightness], alsa_values[partial - 1])

    for i in range(full_brightness, 6, 1):
        set_led(controls[i], 0)


def set_led(alsa_id, brightness):
    subprocess.call(
        ["amixer", "-c", ALSA_DEV, "cset", f"numid={alsa_id}", str(brightness)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def handle_midi_input(msg, _):
    control = midi_to_alsa_control(msg[0])

    if control is None:
        return

    cc = msg[0][1]
    value = msg[0][2]

    # TODO: handle LED control based on ALSA control code so user can modify mapping without breaking this
    if cc == 0x46:  # Vu meters
        set_vu_meter(control, value)

    if cc in BTN_CCS:
        alsa_val = 31 if value else 0
        set_led(control, alsa_val)


def calculate_jog_midi_value_update_jog_data(event, jog_data):
    if jog_data["prev_control_value"] is None:
        jog_data["prev_control_value"] = event.value
        jog_data["updated"] = time.time()
        return None, jog_data

    # Get the change in the jog wheel control value since the last event
    if event.value <= 255 and jog_data["prev_control_value"] >= 767:  # value increased past max
        diff = 1024 - jog_data["prev_control_value"] + event.value
    elif event.value >= 767 and jog_data["prev_control_value"] <= 255:  # value decreased past min
        diff = event.value - 1024 - jog_data["prev_control_value"]
    else:
        diff = event.value - jog_data["prev_control_value"]  # value stayed within range

    jog_data["prev_control_value"] = event.value

    # If it's been less than the interval specified in jog_sensitivity, store the cumulative jog wheel control value
    # change for later and stop processing.
    if time.time() - jog_data["updated"] < jog_data["sensitivity"]:
        jog_data["counter"] += diff
        return None, jog_data
    else:
        midi_value = jog_data["counter"] + diff
        jog_data["counter"] = 0
        jog_data["updated"] = time.time()

        # Convert signed int value to unsigned values that Mixxx expects in jog wheel MIDI messages
        if -64 <= midi_value < 0:
            midi_value = 128 + midi_value
        elif midi_value < -64:
            midi_value = 64
        elif midi_value >= 63:
            midi_value = 63

        return midi_value, jog_data


def calculate_gain_midi_value_update_gain_data(event, gain_data):
    if gain_data["prev_control_value"] is None:
        gain_data["prev_control_value"] = event.value
        gain_data["counter"] = 0x3F
        gain_data["updated"] = time.time()
        return 0x3F, gain_data

    # Get the change in the rotary encoder value since the last event
    if event.value <= 3 and gain_data["prev_control_value"] >= 12:  # value increased past max
        diff = 16 - gain_data["prev_control_value"] + event.value
    elif event.value >= 12 and gain_data["prev_control_value"] <= 3:  # value decreased past min
        diff = event.value - 16 - gain_data["prev_control_value"]
    else:
        diff = event.value - gain_data["prev_control_value"]  # value stayed within range

    gain_data["prev_control_value"] = event.value

    # If it has been less than 5ms since last gain rot message, store cumulative gain rot control data for later and
    # stop processing.
    if time.time() - gain_data["updated"] < 0.005:
        gain_data["counter"] += diff
        return None, gain_data
    else:
        gain_data["counter"] += diff
        gain_data["updated"] = time.time()

        if gain_data["counter"] > 0x7F:
            gain_data["counter"] = 0x7F
        elif gain_data["counter"] < 0:
            gain_data["counter"] = 0

        return gain_data["counter"], gain_data


def calculate_rot_midi_value_update_rot_data(event, rot_data):
    if rot_data["prev_control_value"] is None:
        rot_data["prev_control_value"] = event.value
        rot_data["updated"] = time.time()
        return None, rot_data

    # Get the change in the rotary encoder value since the last event
    if event.value <= 3 and rot_data["prev_control_value"] >= 12:  # value increased past max
        diff = 16 - rot_data["prev_control_value"] + event.value
    elif event.value >= 12 and rot_data["prev_control_value"] <= 3:  # value decreased past min
        diff = event.value - 16 - rot_data["prev_control_value"]
    else:
        diff = event.value - rot_data["prev_control_value"]  # value stayed within range

    rot_data["prev_control_value"] = event.value

    # If it has been less than 5ms since last rot message, store cumulative control data for later and stop processing.
    if time.time() - rot_data["updated"] < 0.005:
        rot_data["counter"] += diff
        return None, rot_data
    else:
        midi_value = 0x3F + rot_data["counter"] + diff
        rot_data["counter"] = 0
        rot_data["updated"] = time.time()

        if midi_value > 0x7F:
            midi_value = 0x7F
        elif midi_value < 0:
            midi_value = 0

        return midi_value, rot_data


# Values ranges are translated from snd-usb-caiaq ranges to MIDI ranges based on the control type. For example,
# a fader has a value range from 0-4095 in snd-usb-caiaq events, but Mixxx expects MIDI values between 0-127.
# Thus, integer division by 32 converts the value for all fader CCs from snd-usb-caiaq to MIDI.
def calculate_midi_value_update_controller_data(event, controller_data, toggle_ac, toggle_bd):
    match EVCODE_TYPE_MAP[event.code]:
        case "BTN":
            return event.value, controller_data
        case "POT":
            value = event.value // 32
            return value, controller_data
        case "JOG_ROT":
            # TODO: make these deck toggle aware
            jog_rots = ["jog_a", "jog_b"]
            jog_rot = jog_rots[event.code - 52]  # jog rot event codes are sequential beginning at 52

            value, controller_data[jog_rot] = calculate_jog_midi_value_update_jog_data(event, controller_data[jog_rot])

            return value, controller_data
        case "BROWSE_ROT":
            value, rot_data = calculate_rot_midi_value_update_rot_data(event, controller_data["browse_rot"])
            controller_data["browse_rot"] = rot_data

            return value, controller_data
        case "ROT":
            rots = ["move_rot_", "size_rot_", "move_rot_", "size_rot_"]
            rot = rots[event.code - 55]  # move / size rot event codes are sequential beginning at 55

            if event.code <= 56:
                if toggle_ac:
                    rot = rot + "c"
                else:
                    rot = rot + "a"
            else:
                if toggle_bd:
                    rot = rot + "d"
                else:
                    rot = rot + "b"

            value, controller_data[rot] = calculate_rot_midi_value_update_rot_data(event, controller_data[rot])

            return value, controller_data
        case "GAIN_ROT":
            gain_rots = ["gain_rot_a", "gain_rot_b", "gain_rot_c", "gain_rot_d"]
            gain_rot = gain_rots[event.code - 59]  # gain rot event codes are sequential beginning at 59

            value, rot_data = calculate_gain_midi_value_update_gain_data(event, controller_data[gain_rot])
            controller_data[gain_rot] = rot_data

            return value, controller_data
        case "JOG_TOUCH":
            value = 0

            if event.value >= 3050:
                value = 0x7F

            return value, controller_data
        case _:
            return None, controller_data


def midify():
    jog_sensitivity = 0.005

    parser = argparse.ArgumentParser(
        description="Convert events generated by the snd-usb-caiaq kernel module to MIDI signals"
    )

    parser.add_argument(
        "-j",
        "--jog_sensitivity",
        type=int,
        help="Adjust jog wheel sensitivity (min: 1, max: 100, default: 5)",
    )

    parser.add_argument("-d", "--debug", action="store_true", help="Show debug log messages")
    args = parser.parse_args()

    if args.jog_sensitivity and 0 < int(args.jog_sensitivity) <= 100:
        jog_sensitivity = int(args.jog_sensitivity) * 0.001
    else:
        print("Jog sensitivity must be between 1 and 100. Using default value (5).")

    detect_alsa_device()
    traktor_s4 = detect_controller_device()
    midiin = rtmidi.MidiIn(name="blaxpot")
    inport = midiin.open_virtual_port(name="traktor-s4-mk1-midify")
    inport.set_callback(handle_midi_input)
    midiout = rtmidi.MidiOut(name="blaxpot")
    outport = midiout.open_virtual_port(name="traktor-s4-mk1-midify")
    shift_a = False
    shift_b = False
    toggle_ac = False
    toggle_bd = False
    control_values = [None for _ in range(350)]

    controller_data = {
        "jog_a": {
            "counter": 0,
            "prev_control_value": None,
            "sensitivity": jog_sensitivity,
            "updated": time.time(),
        },
        "jog_b": {
            "counter": 0,
            "prev_control_value": None,
            "sensitivity": jog_sensitivity,
            "updated": time.time(),
        },
        "browse_rot": {
            "counter": 0,
            "prev_control_value": None,
            "updated": time.time(),
        },
    }

    for control in ["move", "size", "gain"]:
        for deck in ["a", "b", "c", "d"]:
            rotary_encoder = "{}_rot_{}".format(control, deck)

            controller_data[rotary_encoder] = {
                "counter": 0,
                "prev_control_value": None,
                "updated": time.time(),
            }

    for event in traktor_s4.read_loop():
        # TODO: When the following controls are used, it doesn't look like any events are sent. This looks to be caused
        # by bugs in the snd-usb-caiaq module. Some events are recieved when the controls are used, but their evcodes
        # are for other controls and their values don't change. Investigate.

        # TODO: The footswitch doesn't send any events. It's hard to guess what evcode to expect here.

        # TODO: The HI eq pot on deck C doesn't seem to send any event values either. Expect evcode 47, values 0-4095.

        # TODO: Likewise for the loop recorder dry / wet pot. Expect evcode 20, values 0-4095.

        # Ignore events which don't change control values
        if event.value == control_values[event.code]:
            continue

        control_values[event.code] = event.value

        if args.debug:
            print(
                "[Processing event] Code: {}, Value: {}, Timestamp: {}".format(
                    event.code, event.value, event.timestamp()
                )
            )

        # Handle modifier key event codes
        if event.code == 257:
            shift_a = not shift_a
            continue

        if event.code == 264 and event.value:
            toggle_ac = not toggle_ac
            continue

        if event.code == 313:
            shift_b = not shift_b
            continue

        if event.code == 304 and event.value:
            toggle_bd = not toggle_bd
            continue

        midi = evcode_to_midi(event.code, shift_a, shift_b, toggle_ac, toggle_bd)

        # Ignore events with no corresponding MIDI control defined
        if midi is None:
            continue

        value, controller_data = calculate_midi_value_update_controller_data(
            event, controller_data, toggle_ac, toggle_bd
        )

        if value is None:
            continue

        # TODO: consider rate limiting MIDI messages from controls that can produce a lot of messages, e.g. jog wheels
        # / faders, since these seem to overwhelm Mixxx if used a lot.
        outport.send_message([midi[1], midi[0], value])

        if args.debug:
            print("[Sent MIDI message] Channel: {}, CC: {}, Value: {}".format(hex(midi[1]), hex(midi[0]), hex(value)))

    inport.close_port()
    midiin.delete()
    outport.close_port()
    midiout.delete()
    traktor_s4.close()


def print_events():
    traktor_s4 = detect_controller_device()
    control_values = [None for _ in range(350)]

    for event in traktor_s4.read_loop():
        if event.value == control_values[event.code]:
            continue

        control_values[event.code] = event.value
        print(event)

    traktor_s4.close()
