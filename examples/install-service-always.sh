#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
PROJECT_ROOT="$(realpath "$DIR/..")"
DEFAULT_VENV="$PROJECT_ROOT/test-env/bin"
TEMP_MIN=58
TEMP_STEP1=68
TEMP_STEP2=74
TEMP_MAX=80
MIN_PWM=5
DUTY_RAMP_MAX=20
DUTY_STEP1=50
DUTY_STEP2=80
MAX_PWM=100
PWM_FREQUENCY=25000
STARTUP_BOOST_DUTY=100
STARTUP_BOOST_SECONDS=3.0
DELAY=2
COOLDOWN_DELAY=60
PREEMPT="no"
POSITIONAL_ARGS=()
NOLED="no"
BRIGHTNESS=255
EXTCOLOURS="no"
MAX_DUTY_STEP=0.1
HOT_DUTY_STEP=5.0
DUTY_DEADBAND=0.5
TEMP_ALPHA=0.30
PYTHON="python3"
PIP="pip3"
PSUTIL_MIN_VERSION="5.6.7"

SERVICE_PATH=/etc/systemd/system/pimoroni-fanshim-always.service
LEGACY_SERVICE=pimoroni-fanshim.service
ALWAYS_SERVICE=pimoroni-fanshim-always.service

USAGE="sudo ./install-service-always.sh --temp-min <n> --temp-step1 <n> --temp-step2 <n> --temp-max <n> --min-pwm <n> --duty-ramp-max <n> --duty-step1 <n> --duty-step2 <n> --max-pwm <n> --pwm-frequency <n> --startup-boost-duty <n> --startup-boost-seconds <n> --delay <n> --cooldown-delay <n> --max-duty-step <n> --hot-duty-step <n> --duty-deadband <n> --temp-alpha <n> --brightness <n> --venv <python_virtual_environment> (--preempt) (--noled) (--extended-colours)"

# Prefer project-local isolated environment when available.
if [[ -x "$DEFAULT_VENV/python3" && -x "$DEFAULT_VENV/pip3" ]]; then
	PYTHON="$DEFAULT_VENV/python3"
	PIP="$DEFAULT_VENV/pip3"
fi

# Convert Python path to absolute for systemd
PYTHON=$(type -P "$PYTHON")

while [[ $# -gt 0 ]]; do
	K="$1"
	case $K in
	-p|--preempt)
		if [[ "$2" == "yes" || "$2" == "no" ]]; then
			PREEMPT="$2"
			shift
		else
			PREEMPT="yes"
		fi
		shift
		;;
	-l|--noled)
		if [[ "$2" == "yes" || "$2" == "no" ]]; then
			NOLED="$2"
			shift
		else
			NOLED="yes"
		fi
		shift
		;;
	-t|--temp-min)
		TEMP_MIN="$2"
		shift
		shift
		;;
	-1|--temp-step1)
		TEMP_STEP1="$2"
		shift
		shift
		;;
	-2|--temp-step2)
		TEMP_STEP2="$2"
		shift
		shift
		;;
	-T|--temp-max)
		TEMP_MAX="$2"
		shift
		shift
		;;
	-m|--min-pwm)
		MIN_PWM="$2"
		shift
		shift
		;;
	-a|--duty-ramp-max)
		DUTY_RAMP_MAX="$2"
		shift
		shift
		;;
	-A|--duty-step1)
		DUTY_STEP1="$2"
		shift
		shift
		;;
	-B|--duty-step2)
		DUTY_STEP2="$2"
		shift
		shift
		;;
	-M|--max-pwm)
		MAX_PWM="$2"
		shift
		shift
		;;
	-f|--pwm-frequency)
		PWM_FREQUENCY="$2"
		shift
		shift
		;;
	-s|--startup-boost-duty)
		STARTUP_BOOST_DUTY="$2"
		shift
		shift
		;;
	-S|--startup-boost-seconds)
		STARTUP_BOOST_SECONDS="$2"
		shift
		shift
		;;
	-d|--delay)
		DELAY="$2"
		shift
		shift
		;;
	-c|--cooldown-delay)
		COOLDOWN_DELAY="$2"
		shift
		shift
		;;
	-k|--max-duty-step)
		MAX_DUTY_STEP="$2"
		shift
		shift
		;;
	-K|--hot-duty-step)
		HOT_DUTY_STEP="$2"
		shift
		shift
		;;
	-D|--duty-deadband)
		DUTY_DEADBAND="$2"
		shift
		shift
		;;
	-P|--temp-alpha)
		TEMP_ALPHA="$2"
		shift
		shift
		;;
	-r|--brightness)
		BRIGHTNESS="$2"
		shift
		shift
		;;
	--venv)
		VENV="$(realpath ${2%/})/bin"
		PYTHON="$VENV/python3"
		PIP="$VENV/pip3"
		shift
		shift
		;;
	-x|--extended-colours)
		if [[ "$2" == "yes" || "$2" == "no" ]]; then
			EXTCOLOURS="$2"
			shift
		else
			EXTCOLOURS="yes"
		fi
		shift
		;;
	*)
		if [[ $1 == -* ]]; then
			printf "Unrecognised option: $1\n"
			printf "Usage: $USAGE\n"
			exit 1
		fi
		POSITIONAL_ARGS+=("$1")
		shift
	esac
