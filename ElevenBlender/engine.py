import bpy
import array
import gpu
import os
import addon_utils
import math
import time
import ctypes
import mmap
import subprocess

from .rendersocket import RenderSocket
from .message import * 
from .panel import ElevenPanel

def get_eleven_bin_path():
    for mod in addon_utils.modules():
        if mod.bl_info['name'] == "Eleven Render":
            return mod.__file__.replace("__init__.py", "bin\\ElevenRender.exe")

def get_eleven_addon_path():
    return get_eleven_bin_path().replace("bin\\ElevenRender.exe", "")

def scene_update_handler(dummy):
    bpy.context.scene.my_update_flag = True

def quick_pass_move(origin, pass_dest, width, height):
    src = origin.ctypes.data_as(ctypes.c_void_p)
    dst = pass_dest.as_pointer() + 96
    dst = ctypes.cast(dst, ctypes.POINTER(ctypes.c_void_p))
    ctypes.memmove(dst.contents, src, width * height * 4 * 4)

bpy.types.Scene.my_update_flag = bpy.props.BoolProperty(default=True)
bpy.app.handlers.render_init.append(scene_update_handler)

class SCENE_OT_watch_changes(bpy.types.Operator):
    bl_idname = "scene.watch_changes"
    bl_label = "Watch for Changes"

    def modal(self, context, event):
        if bpy.context.scene.my_update_flag and bpy.context.scene.render.engine == "ELEVEN":
            # Way faster but broken in 3.4 because some line jumps.
            
            print("exporting")
            bpy.ops.wm.obj_export(filepath=get_eleven_addon_path() + "temp\\scene.obj", path_mode='ABSOLUTE', export_triangulated_mesh=True)
                
            bpy.context.scene.my_update_flag = False

            
        return {'PASS_THROUGH'}

    def execute(self, context):
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        bpy.app.handlers.render_init.remove(scene_update_handler)

class ShaderSelectorNode(bpy.types.Node):
    bl_idname = 'ShaderSelectorNode'
    bl_label = 'Eleven Shader Selector node'

    value: bpy.props.IntProperty(
        name="Shader ID",
        default=-1,
        description="Shader ID value")

    def init(self, context):
        self.outputs.new('NodeSocketColor', 'Output')
        
    def draw_buttons(self, context, layout):
        layout.prop(self, 'value')

class RunInstanceOperator(bpy.types.Operator):

    bl_idname = "eleven.run_instance_operator"
    bl_label = "Run Instance Operator"

    def execute(self, context):     
        filepath = get_eleven_bin_path()
        global render_process
        render_process = subprocess.Popen(filepath, shell=True)
        self.report({'INFO'}, "Opened " + filepath)
        return {'FINISHED'}

class ConnectOperator(bpy.types.Operator):

    bl_idname = "eleven.connect_operator"
    bl_label = "Connect Operator"

    def execute(self, context):     

        global connect_context
        connect_context = context

        print("Connecting to", context.scene.ip)
        global eleven_socket
        eleven_socket = RenderSocket(context.scene.ip)
        eleven_socket.wait_ok()
        
        eleven_socket.write_message(GetSyclInfoMessage())
        info_msg = eleven_socket.read_message()
                
        ElevenPanel.devices = []
        
        print(info_msg)
        
        for device in info_msg["data"]["devices"] :
            device_str = device["name"] + "|" + device["platform"]
            if device["is_compatible"]:   
                ElevenPanel.devices.append((device_str,device_str,device_str))
            else:
                self.report({'WARNING'}, "Found an incompatible device: " + device_str)

        context.scene.connection_status = "connected"
        return {'FINISHED'}

class DisconnectOperator(bpy.types.Operator):

    bl_idname = "eleven.disconnect_operator"
    bl_label = "Disconnect Operator"

    def execute(self, context):
        try:
            eleven_socket.disconnect()
            subprocess.Popen("TASKKILL /F /PID {pid} /T".format(pid=render_process.pid))
            self.report({'INFO'}, "Disconnected succesfully ")
        except:
            pass
           
        bpy.context.scene.my_update_flag = True
        context.scene.connection_status = "disconnected"
        return {'FINISHED'}




