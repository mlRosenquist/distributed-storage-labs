import kodo
import math
import random
import copy  # for deepcopy
from utils import random_string
import messages_pb2
import json

STORAGE_NODES_NUM = 4


def store_file(file_data, max_erasures, subfragments_per_node,
               send_task_socket, response_socket):
    """
    Store a file using RLNC, protecting it against 'max_erasures' unavailable storage nodes.
    Alternatively, protect against a total of 'max_erasures' * 'subfragments_per_node'
    subfragment losses distributed in any way across the nodes
    :param file_data: The file contents to be stored as a Python bytearray
    :param max_erasures: How many storage node failures should the data survive
    :param subfragments_per_node: How many sugfragments are stored per fragment on a node
    :param send_task_socket: A ZMQ PUSH socket to the storage nodes
    :param response_socket: A ZMQ PULL socket where the storage nodes respond
    :return: A list of the coded fragment names, e.g. (c1,c2,c3,c4)
    """
    # Make sure we can realize max_erasures with 4 storage nodes
    assert (max_erasures >= 0)
    assert (max_erasures < STORAGE_NODES_NUM)

    # At least one subfragment per node
    assert (subfragments_per_node > 0)

    # How many coded subfragments (=symbols) will be required to reconstruct the encoded data.

    symbols = (STORAGE_NODES_NUM - max_erasures) * subfragments_per_node
    # The size of one coded subfragment (total size/number of symbols, rounded up)

    symbol_size = math.ceil(len(file_data) / symbols)

    # Kodo RLNC encoder using 2^8 finite field
    field = kodo.FiniteField.binary8
    encoder = kodo.block.Encoder(field)
    encoder.configure(symbols, symbol_size)

    encoder.set_symbols_storage(file_data)

    # Preallocate array for a coded symbol (avoid allocation in a loop)
    symbol = bytearray(encoder.symbol_bytes)

    # Random coefficient generator
    generator = kodo.block.generator.RandomUniform(field)
    generator.configure(encoder.symbols)

    # Preallocate array for coefficients (avoid allocation in a loop)
    coefficients = bytearray(generator.max_coefficients_bytes)

    # Store the generated fragment names
    fragment_names = []

    # Generate several coded subfragments for each Storage Node
    for i in range(STORAGE_NODES_NUM):

        # Generate a random name for them and save
        name = random_string(8)
        fragment_names.append(name)
        # Prepare a multi-frame ZMQ message that includes the
        # fragment name and all subfragments.
        frames = []
        # First frame: a Protobuf STORE DATA message
        task = messages_pb2.storedata_request()
        task.filename = name
        frames.append(task.SerializeToString())

        for j in range(subfragments_per_node):
            # Generate a fresh set of coefficients
            generator.generate(coefficients)
            # Generate a coded symbol with these coefficients
            encoder.encode_symbol(symbol, coefficients)
            # Add to the message frames
            frames.append(coefficients + bytearray(symbol))
        # Send all frames as a single multipart message
        send_task_socket.send_multipart(frames)

    # Wait until we receive a response for every message
    for task_nbr in range(STORAGE_NODES_NUM):
        resp = response_socket.recv_string()
        print('Received: %s' % resp)

    return fragment_names


#


def __decode_file(symbols):
    """
    Decode a file using RLNC decoder and the provided coded symbols.
    The number of symbols must be the same as (STORAGE_NODES_NUM - max_erasures) *
    subfragments_per_node.
    The implementation is almost identical to the Reed-Solomon equivalent function.
    :param symbols: coded symbols that contain both the coefficients and symbol data
    :return: the decoded file data
    """
    # Reconstruct the original data with a decoder
    symbols_num = len(symbols)
    symbol_size = len(symbols[0]['data']) - symbols_num  # subtract the coefficients' size
    decoder = kodo.block.Decoder(kodo.FiniteField.binary8)
    decoder.configure(symbols_num, symbol_size)
    data_out = bytearray(decoder.block_bytes)
    decoder.set_symbols_storage(data_out)

    for symbol in symbols:
        # Separate the coefficients from the symbol data
        coefficients = symbol['data'][:symbols_num]
        symbol_data = symbol['data'][symbols_num:]
        # Feed it to the decoder
        decoder.decode_symbol(symbol_data, coefficients)

    # Check that the decoder successfully reconstructed the file
    if (decoder.is_complete()):
        print("File decoded successfully")
    else:
        print(f"Decoding file failed! Decoder rank {decoder.rank} after {len(symbols)}symbols")
        # In a real system we might add more complex error handling
    return data_out


