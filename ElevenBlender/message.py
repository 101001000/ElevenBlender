import json
import numpy as np

class Message(dict):

    MESSAGE_HEADER_SIZE = 1024

    def __init__(self):
        self.__dict__ = dict()
        
    def print(self):
        print(json.dumps(self))
        
class DataMessage(Message):

    def __init__(self, data):
        Message.__init__(self)
        self["type"] = "data"
        self["data"] = data
        
                
class Float4Message(DataMessage):

    def __init__(self, arr):
        DataMessage.__init__(self, arr)
        self["data_format"] = "float4"
        
    def data_serialized(self):
        return self["data"].tobytes() 
    

class JsonMessage(DataMessage):

    def __init__(self, json):
        DataMessage.__init__(self, json)
        self["data_format"] = "json"
    
    def data_serialized(self):
        return bytearray(json.dumps(self["data"], indent = 4).encode()) + b'\00'
    

class CommandMessage(Message):

    def __init__(self, command):
        Message.__init__(self)
        self["type"] = "command"
        self["data_format"] = "string"
        self["data"] = command
    
    def data_serialized(self):
        return self["data"].encode('utf-8') + b'\00'
    
    
    
#TODO: Thinking about merging messages
    
def LoadHDRIMessage():
    return CommandMessage("--load_hdri --mirror_y")
    
def LoadConfigMessage():
    return CommandMessage("--load_config")
    
def LoadBrdfMaterialMessage():
    return CommandMessage("--load_brdf_material")
    
def LoadTextureMessage():
    return CommandMessage("--load_texture")  
    
def LoadCameraMessage():
    return CommandMessage("--load_camera")  
    
def LoadObjectMessage(path, mode):
    return CommandMessage('--load_object --path="' + path + '"' + (" --recompute_normals" if mode == "Face Weighted" else ""))  
  
def GetInfoMessage():
    return CommandMessage('--get_info')
    
def GetPassMessage(render_pass):
    return CommandMessage("--get_pass " + render_pass)
    
    
        
  
def StartMessage():
    return CommandMessage("--start")  

def AbortMessage():
    return CommandMessage("--abort")      

def ConfigMessage(config):
    return JsonMessage(config)
    
def CameraMessage(camera):
    return JsonMessage(camera)
    
def BrdfMaterialMessage(mat):
    return JsonMessage(mat)
    
def TextureMetadataMessage(image):
    tex_metadata = dict()
    tex_metadata["name"] = image.name
    tex_metadata["width"] = int(image.size[0])
    tex_metadata["height"] = int(image.size[1]) 
    tex_metadata["channels"] = int(image.channels) 
    tex_metadata["color_space"] = image.colorspace_settings.name
    return JsonMessage(tex_metadata)
    
def TextureDataMessage(image):
    arr = np.empty((image.size[1] * image.size[0] * 4), dtype=np.single)
    image.pixels.foreach_get(arr)
    return Float4Message(arr)