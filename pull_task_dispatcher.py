import redis
import json
import zmq
import threading
import requests
import time
import redis_client
import dill

class PullTaskDispatcher:
    def __init__(self):
        # Create a ZMQ context and socket for communication with workers
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind("tcp://*:5555")

        # Connect to Redis to listen for tasks
        self.r = redis.Redis(host='localhost', port=6379, db=0)
        self.task_channel = self.r.pubsub()
        self.task_channel.subscribe("tasks")

        # Store registered workers in a list
        self.workers = []

        # Create a lock for thread synchronization
        self.socket_lock = threading.Lock()

        self.register_thread = threading.Thread(target=self.register_workers)
        self.listen_thread = threading.Thread(target=self.listen_for_tasks)
                
        self.register_thread.daemon = True
        self.listen_thread.daemon = True

        self.register_thread.start()
        self.listen_thread.start()

    def register_workers(self):
        """ listen for tasks and dispatch them to available workers"""
        while True:
            # Listen for registration requests from workers
            try:
                request = self.socket.recv(flags=zmq.NOBLOCK)
                print(f"Received request: {request}")

                if request:
                    try:
                        request_info = json.loads(request.decode())
                        print(f"Parsed request info: {request_info}")

                        if request_info.get("worker_id") and request_info["worker_id"] not in self.workers:

                            # Add new worker to available workers

                            # Acquire the lock before connecting to the worker
                            self.socket_lock.acquire()

                            try:
                                worker_socket = self.context.socket(zmq.REQ)
                                worker_socket.connect("tcp://localhost:5556")
                                self.workers.append(worker_socket)
                            finally:
                                # Release the lock after connecting to the worker
                                self.socket_lock.release()

                        self.socket.send(json.dumps({"status": "ok"}).encode())
                    except json.decoder.JSONDecodeError as e:
                        # Handle JSON decoding error
                        print(f"Error decoding JSON: {str(e)}")
                        self.socket.send(json.dumps({"status": "error", "message": "Invalid JSON"}).encode())
            except zmq.Again:
                pass

    def listen_for_tasks(self):
        """Listen for tasks and dispatch them to available workers"""
        while True:
            for message in self.task_channel.listen():
                task_id = message['data']
                if task_id is not None and task_id != 1:
                    task_payload = redis_client.get_task(task_id)
                    redis_client.update_task_status(task_id, 'RUNNING')
                    function_data = task_payload["function_data"]

                    # Extract the function_body from the function_data
                    function_body = function_data["function_body"]
                    print(f"Retrieved function body: {function_body}")
                    
                    # Update the task_data dictionary with the function_body key-value pair
                    task_payload["function_body"] = function_body
                    print(f"Received task: {task_payload}")
                    worker_payload = {
                        "request": "task",
                        "task_payload": task_payload
                    }

                response = self.socket.send(dill.dumps(worker_payload))
                if response.status_code == 200:
                    print("Task sent successfully to pull_worker.py")
                else:
                    print(f"Failed to send task: {response.text}")
                    

 

if __name__ == "__main__":
    # Create an instance of PullTaskDispatcher
    dispatcher = PullTaskDispatcher()

    while True:
        # Add a blocking statement to keep the main thread active
        time.sleep(1)



        # for message in self.task_channel.listen():
        #     if message['type'] == 'message':
        #         data = message['data'].decode("utf-8")
        #         print(f"data: {data}")

        #         try:
        #             task_data = json.loads(data)
        #             print(f"task_data: {task_data}")

        #             function_id = task_data.get("function_id")

        #             # Retrieve the function_data from Redis using the function_id
        #             try:
        #                 function_data = get_function(function_id)
        #                 function_body = function_data.get("function_body")

        #                 if function_body is not None:
        #                     # Update the task_data dictionary with the function_body key-value pair
        #                     task_data["function_body"] = function_body
        #                     print(f"Received task: {task_data}")

        #                     # Send the task_data to pull_worker.py
        #                     try:
        #                         response = requests.post("http://localhost:8000/execute_task", json=task_data)
        #                         if response.status_code == 200:
        #                             print("Task sent successfully to pull_worker.py")
        #                         else:
        #                             print(f"Failed to send task: {response.text}")
        #                     except requests.exceptions.RequestException as e:
        #                         print(f"Error sending task: {str(e)}")

        #             except (redis.exceptions.DataError, KeyError):
        #                 # Handle exception if function_id is invalid or function_body is missing
        #                 print(f"Invalid function_id: {function_id}")
        #         except (json.JSONDecodeError, TypeError):
        #             # Handle exception if there's an error parsing the JSON or task_data is not a dictionary
        #             print("Invalid task_data")
