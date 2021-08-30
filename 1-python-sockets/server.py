import _thread, sys, random, string
from socket import *

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
    messageType = int.from_bytes(messageTypeBytes, byteorder=sys.byteorder)

    data = c.recv(1000000)
    if(messageType == 1):
        print('String data received')
        print('Message: {}'.format(data, 'utf-8'))
    elif(messageType == 2):
        print('Binary data received')
        write_file(data, 'hello.txt')
    c.close()

s = socket(AF_INET, SOCK_STREAM)
s.bind(("", 9000))
s.listen(5)
while True:
    c,a = s.accept()
    _thread.start_new_thread(handleConnection, (c,a,))



