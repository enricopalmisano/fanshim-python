# led.py

Basic demonstration of Fan Shim's RGB LED. Cycles around the circumference of the Hue/Saturation/Value colourspace.

# button.py

Demonstrates usage of button press, release and hold handlers.

# toggle.py

Demonstrates toggling the fan on and off with the button.

# manual.py

A barebones demonstration of how to control Fan SHIM manually.

Since a Python script writing a GPIO pin and exiting can have unpredictable effects, this example shows how you might craft a "service" that runs continuously and ensures the Fan's GPIO pin is asserted either on/off, and that the LED is continuously driven.

# manual-duty.py

Manual hardware PWM fan speed control for noise testing and calibration.

This script lets you set duty cycle directly, change frequency interactively, and listen to fan behavior at each level.

Run interactive mode:

```
python3 ./manual-duty.py
```

Run fixed duty mode:

```
python3 ./manual-duty.py --duty 35 --frequency 25000
```

In interactive mode:

* type `0..100` to set duty directly
* type `+` or `-` to change by `--step`
* type `f <freq>` to change PWM frequency live (example: `f 25000`)
* type `q` to quit

Notes:

* This script uses `rpi_hardware_pwm` (PWM channel 0 on GPIO 18).
* It attempts to restore pin 18 to ALT5 (`pinctrl` or `raspi-gpio`) after FanShim initialization.
* If your fan needs spin-up help, tune `--boost-duty` and `--boost-seconds`.

# automatic.py

Complete example for monitoring temperature and automatic fan control.

* A long press on the button will toggle automatic mode off/on
* A short press - when automatic is off - will toggle the fan

The LED will fade between green (cool) to red (hot) as the Pi's temperature changes.

The script supports these arguments:

* `--on-threshold N` the temperature at which to turn the fan on, in degrees C (default 65)
* `--off-threshold N` the temperature at which to turn the fan off, in degrees C (default 55)
* `--delay N` the delay between subsequent temperature readings, in seconds (default 2)
* `--preempt` preemptively kick in the fan when the CPU frequency is raised (default off)
* `--brightness` the brightness (value of HSV) of the LED (0-255, default 255)

Deprecated arguments

* `--threshold N` the temperature at which the fan should turn on, in degrees C (default 55)
* `--hysteresis N` the change in temperature needed to trigger a fan state change, in degrees C (default 5)

You can use systemd or crontab to run this example as a fan controller service on your Pi.

To use systemd, just run:

```
sudo ./install-service.sh
```

You can then stop the fan service with:

```
sudo systemctl stop pimoroni-fanshim.service
```

If you need to change the threshold, hysteresis or delay you can add them as arguments to the installer:

```
sudo ./install-service.sh --on-threshold 65 --off-threshold 55 --delay 2
```

To enable CPU-frequency based control:

```
sudo ./install-service.sh --on-threshold 65 --off-threshold 55 --delay 2 --preempt
```

You can also add `--noled` to disable LED control and/or `--nobutton` to disable button input.

# automatic_always_run.py

Hardware PWM temperature controller with hybrid step logic, smoothing, and cooldown hysteresis.

Unlike `automatic.py` (on/off), this script maps temperature to duty cycle with:

* gradual ramp in the low-temperature range
* direct thermal steps in hot ranges
* startup boost for reliable fan spin-up
* cooldown timer before dropping to minimum duty

Button input is disabled in this script by design.

The script supports these arguments:

* `--temp-min N` temperature where gradual ramp starts (default 58)
* `--temp-step1 N` first direct step temperature (default 68)
* `--temp-step2 N` second direct step temperature (default 74)
* `--temp-max N` maximum step temperature (default 80)
* `--min-pwm N` minimum duty cycle (default 5)
* `--duty-ramp-max N` max duty used in gradual ramp range (default 20)
* `--duty-step1 N` duty for first thermal step (default 50)
* `--duty-step2 N` duty for second thermal step (default 80)
* `--max-pwm N` maximum duty (default 100)
* `--pwm-frequency N` PWM frequency in Hz (default 25000)
* `--cooldown-delay N` delay before dropping to minimum duty when temp is below temp-min (default 60)
* `--max-duty-step N` smooth duty step in quiet ramp zone (default 0.1)
* `--hot-duty-step N` faster duty step in hot zone (default 5.0)
* `--duty-deadband N` ignore very small duty changes (default 0.5)
* `--temp-alpha N` temperature smoothing factor (0..1, default 0.30)
* `--startup-boost-duty N` startup kick duty cycle in percent (default 100)
* `--startup-boost-seconds N` startup kick duration in seconds (default 3.0)
* `--startup-ramp-interval N` delay between startup ramp-down steps in seconds (default 0.1)
* `--delay N` delay between temperature readings, in seconds (default 2)
* `--preempt` set fan to max duty while CPU frequency is maxed (default off)
* `--brightness` LED brightness (0-255, default 255)
* `--noled` disable LED control
* `--extended-colours` extend LED colour range below/above normal temp range

To run it directly:

```
sudo $(which python3) ./automatic_always_run.py --verbose
```

Suggested profiles:

* Balanced and quiet:
	* `--temp-min 55 --temp-step1 65 --temp-step2 72 --temp-max 80`
* Ultra-quiet:
	* `--temp-min 58 --temp-step1 68 --temp-step2 74 --temp-max 80`

To install this variant as a separate service, run:

```
sudo ./install-service-always.sh
```

You can tune startup kick from installer too:

```
sudo ./install-service-always.sh --startup-boost-duty 100 --startup-boost-seconds 2

# Slower startup ramp-down (smoother but longer)
sudo ./install-service-always.sh --startup-ramp-interval 0.15
```

The installer creates `pimoroni-fanshim-always.service` and automatically disables/stops
the legacy `pimoroni-fanshim.service` if it is active.
