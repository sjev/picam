#!/usr/bin/python

"""
Some test code

led: attached to GPIO4


"""

import time
from gpiozero import LED


led = LED(4)

print("Starting")

for i in range(10):
    time.sleep(0.1)
    led.toggle()
    print(f"cycle {i}")

print("Done")
