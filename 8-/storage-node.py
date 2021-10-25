"""
Aarhus University - Distributed Storage course - Lab 4

Storage Node
"""
import zmq
import messages_pb2

import sys
import os
import random
import string

import rlnc

from utils import random_string, write_file, is_raspberry_pi

MAX_CHUNKS_PER_FILE = 10

# Read the folder name where chunks should be stored from the first program argument
# (or use the current folder if none was given)
data_folder = sys.argv[1] if len(sys.argv) > 1 else "./"
if data_folder != "./":
    # Try to create the folder  
    try:
        os.mkdir('./'+data_folder)
    except FileExistsError as _:
        # OK, the folder exists 
        pass
print("Data folder: %s" % data_folder)

# Check whether the node has an id. If it doesn't, generate one and save it to disk.
try:
    with open(data_folder+'/.id', "r") as id_file:
        node_id = id_file.read()
        print("ID read from file: %s" % node_id)

except FileNotFoundError:
    # This is OK, this must be the first time the node was started
    node_id = random_string(8)
    # Save it to file for the next start
    with open(data_folder+'/.id', "w") as id_file:
        id_file.write(node_id)
        print("New ID generated and saved to file: %s" % node_id)

if False:
    # On the Raspberry Pi: ask the user to input the last segment of the server IP address
    server_address = input("Server address: 192.168.0.___ ")
    pull_address = "tcp://192.168.0."+server_address+":5557"
    sender_address = "tcp://192.168.0."+server_address+":5558"
    subscriber_address = "tcp://192.168.0."+server_address+":5559"
    repair_subscriber_address = "tcp://192.168.0."+server_address+":5560"
    repair_sender_address = "tcp://192.168.0."+server_address+":5561"
else:
    # On the local computer: use localhost
    pull_address = "tcp://localhost:5557"
    push_address = "tcp://localhost:5558"
    subscriber_address = "tcp://localhost:5559"
    repair_subscriber_address = "tcp://localhost:5560"
    repair_sender_address = "tcp://localhost:5561"
    

context = zmq.Context()
# Socket to receive Store Chunk messages from the controller
receiver = context.socket(zmq.PULL)
receiver.connect(pull_address)
print("Listening on "+ pull_address)
# Socket to send results to the controller
sender = context.socket(zmq.PUSH)
sender.connect(push_address)
# Socket to receive Get Chunk messages from the controller
subscriber = context.socket(zmq.SUB)
subscriber.connect(subscriber_address)
# Receive every message (empty subscription)
subscriber.setsockopt(zmq.SUBSCRIBE, b'')

# Socket to receive Repair request messages from the controller
repair_subscriber = context.socket(zmq.SUB)
repair_subscriber.connect(repair_subscriber_address)
# Receive messages destined for all nodes
repair_subscriber.setsockopt(zmq.SUBSCRIBE, b'all_nodes')
# Receive messages destined for this node
repair_subscriber.setsockopt(zmq.SUBSCRIBE, node_id.encode('UTF-8'))
# Socket to send repair results to the controller
repair_sender = context.socket(zmq.PUSH)
repair_sender.connect(repair_sender_address)


# Use a Poller to monitor three sockets at the same time
poller = zmq.Poller()
poller.register(receiver, zmq.POLLIN)
poller.register(subscriber, zmq.POLLIN)
poller.register(repair_subscriber, zmq.POLLIN)


