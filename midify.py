#!/usr/bin/env python3

import evdev
import mido

MIDI_MAP = {
    18: {'cc': 0x45, 'ch': 0},   # Deck A volume
    17: {'cc': 0x45, 'ch': 1},   # Deck B volume
    19: {'cc': 0x45, 'ch': 2},   # Deck C volume
    16: {'cc': 0x45, 'ch': 3},   # Deck D volume
    263: {'cc': 0x0A, 'ch': 0},  # Deck A play
    319: {'cc': 0x0A, 'ch': 1},  # Deck B play
    # 263: {'cc': 0x0A, 'ch': 2},  # Deck C play (need to check deck toggle state for this to work)
    # 319: {'cc': 0x0A, 'ch': 3},  # Deck D play (need to check deck toggle state for this to work)
}


def evcode_to_midi(evcode):
    return MIDI_MAP[evcode] if evcode in MIDI_MAP else {}


def main():
    print('List of your devices:')
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]

    for i, device in enumerate(devices):
        print("[{}]\t{}\t{}\t{}".format(i, device.path, device.name, device.phys))

    device_id = int(input("Which of these is the controller? "))
    traktor_s4 = devices.pop(device_id)

    for device in devices:
        device.close()

    outport = mido.open_output('Traktor S4 mk1', virtual=True)

    for event in traktor_s4.read_loop():
        midi = evcode_to_midi(event.code)

        if not midi:
            continue

        if midi['cc'] == 0x45:  # volume sliders
            outport.send(mido.Message('control_change', control=midi['cc'], channel=midi['ch'], value=event.value//32))
        if midi['cc'] == 0x0A:  # play buttons
            outport.send(mido.Message('control_change', control=midi['cc'], channel=midi['ch'], value=event.value))

    outport.close()
    traktor_s4.close()
