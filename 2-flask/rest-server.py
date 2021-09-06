import base64
import json
import sqlite3
import string
import random

from flask import Flask, make_response, g, request, send_file, jsonify

app = Flask(__name__)


def get_db():
    # Connect to the sqlite DB at 'files.db' and store the connection in 'g.db'
    # Re-use the connection if it already exists
    if 'db' not in g:
        g.db = sqlite3.connect(
            'files.db',
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        # Enable casting Row objects to Python dictionaries
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    # Close the DB connection and remove it from the 'g' object
    db = g.pop('db', None)
    if db is not None:
        db.close()
    app = Flask(__name__)
    # Close the DB connection after serving a request
    app.teardown_appcontext(close_db)


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


@app.route('/')
def hello():
    return make_response({'message': 'Hello World!'})


@app.route('/files', methods=['POST'])
def add_files():
    # Parse the request body as JSON and convert to a Python dictionary
    payload = request.get_json()
    filename = payload.get('filename')
    content_type = payload.get('content_type')
    # Decode the file contents and calculate its original size
    file_data = base64.b64decode(payload.get('contents_b64'))
    size = len(file_data)
    # Store the file locally with a random generated name
    blob_name = write_file(file_data)
    # Insert the File record in the DB
    db = get_db()
    cursor = db.execute(
        "INSERT INTO `file` (`filename`, `size`, `content_type`, `blob_name`) VALUES (?,?,?,?)",
        (filename, size, content_type, blob_name)
    )

    db.commit()
    # Return the ID of the new file record with HTTP 201 (Created) status code
    return make_response({"id": cursor.lastrowid}, 201)


#

@app.route('/files', methods=['GET'])
def list_files():
    # Query the database for all files
    db = get_db()
    cursor = db.execute("SELECT * FROM `file`")
    if not cursor:
        return make_response({"message": "Error connecting to the database"}, 500)
    files = cursor.fetchall()
    # Convert files from sqlite3.Row object (which is not JSON-encodable) to
    # a standard Python dictionary simply by casting
    files = [dict(f) for f in files]
    return make_response({"files": files})


# @app.route('/files/<int:file_id>', methods=['GET'])
# def download_file(file_id):
#     db = get_db()
#     cursor = db.execute("SELECT * FROM `file` WHERE `id`=?", [file_id])
#
#     if not cursor:
#         return make_response({"message": "Error connecting to the database"}, 500)
#     f = cursor.fetchone()
#     # Convert to a Python dictionary
#     f = dict(f)
#     print("File requested: {}".format(f))
#     # Return the binary file contents with the proper Content-Type header.
#     return send_file(f['blob_name'], mimetype=f['content_type'])

@app.route('/files/<int:file_id>', methods=['DELETE'])
def delete_file(file_id):
    db = get_db()
    cursor = db.execute("DELETE FROM `file` WHERE `id`=?", [file_id])
    db.commit()
    if not cursor:
        return make_response({"message": "Error connecting to the database"}, 500)

    print("File delete requested: {}".format(file_id))
    # Return the binary file contents with the proper Content-Type header.
    return make_response({"Deleted id": file_id}, 201)


@app.route('/files/<int:file_id>', methods=['HEAD'])
def retrieve_metadata(file_id):
    db = get_db()
    cursor = db.execute("SELECT * FROM `file` WHERE `id`=?", [file_id])

    if not cursor:
        return make_response({"message": "Error connecting to the database"}, 500)
    f = cursor.fetchone()
    # Convert to a Python dictionary
    f = dict(f)

    print("File requested: {}".format(f))
    return make_response(jsonify(f), 200)





app.run(host="localhost", port=80)
