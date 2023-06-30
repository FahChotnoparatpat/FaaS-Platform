import threading
from multiprocessing import Pool, freeze_support
import zmq
import dill
import codecs
import sys

NUM_WORKERS = int(sys.argv[1])
DISPATCHER_URL = sys.argv[2]

# Set up the ZMQ context and socket
context = zmq.Context()
dealer = context.socket(zmq.DEALER)
dealer.connect(f"{DISPATCHER_URL}")

def deserialize(obj: str):
    return dill.loads(codecs.decode(obj.encode(), "base64"))

def execute_function(task_payload):
    task_id = task_payload[0]
    func = task_payload[1]
    args = task_payload[2]
    res = deserialize(func)(args)
    out = ['Res', task_id, res]
    dealer.send(dill.dumps(out))
    print(out)

def worker_loop():
    pool = Pool(NUM_WORKERS)
    while True:
        dealer.send(dill.dumps(["Available"]))
        message = dill.loads(dealer.recv())
        if message:
            execute_function(message)
            # pool.apply_async(execute_function, message)

if __name__ == '__main__':
    worker_loop()
