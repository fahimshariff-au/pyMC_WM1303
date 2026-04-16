#!/bin/sh
# Auto-generated GPIO reset script for WM1303 CoreCell
# BCM pins: reset=17, power=18, sx1261=5, ad5338r=13
# GPIO base offset: 512

SX1302_RESET_PIN=529
SX1302_POWER_EN_PIN=530
SX1261_RESET_PIN=517
AD5338R_RESET_PIN=525

WAIT_GPIO() {
    sleep 0.1
}

init() {
    for pin in ${SX1302_RESET_PIN} ${SX1261_RESET_PIN} ${SX1302_POWER_EN_PIN} ${AD5338R_RESET_PIN}; do
        echo "${pin}" > /sys/class/gpio/export 2>/dev/null || true; WAIT_GPIO
        echo "out" > /sys/class/gpio/gpio${pin}/direction; WAIT_GPIO
    done
}

reset() {
    echo "CoreCell power enable through GPIO${SX1302_POWER_EN_PIN} (BCM18)..."
    echo "1" > /sys/class/gpio/gpio${SX1302_POWER_EN_PIN}/value; WAIT_GPIO

    echo "CoreCell reset through GPIO${SX1302_RESET_PIN} (BCM17)..."
    echo "1" > /sys/class/gpio/gpio${SX1302_RESET_PIN}/value; WAIT_GPIO
    echo "0" > /sys/class/gpio/gpio${SX1302_RESET_PIN}/value; WAIT_GPIO

    echo "SX1261 reset through GPIO${SX1261_RESET_PIN} (BCM5)..."
    echo "0" > /sys/class/gpio/gpio${SX1261_RESET_PIN}/value; WAIT_GPIO
    echo "1" > /sys/class/gpio/gpio${SX1261_RESET_PIN}/value; WAIT_GPIO

    echo "AD5338R reset through GPIO${AD5338R_RESET_PIN} (BCM13)..."
    echo "0" > /sys/class/gpio/gpio${AD5338R_RESET_PIN}/value; WAIT_GPIO
    echo "1" > /sys/class/gpio/gpio${AD5338R_RESET_PIN}/value; WAIT_GPIO
}

term() {
    for pin in ${SX1302_RESET_PIN} ${SX1261_RESET_PIN} ${SX1302_POWER_EN_PIN} ${AD5338R_RESET_PIN}; do
        if [ -d /sys/class/gpio/gpio${pin} ]; then
            echo "${pin}" > /sys/class/gpio/unexport 2>/dev/null || true; WAIT_GPIO
        fi
    done
}

case "$1" in
    start)
        term
        init
        reset
        sleep 1
        ;;
    stop)
        reset
        term
        ;;
    *)
        echo "Usage: $0 {start|stop}"
        exit 1
        ;;
esac
exit 0
