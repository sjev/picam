#!/usr/bin/env python3

from picamera2 import Picamera2, MappedArray
from http import server
import socketserver
import threading
import io
from PIL import Image

# Configuration
PORT = 8000


class StreamingOutput:
    def __init__(self, camera):
        self.camera = camera
        self.frame = None
        self.lock = threading.Lock()

    def capture_frame(self):
        with self.lock:
            buffer = io.BytesIO()
            image = self.camera.capture_array()
            pil_image = Image.fromarray(image)
            # Convert to RGB to avoid RGBA issue
            if pil_image.mode != "RGB":
                pil_image = pil_image.convert("RGB")
            pil_image.save(buffer, format="JPEG")
            buffer.seek(0)
            self.frame = buffer.getvalue()

    def get_frame(self):
        with self.lock:
            return self.frame


class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/stream.mjpg":
            self.stream_video()
        else:
            self.send_error(404)
            self.end_headers()

    def stream_video(self):
        self.send_response(200)
        self.send_header("Age", 0)
        self.send_header("Cache-Control", "no-cache, private")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=FRAME")
        self.end_headers()

        try:
            while True:
                output.capture_frame()
                frame = output.get_frame()
                self.wfile.write(b"--FRAME\r\n")
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", len(frame))
                self.end_headers()
                self.wfile.write(frame)
                self.wfile.write(b"\r\n")
        except Exception as e:
            print(f"Streaming client disconnected: {e}")


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    camera = Picamera2()
    camera.configure(camera.create_video_configuration(main={"size": (640, 480)}))
    camera.start()

    output = StreamingOutput(camera)

    try:
        address = ("", PORT)
        server = StreamingServer(address, StreamingHandler)
        print(f"Server running on port {PORT}")
        server.serve_forever()
    except KeyboardInterrupt:
        print("Server stopped.")
    finally:
        camera.close()