#


def recode(symbols, symbol_count, output_symbol_count):
    """
    Recode a file using an RLNC recoder and the provided coded symbols.
    The symbols are fed into the recoder where output_symbol_count symbols are created
    by generating new linear combinations.
    Examples of different techiques to recode using Kodo can be found here:
    https://github.com/steinwurf/kodo-python/blob/master/examples/pure_recode_symbol_api.py
    https://github.com/steinwurf/kodo-python/blob/master/examples/pure_recode_payload_api.py
    https://github.com/steinwurf/kodo-python/blob/master/examples/encode_recode_decode_simple.py
    :param symbols: coded symbols that contain both the coefficients and symbol data
    :param symbol_count: number of symbols needed to decode the file
    :param output_symbol_count: number of symbols to create
    :return: the recoded symbols
    """
    symbol_size = len(symbols[0]) - symbol_count  # subtract the coefficients' size
    field = kodo.FiniteField.binary8

    # Set up the recoder
    recoder = kodo.block.Decoder(field)
    recoder.configure(symbol_count, symbol_size)
    recoder_internal_storage = bytearray(recoder.block_bytes)
    recoder.set_symbols_storage(recoder_internal_storage)

    # Random coefficient generator, will be used for the recoded symbols
    generator = kodo.block.generator.RandomUniform(field)
    generator.configure(symbol_count)

    # Allocate buffers for where the recoded symbols (coeffs and data) will be produced
    # Recoding requires 2 coefficient buffers

    recoding_coefficients = bytearray(generator.max_coefficients_bytes)
    coefficients_out = bytearray(generator.max_coefficients_bytes)
    recoded_symbol = bytearray(symbol_size)
    # Feed the provided symbols to the decoder
    for symbol in symbols:
        # Separate the coefficients from the symbol data
        coefficients = symbol[:symbol_count]
        symbol_data = symbol[symbol_count:]
        # Feed it to the recoder
        recoder.decode_symbol(symbol_data, coefficients)

    # Generate new recoded symbols
    output_symbols = []
    for i in range(output_symbol_count):
        # Generate fresh recoding multipliers
        generator.generate_recode(recoding_coefficients, recoder)
        # Perform recoding
        recoder.recode_symbol(recoded_symbol, coefficients_out, recoding_coefficients)
        # Save the new recoded symbol and its coeffs to output_symbols
        output_symbols.append(coefficients_out + recoded_symbol)
    return output_symbols


def get_file(coded_fragments, max_erasures, file_size, data_req_socket, response_socket):
    """
    Implements retrieving a file that is stored with RLNC erasure coding. Only works
    if there are no missing fragments.
    The implementation is similar to the Reed-Solomon equivalent function.
    :param coded_fragments: Names of the coded fragments
    :param max_erasures: Max erasures setting that was used when storing the file
    :param file_size: The original data size.
    :param data_req_socket: A ZMQ SUB socket to request chunks from the storage nodes
    :param response_socket: A ZMQ PULL socket where the storage nodes respond.
    :return: The decoded file
    """
    # We need fragments from 4-max_erasures nodes to reconstruct the file, select this many
    # by randomly removing 'max_erasures' elements from the given chunk names.
    fragnames = copy.deepcopy(coded_fragments)
    for i in range(max_erasures):
        fragnames.remove(random.choice(fragnames))

    # Request the coded fragments in parallel. Nodes return all their subfragments
    for name in fragnames:
        task = messages_pb2.getdata_request()
        task.filename = name
        data_req_socket.send(task.SerializeToString())

    # Receive all chunks and insert them into the symbols array
    symbols = []
    for _ in range(len(fragnames)):
        result = response_socket.recv_multipart()
        for i in range(1, len(result)):
            symbols.append({"data": bytearray(result[i])})
    print("All coded fragments received successfully")

    # Reconstruct the original file data
    file_data = __decode_file(symbols)

    return file_data[:file_size]


