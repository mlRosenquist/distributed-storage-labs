import os
import sys

from enum import Enum
from socket import *

class MessageType(Enum):
    String = '1',
    Binary = '2'

while True:
    messageType: MessageType = input('1 for string, 2 for binary')

    if(messageType == '1'):
        type = 1

        userInput = input("Write what you want to send to the server")
        s = socket(AF_INET, SOCK_STREAM)
        s.connect(("localhost", 9000))
        s.send(type.to_bytes(length=1, byteorder=sys.byteorder))

        s.send(bytes(userInput[0: 4096], 'utf-8'))
        s.close()

    elif(messageType == '2'):
        userInput = print("Sending random binary to server")
        type = 2

        randomBytes = bytearray(os.urandom(1000000))
        s = socket(AF_INET, SOCK_STREAM)
        s.connect(("localhost", 9000))

        s.send(type.to_bytes(length=1, byteorder=sys.byteorder))
        s.send(randomBytes)
        s.close()


