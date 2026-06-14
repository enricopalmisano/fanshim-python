#!/usr/bin/env python3
from fanshim import FanShim
import RPi.GPIO as GPIO
import colorsys
import psutil
import argparse
import time
import signal
import sys
import subprocess  # Utilizzato per reimpostare la modalità del pin
from rpi_hardware_pwm import HardwarePWM  # Libreria Hardware PWM

parser = argparse.ArgumentParser()
# PARAMETRI DELLE SOGLIE DI TEMPERATURA
parser.add_argument('--temp-min', type=float, default=58.0, help='Temperature in C for start of gradual ramp (default: 50.0)')
parser.add_argument('--temp-step1', type=float, default=68.0, help='Temperature in C for first direct step (default: 60.0)')
parser.add_argument('--temp-step2', type=float, default=74.0, help='Temperature in C for second direct step (default: 70.0)')
parser.add_argument('--temp-max', type=float, default=80.0, help='Temperature in C for maximum step / 100 percent duty (default: 80.0)')

# PARAMETRI DEI LIVELLI DI POTENZA (DUTY CYCLE)
parser.add_argument('--min-pwm', type=float, default=13.0, help='Minimum fan duty cycle in percent (0-100)')
parser.add_argument('--duty-ramp-max', type=float, default=20.0, help='Maximum duty cycle for the gradual ramp range (default: 20.0)')
parser.add_argument('--duty-step1', type=float, default=50.0, help='Duty cycle in percent for first step (default: 50.0)')
parser.add_argument('--duty-step2', type=float, default=80.0, help='Duty cycle in percent for second step (default: 80.0)')
parser.add_argument('--max-pwm', type=float, default=100.0, help='Maximum fan duty cycle in percent (0-100)')

# PARAMETRI DI SISTEMA E TIMING
parser.add_argument('--pwm-frequency', type=float, default=25000.0, help='Fan PWM frequency in Hz')
parser.add_argument('--delay', type=float, default=2.0, help='Delay, in seconds, between temperature readings')
parser.add_argument('--cooldown-delay', type=float, default=60.0, help='Time in seconds to wait before dropping to min-pwm when temp is below temp-min (default: 60.0)')
parser.add_argument('--preempt', action='store_true', default=False, help='Set fan to max duty while CPU frequency is maxed')
parser.add_argument('--max-duty-step', type=float, default=0.1, help='Maximum PWM duty change per loop iteration in quiet zone, in percent')
parser.add_argument('--hot-duty-step', type=float, default=5.0, help='Maximum PWM duty change per loop iteration in hot zone, in percent (default: 5.0)')
parser.add_argument('--duty-deadband', type=float, default=0.5, help='Ignore target duty changes smaller than this percent')
parser.add_argument('--temp-alpha', type=float, default=0.30, help='Temperature smoothing factor from 0 to 1')
parser.add_argument('--verbose', action='store_true', default=False, help='Output temp and fan speed messages')
parser.add_argument('--noled', action='store_true', default=False, help='Disable LED control')
parser.add_argument('--brightness', type=float, default=255.0, help='LED brightness, from 0 to 255')
parser.add_argument('--extended-colours', action='store_true', default=False, help='Extend LED colours outside normal temp range')
parser.add_argument('--startup-boost-duty', type=float, default=80.0, help='Startup kick duty cycle in percent (0-100)')
parser.add_argument('--startup-boost-seconds', type=float, default=3.0, help='Duration of startup kick, in seconds')

args = parser.parse_args()


def clamp(value, low, high):
    return max(low, min(high, value))


