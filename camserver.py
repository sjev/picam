#!/usr/bin/env python3

# Web streaming example
# Source code from the official PiCamera package
# http://picamera.readthedocs.io/en/latest/recipes2.html#web-streaming

# Serving on port 8000

import io
from gpiozero import LED
import picamera
import logging
import socketserver
from threading import Condition
from http import server
import time

logging.basicConfig(level=logging.INFO)

PORT = 8000
VIDEO_WIDTH = 640  # 1640
VIDEO_HEIGHT = 480  # 1232

ROTATE = True  # rotate image 90 deg

RESOLUTION = (
    f"{VIDEO_HEIGHT}x{VIDEO_WIDTH}" if ROTATE else f"{VIDEO_WIDTH}x{VIDEO_HEIGHT}"
)

img_width, img_height = (
    (VIDEO_WIDTH, VIDEO_HEIGHT) if not ROTATE else (VIDEO_HEIGHT, VIDEO_WIDTH)
)


PAGE = f"""\
<html>
<head>
<title>Raspberry Pi - Chicken Cam!</title>
</head>
<body>
<center><h1>All the chickens in the house?</h1></center>
<center><img src="stream.mjpg" ></center>
</body>
</html>
"""

led = LED(4)
led.off()

is_streaming = False


class StreamingOutput(object):
    def __init__(self):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = Condition()

    def write(self, buf):
        if buf.startswith(b"\xff\xd8"):
            # New frame, copy the existing buffer's content and notify all
            # clients it's available
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(buf)


class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):

        global is_streaming

        if self.path == "/":
            self.send_response(301)
            self.send_header("Location", "/index.html")
            self.end_headers()
        elif self.path == "/index.html":
            content = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == "/frame.jpg":
            logging.info("Requesting frame")
            logging.info("Switching led ON")
            led.on()

            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.end_headers()

            camera.wait_recording(0.1)
            buffer = io.BytesIO()
            camera.capture(buffer, use_video_port=True, format="jpeg")

            self.wfile.write(buffer.getvalue())

            if not is_streaming:
                logging.info("Switching led OFF")
                led.off()

        elif self.path == "/stream.mjpg":

            is_streaming = True
            logging.info("Switching led ON")
            led.on()

            self.send_response(200)
            self.send_header("Age", 0)
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Pragma", "no-cache")
            self.send_header(
                "Content-Type", "multipart/x-mixed-replace; boundary=FRAME"
            )
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b"--FRAME\r\n")
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b"\r\n")
            except Exception as e:
                logging.warning(
                    "Removed streaming client %s: %s", self.client_address, str(e)
                )
            finally:
                is_streaming = False
                logging.info("Switching led OFF")
                led.off()
        else:
            self.send_error(404)
            self.end_headers()


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


with picamera.PiCamera(resolution=RESOLUTION, framerate=24) as camera:
    output = StreamingOutput()

    # Uncomment the next line to change your Pi's Camera rotation (in degrees)
    if ROTATE:
        camera.rotation = -90

    camera.start_recording(output, format="mjpeg")
    try:
        address = ("", PORT)
        server = StreamingServer(address, StreamingHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print("stopped.")

    finally:
        camera.stop_recording()
