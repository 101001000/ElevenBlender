import bpy
import array
import gpu
import subprocess
import os
import addon_utils


from .rendersocket import RenderSocket
from .message import Message


class ElevenEngine(bpy.types.RenderEngine):

    bl_idname = "ELEVEN"
    bl_label = "Eleven"
    bl_use_preview = False
    
    render_process = False

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
                else:
                    pass
            print("Opening..." + filepath)
            render_process = subprocess.Popen(filepath, shell=True)
        except:
            self.report({"ERROR"}, "Eleven executable not found")
            return
    
        scene = depsgraph.scene
        scale = scene.render.resolution_percentage / 100.0
        self.size_x = int(scene.render.resolution_x * scale)
        self.size_y = int(scene.render.resolution_y * scale)      
        
        sample_target = scene.sample_target
        denoise = scene.denoise
        x_res = self.size_x
        y_res = self.size_y
        max_bounces = scene.max_bounces
        ip = scene.ip
        
        self.update_stats("Eleven Render:", "Connecting")
        
        
        eleven_socket = RenderSocket(ip)
                
        # Send config
        self.update_stats("Eleven Render:", "Sending config")
        
        config = dict()
        config["sample_target"] = sample_target
        config["x_res"] = x_res
        config["y_res"] = y_res
        config["max_bounces"] = max_bounces
        
        config_data_msg = Message.ConfigDataMessage(config)
        send_config_message = Message.SendConfigMessage(mode="tcp")

        config_data_msg.print()
        send_config_message.print()
        
        eleven_socket.write_message(send_config_message)
        eleven_socket.write_message(config_data_msg)
        eleven_socket.wait_ok()
        
        
        # Send HDRI:
        # TODO: See what the hell happened with the xOffset (?)
        self.update_stats("Eleven Render:", "Sending environment")
        
        if bpy.context.scene.world.node_tree.nodes.find('Environment Texture') != -1:
            hdri_tex = bpy.context.scene.world.node_tree.nodes['Environment Texture'].image
            hdri_metadata_msg = Message.TextureMetadataMessage(hdri_tex)
            hdri_data_msg = Message.TextureDataMessage(hdri_tex)
            send_hdri_msg = Message.SendHDRIMessage(mode="tcp")
            
            eleven_socket.write_message(send_hdri_msg)
            eleven_socket.write_message(hdri_metadata_msg)
            eleven_socket.write_message(hdri_data_msg)
            eleven_socket.wait_ok()
        else:
            # TODO: Send environment color
            self.report({"WARNING"}, "Non compatible environment has been choosen. Default gray will be used")
            pass        
    
        
        material = set()
        textures = set()
        
        self.update_stats("Eleven Render:", "Getting materials")
        
        # Get all compatible materials from every object
        for obj in scene.objects:
            if obj.type == "MESH":
                if len(obj.material_slots) > 1:
                    self.report({"WARNING"}, str(obj.name) + " has more than one material. Only the first material slot will be used")
            
                elif len(obj.material_slots) == 0:
                    self.report({"WARNING"}, str(obj.name) + " has no materials")
                
                elif not compatible(obj.material_slots[0].material):
                    self.report({"WARNING"}, str(obj.material_slots[0].material.name) + " is not compatible with Eleven")
                else:
                    materials.add(obj.material_slots[0].material)

    
        self.update_stats("Eleven Render:", "Extracting textures")
    
        # Get all relevant textures from each material
        for mat in materials:
            # TODO: I don't really know how an image set behaves. I should check what happens in different cases.
            # TODO: Image names are not UNIQUE. Texture conflict can happen!
            mat_textures = extract_textures_from_mat(mat)
            
            for tex in mat_textures:
                textures.add(tex)
        
        
        self.update_stats("Eleven Render:", "Sending textures")
        
        # Send each texture to Eleven
        for tex in textures:
            
            # Eleven requires unique texture names. 
            for tex2 in textures:
                if tex.name == tex2.name and tex != tex2:
                    self.report({"WARNING"}, "There is more than one texture with the name: " + str(tex.name))
            
            self.update_stats("Eleven Render:", "Sending " + str(tex.name))
            
            metadata_msg = Message.TextureMetadataMessage(tex)
            data_msg = Message.TextureDataMessage(tex)
            send_msg = Message.SendTextureCommandMessage(mode="tcp")
            
            eleven_socket.write_message(metadata_msg)
            eleven_socket.write_message(data_msg)
            eleven_socket.write_message(send_msg)
            
            eleven_socket.wait_ok()
        
        
        self.update_stats("Eleven Render:", "Sending materials")
        
        # Send each material to Eleven
        for mat in materials:
            pass
        

        # Fill the render result with a flat color. The framebuffer is
        # defined as a list of pixels, each pixel itself being a list of
        # R,G,B,A values.
        if self.is_preview:
            color = [0.1, 0.2, 0.1, 1.0]
        else:
            color = [0.2, 0.1, 0.1, 1.0]

        pixel_count = self.size_x * self.size_y
        rect = [color] * pixel_count

        # Here we write the pixel values to the RenderResult
        result = self.begin_result(0, 0, self.size_x, self.size_y)
        layer = result.layers[0].passes["Combined"]
        layer.rect = rect
        self.end_result(result)


def compatible(mat):
    try:
        next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        return True
    except:
        return False
        
  
def extract_textures_from_mat(mat):
    
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    
    texs = []
    
    for input in bsdf.inputs:
        if input.links:
            tex_node = input.links[0].from_node
            if tex_node.type =='TEX_IMAGE':
                texs.append(tex_node)
            if tex_node.type == 'NORMAL_MAP':
                try:
                    texs.append(tex_node.inputs['Color'].links[0].from_node.image)
                except:
                    pass
    
    return texs