def validate_args():
    if args.pwm_frequency <= 0:
        print('Error: --pwm-frequency must be greater than 0')
        sys.exit(1)

    # Validazione di sicurezza delle soglie di temperatura (devono essere in ordine crescente)
    if not (args.temp_min < args.temp_step1 < args.temp_step2 < args.temp_max):
        print('Error: Temperatures must be in increasing order: temp-min < temp-step1 < temp-step2 < temp-max')
        sys.exit(1)

    args.min_pwm = clamp(args.min_pwm, 0.0, 100.0)
    args.duty_ramp_max = clamp(args.duty_ramp_max, args.min_pwm, 100.0)
    args.duty_step1 = clamp(args.duty_step1, 0.0, 100.0)
    args.duty_step2 = clamp(args.duty_step2, 0.0, 100.0)
    args.max_pwm = clamp(args.max_pwm, 0.0, 100.0)

    if args.min_pwm > args.max_pwm:
        print('Error: --min-pwm cannot be greater than --max-pwm')
        sys.exit(1)

    args.brightness = clamp(args.brightness, 0.0, 255.0)
    args.startup_boost_duty = clamp(args.startup_boost_duty, 0.0, 100.0)

    if args.startup_boost_seconds < 0:
        print('Error: --startup-boost-seconds cannot be negative')
        sys.exit(1)

    if args.max_duty_step < 0:
        print('Error: --max-duty-step cannot be negative')
        sys.exit(1)

    if args.hot_duty_step < 0:
        print('Error: --hot-duty-step cannot be negative')
        sys.exit(1)

    if args.duty_deadband < 0:
        print('Error: --duty-deadband cannot be negative')
        sys.exit(1)

    if args.temp_alpha < 0 or args.temp_alpha > 1:
        print('Error: --temp-alpha must be between 0 and 1')
        sys.exit(1)

    if args.cooldown_delay < 0:
        print('Error: --cooldown-delay cannot be negative')
        sys.exit(1)


validate_args()

# 1. Inizializzazione FanShim (imposta erroneamente il GPIO 18 come GPIO.OUT)
fanshim = FanShim(disable_button=True, disable_led=args.noled)

