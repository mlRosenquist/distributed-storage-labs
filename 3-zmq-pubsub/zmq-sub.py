# Weather update client
# Connects SUB socket to tcp://localhost:5556
# Collects weather updates and finds avg temp in zipcode

#
import _thread
import sys
import threading

import zmq

# Socket to talk to server
context = zmq.Context()
socket = context.socket(zmq.SUB)
socket.bind("tcp://*:5556")

def subscribeToTemperatures(zip):
    socket.setsockopt_string(zmq.SUBSCRIBE, zip)

    # Process 10 updates
    total_temp = 0
    for update_nbr in range(10):
        string = socket.recv_string()
        zipcode, temperature, relhumidity = string.split()
        total_temp += int(temperature)
    print(f"Average temperature for zipcode '{zip}' was {total_temp / (update_nbr+1)}F")

# Subscribe to zipcode, default is NYC, 10001
thread1 = threading.Thread(target=subscribeToTemperatures, args=("10001",))
thread2 = threading.Thread(target=subscribeToTemperatures, args=("10002",))

thread1.start()
thread2.start()

thread1.join()
thread2.join()


