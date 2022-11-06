import bpy
import gpu
import socket
import array
import json
import subprocess
import struct
import sys
import os
import bgl
import math
import time
import ctypes
import numpy as np
from datetime import datetime
from gpu_extras.presets import draw_texture_2d


ELEVEN_PATH = "C:\\Users\\Kike\\Desktop\\TFM\\repos\\ElevenRender\\ElevenRender.exe"
TCP_MESSAGE_MAXSIZE = 1024
TARGET_SAMPLES = 50

def export_scene(scene, path):
    
    scene_object = dict()

    #Camera setup:
    b_cam_loc = bpy.data.objects['Camera'].location
    b_cam_rot = bpy.data.objects['Camera'].rotation_euler 

    scene_object['camera'] = dict()

    scene_object['camera']['xRes'] = scene.render.resolution_x
    scene_object['camera']['yRes'] = scene.render.resolution_y

    scene_object['camera']['position'] = {'x':b_cam_loc.x,'y':b_cam_loc.z,'z':b_cam_loc.y}
    scene_object['camera']['rotation'] = {'x': 90 - b_cam_rot.x / (math.pi/180), 'y':-b_cam_rot.z / (math.pi/180), 'z': -b_cam_rot.y / (math.pi/180)}

    scene_object['camera']['focalLength'] = bpy.data.cameras[0].lens/1000
    scene_object['camera']['focusDistance'] = bpy.data.cameras[0].dof.focus_distance
    scene_object['camera']['aperture'] = bpy.data.cameras[0].dof.aperture_fstop
    scene_object['camera']['bokeh'] = bpy.data.cameras[0].dof.use_dof


    #Hdri setup:

    scene_object['hdri'] = dict()

    if bpy.context.scene.world.node_tree.nodes.find('Environment Texture') != -1:
        
        tex = bpy.context.scene.world.node_tree.nodes['Environment Texture'].image
        full_path = bpy.path.abspath(tex.filepath, library=tex.library)
        norm_path = os.path.normpath(full_path)
        scene_object['hdri']['name'] = norm_path
        
    else:        
        b_env_color = bpy.context.scene.world.node_tree.nodes['Background'].inputs[0].default_value
        scene_object['hdri']['color'] = {'r':b_env_color[0], 'g':b_env_color[1], 'b':b_env_color[2]}        

    """
    for obj in bpy.data.objects:
        print(obj)
        obj.matrix_world @ obj.data.vertices[0].co
    """    
        
    bpy.ops.export_scene.obj(filepath=path + "\\scene.obj", use_triangles=True, path_mode='ABSOLUTE')
    with open(path + "\\scene.json", 'w') as fs:
            fs.write(json.dumps(scene_object))

def get_render_info_msg():
              
    msg = dict()
    msg["type"] = "command"
    msg["msg"] = '--get_info'
    return msg

def write_message(msg, sock):
                           
    if "additional_data" in msg:
        add_data = msg["additional_data"]["data"]
        msg["additional_data"].pop("data")
            
    message_str = json.dumps(msg, indent = 4) 
    message_bytes = message_str.encode('utf-8') + b'\00'
    
    sock.sendall(message_bytes)
    
    if "additional_data" in msg:
        
        log("Sending additional bytes")
        sock.sendall(add_data)

    log("Message written: " + str(message_str))

def read_message(sock):
                
    message_bytes = sock.recv(TCP_MESSAGE_MAXSIZE)
    
    message_str = message_bytes.decode("utf-8")
    
    message_json = json.loads(message_str)
    
    if "additional_data" in message_json:
        
        message_json["additional_data"]["data"] = bytearray()
        amount_received = 0
                
        while amount_received < message_json["additional_data"]["data_size"]:
            data = sock.recv(8096)
            amount_received += len(data)
            message_json["additional_data"]["data"] += data
            
    
    print("Message read ", message_str)
    
    return message_json    

def extractTextureNodesFromMat(mat):
    
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    
    texs = []
    
    for input in bsdf.inputs:
        if input.links:
            tex_node = input.links[0].from_node
            if tex_node.type =='TEX_IMAGE':
                texs.append(tex_node)
            if tex_node.type == 'NORMAL_MAP':
                try:
                    texs.append(tex_node.inputs['Color'].links[0].from_node)
                except:
                    pass
    
    return texs

def sendHDRI(sock, json_tex):
    arr = np.array(json_tex.pop("data"), dtype=np.single)
    arr = np.delete(arr, np.arange(3, arr.size, 4))

    byte_data = arr.tobytes()   
    
             
    tex_load_msg = dict()
    tex_load_msg["type"] = "command"
    tex_load_msg["msg"] = '--load_hdri ' + json.dumps(json_tex, separators=(',', ':'))
    tex_load_msg["additional_data"] = dict()
    tex_load_msg["additional_data"]["data_type"] = "float"
    tex_load_msg["additional_data"]["data"] = byte_data
    tex_load_msg["additional_data"]["data_size"] = len(byte_data)


