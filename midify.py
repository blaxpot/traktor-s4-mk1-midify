#!/usr/bin/env python3

import evdev
import rtmidi
from subprocess import DEVNULL, STDOUT, check_call

# Keys are snd-usb-caiaq event codes, values are MIDI control change (CC) codes/channels. Values ranges are translated
# from snd-usb-caiaq ranges to MIDI ranges based on the control code. For example, a fader has a value range from 0-4095
# in snd-usb-caiaq messages, but Mixxx expects MIDI values between 0-127. Thus, integer division by 32 converts the
# value for all fader CCs from snd-usb-caiaq to MIDI.
MIDI_MAP = {
    270: {'cc': 0x01, 'ch': 0},  # Deck A load [BTN]
    26:  {'cc': 0x02, 'ch': 0},  # Deck A jog wheel press
    52:  {'cc': 0x03, 'ch': 0},  # Deck A jog wheel turn
    21:  {'cc': 0x04, 'ch': 0},  # Deck A tempo [FADER]
    273: {'cc': 0x05, 'ch': 0},  # Deck A tempo range adjust down [BTN]
    272: {'cc': 0x06, 'ch': 0},  # Deck A tempo range adjust up [BTN]
    259: {'cc': 0x08, 'ch': 0},  # Deck A sync [BTN]
    261: {'cc': 0x09, 'ch': 0},  # Deck A cue [BTN]
    263: {'cc': 0x0A, 'ch': 0},  # Deck A play [BTN]
    256: {'cc': 0x0B, 'ch': 0},  # Deck A Cue 1 [BTN]
    258: {'cc': 0x0C, 'ch': 0},  # Deck A Cue 2 [BTN]
    260: {'cc': 0x0D, 'ch': 0},  # Deck A Cue 3 [BTN]
    262: {'cc': 0x0E, 'ch': 0},  # Deck A Cue 4 [BTN]
    265: {'cc': 0x0F, 'ch': 0},  # Deck A Sample 1 [BTN]
    267: {'cc': 0x10, 'ch': 0},  # Deck A Sample 2 [BTN]
    269: {'cc': 0x11, 'ch': 0},  # Deck A Sample 3 [BTN]
    271: {'cc': 0x12, 'ch': 0},  # Deck A Sample 4 [BTN]
    275: {'cc': 0x13, 'ch': 0},  # Deck A loop move knob press [BTN]
    55:  {'cc': 0x14, 'ch': 0},  # Deck A loop move knob turn [ROT_ENC]
    274: {'cc': 0x15, 'ch': 0},  # Deck A loop size knob press [BTN]
    56:  {'cc': 0x16, 'ch': 0},  # Deck A loop size knob turn [ROT_ENC]
    266: {'cc': 0x17, 'ch': 0},  # Deck A loop in [BTN]
    268: {'cc': 0x18, 'ch': 0},  # Deck A loop out [BTN]
    18:  {'cc': 0x45, 'ch': 0},  # Deck A volume [FADER]
    310: {'cc': 0x01, 'ch': 1},  # Deck B load [BTN]
    27:  {'cc': 0x02, 'ch': 1},  # Deck B jog wheel press
    53:  {'cc': 0x03, 'ch': 1},  # Deck B jog wheel turn
    22:  {'cc': 0x04, 'ch': 1},  # Deck B tempo [FADER]
    297: {'cc': 0x05, 'ch': 1},  # Deck B tempo range adjust down [BTN]
    296: {'cc': 0x06, 'ch': 1},  # Deck B tempo range adjust up [BTN]
    315: {'cc': 0x08, 'ch': 1},  # Deck B sync [BTN]
    317: {'cc': 0x09, 'ch': 1},  # Deck B cue [BTN]
    319: {'cc': 0x0A, 'ch': 1},  # Deck B play [BTN]
    312: {'cc': 0x0B, 'ch': 1},  # Deck B Cue 1 [BTN]
    314: {'cc': 0x0C, 'ch': 1},  # Deck B Cue 2 [BTN]
    316: {'cc': 0x0D, 'ch': 1},  # Deck B Cue 3 [BTN]
    318: {'cc': 0x0E, 'ch': 1},  # Deck B Cue 4 [BTN]
    305: {'cc': 0x0F, 'ch': 1},  # Deck B Sample 1 [BTN]
    307: {'cc': 0x10, 'ch': 1},  # Deck B Sample 2 [BTN]
    309: {'cc': 0x11, 'ch': 1},  # Deck B Sample 3 [BTN]
    311: {'cc': 0x12, 'ch': 1},  # Deck B Sample 4 [BTN]
    299: {'cc': 0x13, 'ch': 1},  # Deck B loop move knob press [BTN]
    57:  {'cc': 0x14, 'ch': 1},  # Deck B loop move knob turn [ROT_ENC]
    298: {'cc': 0x15, 'ch': 1},  # Deck B loop size knob press [BTN]
    58:  {'cc': 0x16, 'ch': 1},  # Deck B loop size knob turn [ROT_ENC]
    306: {'cc': 0x17, 'ch': 1},  # Deck B loop in [BTN]
    308: {'cc': 0x18, 'ch': 1},  # Deck B loop out [BTN]
    17:  {'cc': 0x45, 'ch': 1},  # Deck B volume [FADER]
    19:  {'cc': 0x45, 'ch': 2},  # Deck C volume [FADER]
    16:  {'cc': 0x45, 'ch': 3},  # Deck D volume [FADER]
    # 263: {'cc': 0x0A, 'ch': 2},  # Deck C play (need to check deck toggle state for this to work)
    # 319: {'cc': 0x0A, 'ch': 3},  # Deck D play (need to check deck toggle state for this to work)
}

