@echo off
cd "C:\Program Files\mosquitto"

start "" mosquitto -c "C:\Program Files\mosquitto\mosquitto_a.conf"
start "" mosquitto -c "C:\Program Files\mosquitto\mosquitto_b.conf"

exit