class ElevenEngine(bpy.types.RenderEngine):

    bl_idname = "ELEVEN"
    bl_label = "Eleven"
    bl_use_preview = False
    bl_use_shading_nodes_custom = False
    bl_use_eevee_viewport = True
    
    addon_path = get_eleven_addon_path()

    instance_count = 0

    # Init is called whenever a new render engine instance is created. Multiple
    # instances may exist at the same time, for example for a viewport and final
    # render.
    def __init__(self):
        self.instance_id = ElevenEngine.instance_count
        print("Eleven instance ", self.instance_id, " created")
        ElevenEngine.instance_count = ElevenEngine.instance_count + 1
            

    # When the render engine instance is destroy, this is called. Clean up any
    # render engine data here, for example stopping running render threads.
    def __del__(self):
        #if ElevenEngine.instance_count == 1:
        #    eleven_socket.disconnect()
        #    subprocess.Popen("TASKKILL /F /PID {pid} /T".format(pid=render_process.pid))
        ElevenEngine.instance_count = ElevenEngine.instance_count - 1
 
    def update_render_passes(self, scene=None, renderlayer=None):
        self.register_pass(scene, renderlayer, "Combined", 4, "RGBA", 'COLOR')
        self.register_pass(scene, renderlayer, "Normal", 4, "RGBA", 'COLOR')

    def update_passes_result(self):
        eleven_socket.write_message(GetPassMessage("beauty"))
        beauty_msg = eleven_socket.read_message()
        
        eleven_socket.write_message(GetPassMessage("normal"))
        normal_msg = eleven_socket.read_message()
        
        result = self.begin_result(0, 0, self.size_x, self.size_y)
        
        beauty_pass = result.layers[0].passes["Combined"]
        normal_pass = result.layers[0].passes["Normal"]
        
        # https://github.com/blender/blender/blob/main/source/blender/render/RE_pipeline.h
        # RenderPass is now handled differently.
        if bpy.app.version < (4, 0, 0) :
            quick_pass_move(beauty_msg["data"], beauty_pass, self.scene.render.resolution_x, self.scene.render.resolution_y)
            quick_pass_move(normal_msg["data"], normal_pass, self.scene.render.resolution_x, self.scene.render.resolution_y)
        else:
            beauty_pass.rect = beauty_msg["data"].reshape(-1, 4).tolist()
            beauty_pass.rect = normal_msg["data"].reshape(-1, 4).tolist()
                  
        self.end_result(result)

    # This is the method called by Blender for both final renders (F12) and
    # small preview for materials, world and lights.
    def render(self, depsgraph):
         
        while(bpy.context.scene.my_update_flag):
            time.sleep(0.5)
          
        self.scene = depsgraph.scene
        scale = self.scene.render.resolution_percentage / 100.0
        self.size_x = int(self.scene.render.resolution_x * scale)
        self.size_y = int(self.scene.render.resolution_y * scale)      
            
        self.send_camera()
        self.send_config()
        self.send_hdri()
                
        materials = self.extract_materials()
        textures = self.extract_textures(materials)
        
        self.send_textures(textures)
        self.send_materials(materials)
        self.send_objects()
        
        self.update_stats("Eleven Render:", "Starting rendering")
        print("Starting rendering")
        
        eleven_socket.write_message(StartMessage())
        eleven_socket.wait_ok()
        
        samples = 0
        
        time.sleep(1)
        
        print("Getting samples!")
        
        while samples < self.scene.sample_target:
            print("Gettin samples")
            eleven_socket.write_message(GetInfoMessage())
            info_msg = eleven_socket.read_message()
            
            samples = info_msg["data"]["samples"]
            self.update_progress(samples / self.scene.sample_target) 
            print(samples, " samples")
        
            self.update_passes_result()
            
            time.sleep(1) 

        self.update_passes_result()


    

    def send_camera(self):
        #TODO: Blender uses two different types for handling cameras. Object and Camera. For the moment I don't know how to relationate both.
        #Camera setup:
        b_cam_loc = bpy.data.objects['Camera'].location
        b_cam_rot = bpy.data.objects['Camera'].rotation_euler 

        camera = dict()

        camera['position'] = {'x':b_cam_loc.x,'y':b_cam_loc.z,'z':b_cam_loc.y}
        camera['rotation'] = {'x': 90 - b_cam_rot.x / (math.pi/180), 'y':-b_cam_rot.z / (math.pi/180), 'z': -b_cam_rot.y / (math.pi/180)}

        camera['focal_length'] = bpy.data.cameras[0].lens/1000
        camera['focus_distance'] = bpy.data.cameras[0].dof.focus_distance
        camera['aperture'] = bpy.data.cameras[0].dof.aperture_fstop
        camera['bokeh'] = bpy.data.cameras[0].dof.use_dof
        
        aspect_ratio = float(self.size_x) / float(self.size_y)
        sensor_aspect_ration = float(bpy.data.cameras[0].sensor_width) / float(bpy.data.cameras[0].sensor_height)
        
        sf = bpy.data.cameras[0].sensor_fit
           
        if sf == 'AUTO' :
            sensor_size = bpy.data.cameras[0].sensor_width
            
        if sf == 'HORIZONTAL':
            sensor_size = bpy.data.cameras[0].sensor_width
            
        if sf == 'VERTICAL' :
            sensor_size = bpy.data.cameras[0].sensor_height

         
        if sf == 'AUTO' :
            sf = 'HORIZONTAL' if self.size_x >= self.size_y else 'VERTICAL'
            #sf = 'HORIZONTAL' if bpy.data.cameras[0].sensor_width < bpy.data.cameras[0].sensor_height else 'VERTICAL'
            
        if sf == 'HORIZONTAL':
            camera['sensor_width'] = sensor_size / 1000
            camera['sensor_height'] =camera['sensor_width'] / aspect_ratio
            
        if sf == 'VERTICAL' :
            camera['sensor_height'] = sensor_size / 1000
            camera['sensor_width'] =camera['sensor_height'] * aspect_ratio
         
        
        eleven_socket.write_message(LoadCameraMessage())
        eleven_socket.write_message(CameraMessage(camera))         
        eleven_socket.wait_ok()
       
    
    def send_config(self):
        # Send config
        self.update_stats("Eleven Render:", "Sending config")
        
        config = dict()
        config["sample_target"] = self.scene.sample_target
        config["x_res"] = self.size_x
        config["y_res"] = self.size_y
        config["max_bounces"] = self.scene.max_bounces
        config["denoise"] = self.scene.denoise
        config["device"] = self.scene.device
        config["block_size"] = self.scene.block_size
        config["frame"] = int(self.scene.frame_float)
        config["fps"] = int(self.scene.render.fps)
        
        
        print(config)
        
        config_data_msg = ConfigMessage(config)
        load_config_message = LoadConfigMessage()
        
        eleven_socket.write_message(load_config_message)
        eleven_socket.write_message(config_data_msg)
        eleven_socket.wait_ok()

    def send_hdri(self):
        # Send HDRI:
        # TODO: See what the hell happened with the xOffset (?)
        self.update_stats("Eleven Render:", "Sending environment")
        print("Sending environment")
        
        if bpy.context.scene.world.node_tree.nodes.find('Environment Texture') != -1:
            hdri_tex = bpy.context.scene.world.node_tree.nodes['Environment Texture'].image
            hdri_metadata_msg = TextureMetadataMessage(hdri_tex)
            hdri_data_msg = TextureDataMessage(hdri_tex)
            load_hdri_msg = LoadHDRIMessage()
            
            eleven_socket.write_message(load_hdri_msg)
            eleven_socket.write_message(hdri_metadata_msg)
            #eleven_socket.wait_ok()
            eleven_socket.write_message(hdri_data_msg)
            eleven_socket.wait_ok()
        else:
            #Quick ugly patch for color environment. In the future, Environment will work with shaders.
            env_color = bpy.context.scene.world.node_tree.nodes['Background'].inputs[0].default_value
            image = bpy.data.images.new("hdri_color", width=1, height=1, float_buffer=True)
            image.pixels = [env_color[0], env_color[1], env_color[2], 1]          
            eleven_socket.write_message(LoadHDRIMessage())
            eleven_socket.write_message(TextureMetadataMessage(image))
            #eleven_socket.wait_ok()
            eleven_socket.write_message(TextureDataMessage(image))
            eleven_socket.wait_ok()
            bpy.data.images.remove(image)


    def extract_materials(self):
        materials = set()
        self.update_stats("Eleven Render:", "Getting materials")
        print("Getting materials")
        
        # Get all compatible materials from every object
        for obj in self.scene.objects:
            if obj.type == "MESH":

                if len(obj.material_slots) == 0:
                    self.report({"WARNING"}, str(obj.name) + " has no materials")
            
                for material_slot in obj.material_slots:
                    if material_slot.material == None:
                        self.report({"WARNING"}, "Material not found")                 
                    elif not compatible(material_slot.material):
                        self.report({"WARNING"}, str(material_slot.material.name) + " is not compatible with Eleven")
                    else:
                        materials.add(material_slot.material)

        return materials

    def extract_textures(self, materials):
        textures = set()
        self.update_stats("Eleven Render:", "Extracting textures")
        print("Extracting textures")
    
        # Get all relevant textures from each material
        for mat in materials:
            # TODO: I don't really know how an image set behaves. I should check what happens in different cases.
            # TODO: Image names are not UNIQUE. Texture conflict can happen!
            mat_textures = extract_textures_from_mat(mat)
            
            for tex in mat_textures:
                textures.add(tex)
        return textures

    def send_texture_sm(self, texture):
        eleven_socket.write_message(LoadTextureMessage())
        eleven_socket.write_message(TextureMetadataMessage(texture))
        
        with open("shm", mode="a+", encoding="utf-8") as file_obj:
            file_obj.seek(0)
            with mmap.mmap(file_obj.fileno(), length= texture.size[0] * texture.size[1] * texture.channels * 4, access=mmap.ACCESS_COPY) as mmap_obj:
                msg = TextureDataMessage(texture)                    
                msg_data_bytes = msg.data_serialized() 
                mmap_obj.write(msg_data_bytes)
                    
        eleven_socket.wait_ok()

    def send_textures(self, textures):
        self.update_stats("Eleven Render:", "Sending textures")
        print("Sending textures")
        
        # Send each texture to Eleven
        for tex in textures:
            
            # Eleven requires unique texture names. 
            for tex2 in textures:
                if tex.name == tex2.name and tex != tex2:
                    self.report({"WARNING"}, "There is more than one texture with the name: " + str(tex.name))
            
            self.update_stats("Eleven Render:", "Sending " + str(tex.name))
            print("Sending " + str(tex.name))
                       
            old_width  = tex.size[0]
            old_height = tex.size[1]
              
            ds = int(self.scene.tex_downscale)
              
            if ds > 0 and tex.has_data and (old_width > ds or old_height > ds)  :
                scale = ds / max(old_width, old_height)
                tex.scale(int(old_width * scale), int(old_height * scale))

            eleven_socket.write_message(LoadTextureMessage())
            eleven_socket.write_message(TextureMetadataMessage(tex))      
            eleven_socket.write_message(TextureDataMessage(tex))
            eleven_socket.wait_ok()
                        
            if ds > 0 and tex.has_data and (old_width > ds or old_height > ds)  :
                try:
                    tex.reload()
                except:
                    print("error reloading")
            
             

    def send_materials(self, materials):
        self.update_stats("Eleven Render:", "Sending materials")
        print("Sending materials")
        
        # Send each material to Eleven
        for mat in materials:
        
            bsdf = mat.node_tree.nodes['Material Output'].inputs['Surface'].links[0].from_node
        
            p_base_color = bsdf.inputs['Base Color'].default_value
            p_metalness = bsdf.inputs['Metallic'].default_value
            p_roughness = bsdf.inputs['Roughness'].default_value
            p_specular = bsdf.inputs['Specular'].default_value
            p_opacity = bsdf.inputs['Alpha'].default_value
            p_emission_color = bsdf.inputs['Emission'].default_value
            p_emission_strength = bsdf.inputs['Emission Strength'].default_value
            p_transmission = bsdf.inputs['Transmission'].default_value
            
            albedo_map = get_imagename(bsdf, "Base Color")
            metallic_map = get_imagename(bsdf, "Metallic")
            roughness_map = get_imagename(bsdf, "Roughness")
            emission_map = get_imagename(bsdf, "Emission")
            opacity_map = get_imagename(bsdf, "Alpha")
            normal_map = get_imagename(bsdf, "Normal")
            transmission_map = get_imagename(bsdf, "Transmission")
            
                        
            json_mat = dict()
            
            json_mat["albedo_shader_id"] = get_shaderid(bsdf, "Base Color")
            json_mat["metallic_shader_id"] = get_shaderid(bsdf, "Metallic")
            json_mat["roughness_shader_id"] = get_shaderid(bsdf, "Roughness")
            json_mat["emission_shader_id"] = get_shaderid(bsdf, "Emission")
            json_mat["alpha_shader_id"] = get_shaderid(bsdf, "Alpha")
            json_mat["normal_shader_id"] = get_shaderid(bsdf, "Normal")
            json_mat["transmission_shader_id"] = get_shaderid(bsdf, "Transmission")

            json_mat["name"] = mat.name
            json_mat["albedo"] = {"r":p_base_color[0], "g":p_base_color[1], "b":p_base_color[2]}
            json_mat["metalness"] = p_metalness
            json_mat["roughness"] = p_roughness
            json_mat["transmission"] = p_transmission
            json_mat["specular"] = p_specular
            json_mat["emission"] = {"r":p_emission_color[0] * p_emission_strength, "g":p_emission_color[1] * p_emission_strength, "b":p_emission_color[2] * p_emission_strength}
               
            if albedo_map :
                json_mat["albedo_map"] = albedo_map
            
            if metallic_map :
                json_mat["metallic_map"] = metallic_map
                
            if roughness_map :
                json_mat["roughness_map"] = roughness_map
                
            if emission_map :
                json_mat["emission_map"] = emission_map
            
            if opacity_map :
                json_mat["opacity_map"] = opacity_map
                
            if normal_map :
                json_mat["normal_map"] = normal_map
                
            if transmission_map :
                json_mat["transmission_map"] = transmission_map
        
            eleven_socket.write_message(LoadBrdfMaterialMessage())
            eleven_socket.write_message(BrdfMaterialMessage(json_mat))
            eleven_socket.wait_ok()
    
    def send_objects(self):
        self.update_stats("Eleven Render:", "Exporting .obj")
        print("Exporting .obj")
                        
        with open(get_eleven_addon_path() + "temp\\scene.obj", 'r') as f:
            lines = f.readlines()

        # Filter out the unwanted lines
        lines = [line for line in lines if not (line.startswith("usemtl") and line.strip().split()[-1] == "usemtl")]

        # Write the processed lines back to the file
        with open(get_eleven_addon_path() + "temp\\scene.obj", 'w') as f:
            f.writelines(lines)
                
        with open(get_eleven_addon_path() + "temp\\scene.obj", 'rb') as f:
            obj_data = f.read()
        with open(get_eleven_addon_path() + "temp\\scene.mtl", 'r') as f:
            mtl_data = f.read()
        
        eleven_socket.write_message(LoadObjectMessageTCP(self.scene.normals))
        eleven_socket.write_message(ObjDataMessage(obj_data))
        #eleven_socket.write_message(ObjDataMessage(bytes(trim_wavefront_mtls(mtl_data.replace("/", "\\")), 'utf-8') + b'\00'))
        eleven_socket.write_message(ObjDataMessage(bytes(mtl_data.replace("/", "\\"), 'utf-8') + b'\00'))
        eleven_socket.wait_ok()
        
        #os.remove(get_eleven_addon_path() + "temp\\scene.obj")
        #os.remove(get_eleven_addon_path() + "temp\\scene.mtl")

    

