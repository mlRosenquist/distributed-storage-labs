import _thread, sys, random, string
from enum import IntEnum
from socket import *

class MessageType(IntEnum):
    String = 1,
    Binary_1B = 2,
    Binary_2B = 3,
    Binary_3B = 4,
    File = 5

def write_file(data, filename=None):
    """
    Write the given data to a local file with the given filename
    :param data: A bytes object that stores the file contents
    :param filename: The file name. If not given, a random string is generated
    :return: The file name of the newly written file, or None if there was an error
    """
    if not filename:
        # Generate random filename
        filename_length = 8
        filename = ''.join([random.SystemRandom().choice(string.ascii_letters +
        string.digits) for n in range(filename_length)])
        # Add '.bin' extension
        filename += ".bin"
    try:
        # Open filename for writing binary content ('wb')
        # note: when a file is opened using the 'with' statement
        # it is closed automatically when the scope ends
        with open('./' + filename, 'wb') as f:
            f.write(data)
    except EnvironmentError as e:
        print("Error writing file: {}".format(e))
        return None
    return filename


def handleConnection(c: socket, a):
    print('Received connection from {}'.format(a))
    messageTypeBytes = c.recv(1)
    messageType = MessageType(int.from_bytes(messageTypeBytes, byteorder=sys.byteorder))

    if(messageType == MessageType.String):
        data = c.recv(1000000)
        print('String data received')
        print('Message: {}'.format(data, 'utf-8'))
    elif(messageType == MessageType.Binary_1B):
        print('Binary_1B data received')
        data = c.recv(255)
        if (len(data) == 255):
            write_file(data, 'binary_1B.txt')
    elif (messageType == MessageType.Binary_2B):
        print('Binary_2B data received')
        data = c.recv(64000)
        if (len(data) == 64000):
            write_file(data, 'binary_2B.txt')
    elif (messageType == MessageType.Binary_3B):
        print('Binary_3B data received')
        data = c.recv(16000000)
        if(len(data) == 16000000):
            write_file(data, 'binary_3B.txt')
    elif (messageType == MessageType.File):
        print('File is to be received')
        fileName = c.recv(100).decode('utf-8')
        c.send(bytes('OK', 'utf-8'))
        data = c.recv(16000000)
        write_file(data, "server_"+fileName)

    c.close()

s = socket(AF_INET, SOCK_STREAM)
s.bind(("", 9000))
s.listen(5)
while True:
    c,a = s.accept()
    _thread.start_new_thread(handleConnection, (c,a,))