def __store_repair_fragments(missing_fragments, partially_missing_fragments,
                             repair_symbols, subfragments_per_node,
                             repair_socket, repair_response_socket):
    '''
    Sends the repaired fragments/subfragments to the appropriate storage nodes
    :param missing fragments: Fragments that are completely missing
    :param partially_missing fragments: Fragments with missing subfragments
    :param repair_symbols: the symbols(subfragments) to store
    :param subfragments_per_node: number of subfragments per fragment
    :param repair_socket: A ZMQ PUB socket to send requests to the storage nodes
    :param repair_response_socket: A ZMQ PULL socket on which the storage nodes respond.
    :return: the number of repaired subfragments
    '''

    number_of_repaired_subfragments = 0

    # 1. Full missing fragments (arbitrary choice to have this first as all repair packets
    # are functionally equivalent)
    for fragment in missing_fragments:
        task = messages_pb2.storedata_request()
        task.filename = fragment["name"]
        header = messages_pb2.header()
        header.request_type = messages_pb2.STORE_FRAGMENT_DATA_REQ

        frames = [fragment["node_id"].encode('UTF-8'),  # Use the node_id as the topic
              header.SerializeToString(),
              task.SerializeToString()]
        for i in range(number_of_repaired_subfragments,
                   number_of_repaired_subfragments + subfragments_per_node):
            frames.append(bytearray(repair_symbols[i]))

    number_of_repaired_subfragments += subfragments_per_node
    repair_socket.send_multipart(frames)

    # Wait until we receive a response for every fragment
    for task_nbr in range(len(missing_fragments)):
        resp = repair_response_socket.recv_string()
        print('Repaired fully missing fragment: %s' % resp)

    # 2. Partially missing fragments
    for fragment in partially_missing_fragments:
        task = messages_pb2.storedata_request()
        task.filename = fragment["name"]

        header = messages_pb2.header()
        header.request_type = messages_pb2.STORE_FRAGMENT_DATA_REQ
        frames = [fragment["node_id"].encode('UTF-8'),  # Use the node_id as the topic
              header.SerializeToString(),
              task.SerializeToString()]
        for i in range(number_of_repaired_subfragments,
                   number_of_repaired_subfragments + fragment["subfragments_lost"]):
            frames.append(bytearray(repair_symbols[i]))

    number_of_repaired_subfragments += fragment["subfragments_lost"]
    repair_socket.send_multipart(frames)

    # Wait until we receive a response for every fragment
    for task_nbr in range(len(partially_missing_fragments)):
        resp = repair_response_socket.recv_string()
        print('Repaired partially missing fragment: %s' % resp)

    return number_of_repaired_subfragments
#



