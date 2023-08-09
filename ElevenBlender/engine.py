import bpy
import array
import gpu
import subprocess
import os
import addon_utils
import math
import time
import ctypes
import mmap

from .rendersocket import RenderSocket
from .message import * 



class ElevenEngine(bpy.types.RenderEngine):

    bl_idname = "ELEVEN"
    bl_label = "Eleven"
    bl_use_preview = False
    bl_use_shading_nodes_custom = False
    bl_use_eevee_viewport = True
    
    render_process = False
    eleven_socket = None
    scene = None
    addon_path = None

    # Init is called whenever a new render engine instance is created. Multiple
    # instances may exist at the same time, for example for a viewport and final
    # render.
    def __init__(self):
        # Eleven at the moment won't handle multiple instances.
        pass 
        

    # When the render engine instance is destroy, this is called. Clean up any
    # render engine data here, for example stopping running render threads.
    def __del__(self):
        pass
        
    # This is the method called by Blender for both final renders (F12) and
    # small preview for materials, world and lights.
    def render(self, depsgraph):
        
        self.update_stats("Eleven Render:", "Starting engine")
            
        try:
            filepath = ""
            for mod in addon_utils.modules():
                if mod.bl_info['name'] == "Eleven Render":
                    filepath = mod.__file__.replace("__init__.py", "bin\\ElevenRender.exe")
                    self.addon_path = filepath.replace("bin\\ElevenRender.exe", "")
                else:
                    pass
            print("Opening..." + filepath )
            self.render_process = subprocess.Popen(filepath, shell=True)
        except:
            self.report({"ERROR"}, "Eleven executable not found")
            return
    
        self.scene = depsgraph.scene
        scale = self.scene.render.resolution_percentage / 100.0
        self.size_x = int(self.scene.render.resolution_x * scale)
        self.size_y = int(self.scene.render.resolution_y * scale)      
                
        self.update_stats("Eleven Render:", "Connecting")
        print("Connecting to", self.scene.ip)
        self.eleven_socket = RenderSocket(self.scene.ip)
            
        self.eleven_socket.wait_ok()
            
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
        
        self.eleven_socket.write_message(StartMessage())
        self.eleven_socket.wait_ok()
        
        samples = 0
        
        print("Gettin samples!")
        
        while samples < self.scene.sample_target:
            print("Gettin samples")
            self.eleven_socket.write_message(GetInfoMessage())
            info_msg = self.eleven_socket.read_message()
            
            samples = info_msg["data"]["samples"]
            self.update_progress(samples / self.scene.sample_target) 
            print(samples, " samples")
        
            self.eleven_socket.write_message(GetPassMessage("beauty"))
            pass_msg = self.eleven_socket.read_message()
        
            result = self.begin_result(0, 0, self.size_x, self.size_y)
            render_pass = result.layers[0].passes["Combined"]
            
            src = pass_msg["data"].ctypes.data_as(ctypes.c_void_p)
            dst = render_pass.as_pointer() + 96
            dst = ctypes.cast(dst, ctypes.POINTER(ctypes.c_void_p))
            ctypes.memmove(dst.contents, src, self.scene.render.resolution_x * self.scene.render.resolution_y * 4 * 4)
                            
            self.end_result(result)
            
            time.sleep(1) 

        print("End")
        self.eleven_socket.disconnect()
        subprocess.Popen("TASKKILL /F /PID {pid} /T".format(pid=self.render_process.pid))

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
         
        
        self.eleven_socket.write_message(LoadCameraMessage())
        self.eleven_socket.write_message(CameraMessage(camera))         
        self.eleven_socket.wait_ok()
        
    def send_config(self):
        # Send config
        self.update_stats("Eleven Render:", "Sending config")
        
        config = dict()
        config["sample_target"] = self.scene.sample_target
        config["x_res"] = self.size_x
        config["y_res"] = self.size_y
        config["max_bounces"] = self.scene.max_bounces
        config["denoise"] = self.scene.denoise
        
        config_data_msg = ConfigMessage(config)
        load_config_message = LoadConfigMessage()
        
        self.eleven_socket.write_message(load_config_message)
        self.eleven_socket.write_message(config_data_msg)
        self.eleven_socket.wait_ok()

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
            
            self.eleven_socket.write_message(load_hdri_msg)
            self.eleven_socket.write_message(hdri_metadata_msg)
            #self.eleven_socket.wait_ok()
            self.eleven_socket.write_message(hdri_data_msg)
            self.eleven_socket.wait_ok()
        else:
            #Quick ugly patch for color environment. In the future, Environment will work with shaders.
            env_color = bpy.context.scene.world.node_tree.nodes['Background'].inputs[0].default_value
            image = bpy.data.images.new("hdri_color", width=1, height=1, float_buffer=True)
            image.pixels = [env_color[0], env_color[1], env_color[2], 1]          
            self.eleven_socket.write_message(LoadHDRIMessage())
            self.eleven_socket.write_message(TextureMetadataMessage(image))
            #self.eleven_socket.wait_ok()
            self.eleven_socket.write_message(TextureDataMessage(image))
            self.eleven_socket.wait_ok()
            bpy.data.images.remove(image)


    def extract_materials(self):
        materials = set()
        self.update_stats("Eleven Render:", "Getting materials")
        print("Getting materials")
        
        # Get all compatible materials from every object
        for obj in self.scene.objects:
            if obj.type == "MESH":
                if len(obj.material_slots) > 1:
                    self.report({"WARNING"}, str(obj.name) + " has more than one material. Only the first material slot will be used")
                    materials.add(obj.material_slots[0].material)
                elif len(obj.material_slots) == 0:
                    self.report({"WARNING"}, str(obj.name) + " has no materials")
                    
                elif not compatible(obj.material_slots[0].material):
                    self.report({"WARNING"}, str(obj.material_slots[0].material.name) + " is not compatible with Eleven")
                else:
                    materials.add(obj.material_slots[0].material)
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
        self.eleven_socket.write_message(LoadTextureMessage())
        self.eleven_socket.write_message(TextureMetadataMessage(texture))
        
        with open("shm", mode="a+", encoding="utf-8") as file_obj:
            file_obj.seek(0)
            with mmap.mmap(file_obj.fileno(), length= texture.size[0] * texture.size[1] * texture.channels * 4, access=mmap.ACCESS_COPY) as mmap_obj:
                msg = TextureDataMessage(texture)                    
                msg_data_bytes = msg.data_serialized() 
                mmap_obj.write(msg_data_bytes)
                    
        self.eleven_socket.wait_ok()

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
                        
            self.eleven_socket.write_message(LoadTextureMessage())
            self.eleven_socket.write_message(TextureMetadataMessage(tex))      
            self.eleven_socket.write_message(TextureDataMessage(tex))
            self.eleven_socket.wait_ok()
            

    def send_materials(self, materials):
        self.update_stats("Eleven Render:", "Sending materials")
        print("Sending materials")
        
        # Send each material to Eleven
        for mat in materials:
        
            bsdf = mat.node_tree.nodes["Principled BSDF"]
        
            p_base_color = bsdf.inputs['Base Color'].default_value
            p_metalness = bsdf.inputs['Metallic'].default_value
            p_roughness = bsdf.inputs['Roughness'].default_value
            p_specular = bsdf.inputs['Specular'].default_value
            p_opacity = bsdf.inputs['Alpha'].default_value
            p_emission_color = bsdf.inputs['Emission'].default_value
            p_emission_strength = bsdf.inputs['Emission Strength'].default_value
            
            albedo_map = get_imagename(bsdf, "Base Color")
            metallic_map = get_imagename(bsdf, "Metallic")
            roughness_map = get_imagename(bsdf, "Roughness")
            emssion_map = get_imagename(bsdf, "Emission")
            opacity_map = get_imagename(bsdf, "Alpha")
            normal_map = get_imagename(bsdf, "Normal")
            
            
            json_mat = dict()
            json_mat["name"] = mat.name
            json_mat["albedo"] = {"r":p_base_color[0], "g":p_base_color[1], "b":p_base_color[2]}
            json_mat["metalness"] = p_metalness
            json_mat["roughness"] = p_roughness
            json_mat["specular"] = p_specular
            json_mat["emission"] = {"r":p_emission_color[0] * p_emission_strength, "g":p_emission_color[1] * p_emission_strength, "b":p_emission_color[2] * p_emission_strength}
                
            if albedo_map :
                json_mat["albedo_map"] = albedo_map
            
            if metallic_map :
                json_mat["metallic_map"] = metallic_map
                
            if roughness_map :
                json_mat["roughness_map"] = roughness_map
                
            if emssion_map :
                json_mat["emssion_map"] = emssion_map
            
            if opacity_map :
                json_mat["opacity_map"] = opacity_map
                
            if normal_map :
                json_mat["normal_map"] = normal_map
        
            self.eleven_socket.write_message(LoadBrdfMaterialMessage())
            self.eleven_socket.write_message(BrdfMaterialMessage(json_mat))
            self.eleven_socket.wait_ok()
        

    def send_objects(self):
        self.update_stats("Eleven Render:", "Exporting .obj")
        print("Exporting .obj")
        bpy.ops.export_scene.obj(filepath=self.addon_path + "temp\\scene.obj", use_triangles=True, path_mode='ABSOLUTE')        
        self.eleven_socket.write_message(LoadObjectMessage(self.addon_path + "temp\\scene.obj", self.scene.normals))
        self.eleven_socket.wait_ok()
        

    

def compatible(mat):
    try:
        next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        return True
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
  
def extract_textures_from_mat(mat):
    
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    
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