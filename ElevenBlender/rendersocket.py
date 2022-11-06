import socket
import copy
import json

from .message import Message

class RenderSocket(socket.socket):

    MESSAGE_CHUNK_SIZE = 8192

    def __init__(self, address):
            super().__init__(socket.AF_INET, socket.SOCK_STREAM)
            str_tuple = tuple(filter(None, address.split(':')))
            self.address = (str_tuple[0], int(str_tuple[1]))
            self.connect(self.address)
    
    
    def write_message(self, msg):
        
        # This is not as efficient as could be. Copying big data messages can be troublesome.
        # Maybe popping first the element and making a copy after, could be better.
        msg_header = copy.deepcopy(msg)
        msg_header.pop("data")
                
        if msg["data_format"] == "json":
            msg_data_str = json.dumps(msg["data"], indent = 4)
            msg_data_bytes = msg_data_str.encode('utf-8') + b'\00'
        elif msg["data_format"] == "float3":
            msg_data_bytes = msg["data"].tobytes()  
        elif msg["data_format"] == "float4":
            msg_data_bytes = msg["data"].tobytes() 
        elif msg["data_format"] == "string":
            msg_data_bytes = msg["data"].encode('utf-8') + b'\00'
        else:
            raise Exception("Message data type unspecified")

        msg_header["data_size"] = len(msg_data_bytes)
        msg["data_size"] = msg_header["data_size"]
 
        msg_header_str = json.dumps(msg_header, indent = 4)
        msg_header_bytes = msg_header_str.encode('utf-8') + b'\00'
        
        if len(msg_header_bytes) > Message.MESSAGE_HEADER_SIZE:
            raise Exception("Message header size exceded.")
 
        self.sendall(msg_header_bytes)           
        self.sendall(msg_data_bytes)
        
    def read_message(self):
        
        msg_header_bytes = self.recv(Message.MESSAGE_HEADER_SIZE)
        msg_header_str = msg_header_bytes.decode("utf-8")
        msg = json.loads(msg_header_str)
        
        msg["data"] = bytearray()
        bytes_received = 0
                    
        while amount_received < msg["data_size"]:
            data = self.recv(MESSAGE_CHUNK_SIZE)
            amount_received += len(data)
            msg["data"] += data
        
        return msg    

    def wait_ok(self):
        msg = self.read_message()
        return msg["type"] == "status" and msg["data"] == "OK"