# 2. Risoluzione conflitto: Ripristiniamo in modo sicuro il GPIO 18 in modalità ALT5 (a5)
try:
    subprocess.run(["pinctrl", "set", "18", "a5"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
except (FileNotFoundError, subprocess.CalledProcessError):
    try:
        subprocess.run(["raspi-gpio", "set", "18", "a5"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("Warning: Impossible to set pin 18 to ALT5 automatically.")

# 3. Inizializzazione Hardware PWM (canale 0 sul GPIO 18)
pwm = HardwarePWM(pwm_channel=0, hz=args.pwm_frequency)
current_duty = args.min_pwm
is_fast = False
filtered_temp = None
min_temp = 30.0
max_temp = 85.0
temp_below_min_time = None  # Variabile per tracciare il tempo sotto la soglia minima
cooldown_start_duty = None  # Variabile per memorizzare la potenza all'inizio del cooldown


def clean_exit(signum, frame):
    try:
        pwm.stop()
    finally:
        if not args.noled:
            fanshim.set_light(0, 0, 0)
        sys.exit(0)


def get_cpu_temp():
    try:
        temps = psutil.sensors_temperatures()
        for sensor in ['cpu-thermal', 'cpu_thermal']:
            if sensor in temps and len(temps[sensor]) > 0:
                return temps[sensor][0].current
    except Exception:
        pass
    print('Warning: Unable to get CPU temperature! (Using fallback 0.0)')
    return 0.0


def get_cpu_freq():
    try:
        freq = psutil.cpu_freq()
        if freq is not None and hasattr(freq, 'current') and hasattr(freq, 'max'):
            return freq
    except Exception:
        pass
    
    class DummyFreq:
        current = 600.0
        max = 1500.0
    return DummyFreq()


# LOGICA DINAMICA BASATA SUI PARAMETRI DI INGRESSO
def temp_to_duty(temp):
    if temp >= args.temp_max:
        return args.max_pwm  # Applica la potenza massima (100% di default)
    elif temp >= args.temp_step2:
        return args.duty_step2  # Applica lo step 2 (80% di default)
    elif temp >= args.temp_step1:
        return args.duty_step1  # Applica lo step 1 (50% di default)
    elif temp >= args.temp_min:
        # Calcolo graduale (rampa lineare) tra temp-min e lo step 1.
        # Sale dal minimo fino al valore limite della rampa (duty-ramp-max, default: 20.0%)
        temp_range_min = args.temp_min
        temp_range_max = args.temp_step1
        duty_range_min = args.min_pwm
        duty_range_max = args.duty_ramp_max

        ratio = (temp - temp_range_min) / (temp_range_max - temp_range_min)
        ratio = clamp(ratio, 0.0, 1.0)
        return duty_range_min + ratio * (duty_range_max - duty_range_min)
    else:
        return args.min_pwm


def step_towards_target(current, target, max_step):
    if max_step == 0:
        return current

    if target > current:
        return min(target, current + max_step)

    return max(target, current - max_step)


def update_led_temperature(temp):
    temp = float(temp)
    # Luminosita dinamica: minima a temp-min, massima a temp-max.
    min_brightness_ratio = 0.20
    if temp <= args.temp_min:
        dynamic_brightness = args.brightness * min_brightness_ratio
    elif temp >= args.temp_max:
        dynamic_brightness = args.brightness
    else:
        brightness_ratio = (temp - args.temp_min) / (args.temp_max - args.temp_min)
        brightness_ratio = clamp(brightness_ratio, 0.0, 1.0)
        dynamic_brightness = args.brightness * (
            min_brightness_ratio + (1.0 - min_brightness_ratio) * brightness_ratio
        )

    brightness_scale = dynamic_brightness / 255.0

    if temp >= args.temp_max:
        # Rosso intenso alla soglia massima.
        base_r, base_g, base_b = (255, 0, 0)
    elif temp >= args.temp_step2:
        # Arcobaleno ciclico nella fascia alta di temperatura.
        rainbow = [
            (255, 0, 0),
            (255, 127, 0),
            (255, 255, 0),
            (0, 255, 0),
            (0, 0, 255),
            (75, 0, 130),
            (148, 0, 211),
        ]
        palette_index = int(time.time() * 4.0) % len(rainbow)
        base_r, base_g, base_b = rainbow[palette_index]
    elif temp >= args.temp_step1:
        # Arancione stabile al raggiungimento di temp-step1.
        base_r, base_g, base_b = (255, 165, 0)
    elif temp < args.temp_min:
        # Verde puro sotto la temperatura minima.
        hue = 120.0 / 360.0
        base_r, base_g, base_b = [int(c * 255.0) for c in colorsys.hsv_to_rgb(hue, 1.0, 1.0)]
    else:
        # Sfumatura da verde a arancione tra temp-min e temp-step1.
        temp_ratio = (temp - args.temp_min) / (args.temp_step1 - args.temp_min)
        temp_ratio = clamp(temp_ratio, 0.0, 1.0)
        hue = (120.0 - (90.0 * temp_ratio)) / 360.0
        base_r, base_g, base_b = [int(c * 255.0) for c in colorsys.hsv_to_rgb(hue, 1.0, 1.0)]

    r = int(clamp(base_r * brightness_scale, 0.0, 255.0))
    g = int(clamp(base_g * brightness_scale, 0.0, 255.0))
    b = int(clamp(base_b * brightness_scale, 0.0, 255.0))
    fanshim.set_light(r, g, b)


def apply_startup_boost():
    global current_duty

    pwm.start(0.0)
    if args.startup_boost_seconds > 0 and args.startup_boost_duty > args.min_pwm:
        if args.verbose:
            print(
                'Startup boost: applying {:0.1f}% for {:0.2f}s (min duty {:0.1f}%)'.format(
                    args.startup_boost_duty,
                    args.startup_boost_seconds,
                    args.min_pwm
                )
            )
        pwm.change_duty_cycle(args.startup_boost_duty)
        time.sleep(args.startup_boost_seconds)
    elif args.verbose:
        print(
            'Startup boost: skipped (boost {:0.1f}%, min {:0.1f}%, seconds {:0.2f})'.format(
                args.startup_boost_duty,
                args.min_pwm,
                args.startup_boost_seconds
            )
        )

    # CORREZIONE FISICA: Invece di tagliare istantaneamente a min_pwm, inizializziamo current_duty a 100%
    # e lasciamo che la rampa automatica del ciclo principale faccia scendere la ventola in modo graduale.
    current_duty = args.startup_boost_duty
    if args.verbose:
        print('Startup duty initialized to {:0.1f}% (gradual cooldown ramp will follow)'.format(current_duty))


signal.signal(signal.SIGTERM, clean_exit)
apply_startup_boost()

try:
    while True:
        temp = get_cpu_temp()
        freq = get_cpu_freq()

        if filtered_temp is None:
            filtered_temp = temp
        else:
            filtered_temp = (args.temp_alpha * temp) + ((1.0 - args.temp_alpha) * filtered_temp)

        was_fast = is_fast
        is_fast = (int(freq.current) == int(freq.max))

        # GESTIONE DEL RITARDO DI DISCESA SOTTO LA TEMPERATURA MINIMA (ISTERESI)
        if filtered_temp < args.temp_min:
            if temp_below_min_time is None:
                # Avvia il conteggio del tempo (in secondi)
                temp_below_min_time = time.time()
                # Memorizziamo la potenza della ventola nell'istante esatto di inizio del cooldown
                cooldown_start_duty = current_duty
                if args.verbose:
                    print("Temperature dropped below {:.1f}C. Cooldown timer started (from {:.1f}%).".format(args.temp_min, cooldown_start_duty))
            
            # Se siamo dentro la finestra di tempo impostata (es. 60 secondi)
            if time.time() - temp_below_min_time < args.cooldown_delay:
                # Se la potenza di partenza era superiore al limite della rampa (es. 20.0%)
                if cooldown_start_duty > args.duty_ramp_max:
                    duty = args.duty_ramp_max
                else:
                    # Se era già inferiore (es. 8.0%), mantiene quel valore per non causare sbalzi inutili
                    duty = cooldown_start_duty
            else:
                # Se è rimasta stabilmente fredda per oltre un minuto continuo, scendiamo al minimo (8.0% o 10.0%)
                duty = args.min_pwm
        else:
            # Se la temperatura risale sopra la soglia minima, resettiamo il timer di sicurezza
            temp_below_min_time = None
            cooldown_start_duty = None
            duty = temp_to_duty(filtered_temp)

        if args.preempt and is_fast and was_fast:
            duty = args.max_pwm

        duty = clamp(duty, args.min_pwm, args.max_pwm)
        if abs(duty - current_duty) < args.duty_deadband:
            duty = current_duty

        # RILEVAMENTO DELLA VELOCITÀ DI RAMPA (DOLCE, RAPIDA O COOLDOWN)
        if filtered_temp >= args.temp_step1:
            # Sopra lo step 1 (zona calda), usiamo la rampa rapida (5% a ciclo)
            step_size = args.hot_duty_step
        elif filtered_temp < args.temp_min:
            # Sotto la temperatura minima (zona di cooldown)
            if current_duty > args.duty_ramp_max:
                # Se stiamo scendendo dal boost iniziale (che è molto alto), usiamo la rampa decisa (5% a ciclo)
                step_size = args.hot_duty_step
            else:
                # Una volta vicini o sotto il massimo di rampa, scendiamo con l'intermedio (2.0% a ciclo)
                step_size = 2.0
        else:
            # Nella rampa graduale tra temp-min e temp-step1, la rampa rimane dolcissima (0.1% a ciclo)
            step_size = args.max_duty_step

        # LOGICA ASIMMETRICA DI ACCELERAZIONE/DECELERAZIONE DI SICUREZZA
        # Se stiamo rallentando (decelerando la ventola), limitiamo lo step di discesa a massimo il 2.0%
        # per consentire al motore di rallentare per inerzia senza generare tensioni anomale (back-EMF)
        if duty < current_duty:
            actual_step = min(step_size, 2.0)
        else:
            actual_step = step_size

        # Applichiamo lo step effettivo calcolato verso il target
        duty = step_towards_target(current_duty, duty, actual_step)

        if abs(duty - current_duty) >= 0.05:
            pwm.change_duty_cycle(duty)
            current_duty = duty

        if not args.noled:
            update_led_temperature(temp)

        if args.verbose:
            timer_status = ""
            if temp_below_min_time is not None:
                elapsed = time.time() - temp_below_min_time
                timer_status = " [Timer: {:0.1f}s/{:0.1f}s]".format(elapsed, args.cooldown_delay)
            
            print(
                'Current: {:05.02f}C Filtered: {:05.02f}C Freq: {: 5.02f}GHz Duty: {:05.1f}%{}'.format(
                    temp,
                    filtered_temp,
                    freq.current / 1000.0,
                    current_duty,
                    timer_status
                )
            )

        time.sleep(args.delay)
except KeyboardInterrupt:
    clean_exit(None, None)