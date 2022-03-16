#!/usr/bin/env python3

import csv
import evdev
import getopt
import rtmidi
import subprocess
import sys


def is_hex(string):
    try:
        int(string, 16)
        return True
    except ValueError:
        return False


class Mappings:
    def __init__(self,
                 alsa_control_mapping='alsa-control-map.csv',
                 deck_mapping='midi-evcode-map-deck.csv',
                 mixer_effect_mapping='midi-evcode-map-mixer-effect.csv'):
        self.alsa_control = [None for i in range(76)]
        self.deck = [None for i in range(320)]
        self.mixer_effect = [None for i in range(350)]
        self.set_alsa_control_mapping(alsa_control_mapping)
        self.set_deck_mapping(deck_mapping)
        self.set_mixer_effect_mapping(mixer_effect_mapping)

    # Indicies are MIDI control codes, values are an array of ALSA numeric control IDs indexed on the MIDI channel.
    def set_alsa_control_mapping(self, filename):
        with open(filename, newline='') as csvfile:
            reader = csv.reader(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

            for line in reader:
                if not is_hex(line[0]):
                    continue

                cc = int(line[0], 16)
                self.alsa_control[cc] = [None for i in range(5)]

                for i in range(1, 6, 1):
                    if line[i].isdigit():
                        self.alsa_control[cc][i - 1] = int(line[i])
                    elif all(ele.isdigit() for ele in line[i].split(',')):
                        self.alsa_control[cc][i - 1] = list(map(int, line[i].split(',')))
                    else:
                        self.alsa_control[cc][i - 1] = None

    # Indicies are snd-usb-caiaq event codes, values are MIDI control change (CC) codes/channels.
    # Decks are affected by the shift modifier key and the deck toggle buttons, so alternate mappings are included based
    # on the state of these modifiers.
    def set_deck_mapping(self, filename):
        with open(filename, newline='') as csvfile:
            reader = csv.reader(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

            for line in reader:
                self.deck[int(line[0])] = [
                    [int(line[1], 16), int(line[2], 16)],
                    [int(line[3], 16), int(line[4], 16)],
                    [int(line[5], 16), int(line[6], 16)],
                    [int(line[7], 16), int(line[8], 16)]
                ]

    # Indicies are snd-usb-caiaq event codes, values are MIDI control change (CC) codes/channels.
    # The mixer / effect unit controls could have alternative functions if shift buttons are in use, so alternate
    # mappings are included for each event code.
    def set_mixer_effect_mapping(self, filename):
        with open(filename, newline='') as csvfile:
            reader = csv.reader(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

            for line in reader:
                self.mixer_effect[int(line[0])] = [
                    [int(line[1], 16), int(line[2], 16)],
                    [int(line[3], 16), int(line[4], 16)]
                ]


def usage():
    print("Usage: traktor-s4-mk1-midify [options]\n"
          "\n"
          "Options:\n"
          "  -a <mapping.csv>\tCSV file mapping MIDI control codes to alsa LED control ids\n"
          "  -d <mapping.csv>\tCSV file mapping snd-usb-caiaq event codes for deck inputs to MIDI CC codes/channels\n"
          "  -m <mapping.csv>\tCSV file mapping snd-usb-caiaq event codes for mixer/effect unit inputs to MIDI CC "
          "codes/channels")
    quit(1)


alsa_control_mapping = 'alsa-control-map.csv'
deck_mapping = 'midi-evcode-map-deck.csv'
mixer_effect_mapping = 'midi-evcode-map-mixer-effect.csv'

try:
    opts, args = getopt.getopt(sys.argv[1:], 'a:d:m:')
except:
    usage()

for opt, arg in opts:
    if opt in ['-a']:
        alsa_control_mapping = arg
    elif opt in ['-d']:
        deck_mapping = arg
    elif opt in ['-m']:
        mixer_effect_mapping = arg
    else:
        usage()

mappings = Mappings(alsa_control_mapping, deck_mapping, mixer_effect_mapping)
MIDI_MAP_MIXER_EFFECT = mappings.mixer_effect
MIDI_MAP_DECK = mappings.deck
ALSA_CONTROL_MAP = mappings.alsa_control
ALSA_DEV = subprocess.getoutput('aplay -l | grep "Traktor Kontrol S4" | cut -d " " -f 2').replace(':', '')
# TODO: probably better to have a single array of strings to determine input types from event codes - faster lookup
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

    if cc >= len(ALSA_CONTROL_MAP):
        return None

    if not ALSA_CONTROL_MAP[cc]:
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

    value = msg[0][2]

    # TODO: Handle segment displays in elif here, otherwise assume simple LED with 2 states (on/off)
    if type(control) is list:  # Vu meters
        set_vu_meter(control, value)
    else:
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