def sendTexture(sock, json_tex):
        
    image = json_tex.pop("data")  
            

    arr = np.empty((image.size[1] * image.size[0] * 4), dtype=np.single)
    image.pixels.foreach_get(arr)
    byte_data = arr.tobytes()  
             
    tex_load_msg = dict()
    tex_load_msg["type"] = "command"
    tex_load_msg["msg"] = '--load_texture ' + json.dumps(json_tex, separators=(',', ':'))
    tex_load_msg["additional_data"] = dict()
    tex_load_msg["additional_data"]["data_type"] = "float"
    tex_load_msg["additional_data"]["data"] = byte_data
    tex_load_msg["additional_data"]["data_size"] = len(byte_data)
      
    write_message(tex_load_msg, sock)

def sendMaterial(sock, json_mat):
    
    byte_data = bytearray(json.dumps(json_mat, indent = 4).encode()) + b'\00'
            
    mat_load_msg = dict()
    mat_load_msg["type"] = "command"
    mat_load_msg["msg"] = "--load_brdf_material" 
    mat_load_msg["additional_data"] = dict()
    mat_load_msg["additional_data"]["data_type"] = "json"
    mat_load_msg["additional_data"]["data"] = byte_data 
    mat_load_msg["additional_data"]["data_size"] = len(byte_data)
    
    write_message(mat_load_msg, sock)

def convertTextureNode(tex_node):
    
    log("Converting texture...")
    
    tex_json = dict()
    tex_json["name"] = tex_node.image.name
    tex_json["width"] = int(tex_node.image.size[0])
    tex_json["height"] = int(tex_node.image.size[1]) 
    tex_json["data"] = tex_node.image
    tex_json["color_space"] = tex_node.image.colorspace_settings.name
            
    log("Converted texture")
    
    return tex_json  
 
def compatible(mat):
    try:
        next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        return True
    except:
        return False
        
        
def get_texturename_from_principled_input(principled_input):
    
    try:
        name = principled_input.links[0].from_node.image.name
        if principled_input.links[0].from_node.image.size[0] == 0 or principled_input.links[0].from_node.image.size[1] == 0:
            return False
    except:
        return False
    return name
 
def convertMaterial(mat):
    
    principled = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    
    p_base_color = principled.inputs['Base Color'].default_value
    p_metalness = principled.inputs['Metallic'].default_value
    p_roughness = principled.inputs['Roughness'].default_value
    p_specular = principled.inputs['Specular'].default_value
    p_opacity = principled.inputs['Alpha'].default_value
        
    p_emission_color = principled.inputs['Emission'].default_value
    p_emission_strength = principled.inputs['Emission Strength'].default_value
        
    mat_json = dict()
    mat_json["name"] = mat.name
    mat_json["albedo"] = {"r":p_base_color[0], "g":p_base_color[1], "b":p_base_color[2]}
    mat_json["metalness"] = p_metalness
    mat_json["roughness"] = p_roughness
    mat_json["specular"] = p_specular
    mat_json["emission"] = {"r":p_emission_color[0] * p_emission_strength, "g":p_emission_color[1] * p_emission_strength, "b":p_emission_color[2] * p_emission_strength}
    
    
    if get_texturename_from_principled_input(principled.inputs['Base Color']) != False:
        mat_json["albedo_map"] = get_texturename_from_principled_input(principled.inputs['Base Color'])
    
    if get_texturename_from_principled_input(principled.inputs['Roughness']) != False:
        mat_json["roughness_map"] = get_texturename_from_principled_input(principled.inputs['Roughness'])
    
    if get_texturename_from_principled_input(principled.inputs['Metallic']) != False:
        mat_json["metallic_map"] = get_texturename_from_principled_input(principled.inputs['Metallic'])
    
    if get_texturename_from_principled_input(principled.inputs['Emission']) != False:
        mat_json["emission_map"] = get_texturename_from_principled_input(principled.inputs['Emission'])
    
    try:
        if get_texturename_from_principled_input(principled.inputs['Normal'].links[0].from_node.inputs['Color']) != False:
            mat_json["normal_map"] = get_texturename_from_principled_input(principled.inputs['Normal'].links[0].from_node.inputs['Color'])
    except:
        pass
    
    if get_texturename_from_principled_input(principled.inputs['Alpha']) != False:
        mat_json["opacity_map"] = get_texturename_from_principled_input(principled.inputs['Alpha'])
        
    return mat_json

