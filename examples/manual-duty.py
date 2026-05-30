#!/usr/bin/env python3
from fanshim import FanShim
import RPi.GPIO as GPIO
import argparse
import signal
import sys
import time
import subprocess
from rpi_hardware_pwm import HardwarePWM  # Libreria Hardware PWM

parser = argparse.ArgumentParser(description='Manual Hardware PWM duty and frequency control for Fan SHIM')
parser.add_argument('--frequency', type=float, default=25000.0, help='PWM frequency in Hz (default: 25000)')
parser.add_argument('--duty', type=float, default=None, help='Fixed duty cycle 0-100. If omitted, starts interactive mode')
parser.add_argument('--step', type=float, default=5.0, help='Step size for +/- in interactive mode (default: 5)')
parser.add_argument('--boost-duty', type=float, default=100.0, help='Startup boost duty when moving from 0 to >0 (default: 100)')
# Impostato il default di avvio a 3.0 secondi per superare l'attrito iniziale
parser.add_argument('--boost-seconds', type=float, default=3.0, help='Startup boost duration in seconds (default: 3.0)')
parser.add_argument('--noled', action='store_true', default=False, help='Disable LED output')

args = parser.parse_args()


def clamp(value, low, high):
    return max(low, min(high, value))


def validate_args():
    if args.frequency <= 0:
        print('Error: --frequency must be greater than 0')
        sys.exit(1)

    args.step = max(0.1, args.step)
    args.boost_duty = clamp(args.boost_duty, 0.0, 100.0)

    if args.boost_seconds < 0:
        print('Error: --boost-seconds cannot be negative')
        sys.exit(1)

    if args.duty is not None:
        args.duty = clamp(args.duty, 0.0, 100.0)


validate_args()

# 1. Inizializzazione FanShim (imposta erroneamente il GPIO 18 in modalità GPIO.OUT classica)
fanshim = FanShim(disable_button=True, disable_led=args.noled)

# 2. Risoluzione conflitto: Ripristiniamo in modo sicuro il GPIO 18 in modalità ALT5 (a5)
try:
    subprocess.run(["pinctrl", "set", "18", "a5"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
except (FileNotFoundError, subprocess.CalledProcessError):
    try:
        subprocess.run(["raspi-gpio", "set", "18", "a5"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("Warning: Impossible to set pin 18 to ALT5 automatically.")

current_duty = 0.0
current_frequency = args.frequency


# 3. Classe per la gestione dell'Hardware PWM
class HardwarePwmBackend:
    def __init__(self, frequency):
        # Utilizza il canale PWM0 nativo del GPIO 18
        self._pwm = HardwarePWM(pwm_channel=0, hz=frequency)

    def start(self):
        self._pwm.start(0.0)

    def set_duty(self, duty):
        self._pwm.change_duty_cycle(duty)

    def change_frequency(self, frequency):
        self._pwm.change_frequency(frequency)

    def stop(self):
        self._pwm.stop()


pwm_backend = HardwarePwmBackend(args.frequency)


def set_led_from_duty(duty):
    if args.noled:
        return

    # Green at low duty, red at high duty.
    ratio = clamp(duty / 100.0, 0.0, 1.0)
    r = int(255 * ratio)
    g = int(255 * (1.0 - ratio))
    fanshim.set_light(r, g, 0)


def apply_duty(new_duty):
    global current_duty
    new_duty = clamp(new_duty, 0.0, 100.0)

    # Alcune ventole hanno bisogno di un boost per partire da ferme
    if current_duty <= 0.0 and new_duty > 0.0 and args.boost_seconds > 0 and args.boost_duty > new_duty:
        pwm_backend.set_duty(args.boost_duty)
        time.sleep(args.boost_seconds)

    pwm_backend.set_duty(new_duty)
    current_duty = new_duty
    set_led_from_duty(current_duty)
    print('Duty set to {:05.1f}%'.format(current_duty))


def clean_exit(signum=None, frame=None):
    try:
        pwm_backend.stop()
    finally:
        # Non modifichiamo più il pin 18 con RPi.GPIO per non invalidare la configurazione hardware PWM
        if not args.noled:
            fanshim.set_light(0, 0, 0)
        sys.exit(0)


signal.signal(signal.SIGTERM, clean_exit)
pwm_backend.start()

if args.duty is not None:
    apply_duty(args.duty)
    print('Fixed mode active. Press Ctrl+C to stop.')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        clean_exit()

print('manual-duty.py interactive mode')
print('Enter a value from 0 to 100 to set duty directly.')
print('Enter + or - to increase/decrease by --step.')
print("Enter f <frequency> to change frequency (e.g. 'f 40' or 'f 25000').")
print('Enter q to quit.')

try:
    while True:
        # Prompt dinamico che mostra costantemente lo stato del PWM
        prompt = f'duty:{current_duty:.1f}% freq:{current_frequency:.0f}Hz > '
        raw = input(prompt).strip().lower()
        if raw in ('q', 'quit', 'exit'):
            break
        if raw == '+':
            apply_duty(current_duty + args.step)
            continue
        if raw == '-':
            apply_duty(current_duty - args.step)
            continue
            
        # Rileva se l'utente desidera cambiare la frequenza di clock
        if raw.startswith('f '):
            try:
                new_freq = float(raw[2:].strip())
                if new_freq <= 0:
                    print('Error: Frequency must be greater than 0')
                    continue
                pwm_backend.change_frequency(new_freq)
                current_frequency = new_freq
                print(f'Frequency set to {current_frequency:.0f} Hz')
            except ValueError:
                print("Invalid frequency format. Use 'f <number>', e.g. 'f 25000'")
            continue

        try:
            apply_duty(float(raw))
        except ValueError:
            print("Invalid input. Use number 0-100, +, -, 'f <freq>', or 'q' to quit.")
except KeyboardInterrupt:
    pass

clean_exit()