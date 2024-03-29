import bpy

def get_devices(self, context):
    return ElevenPanel.devices
        

class ElevenPanel(bpy.types.Panel):
    bl_idname = "RENDER_PT_eleven"
    bl_label = "Eleven"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "render"

    devices = []

    def __init__(self):
        bpy.types.Scene.denoise = bpy.props.BoolProperty(name="Denoise (Open AI Denoise)")
        bpy.types.Scene.sample_target = bpy.props.IntProperty(name="Sample Target", default=100)
        bpy.types.Scene.block_size = bpy.props.IntProperty(name="Block Size", default=8)
        bpy.types.Scene.ip = bpy.props.StringProperty(name="Ip", default="127.0.0.1:5557")
        bpy.types.Scene.normals = bpy.props.EnumProperty(name="Recompute Normals",
                items=(
                    ("None", "None", "Use Blender's computed normals"),
                    ("Face Weighted", "Face Weighted", "Bigger faces impact more on normal direction"),
                ))
        bpy.types.Scene.tex_downscale = bpy.props.EnumProperty(name="Texture downsampling",
                items=(
                    ("0", "None", "Use default resolution"),
                    ("128", "128x128", "Limit to 128x128"),
                    ("256", "256x256", "Limit to 256x256"),
                    ("512", "512x512", "Limit to 512x512"),
                    ("1024", "1024x1024", "Limit to 1024x1024"),
                    ("2048", "2048x2048", "Limit to 2048x2048"),
                    ("4096", "4096x4096", "Limit to 4096x4096"),
                ))
        bpy.types.Scene.device = bpy.props.EnumProperty(name="Device", items=get_devices)
        bpy.types.Scene.max_bounces = bpy.props.IntProperty(name="Max Bounces", default=5)
        bpy.types.Scene.connection_status = bpy.props.StringProperty(name="Connection Status", default="disconnected")
        
        bpy.ops.scene.watch_changes()

    def draw(self, context):
        
        layout = self.layout

        ip = layout.prop(context.scene, 'ip')
        block_size = layout.prop(context.scene, 'block_size')
        normals = layout.prop(context.scene, 'normals')
        device = layout.prop(context.scene, 'device')

        row = layout.row()
        
        denoise = layout.prop(context.scene, 'denoise')
        tex_downscale = layout.prop(context.scene, 'tex_downscale')
        sample_target = layout.prop(context.scene, 'sample_target')
        max_bounces = layout.prop(context.scene, 'max_bounces')
        
        if context.scene.connection_status == "disconnected" :
            connect_op = layout.operator("eleven.connect_operator", text="Connect", icon="CONSOLE")
        else:
            connect_op = layout.operator("eleven.disconnect_operator", text="Disconnect", icon="CONSOLE")
            
                  
        run_instance_op = layout.operator("eleven.run_instance_operator", text="Run Local instance", icon="CONSOLE")
        
        layout.label(text=f"Connection Status: {context.scene.connection_status}")
        
        #connection_status= layout.prop(context.scene, 'connection_status')
        
        