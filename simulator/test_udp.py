import socket
import json

WINDOWS_SELF_IP = "127.0.0.1"
PORT = 9000

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
test_msg = json.dumps({
    "type":"state",
    "width":32,
    "height":16,
    "text":"Test Demo Text",
    "color":[0,255,255],
    "brightness":70,
    "mode":"scroll",
    "version":1
})
sock.sendto(test_msg.encode("utf-8"), (WINDOWS_SELF_IP, PORT))
print("测试报文已发送")
