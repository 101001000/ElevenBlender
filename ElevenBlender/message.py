import json

class Message(dict):

    MESSAGE_HEADER_SIZE = 1024

    def __init__(self):
        self.__dict__ = dict()
        
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
    
    def TextureDataMessage(image):
        arr = np.empty((image.size[1] * image.size[0] * 4), dtype=np.single)
        image.pixels.foreach_get(arr)
        return Float4Message(arr)

class JsonMessage(DataMessage):

    def __init__(self, json):
        DataMessage.__init__(self, json)
        self["data_format"] = "json"
    
    def data_serialized(self):
        return bytearray(json.dumps(self["data"], indent = 4).encode()) + b'\00'
    
    def ConfigMessage(config):
        return JsonMessage(config)
        
    def TextureMetadataMessage(image):
        tex_metadata = dict()
        tex_metadata["name"] = image.name
        tex_metadata["width"] = int(image.size[0])
        tex_metadata["height"] = int(image.size[1]) 
        tex_metadata["color_space"] = image.colorspace_settings.nam
        return JsonMessage(tex_metadata)

class CommandMessage(Message):

    def __init__(self, command):
        Message.__init__(self)
        self["type"] = "command"
        self["data_format"] = "string"
        self["data"] = command
    
    def data_serialized(self):
        return self["data"].encode('utf-8') + b'\00'
    
    def SendHDRIMessage():
        return CommandMessage("--load_hdri")
        
    def SendConfigMessage():
        return CommandMessage("--load_config")
        
    def SendTextureMessage():
        return CommandMessage("--load_texture")