def log(str):
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S.%f")
    print("[python]", current_time, str)
    
def sceneTCP(scene, scene_path, render_instance):

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    server_address = ('127.0.0.1', 5557)
    print('connecting to {} port {}'.format(*server_address))
    sock.connect(server_address)
    print('connected!')

    response_bytes = bytearray()

    try:
        
        scene_load_msg = dict()
        scene_load_msg["type"] = "command"
        scene_load_msg["msg"] = "--load_object --path=" + scene_path
        
        write_message(scene_load_msg, sock)
        ack_message = read_message(sock) 
        
        if ack_message["type"] == "status" and ack_message["msg"] == "ok":
            print("Scene loaded")
            
        texture_queue = []
            
        for mat in bpy.data.materials:
            
            if compatible(mat):
            
                print("parsing ", mat.name)
                
                texture_queue.append(extractTextureNodesFromMat(mat))
                
                sendMaterial(sock, convertMaterial(mat))
                    
                ack_mat_message = read_message(sock) 
            
                if ack_mat_message["type"] == "status" and ack_mat_message["msg"] == "ok":
                    print(mat.name, " loaded")
            
            
        texture_queue = [item for sublist in texture_queue for item in sublist]
        texture_queue_non_dup = []
        [texture_queue_non_dup.append(x) for x in texture_queue if x not in texture_queue_non_dup]
        
        for tex_node in texture_queue_non_dup:
            log("Sending texture " + tex_node.name)
            sendTexture(sock, convertTextureNode(tex_node))
            log("Texture sent, waiting for ack")
            ack_mat_message = read_message(sock) 
            if ack_mat_message["type"] == "status" and ack_mat_message["msg"] == "ok":
                print(tex_node.name, " loaded")
            
        
                    
        render_start_msg = dict()
        render_start_msg["type"] = "command"
        render_start_msg["msg"] = "--start"       
        
        write_message(render_start_msg, sock)    
        ack_mat_message = read_message(sock) 
        
        time.sleep(0.5) 
        
        samples = 0
                
        while True:
            print("getting samples...")
            write_message(get_render_info_msg(), sock)
            info_msg = read_message(sock)
            if info_msg["type"] == "render_info":
                samples = json.loads(info_msg["msg"])["samples"]
                render_instance.update_progress(samples / TARGET_SAMPLES) 
                print(samples)
                
                get_pass_msg = dict()
                get_pass_msg["type"] = "command"
                get_pass_msg["msg"] = "--get_pass beauty" 
            
                write_message(get_pass_msg, sock)
                pass_message = read_message(sock)
                bytes = pass_message["additional_data"]["data"]
            
                result = render_instance.begin_result(0, 0, render_instance.size_x, render_instance.size_y)
                render_pass = result.layers[0].passes["Combined"]
            
                src = np.frombuffer(bytes, dtype=np.single)   
                src = src.ctypes.data_as(ctypes.c_void_p)
                dst = render_pass.as_pointer() + 96
                dst = ctypes.cast(dst, ctypes.POINTER(ctypes.c_void_p))
                ctypes.memmove(dst.contents, src, scene.render.resolution_x * scene.render.resolution_y * 4 * 4)
                                
                render_instance.end_result(result)
                
            else:
                break
            time.sleep(1) 
            
        
        get_pass_msg = dict()
        get_pass_msg["type"] = "command"
        get_pass_msg["msg"] = "--get_pass beauty" 
    
        write_message(get_pass_msg, sock)
        pass_message = read_message(sock) 
        
        if pass_message["type"] == "buffer":
            print("Scene loaded")    

    finally:
        print('closing socket')
        sock.close()
        

    #return pass_message["additional_data"]["data"]
    

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
        subprocess.Popen(ELEVEN_PATH, shell=True)

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

        result = self.begin_result(0, 0, self.size_x, self.size_y)
        layer = result.layers[0].passes["Combined"]
    
        export_scene(scene, "C:\\Users\\Kike\\Desktop\\TFM\\scenes\\SeaHouse")
        
        sceneTCP(scene,"C:\\Users\\Kike\\Desktop\\TFM\\scenes\\SeaHouse", self)    
          
        """               
        src = np.frombuffer(bytes, dtype=np.single)   
        src = src.ctypes.data_as(ctypes.c_void_p)
        render_pass = result.layers[0].passes["Combined"]
        dst = render_pass.as_pointer() + 96
        dst = ctypes.cast(dst, ctypes.POINTER(ctypes.c_void_p))
        ctypes.memmove(dst.contents, src, 1920 * 1080 * 4 * 4)
        self.end_result(result)
        """

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
        
        pixels = gpu.types.Buffer('FLOAT', width * height * 4)

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