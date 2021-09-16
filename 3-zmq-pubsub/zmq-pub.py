# Weather update server
# Binds PUB socket to tcp://*:5556
# Publishes random weather updates
import zmq
from random import randrange
from messages_pb2 import weatherupdate

context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.connect("tcp://localhost:5556")

while True:
    update = weatherupdate()
    update.zipcode = randrange(1, 100000)
    update.temperature = randrange(-80, 135)
    update.relhumidity = randrange(10, 60)
    socket.send(update.SerializeToString())

