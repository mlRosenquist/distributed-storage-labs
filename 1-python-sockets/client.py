import os
import sys
from enum import IntEnum

from socket import *

class MessageType(IntEnum):
    String = 1,
    Binary_1B = 2,
    Binary_2B = 3,
    Binary_3B = 4,
    File = 5

def read_file(filename):
    try:
        with open('./' + filename, 'r') as f:
            data = f.read()
            return data
    except EnvironmentError as e:
        print("Error writing file: {}".format(e))
        return None

while True:
    messageType = MessageType(int(input('1 for string, 2-4 for binary, 5 for file')))

    s = socket(AF_INET, SOCK_STREAM)
    s.connect(("localhost", 9000))
    s.send(messageType.to_bytes(length=1, byteorder=sys.byteorder))

    if(messageType == MessageType.String):
        userInput = input("Write what you want to send to the server")
        s.send(bytes(userInput[0: 4096], 'utf-8'))

    elif(messageType == MessageType.Binary_1B):
        print("Sending random binary_1B to server")
        randomBytes = bytearray(os.urandom(255))
        s.send(randomBytes)

    elif (messageType == MessageType.Binary_2B):
        print("Sending random binary_2B to server")
        randomBytes = bytearray(os.urandom(64000))
        s.send(randomBytes)

    elif (messageType == MessageType.Binary_3B):
        print("Sending random binary_3B to server")
        randomBytes = bytearray(os.urandom(16000000))
        s.send(randomBytes)
    elif (messageType == MessageType.File):
        fileName = input("Enter filename")
        fileExists = os.path.isfile(fileName)
        if(fileExists == True):
            print('File exists')
            s.send(bytes(fileName, 'utf-8'))

            response = s.recv(100).decode('utf-8');
            if(response == "OK"):
                print("Acknowledge received")
                fileData = read_file(fileName)
                s.send(bytes(fileData, 'utf-8'))



    s.close();


