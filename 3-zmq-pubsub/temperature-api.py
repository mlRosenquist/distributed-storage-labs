import base64
import json
import sqlite3
import string
import random

import zmq

from messages_pb2 import weatherupdate
from flask import Flask, make_response, g, request, send_file, jsonify

app = Flask(__name__)

@app.route('/weatherupdate/<int:zipcode>', methods=['GET'])
def get_weatherupdate(zipcode):
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.bind("tcp://*:5556")
    socket.setsockopt_string(zmq.SUBSCRIBE, "")

    sampleCount = 0
    total_temp = 0
    total_hum = 0
    while True:
        string = socket.recv()

        update: weatherupdate = weatherupdate()
        update.ParseFromString(string)

        if (update.zipcode == 10001):
            total_temp += int(update.temperature)
            total_hum += int(update.relhumidity)
            sampleCount += 1

        if (sampleCount == 5):
            break

    jsonUpdate = {
        "zipcode": zipcode,
        "average_temp": total_temp/5,
        "average_hum": total_hum/5
    }
    return make_response(jsonify(jsonUpdate), 200)

app.run(host="localhost", port=80)