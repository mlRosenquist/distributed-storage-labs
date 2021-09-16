import time
import zmq

context = zmq.Context()

# Socket to receive messages on
receiver = context.socket(zmq.PULL)
receiver.bind("tcp://*:5558")

# Wait for start of batch from the ventilator
s = receiver.recv()

# Start our clock now
tstart = time.time()

# Collect 100 results from the workers
for task_nbr in range(100):
    s = receiver.recv()
    print('.')

# Calculate and report duration of batch
tend = time.time()
print(f"Total elapsed time: {(tend-tstart)*1000} msec")
