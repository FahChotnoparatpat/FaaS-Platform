import requests
import dill
import json
import codecs
import time

# Optional: exit(1) with corresponding error messages upon failed responses

# Function to register
def my_function(x):
    return x * 2

def serialize(obj) -> str:
    return codecs.encode(dill.dumps(obj), "base64").decode()
def deserialize(obj: str):
    return dill.loads(codecs.decode(obj.encode(), "base64"))


# Register the function
registration_response = requests.post(
    "http://localhost:8000/register_function",
    json={"name": "my_function", "payload": serialize(my_function)}
)


# Check if registration was successful
if registration_response.status_code == 200:
    try:
        registration_response_txt = json.loads(registration_response.text)
        function_id = registration_response_txt.get("function_id")
        if function_id:
            print(f"Successfully registered function with function_id = {function_id}\n")
        else:
            print("Error: 'function_id' not found in response JSON\n")
            exit(1)

        # Continue with the remaining code only if registration was successful
        if function_id:

            # Execute the function
            execution_payload = {
                "function_id": function_id,
                "payload": 5  # Update the payload here with the necessary input arguments
            }

            execution_response = requests.post("http://localhost:8000/execute_function", json=execution_payload)
            if execution_response.status_code == 200 and execution_response.text:
                execution_response_txt = json.loads(execution_response.text)
                print(f"Execution Response: {execution_response.text}")
                task_id = execution_response_txt.get("task_id")
                if task_id:
                    print(f"Task ID: {task_id}")

                    # Get task status
                    status_response = requests.get(f"http://localhost:8000/get_task_status/{task_id}")
                    if status_response.status_code == 200 and status_response.text:
                        status_response_txt = json.loads(status_response.text)
                        print(f"Task Status Response: {status_response_txt}")
                        status = status_response_txt.get("status")
                        if status:
                            print(f"Task status: {status}")

                            # Retrieve the result of the task
                            result_response = requests.get(f"http://localhost:8000/get_task_result/{task_id}")
                            if result_response.status_code == 200 and result_response.text:
                                result_response_txt = json.loads(result_response.text)
                                print(f"Task Result Response: {result_response.text}")
                                result = result_response_txt.get("result")
                            else:
                                print(f"Error retrieving task result: {execution_response.status_code}")
                        else:
                            print("Error: 'status' not found in response JSON")
                    else:
                        print(f"Error retrieving task status: {status_response.status_code}")
                else:
                    print("Error: 'task_id' not found in response JSON")
            else:
                print("Error executing function")
                exit(1)
    except KeyError:
        print("Error: 'function_id' not found in response JSON")
else:
    print(f"Registration failed with status code: {registration_response.status_code}")