while True:
    try:
        # Poll all sockets
        socks = dict(poller.poll())
    except KeyboardInterrupt:
        break
    pass

    # At this point one or multiple sockets may have received a message

    if receiver in socks:
        # Incoming message on the 'receiver' socket where we get tasks to store a chunk
        msg = receiver.recv_multipart()
        # Parse the Protobuf message from the first frame
        task = messages_pb2.storedata_request()
        task.ParseFromString(msg[0])

        # The data starts with the second frame, iterate and store all frames
        for i in range(0, len(msg) - 1):
            data = msg[1 + i]
            print('Chunk to save: %s, size: %d bytes' % (task.filename + "." + str(i), len(data)))
            # Store the chunk with the given filename
            chunk_local_path = data_folder + '/' + task.filename + "." + str(i)
            write_file(data, chunk_local_path)
            print("Chunk saved to %s" % chunk_local_path)

        # Send response (just the file name)
        sender.send_string(task.filename)

    if subscriber in socks:
        # Incoming message on the 'subscriber' socket where we get retrieve requests
        msg = subscriber.recv()
        
        # Parse the Protobuf message from the first frame
        task = messages_pb2.getdata_request()
        task.ParseFromString(msg)

        filename = task.filename
        print("Data chunk request: %s" % filename)

        # Try to load all fragments with this name
        # First frame is the filename
        frames = [bytes(filename, 'utf-8')]
        # Subsequent frames will contain the chunks' data
        for i in range(0, MAX_CHUNKS_PER_FILE):
            try:
                with open(data_folder + '/' + filename + "." + str(i), "rb") as in_file:
                    print("Found chunk %s, sending it back" % filename)
                    # Add chunk as a new frame
                    frames.append(in_file.read())
            except FileNotFoundError:
                # This is OK here
                break
        # Only send a result if at least one chunk was found
        if (len(frames) > 1):
            sender.send_multipart(frames)

    if repair_subscriber in socks:
        # Incoming message on the 'repair_subscriber' socket

        # Parse the multi-part message
        msg = repair_subscriber.recv_multipart()

        # The topic is sent a frame 0
        #topic = str(msg[0])
        
        # Parse the header from frame 1. This is used to distinguish between
        # different types of requests
        header = messages_pb2.header()
        header.ParseFromString(msg[1])

        # Parse the actual message based on the header
        if header.request_type == messages_pb2.FRAGMENT_STATUS_REQ:
            # Fragment Status requests
            task = messages_pb2.fragment_status_request()
            task.ParseFromString(msg[2])

            chunk_name = task.fragment_name
            chunk_count = 0

            # Check whether the chunks are on the disk
            for i in range(0, MAX_CHUNKS_PER_FILE):
                chunk_found = os.path.exists(data_folder + '/' + chunk_name + "." + str(i)) and \
                              os.path.isfile(data_folder + '/' + chunk_name + "." + str(i))

            if chunk_found == True:
                print("Status request for fragment: %s - Found" % chunk_name)
                chunk_count += 1
            else:
                print("Status request for fragment: %s - Not found" % chunk_name)

            # Send the response
            response = messages_pb2.fragment_status_response()
            response.fragment_name = chunk_name
            response.is_present = chunk_count > 0
            response.node_id = node_id
            response.count = chunk_count

            repair_sender.send(response.SerializeToString())

        elif header.request_type == messages_pb2.FRAGMENT_DATA_REQ:
            # Fragment data request - same implementation as serving normal data
            # requests, except for the different socket the response is sent on
            # and the incoming request's format.
            # This is currently only used by Reed-Solomon, which stores a single
            # chunk per storage node.
            task = messages_pb2.getdata_request()
            task.ParseFromString(msg[2])

            filename = task.filename
            print("Data chunk request: %s" % filename)
            # Try to load all fragments with this name
            # First frame of the response is the filename
            frames = [bytes(filename, 'utf-8')]
            # Subsequent frames will contain the file data
            for i in range(0, MAX_CHUNKS_PER_FILE):
                try:
                    with open(data_folder + '/' + filename + "." + str(i), "rb") as in_file:
                        print("Found chunk %s, sending it back" % filename)
                        # Add chunk as a new frame
                        frames.append(in_file.read())
                except FileNotFoundError:
                    # This is OK here
                    break
            # Only send a result if at least one chunk was found
            if (len(frames) > 1):
                repair_sender.send_multipart(frames)

        elif header.request_type == messages_pb2.STORE_FRAGMENT_DATA_REQ:
            # Fragment store request
            task = messages_pb2.storedata_request()
            task.ParseFromString(msg[2])
            chunk_name = task.filename
            chunks_saved = 0

            # Iterate over stored chunks, replacing missing ones
            for i in range(0, MAX_CHUNKS_PER_FILE):
                chunk_local_path = data_folder + '/' + chunk_name + "." + str(i)
                if os.path.exists(chunk_local_path) and os.path.isfile(chunk_local_path):
                    continue  # chunk already here
                # Chunk missing
                # The data starts with the third frame
                data = msg[3 + chunks_saved]
                # Store the chunk with the given filename
                write_file(data, chunk_local_path)
                chunks_saved += 1
                print("Chunk saved to %s" % chunk_local_path)
                # Stop when all frames have been consumed (all repair fragments have been saved)
                if chunks_saved + 3 >= len(msg):
                    break

            # Send response (just the file name)
            repair_sender.send_string(task.filename)

        elif header.request_type == messages_pb2.RECODE_FRAGMENTS_REQ:
            # Recode fragment data request, specific to RLNC repairs
            task = messages_pb2.recode_fragments_request()
            task.ParseFromString(msg[2])
            fragment_name = task.fragment_name
            symbol_count = task.symbol_count
            output_fragment_count = task.output_fragment_count
            print("Recoded fragment request: %s" % fragment_name)

            # Try to load the requested files from the local file system
            fragment_count = 0
            fragments = []

            for i in range(0, MAX_CHUNKS_PER_FILE):
                try:
                    with open(data_folder + '/' + fragment_name + "." + str(i), "rb") as in_file:
                        fragments.append(bytearray(in_file.read()))
                    fragment_count += 1
                except FileNotFoundError:
                    # This is OK here
                    pass
            # If at least one fragment is found, recode and send the result
            if fragment_count > 0:
                recoded_symbols = rlnc.recode(fragments, symbol_count, output_fragment_count)
            print("Fragment found, sending requested recoded symbols")
            repair_sender.send_multipart(recoded_symbols)
        else:
            print("Message type not supported")
#
