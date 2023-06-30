import zmq
from multiprocessing import Pool, freeze_support
import dill
import sys
import codecs

NUM_WORKERS = int(sys.argv[1])
DISPATCHER_URL = sys.argv[2]

# Set up the ZMQ context and socket
context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.connect(f"{DISPATCHER_URL}")

def serialize(obj) -> str:
    return codecs.encode(dill.dumps(obj), "base64").decode()

def deserialize(obj: str):
    return dill.loads(codecs.decode(obj.encode(), "base64"))

def execute_function(task_payload):
    task_id = task_payload[0]
    func = task_payload[1]
    args = task_payload[2]
    res = deserialize(func)(args)
    out = {
        'type': 'Res',
        'task_id': task_id,
        'res': res
    }
    socket.send(dill.dumps(out))

def worker_loop():
    # pool = Pool(NUM_WORKERS)
    while True:
        socket.send(dill.dumps({'type': "Available"}))
        message = dill.loads(socket.recv())
        print(message)
        if 'task' in message and message['task'] != 'None':
            print(message['task'])
            execute_function(message['task'])
            # pool.apply_async(execute_function, (message['task']))

if __name__ == '__main__':
    worker_loop()
