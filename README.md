# Fan Shim for Raspberry Pi

[![Build Status](https://travis-ci.com/pimoroni/fanshim-python.svg?branch=master)](https://travis-ci.com/pimoroni/fanshim-python)
[![Coverage Status](https://coveralls.io/repos/github/pimoroni/fanshim-python/badge.svg?branch=master)](https://coveralls.io/github/pimoroni/fanshim-python?branch=master)
[![PyPi Package](https://img.shields.io/pypi/v/fanshim.svg)](https://pypi.python.org/pypi/fanshim)
[![Python Versions](https://img.shields.io/pypi/pyversions/fanshim.svg)](https://pypi.python.org/pypi/fanshim)

# Installing

Stable library from PyPi:

* Just run `sudo pip install fanshim`

Note for virtualenv/development installs:

* If you install this project with `pip install -e library`, `RPi.GPIO` is not installed automatically.
* Install it explicitly with `pip install RPi.GPIO` (or install your distro package, for example `python3-rpi.gpio`).
* The `examples/automatic.py` script also requires `psutil`, install it with `pip install psutil`.

Latest/development library from GitHub:

* `apt install git python3-pip`
* `git clone https://github.com/pimoroni/fanshim-python`
* `cd fanshim-python`
* `sudo ./install.sh`

Hardware PWM controller (recommended for low noise):

* Use `examples/automatic_always_run.py` for the optimized controller with native hardware PWM, smooth ramps and thermal step logic.
* Use `examples/manual-duty.py` to test fixed duty/frequency combinations and identify the quietest stable operating point for your fan.

Requirements for hardware PWM on GPIO 18:

* In `/boot/firmware/config.txt` (or `/boot/config.txt` on older systems), set:
    * `dtparam=audio=off`
    * `dtoverlay=pwm`
* Reboot after editing boot config.
* Install Python dependency: `pip install rpi-hardware-pwm`

Run the controller (from active virtualenv):

* `sudo $(which python3) ./examples/automatic_always_run.py --verbose`

Profiles suggested for Raspberry Pi 4 via SSH/VS Code:

* Balanced and quiet (recommended):
    * `--temp-min 55 --temp-step1 65 --temp-step2 72 --temp-max 80`
* Ultra-quiet:
    * `--temp-min 58 --temp-step1 68 --temp-step2 74 --temp-max 80`

Why these values:

* During typical SSH/VS Code usage, CPU often stays around 45-53C, so the fan can remain at minimum duty for most of the time.
* Delaying the jump to higher steps reduces sudden noisy transitions while keeping a strong safety barrier at 80C (thermal throttling threshold).

Example commands:

* Balanced and quiet:
    * `sudo $(which python3) ./examples/automatic_always_run.py --verbose --temp-min 55 --temp-step1 65 --temp-step2 72 --temp-max 80`
* Ultra-quiet:
    * `sudo $(which python3) ./examples/automatic_always_run.py --verbose --temp-min 58 --temp-step1 68 --temp-step2 74 --temp-max 80`

Install as a service with the new installer:

* Balanced and quiet:
    * `sudo ./examples/install-service-always.sh --temp-min 55 --temp-step1 65 --temp-step2 72 --temp-max 80 --min-pwm 5 --duty-ramp-max 20 --duty-step1 50 --duty-step2 80 --max-pwm 100 --pwm-frequency 25000 --delay 2 --cooldown-delay 60 --max-duty-step 0.1 --hot-duty-step 5.0 --duty-deadband 0.5 --temp-alpha 0.30 --startup-boost-duty 100 --startup-boost-seconds 3`
* Ultra-quiet:
    * `sudo ./examples/install-service-always.sh --temp-min 58 --temp-step1 68 --temp-step2 74 --temp-max 80 --min-pwm 5 --duty-ramp-max 20 --duty-step1 50 --duty-step2 80 --max-pwm 100 --pwm-frequency 25000 --delay 2 --cooldown-delay 60 --max-duty-step 0.1 --hot-duty-step 5.0 --duty-deadband 0.5 --temp-alpha 0.30 --startup-boost-duty 100 --startup-boost-seconds 3`

# Reference

You should first set up an instance of the `FANShim` class, eg:

```python
from fanshim import FanShim
fanshim = FanShim()
```

## Fan

Turn the fan on with:

```python
fanshim.set_fan(True)
```

Turn it off with:

```python
fanshim.set_fan(False)
```

You can also toggle the fan with:

```python
fanshim.toggle_fan()
```

You can check the status of the fan with:

```python
fanshim.get_fan() # returns 1 for 'on', 0 for 'off'
```

## LED

Fan Shim includes one RGB APA-102 LED.

Set it to any colour with:

```python
fanshim.set_light(r, g, b)
```

Arguments r, g and b should be numbers between 0 and 255 that describe the colour you want.

For example, full red:

```
fanshim.set_light(255, 0, 0)
```

## Button

Fan Shim includes a button, you can bind actions to press, release and hold events.

Do something when the button is pressed:

```python
@fanshim.on_press()
def button_pressed():
    print("The button has been pressed!")
```

Or when it has been released:

```python
@fanshim.on_release()
def button_released(was_held):
    print("The button has been pressed!")
```

Or when it's been pressed long enough to trigger a hold:

```python
fanshim.set_hold_time(2.0)

@fanshim.on_hold()
def button_held():
    print("The button was held for 2 seconds")
```

The function you bind to `on_release()` is passed a `was_held` parameter,
this lets you know if the button was held down for longer than the configured
hold time. If you want to bind an action to "press" and another to "hold" you
should check this flag and perform your action in the `on_release()` handler:

```python
@fanshim.on_release()
def button_released(was_held):
    if was_held:
        print("Long press!")
    else:
        print("Short press!")
```

To configure the amount of time the button should be held (in seconds), use:

```python
fanshim.set_hold_time(number_of_seconds)
```

If you need to stop Fan Shim from polling the button, use:

```python
fanshim.stop_polling()
```

You can start it again with:

```python
fanshim.start_polling()
```

# Alternate Software

* Fan SHIM in C, using WiringPi - https://github.com/flobernd/raspi-fanshim
* Fan SHIM in C++, using libgpiod - https://github.com/daviehh/fanshim-cpp

