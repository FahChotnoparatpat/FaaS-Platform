# FaaS-Platform
This is a project by Praneeth Chandu and Natcha Chotnoparatpat

**Redis Client:**
Our Redis Client contains functions to serve the FastAPI. In our Redis client, we implemented the following methods:
* `register_function(function_name, function_body):`
    * Creates a new uuid for function_id and sets the function_id with a JSON containing function_name and function body as it's value
    * Returns the str version of the function_id
* `get_function(function_id):`
    * Simply retrieves the value in the db with the key of `function_id` and returns a dictionary with function_name and it's content (the function itself)
    * Raises an exception if there is no value found in the redis db with the function_id as a key 
* `create_task(function_id, input_arguments):`
    * Creates a task_id and sets the task_id in the db with a JSON containing function payload, args, status, and result as the value
    * Status is default set to 'QUEUED'
    * Result is default set to None
    * The task is published to the tasks channel which dispatchers are listening to
    * The task_id is returned once published
* `get_task(task_id):`
    * Retrieves the task payload of the task_id arg from the redis db and returns to caller
    * Exception is raised if no key of task_id is found in db
* `update_task_status(task_id, status):`
    * Retrieves the task payload of task_id arg from redis db and updates the payload's status with the status arg
    * Exception is raised if no key of task_id is found in db
* `update_task_result(task_id, result):`
    * Retrieves the task payload of task_id arg from redis db and updates the payload's result with the result arg
    * Exception is raised if no key of task_id is found in db

**Fast API:**
An interface between a client and redis database.

The validations for responses from each API call were imported from project spec file. There are four requests clients can make:
* `/register_function`
    * Calls the redis_client's `register_function` method with request's payload: function_name and function_payload
    * Returns function_id back to the client
* `/execute_function`
    * Calls the redis_client's `execute_function` method with request's payload: function_id and function_payload (containing the arguments to execute)
    * Returns task_id back to the client as there is now a task created for in the redis client
* `/get_task_status`
    * Retrieves the task payload for the given task_id and returns the status from the payload
* `/get_task_result`
    * Retrieves the task payload for the given task_id
    * Checks if the task is completed and errors if it is not as the result has not been computed
    * Returns the task's id, status, and result otherwise

**Task Dispatcher & Corresponding Workers**

* Connects to redis client and subscribes to the tasks channel. Individual dispatcher implementation start listening depending on which dispatcher is chosen by user.
* `execute_function` deserializes the func payload which results in a python function object that is executed with the args stored from the client's execute task request.
* all dispatchers start a thread to listen to messages from the tasks channel socket via `listen_to_pub(mode)` (where mode is either local, push, or pull)

*Local Dispatcher*
* Creates a pool of workers based on command line args when running task_dispatcher.
* If a message is received, it is assumed that the message is a task_id as those are the only messages that get pushed from the publisher
* Once a message is received, the dispatcher retrieves the task's payload from the redis client and executes using `execute_function` described above async through the worker pool 

*Limitations of Local Dispatcher*

* Limited Scalability: The local dispatcher creates a fixed pool of workers based on command line arguments. This means that the number of workers is predetermined and cannot easily scale up or down based on the workload or system resources. 
* Single Point of Failure: The local dispatcher operates as a single instance, listening for messages and dispatching tasks. If the local dispatcher encounters an error or crashes, the entire task dispatching system may be affected, leading to service interruptions or loss of tasks.

*Push Dispatcher*

* Creates a socket with ROUTER protocol and starts listening to messages from publisher as mentioned in local_dispatcher
* If a message is received, it is processed via `process_dealer_message`, which checks the content of the message. The push worker sends messages starting with either "Available" or "Res".
    * if a message starts with "Available", it is a signal that the worker is not executing a task. 
    * if a message starts with "Res", it is a signal that the worker has completed executing a task. "Res" messages also contain the task_id and result of the execution which `process_dealer_message` uses to update the task status and result accordingly. The task is now completed.
    * for both types of messages, the ID of the message's sender (a worker node) is added to the worker's list, which contains the IDs of all available workers.

*Push Worker*

* Creates a socket with DEALER context and connects the URL from the command line args
* Spawns a thread that runs the main worker loop
* Main worker loop creates a multiprocessing pool according to the argument passed in
* Upon initialization, the dealer sends a message to the router it's connected with stating it is available
* Upon receiving a message, the worker node will run `execute_function` async via the multiproc pool with the message as the argument (the message is the task_id, function_payload, and corresponding args)

*Limitations of Push Dispatcher/Worker*

* Limited Error Handling: The current implementation does not explicitly handle potential errors or exceptions that may occur during task execution.
* Fault Tolerance: With this currently implementation, the dispatcher does not have a mechanism to detect and reassign the task to another worker if a worker fails.

*Pull Dispatcher*

* Creates a socket with REQ protocol and starts listening to messages from publisher via `listen_to_pub`
* Starts receiving messages from the pull worker and checks what the message's 'type' key's value is.
    * If the message's type is 'Available', then the dispatcher checks if there are any tasks in the tasks list. If there is a task, then dispatcher will send the task's payload to it's worker. Otherwise, it will send back a task with value 'None'.
    * If the message's type is 'Res' (result), the dispatcher will update the redis db's status and task via task ID that is also in that message. Then, it will send back the {'task':'None'} back to the worker.

*Pull Worker*

* Connects to the REP
* Receives messages and executes if there is a task in the message. 
* Execution is the same as the other dispatchers except the message back to REP is in a dict format instead of a list or tuple because of the distinct pull dispatcher logic

*Limitations of Pull Dispatcher/Worker*

**Communication Overhead**: In the pull implementation, workers frequently query the dispatcher for available tasks. This frequent communication between workers and the dispatcher can introduce additional network overhead and latency. The overhead increases as the number of workers and task requests grows, potentially impacting the overall system performance.

**Fault Tolerance**: With this currently implementation, the dispatcher does not have a mechanism to detect and reassign the task to another worker if a worker fails.

**Single Point of Failure**: The pull dispatcher acts as a single point of failure in this implementation. If the dispatcher fails or becomes unavailable, the entire task distribution process is disrupted, and no new tasks can be assigned to workers until the dispatcher is restored.