def compatible(mat):
    try:
        if mat.node_tree.nodes['Material Output'].inputs['Surface'].links[0].from_node.type == 'BSDF_PRINCIPLED':
            return True
        else:
            return False
    except:
        return False
        
  
def get_imagename(bsdf, att):
    try:
        tex_node = bsdf.inputs[att].links[0].from_node
        if tex_node.type =='TEX_IMAGE':
            return tex_node.image.name
        if tex_node.type == 'NORMAL_MAP':
            return tex_node.inputs['Color'].links[0].from_node.image.name
    except:
        return False
        
def get_shaderid(bsdf, att):
    try:
        shader_id_node = bsdf.inputs[att].links[0].from_node
        if shader_id_node.bl_idname =='ShaderSelectorNode':
            return shader_id_node.value
    except:
        return -1
    return -1
  
def extract_textures_from_mat(mat):
        
    bsdf = mat.node_tree.nodes['Material Output'].inputs['Surface'].links[0].from_node
    
    texs = []
    
    for input in bsdf.inputs:
        if input.links:
            tex_node = input.links[0].from_node
            if tex_node.type =='TEX_IMAGE':
                texs.append(tex_node.image)
            if tex_node.type == 'NORMAL_MAP':
                try:
                    texs.append(tex_node.inputs['Color'].links[0].from_node.image)
                except:
                    pass
    
    return texs
  
def trim_wavefront_mtls(istr):
    str = ""
    
    for line in istr.splitlines():
        print("parsing line ", line)
        if "newmtl" in line :
            print("Line appended")
            str = str + line + "\n"
    return str