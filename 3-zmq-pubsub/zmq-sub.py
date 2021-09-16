# Weather update client
# Connects SUB socket to tcp://localhost:5556
# Collects weather updates and finds avg temp in zipcode

#
import _thread
import sys
import threading
import zmq
from messages_pb2 import weatherupdate

# Socket to talk to server
context = zmq.Context()
socket = context.socket(zmq.SUB)
socket.bind("tcp://*:5556")

def subscribeToTemperatures():
    socket.setsockopt_string(zmq.SUBSCRIBE, "")
    sampleCount = 0
    total_temp = 0
    while True:
        string = socket.recv()

        update: weatherupdate = weatherupdate()
        update.ParseFromString(string)

        if(update.zipcode == 10001):
            total_temp += int(update.temperature)
            sampleCount += 1

        if(sampleCount == 5):
            break

    print(f"Average temperature for zipcode '{10001}' was {total_temp / (sampleCount)}F")

# Subscribe to zipcode, default is NYC, 10001
thread1 = threading.Thread(target=subscribeToTemperatures)
thread1.start()
thread1.join()

#thread2 = threading.Thread(target=subscribeToTemperatures, args=("10002",))
#thread2.start()
#thread2.join()


