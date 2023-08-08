import socket
import copy
import json
import numpy as np

from .message import Message

class RenderSocket(socket.socket):

    MESSAGE_CHUNK_SIZE = 8192

    def __init__(self, address):
        super().__init__(socket.AF_INET, socket.SOCK_STREAM)
        str_tuple = tuple(filter(None, address.split(':')))
        self.address = (str_tuple[0], int(str_tuple[1]))
        self.connect(self.address)
    
    def disconnect(self):
        self.close()
    
    def write_message(self, msg):
        
        msg_data_bytes = msg.data_serialized() 

        msg_header = dict()
        msg_header["type"] = msg["type"]
        msg_header["data_format"] = msg["data_format"]
        msg_header["data_size"] = len(msg_data_bytes)

        msg_header_str = json.dumps(msg_header, indent = 4)
        msg_header_bytes = msg_header_str.encode('utf-8') + b'\00'
        
        while(len(msg_header_bytes) < Message.MESSAGE_HEADER_SIZE):
            msg_header_bytes += b'\00'
        
        if len(msg_header_bytes) > Message.MESSAGE_HEADER_SIZE:
            raise Exception("Message header size exceded.")
 
        self.sendall(msg_header_bytes)           
        self.sendall(msg_data_bytes)
        
    def read_message(self):
        
        msg_header_bytes = self.recv(Message.MESSAGE_HEADER_SIZE)
        msg_header_str = msg_header_bytes.decode("utf-8").rstrip('\x00')
        msg = json.loads(msg_header_str)
        
        msg["data"] = bytearray()
        bytes_received = 0
                    
        while bytes_received < msg["data_size"]:
            data = self.recv(RenderSocket.MESSAGE_CHUNK_SIZE)
            bytes_received += len(data)
            msg["data"] += data
        
        if msg["data_format"] == "json":
            msg["data"] = json.loads(msg["data"])

        if msg["data_format"] == "float4":
            msg["data"] = np.frombuffer(msg["data"], dtype=np.single)   
        
        print("LEIDO MENSAJEEE")
        print(msg)
        
        return msg    

    def wait_ok(self):
        msg = self.read_message()
        return msg["type"] == "status" and msg["data"] == "ok"