done

if ! ( type -P "$PYTHON" > /dev/null ) ; then
	if [[ "$PYTHON" == "python3" ]]; then
		printf "Fan SHIM controller requires Python 3\n"
		printf "You should run: 'sudo apt install python3'\n"
	else
		printf "Cannot find virtual environment.\n"
		printf "Set to base of virtual environment i.e. <venv>/bin/python3.\n"
	fi
	exit 1
fi

if ! ( type -P "$PIP" > /dev/null ) ; then
	printf "Fan SHIM controller requires Python 3 pip\n"
	if [[ "$PIP" == "pip3" ]]; then
		printf "You should run: 'sudo apt install python3-pip'\n"
	else
		printf "Ensure that your virtual environment has pip3 installed.\n"
	fi
	exit 1
fi

set -- "${POSITIONAL_ARGS[@]}"

EXTRA_ARGS=""

$PYTHON - <<EOF
import sys

try:
	temp_min = float('$TEMP_MIN')
	temp_step1 = float('$TEMP_STEP1')
	temp_step2 = float('$TEMP_STEP2')
	temp_max = float('$TEMP_MAX')
	min_pwm = float('$MIN_PWM')
	duty_ramp_max = float('$DUTY_RAMP_MAX')
	duty_step1 = float('$DUTY_STEP1')
	duty_step2 = float('$DUTY_STEP2')
	max_pwm = float('$MAX_PWM')
	pwm_frequency = float('$PWM_FREQUENCY')
	startup_boost_duty = float('$STARTUP_BOOST_DUTY')
	startup_boost_seconds = float('$STARTUP_BOOST_SECONDS')
	delay = float('$DELAY')
	cooldown_delay = float('$COOLDOWN_DELAY')
	max_duty_step = float('$MAX_DUTY_STEP')
	hot_duty_step = float('$HOT_DUTY_STEP')
	duty_deadband = float('$DUTY_DEADBAND')
	temp_alpha = float('$TEMP_ALPHA')
	brightness = float('$BRIGHTNESS')
except ValueError:
	print('Error: one or more numeric arguments are invalid.')
	sys.exit(1)

if not (temp_min < temp_step1 < temp_step2 < temp_max):
	print('Error: temperatures must satisfy --temp-min < --temp-step1 < --temp-step2 < --temp-max.')
	sys.exit(1)

if min_pwm > max_pwm:
	print('Error: --min-pwm cannot be greater than --max-pwm.')
	sys.exit(1)

if min_pwm < 0 or max_pwm > 100 or duty_ramp_max < min_pwm or duty_ramp_max > 100:
	print('Error: --min-pwm/--max-pwm/--duty-ramp-max are outside allowed range.')
	sys.exit(1)

if duty_step1 < 0 or duty_step1 > 100 or duty_step2 < 0 or duty_step2 > 100:
	print('Error: --duty-step1 and --duty-step2 must be in range 0 to 100.')
	sys.exit(1)

if pwm_frequency <= 0:
	print('Error: --pwm-frequency must be greater than 0.')
	sys.exit(1)

if startup_boost_duty < 0 or startup_boost_duty > 100:
	print('Error: --startup-boost-duty must be in range 0 to 100.')
	sys.exit(1)

if startup_boost_seconds < 0:
	print('Error: --startup-boost-seconds cannot be negative.')
	sys.exit(1)

if delay <= 0:
	print('Error: --delay must be greater than 0.')
	sys.exit(1)

if cooldown_delay < 0:
	print('Error: --cooldown-delay cannot be negative.')
	sys.exit(1)

if max_duty_step < 0 or hot_duty_step < 0:
	print('Error: --max-duty-step and --hot-duty-step cannot be negative.')
	sys.exit(1)

if duty_deadband < 0:
	print('Error: --duty-deadband cannot be negative.')
	sys.exit(1)

if temp_alpha < 0 or temp_alpha > 1:
	print('Error: --temp-alpha must be between 0 and 1.')
	sys.exit(1)

if brightness < 0 or brightness > 255:
	print('Error: --brightness must be between 0 and 255.')
	sys.exit(1)
EOF

if [[ $? -ne 0 ]]; then
	printf "Usage: $USAGE\n"
	exit 1
fi

if [[ "$PREEMPT" == "yes" ]]; then
	EXTRA_ARGS+=' --preempt'
fi

if [[ "$NOLED" == "yes" ]]; then
	EXTRA_ARGS+=' --noled'
fi

if [[ "$EXTCOLOURS" == "yes" ]]; then
	EXTRA_ARGS+=' --extended-colours'
fi