def start_repair_process(files, repair_socket, repair_response_socket):
    """
    Implements the repair process for RLNC-based erasure coding. It receives a list
    of files that are to be checked. For each file, it sends queries to the Storage
    nodes to check how many coded subfragments are stored safely. If it finds a missing
    subfragment, it determines which Storage node was supposed to store it and repairs it.
    Based on how many subfragments are missing, it instructs the storage nodes to send over
    a certain number of recoded subfragments. It then recodes over these creating as many
    subfragments as were missing, sending the appropriate number to each of the nodes.
    :param files: List of files to be checked
    :param repair_socket: A ZMQ PUB socket to send requests to the storage nodes
    :param repair_response_socket: A ZMQ PULL socket on which the storage nodes respond.
    :return: the number of missing subfragments, the number of repaired subfragments
    """

    total_missing_subfragment_count = 0
    total_repaired_subfragment_count = 0

    # Check each file for missing fragments to repair
    for file in files:
        print("Checking file with id: %s" % file["id"])
        # We parse the JSON into a python dictionary
        storage_details = json.loads(file["storage_details"])
        max_erasures = storage_details["max_erasures"]
        subfragments_per_node = storage_details["subfragments_per_node"]
        symbol_count = (STORAGE_NODES_NUM - max_erasures) * subfragments_per_node
        '''
        Iterate over each node's coded subfragments to check what is missing.
        Because this is a distributed system where the central Controller has no knowledge
        of what is stored on each Storage node, we build several lists and sets to get an
        accurate picture. Through these lists and sets we determine:
        - which nodes respond to our queries
        - which nodes have a partially missing fragment (and how many subfragments are
        missing)
        - which nodes have fully lost their fragment
        This information will be key in determining where and how many repaired subfragments
        to send later.
        '''
        nodes = set()  # list of all storage nodes
        nodes_with_fragment = set()  # list of storage nodes with at least partial fragments
        coded_fragments = storage_details["coded_fragments"]  # list of all coded fragments
        missing_fragments = []  # list of coded fragments that are fully missing
        partially_missing_fragments = []  # list of coded fragments that are partially missing
        existing_fragments = []  # list of coded fragments that are at least in part intact
        missing_subfragment_count = 0

        for fragment in coded_fragments:
            fragment_found = False
            task = messages_pb2.fragment_status_request()
            task.fragment_name = fragment
            header = messages_pb2.header()
            header.request_type = messages_pb2.FRAGMENT_STATUS_REQ
            repair_socket.send_multipart([b"all_nodes",
                                          header.SerializeToString(),
                                          task.SerializeToString()])

            # Wait until we receive a response from each node
            for task_nbr in range(STORAGE_NODES_NUM):
                msg = repair_response_socket.recv()
                response = messages_pb2.fragment_status_response()
                response.ParseFromString(msg)

                nodes.add(response.node_id)  # Build a set of nodes
                if response.is_present == True:
                    nodes_with_fragment.add(response.node_id)
                    existing_fragments.append(fragment)
                    fragment_found = True

                    # Check for partially missing fragments
                    if response.count < subfragments_per_node:
                        subfragments_lost = subfragments_per_node - response.count
                        print("Partial (%s of %s) RLNC fragments lost for %s from node %s" % (
                            subfragments_lost, subfragments_per_node, fragment, response.node_id))
                        # Register it as a partial fragment loss
                        partially_missing_fragments.append({"name": fragment,
                                                            "subfragments_lost":
                                                                subfragments_lost,
                                                            "node_id": response.node_id})
                        missing_subfragment_count += subfragments_lost
                    else:
                        print("Fragment %s OK" % fragment)
                # Perform the actual repair, if necessary
                if missing_subfragment_count > 0:
                    # Check that enough fragments still remain to be able to reconstruct the data
                    if missing_subfragment_count > max_erasures * subfragments_per_node:
                        print("Too many lost fragments: %s. Unable to repair file. " % missing_subfragment_count)
                        continue  # Move onto the next file
                    # Retrieve sufficient fragments and recode
                    for fragment in coded_fragments:
                        task = messages_pb2.recode_fragments_request()
                        task.fragment_name = fragment
                        task.symbol_count = symbol_count
                        # Request as many fragments as the node originally had stored.
                        # Quite wasteful, surely we can do better
                        task.output_fragment_count = subfragments_per_node
                        header = messages_pb2.header()
                        header.request_type = messages_pb2.RECODE_FRAGMENTS_REQ
                        repair_socket.send_multipart([b"all_nodes",
                                                      header.SerializeToString(),
                                                      task.SerializeToString()])
                    # Wait until we receive a response from each node that has at least one subfragment
                    recoded_symbols = []
                    for task_nbr in range(len(nodes_with_fragment)):
                        response = repair_response_socket.recv_multipart()
                        for i in range(len(response)):
                            recoded_symbols.append(bytearray(response[i]))
                    # Recreate sufficient repair symbols by recoding over the retrieved symbols again
                    repair_symbols = recode(recoded_symbols, symbol_count, missing_subfragment_count)
                    print("Retrieved %s recoded symbols from Storage nodes. Created %s new recoded symbols" % (
                        len(recoded_symbols), len(repair_symbols)))
                    # Send the repair symbols to the storage nodes based on the lists we previously built
                    repaired_subfragment_count = __store_repair_fragments(missing_fragments,
                                                                          partially_missing_fragments,
                                                                          repair_symbols,
                                                                          subfragments_per_node,
                                                                          repair_socket,
                                                                          repair_response_socket)

                # If neither node responded with a positive message, the fragment is fully missing
            if fragment_found == False:
                print("RLNC all parts of fragment %s missing" % fragment)
                # Register it as a full lost fragment, we cannot yet determine which node had it
                missing_fragments.append({"name": fragment, "node_id": "?"})
                missing_subfragment_count += subfragments_per_node

    # We can now determine which nodes had a full missing fragment by subtracting the two
    # sets from each other.
    nodes_without_fragment = list(nodes.difference(nodes_with_fragment))
    assert (len(nodes_without_fragment) == len(missing_fragments))

    # Assign each full missing fragment to a node that has not fragments stored on it
    i = 0
    for node in nodes_without_fragment:
        missing_fragments[i]["node_id"] = node
        i += 1
        # TO BE DONE: placeholder for the recode on the Controller
        # Add the per-file counters to the total tally
    total_repaired_subfragment_count += repaired_subfragment_count
    total_missing_subfragment_count += missing_subfragment_count

    return total_missing_subfragment_count, total_repaired_subfragment_count
