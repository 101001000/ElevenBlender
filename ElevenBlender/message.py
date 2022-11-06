import json

class Message(dict):

    # Message:
    # data:
    # data_size (in bytes) # TODO: think about discarding this field
    # data_format: float4, json, string
    # type: data, command, status

    MESSAGE_HEADER_SIZE = 1024

    def __init__(self):
        self.__dict__ = dict()

    def TextureMetadataMessage(image):
        
        msg = Message()
        
        tex_metadata = dict()
        tex_metadata["name"] = image.name
        tex_metadata["width"] = int(image.size[0])
        tex_metadata["height"] = int(image.size[1]) 
        tex_metadata["color_space"] = image.colorspace_settings.name
        
        byte_data = bytearray(json.dumps(tex_metadata, indent = 4).encode()) + b'\00'
        
        msg["type"] = "data"
        msg["data"] = dict()
        msg["data"]["data_type"] = "json"
        msg["data"]["data"] = tex_metadata
        #msg["data"]["data_size"] = len(byte_data) + 1
        
        return msg

    def TextureDataMessage(image):
        
        msg = Message()
        
        arr = np.empty((image.size[1] * image.size[0] * 4), dtype=np.single)
        image.pixels.foreach_get(arr)
        
        msg["type"] = "data"
        msg["data_format"] = "float4"
        #msg["data_size"] = len(arr)*4
        msg["data"] = arr
        
        return msg
            
    def SendTextureCommandMessage(mode="tcp"):
            
        msg = Message()
        
        if mode == "tcp":
            msg["type"] = "command"
            msg["data_format"] = "string"
            msg["data"] = "--load_texture"
            #msg["data_size"] = len(msg["data"]) + 1
        
        
        return msg
        

    def ConfigDataMessage(config):
            
        msg = Message()
        byte_data = bytearray(json.dumps(config, indent = 4).encode()) + b'\00'
            
        msg["type"] = "data"
        msg["data_format"] = "json"
        msg["data"] = config
        #msg["data_size"] = len(msg["data"]) + 1
        
        return msg

    def SendConfigMessage(mode="tcp"):
            
        msg = Message()
        
        if mode == "tcp":
            msg["type"] = "command"
            msg["data_format"] = "string"
            msg["data"] = "--load_config"
            #msg["data_size"] = len(msg["data"]) + 1
            
        
        return msg


    def SendHDRIMessage(mode="tcp"):
            
        msg = Message()
        
        if mode == "tcp":
            msg["type"] = "command"
            msg["data_format"] = "string"
            msg["data"] = "--load_hdri"
            #msg["data_size"] = len(msg["data"]) + 1
        
        
        return msg


    def print(self):
        print("type: ", self["type"])
        print("data_format: ", self["data_format"])
        print("data: ", self["data"])

    #TODO: Abstracting Send messages