cat << EOF
Setting up with:
Temp Min:         $TEMP_MIN C
Temp Step1:       $TEMP_STEP1 C
Temp Step2:       $TEMP_STEP2 C
Temp Max:         $TEMP_MAX C
Min PWM:          $MIN_PWM %
Duty Ramp Max:    $DUTY_RAMP_MAX %
Duty Step1:       $DUTY_STEP1 %
Duty Step2:       $DUTY_STEP2 %
Max PWM:          $MAX_PWM %
PWM Frequency:    $PWM_FREQUENCY Hz
Startup Boost:    $STARTUP_BOOST_DUTY % for $STARTUP_BOOST_SECONDS s
Delay:            $DELAY seconds
Cooldown Delay:   $COOLDOWN_DELAY seconds
Max Duty Step:    $MAX_DUTY_STEP %
Hot Duty Step:    $HOT_DUTY_STEP %
Duty Deadband:    $DUTY_DEADBAND %
Temp Alpha:       $TEMP_ALPHA
Preempt:          $PREEMPT
Disable LED:      $NOLED
Brightness:       $BRIGHTNESS
Extended Colours: $EXTCOLOURS

To change these options, run:
$USAGE

Or edit: $SERVICE_PATH

EOF

# UNIT_FILE AGGIORNATO E OTTIMIZZATO PER EVITARE RACE CONDITION AL BOOT
read -r -d '' UNIT_FILE << EOF
[Unit]
Description=Fan Shim Always-On PWM Service
After=multi-user.target sound.target udev.target

[Service]
Type=simple
WorkingDirectory=$(pwd)
ExecStartPre=/bin/sleep 5
ExecStart=$PYTHON $(pwd)/automatic_always_run.py --temp-min $TEMP_MIN --temp-step1 $TEMP_STEP1 --temp-step2 $TEMP_STEP2 --temp-max $TEMP_MAX --min-pwm $MIN_PWM --duty-ramp-max $DUTY_RAMP_MAX --duty-step1 $DUTY_STEP1 --duty-step2 $DUTY_STEP2 --max-pwm $MAX_PWM --pwm-frequency $PWM_FREQUENCY --delay $DELAY --cooldown-delay $COOLDOWN_DELAY --max-duty-step $MAX_DUTY_STEP --hot-duty-step $HOT_DUTY_STEP --duty-deadband $DUTY_DEADBAND --temp-alpha $TEMP_ALPHA --startup-boost-duty $STARTUP_BOOST_DUTY --startup-boost-seconds $STARTUP_BOOST_SECONDS --brightness $BRIGHTNESS $EXTRA_ARGS
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

printf "Checking for rpi.gpio >= 0.7.0 (for Pi 4 support)\n"
# Sostituita la dipendenza da pkg_resources con una comparazione di tuple nativa di Python
$PYTHON - <<EOF
import RPi.GPIO as GPIO
import sys
try:
    v = [int(x) for x in GPIO.VERSION.split('.')[:3]]
    if v < [0, 7, 0]:
        sys.exit(1)
except Exception:
    sys.exit(1)
EOF

if [[ $? -ne 0 ]]; then
	printf "Installing rpi.gpio\n"
	$PIP install --upgrade "rpi.gpio>=0.7.0"
else
	printf "rpi.gpio >= 0.7.0 already installed\n"
fi

printf "Checking for Fan SHIM\n"
$PYTHON - > /dev/null 2>&1 <<EOF
import fanshim
EOF

if [[ $? -ne 0 ]]; then
	printf "Installing Fan SHIM\n"
	$PIP install fanshim
else
	printf "Fan SHIM already installed\n"
fi

printf "Checking for psutil >= $PSUTIL_MIN_VERSION\n"
# Sostituita la dipendenza da pkg_resources con una comparazione di tuple nativa di Python
$PYTHON - > /dev/null 2>&1 <<EOF
import sys
import psutil
try:
    v = [int(x) for x in psutil.__version__.split('.')[:3]]
    min_v = [int(x) for x in '$PSUTIL_MIN_VERSION'.split('.')]
    sys.exit(0 if v >= min_v else 1)
except Exception:
    sys.exit(1)
EOF

if [[ $? -ne 0 ]]; then
	printf "Installing psutil\n"
	$PIP install --ignore-installed psutil
else
	printf "psutil >= $PSUTIL_MIN_VERSION already installed\n"
fi

printf "Checking for rpi-hardware-pwm\n"
$PYTHON - > /dev/null 2>&1 <<EOF
import rpi_hardware_pwm
EOF

if [[ $? -ne 0 ]]; then
	printf "Installing rpi-hardware-pwm\n"
	$PIP install rpi-hardware-pwm
else
	printf "rpi-hardware-pwm already installed\n"
fi

if systemctl is-enabled --quiet "$LEGACY_SERVICE"; then
	printf "Disabling legacy service: $LEGACY_SERVICE\n"
	systemctl disable --no-pager "$LEGACY_SERVICE"
fi

if systemctl is-active --quiet "$LEGACY_SERVICE"; then
	printf "Stopping legacy service: $LEGACY_SERVICE\n"
	systemctl stop --no-pager "$LEGACY_SERVICE"
fi

printf "\nInstalling service to: $SERVICE_PATH\n"
echo "$UNIT_FILE" > "$SERVICE_PATH"
systemctl daemon-reload
systemctl enable --no-pager "$ALWAYS_SERVICE"
systemctl restart --no-pager "$ALWAYS_SERVICE"
systemctl status --no-pager "$ALWAYS_SERVICE"