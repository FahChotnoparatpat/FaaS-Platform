import redis
from multiprocessing import Pool, freeze_support
import threading
import redis_client
import dill
import argparse
import zmq
import codecs
import sys

# Connect to Redis to listen for tasks
redis_db = redis.Redis(host='localhost', port=6379, db=0)
sub = redis_db.pubsub()
sub.subscribe('tasks')

workers = [] # in-memory data store of workers
tasks = [] # in-memory data store of tasks

# Create a ZMQ context and socket for communication with workers
context = zmq.Context()
socket = context.socket(zmq.ROUTER)

if sys.argv[2] == 'push':
    socket.bind("tcp://*:5555")
elif sys.argv[2] == 'pull':
    socket = context.socket(zmq.REP)
    socket.bind("tcp://*:5555")

def serialize(obj) -> str:
    return codecs.encode(dill.dumps(obj), "base64").decode()

def deserialize(obj: str):
    return dill.loads(codecs.decode(obj.encode(), "base64"))

def execute_function(task_id, func, args):
    res = deserialize(func)(args)
    redis_client.update_task_status(task_id, "COMPLETED")
    redis_client.update_task_result(task_id, res)

def local_dispatcher(num_workers):
    global sub
    pool = Pool(num_workers)
    while True:
        for message in sub.listen():
            task_id = message['data']
            if task_id is not None and task_id != 1:
                task_payload = redis_client.get_task(task_id)
                redis_client.update_task_status(task_id, 'RUNNING')
                function_data = task_payload["function_data"]
                pool.apply_async(execute_function, (task_id, function_data["function_body"], task_payload["args"]))

def push_dispatcher():
    global workers, socket
    threading.Thread(target=(listen_to_pub), kwargs=({"mode":"push"})).start()
    while True:
        message = socket.recv_multipart()
        process_dealer_message(message)

def pull_dispatcher():
    global workers, rep
    threading.Thread(target=(listen_to_pub), kwargs=({"mode":"pull"})).start()
    while True:
        message = socket.recv()
        print(message)
        message = dill.loads(message)

        if(message['type']=='Available'):
            if tasks:
                print("RECEIVED TASK", tasks[-1])
                task_id = tasks.pop()
                task_payload = redis_client.get_task(task_id)
                redis_client.update_task_status(task_id, 'RUNNING')
                function_data = task_payload["function_data"]
                args = task_payload["args"]
                task = (task_id, function_data["function_body"], args)
                socket.send(dill.dumps({'task': task}))
            else:
                socket.send(dill.dumps({'task': 'None'}))
        elif(message['type']=='Res'):
            task_id = message['task_id']
            res = message['res']
            print(f'res is: {res}')
            redis_client.update_task_status(task_id, "COMPLETED")
            redis_client.update_task_result(task_id, res)
            print(message)
            socket.send(dill.dumps({'task': 'None'}))

    
def listen_to_pub(mode):
    global socket, tasks
    while True:
        for message in sub.listen():
            task_id = message['data']
            if task_id is not None and task_id != 1:
                tasks.append(task_id)
                if mode == 'push':
                    threading.Thread(target=(send_push_worker_message), args=()).start()
                    redis_client.update_task_status(task_id, 'RUNNING')

# helper function for push_dispatcher to process messages
def process_dealer_message(message):
    global workers
    client_id = message[0]
    content = dill.loads(message[1])
    
    if content[0] == 'Available':
        workers.append(client_id)
        print(f"appended {client_id}")
    elif content[0] == 'Res': #then content should look like ['Res', {task_id}, {res}]
        print(content)
        task_id = content[1]
        res = content[2]
        print(f'res is: {res}')
        redis_client.update_task_status(task_id, "COMPLETED")
        redis_client.update_task_result(task_id, res) 
        workers.append(client_id)

# helper function to recv messages from a worker
def recv_worker_message(socket):
    message = socket.recv_multipart()
    process_dealer_message(message)

# helper function to send 
def send_push_worker_message():
    global workers, socket

    task_id = tasks.pop()
    task_payload = redis_client.get_task(task_id)
    redis_client.update_task_status(task_id, 'RUNNING')
    function_data = task_payload["function_data"]
    args = task_payload["args"]
    task = (task_id, function_data["function_body"], args)
    available_worker = workers.pop()
    # Send the task to an available worker
    socket.send_multipart([available_worker, dill.dumps(task)])

if __name__ == '__main__':
    freeze_support() #for multiprocessing pool
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--mode', choices=['local', 'pull', 'push'], help='Mode: local, pull, or push')
    parser.add_argument('-p', '--port', type=int, help='Port number (Hint: it should be the same as your Redis server)')
    parser.add_argument('-w', '--num_worker_processors', type=int, help='Number of worker processors')
    args = parser.parse_args()

    if args.mode == 'local':
        local_dispatcher(args.num_worker_processors)
    elif args.mode == 'push':
        push_dispatcher()
    elif args.mode == 'pull':
        pull_dispatcher()
