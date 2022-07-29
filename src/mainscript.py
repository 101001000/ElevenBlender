import bpy
import array
import gpu
import json
import subprocess
import sys
import os
import math
import imageio
import numpy as np
from gpu_extras.presets import draw_texture_2d




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

        # Fill the render result with a flat color. The framebuffer is
        # defined as a list of pixels, each pixel itself being a list of
        # R,G,B,A values.
        if self.is_preview:
            color = [0.1, 0.2, 0.1, 1.0]
        else:
            color = [1, 0, 0, 1.0]

        pixel_count = self.size_x * self.size_y
        rect = [color] * pixel_count
                        
        print("Starting rendering proccess")
    
        scene_object = dict()
        
        #Camera setup:
        b_cam_loc = bpy.data.objects['Camera'].location
        b_cam_rot = bpy.data.objects['Camera'].rotation_euler 
        
        scene_object['camera'] = dict()
                
        scene_object['camera']['xRes'] = scene.render.resolution_x
        scene_object['camera']['yRes'] = scene.render.resolution_y
        
        scene_object['camera']['position'] = {'x':b_cam_loc.x,'y':b_cam_loc.z,'z':b_cam_loc.y}
        scene_object['camera']['rotation'] = {'x': 90 - b_cam_rot.x / (math.pi/180), 'y':-b_cam_rot.z / (math.pi/180), 'z': -b_cam_rot.y / (math.pi/180)}

        scene_object['camera']['focalLength'] = 0.05
        scene_object['camera']['focusDistance'] = 0.69
        scene_object['camera']['aperture'] = 2.8
        scene_object['camera']['bokeh'] = "false"
        
        
        #Hdri setup:
        
        scene_object['hdri'] = dict()
          
        if bpy.context.scene.world.node_tree.nodes.find('Environment Texture') != -1:
            pass
        else:
            b_env_color = bpy.context.scene.world.node_tree.nodes['Background'].inputs[0].default_value
            scene_object['hdri']['color'] = {'r':b_env_color[0], 'g':b_env_color[1], 'b':b_env_color[2]}        
        
        
        objs = bpy.context.scene.objects
        
        rendering_path = "C:\\Users\\Kike\\Desktop\\TFM\\scenes\\blenderTest"
        output_file_path = "C:\\Users\\Kike\\Desktop\\TFM\\repos\\ElevenRender\\output.png"
        
        proc = '"C:\\Users\\Kike\\Desktop\\TFM\\repos\\ElevenRender\\ElevenRender.exe" "' + rendering_path  + '" 50 "' + output_file_path + '"'

        print(proc)

        """

        arr = np.fromiter([1.1], dtype=np.single)
        bytedata = arr.tobytes()
        print(arr)
        print(bytedata)
        print("\n byte data: ", bytedata[0], " - ", bytedata[1], " - ", bytedata[2], " - ", bytedata[3], "\n")

        """

        #pipe = subprocess.Popen(proc, shell=False, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=4096*4096*4*4)
        
        #print(pipe.communicate(input=b'one\ntwo\nthree\nfour\nfive\nsix\n')[0])
        
        """
        
        for obj in objs:
        
            if obj.name != "Camera":
                for node in obj.active_material.node_tree.nodes:
                    if node.type == 'TEX_IMAGE':
                        print("Sending img", node.image)
                        floatdata = np.fromiter(node.image.pixels, dtype=np.single)
    
                        
                        bytedata = floatdata.tobytes()

                        print(pipe.communicate(input=bytedata)[0])
                        #print("first value: ", node.image.pixels[0], " and ", floatdata[0], "\n byte data: ", bytedata[0], " - ", bytedata[1], " - ", bytedata[2], " - ", bytedata[3], "\n")

                        #for i in range(0, len(bytedata), chunksize): 
                        #    print(pipe.communicate(input=bytedata[i:i+chunksize])[0])
                        break
                        
                break   

        """    

        bpy.ops.export_scene.obj(filepath=rendering_path + "\\scene.obj", use_triangles=True, path_mode='ABSOLUTE')            
        
        with open(rendering_path + "\\scene.json", 'w') as fs:
            fs.write(json.dumps(scene_object))
            
      
        subprocess.run(proc, shell=True, check=False)

        #img = imageio.imread(output_file_path)/255.0
        #img = np.flip(img, axis=0)
        #img = img.reshape(self.size_x * self.size_y, 3)
        #img = np.concatenate((img, np.ones((self.size_x * self.size_y, 1))), axis=1)

        
        
        # Here we write the pixel values to the RenderResult
        result = self.begin_result(0, 0, self.size_x, self.size_y)
        layer = result.layers[0].passes["Combined"]
        #layer.rect = img
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