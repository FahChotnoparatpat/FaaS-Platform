import uuid
import json
import dill
import redis
import uvicorn
import codecs
import redis_client
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
app = FastAPI()

class RegisterFn(BaseModel):
    name: str
    payload: str

class RegisterFnRep(BaseModel):
    function_id: uuid.UUID

class ExecuteFnReq(BaseModel):
    function_id: uuid.UUID
    payload: str

class ExecuteFnRep(BaseModel):
    task_id: uuid.UUID

class TaskStatusRep(BaseModel):
    task_id: uuid.UUID
    status: str

class TaskResultRep(BaseModel):
    task_id: uuid.UUID
    status: str
    result: Optional[str]

@app.post("/register_function", response_model=RegisterFnRep)
async def register_function(fn: RegisterFn):
    function_id = redis_client.register_function(fn.name, fn.payload)
    return {"function_id": function_id}

@app.post("/execute_function", response_model=ExecuteFnRep)
async def execute_function(req: ExecuteFnReq):
    task_id = redis_client.create_task(str(req.function_id), req.payload)
    return {"task_id": task_id}

@app.get("/get_task_status/{task_id}", response_model=TaskStatusRep)
async def get_task_status(task_id: str):
    task = redis_client.get_task(task_id)
    return { 'task_id': task_id, "status": task["status"]}

@app.get("/get_task_result/{task_id}", response_model=TaskResultRep)
async def get_task_result(task_id: str):
    task = redis_client.get_task(task_id)
    return {"task_id": task_id, "status": task["status"], "result": task.get("result")}
