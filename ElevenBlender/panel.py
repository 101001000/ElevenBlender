import bpy

class ElevenPanel(bpy.types.Panel):
    bl_idname = "RENDER_PT_eleven"
    bl_label = "Eleven"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "render"

    def __init__(self):
        bpy.types.Scene.denoise = bpy.props.BoolProperty(name="Denoise (Open AI Denoise)")
        bpy.types.Scene.sample_target = bpy.props.IntProperty(name="Sample Target", default=100)
        bpy.types.Scene.ip = bpy.props.StringProperty(name="Ip", default="127.0.0.1:5557")
        bpy.types.Scene.mode = bpy.props.EnumProperty(name="Mode",
                items=(
                    ("Shared Memory", "Shared Memory", "Fastest. Use it if the render instance is in the same machine as Blender"),
                    ("TCP", "TCP", "Send scene data through TCP. Only needed for render instances hosted in other machine"),
                    ("Filesystem", "Filesystem", "Export data and load it through a file. Unperformant, used for compatibility"),
                ))
        bpy.types.Scene.normals = bpy.props.EnumProperty(name="Recompute Normals",
                items=(
                    ("None", "None", "Use Blender's computed normals"),
                    ("Face Weighted", "Face Weighted", "Bigger faces impact more on normal direction"),
                ))
        bpy.types.Scene.max_bounces = bpy.props.IntProperty(name="Max Bounces", default=5)

    def draw(self, context):
        
        layout = self.layout

        ip = layout.prop(context.scene, 'ip')
        mode = layout.prop(context.scene, 'mode')
        normals = layout.prop(context.scene, 'normals')
        row = layout.row()
        
        denoise = layout.prop(context.scene, 'denoise')
        sample_target = layout.prop(context.scene, 'sample_target')
        max_bounces = layout.prop(context.scene, 'max_bounces')
        
        