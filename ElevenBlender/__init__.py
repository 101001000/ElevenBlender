import bpy
import os

from .panel import ElevenPanel
from .engine import ElevenEngine, ConnectOperator, DisconnectOperator




bl_info = {
    "name": "Eleven Render",
    "description": "A super-compatible GPU/CPU rendering engine",
    "author": "Enrique de la Calle",
    "version": (0, 1),
    "blender": (3, 2, 0),
    "location": "Scene > Render > Eleven",
    "warning": "Extremely unstable",
    "doc_url": "https://github.com/101001000/ElevenBlender",
    "tracker_url": "https://github.com/101001000/ElevenBlender/issues",
    "support": "COMMUNITY",
    "category": "Render"
}



def get_panels():
    exclude_panels = {
        'VIEWLAYER_PT_filter',
        'VIEWLAYER_PT_layer_passes',
    }
    
    include_panels = {
        'EEVEE_MATERIAL_PT_surface',
        'MATERIAL_PT_custom_props',
        'MATERIAL_PT_preview',
        'EEVEE_MATERIAL_PT_context_material',
        'MATERIAL_PT_viewport',
    }

    panels = []
    for panel in bpy.types.Panel.__subclasses__():       
        if hasattr(panel, 'COMPAT_ENGINES') and panel.__name__ not in exclude_panels:
            if panel.__name__ in include_panels or 'BLENDER_RENDER' in panel.COMPAT_ENGINES:
                panels.append(panel)
                    
    return panels


def register():

    os.system('cls') 

    bpy.utils.register_class(DisconnectOperator)
    bpy.utils.register_class(ConnectOperator)
    bpy.utils.register_class(ElevenEngine)

    for panel in get_panels():
        panel.COMPAT_ENGINES.add('ELEVEN')
        
    bpy.utils.register_class(ElevenPanel)


def unregister():

    bpy.ops.eleven.disconnect_operator()

    bpy.utils.unregister_class(ElevenEngine)

    for panel in get_panels():
        if 'ELEVEN' in panel.COMPAT_ENGINES:
            panel.COMPAT_ENGINES.remove('ELEVEN')
            
    bpy.utils.unregister_class(ElevenPanel)
    bpy.utils.unregister_class(ConnectOperator)
    bpy.utils.unregister_class(DisconnectOperator)
    
    cleanse_modules()
    


if __name__ == "__main__":
    register()
    
    
def cleanse_modules():
    """search for your plugin modules in blender python sys.modules and remove them"""

    import sys

    all_modules = sys.modules 
    all_modules = dict(sorted(all_modules.items(),key= lambda x:x[0])) #sort them

    for k,v in all_modules.items():
        if k.startswith(__name__):
            del sys.modules[k]

    return None 