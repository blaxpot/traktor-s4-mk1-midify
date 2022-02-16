#!/usr/bin/env python3

import csv
import evdev
import rtmidi
import subprocess

# TODO: allow user specified event code mappings via CLI option

# Keys are snd-usb-caiaq event codes, values are MIDI control change (CC) codes/channels. Values ranges are translated
# from snd-usb-caiaq ranges to MIDI ranges based on the control code. For example, a fader has a value range from 0-4095
# in snd-usb-caiaq messages, but Mixxx expects MIDI values between 0-127. Thus, integer division by 32 converts the
# value for all fader CCs from snd-usb-caiaq to MIDI.
def load_midi_map_mixer_effect(filename='midi-evcode-map-mixer-effect.csv'):
    mapping = [None for i in range(350)]

    with open(filename, newline='') as csvfile:
        reader = csv.reader(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        for line in reader:
            mapping[int(line[0])] = [
                [int(line[1], 16), int(line[2], 16)],
                [int(line[3], 16), int(line[4], 16)]
            ]

    return mapping

MIDI_MAP_MIXER_EFFECT = load_midi_map_mixer_effect()


# Decks are affected by the shift modifier key and the deck toggle buttons, so we need to send different MIDI data based
# on the state of these modifiers.
def load_midi_map_deck(filename='midi-evcode-map-deck.csv'):
    mapping = [None for i in range(320)]

    with open(filename, newline='') as csvfile:
        reader = csv.reader(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        for line in reader:
            mapping[int(line[0])] = [
                [int(line[1], 16), int(line[2], 16)],
                [int(line[3], 16), int(line[4], 16)],
                [int(line[5], 16), int(line[6], 16)],
                [int(line[7], 16), int(line[8], 16)]
            ]

    return mapping


MIDI_MAP_DECK = load_midi_map_deck()

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
        [*range(55, 62, 1)]
    ],
}

ALSA_DEV = subprocess.getoutput('aplay -l | grep "Traktor Kontrol S4" | cut -d " " -f 2').replace(':', '')
BTN_CCS = [0x01, 0x05, 0x06, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10, 0x11, 0x12, 0x13, 0x15, 0x17, 0x18]

# TODO: probably better to have a single array of strings to determine input types from event codes - faster lookups
BTN_EVCODES = [270, 310, 267, 307, 269, 309, 271, 311, 275, 299, 274, 298, 266, 306, 268, 308, 273, 297, 272, 296, 259,
               315, 261, 317, 263, 319, 256, 312, 258, 314, 260, 316, 262, 318, 265, 305, 321, 322, 323, 324, 325, 330,
               331, 332, 333, 328, 329, 334, 335, 289, 290, 288, 291, 284, 283, 281, 282, 280, 292, 345, 346, 347, 348,
               349]
POT_EVCODES = [21, 22, 18, 17, 19, 16, 50, 49, 48, 43, 39, 47, 31, 42, 38, 46, 30, 41, 37, 45, 29, 40, 36, 44, 28, 23,
               34, 33, 32, 51, 35]
ROT_EVCODES = [55, 57, 56, 58, 59, 60, 61, 62, 54]
JOG_POT_EVCODES = [26, 27]
JOG_ROT_EVCODES = [53, 53]


def select_controller_device():
    print('List of your devices:')
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]

    for i, device in enumerate(devices):
        print(f'[{i}]\t{device.path}\t{device.name}\t{device.phys}')

    device_id = int(input("Which of these is the controller? "))
    controller = devices.pop(device_id)

    for device in devices:
        device.close()

    return controller


def detect_controller_device():
    for path in evdev.list_devices():
        device = evdev.InputDevice(path)

        if device.name.__contains__('Traktor Kontrol S4'):
            print('Detected evdev:')
            print(f'{device.name}\t{device.path}\t{device.phys}')
            return device
        else:
            device.close()

    print("Couldn't find your controller. Do you see it in the output of lsusb?")
    quit()


def detect_alsa_device():
    if ALSA_DEV:
        print('Detected ALSA device: ')
        print(subprocess.getoutput('aplay -l | grep "Traktor Kontrol S4"'))
    else:
        print("Couldn't find your controller with aplay. Do you have the snd-usb-caiaq installed / enabled?")
        quit()


def evcode_to_midi(evcode, shift_a, shift_b, toggle_ac, toggle_bd):
    if MIDI_MAP_MIXER_EFFECT[evcode]:
        if shift_a or shift_b:
            return MIDI_MAP_MIXER_EFFECT[evcode][1]
        else:
            return MIDI_MAP_MIXER_EFFECT[evcode][0]
    elif MIDI_MAP_DECK[evcode]:
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
        return []


def midi_to_alsa_control(midi_bytes):
    # Bitwise & to get the lower 4 bytes of the MIDI CC
    channel = midi_bytes[0] & 0x4f
    cc = midi_bytes[1]

    if cc not in ALSA_CONTROL_MAP:
        return 0

    if channel < len(ALSA_CONTROL_MAP[cc]):
        return ALSA_CONTROL_MAP[cc][channel]
    else:
        return 0


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
            alsa_values = [2, 4, 5, 7, 9, 10, 12, 14, 15, 17, 19, 21, 22, 24, 26, 28, 29, 31]
            set_led(controls[full_brightness], alsa_values[partial - 1])

    for i in range(full_brightness, 6, 1):
        set_led(controls[i], 0)


def set_led(alsa_id, brightness):
    subprocess.call(['amixer', '-c', ALSA_DEV, 'cset', f'numid={alsa_id}', str(brightness)], stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL)


def handle_midi_input(msg, data):
    control = midi_to_alsa_control(msg[0])

    if not control:
        return

    cc = msg[0][1]
    value = msg[0][2]

    # TODO: handle LED control based on ALSA control code so user can modify mapping without breaking this
    if cc == 0x46:  # Vu meters
        set_vu_meter(control, value)

    if cc in BTN_CCS:
        alsa_val = 31 if value else 0
        set_led(control, alsa_val)


def main():
    detect_alsa_device()
    traktor_s4 = detect_controller_device()
    midiin = rtmidi.MidiIn(name='blaxpot')
    inport = midiin.open_virtual_port(name='traktor-s4-mk1-midify')
    inport.set_callback(handle_midi_input)
    midiout = rtmidi.MidiOut(name='blaxpot')
    outport = midiout.open_virtual_port(name='traktor-s4-mk1-midify')
    shift_a = False
    shift_b = False
    toggle_ac = False
    toggle_bd = False

    for event in traktor_s4.read_loop():
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

        if not midi:
            continue

        if event.code in POT_EVCODES:
            outport.send_message([midi[1], midi[0], event.value // 32])
        if event.code in BTN_EVCODES:
            outport.send_message([midi[1], midi[0], event.value])

    inport.close_port()
    midiin.delete()
    outport.close_port()
    midiout.delete()
    traktor_s4.close()


def print_events():
    traktor_s4 = select_controller_device()

    for event in traktor_s4.read_loop():
        print(event)

    traktor_s4.close()
