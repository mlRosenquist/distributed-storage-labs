import time
import zmq

context = zmq.Context()

# Socket to receive tasks from the ventilator
receiver = context.socket(zmq.PULL)
receiver.connect("tcp://localhost:5557")

# Socket to send results to the sink
sender = context.socket(zmq.PUSH)
sender.connect("tcp://localhost:5558")

# Process tasks forever
while True:
    s = receiver.recv()
    # Simple progress indicator for the viewer
    print('.')
    # Simulate do the work by waiting the received amount of time
    time.sleep(int(s)*0.001)
    # Send results to sink (just an empty message now)
    sender.send(b'')