# Keys are MIDI control codes, values are an array of ALSA numeric control IDs indexed on the MIDI channel.
ALSA_CONTROL_MAP = {
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

BTN_CCS = [0x01, 0x05, 0x06, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10, 0x11, 0x12, 0x13, 0x15, 0x17, 0x18]
FADER_CCS = [0x04, 0x45]
ROT_ENC_CCS = [0x14, 0x16]


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


def evcode_to_midi(evcode):
    return MIDI_MAP[evcode] if evcode in MIDI_MAP else {}


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

        # Set
        for i in range(full_brightness):
            check_call(['amixer', '-c', 'TraktorKontrolS', 'cset', f'numid={controls[i]}', '31'], stdout=DEVNULL,
                       stderr=STDOUT)
        if partial:
            alsa_values = [2, 4, 5, 7, 9, 10, 12, 14, 15, 17, 19, 21, 22, 24, 26, 28, 29, 31]
            check_call(['amixer', '-c', 'TraktorKontrolS', 'cset', f'numid={controls[full_brightness]}',
                        str(alsa_values[partial - 1])], stdout=DEVNULL, stderr=STDOUT)

    for i in range(full_brightness, 6, 1):
        check_call(['amixer', '-c', 'TraktorKontrolS', 'cset', f'numid={controls[i]}', '0'], stdout=DEVNULL,
                   stderr=STDOUT)


def handle_midi_input(msg, data):
    control = midi_to_alsa_control(msg[0])

    if not control:
        return

    cc = msg[0][1]
    value = msg[0][2]

    if cc in BTN_CCS:
        alsa_val = '31' if value else '0'
        check_call(['amixer', '-c', 'TraktorKontrolS', 'cset', f'numid={control}', alsa_val], stdout=DEVNULL,
                   stderr=STDOUT)

    if cc == 0x46:  # Vu meters
        set_vu_meter(control, value)


def main():
    traktor_s4 = select_controller_device()

    midiin = rtmidi.MidiIn(name='blaxpot')
    inport = midiin.open_virtual_port(name='traktor-s4-mk1-midify')
    inport.set_callback(handle_midi_input)
    midiout = rtmidi.MidiOut(name='blaxpot')
    outport = midiout.open_virtual_port(name='traktor-s4-mk1-midify')

    for event in traktor_s4.read_loop():
        midi = evcode_to_midi(event.code)

        if not midi:
            continue

        if midi['cc'] in FADER_CCS:
            outport.send_message([0xb0 + midi['ch'], midi['cc'], event.value // 32])
        if midi['cc'] in BTN_CCS:
            outport.send_message([0xb0 + midi['ch'], midi['cc'], event.value])

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
