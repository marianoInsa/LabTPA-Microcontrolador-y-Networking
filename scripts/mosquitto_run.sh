#!/bin/bash

cd /etc/mosquitto/ || exit

mosquitto -c "/etc/mosquitto/mosquitto_a.conf" &
mosquitto -c "/etc/mosquitto/mosquitto_b.conf" &

exit 0