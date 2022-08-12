import bpy
import socket
import array
import gpu
import json
import subprocess
import struct
import sys
import os
import math
import time
import numpy as np
from gpu_extras.presets import draw_texture_2d



TCP_MESSAGE_MAXSIZE = 1024

def write_message(msg, sock):
    
    message_str = json.dumps(msg, indent = 4) 
    message_bytes = message_str.encode('utf-8')
    
    sock.sendall(message_bytes)
    
    if msg["data_size"] > 0:
        sock.sendall(bytes(msg["data"]))


def read_message(sock):
            
    message_bytes = sock.recv(TCP_MESSAGE_MAXSIZE)
    message_str = message_bytes.decode("utf-8")
    message_json = json.loads(message_str)
    
    if message_json["data_size"] > 0:
        
        message_json["data"] = bytearray()
        amount_received = 0
                
        while amount_received < message_json["data_size"]:
            data = sock.recv(8096)
            amount_received += len(data)
            message_json["data"] += data
    
    return message_json    
    
    

def sceneTCP(scene_path):

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    server_address = ('127.0.0.1', 5557)
    print('connecting to {} port {}'.format(*server_address))
    sock.connect(server_address)
    print('connected!')

    response_bytes = bytearray()

    try:
        
        scene_load_msg = dict()
        
        scene_load_msg["type"] = "command"
        scene_load_msg["msg"] = "--load_obj " + scene_path      
        
        write_message(scene_load_msg, sock)        

    finally:
        print('closing socket')
        sock.close()


def tcpTest():

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    server_address = ('127.0.0.1', 5557)
    print('connecting to {} port {}'.format(*server_address))
    sock.connect(server_address)

    response_data = []
    response_bytes = bytearray()


    try:
      
        amount_received = 0
        amount_expected = 1920*1080*4*4
                
        while amount_received < amount_expected:
            data = sock.recv(8096)
            amount_received += len(data)
            response_bytes += data

    finally:
        print('closing socket')
        sock.close()

    # I will need to write a custom c module to break this bottleneck           
    arr = np.frombuffer(response_bytes, dtype=np.single)    
    arr = arr.reshape((1920*1080, 4))          
    return arr 
    

class CustomRenderEngine(bpy.types.RenderEngine):
    # These three members are used by blender to set up the
    # RenderEngine; define its internal name, visible name and capabilities.
    bl_idname = "ELEVENRENDERER"
    bl_label = "Eleven"
    bl_use_preview = True

    # Init is called whenever a new render engine instance is created. Multiple
    # instances may exist at the same time, for example for a viewport and final
    # render.
    def __init__(self):
        self.scene_data = None
        self.draw_data = None

    # When the render engine instance is destroy, this is called. Clean up any
    # render engine data here, for example stopping running render threads.
    def __del__(self):
        pass

    # This is the method called by Blender for both final renders (F12) and
    # small preview for materials, world and lights.
    def render(self, depsgraph):
                
        scene = depsgraph.scene
        scale = scene.render.resolution_percentage / 100.0
        self.size_x = int(scene.render.resolution_x * scale)
        self.size_y = int(scene.render.resolution_y * scale)

        sceneTCP("C:\\Users\\Kike\\Desktop\\TFM\\scenes\\blenderTest")


        result = self.begin_result(0, 0, self.size_x, self.size_y)
        layer = result.layers[0].passes["Combined"]
        #layer.rect = rect        
        self.end_result(result)


    # For viewport renders, this method gets called once at the start and
    # whenever the scene or 3D viewport changes. This method is where data
    # should be read from Blender in the same thread. Typically a render
    # thread will be started to do the work while keeping Blender responsive.
    def view_update(self, context, depsgraph):
        region = context.region
        view3d = context.space_data
        scene = depsgraph.scene

        # Get viewport dimensions
        dimensions = region.width, region.height

        if not self.scene_data:
            # First time initialization
            self.scene_data = []
            first_time = True

            # Loop over all datablocks used in the scene.
            for datablock in depsgraph.ids:
                pass
        else:
            first_time = False

            # Test which datablocks changed
            for update in depsgraph.updates:
                print("Datablock updated: ", update.id.name)

            # Test if any material was added, removed or changed.
            if depsgraph.id_type_updated('MATERIAL'):
                print("Materials updated")

        # Loop over all object instances in the scene.
        if first_time or depsgraph.id_type_updated('OBJECT'):
            for instance in depsgraph.object_instances:
                pass

    # For viewport renders, this method is called whenever Blender redraws
    # the 3D viewport. The renderer is expected to quickly draw the render
    # with OpenGL, and not perform other expensive work.
    # Blender will draw overlays for selection and editing on top of the
    # rendered image automatically.
    def view_draw(self, context, depsgraph):
        region = context.region
        scene = depsgraph.scene

        # Get viewport dimensions
        dimensions = region.width, region.height

        # Bind shader that converts from scene linear to display space,
        gpu.state.blend_set('ALPHA_PREMULT')
        self.bind_display_space_shader(scene)

        if not self.draw_data or self.draw_data.dimensions != dimensions:
            self.draw_data = CustomDrawData(dimensions)

        self.draw_data.draw()

        self.unbind_display_space_shader()
        gpu.state.blend_set('NONE')


class CustomDrawData:
    def __init__(self, dimensions):
        # Generate dummy float image buffer
        self.dimensions = dimensions
        width, height = dimensions

        pixels = width * height * array.array('f', [0.9, 0.2, 0.1, 1.0])
        
        print(len(pixels))
        
        pixels = gpu.types.Buffer('FLOAT', width * height * 4)

        print(len(pixels))

        # Generate texture
        self.texture = gpu.types.GPUTexture((width, height), format='RGBA16F', data=pixels)

        # Note: This is just a didactic example.
        # In this case it would be more convenient to fill the texture with:
        # self.texture.clear('FLOAT', value=[0.1, 0.2, 0.1, 1.0])

    def __del__(self):
        del self.texture

    def draw(self):
        print("drawing")
        draw_texture_2d(self.texture, (0, 0), self.texture.width, self.texture.height)


# RenderEngines also need to tell UI Panels that they are compatible with.
# We recommend to enable all panels marked as BLENDER_RENDER, and then
# exclude any panels that are replaced by custom panels registered by the
# render engine, or that are not supported.
def get_panels():
    exclude_panels = {
        'VIEWLAYER_PT_filter',
        'VIEWLAYER_PT_layer_passes',
    }

    panels = []
    for panel in bpy.types.Panel.__subclasses__():
        if hasattr(panel, 'COMPAT_ENGINES') and 'BLENDER_RENDER' in panel.COMPAT_ENGINES:
            if panel.__name__ not in exclude_panels:
                panels.append(panel)

    return panels


def register():
    # Register the RenderEngine
    bpy.utils.register_class(CustomRenderEngine)

    for panel in get_panels():
        panel.COMPAT_ENGINES.add('CUSTOM')


def unregister():
    bpy.utils.unregister_class(CustomRenderEngine)

    for panel in get_panels():
        if 'CUSTOM' in panel.COMPAT_ENGINES:
            panel.COMPAT_ENGINES.remove('CUSTOM')


if __name__ == "__main__":
        
    register()