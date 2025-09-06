import bpy
import math
import random
from bpy.props import IntProperty

# Properties

bpy.types.Scene.additional_preframes = IntProperty(
    name="Add Preframes",
    description="Frames before selection",
    default=5
)

bpy.types.Scene.additional_postframes = IntProperty(
    name="Add Postframes",
    description="Frames after selection",
    default=5
)

bpy.types.Scene.use_bone_randomization = bpy.props.BoolProperty(
    name="Bone Randomization",
    description="Randomize all channels of a bone with the same value",
    default=True
)



bl_info = {
    "name": "Handle Manipulator",
    "author": "Gemini",
    "version": (1, 2),
    "blender": (4, 5, 0),
    "location": "Graph Editor > Sidebar",
    "description": "Manipulate selected keyframe handles.",
    "category": "Animation",
} 


bpy.types.Scene.keep_framerange = bpy.props.BoolProperty(
    name="Keep Framerange",
    description="Selection dependant framerange while animation is running by default. Toggle on for normal framerange",
    default=False 
)

def update_isolate_bones(self, context):
    is_isolated = self.is_bones_isolated
    
    # Hier kommt die Logik, um die Bones ein- oder auszublenden
    # Basierend auf dem Wert von `is_isolated`
    
    selected_bones = {pbone for pbone in context.active_object.pose.bones if pbone.bone.select}
    
    for pbone in context.active_object.pose.bones:
        if is_isolated:
            # Isoliere die Bones: Nicht ausgewählte ausblenden
            if pbone not in selected_bones:
                pbone.bone.hide = True
            else:
                pbone.bone.hide = False
        else:
            # Zeige alle Bones wieder an
            pbone.bone.hide = False

bpy.types.Scene.is_bones_isolated = bpy.props.BoolProperty(
    name="Isolate Bones",
    description="Toggles the visibility of unselected bones" 
    "\n(Fast Shift+H and Alt+H in 3D-View)",
    update=update_isolate_bones
)
class OBJECT_OT_toggle_bones_isolation(bpy.types.Operator):
    """Isolate selected bones in Viewport"""
    bl_idname = "object.toggle_bones_isolation"
    bl_label = "Isolate Bones"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.scene.is_bones_isolated = not context.scene.is_bones_isolated
        self.report({'INFO'}, f"Bones isolation: {'On' if context.scene.is_bones_isolated else 'Off'}")
        return {'FINISHED'}
    
def filter_fcurves(self, context):
    selected_objects = bpy.context.selected_objects
    
    all_fcurves = []
    for obj in selected_objects:
        if obj.animation_data and obj.animation_data.action:
            all_fcurves.extend(obj.animation_data.action.fcurves)

    for fc in all_fcurves:
        fc.select = False
            
    if self.filter_loc or self.filter_rot or self.filter_scale or self.filter_x or self.filter_y or self.filter_z:
        for fc in all_fcurves:
            data_path = fc.data_path
            array_index = fc.array_index

            loc_match = self.filter_loc and ("location" in data_path)
            rot_match = self.filter_rot and ("rotation_euler" in data_path or "rotation_quaternion" in data_path or "rotation_axis_angle" in data_path)
            scale_match = self.filter_scale and ("scale" in data_path)
            
            x_match = self.filter_x and (array_index == 0)
            y_match = self.filter_y and (array_index == 1)
            z_match = self.filter_z and (array_index == 2)
            
            type_match = (not self.filter_loc and not self.filter_rot and not self.filter_scale) or loc_match or rot_match or scale_match
            axis_match = (not self.filter_x and not self.filter_y and not self.filter_z) or x_match or y_match or z_match
            
            if type_match and axis_match:
                fc.select = True
    else:
        for fc in all_fcurves:
            fc.select = True
    
    for area in context.screen.areas:
        if area.type == 'GRAPH_EDITOR':
            area.tag_redraw()


def set_handles_aligned(context, initial_types):
    """Setzt die Handles der Keyframes auf den Typ 'ALIGNED'."""
    for (data_path, keyframe_index, array_index), types in initial_types.items():
        fcurve = None
        for fc in context.active_object.animation_data.action.fcurves:
            if fc.data_path == data_path and fc.array_index == array_index:
                fcurve = fc
                break
        
        if fcurve and keyframe_index < len(fcurve.keyframe_points):
            keyframe = fcurve.keyframe_points[keyframe_index]
            keyframe.interpolation = 'BEZIER'
            keyframe.handle_left_type = 'ALIGNED'
            keyframe.handle_right_type = 'ALIGNED'

def reset_handles(context, initial_vectors, initial_types, initial_coords):
    """Setzt die Handles auf ihre ursprüngliche Position und ihren Typ zurück."""
    for (data_path, keyframe_index, array_index), initial_vectors in initial_vectors.items():
        fcurve = None
        for fc in context.active_object.animation_data.action.fcurves:
            if fc.data_path == data_path and fc.array_index == array_index:
                fcurve = fc
                break

        if not fcurve or keyframe_index >= len(fcurve.keyframe_points):
            continue
        
        keyframe = fcurve.keyframe_points[keyframe_index]
        initial_coord = initial_coords[(data_path, keyframe_index, array_index)]
        
        vec_right_initial = initial_vectors['right']
        keyframe.handle_right[0] = initial_coord['co_x'] + vec_right_initial[0]
        keyframe.handle_right[1] = initial_coord['co_y'] + vec_right_initial[1]

        vec_left_initial = initial_vectors['left']
        keyframe.handle_left[0] = initial_coord['co_x'] + vec_left_initial[0]
        keyframe.handle_left[1] = initial_coord['co_y'] + vec_left_initial[1]
        
        types = initial_types[(data_path, keyframe_index, array_index)]
        keyframe.handle_left_type = types['left']
        keyframe.handle_right_type = types['right']


# --- NEUE FUNKTION: Setzt den Timeline-Bereich basierend auf den ausgewählten Keyframes ---
def set_timeline_range_to_selected(context):
    selected_frames = []
    all_visible_frames = set()
    found_multi_key_selection = False

    for fcurve in context.selected_visible_fcurves:
        selected_keyframes_in_fcurve = [kf for kf in fcurve.keyframe_points if kf.select_control_point]
        
        if len(selected_keyframes_in_fcurve) > 1:
            found_multi_key_selection = True
            
        for kf in fcurve.keyframe_points:
            all_visible_frames.add(kf.co[0])
            if kf.select_control_point:
                selected_frames.append(kf.co[0])

    if not selected_frames:
        return

    min_frame_selected = min(selected_frames)
    max_frame_selected = max(selected_frames)
    
    preframes = context.scene.additional_preframes
    postframes = context.scene.additional_postframes

    if not found_multi_key_selection:
        # Fall 1: Nur ein Key pro F-Kurve wurde ausgewählt.
        # Finde die benachbarten Keys der gesamten Auswahl.
        sorted_visible_frames = sorted(list(all_visible_frames))
        
        # Finde den Index des ersten und letzten ausgewählten Frames.
        # Fallback, wenn Frame nicht gefunden wird.
        try:
            min_index = sorted_visible_frames.index(min_frame_selected)
            max_index = sorted_visible_frames.index(max_frame_selected)
        except ValueError:
            context.scene.frame_start = int(min_frame_selected - preframes)
            context.scene.frame_end = int(max_frame_selected + postframes)
            return

        new_frame_start = min_frame_selected
        if min_index > 0:
            new_frame_start = sorted_visible_frames[min_index - 1]
            
        new_frame_end = max_frame_selected
        if max_index < len(sorted_visible_frames) - 1:
            new_frame_end = sorted_visible_frames[max_index + 1]

        context.scene.frame_start = int(new_frame_start - preframes)
        context.scene.frame_end = int(new_frame_end + postframes)
    
    else:
        # Fall 2: Auf mindestens einer F-Kurve wurden mehrere Keys ausgewählt.
        # Beschränke den Bereich auf die Auswahl selbst.
        context.scene.frame_start = int(min_frame_selected - preframes)
        context.scene.frame_end = int(max_frame_selected + postframes)
            
# Eine globale Variable, um den Zustand zu speichern.
_is_hidden = False



class GRAPH_OT_select_next_keys(bpy.types.Operator):
    """Selects next keyframes of f-curves"""
    bl_idname = "graph.select_next_keys"
    bl_label = "Nächster Keyframe (Mehrfachauswahl)"
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.area and context.area.type == 'GRAPH_EDITOR'

    def execute(self, context):
        selected_objects_with_action = [obj for obj in context.selected_objects if obj.animation_data and obj.animation_data.action]
        
        if not selected_objects_with_action:
            self.report({'WARNING'}, "No animation")
            return {'CANCELLED'}

        all_new_selection_frames = []
        has_selected_fcurves = False

        for obj in selected_objects_with_action:
            # Korrigierte Logik: Schleife nur über die ausgewählten F-Kurven
            selected_fcurves = [c for c in obj.animation_data.action.fcurves if c.select]
            
            if selected_fcurves:
                has_selected_fcurves = True
            
            for curve in selected_fcurves:
                selected_keys = [k for k in curve.keyframe_points if k.select_control_point]
                
                if not selected_keys:
                    sorted_keys = sorted(curve.keyframe_points, key=lambda k: k.co.x)
                    if sorted_keys:
                        last_key = sorted_keys[-1]
                        last_key.select_control_point = True
                        last_key.select_left_handle = True
                        last_key.select_right_handle = True
                        all_new_selection_frames.append(last_key.co.x)
                    continue
                
                min_frame = min([k.co.x for k in selected_keys])
                first_key = next((k for k in selected_keys if k.co.x == min_frame), None)
                max_frame = max([k.co.x for k in selected_keys])
                
                next_key = None
                for key in curve.keyframe_points:
                    if key.co.x > max_frame:
                        if next_key is None or key.co.x < next_key.co.x:
                            next_key = key
                
                if next_key:
                    if first_key:
                        first_key.select_control_point = False
                        first_key.select_left_handle = False
                        first_key.select_right_handle = False
                    
                    next_key.select_control_point = True
                    next_key.select_left_handle = True
                    next_key.select_right_handle = True
                    all_new_selection_frames.append(next_key.co.x)

        if not has_selected_fcurves:
            self.report({'WARNING'}, "No curve channels selected")
            return {'CANCELLED'}

        if all_new_selection_frames and not context.screen.is_animation_playing and not context.scene.keep_framerange:
            min_frame_new_selection = max(all_new_selection_frames)
            context.scene.frame_current = int(min_frame_new_selection)

        return {'FINISHED'}


    


class GRAPH_OT_select_previous_keys(bpy.types.Operator):
    """Selects previous keyframes of f-curves"""
    bl_idname = "graph.select_previous_keys"
    bl_label = "Vorheriger Keyframe (Mehrfachauswahl)"
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(cls, context):
        # Operator ist nur verfügbar, wenn der aktuelle Bereich der Graph-Editor ist
        return context.area and context.area.type == 'GRAPH_EDITOR'

    def execute(self, context):
        selected_objects_with_action = [obj for obj in context.selected_objects if obj.animation_data and obj.animation_data.action]
        
        if not selected_objects_with_action:
            self.report({'WARNING'}, "No animation")
            return {'CANCELLED'}

        all_new_selection_frames = []
        has_selected_fcurves = False

        for obj in selected_objects_with_action:
            # Filtere nur die F-Kurven, die im Graph-Editor ausgewählt sind
            selected_fcurves = [c for c in obj.animation_data.action.fcurves if c.select]
            
            if selected_fcurves:
                has_selected_fcurves = True
            
            for curve in selected_fcurves:
                selected_keys = [k for k in curve.keyframe_points if k.select_control_point]
                
                if not selected_keys:
                    sorted_keys = sorted(curve.keyframe_points, key=lambda k: k.co.x)
                    if sorted_keys:
                        first_key = sorted_keys[0]
                        first_key.select_control_point = True
                        first_key.select_left_handle = True
                        first_key.select_right_handle = True
                        all_new_selection_frames.append(first_key.co.x)
                    continue
                
                min_frame = min([k.co.x for k in selected_keys])
                
                previous_key = None
                for key in curve.keyframe_points:
                    if key.co.x < min_frame:
                        if previous_key is None or key.co.x > previous_key.co.x:
                            previous_key = key
                
                if previous_key:
                    max_frame = max([k.co.x for k in selected_keys])
                    last_key = next((k for k in selected_keys if k.co.x == max_frame), None)
                    if last_key:
                        last_key.select_control_point = False
                        last_key.select_left_handle = False
                        last_key.select_right_handle = False
                    
                    previous_key.select_control_point = True
                    previous_key.select_left_handle = True
                    previous_key.select_right_handle = True
                    all_new_selection_frames.append(previous_key.co.x)

        if not has_selected_fcurves:
            self.report({'WARNING'}, "No curve channels selected")
            return {'CANCELLED'}

        if all_new_selection_frames and not context.screen.is_animation_playing and not context.scene.keep_framerange:
            min_frame_new_selection = min(all_new_selection_frames)
            context.scene.frame_current = int(min_frame_new_selection)

        return {'FINISHED'}


class GRAPH_OT_add_next_keys(bpy.types.Operator):
    """add keyframe to selection on the right"""
    bl_idname = "graph.add_next_keys"
    bl_label = "Keyframe rechts hinzufügen"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        """Überprüft, ob der Operator ausgeführt werden kann."""
        # Überprüfen, ob der aktuelle Bereich der Graph-Editor ist.
        if context.area and context.area.type == 'GRAPH_EDITOR':
            # Überprüfen, ob ausgewählte Objekte existieren.
            for obj in context.selected_objects:
                # Überprüfen, ob Animationsdaten und eine Action vorhanden sind.
                if obj.animation_data and obj.animation_data.action:
                    # Überprüfen, ob Keyframes in irgendeiner F-Kurve ausgewählt sind.
                    for curve in obj.animation_data.action.fcurves:
                        if any(k.select_control_point for k in curve.keyframe_points):
                            return True
        return False

    def execute(self, context):
        """Führt die Operation aus."""
        area = context.area
        
        # Überprüfen, ob wir im richtigen Bereich sind.
        if area.type != 'GRAPH_EDITOR':
            self.report({'WARNING'}, "Graph editor operation")
            return {'CANCELLED'}

        # Iteriere durch alle ausgewählten Objekte.
        for obj in context.selected_objects:
            if obj.animation_data and obj.animation_data.action:
                # Iteriere durch alle F-Kurven der Action.
                for curve in obj.animation_data.action.fcurves:
                    # Filtere die aktuell ausgewählten Keyframes.
                    selected_keys = [k for k in curve.keyframe_points if k.select_control_point]
                    
                    if not selected_keys:
                        continue
                    
                    # Finde den am weitesten rechts liegenden (höchsten) ausgewählten Keyframe.
                    max_frame = max([k.co.x for k in selected_keys])
                    
                    next_key = None
                    # Finde den ersten Keyframe, der rechts von max_frame liegt.
                    for key in curve.keyframe_points:
                        if key.co.x > max_frame:
                            if next_key is None or key.co.x < next_key.co.x:
                                next_key = key
                    
                    # Füge den nächsten Keyframe und seine Handles zur Auswahl hinzu, falls er existiert.
                    if next_key:
                        next_key.select_control_point = True
                        next_key.select_left_handle = True
                        next_key.select_right_handle = True
        
        return {'FINISHED'}
    


class GRAPH_OT_subtract_keys(bpy.types.Operator):
    """subtract keyframe from selection on the right"""
    bl_idname = "graph.subtract_keys"
    bl_label = "Keyframe rechts entfernen"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        """Überprüft, ob der Operator ausgeführt werden kann."""
        if context.area and context.area.type == 'GRAPH_EDITOR':
            for obj in context.selected_objects:
                if obj.animation_data and obj.animation_data.action:
                    for curve in obj.animation_data.action.fcurves:
                        if any(k.select_control_point for k in curve.keyframe_points):
                            # Nur aktiv, wenn mindestens ein Keyframe in der Kurve ausgewählt ist.
                            return True
        return False

    def execute(self, context):
        """Führt die Operation aus."""
        area = context.area
        
        if area.type != 'GRAPH_EDITOR':
            self.report({'WARNING'}, "Graph editor operation")
            return {'CANCELLED'}

        for obj in context.selected_objects:
            if obj.animation_data and obj.animation_data.action:
                for curve in obj.animation_data.action.fcurves:
                    selected_keys = [k for k in curve.keyframe_points if k.select_control_point]
                    
                    # Bedingung: Prüfen, ob mehr als ein Keyframe ausgewählt ist.
                    # Nur dann darf der letzte Keyframe entfernt werden.
                    if len(selected_keys) > 1:
                        max_frame = max([k.co.x for k in selected_keys])
                        last_key = next((k for k in selected_keys if k.co.x == max_frame), None)
                        
                        if last_key:
                            last_key.select_control_point = False
                            last_key.select_left_handle = False
                            last_key.select_right_handle = False
                    
        return {'FINISHED'}


class BONES_OT_toggle_unselected_bones(bpy.types.Operator):
    bl_idname = "bones.toggle_unselected_bones"
    bl_label = "Toggle Unselected Bones"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Simualtes toggle between Shift + h and Alt + h to hide unused bones quickly. In an editor where you have all keyed bones visible, select all and then click here to isolate them"

    @classmethod
    def poll(cls, context):
        # Der Operator ist nur aktiv, wenn eine Armatur ausgewählt ist
        return context.active_object and context.active_object.type == 'ARMATURE'

    def execute(self, context):
        global _is_hidden

        # Umschalten des Zustands
        _is_hidden = not _is_hidden
        
        # Nur im Pose Mode ausführen
        if context.mode == 'POSE':
            for pbone in context.active_object.pose.bones:
                if not pbone.bone.select:
                    if _is_hidden:
                        pbone.bone.hide = True
                    else:
                        pbone.bone.hide = False

        # Optional: Status-Nachricht in der Info-Leiste anzeigen
        if _is_hidden:
            self.report({'INFO'}, "Selected bones")
        else:
            self.report({'INFO'}, "All bones")
        self.report({'INFO'}, "No selected bones isolated")
        
        return {'FINISHED'}


class GRAPH_OT_decimate_unselected(bpy.types.Operator):
    bl_idname = "graph.decimate_unselected"
    bl_label = "Decimate Unselected Keyframes"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Decimate dense keyframes, preserving selected" 
    

    @classmethod
    def poll(cls, context):
        return (context.active_object and
                context.active_object.animation_data and
                context.active_object.animation_data.action)

    def execute(self, context):
        if not (context.active_object and context.active_object.animation_data and context.active_object.animation_data.action):
            self.report({'WARNING'}, "Keine aktive Animation gefunden.")
            return {'CANCELLED'}

        action = context.active_object.animation_data.action
        selected_bone_names = {pbone.name for pbone in context.active_object.pose.bones if pbone.bone.select}
        
        original_selection_data = []

        for fcurve in action.fcurves:
            if any(f'pose.bones["{bone_name}"]' in fcurve.data_path for bone_name in selected_bone_names):
                for keyframe in fcurve.keyframe_points:
                    original_selection_data.append({
                        'fcurve': fcurve,
                        'keyframe': keyframe,
                        'was_selected': keyframe.select_control_point
                    })

        for item in original_selection_data:
            item['keyframe'].select_control_point = False

        for item in original_selection_data:
            if not item['was_selected']:
                item['keyframe'].select_control_point = True

        fixed_error_margin = 10
        
        try:
            bpy.ops.graph.decimate(mode='ERROR', remove_error_margin=fixed_error_margin)
        except RuntimeError:
            self.report({'WARNING'}, "No valid keyframes")
            return {'CANCELLED'}

        for item in original_selection_data:
            item['keyframe'].select_control_point = item['was_selected']

        self.report({'INFO'}, "Decimate Keyframes has been executed")
        return {'FINISHED'}



class GRAPH_OT_scale_keyframes_x(bpy.types.Operator):
    """Scale keyframes X value, relative to leftmost selected keyframe"""
    bl_idname = "graph.scale_keyframes_x"
    bl_label = "Scale Keys"
    bl_options = {'REGISTER', 'UNDO'}
    
    _timer = None
    _first_mouse_x = None
    _origin_frame = None
    _keyframes_initial_data = []
    _keyframes_after_data = [] # Wichtig: Diese Liste muss in der Klasse definiert werden
    _initial_frame_start = None
    _initial_frame_end = None
    _initial_frame_current = None
    _last_unselected_frame = None # Wichtig: Diese Variable muss auch hier definiert werden

    @classmethod
    def poll(cls, context):
        if not (context.active_object and
                context.active_object.animation_data and
                context.active_object.animation_data.action and
                context.selected_visible_fcurves):
            return False
        
        # Check if there's at least one fcurve with two or more selected keyframes
        for fcurve in context.selected_visible_fcurves:
            selected_keyframes_in_fcurve = [kf for kf in fcurve.keyframe_points if kf.select_control_point]
            if len(selected_keyframes_in_fcurve) >= 2:
                return True
                
        return False
    
    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            # 1. Maus-Warping-Logik
            window_width = context.window.width
            mouse_x = event.mouse_x
            
            # Speichere die ursprüngliche Mausposition
            original_mouse_x = mouse_x

            if mouse_x < 5 or mouse_x > window_width - 5:
                new_x = mouse_x
                if mouse_x < 5:
                    new_x = window_width - 10
                else:
                    new_x = 10
                
                self._first_mouse_x += new_x - mouse_x
                context.window.cursor_warp(new_x, event.mouse_y)

            delta_x = event.mouse_x - self._first_mouse_x
            scale_factor = 1.0 + delta_x * 0.005
            
            new_frame_positions = []
            
            # Skalierung der ausgewählten Keyframes
            for keyframe_data in self._keyframes_initial_data:
                keyframe = keyframe_data['keyframe']
                initial_frame = keyframe_data['frame']
                initial_handle_left_x = keyframe_data['handle_left_x']
                initial_handle_right_x = keyframe_data['handle_right_x']

                new_frame = self._origin_frame + (initial_frame - self._origin_frame) * scale_factor
                
                handle_left_dx = (initial_handle_left_x - initial_frame) * scale_factor
                handle_right_dx = (initial_handle_right_x - initial_frame) * scale_factor

                keyframe.co[0] = new_frame
                keyframe.handle_left[0] = new_frame + handle_left_dx
                keyframe.handle_right[0] = new_frame + handle_right_dx
                
                new_frame_positions.append(new_frame)
            
            # Verschiebung der nachfolgenden Keyframes und der rechten Timeline-Grenze
            if self._keyframes_after_data:
                # Berechne die Verschiebung basierend auf der Skalierung des letzten ausgewählten Keyframes
                last_selected_frame_initial = self._keyframes_initial_data[-1]['frame']
                last_selected_frame_new = self._origin_frame + (last_selected_frame_initial - self._origin_frame) * scale_factor
                displacement_factor = last_selected_frame_new - last_selected_frame_initial

                for keyframe_data in self._keyframes_after_data:
                    keyframe = keyframe_data['keyframe']
                    keyframe.co[0] = keyframe_data['initial_frame'] + displacement_factor
                    keyframe.handle_left[0] = keyframe_data['initial_handle_left_x'] + displacement_factor
                    keyframe.handle_right[0] = keyframe_data['initial_handle_right_x'] + displacement_factor

                # NEUE LOGIK HIER: Anpassung der Timeline-Grenzen
                if context.screen.is_animation_playing and not context.scene.keep_framerange:
                    if self._last_unselected_frame is not None:
                        new_unselected_frame = self._last_unselected_frame + displacement_factor
                        context.scene.frame_end = int(new_unselected_frame + context.scene.additional_postframes)
                    else:
                        # Falls keine nachfolgenden Keyframes existieren, verwende den letzten ausgewählten
                        if new_frame_positions:
                            context.scene.frame_end = int(max(new_frame_positions) + context.scene.additional_postframes)
            
            else:
                # Falls keine nachfolgenden Keyframes existieren
                if context.screen.is_animation_playing and not context.scene.keep_framerange:
                    if new_frame_positions:
                        context.scene.frame_end = int(max(new_frame_positions) + context.scene.additional_postframes)

            # Anpassung der linken Timeline-Grenze (Diese Logik ist bereits korrekt)
            if new_frame_positions and context.screen.is_animation_playing and not context.scene.keep_framerange:
                min_frame = min(new_frame_positions)
                context.scene.frame_start = int(min_frame - context.scene.additional_preframes)
                
                # Passe den aktuellen Frame an, wenn die Skalierung ihn außerhalb der sichtbaren
                # Region verschiebt
                if context.scene.frame_current < context.scene.frame_start:
                    context.scene.frame_current = context.scene.frame_start
                elif context.scene.frame_current > context.scene.frame_end:
                    context.scene.frame_current = context.scene.frame_end


            context.area.tag_redraw()

        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            # Endet den Operator und stellt die Timeline-Grenzen zurück
            context.scene.frame_start = self._initial_frame_start
            context.scene.frame_end = self._initial_frame_end
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            # Bricht ab und setzt alle Keyframes und Timeline-Grenzen zurück
            for keyframe_data in self._keyframes_initial_data:
                keyframe = keyframe_data['keyframe']
                keyframe.co[0] = keyframe_data['frame']
                keyframe.handle_left[0] = keyframe_data['handle_left_x']
                keyframe.handle_right[0] = keyframe_data['handle_right_x']
            
            for keyframe_data in self._keyframes_after_data:
                keyframe = keyframe_data['keyframe']
                keyframe.co[0] = keyframe_data['initial_frame']
                keyframe.handle_left[0] = keyframe_data['initial_handle_left_x']
                keyframe.handle_right[0] = keyframe_data['initial_handle_right_x']

            context.scene.frame_start = self._initial_frame_start
            context.scene.frame_end = self._initial_frame_end
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        selected_keyframes = []
        # Sammelt alle ausgewählten Keyframes in einer Liste
        for fcurve in context.selected_visible_fcurves:
            for keyframe in fcurve.keyframe_points:
                if keyframe.select_control_point:
                    selected_keyframes.append(keyframe)
        
        if not selected_keyframes:
            self.report({'WARNING'}, "Keine Keyframes ausgewählt.")
            return {'CANCELLED'}

        # Sortiert die Keyframes nach ihrem Frame, um den ersten und letzten zu finden
        selected_keyframes.sort(key=lambda kf: kf.co[0])
        
        # Holt den letzten Keyframe, um die nachfolgenden Keyframes zu bestimmen
        last_selected_keyframe = selected_keyframes[-1]
        
        # Hier wird der erste ausgewählte Keyframe gefunden, der als Ursprung dient.
        origin_keyframe = min(selected_keyframes, key=lambda kf: kf.co[0])
        self._origin_frame = origin_keyframe.co[0]

        # Speichert die ursprünglichen Timeline-Grenzen
        self._initial_frame_start = context.scene.frame_start
        self._initial_frame_end = context.scene.frame_end
        
        # Initialisiert die Variable für den nicht-ausgewählten End-Frame
        self._last_unselected_frame = None

        # Finde alle Keyframes, die rechts vom letzten ausgewählten Keyframe liegen
        self._keyframes_after_data.clear()
        last_selected_frame = last_selected_keyframe.co[0]
        for fcurve in context.selected_visible_fcurves:
            for keyframe in fcurve.keyframe_points:
                # Berücksichtige nur nicht-ausgewählte Keyframes, die nach dem letzten kommen
                if not keyframe.select_control_point and keyframe.co[0] > last_selected_frame:
                    self._keyframes_after_data.append({
                        'keyframe': keyframe,
                        'initial_frame': keyframe.co[0],
                        'initial_handle_left_x': keyframe.handle_left[0],
                        'initial_handle_right_x': keyframe.handle_right[0]
                    })
        
        # Suche den ersten nicht-ausgewählten Keyframe nach dem letzten ausgewählten
        # Diese Logik ist nötig, um das Ende der Timeline korrekt zu setzen.
        all_keyframes = []
        for fcurve in context.selected_visible_fcurves:
            all_keyframes.extend(fcurve.keyframe_points)

        self._last_unselected_frame = None
        for keyframe in all_keyframes:
            if not keyframe.select_control_point and keyframe.co[0] > last_selected_keyframe.co[0]:
                if self._last_unselected_frame is None or keyframe.co[0] < self._last_unselected_frame:
                    self._last_unselected_frame = keyframe.co[0]

        # Speichert die initialen Daten aller ausgewählten Keyframes
        self._keyframes_initial_data.clear()
        for keyframe in selected_keyframes:
            self._keyframes_initial_data.append({
                'keyframe': keyframe,
                'frame': keyframe.co[0],
                'handle_left_x': keyframe.handle_left[0],
                'handle_right_x': keyframe.handle_right[0]
            })
        
        self._first_mouse_x = event.mouse_x
        
        context.window.cursor_set('SCROLL_X')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}








class GRAPH_OT_move_keyframes_x(bpy.types.Operator):
    """Move keyframes X value"""
    bl_idname = "graph.move_keyframes_x"
    bl_label = "Move keys"
    bl_options = {'REGISTER', 'UNDO'}

    _first_mouse_x = None
    _keyframes_initial_data = []
    _initial_frame_start = None
    _initial_frame_end = None

    @classmethod
    def poll(cls, context):
        # Überprüft, ob ein aktives Objekt mit Animationsdaten und ausgewählten F-Kurven vorhanden ist.
        # Dann wird geprüft, ob mindestens ein Keyframe in diesen F-Kurven ausgewählt ist.
        return (context.active_object and
                context.active_object.animation_data and
                context.active_object.animation_data.action and
                context.selected_visible_fcurves and
                any(kf.select_control_point for fc in context.selected_visible_fcurves for kf in fc.keyframe_points))
                
    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            if event.type == 'MOUSEMOVE':
                # 1. Maus-Warping-Logik
                window_width = context.window.width
                mouse_x = event.mouse_x
                
                # Speichere die ursprüngliche Mausposition
                original_mouse_x = mouse_x

                if mouse_x < 5 or mouse_x > window_width - 5:
                    new_x = mouse_x
                    if mouse_x < 5:
                        new_x = window_width - 10
                    else:
                        new_x = 10
                    
                    self._first_mouse_x += new_x - mouse_x
                    context.window.cursor_warp(new_x, event.mouse_y)

            delta_x = (event.mouse_x - self._first_mouse_x) * 0.1
            
            new_frame_positions = []
            
            for keyframe_data in self._keyframes_initial_data:
                keyframe = keyframe_data['keyframe']
                initial_frame = keyframe_data['frame']
                initial_handle_left_x = keyframe_data['handle_left_x']
                initial_handle_right_x = keyframe_data['handle_right_x']

                new_frame = initial_frame + delta_x
                
                handle_left_x = initial_handle_left_x + delta_x
                handle_right_x = initial_handle_right_x + delta_x

                keyframe.co[0] = new_frame
                keyframe.handle_left[0] = handle_left_x
                keyframe.handle_right[0] = handle_right_x
                
                new_frame_positions.append(new_frame)
                
            if new_frame_positions and context.screen.is_animation_playing and not context.scene.keep_framerange:
                # Für den Start-Frame
                if self._first_unselected_frame is not None:
                    new_start_frame = self._first_unselected_frame
                else:
                    new_start_frame = min(new_frame_positions)

                # Für den End-Frame
                if self._last_unselected_frame is not None:
                    new_end_frame = self._last_unselected_frame
                else:
                    new_end_frame = max(new_frame_positions)
                    
                context.scene.frame_start = int(new_start_frame - context.scene.additional_preframes)
                context.scene.frame_end = int(new_end_frame + context.scene.additional_postframes)
                #context.scene.frame_current = int(new_start_frame - context.scene.additional_preframes)
            
            context.area.tag_redraw()

        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            context.scene.frame_start = self._initial_frame_start
            context.scene.frame_end = self._initial_frame_end
            
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            for keyframe_data in self._keyframes_initial_data:
                keyframe = keyframe_data['keyframe']
                keyframe.co[0] = keyframe_data['frame']
                keyframe.handle_left[0] = keyframe_data['handle_left_x']
                keyframe.handle_right[0] = keyframe_data['handle_right_x']
            
            context.scene.frame_start = self._initial_frame_start
            context.scene.frame_end = self._initial_frame_end
            
            context.window.cursor_set('DEFAULT')
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}
    
    def invoke(self, context, event):
        selected_keyframes = []
        
        # Sammelt alle ausgewählten Keyframes
        for fcurve in context.selected_visible_fcurves:
            for keyframe in fcurve.keyframe_points:
                if keyframe.select_control_point:
                    selected_keyframes.append(keyframe)
        
        if not selected_keyframes:
            self.report({'WARNING'}, "Keine Keyframes ausgewählt.")
            return {'CANCELLED'}
            
        # Sortiert die ausgewählten Keyframes nach ihrem Frame-Wert
        selected_keyframes.sort(key=lambda kf: kf.co[0])
        
        # Holt den ersten und letzten ausgewählten Keyframe
        first_selected_keyframe = selected_keyframes[0]
        last_selected_keyframe = selected_keyframes[-1] # Füge diese Zeile hinzu

        # Speichert die ursprünglichen Timeline-Grenzen
        self._initial_frame_start = context.scene.frame_start
        self._initial_frame_end = context.scene.frame_end

        # Initialisiere die Variablen für die nicht-ausgewählten Frames
        self._first_unselected_frame = None
        self._last_unselected_frame = None # Füge diese Zeile hinzu

        # Finde den letzten nicht-ausgewählten Keyframe vor dem ersten ausgewählten
        for fcurve in context.selected_visible_fcurves:
            for keyframe in fcurve.keyframe_points:
                if not keyframe.select_control_point and keyframe.co[0] < first_selected_keyframe.co[0]:
                    if self._first_unselected_frame is None or keyframe.co[0] > self._first_unselected_frame:
                        self._first_unselected_frame = keyframe.co[0]
                # Füge diese Logik hinzu, um den ersten nicht-ausgewählten nach dem letzten ausgewählten zu finden
                if not keyframe.select_control_point and keyframe.co[0] > last_selected_keyframe.co[0]:
                    if self._last_unselected_frame is None or keyframe.co[0] < self._last_unselected_frame:
                        self._last_unselected_frame = keyframe.co[0]

        self._keyframes_initial_data.clear()
        for keyframe in selected_keyframes:
            self._keyframes_initial_data.append({
                'keyframe': keyframe,
                'frame': keyframe.co[0],
                'handle_left_x': keyframe.handle_left[0],
                'handle_right_x': keyframe.handle_right[0]
            })

        self._first_mouse_x = event.mouse_x
        
        context.window.cursor_set('MOVE_X')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


class OBJECT_OT_rotate_keys(bpy.types.Operator):
    bl_idname = "object.rotate_keys"
    bl_label = "Rotate Keyframes"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Mousewheel for sensitivity. Rotation direction and strength is dependant on next keyframe"
                 

    _initial_keyframe_data = {}
    
    initial_mouse_x = None
    _strength_multiplier = 0.5
    
    # Empfindlichkeit in Grad pro Pixel
    _degrees_per_pixel = 10

    @classmethod
    def poll(cls, context):
        return (context.active_object and
                context.active_object.animation_data and
                context.active_object.animation_data.action and
                context.selected_visible_fcurves and
                len([kf for fc in context.selected_visible_fcurves for kf in fc.keyframe_points if kf.select_control_point]) > 0)

    def _apply_rotation(self, context, rotation_angle_degrees):
        for (data_path, keyframe_index, array_index), initial_data in self._initial_keyframe_data.items():
            fcurve = None
            for fc in context.active_object.animation_data.action.fcurves:
                if fc.data_path == data_path and fc.array_index == array_index:
                    fcurve = fc
                    break
            
            if not fcurve or keyframe_index >= len(fcurve.keyframe_points):
                continue
            
            keyframe = fcurve.keyframe_points[keyframe_index]
            
            direction = 0.0
            strength_multiplier = 0.0
            
            # 1. Versuche, die Richtung und Stärke am nächsten Keyframe zu bestimmen
            if keyframe_index + 1 < len(fcurve.keyframe_points):
                next_keyframe = fcurve.keyframe_points[keyframe_index + 1]
                if next_keyframe.co[1] != keyframe.co[1]:
                    direction = 1.0 if next_keyframe.co[1] > keyframe.co[1] else -1.0
                    strength_multiplier = abs(next_keyframe.co[1] - keyframe.co[1])
            
            # 2. Wenn der nächste Keyframe nicht verfügbar oder auf gleicher Höhe ist, versuche es mit dem vorherigen Keyframe
            if direction == 0.0 and keyframe_index > 0:
                previous_keyframe = fcurve.keyframe_points[keyframe_index - 1]
                if previous_keyframe.co[1] != keyframe.co[1]:
                    direction = 1.0 if previous_keyframe.co[1] < keyframe.co[1] else -1.0
                    strength_multiplier = abs(previous_keyframe.co[1] - keyframe.co[1])
            
            # Wenn keine Richtung oder Stärke gefunden wurde, fahre mit dem nächsten Keyframe fort
            if direction == 0.0 or strength_multiplier == 0.0:
                continue

            # Wende die Stärke und Richtung an
            modified_rotation_degrees = rotation_angle_degrees * strength_multiplier * direction
            rotation_angle_radians = math.radians(modified_rotation_degrees)
            
            cos_angle = math.cos(rotation_angle_radians)
            sin_angle = math.sin(rotation_angle_radians)
            
            # ... (der Rest der Rotationslogik bleibt gleich)
            x1, y1 = initial_data['handle_left_vec'][0], initial_data['handle_left_vec'][1]
            rx1 = x1 * cos_angle - y1 * sin_angle
            ry1 = x1 * sin_angle + y1 * cos_angle
            
            x2, y2 = initial_data['handle_right_vec'][0], initial_data['handle_right_vec'][1]
            rx2 = x2 * cos_angle - y2 * sin_angle
            ry2 = x2 * sin_angle + y2 * cos_angle
            
            keyframe.handle_left[0] = initial_data['co_x'] + rx1
            keyframe.handle_left[1] = initial_data['co_y'] + ry1
            keyframe.handle_right[0] = initial_data['co_x'] + rx2
            keyframe.handle_right[1] = initial_data['co_y'] + ry2
            
        for area in context.screen.areas:
            if area.type in {'GRAPH_EDITOR', 'VIEW_3D'}:
                area.tag_redraw()

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            if event.mouse_x < 5 or event.mouse_x > context.window.width - 5:
                if event.mouse_x < 5:
                    new_x = context.window.width - 10
                else:
                    new_x = 10
                
                self.initial_mouse_x += (new_x - event.mouse_x)
                context.window.cursor_warp(new_x, event.mouse_y)
            delta_x = (event.mouse_x - self.initial_mouse_x) * 100
            
            # Korrigierte Berechnung der Drehstärke
            rotation_strength_degrees = delta_x * self._degrees_per_pixel * 0.0001
            
            self._apply_rotation(context, rotation_strength_degrees)
            # Ausgabe auf Grad ändern
            #self.report({'INFO'}, f"Rotation Sensitivity: {self._degrees_per_pixel:.2f} ")
            return {'RUNNING_MODAL'}
            
        elif event.type == 'WHEELUPMOUSE':
            self._degrees_per_pixel *= 1.5
            
            # HIER wird der Maus-Startwert neu gesetzt
            self.initial_mouse_x = event.mouse_x

            delta_x = event.mouse_x - self.initial_mouse_x
            rotation_strength_degrees = delta_x * self._degrees_per_pixel
            self._apply_rotation(context, rotation_strength_degrees)
            self.report({'INFO'}, f"Rotation Sensitivity: {self._degrees_per_pixel:.2f} ")
            return {'RUNNING_MODAL'}
            
        elif event.type == 'WHEELDOWNMOUSE':
            self._degrees_per_pixel /= 1.5
            self._degrees_per_pixel = max(0.01, self._degrees_per_pixel)
            
            # HIER wird der Maus-Startwert neu gesetzt
            self.initial_mouse_x = event.mouse_x

            delta_x = event.mouse_x - self.initial_mouse_x
            rotation_strength_degrees = delta_x * self._degrees_per_pixel
            self._apply_rotation(context, rotation_strength_degrees)
            self.report({'INFO'}, f"Rotation Sensitivity: {self._degrees_per_pixel:.2f} ")
            return {'RUNNING_MODAL'}

        elif event.type == 'LEFTMOUSE':
            for (data_path, keyframe_index, array_index), initial_data in self._initial_keyframe_data.items():
                fcurve = None
                for fc in context.active_object.animation_data.action.fcurves:
                    if fc.data_path == data_path and fc.array_index == array_index:
                        fcurve = fc
                        break
                if fcurve and keyframe_index < len(fcurve.keyframe_points):
                    keyframe = fcurve.keyframe_points[keyframe_index]
                    keyframe.handle_left_type = 'ALIGNED'
                    keyframe.handle_right_type = 'ALIGNED'

            context.scene.frame_start = self._initial_frame_start
            context.scene.frame_end = self._initial_frame_end

            context.window.cursor_set('DEFAULT')
            return {'FINISHED'}
        
        

        elif event.type == 'RIGHTMOUSE' or event.type == 'ESC':
            for (data_path, keyframe_index, array_index), initial_data in self._initial_keyframe_data.items():
                fcurve = None
                for fc in context.active_object.animation_data.action.fcurves:
                    if fc.data_path == data_path and fc.array_index == array_index:
                        fcurve = fc
                        break
                
                if fcurve and keyframe_index < len(fcurve.keyframe_points):
                    keyframe = fcurve.keyframe_points[keyframe_index]
                    keyframe.handle_left[0] = initial_data['co_x'] + initial_data['handle_left_vec'][0]
                    keyframe.handle_left[1] = initial_data['co_y'] + initial_data['handle_left_vec'][1]
                    keyframe.handle_right[0] = initial_data['co_x'] + initial_data['handle_right_vec'][0]
                    keyframe.handle_right[1] = initial_data['co_y'] + initial_data['handle_right_vec'][1]
                    keyframe.handle_left_type = initial_data['handle_left_type']
                    keyframe.handle_right_type = initial_data['handle_right_type']
            
            context.scene.frame_start = self._initial_frame_start
            context.scene.frame_end = self._initial_frame_end
            
            context.window.cursor_set('DEFAULT')
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}
    
    def invoke(self, context, event):
        self.report({'INFO'}, f"Rotation Sensitivity: {self._degrees_per_pixel:.2f} ")
        
        # Filtern der Keyframes in der invoke-Methode
        filtered_keyframes = []
        
        # Verwende eine Toleranz für den Vergleich der Werte
        epsilon = 1e-6 
        
        for fcurve in context.selected_visible_fcurves:
            for keyframe_index, keyframe in enumerate(fcurve.keyframe_points):
                if keyframe.select_control_point:
                    current_value = keyframe.co[1]
                    has_different_neighbor = False
                    
                    # Prüfen auf vorherigen Keyframe
                    if keyframe_index > 0:
                        prev_keyframe = fcurve.keyframe_points[keyframe_index - 1]
                        if abs(prev_keyframe.co[1] - current_value) > epsilon:
                            has_different_neighbor = True
                    
                    # Prüfen auf nächsten Keyframe
                    if not has_different_neighbor and keyframe_index < len(fcurve.keyframe_points) - 1:
                        next_keyframe = fcurve.keyframe_points[keyframe_index + 1]
                        if abs(next_keyframe.co[1] - current_value) > epsilon:
                            has_different_neighbor = True
                    
                    if has_different_neighbor:
                        filtered_keyframes.append(keyframe)
        
        if not filtered_keyframes:
            self.report({'WARNING'}, "Neighbouring keys have the same value")
            return {'CANCELLED'}

        self._initial_frame_start = context.scene.frame_start
        self._initial_frame_end = context.scene.frame_end
        if not context.scene.keep_framerange and context.screen.is_animation_playing:
            set_timeline_range_to_selected(context)
            
        if context.screen.is_animation_playing:
            context.scene.frame_current = context.scene.frame_start

        self._initial_keyframe_data.clear()
        self.initial_mouse_x = event.mouse_x

        # Speichern nur der gefilterten Keyframes
        for fcurve in context.selected_visible_fcurves:
            for keyframe_index, keyframe in enumerate(fcurve.keyframe_points):
                if keyframe in filtered_keyframes:
                    key = (fcurve.data_path, keyframe_index, fcurve.array_index)
                    
                    self._initial_keyframe_data[key] = {
                        'co_x': keyframe.co[0],
                        'co_y': keyframe.co[1],
                        'handle_left_type': keyframe.handle_left_type,
                        'handle_right_type': keyframe.handle_right_type,
                        'handle_left_vec': (keyframe.handle_left[0] - keyframe.co[0], keyframe.handle_left[1] - keyframe.co[1]),
                        'handle_right_vec': (keyframe.handle_right[0] - keyframe.co[0], keyframe.handle_right[1] - keyframe.co[1])
                    }

        context.window.cursor_set('SCROLL_X')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}



class OBJECT_OT_flatten_keys(bpy.types.Operator):
    bl_idname = "object.flatten_keys"
    bl_label = "Flatten Keys"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Flatten, or exaggerate handle rotation"
                    
    _initial_keyframe_data = {}
    _initial_mouse_x = None
    _sensitivity = 0.002
    
    _initial_flatten_factor = 0.0

    _initial_frame_start = 0
    _initial_frame_end = 0

    @classmethod
    def poll(cls, context):
        return (context.active_object and
                context.active_object.animation_data and
                context.active_object.animation_data.action and
                context.selected_visible_fcurves and
                len([kf for fc in context.selected_visible_fcurves for kf in fc.keyframe_points if kf.select_control_point]) > 0)

    def _apply_flattening(self, context, flatten_factor):
        # **ÄNDERUNG HIER:** Erlaubt negative Werte, begrenzt positiv bei 1.0
        flatten_factor = min(1.0, flatten_factor)

        for (data_path, keyframe_index, array_index), initial_data in self._initial_keyframe_data.items():
            fcurve = None
            for fc in context.active_object.animation_data.action.fcurves:
                if fc.data_path == data_path and fc.array_index == array_index:
                    fcurve = fc
                    break
            
            if not fcurve or keyframe_index >= len(fcurve.keyframe_points):
                continue
            
            keyframe = fcurve.keyframe_points[keyframe_index]
            
            initial_hl_vec_x, initial_hl_vec_y = initial_data['handle_left_vec']
            flattened_hl_vec_x = initial_hl_vec_x
            flattened_hl_vec_y = 0.0
            
            new_hl_vec_x = initial_hl_vec_x + (flattened_hl_vec_x - initial_hl_vec_x) * flatten_factor
            new_hl_vec_y = initial_hl_vec_y + (flattened_hl_vec_y - initial_hl_vec_y) * flatten_factor

            keyframe.handle_left[0] = initial_data['co_x'] + new_hl_vec_x
            keyframe.handle_left[1] = initial_data['co_y'] + new_hl_vec_y
            
            initial_hr_vec_x, initial_hr_vec_y = initial_data['handle_right_vec']
            flattened_hr_vec_x = initial_hr_vec_x
            flattened_hr_vec_y = 0.0

            new_hr_vec_x = initial_hr_vec_x + (flattened_hr_vec_x - initial_hr_vec_x) * flatten_factor
            new_hr_vec_y = initial_hr_vec_y + (flattened_hr_vec_y - initial_hr_vec_y) * flatten_factor

            keyframe.handle_right[0] = initial_data['co_x'] + new_hr_vec_x
            keyframe.handle_right[1] = initial_data['co_y'] + new_hr_vec_y
            
        for area in context.screen.areas:
            if area.type in {'GRAPH_EDITOR', 'VIEW_3D'}:
                area.tag_redraw()

    def modal(self, context, event):
        # **ÄNDERUNG HIER:** Erlaubt negative Werte, begrenzt positiv bei 1.0
        _flatten_factor = self._initial_flatten_factor + (event.mouse_x - self._initial_mouse_x) * self._sensitivity
        _flatten_factor = min(1.0, _flatten_factor)
        
        if event.type == 'MOUSEMOVE':
            # Hol dir die Breite des Fensters, in dem der Operator aktiv ist.
            # Anstatt context.window.width, nutze besser die Bereichsgröße für mehr Flexibilität
            window_width = context.window.width
        
            # Hol dir die Mausposition im Fenster-Koordinatensystem
            mouse_x = event.mouse_x
            
            # Überprüfe, ob die Maus den linken oder rechten Rand erreicht hat (Puffer von 5 Pixeln)
            if mouse_x < 5 or mouse_x > window_width - 5:
                new_x = mouse_x
                if mouse_x < 5:
                    # Maus ist am linken Rand, teleportiere sie zum rechten Rand
                    new_x = window_width - 10
                else:
                    # Maus ist am rechten Rand, teleportiere sie zum linken Rand
                    new_x = 10
                    
                # Aktualisiere die Anfangsmausposition, um den Sprung auszugleichen
                self._initial_mouse_x += new_x - mouse_x

                # Setze den Cursor an die neue Position
                context.window.cursor_warp(new_x, event.mouse_y)
                
            # Berechne die Delta-Werte basierend auf der aktuellen Mausposition und der initialen Mausposition
            # Die initial_mouse_x wird durch das Warping korrekt angepasst,
            # sodass die Bewegung nahtlos weiterläuft.
            delta_x = event.mouse_x - self._initial_mouse_x
            
            _flatten_factor = self._initial_flatten_factor + delta_x * self._sensitivity
            _flatten_factor = min(1.0, _flatten_factor)
            
            self._apply_flattening(context, _flatten_factor)
            
            return {'RUNNING_MODAL'}
        elif event.type == 'LEFTMOUSE':
            for (data_path, keyframe_index, array_index), initial_data in self._initial_keyframe_data.items():
                fcurve = None
                for fc in context.active_object.animation_data.action.fcurves:
                    if fc.data_path == data_path and fc.array_index == array_index:
                        fcurve = fc
                        break
                if fcurve and keyframe_index < len(fcurve.keyframe_points):
                    keyframe = fcurve.keyframe_points[keyframe_index]
                    keyframe.handle_left_type = 'ALIGNED'
                    keyframe.handle_right_type = 'ALIGNED'
            
            context.scene.frame_start = self._initial_frame_start
            context.scene.frame_end = self._initial_frame_end

            context.window.cursor_set('DEFAULT')
            return {'FINISHED'}
            
        elif event.type == 'RIGHTMOUSE' or event.type == 'ESC':
            for (data_path, keyframe_index, array_index), initial_data in self._initial_keyframe_data.items():
                fcurve = None
                for fc in context.active_object.animation_data.action.fcurves:
                    if fc.data_path == data_path and fc.array_index == array_index:
                        fcurve = fc
                        break
                
                if fcurve and keyframe_index < len(fcurve.keyframe_points):
                    keyframe = fcurve.keyframe_points[keyframe_index]
                    keyframe.handle_left[0] = initial_data['co_x'] + initial_data['handle_left_vec'][0]
                    keyframe.handle_left[1] = initial_data['co_y'] + initial_data['handle_left_vec'][1]
                    keyframe.handle_right[0] = initial_data['co_x'] + initial_data['handle_right_vec'][0]
                    keyframe.handle_right[1] = initial_data['co_y'] + initial_data['handle_right_vec'][1]
                    keyframe.handle_left_type = initial_data['handle_left_type']
                    keyframe.handle_right_type = initial_data['handle_right_type']
            
            context.scene.frame_start = self._initial_frame_start
            context.scene.frame_end = self._initial_frame_end
            
            context.window.cursor_set('DEFAULT')
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}
    
    def invoke(self, context, event):
        epsilon = 1e-6
        selected_keyframes = []
        for fcurve in context.selected_visible_fcurves:
            for keyframe in fcurve.keyframe_points:
                if keyframe.select_control_point:
                    selected_keyframes.append(keyframe)
        
        if not selected_keyframes:
            self.report({'WARNING'}, "Keine ausgewählten Keyframes gefunden.")
            return {'CANCELLED'}

        self._initial_keyframe_data.clear()
        
        self._initial_frame_start = context.scene.frame_start
        self._initial_frame_end = context.scene.frame_end
        
        if not context.scene.keep_framerange and context.screen.is_animation_playing:
            set_timeline_range_to_selected(context)
            if context.screen.is_animation_playing:
                context.scene.frame_current = context.scene.frame_start

        self._initial_mouse_x = event.mouse_x
        self._flatten_factor = 0.0
        self._initial_flatten_factor = self._flatten_factor
        
        for fcurve in context.selected_visible_fcurves:
            for keyframe_index, keyframe in enumerate(fcurve.keyframe_points):
                if keyframe in selected_keyframes:
                    key = (fcurve.data_path, keyframe_index, fcurve.array_index)
                    
                    self._initial_keyframe_data[key] = {
                        'co_x': keyframe.co[0],
                        'co_y': keyframe.co[1],
                        'handle_left_type': keyframe.handle_left_type,
                        'handle_right_type': keyframe.handle_right_type,
                        'handle_left_vec': (keyframe.handle_left[0] - keyframe.co[0], keyframe.handle_left[1] - keyframe.co[1]),
                        'handle_right_vec': (keyframe.handle_right[0] - keyframe.co[0], keyframe.handle_right[1] - keyframe.co[1])
                    }

        context.window.cursor_set('SCROLL_X')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


import bpy
import math



class OBJECT_OT_manipulate_handles(bpy.types.Operator):
    bl_idname = "object.handle_manipulator"
    bl_label = "Manipulate Handles"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Mousewheel for left or right. Extrude handles"
    
    _timer = None
    initial_mouse_x = None
    _mode = 'LEFT_HANDLE' # Starte im linken Modus
    initial_handle_vectors = {}
    initial_handle_types = {}
    initial_keyframe_data = {}
    _initial_frame_start = None
    _initial_frame_end = None
    
    @classmethod
    def poll(cls, context):
        return (context.active_object and
                context.active_object.animation_data and
                context.active_object.animation_data.action and
                context.selected_visible_fcurves and
                len([kf for fc in context.selected_visible_fcurves for kf in fc.keyframe_points if kf.select_control_point]) > 0)
    
    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            # Maus-Warping bleibt unverändert
            if event.mouse_x < 5 or event.mouse_x > context.window.width - 5:
                if event.mouse_x < 5:
                    new_x = context.window.width - 10
                else:
                    new_x = 10
                self.initial_mouse_x += (new_x - event.mouse_x)
                context.window.cursor_warp(new_x, event.mouse_y)
            
            if event.mouse_y < 5 or event.mouse_y > context.window.height - 5:
                if event.mouse_y < 5:
                    new_y = context.window.height - 10
                else:
                    new_y = 10
                self.initial_mouse_y += (new_y - event.mouse_y)
                context.window.cursor_warp(event.mouse_x, new_y)

            delta_x_px = event.mouse_x - self.initial_mouse_x
            
            for key, initial_data in self.initial_keyframe_data.items():
                data_path, keyframe_index, array_index = key
                
                fcurve = None
                for fc in context.active_object.animation_data.action.fcurves:
                    if fc.data_path == data_path and fc.array_index == array_index:
                        fcurve = fc
                        break
                
                if not fcurve:
                    continue
                
                keyframe = fcurve.keyframe_points[keyframe_index]
                
                initial_vectors = self.initial_handle_vectors[key]
                vec_left_initial = initial_vectors['left']
                vec_right_initial = initial_vectors['right']

                # Berechne den Skalierungsfaktor
                # Die 200 ist ein beliebiger Wert für die Empfindlichkeit, du kannst sie anpassen
                factor = 1.0 + (delta_x_px / 200.0) 
                
                if self._mode == 'LEFT_HANDLE':
                    # Skaliere den linken Handle
                    new_vec_left_x = vec_left_initial[0] * factor
                    new_vec_left_y = vec_left_initial[1] * factor
                    keyframe.handle_left[0] = keyframe.co[0] + new_vec_left_x
                    keyframe.handle_left[1] = keyframe.co[1] + new_vec_left_y
                    
                    # Setze den rechten Handle auf den ursprünglichen Zustand zurück
                    keyframe.handle_right[0] = keyframe.co[0] + vec_right_initial[0]
                    keyframe.handle_right[1] = keyframe.co[1] + vec_right_initial[1]

                elif self._mode == 'RIGHT_HANDLE':
                    # Skaliere den rechten Handle
                    new_vec_right_x = vec_right_initial[0] * factor
                    new_vec_right_y = vec_right_initial[1] * factor
                    keyframe.handle_right[0] = keyframe.co[0] + new_vec_right_x
                    keyframe.handle_right[1] = keyframe.co[1] + new_vec_right_y

                    # Setze den linken Handle auf den ursprünglichen Zustand zurück
                    keyframe.handle_left[0] = keyframe.co[0] + vec_left_initial[0]
                    keyframe.handle_left[1] = keyframe.co[1] + vec_left_initial[1]

            for area in context.screen.areas:
                if area.type in {'GRAPH_EDITOR', 'VIEW_3D'}:
                    area.tag_redraw()
        
        elif event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            # Wechsle zwischen den Modi
            self._mode = 'RIGHT_HANDLE' if self._mode == 'LEFT_HANDLE' else 'LEFT_HANDLE'
            self.report({'INFO'}, f"{self._mode}")
            self.initial_mouse_x = event.mouse_x
            
        elif event.type == 'LEFTMOUSE':
            # Bestätige die Änderungen
            for key, types in self.initial_handle_types.items():
                data_path, keyframe_index, array_index = key
                fcurve = None
                for fc in context.active_object.animation_data.action.fcurves:
                    if fc.data_path == data_path and fc.array_index == array_index:
                        fcurve = fc
                        break
                if fcurve:
                    keyframe = fcurve.keyframe_points[keyframe_index]
                    keyframe.interpolation = 'BEZIER'
                    keyframe.handle_left_type = 'ALIGNED' if keyframe.handle_left_type == 'FREE' else keyframe.handle_left_type
                    keyframe.handle_right_type = 'ALIGNED' if keyframe.handle_right_type == 'FREE' else keyframe.handle_right_type

            context.scene.frame_start = self._initial_frame_start
            context.scene.frame_end = self._initial_frame_end
            context.window.cursor_set('DEFAULT')
            if self._timer:
                context.window_manager.event_timer_remove(self._timer)
            return {'FINISHED'}
            
        elif event.type == 'RIGHTMOUSE' or event.type == 'ESC':
            # Abbrechen und die Handles auf den Ausgangszustand zurücksetzen
            for key, initial_vectors in self.initial_handle_vectors.items():
                data_path, keyframe_index, array_index = key
                fcurve = None
                for fc in context.active_object.animation_data.action.fcurves:
                    if fc.data_path == data_path and fc.array_index == array_index:
                        fcurve = fc
                        break
                if fcurve:
                    keyframe = fcurve.keyframe_points[keyframe_index]
                    keyframe.handle_left[0] = keyframe.co[0] + initial_vectors['left'][0]
                    keyframe.handle_left[1] = keyframe.co[1] + initial_vectors['left'][1]
                    keyframe.handle_right[0] = keyframe.co[0] + initial_vectors['right'][0]
                    keyframe.handle_right[1] = keyframe.co[1] + initial_vectors['right'][1]

                    types = self.initial_handle_types[key]
                    keyframe.handle_left_type = types['left']
                    keyframe.handle_right_type = types['right']
            
            context.scene.frame_start = self._initial_frame_start
            context.scene.frame_end = self._initial_frame_end
            context.window.cursor_set('DEFAULT')
            if self._timer:
                context.window_manager.event_timer_remove(self._timer)
            return {'CANCELLED'}
            
        return {'RUNNING_MODAL'}
        
    def invoke(self, context, event):
        self.report({'INFO'}, f"{self._mode}")
        if context.active_object is None or context.active_object.animation_data is None:
            self.report({'WARNING'}, "Kein aktives Objekt oder keine Animationsdaten.")
            return {'CANCELLED'}
        
        if not context.selected_visible_fcurves:
            self.report({'WARNING'}, "Keine F-Kurven im Graph Editor sichtbar und ausgewählt.")
            return {'CANCELLED'}

        self._initial_frame_start = context.scene.frame_start
        self._initial_frame_end = context.scene.frame_end
        
        if not context.scene.keep_framerange and context.screen.is_animation_playing:
            set_timeline_range_to_selected(context)
            
        if context.screen.is_animation_playing:
            context.scene.frame_current = context.scene.frame_start

        self.initial_mouse_x = event.mouse_x
        self.initial_mouse_y = event.mouse_y # Auch diese Zeile wieder eingefügt
        self._mode = 'LEFT_HANDLE'
        self.initial_handle_vectors.clear()
        self.initial_handle_types.clear()
        self.initial_keyframe_data.clear()
        
        selected_keyframes_found = False
        for fcurve in context.selected_visible_fcurves:
            for keyframe_index, keyframe in enumerate(fcurve.keyframe_points):
                if keyframe.select_control_point:
                    selected_keyframes_found = True
                    key = (fcurve.data_path, keyframe_index, fcurve.array_index)
                    
                    self.initial_handle_vectors[key] = {
                        'left': (keyframe.handle_left[0] - keyframe.co[0], keyframe.handle_left[1] - keyframe.co[1]),
                        'right': (keyframe.handle_right[0] - keyframe.co[0], keyframe.handle_right[1] - keyframe.co[1]),
                    }
                    
                    self.initial_handle_types[key] = {
                        'left': keyframe.handle_left_type,
                        'right': keyframe.handle_right_type
                    }
                    
                    self.initial_keyframe_data[key] = {
                        'co_x': keyframe.co[0],
                        'co_y': keyframe.co[1],
                    }

        if not selected_keyframes_found:
            self.report({'WARNING'}, "Keine Keyframes in den aktiven, sichtbaren Kurven ausgewählt.")
            return {'CANCELLED'}
        
        context.window.cursor_set('SCROLL_X')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}



class OBJECT_OT_randomize_keys(bpy.types.Operator):
    bl_idname = "object.randomize_keys"
    bl_label = "Randomize Keyframes"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Mousewheel for seed. Randomize keyframes Y-Value"

    _timer = None
    initial_mouse_x = None
    initial_keyframe_data = {}
    
    _current_strength = 0.0
    _current_seed = 0

    @classmethod
    def poll(cls, context):
        return (context.active_object and
                context.active_object.animation_data and
                context.active_object.animation_data.action and
                context.selected_visible_fcurves and
                len([kf for fc in context.selected_visible_fcurves for kf in fc.keyframe_points if kf.select_control_point]) > 0)

    def _apply_randomization(self, context, strength):
        random.seed(self._current_seed)
        
        # Dictionary zum Speichern der Zufallswerte pro Knochen
        bone_random_offsets = {}
        
        for (data_path, keyframe_index, array_index), initial_data in self.initial_keyframe_data.items():
            fcurve = None
            for fc in context.active_object.animation_data.action.fcurves:
                if fc.data_path == data_path and fc.array_index == array_index:
                    fcurve = fc
                    break

            if not fcurve or keyframe_index >= len(fcurve.keyframe_points):
                continue
            
            keyframe = fcurve.keyframe_points[keyframe_index]
            
            # Neue Logik: Zufalls-Offset basierend auf der Eigenschaft
            if context.scene.use_bone_randomization:
                # Extrahiere Knochennamen aus dem data_path
                try:
                    bone_name = data_path.split('"')[1]
                except IndexError:
                    bone_name = None # Fallback für nicht-Knochen-Pfade
                
                if bone_name not in bone_random_offsets:
                    # Berechne den Offset nur einmal pro Knochen
                    bone_random_offsets[bone_name] = random.uniform(-strength, strength)
                
                random_offset_y = bone_random_offsets.get(bone_name, 0.0)
            else:
                # Ursprüngliche Logik: Zufalls-Offset pro Kanal
                random_offset_y = random.uniform(-strength, strength)
                
            keyframe.co[1] = initial_data['co_y'] + random_offset_y

            # Die Handle-Vektoren werden basierend auf der neuen Keyframe-Position neu berechnet.
            keyframe.handle_left[0] = keyframe.co[0] + initial_data['handle_left_vec'][0]
            keyframe.handle_left[1] = keyframe.co[1] + initial_data['handle_left_vec'][1]
            keyframe.handle_right[0] = keyframe.co[0] + initial_data['handle_right_vec'][0]
            keyframe.handle_right[1] = keyframe.co[1] + initial_data['handle_right_vec'][1]
        
        for area in context.screen.areas:
            if area.type in {'GRAPH_EDITOR', 'VIEW_3D'}:
                area.tag_redraw()

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            if event.mouse_x < 5 or event.mouse_x > context.window.width - 5:
                if event.mouse_x < 5:
                    new_x = context.window.width - 10
                else:
                    new_x = 10
                
                self.initial_mouse_x += (new_x - event.mouse_x)
                context.window.cursor_warp(new_x, event.mouse_y)
                
            base_divisor = 1000.0 if event.alt else 200.0
            delta_x = event.mouse_x - self.initial_mouse_x
            delta_x = max(0.0, delta_x)
            power_exponent = 2.0
            abs_delta_x = abs(delta_x)
            strength = (abs_delta_x / base_divisor) ** power_exponent
            if delta_x < 0:
                strength *= -1.0
            
            self._current_strength = strength
            self._apply_randomization(context, self._current_strength)
            
            return {'RUNNING_MODAL'}
            
        elif event.type == 'WHEELUPMOUSE':
            self._current_seed += 1
            self._apply_randomization(context, self._current_strength)
            self.report({'INFO'}, f"Seed: {self._current_seed}")
            return {'RUNNING_MODAL'}
        
        elif event.type == 'WHEELDOWNMOUSE':
            self._current_seed -= 1
            self._apply_randomization(context, self._current_strength)
            self.report({'INFO'}, f"Seed: {self._current_seed}")
            return {'RUNNING_MODAL'}

        elif event.type == 'LEFTMOUSE':
            for (data_path, keyframe_index, array_index), initial_data in self.initial_keyframe_data.items():
                fcurve = None
                for fc in context.active_object.animation_data.action.fcurves:
                    if fc.data_path == data_path and fc.array_index == array_index:
                        fcurve = fc
                        break
                
                if fcurve and keyframe_index < len(fcurve.keyframe_points):
                    keyframe = fcurve.keyframe_points[keyframe_index]
                    keyframe.interpolation = 'BEZIER'
                    keyframe.handle_left_type = 'ALIGNED'
                    keyframe.handle_right_type = 'ALIGNED'
            
            context.scene.frame_start = self._initial_frame_start
            context.scene.frame_end = self._initial_frame_end
            
            context.window.cursor_set('DEFAULT')
            if self._timer:
                context.window_manager.event_timer_remove(self._timer)
            return {'FINISHED'}
        
    


        elif event.type == 'RIGHTMOUSE' or event.type == 'ESC':
            for (data_path, keyframe_index, array_index), initial_data in self.initial_keyframe_data.items():
                fcurve = None
                for fc in context.active_object.animation_data.action.fcurves:
                    if fc.data_path == data_path and fc.array_index == array_index:
                        fcurve = fc
                        break
                
                if fcurve and keyframe_index < len(fcurve.keyframe_points):
                    keyframe = fcurve.keyframe_points[keyframe_index]
                    keyframe.co[1] = initial_data['co_y']
                    keyframe.handle_left[0] = initial_data['co_x'] + initial_data['handle_left_vec'][0]
                    keyframe.handle_left[1] = initial_data['co_y'] + initial_data['handle_left_vec'][1]
                    keyframe.handle_right[0] = initial_data['co_x'] + initial_data['handle_right_vec'][0]
                    keyframe.handle_right[1] = initial_data['co_y'] + initial_data['handle_right_vec'][1]
                    keyframe.handle_left_type = initial_data['handle_left_type']
                    keyframe.handle_right_type = initial_data['handle_right_type']
            
            context.scene.frame_start = self._initial_frame_start
            context.scene.frame_end = self._initial_frame_end
                        
            context.window.cursor_set('DEFAULT')
            if self._timer:
                context.window_manager.event_timer_remove(self._timer)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}
    
    def invoke(self, context, event):
        if context.active_object is None or context.active_object.animation_data is None:
            self.report({'WARNING'}, "Kein aktives Objekt oder keine Animationsdaten.")
            return {'CANCELLED'}

        if not context.selected_visible_fcurves:
            self.report({'WARNING'}, "Keine F-Kurven im Graph Editor sichtbar und ausgewählt.")
            return {'CANCELLED'}
        
        # Filtern der Keyframes in der invoke-Methode
        filtered_keyframes_data = []
        epsilon = 1e-6
        
        for fcurve in context.selected_visible_fcurves:
            for keyframe_index, keyframe in enumerate(fcurve.keyframe_points):
                if keyframe.select_control_point:
                    current_value = keyframe.co[1]
                    has_different_neighbor = False
                    
                    # Prüfen auf vorherigen Keyframe
                    if keyframe_index > 0:
                        prev_keyframe = fcurve.keyframe_points[keyframe_index - 1]
                        if abs(prev_keyframe.co[1] - current_value) > epsilon:
                            has_different_neighbor = True
                    
                    # Prüfen auf nächsten Keyframe
                    if not has_different_neighbor and keyframe_index < len(fcurve.keyframe_points) - 1:
                        next_keyframe = fcurve.keyframe_points[keyframe_index + 1]
                        if abs(next_keyframe.co[1] - current_value) > epsilon:
                            has_different_neighbor = True
                    
                    if has_different_neighbor:
                        filtered_keyframes_data.append({
                            'fcurve': fcurve,
                            'keyframe': keyframe,
                            'keyframe_index': keyframe_index
                        })

        if not filtered_keyframes_data:
            self.report({'WARNING'}, "Keine Keyframes gefunden, die unterschiedliche Nachbarwerte haben.")
            return {'CANCELLED'}

        self._initial_frame_start = context.scene.frame_start
        self._initial_frame_end = context.scene.frame_end
        
        if not context.scene.keep_framerange and context.screen.is_animation_playing:
            set_timeline_range_to_selected(context)

        self.initial_mouse_x = event.mouse_x
        self.initial_keyframe_data.clear()
        
        self._current_strength = 0.0
        self._current_seed = 0
        
        if context.screen.is_animation_playing:
            context.scene.frame_current = context.scene.frame_start

        # Speichern nur der gefilterten Keyframes
        for data in filtered_keyframes_data:
            fcurve = data['fcurve']
            keyframe = data['keyframe']
            keyframe_index = data['keyframe_index']
            
            key = (fcurve.data_path, keyframe_index, fcurve.array_index)
            
            self.initial_keyframe_data[key] = {
                'co_x': keyframe.co[0], 
                'co_y': keyframe.co[1],
                'handle_left_type': keyframe.handle_left_type,
                'handle_right_type': keyframe.handle_right_type,
                'handle_left_vec': (keyframe.handle_left[0] - keyframe.co[0], keyframe.handle_left[1] - keyframe.co[1]),
                'handle_right_vec': (keyframe.handle_right[0] - keyframe.co[0], keyframe.handle_right[1] - keyframe.co[1])
            }
        
        context.window.cursor_set('SCROLL_X')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}




class OBJECT_OT_random_x_pos(bpy.types.Operator):
    bl_idname = "object.random_x_pos"
    bl_label = "Randomize Keyframes"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Mousewheel for seed. Randomize keyframes X-Value"
                     

    _timer = None
    initial_mouse_x = None
    initial_keyframe_data = {}
    
    _current_strength = 0.0
    _current_seed = 0
    
    _initial_frame_start = 0
    _initial_frame_end = 0

    # Neuer Schalter für die Randomisierungs-Art
    
    

    @classmethod
    def poll(cls, context):
        return (context.active_object and
                context.active_object.animation_data and
                context.active_object.animation_data.action and
                context.selected_visible_fcurves and
                any(kf.select_control_point for fc in context.selected_visible_fcurves for kf in fc.keyframe_points))

    def _apply_randomization(self, context, strength):
        random.seed(self._current_seed)
        
        if self.use_bone_randomization:
            # Logic for per-bone randomization
            bone_offsets = {}
            for (data_path, _, _), _ in self.initial_keyframe_data.items():
                if data_path.startswith('pose.bones['):
                    bone_name = data_path.split('"')[1]
                    if bone_name not in bone_offsets:
                        bone_offsets[bone_name] = random.uniform(-strength, strength)

            for (data_path, keyframe_index, array_index), initial_data in self.initial_keyframe_data.items():
                fcurve = next((fc for fc in context.active_object.animation_data.action.fcurves
                               if fc.data_path == data_path and fc.array_index == array_index), None)
                
                if not fcurve or keyframe_index >= len(fcurve.keyframe_points):
                    continue
                
                keyframe = fcurve.keyframe_points[keyframe_index]
                offset_x = bone_offsets.get(data_path.split('"')[1], 0.0) if data_path.startswith('pose.bones[') else 0.0
                
                keyframe.co[0] = initial_data['co_x'] + offset_x
                keyframe.handle_left[0] = initial_data['co_x'] + initial_data['handle_left_vec'][0] + offset_x
                keyframe.handle_right[0] = initial_data['co_x'] + initial_data['handle_right_vec'][0] + offset_x

        else:
            # Logic for per-channel randomization (original logic)
            for (data_path, keyframe_index, array_index), initial_data in self.initial_keyframe_data.items():
                fcurve = next((fc for fc in context.active_object.animation_data.action.fcurves
                               if fc.data_path == data_path and fc.array_index == array_index), None)
                
                if not fcurve or keyframe_index >= len(fcurve.keyframe_points):
                    continue
                
                keyframe = fcurve.keyframe_points[keyframe_index]
                random_offset_x = random.uniform(-strength, strength)
                
                keyframe.co[0] = initial_data['co_x'] + random_offset_x
                keyframe.handle_left[0] = initial_data['co_x'] + initial_data['handle_left_vec'][0] + random_offset_x
                keyframe.handle_right[0] = initial_data['co_x'] + initial_data['handle_right_vec'][0] + random_offset_x

        for area in context.screen.areas:
            if area.type in {'GRAPH_EDITOR', 'VIEW_3D'}:
                area.tag_redraw()

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            if event.mouse_x < 5 or event.mouse_x > context.window.width - 5:
                new_x = context.window.width - 10 if event.mouse_x < 5 else 10
                self.initial_mouse_x += (new_x - event.mouse_x)
                context.window.cursor_warp(new_x, event.mouse_y)
                
            base_divisor = 1000.0 if event.alt else 200.0
            delta_x = event.mouse_x - self.initial_mouse_x
            delta_x = max(0.0, delta_x)
            power_exponent = 2.0
            strength = abs(delta_x / base_divisor) ** power_exponent
            strength = strength if delta_x >= 0 else -strength
            
            self._current_strength = strength
            self._apply_randomization(context, self._current_strength)
            return {'RUNNING_MODAL'}
            
        elif event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            self._current_seed += 1 if event.type == 'WHEELUPMOUSE' else -1
            self._apply_randomization(context, self._current_strength)
            self.report({'INFO'}, f"Seed: {self._current_seed}")
            return {'RUNNING_MODAL'}

        elif event.type == 'LEFTMOUSE':
            for (data_path, keyframe_index, array_index), initial_data in self.initial_keyframe_data.items():
                fcurve = next((fc for fc in context.active_object.animation_data.action.fcurves
                               if fc.data_path == data_path and fc.array_index == array_index), None)
                if fcurve and keyframe_index < len(fcurve.keyframe_points):
                    keyframe = fcurve.keyframe_points[keyframe_index]
                    keyframe.interpolation = 'BEZIER'
                    keyframe.handle_left_type = 'ALIGNED'
                    keyframe.handle_right_type = 'ALIGNED'
            context.scene.frame_start = self._initial_frame_start
            context.scene.frame_end = self._initial_frame_end
            context.window.cursor_set('DEFAULT')
            if self._timer: context.window_manager.event_timer_remove(self._timer)
            return {'FINISHED'}
            
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            for (data_path, keyframe_index, array_index), initial_data in self.initial_keyframe_data.items():
                fcurve = next((fc for fc in context.active_object.animation_data.action.fcurves
                               if fc.data_path == data_path and fc.array_index == array_index), None)
                if fcurve and keyframe_index < len(fcurve.keyframe_points):
                    keyframe = fcurve.keyframe_points[keyframe_index]
                    keyframe.co[0] = initial_data['co_x']
                    keyframe.co[1] = initial_data['co_y']
                    keyframe.handle_left[0] = initial_data['co_x'] + initial_data['handle_left_vec'][0]
                    keyframe.handle_left[1] = initial_data['co_y'] + initial_data['handle_left_vec'][1]
                    keyframe.handle_right[0] = initial_data['co_x'] + initial_data['handle_right_vec'][0]
                    keyframe.handle_right[1] = initial_data['co_y'] + initial_data['handle_right_vec'][1]
                    keyframe.handle_left_type = initial_data['handle_left_type']
                    keyframe.handle_right_type = initial_data['handle_right_type']
            context.scene.frame_start = self._initial_frame_start
            context.scene.frame_end = self._initial_frame_end
            context.window.cursor_set('DEFAULT')
            if self._timer: context.window_manager.event_timer_remove(self._timer)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}
    
    def invoke(self, context, event):
        if not self.poll(context):
            self.report({'WARNING'}, "Voraussetzungen nicht erfüllt.")
            return {'CANCELLED'}
        
        filtered_keyframes_data = []
        self.use_bone_randomization = context.scene.use_bone_randomization
        
        if self.use_bone_randomization:
            # Bone-basierte Filterung
            filtered_bones = set()
            for fcurve in context.selected_visible_fcurves:
                if not fcurve.data_path.startswith('pose.bones['): continue
                for kf_idx, kf in enumerate(fcurve.keyframe_points):
                    if kf.select_control_point:
                        if (kf_idx > 0 and abs(fcurve.keyframe_points[kf_idx - 1].co[0] - kf.co[0]) > 1e-6) or \
                           (kf_idx < len(fcurve.keyframe_points) - 1 and abs(fcurve.keyframe_points[kf_idx + 1].co[0] - kf.co[0]) > 1e-6):
                            filtered_bones.add(fcurve.data_path.split('"')[1])
                            break
            
            if not filtered_bones:
                self.report({'WARNING'}, "Keine Keyframes von Bones mit unterschiedlichen Nachbarn gefunden.")
                return {'CANCELLED'}

            for fcurve in context.selected_visible_fcurves:
                if fcurve.data_path.startswith('pose.bones[') and fcurve.data_path.split('"')[1] in filtered_bones:
                    for kf_idx, kf in enumerate(fcurve.keyframe_points):
                        if kf.select_control_point:
                            filtered_keyframes_data.append({'fcurve': fcurve, 'keyframe': kf, 'keyframe_index': kf_idx})
        
        else:
            # Channel-basierte Filterung (Original-Logik)
            for fcurve in context.selected_visible_fcurves:
                for kf_idx, kf in enumerate(fcurve.keyframe_points):
                    if kf.select_control_point:
                        if (kf_idx > 0 and abs(fcurve.keyframe_points[kf_idx - 1].co[0] - kf.co[0]) > 1e-6) or \
                           (kf_idx < len(fcurve.keyframe_points) - 1 and abs(fcurve.keyframe_points[kf_idx + 1].co[0] - kf.co[0]) > 1e-6):
                            filtered_keyframes_data.append({'fcurve': fcurve, 'keyframe': kf, 'keyframe_index': kf_idx})

        if not filtered_keyframes_data:
            self.report({'WARNING'}, "Keine Keyframes mit unterschiedlichen Nachbarwerten gefunden.")
            return {'CANCELLED'}

        self._initial_frame_start = context.scene.frame_start
        self._initial_frame_end = context.scene.frame_end
        if not context.scene.keep_framerange and context.screen.is_animation_playing:
            set_timeline_range_to_selected(context)

        self.initial_mouse_x = event.mouse_x
        self.initial_keyframe_data.clear()
        self._current_strength = 0.0
        self._current_seed = 0
        if context.screen.is_animation_playing:
            context.scene.frame_current = context.scene.frame_start

        for data in filtered_keyframes_data:
            fcurve, kf, kf_idx = data['fcurve'], data['keyframe'], data['keyframe_index']
            key = (fcurve.data_path, kf_idx, fcurve.array_index)
            self.initial_keyframe_data[key] = {
                'co_x': kf.co[0], 'co_y': kf.co[1],
                'handle_left_type': kf.handle_left_type, 'handle_right_type': kf.handle_right_type,
                'handle_left_vec': (kf.handle_left[0] - kf.co[0], kf.handle_left[1] - kf.co[1]),
                'handle_right_vec': (kf.handle_right[0] - kf.co[0], kf.handle_right[1] - kf.co[1])
            }
        
        context.window.cursor_set('SCROLL_X')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


class OBJECT_OT_randomize_handle_rotation(bpy.types.Operator):
    bl_idname = "object.randomize_handle_rotation"
    bl_label = "Randomize Handle Rotation" # label for button
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Mousewheel for seed. Randomize handle rotation"

    _timer = None
    initial_mouse_x = None
    initial_handle_vectors = {}
    initial_handle_types = {}
    _current_strength = 0.0
    _current_seed = 0
    _initial_frame_start = 0
    _initial_frame_end = 0

    @classmethod
    def poll(cls, context):
        return (context.active_object and
                context.active_object.animation_data and
                context.active_object.animation_data.action and
                context.selected_visible_fcurves and
                len([kf for fc in context.selected_visible_fcurves for kf in fc.keyframe_points if kf.select_control_point]) > 0)

    def _apply_randomized_extrusion(self, context, strength):
        random.seed(self._current_seed)
        
        # Dictionary zum Speichern der Zufallswerte pro Knochen
        bone_random_rotations = {}

        for (data_path, keyframe_index, array_index), initial_vectors in self.initial_handle_vectors.items():
            fcurve = None
            for fc in context.active_object.animation_data.action.fcurves:
                if fc.data_path == data_path and fc.array_index == array_index:
                    fcurve = fc
                    break

            if not fcurve or keyframe_index >= len(fcurve.keyframe_points):
                continue
            
            keyframe = fcurve.keyframe_points[keyframe_index]
            
            # Neue Logik: Zufallsrotation basierend auf der Eigenschaft
            if context.scene.use_bone_randomization:
                # Extrahiere Knochennamen aus dem data_path
                try:
                    bone_name = data_path.split('"')[1]
                except IndexError:
                    bone_name = None  # Fallback für nicht-Knochen-Pfade
                
                if bone_name not in bone_random_rotations:
                    # Berechne den Rotationswert nur einmal pro Knochen
                    bone_random_rotations[bone_name] = random.uniform(-strength * math.pi, strength * math.pi)
                
                random_rotation_rad = bone_random_rotations.get(bone_name, 0.0)
            else:
                # Ursprüngliche Logik: Zufallsrotation pro Kanal
                random_rotation_rad = random.uniform(-strength * math.pi, strength * math.pi)

            # Linkes Handle
            vec_left_initial = initial_vectors['left']
            length_left_initial = math.sqrt(vec_left_initial[0]**2 + vec_left_initial[1]**2)
            
            if length_left_initial > 0:
                initial_angle_left = math.atan2(vec_left_initial[1], vec_left_initial[0])
                new_angle_left = initial_angle_left + random_rotation_rad
                
                new_x_left = keyframe.co[0] + length_left_initial * math.cos(new_angle_left)
                new_y_left = keyframe.co[1] + length_left_initial * math.sin(new_angle_left)
                keyframe.handle_left[0] = new_x_left
                keyframe.handle_left[1] = new_y_left

            # Rechtes Handle
            vec_right_initial = initial_vectors['right']
            length_right_initial = math.sqrt(vec_right_initial[0]**2 + vec_right_initial[1]**2)

            if length_right_initial > 0:
                initial_angle_right = math.atan2(vec_right_initial[1], vec_right_initial[0])
                new_angle_right = initial_angle_right + random_rotation_rad
                
                new_x_right = keyframe.co[0] + length_right_initial * math.cos(new_angle_right)
                new_y_right = keyframe.co[1] + length_right_initial * math.sin(new_angle_right)
                keyframe.handle_right[0] = new_x_right
                keyframe.handle_right[1] = new_y_right
        
        for area in context.screen.areas:
            if area.type in {'GRAPH_EDITOR', 'VIEW_3D'}:
                area.tag_redraw()

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            if event.mouse_x < 5 or event.mouse_x > context.window.width - 5:
                if event.mouse_x < 5:
                    new_x = context.window.width - 10
                else:
                    new_x = 10
                self.initial_mouse_x += (new_x - event.mouse_x)
                context.window.cursor_warp(new_x, event.mouse_y)
            
            base_divisor = 1000.0 if event.alt else 200.0
            delta_x = (event.mouse_x - self.initial_mouse_x) * 0.1
            
            # Verhindere, dass delta_x negativ wird
            delta_x = max(0.0, delta_x)
            
            power_exponent = 2.0
            strength = (delta_x / base_divisor) ** power_exponent
            
            self._current_strength = strength
            self._apply_randomized_extrusion(context, self._current_strength)
            #self.report({'INFO'}, f"Strength: {10000 *self._current_strength:.2f}, Seed: {self._current_seed}")
            return {'RUNNING_MODAL'}
            
        elif event.type == 'WHEELUPMOUSE':
            self._current_seed += 1
            self._apply_randomized_extrusion(context, self._current_strength)
            self.report({'INFO'}, f"Seed: {self._current_seed}")
            return {'RUNNING_MODAL'}
        
        elif event.type == 'WHEELDOWNMOUSE':
            self._current_seed -= 1
            self._apply_randomized_extrusion(context, self._current_strength)
            self.report({'INFO'}, f"Strength: {self._current_strength:.6f}, Seed: {self._current_seed}")
            return {'RUNNING_MODAL'}

        elif event.type == 'LEFTMOUSE':
            # Iteriere über alle initial gespeicherten Keyframes
            for (data_path, keyframe_index, array_index), initial_vectors in self.initial_handle_vectors.items():
                fcurve = None
                for fc in context.active_object.animation_data.action.fcurves:
                    if fc.data_path == data_path and fc.array_index == array_index:
                        fcurve = fc
                        break
                
                # Wenn der Keyframe noch existiert, setze die Handle-Typen
                if fcurve and keyframe_index < len(fcurve.keyframe_points):
                    keyframe = fcurve.keyframe_points[keyframe_index]
                    keyframe.handle_left_type = 'ALIGNED'
                    keyframe.handle_right_type = 'ALIGNED'

            context.scene.frame_start = self._initial_frame_start
            context.scene.frame_end = self._initial_frame_end

            context.window.cursor_set('DEFAULT')
            return {'FINISHED'}
        
        elif event.type == 'RIGHTMOUSE' or event.type == 'ESC':
            for (data_path, keyframe_index, array_index), initial_vectors in self.initial_handle_vectors.items():
                fcurve = None
                for fc in context.active_object.animation_data.action.fcurves:
                    if fc.data_path == data_path and fc.array_index == array_index:
                        fcurve = fc
                        break
                
                if not fcurve or keyframe_index >= len(fcurve.keyframe_points):
                    continue
                
                keyframe = fcurve.keyframe_points[keyframe_index]
                initial_types = self.initial_handle_types[(data_path, keyframe_index, array_index)]
                
                keyframe.handle_left[0] = keyframe.co[0] + initial_vectors['left'][0]
                keyframe.handle_left[1] = keyframe.co[1] + initial_vectors['left'][1]
                keyframe.handle_right[0] = keyframe.co[0] + initial_vectors['right'][0]
                keyframe.handle_right[1] = keyframe.co[1] + initial_vectors['right'][1]
                
                keyframe.handle_left_type = initial_types['left']
                keyframe.handle_right_type = initial_types['right']
            
            context.scene.frame_start = self._initial_frame_start
            context.scene.frame_end = self._initial_frame_end
            
            context.window.cursor_set('DEFAULT')
            if self._timer:
                context.window_manager.event_timer_remove(self._timer)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}
    
    def invoke(self, context, event):
        if not context.selected_visible_fcurves or not [kf for fc in context.selected_visible_fcurves for kf in fc.keyframe_points if kf.select_control_point]:
            self.report({'WARNING'}, "Keine Keyframes in den aktiven, sichtbaren Kurven ausgewählt.")
            return {'CANCELLED'}
        
        self._initial_frame_start = context.scene.frame_start
        self._initial_frame_end = context.scene.frame_end
        
        if not context.scene.keep_framerange and context.screen.is_animation_playing:
            set_timeline_range_to_selected(context)
        
        if context.screen.is_animation_playing:
            context.scene.frame_current = context.scene.frame_start
        
        self.initial_mouse_x = event.mouse_x
        self.initial_handle_vectors.clear()
        self.initial_handle_types.clear()
        self._current_strength = 0.0
        self._current_seed = 0

        selected_keyframes_found = False
        for fcurve in context.selected_visible_fcurves:
            for keyframe_index, keyframe in enumerate(fcurve.keyframe_points):
                if keyframe.select_control_point:
                    
                    # Wert des aktuellen Keyframes
                    current_value = keyframe.co[1]
                    
                    # Checke, ob der Wert des vorherigen oder nächsten Keyframes anders ist
                    has_different_neighbor = False
                    num_decimals = 6  # Definiere die Anzahl der Nachkommastellen

                    # Runde den aktuellen Wert für den Vergleich
                    rounded_current_value = round(current_value, num_decimals)

                    if keyframe_index > 0:
                        prev_keyframe = fcurve.keyframe_points[keyframe_index - 1]
                        # Runde auch den Wert des vorherigen Keyframes
                        rounded_prev_value = round(prev_keyframe.co[1], num_decimals)
                        
                        if rounded_prev_value != rounded_current_value:
                            has_different_neighbor = True

                    if keyframe_index < len(fcurve.keyframe_points) - 1:
                        next_keyframe = fcurve.keyframe_points[keyframe_index + 1]
                        # Runde auch den Wert des nächsten Keyframes
                        rounded_next_value = round(next_keyframe.co[1], num_decimals)
                        
                        if rounded_next_value != rounded_current_value:
                            has_different_neighbor = True
                    
                    if has_different_neighbor:
                        selected_keyframes_found = True
                        key = (fcurve.data_path, keyframe_index, fcurve.array_index)
                        
                        self.initial_handle_types[key] = {
                            'left': keyframe.handle_left_type,
                            'right': keyframe.handle_right_type
                        }
                        self.initial_handle_vectors[key] = {
                            'left': (keyframe.handle_left[0] - keyframe.co[0], keyframe.handle_left[1] - keyframe.co[1]),
                            'right': (keyframe.handle_right[0] - keyframe.co[0], keyframe.handle_right[1] - keyframe.co[1]),
                        }

        if not selected_keyframes_found:
            self.report({'WARNING'}, "Neighbouring keys have the same value")
            return {'CANCELLED'}
        
        context.window.cursor_set('SCROLL_X')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


class OBJECT_OT_slide_handles(bpy.types.Operator):
    bl_idname = "object.slide_manipulator"
    bl_label = "Slide Handles"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Slide handles"
    
    _timer = None
    initial_mouse_x = None
    initial_handle_vectors = {}
    initial_handle_types = {}
    initial_keyframe_data = {}

    @classmethod
    def poll(cls, context):
        return (context.active_object and
                context.active_object.animation_data and
                context.active_object.animation_data.action and
                context.selected_visible_fcurves and
                len([kf for fc in context.selected_visible_fcurves for kf in fc.keyframe_points if kf.select_control_point]) > 0)

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            if event.mouse_x < 5 or event.mouse_x > context.window.width - 5:
                if event.mouse_x < 5:
                    new_x = context.window.width - 10
                else:
                    new_x = 10
                
                self.initial_mouse_x += (new_x - event.mouse_x)
                context.window.cursor_warp(new_x, event.mouse_y)
            
            delta_x = event.mouse_x - self.initial_mouse_x
            
            # Neue Logik: Das Verschieben der Maus steuert das Verhältnis
            # Vergrößerung/Schrumpfung
            ratio = max(min(delta_x / 200.0, 1.0), -1.0) # Begrenzt auf [-1, 1]

            for (data_path, keyframe_index, array_index), initial_vectors in self.initial_handle_vectors.items():
                fcurve = None
                for fc in context.active_object.animation_data.action.fcurves:
                    if fc.data_path == data_path and fc.array_index == array_index:
                        fcurve = fc
                        break

                if not fcurve:
                    continue
                
                keyframe = fcurve.keyframe_points[keyframe_index]
                
                vec_right_initial = initial_vectors['right']
                vec_left_initial = initial_vectors['left']

                length_right_initial = (vec_right_initial[0]**2 + vec_right_initial[1]**2)**0.5
                length_left_initial = (vec_left_initial[0]**2 + vec_left_initial[1]**2)**0.5
                
                # Gesamtlänge bleibt konstant
                total_length = length_right_initial + length_left_initial
                
                # Berechne die neue Länge für den rechten Handle
                new_length_right = length_right_initial * (1.0 + ratio)
                
                # Begrenze die neue Länge, um negativen oder zu hohen Werten vorzubeugen
                if new_length_right < 0:
                    new_length_right = 0
                if new_length_right > total_length:
                    new_length_right = total_length
                
                # Die neue Länge des linken Handles ist die Differenz zur Gesamtlänge
                new_length_left = total_length - new_length_right
                
                # Aktualisiere die Handles basierend auf den neuen Längen und den ursprünglichen Vektoren
                if length_right_initial > 0:
                    unit_vector_right = (vec_right_initial[0] / length_right_initial, vec_right_initial[1] / length_right_initial)
                    keyframe.handle_right[0] = keyframe.co[0] + unit_vector_right[0] * new_length_right
                    keyframe.handle_right[1] = keyframe.co[1] + unit_vector_right[1] * new_length_right
                
                if length_left_initial > 0:
                    unit_vector_left = (vec_left_initial[0] / length_left_initial, vec_left_initial[1] / length_left_initial)
                    keyframe.handle_left[0] = keyframe.co[0] + unit_vector_left[0] * new_length_left
                    keyframe.handle_left[1] = keyframe.co[1] + unit_vector_left[1] * new_length_left
            
            for area in context.screen.areas:
                if area.type in {'GRAPH_EDITOR', 'VIEW_3D'}:
                    area.tag_redraw()

        elif event.type == 'LEFTMOUSE':
            for (data_path, keyframe_index, array_index), types in self.initial_handle_types.items():
                fcurve = None
                for fc in context.active_object.animation_data.action.fcurves:
                    if fc.data_path == data_path and fc.array_index == array_index:
                        fcurve = fc
                        break
                
                if fcurve:
                    keyframe = fcurve.keyframe_points[keyframe_index]
                    keyframe.interpolation = 'BEZIER'
                    keyframe.handle_left_type = 'ALIGNED'
                    keyframe.handle_right_type = 'ALIGNED'
            
            context.scene.frame_start = self._initial_frame_start
            context.scene.frame_end = self._initial_frame_end
            
            context.window.cursor_set('DEFAULT')
            if self._timer:
                context.window_manager.event_timer_remove(self._timer)
            return {'FINISHED'}
        
        elif event.type == 'RIGHTMOUSE' or event.type == 'ESC':
            for (data_path, keyframe_index, array_index), initial_vectors in self.initial_handle_vectors.items():
                fcurve = None
                for fc in context.active_object.animation_data.action.fcurves:
                    if fc.data_path == data_path and fc.array_index == array_index:
                        fcurve = fc
                        break

                if not fcurve:
                    continue
                
                keyframe = fcurve.keyframe_points[keyframe_index]
                
                vec_right_initial = initial_vectors['right']
                keyframe.handle_right[0] = keyframe.co[0] + vec_right_initial[0]
                keyframe.handle_right[1] = keyframe.co[1] + vec_right_initial[1]

                vec_left_initial = initial_vectors['left']
                keyframe.handle_left[0] = keyframe.co[0] + vec_left_initial[0]
                keyframe.handle_left[1] = keyframe.co[1] + vec_left_initial[1]
                
                types = self.initial_handle_types[(data_path, keyframe_index, array_index)]
                keyframe.handle_left_type = types['left']
                keyframe.handle_right_type = types['right']
            
            context.scene.frame_start = self._initial_frame_start
            context.scene.frame_end = self._initial_frame_end
            
            context.window.cursor_set('DEFAULT')
            if self._timer:
                context.window_manager.event_timer_remove(self._timer)
            return {'CANCELLED'}          
        
        return {'RUNNING_MODAL'}
    
    def invoke(self, context, event):
        if context.active_object is None or context.active_object.animation_data is None:
            self.report({'WARNING'}, "No active object or animation data.")
            return {'CANCELLED'}

        if context.active_object is None or context.active_object.animation_data is None:
            self.report({'WARNING'}, "Kein aktives Objekt oder keine Animationsdaten.")
            return {'CANCELLED'}

        if not context.selected_visible_fcurves:
            self.report({'WARNING'}, "Keine F-Kurven im Graph Editor sichtbar und ausgewählt.")
            return {'CANCELLED'}
        
        self._initial_frame_start = context.scene.frame_start
        self._initial_frame_end = context.scene.frame_end
            
        # --- NEUE FUNKTION HIER AUFRUFEN ---
        if not context.scene.keep_framerange and context.screen.is_animation_playing:
            set_timeline_range_to_selected(context)

        self.initial_mouse_x = event.mouse_x
        self.initial_handle_vectors.clear()
        self.initial_handle_types.clear()
        self.initial_keyframe_data.clear()
        
        if context.screen.is_animation_playing:
            # Cursor zum Start der Timeline springen lassen
            context.scene.frame_current = context.scene.frame_start

        
        selected_keyframes_found = False
        for fcurve in context.selected_visible_fcurves:
            for keyframe_index, keyframe in enumerate(fcurve.keyframe_points):
                if keyframe.select_control_point:
                    selected_keyframes_found = True
                    key = (fcurve.data_path, keyframe_index, fcurve.array_index)
                    
                    self.initial_keyframe_data[key] = {
                        'co_x': keyframe.co[0],
                    }
                    
                    self.initial_handle_types[key] = {
                        'left': keyframe.handle_left_type,
                        'right': keyframe.handle_right_type
                    }
                    
                    self.initial_handle_vectors[key] = {
                        'left': (keyframe.handle_left[0] - keyframe.co[0], keyframe.handle_left[1] - keyframe.co[1]),
                        'right': (keyframe.handle_right[0] - keyframe.co[0], keyframe.handle_right[1] - keyframe.co[1]),
                    }

        if not selected_keyframes_found:
            self.report({'WARNING'}, "Keine Keyframes in den aktiven, sichtbaren Kurven ausgewählt.")
            return {'CANCELLED'}

        context.window.cursor_set('SCROLL_X')
        self._timer = context.window_manager.event_timer_add(0.01, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}



import bpy
import math

# Hilfsfunktionen sind hier nicht gezeigt, aber sie sollten vorhanden sein.
# set_handles_aligned
# reset_handles
# set_timeline_range_to_selected

class OBJECT_OT_manipulate_right_handles(bpy.types.Operator):
    bl_idname = "object.manipulate_right_handles"
    bl_label = "Manipulate Right Handles"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Extrude right handles"
    
    mode: bpy.props.EnumProperty(
        items=[
            ('EXTRUDE', "Extrude", "Extrudes the handles"),
            ('SLIDE', "Slide", "Slides the handles")
        ],
        name="Mode",
        default='EXTRUDE'
    )
    
    _timer = None
    initial_mouse_x = None
    initial_mouse_y = None
    
    initial_vectors_left_batch = {}
    initial_types_left_batch = {}
    initial_keyframe_coords_left_batch = {}
    initial_partner_x_coords_left = {}
    initial_keyframe_distances_left = {}
    
    initial_vectors_right_batch = {}
    initial_types_right_batch = {}
    initial_keyframe_coords_right_batch = {}
    initial_partner_x_coords_right = {}
    initial_keyframe_distances_right = {}
    
    

    @classmethod
    def poll(cls, context):
        if not (context.active_object and
                context.active_object.animation_data and
                context.active_object.animation_data.action and
                context.selected_visible_fcurves):
            return False
        
        for fcurve in context.selected_visible_fcurves:
            selected_keyframes_in_fcurve = [kf for kf in fcurve.keyframe_points if kf.select_control_point]
            if len(selected_keyframes_in_fcurve) >= 2:
                return True
        return False
    
    def modal(self, context, event):
        extrude_sensitivity = 0.1
        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
        # Wechsel den Modus bei Tastendruck 'X'
        #if event.type == 'X' and event.value == 'PRESS':
            if self.mode == 'EXTRUDE':
                self.mode = 'SLIDE'
                self.report({'INFO'}, "Switched to Slide Mode")
                context.window.cursor_set('SCROLL_Y')  # Besser passender Cursor
            elif self.mode == 'SLIDE':
                self.mode = 'EXTRUDE'
                self.report({'INFO'}, "Switched to Extrude Mode")
                context.window.cursor_set('SCROLL_X') # Besser passender Cursor
            
            # Setze die Maus-Position neu
            self.initial_mouse_x = event.mouse_x
            self.initial_mouse_y = event.mouse_y
            return {'RUNNING_MODAL'}
        
        if event.type == 'MOUSEMOVE':
            # Cursor-Warping-Logik
            if event.mouse_x < 5 or event.mouse_x > context.window.width - 5:
                if event.mouse_x < 5:
                    new_x = context.window.width - 10
                else:
                    new_x = 10
                self.initial_mouse_x += (new_x - event.mouse_x)
                context.window.cursor_warp(new_x, event.mouse_y)
            
            delta_x = event.mouse_x - self.initial_mouse_x
            
            # Gemeinsame Logik für beide Modi
            # left batch (handle right)
            for (data_path, keyframe_index, array_index), initial_vectors in self.initial_vectors_left_batch.items():
                fcurve = next((fc for fc in context.active_object.animation_data.action.fcurves if fc.data_path == data_path and fc.array_index == array_index), None)
                if not fcurve or keyframe_index >= len(fcurve.keyframe_points): continue
                keyframe = fcurve.keyframe_points[keyframe_index]
                vec_right_initial = initial_vectors['right']
                length_right_initial = math.sqrt(vec_right_initial[0]**2 + vec_right_initial[1]**2)
                
                # Modus-spezifische Logik für die Anpassung der Länge
                if self.mode == 'EXTRUDE':
                    adjustment_amount = (delta_x * extrude_sensitivity)
                elif self.mode == 'SLIDE':
                    adjustment_amount = (delta_x * extrude_sensitivity)

                keyframe_x_distance = self.initial_keyframe_distances_left.get((data_path, keyframe_index, array_index), 1.0)
                if keyframe_x_distance < 1.0: keyframe_x_distance = 1.0
                min_length = 0.001 * keyframe_x_distance
                
                new_length_right = max(length_right_initial + adjustment_amount, min_length)
                
                if length_right_initial > 1e-6:
                    factor = new_length_right / length_right_initial
                    new_x_right_unlimited = keyframe.co[0] + vec_right_initial[0] * factor
                    new_y_right_unlimited = keyframe.co[1] + vec_right_initial[1] * factor
                else:
                    new_x_right_unlimited = keyframe.co[0] + new_length_right
                    new_y_right_unlimited = keyframe.co[1]

                partner_x_coord = self.initial_partner_x_coords_left.get((data_path, keyframe_index, array_index), keyframe.co[0])
                new_x_right = max(min(new_x_right_unlimited, partner_x_coord), keyframe.co[0])
                
                dx_initial = initial_vectors['right'][0]
                dy_initial = initial_vectors['right'][1]

                if abs(dx_initial) > 1e-6:
                    new_y_right = keyframe.co[1] + (new_x_right - keyframe.co[0]) * (dy_initial / dx_initial)
                else:
                    if dy_initial > 0:
                        new_y_right = keyframe.co[1] + math.sqrt((new_x_right - keyframe.co[0])**2 + (new_y_right_unlimited - keyframe.co[1])**2)
                    else:
                        new_y_right = keyframe.co[1] - math.sqrt((new_x_right - keyframe.co[0])**2 + (new_y_right_unlimited - keyframe.co[1])**2)

                keyframe.handle_right[0] = new_x_right
                keyframe.handle_right[1] = new_y_right

            # right batch (handle left)
            for (data_path, keyframe_index, array_index), initial_vectors in self.initial_vectors_right_batch.items():
                fcurve = next((fc for fc in context.active_object.animation_data.action.fcurves if fc.data_path == data_path and fc.array_index == array_index), None)
                if not fcurve or keyframe_index >= len(fcurve.keyframe_points): continue
                keyframe = fcurve.keyframe_points[keyframe_index]
                vec_left_initial = initial_vectors['left']
                length_left_initial = math.sqrt(vec_left_initial[0]**2 + vec_left_initial[1]**2)

                # Modus-spezifische Logik für die Anpassung der Länge
                if self.mode == 'EXTRUDE':
                    adjustment_amount = (delta_x * extrude_sensitivity)
                elif self.mode == 'SLIDE':
                    adjustment_amount = -(delta_x * extrude_sensitivity)  # HIER WIRD DIE RICHTUNG UMGEKEHRT

                keyframe_x_distance = self.initial_keyframe_distances_right.get((data_path, keyframe_index, array_index), 1.0)
                if keyframe_x_distance < 1.0: keyframe_x_distance = 1.0
                min_length = 0.001 * keyframe_x_distance

                new_length_left = max(length_left_initial + adjustment_amount, min_length)
                
                if length_left_initial > 1e-6:
                    factor = new_length_left / length_left_initial
                    new_x_left_unlimited = keyframe.co[0] + vec_left_initial[0] * factor
                    new_y_left_unlimited = keyframe.co[1] + vec_left_initial[1] * factor
                else:
                    new_x_left_unlimited = keyframe.co[0] - new_length_left
                    new_y_left_unlimited = keyframe.co[1]
                
                partner_x_coord = self.initial_partner_x_coords_right.get((data_path, keyframe_index, array_index), keyframe.co[0])
                new_x_left = min(max(new_x_left_unlimited, partner_x_coord), keyframe.co[0])
                
                dx_initial = initial_vectors['left'][0]
                dy_initial = initial_vectors['left'][1]

                if abs(dx_initial) > 1e-6:
                    new_y_left = keyframe.co[1] + (new_x_left - keyframe.co[0]) * (dy_initial / dx_initial)
                else:
                    if dy_initial > 0:
                        new_y_left = keyframe.co[1] + math.sqrt((new_x_left - keyframe.co[0])**2 + (new_y_left_unlimited - keyframe.co[1])**2)
                    else:
                        new_y_left = keyframe.co[1] - math.sqrt((new_x_left - keyframe.co[0])**2 + (new_y_left_unlimited - keyframe.co[1])**2)

                keyframe.handle_left[0] = new_x_left
                keyframe.handle_left[1] = new_y_left
            
            # Finalize changes for both modes
            for area in context.screen.areas:
                if area.type in {'GRAPH_EDITOR', 'VIEW_3D'}:
                    area.tag_redraw()
            
            return {'RUNNING_MODAL'}
            
        elif event.type == 'LEFTMOUSE':
            set_handles_aligned(context, self.initial_types_left_batch)
            set_handles_aligned(context, self.initial_types_right_batch)
            context.scene.frame_start = self._initial_frame_start
            context.scene.frame_end = self._initial_frame_end
            context.window.cursor_set('DEFAULT')
            if self._timer:
                context.window_manager.event_timer_remove(self._timer)
            return {'FINISHED'}
        
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            reset_handles(context, self.initial_vectors_left_batch, self.initial_types_left_batch, self.initial_keyframe_coords_left_batch)
            reset_handles(context, self.initial_vectors_right_batch, self.initial_types_right_batch, self.initial_keyframe_coords_right_batch)
            context.scene.frame_start = self._initial_frame_start
            context.scene.frame_end = self._initial_frame_end
            context.window.cursor_set('DEFAULT')
            if self._timer:
                context.window_manager.event_timer_remove(self._timer)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}
    
    def invoke(self, context, event):
        self.mode = 'EXTRUDE'
        if not self.poll(context):
            self.report({'WARNING'}, "No active object or matching keyframes found.")
            return {'CANCELLED'}
        
        # Den Modus nicht explizit auf "EXTRUDE" setzen.
        # Er wird automatisch auf den Standardwert des EnumProperty gesetzt,
        # wenn der Operator zum ersten Mal ausgeführt wird,
        # und behält seinen Wert danach bei, bis er geändert wird.

        self.initial_mouse_x = event.mouse_x
        self.initial_mouse_y = event.mouse_y
        self._initial_frame_start = context.scene.frame_start
        self._initial_frame_end = context.scene.frame_end
        
        # Clear all dictionaries
        self.initial_vectors_left_batch.clear()
        self.initial_types_left_batch.clear()
        self.initial_keyframe_coords_left_batch.clear()
        self.initial_partner_x_coords_left.clear()
        self.initial_keyframe_distances_left.clear()
        self.initial_vectors_right_batch.clear()
        self.initial_types_right_batch.clear()
        self.initial_keyframe_coords_right_batch.clear()
        self.initial_partner_x_coords_right.clear()
        self.initial_keyframe_distances_right.clear()
        
        has_valid_pair = False
        for fcurve in context.selected_visible_fcurves:
            selected_keyframes_with_indices = [(index, kf) for index, kf in enumerate(fcurve.keyframe_points) if kf.select_control_point]
            if len(selected_keyframes_with_indices) >= 2:
                has_valid_pair = True
                selected_keyframes_with_indices.sort(key=lambda item: item[1].co[0])
                first_keyframe_index, first_keyframe = selected_keyframes_with_indices[0]
                last_keyframe_index, last_keyframe = selected_keyframes_with_indices[-1]

                keyframe_x_distance = last_keyframe.co[0] - first_keyframe.co[0]
                self.initial_keyframe_distances_left[(fcurve.data_path, first_keyframe_index, fcurve.array_index)] = keyframe_x_distance
                self.initial_keyframe_distances_right[(fcurve.data_path, last_keyframe_index, fcurve.array_index)] = keyframe_x_distance

                key_first = (fcurve.data_path, first_keyframe_index, fcurve.array_index)
                key_last = (fcurve.data_path, last_keyframe_index, fcurve.array_index)
                
                self.initial_types_left_batch[key_first] = {'left': first_keyframe.handle_left_type, 'right': first_keyframe.handle_right_type}
                self.initial_vectors_left_batch[key_first] = {'left': (first_keyframe.handle_left[0] - first_keyframe.co[0], first_keyframe.handle_left[1] - first_keyframe.co[1]),
                                                             'right': (first_keyframe.handle_right[0] - first_keyframe.co[0], first_keyframe.handle_right[1] - first_keyframe.co[1])}
                self.initial_keyframe_coords_left_batch[key_first] = {'co_x': first_keyframe.co[0], 'co_y': first_keyframe.co[1]}
                self.initial_partner_x_coords_left[key_first] = last_keyframe.co[0]

                self.initial_types_right_batch[key_last] = {'left': last_keyframe.handle_left_type, 'right': last_keyframe.handle_right_type}
                self.initial_vectors_right_batch[key_last] = {'left': (last_keyframe.handle_left[0] - last_keyframe.co[0], last_keyframe.handle_left[1] - last_keyframe.co[1]),
                                                             'right': (last_keyframe.handle_right[0] - last_keyframe.co[0], last_keyframe.handle_right[1] - last_keyframe.co[1])}
                self.initial_keyframe_coords_right_batch[key_last] = {'co_x': last_keyframe.co[0], 'co_y': last_keyframe.co[1]}
                self.initial_partner_x_coords_right[key_last] = first_keyframe.co[0]

        if not has_valid_pair:
            self.report({'WARNING'}, "Es wurden keine F-Kurven gefunden, die mindestens zwei ausgewählte Keyframes enthalten.")
            return {'CANCELLED'}

        if not context.scene.keep_framerange and context.screen.is_animation_playing:
            set_timeline_range_to_selected(context)

        context.window.cursor_set('SCROLL_X')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

from mathutils import Vector

class OBJECT_OT_scale_handles(bpy.types.Operator):
    bl_idname = "object.scale_handles"
    bl_label = "scale handles"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Mousewheel for Y- or X-Axis"
    
    _timer = None
    initial_mouse_x = None
    initial_mouse_y = None
    _mode = 'X_AXIS'
    initial_handle_vectors = {}
    initial_handle_types = {}
    initial_keyframe_data = {}
    _initial_frame_start = None
    _initial_frame_end = None

    @classmethod
    def poll(cls, context):
        return (context.active_object and
                context.active_object.animation_data and
                context.active_object.animation_data.action and
                context.selected_visible_fcurves and
                len([kf for fc in context.selected_visible_fcurves for kf in fc.keyframe_points if kf.select_control_point]) > 0)
    
    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            # Maus-Warping für unendliche Bewegung
            if event.mouse_x < 5 or event.mouse_x > context.window.width - 5:
                if event.mouse_x < 5:
                    new_x = context.window.width - 10
                else:
                    new_x = 10
                self.initial_mouse_x += (new_x - event.mouse_x)
                context.window.cursor_warp(new_x, event.mouse_y)

            if event.mouse_y < 5 or event.mouse_y > context.window.height - 5:
                if event.mouse_y < 5:
                    new_y = context.window.height - 10
                else:
                    new_y = 10
                self.initial_mouse_y += (new_y - event.mouse_y)
                context.window.cursor_warp(event.mouse_x, new_y)

            delta_x = event.mouse_x - self.initial_mouse_x
            delta_y = event.mouse_y - self.initial_mouse_y
            
            if self._mode == 'X_AXIS':
                factor = delta_x / 200.0
            elif self._mode == 'Y_AXIS':
                factor = delta_x / 200.0
            else: # 'XY_AXIS'
                factor = delta_x / 200.0

            for key, initial_vectors in self.initial_handle_vectors.items():
                data_path, keyframe_index, array_index = key

                fcurve = None
                for fc in context.active_object.animation_data.action.fcurves:
                    if fc.data_path == data_path and fc.array_index == array_index:
                        fcurve = fc
                        break

                if not fcurve:
                    continue
                
                keyframe = fcurve.keyframe_points[keyframe_index]
                vec_left_initial = Vector(initial_vectors['left'])
                vec_right_initial = Vector(initial_vectors['right'])

                if self._mode == 'X_AXIS':
                    # Skalierung nur in X-Richtung
                    new_x_left = keyframe.co[0] + vec_left_initial.x * (1.0 + factor)
                    new_y_left = keyframe.co[1] + vec_left_initial.y
                    keyframe.handle_left[0] = new_x_left
                    keyframe.handle_left[1] = new_y_left
                    
                    new_x_right = keyframe.co[0] + vec_right_initial.x * (1.0 + factor)
                    new_y_right = keyframe.co[1] + vec_right_initial.y
                    keyframe.handle_right[0] = new_x_right
                    keyframe.handle_right[1] = new_y_right

                elif self._mode == 'Y_AXIS':
                    # Skalierung nur in Y-Richtung
                    new_x_left = keyframe.co[0] + vec_left_initial.x
                    new_y_left = keyframe.co[1] + vec_left_initial.y * (1.0 + factor)
                    keyframe.handle_left[0] = new_x_left
                    keyframe.handle_left[1] = new_y_left
                    
                    new_x_right = keyframe.co[0] + vec_right_initial.x
                    new_y_right = keyframe.co[1] + vec_right_initial.y * (1.0 + factor)
                    keyframe.handle_right[0] = new_x_right
                    keyframe.handle_right[1] = new_y_right
                
                elif self._mode == 'XY_AXIS':
                    # Proportionale Skalierung in X und Y
                    new_vec_left = vec_left_initial * (1.0 + factor)
                    new_vec_right = vec_right_initial * (1.0 + factor)
                    
                    keyframe.handle_left = keyframe.co + new_vec_left
                    keyframe.handle_right = keyframe.co + new_vec_right
                    
            for area in context.screen.areas:
                if area.type in {'GRAPH_EDITOR', 'VIEW_3D'}:
                    area.tag_redraw()

        elif event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            self.initial_mouse_x = event.mouse_x
            self.initial_mouse_y = event.mouse_y
            
            if self._mode == 'X_AXIS':    
                self._mode = 'XY_AXIS'
                context.window.cursor_set('SCROLL_X')
                self.report({'INFO'}, f"Initial-Axis")
            elif self._mode == 'Y_AXIS':
                self._mode = 'X_AXIS'
                context.window.cursor_set('SCROLL_X')
                self.report({'INFO'}, f"X-Axis")
            else:
                self._mode = 'Y_AXIS'
                context.window.cursor_set('SCROLL_X')
                self.report({'INFO'}, f"Y-Axis")
                
            
            
        elif event.type == 'LEFTMOUSE':
            for key, types in self.initial_handle_types.items():
                data_path, keyframe_index, array_index = key
                fcurve = None
                for fc in context.active_object.animation_data.action.fcurves:
                    if fc.data_path == data_path and fc.array_index == array_index:
                        fcurve = fc
                        break
                
                if fcurve:
                    keyframe = fcurve.keyframe_points[keyframe_index]
                    keyframe.interpolation = 'BEZIER'
                    keyframe.handle_left_type = 'ALIGNED'
                    keyframe.handle_right_type = 'ALIGNED'
            
            context.scene.frame_start = self._initial_frame_start
            context.scene.frame_end = self._initial_frame_end
                    
            context.window.cursor_set('DEFAULT')
            if self._timer:
                context.window_manager.event_timer_remove(self._timer)
            return {'FINISHED'}
        
        elif event.type == 'RIGHTMOUSE' or event.type == 'ESC':
            for key, initial_vectors in self.initial_handle_vectors.items():
                data_path, keyframe_index, array_index = key
                fcurve = None
                for fc in context.active_object.animation_data.action.fcurves:
                    if fc.data_path == data_path and fc.array_index == array_index:
                        fcurve = fc
                        break

                if not fcurve:
                    continue
                
                keyframe = fcurve.keyframe_points[keyframe_index]
                
                vec_right_initial = initial_vectors['right']
                keyframe.handle_right[0] = keyframe.co[0] + vec_right_initial[0]
                keyframe.handle_right[1] = keyframe.co[1] + vec_right_initial[1]

                vec_left_initial = initial_vectors['left']
                keyframe.handle_left[0] = keyframe.co[0] + vec_left_initial[0]
                keyframe.handle_left[1] = keyframe.co[1] + vec_left_initial[1]
                
                types = self.initial_handle_types[key]
                keyframe.handle_left_type = types['left']
                keyframe.handle_right_type = types['right']
            
            context.scene.frame_start = self._initial_frame_start
            context.scene.frame_end = self._initial_frame_end
            
            context.window.cursor_set('DEFAULT')
            if self._timer:
                context.window_manager.event_timer_remove(self._timer)
            return {'CANCELLED'}          
        
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        self.report({'INFO'}, f"Initial-Axis")
        if context.active_object is None or context.active_object.animation_data is None:
            self.report({'WARNING'}, "Kein aktives Objekt oder keine Animationsdaten.")
            return {'CANCELLED'}

        if not context.selected_visible_fcurves:
            self.report({'WARNING'}, "Keine F-Kurven im Graph Editor sichtbar und ausgewählt.")
            return {'CANCELLED'}
        
        self._initial_frame_start = context.scene.frame_start
        self._initial_frame_end = context.scene.frame_end
        
        if not context.scene.keep_framerange and context.screen.is_animation_playing:
            set_timeline_range_to_selected(context)

        self.initial_mouse_x = event.mouse_x
        self.initial_mouse_y = event.mouse_y
        self._mode = 'XY_AXIS'
        self.initial_handle_vectors.clear()
        self.initial_handle_types.clear()
        self.initial_keyframe_data.clear()
        
        if context.screen.is_animation_playing:
            context.scene.frame_current = context.scene.frame_start

        selected_keyframes_found = False
        for fcurve in context.selected_visible_fcurves:
            for keyframe_index, keyframe in enumerate(fcurve.keyframe_points):
                if keyframe.select_control_point:
                    selected_keyframes_found = True
                    key = (fcurve.data_path, keyframe_index, fcurve.array_index)
                    
                    self.initial_keyframe_data[key] = {
                        'co_x': keyframe.co[0],
                    }
                    
                    self.initial_handle_types[key] = {
                        'left': keyframe.handle_left_type,
                        'right': keyframe.handle_right_type
                    }
                    
                    self.initial_handle_vectors[key] = {
                        'left': (keyframe.handle_left[0] - keyframe.co[0], keyframe.handle_left[1] - keyframe.co[1]),
                        'right': (keyframe.handle_right[0] - keyframe.co[0], keyframe.handle_right[1] - keyframe.co[1]),
                    }

        if not selected_keyframes_found:
            self.report({'WARNING'}, "Keine Keyframes in den aktiven, sichtbaren Kurven ausgewählt.")
            return {'CANCELLED'}

        context.window.cursor_set('SCROLL_X')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}







class OBJECT_OT_extrude_slide_handles_between_frames(bpy.types.Operator):
    bl_idname = "object.extrude_slide_handles_between_frames"
    bl_label = "slide batches"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Select two consecutive keyframes. Mousewheel for Extrude or Slide on X-Axis. Hold ALT for Y-Axis"
    
    _timer = None
    initial_mouse_x = None
    initial_mouse_y = None
    initial_vectors_left_batch = {}
    initial_types_left_batch = {}
    initial_vectors_right_batch = {}
    initial_types_right_batch = {}
    initial_keyframe_coords_left_batch = {}
    initial_keyframe_coords_right_batch = {}
    initial_keyframe_distances = {}
    
    # Variable für den Umschalt-Modus
    invert_effect = False

    @classmethod
    def poll(cls, context):
        if not (context.active_object and
                context.active_object.animation_data and
                context.active_object.animation_data.action and
                context.selected_visible_fcurves):
            return False
        
        for fcurve in context.selected_visible_fcurves:
            selected_keyframes_in_fcurve = [kf for kf in fcurve.keyframe_points if kf.select_control_point]
            if len(selected_keyframes_in_fcurve) >= 2:
                return True
        return False
    
    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            # Cursor-Warping-Logik
            if event.mouse_x < 5 or event.mouse_x > context.window.width - 5:
                if event.mouse_x < 5:
                    new_x = context.window.width - 10
                else:
                    new_x = 10
                self.initial_mouse_x += (new_x - event.mouse_x)
                context.window.cursor_warp(new_x, event.mouse_y)

            delta_x = event.mouse_x - self.initial_mouse_x
            delta_y = event.mouse_y - self.initial_mouse_y
            
            angle_sensitivity = 0.005
            translate_sensitivity = 0.05

            if event.alt:
                x_movement_factor = 0.0
                y_movement_factor = 1.0
            else:
                x_movement_factor = 1.0
                y_movement_factor = 0.0

            # Verarbeitung für den linken Keyframe (Handle Right)
            for (data_path, keyframe_index, array_index), initial_vectors in self.initial_vectors_left_batch.items():
                fcurve = next((fc for fc in context.active_object.animation_data.action.fcurves if fc.data_path == data_path and fc.array_index == array_index), None)
                if not fcurve or keyframe_index >= len(fcurve.keyframe_points):
                    continue
                
                keyframe = fcurve.keyframe_points[keyframe_index]
                
                # Verschieben des inneren (rechten) Handles
                vec_right_initial = initial_vectors['right']
                keyframe_x_distance = self.initial_keyframe_distances[(data_path, keyframe_index, array_index)]
                initial_handle_x = keyframe.co[0] + vec_right_initial[0]
                new_x_right = initial_handle_x + (delta_x * translate_sensitivity * x_movement_factor)
                min_x = keyframe.co[0]
                max_x = keyframe.co[0] + keyframe_x_distance
                new_x_right_clamped = max(min_x, min(max_x, new_x_right))

                initial_angle_rad_right = math.atan2(vec_right_initial[1], vec_right_initial[0])
                adjustment_sign_right = 1.0 if vec_right_initial[1] >= 0 else -1.0
                angle_adjustment_right = math.radians(delta_y * angle_sensitivity * y_movement_factor * adjustment_sign_right)
                new_angle_rad_right = initial_angle_rad_right + angle_adjustment_right
                
                length_right_initial = math.sqrt(vec_right_initial[0]**2 + vec_right_initial[1]**2)
                
                keyframe.handle_right[0] = new_x_right_clamped
                keyframe.handle_right[1] = keyframe.co[1] + length_right_initial * math.sin(new_angle_rad_right)

                # NEUE LOGIK: Setze den äußeren (linken) Handle relativ zum inneren
                vec_left_initial = initial_vectors['left']
                length_left_initial = math.sqrt(vec_left_initial[0]**2 + vec_left_initial[1]**2)
                
                # Verwende den neuen Winkel des inneren Handles + 180 Grad
                new_angle_rad_left = math.atan2(keyframe.handle_right[1] - keyframe.co[1], keyframe.handle_right[0] - keyframe.co[0]) + math.pi
                
                keyframe.handle_left[0] = keyframe.co[0] + length_left_initial * math.cos(new_angle_rad_left)
                keyframe.handle_left[1] = keyframe.co[1] + length_left_initial * math.sin(new_angle_rad_left)

            # Verarbeitung für den rechten Keyframe (Handle Left)
            for (data_path, keyframe_index, array_index), initial_vectors in self.initial_vectors_right_batch.items():
                fcurve = next((fc for fc in context.active_object.animation_data.action.fcurves if fc.data_path == data_path and fc.array_index == array_index), None)
                if not fcurve or keyframe_index >= len(fcurve.keyframe_points):
                    continue
                
                keyframe = fcurve.keyframe_points[keyframe_index]
                left_keyframe = fcurve.keyframe_points[keyframe_index - 1]
                
                # Verschieben des inneren (linken) Handles
                vec_left_initial = initial_vectors['left']
                initial_handle_x = keyframe.co[0] + vec_left_initial[0]
                
                if self.invert_effect:
                    new_x_left = initial_handle_x + (delta_x * translate_sensitivity * x_movement_factor)
         
                else:
                    new_x_left = initial_handle_x - (delta_x * translate_sensitivity * x_movement_factor)
                
                min_x = left_keyframe.co[0]
                max_x = keyframe.co[0]
                new_x_left_clamped = max(min_x, min(max_x, new_x_left))
                
                initial_angle_rad_left = math.atan2(vec_left_initial[1], vec_left_initial[0])
                adjustment_sign_left = -1.0 if vec_left_initial[1] >= 0 else 1.0
                
                if self.invert_effect:
                    angle_adjustment_left = math.radians(delta_y * angle_sensitivity * y_movement_factor * adjustment_sign_left)
                else:
                    angle_adjustment_left = math.radians(-delta_y * angle_sensitivity * y_movement_factor * adjustment_sign_left)
                        
                new_angle_rad_left = initial_angle_rad_left + angle_adjustment_left
                length_left_initial = math.sqrt(vec_left_initial[0]**2 + vec_left_initial[1]**2)

                keyframe.handle_left[0] = new_x_left_clamped
                keyframe.handle_left[1] = keyframe.co[1] + length_left_initial * math.sin(new_angle_rad_left)
                
                # NEUE LOGIK: Setze den äußeren (rechten) Handle relativ zum inneren
                vec_right_initial = initial_vectors['right']
                length_right_initial = math.sqrt(vec_right_initial[0]**2 + vec_right_initial[1]**2)
                
                # Verwende den neuen Winkel des inneren Handles + 180 Grad
                new_angle_rad_right = math.atan2(keyframe.handle_left[1] - keyframe.co[1], keyframe.handle_left[0] - keyframe.co[0]) + math.pi
                
                keyframe.handle_right[0] = keyframe.co[0] + length_right_initial * math.cos(new_angle_rad_right)
                keyframe.handle_right[1] = keyframe.co[1] + length_right_initial * math.sin(new_angle_rad_right)


            for area in context.screen.areas:
                if area.type in {'GRAPH_EDITOR', 'VIEW_3D'}:
                    area.tag_redraw()
            
            return {'RUNNING_MODAL'}
        
        elif event.type == 'WHEELUPMOUSE' or event.type == 'WHEELDOWNMOUSE':
            self.invert_effect = not self.invert_effect
            if self.invert_effect == 0:
                self.report({'INFO'}, "EXTRUDE")
            else:
                self.report({'INFO'}, "SLIDE")
                
            for area in context.screen.areas:
                if area.type in {'GRAPH_EDITOR', 'VIEW_3D'}:
                    area.tag_redraw()
            return {'RUNNING_MODAL'}
        
        elif event.type == 'LEFTMOUSE':
            set_handles_aligned(context, self.initial_types_left_batch)
            set_handles_aligned(context, self.initial_types_right_batch)
            context.scene.frame_start = self._initial_frame_start
            context.scene.frame_end = self._initial_frame_end
            context.window.cursor_set('DEFAULT')
            if self._timer:
                context.window_manager.event_timer_remove(self._timer)
            self.invert_effect = False
            return {'FINISHED'}
        
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            reset_handles(context, self.initial_vectors_left_batch, self.initial_types_left_batch, self.initial_keyframe_coords_left_batch)
            reset_handles(context, self.initial_vectors_right_batch, self.initial_types_right_batch, self.initial_keyframe_coords_right_batch)
            context.scene.frame_start = self._initial_frame_start
            context.scene.frame_end = self._initial_frame_end
            context.window.cursor_set('DEFAULT')
            if self._timer:
                context.window_manager.event_timer_remove(self._timer)
            self.invert_effect = False
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        self.report({'INFO'}, "EXTRUDE")
         
        if context.active_object is None or context.active_object.animation_data is None:
            self.report({'WARNING'}, "Kein aktives Objekt oder keine Animationsdaten gefunden.")
            return {'CANCELLED'}

        if not context.selected_visible_fcurves:
            self.report({'WARNING'}, "Keine F-Kurven im Graph Editor sichtbar und ausgewählt.")
            return {'CANCELLED'}

        self.initial_vectors_left_batch.clear()
        self.initial_types_left_batch.clear()
        self.initial_vectors_right_batch.clear()
        self.initial_types_right_batch.clear()
        self.initial_keyframe_coords_left_batch.clear()
        self.initial_keyframe_coords_right_batch.clear()
        self.initial_keyframe_distances.clear()
        
        has_valid_pair = False
        
        for fcurve in context.selected_visible_fcurves:
            selected_keyframes_with_indices = [
                (index, kf) for index, kf in enumerate(fcurve.keyframe_points) if kf.select_control_point
            ]

            if len(selected_keyframes_with_indices) >= 2:
                has_valid_pair = True
                
                selected_keyframes_with_indices.sort(key=lambda item: item[1].co[0])
                
                first_keyframe_index, first_keyframe = selected_keyframes_with_indices[0]
                last_keyframe_index, last_keyframe = selected_keyframes_with_indices[-1]

                keyframe_x_distance = last_keyframe.co[0] - first_keyframe.co[0]
                self.initial_keyframe_distances[(fcurve.data_path, first_keyframe_index, fcurve.array_index)] = keyframe_x_distance

                key_first = (fcurve.data_path, first_keyframe_index, fcurve.array_index)
                key_last = (fcurve.data_path, last_keyframe_index, fcurve.array_index)
                
                self.initial_types_left_batch[key_first] = {
                    'left': first_keyframe.handle_left_type,
                    'right': first_keyframe.handle_right_type
                }
                self.initial_vectors_left_batch[key_first] = {
                    'left': (first_keyframe.handle_left[0] - first_keyframe.co[0], first_keyframe.handle_left[1] - first_keyframe.co[1]),
                    'right': (first_keyframe.handle_right[0] - first_keyframe.co[0], first_keyframe.handle_right[1] - first_keyframe.co[1]),
                }
                self.initial_keyframe_coords_left_batch[key_first] = {'co_x': first_keyframe.co[0], 'co_y': first_keyframe.co[1]}
                
                self.initial_types_right_batch[key_last] = {
                    'left': last_keyframe.handle_left_type,
                    'right': last_keyframe.handle_right_type
                }
                self.initial_vectors_right_batch[key_last] = {
                    'left': (last_keyframe.handle_left[0] - last_keyframe.co[0], last_keyframe.handle_left[1] - last_keyframe.co[1]),
                    'right': (last_keyframe.handle_right[0] - last_keyframe.co[0], last_keyframe.handle_right[1] - last_keyframe.co[1]),
                }
                self.initial_keyframe_coords_right_batch[key_last] = {'co_x': last_keyframe.co[0], 'co_y': last_keyframe.co[1]}
        
        if not has_valid_pair:
            self.report({'WARNING'}, "Es wurden keine F-Kurven gefunden, die mindestens zwei ausgewählte Keyframes enthalten.")
            return {'CANCELLED'}

        self._initial_frame_start = context.scene.frame_start
        self._initial_frame_end = context.scene.frame_end
        
        if not context.scene.keep_framerange and context.screen.is_animation_playing:
            set_timeline_range_to_selected(context)

        self.initial_mouse_x = event.mouse_x
        self.initial_mouse_y = event.mouse_y # Neu hinzugefügt
        
        if context.screen.is_animation_playing:
            context.scene.frame_current = context.scene.frame_start
        
        context.window.cursor_set('SCROLL_X')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


class OBJECT_OT_extrude_handles_between_frames(bpy.types.Operator):
    bl_idname = "object.extrude_handles_between_frames"
    bl_label = "extrude_handles_between_frames"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Mousewheel for Extrude or Slide on Initial-Axis. Select two consecutive keyframes"
    
    _timer = None
    initial_mouse_x = None
    
    initial_vectors_left_batch = {}
    initial_types_left_batch = {}
    initial_keyframe_coords_left_batch = {}
    initial_partner_x_coords_left = {}
    
    initial_vectors_right_batch = {}
    initial_types_right_batch = {}
    initial_keyframe_coords_right_batch = {}
    initial_partner_x_coords_right = {}
    
    initial_keyframe_distances = {}

    invert_effect = True

    @classmethod
    def poll(cls, context):
        if not (context.active_object and
                context.active_object.animation_data and
                context.active_object.animation_data.action and
                context.selected_visible_fcurves):
            return False
        
        for fcurve in context.selected_visible_fcurves:
            selected_keyframes_in_fcurve = [kf for kf in fcurve.keyframe_points if kf.select_control_point]
            if len(selected_keyframes_in_fcurve) >= 2:
                return True
        return False

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            if event.mouse_x < 5 or event.mouse_x > context.window.width - 5:
                if event.mouse_x < 5:
                    new_x = context.window.width - 10
                else:
                    new_x = 10
                
                self.initial_mouse_x += (new_x - event.mouse_x)
                context.window.cursor_warp(new_x, event.mouse_y)
            
            delta_x = event.mouse_x - self.initial_mouse_x
            
            # Verarbeitung für den linken Keyframe (Handle Right)
            # Diese Logik bleibt immer gleich, unabhängig vom invert_effect
            for (data_path, keyframe_index, array_index), initial_vectors in self.initial_vectors_left_batch.items():
                fcurve = None
                for fc in context.active_object.animation_data.action.fcurves:
                    if fc.data_path == data_path and fc.array_index == array_index:
                        fcurve = fc
                        break

                if not fcurve: continue
                if keyframe_index >= len(fcurve.keyframe_points): continue
                
                keyframe = fcurve.keyframe_points[keyframe_index]
                vec_right_initial = initial_vectors['right']
                length_right_initial = math.sqrt(vec_right_initial[0]**2 + vec_right_initial[1]**2)

                keyframe_x_distance = self.initial_keyframe_distances.get((data_path, keyframe_index, array_index), 1.0)
                if keyframe_x_distance < 1.0: keyframe_x_distance = 1.0

                min_length = 0.001 * keyframe_x_distance

                # Standard-Extrusion: Länge erhöht sich mit positivem delta_x
                adjustment_amount = (delta_x * keyframe_x_distance * 0.005)

                new_length_right = length_right_initial + adjustment_amount

                new_length_right = max(new_length_right, min_length)

                if length_right_initial > 1e-6:
                    new_x_right_unlimited = keyframe.co[0] + vec_right_initial[0] / length_right_initial * new_length_right
                    new_y_right_unlimited = keyframe.co[1] + vec_right_initial[1] / length_right_initial * new_length_right
                else:
                    new_length_right = max(new_length_right, min_length)
                    if new_length_right > 0:
                        vec_right = (1.0, 0.0)
                        new_x_right_unlimited = keyframe.co[0] + vec_right[0] * new_length_right
                        new_y_right_unlimited = keyframe.co[1] + vec_right[1] * new_length_right
                    else:
                        new_x_right_unlimited = keyframe.co[0]
                        new_y_right_unlimited = keyframe.co[1]
                
                partner_x_coord = self.initial_partner_x_coords_left.get((data_path, keyframe_index, array_index), keyframe.co[0])
                
                new_x_right = max(min(new_x_right_unlimited, partner_x_coord), keyframe.co[0])
                
                dx = new_x_right - keyframe.co[0]
                dy = (vec_right_initial[1] / vec_right_initial[0]) * dx if abs(vec_right_initial[0]) > 1e-6 else 0
                new_y_right = keyframe.co[1] + dy
                
                keyframe.handle_right[0] = new_x_right
                keyframe.handle_right[1] = new_y_right

            
            # Verarbeitung für den rechten Keyframe (Handle Left)
            # Hier wird die Logik basierend auf invert_effect umgeschaltet
            for (data_path, keyframe_index, array_index), initial_vectors in self.initial_vectors_right_batch.items():
                fcurve = None
                for fc in context.active_object.animation_data.action.fcurves:
                    if fc.data_path == data_path and fc.array_index == array_index:
                        fcurve = fc
                        break

                if not fcurve: continue
                if keyframe_index >= len(fcurve.keyframe_points): continue

                keyframe = fcurve.keyframe_points[keyframe_index]
                vec_left_initial = initial_vectors['left']
                length_left_initial = math.sqrt(vec_left_initial[0]**2 + vec_left_initial[1]**2)
                
                keyframe_x_distance = self.initial_keyframe_distances.get((data_path, keyframe_index, array_index), 1.0)
                if keyframe_x_distance < 1.0: keyframe_x_distance = 1.0
                
                min_length = 0.001 * keyframe_x_distance

                # KORREKTUR: Jetzt nur hier die Anpassung der Richtung
                if not self.invert_effect:
                    # Standard: Länge verringert sich mit positivem delta_x
                    adjustment_amount = (-delta_x * keyframe_x_distance * 0.005)
                else:
                    # Invertiert: Länge verringert sich mit negativem delta_x
                    adjustment_amount = (delta_x * keyframe_x_distance * 0.005)
                
                new_length_left = length_left_initial + adjustment_amount

                new_length_left = max(new_length_left, min_length)

                if length_left_initial > 1e-6:
                    new_x_left_unlimited = keyframe.co[0] + vec_left_initial[0] / length_left_initial * new_length_left
                    new_y_left_unlimited = keyframe.co[1] + vec_left_initial[1] / length_left_initial * new_length_left
                else:
                    new_length_left = max(new_length_left, min_length)
                    if new_length_left > 0:
                        vec_left = (-1.0, 0.0)
                        new_x_left_unlimited = keyframe.co[0] + vec_left[0] * new_length_left
                        new_y_left_unlimited = keyframe.co[1] + vec_left[1] * new_length_left
                    else:
                        new_x_left_unlimited = keyframe.co[0]
                        new_y_left_unlimited = keyframe.co[1]

                partner_x_coord = self.initial_partner_x_coords_right.get((data_path, keyframe_index, array_index), keyframe.co[0])
                
                new_x_left = min(max(new_x_left_unlimited, partner_x_coord), keyframe.co[0])
                
                dx = new_x_left - keyframe.co[0]
                dy = (vec_left_initial[1] / vec_left_initial[0]) * dx if abs(vec_left_initial[0]) > 1e-6 else 0
                new_y_left = keyframe.co[1] + dy
                
                keyframe.handle_left[0] = new_x_left
                keyframe.handle_left[1] = new_y_left

            for area in context.screen.areas:
                if area.type in {'GRAPH_EDITOR', 'VIEW_3D'}:
                    area.tag_redraw()
            
            return {'RUNNING_MODAL'}
        
        elif event.type == 'WHEELUPMOUSE' or event.type == 'WHEELDOWNMOUSE':
            self.invert_effect = not self.invert_effect
            # KORREKTUR: Setze die Initialmausposition zurück, um ein Springen zu verhindern
            self.initial_mouse_x = event.mouse_x
            if self.invert_effect == 1:
                self.report({'INFO'}, "EXTRUDE")
            else:
                self.report({'INFO'}, "SLIDE")
            for area in context.screen.areas:
                if area.type in {'GRAPH_EDITOR', 'VIEW_3D'}:
                    area.tag_redraw()
            return {'RUNNING_MODAL'}
        
        elif event.type == 'LEFTMOUSE':
            set_handles_aligned(context, self.initial_types_left_batch)
            set_handles_aligned(context, self.initial_types_right_batch)
            
            context.scene.frame_start = self._initial_frame_start
            context.scene.frame_end = self._initial_frame_end
            
            context.window.cursor_set('DEFAULT')
            if self._timer:
                context.window_manager.event_timer_remove(self._timer)
            self.invert_effect = False
            return {'FINISHED'}
        
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            reset_handles(context, self.initial_vectors_left_batch, self.initial_types_left_batch, self.initial_keyframe_coords_left_batch)
            reset_handles(context, self.initial_vectors_right_batch, self.initial_types_right_batch, self.initial_keyframe_coords_right_batch)
            
            context.scene.frame_start = self._initial_frame_start
            context.scene.frame_end = self._initial_frame_end
            
            context.window.cursor_set('DEFAULT')
            if self._timer:
                context.window_manager.event_timer_remove(self._timer)
            self.invert_effect = False
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}
    
    def invoke(self, context, event):
        self.report({'INFO'}, "EXTRUDE")
        # ... (dein restlicher invoke Code bleibt unverändert) ...
        if context.active_object is None or context.active_object.animation_data is None:
            self.report({'WARNING'}, "No active object")
            return {'CANCELLED'}

        if not context.selected_visible_fcurves:
            self.report({'WARNING'}, "No f-curves visible")
            return {'CANCELLED'}
        
        self.initial_vectors_left_batch.clear()
        self.initial_types_left_batch.clear()
        self.initial_keyframe_coords_left_batch.clear()
        self.initial_partner_x_coords_left.clear()
        
        self.initial_vectors_right_batch.clear()
        self.initial_types_right_batch.clear()
        self.initial_keyframe_coords_right_batch.clear()
        self.initial_partner_x_coords_right.clear()
        
        self.initial_keyframe_distances.clear()
        
        has_valid_pair = False
        
        for fcurve in context.selected_visible_fcurves:
            selected_keyframes_with_indices = [(index, kf) for index, kf in enumerate(fcurve.keyframe_points) if kf.select_control_point]

            if len(selected_keyframes_with_indices) >= 2:
                has_valid_pair = True
                
                selected_keyframes_with_indices.sort(key=lambda item: item[1].co[0])
                
                first_keyframe_index, first_keyframe = selected_keyframes_with_indices[0]
                last_keyframe_index, last_keyframe = selected_keyframes_with_indices[-1]

                keyframe_x_distance = last_keyframe.co[0] - first_keyframe.co[0]
                self.initial_keyframe_distances[(fcurve.data_path, first_keyframe_index, fcurve.array_index)] = keyframe_x_distance
                self.initial_keyframe_distances[(fcurve.data_path, last_keyframe_index, fcurve.array_index)] = keyframe_x_distance

                key_first = (fcurve.data_path, first_keyframe_index, fcurve.array_index)
                key_last = (fcurve.data_path, last_keyframe_index, fcurve.array_index)
                
                self.initial_types_left_batch[key_first] = {
                    'left': first_keyframe.handle_left_type,
                    'right': first_keyframe.handle_right_type
                }
                self.initial_vectors_left_batch[key_first] = {
                    'left': (first_keyframe.handle_left[0] - first_keyframe.co[0], first_keyframe.handle_left[1] - first_keyframe.co[1]),
                    'right': (first_keyframe.handle_right[0] - first_keyframe.co[0], first_keyframe.handle_right[1] - first_keyframe.co[1]),
                }
                self.initial_keyframe_coords_left_batch[key_first] = {'co_x': first_keyframe.co[0], 'co_y': first_keyframe.co[1]}
                self.initial_partner_x_coords_left[key_first] = last_keyframe.co[0]
                
                self.initial_types_right_batch[key_last] = {
                    'left': last_keyframe.handle_left_type,
                    'right': last_keyframe.handle_right_type
                }
                self.initial_vectors_right_batch[key_last] = {
                    'left': (last_keyframe.handle_left[0] - last_keyframe.co[0], last_keyframe.handle_left[1] - last_keyframe.co[1]),
                    'right': (last_keyframe.handle_right[0] - last_keyframe.co[0], last_keyframe.handle_right[1] - last_keyframe.co[1]),
                }
                self.initial_keyframe_coords_right_batch[key_last] = {'co_x': last_keyframe.co[0], 'co_y': last_keyframe.co[1]}
                self.initial_partner_x_coords_right[key_last] = first_keyframe.co[0]
        
        if not has_valid_pair:
            self.report({'WARNING'}, "Es wurden keine F-Kurven gefunden, die mindestens zwei ausgewählte Keyframes enthalten.")
            return {'CANCELLED'}
        
        self._initial_frame_start = context.scene.frame_start
        self._initial_frame_end = context.scene.frame_end
        
        if not context.scene.keep_framerange and context.screen.is_animation_playing:
            set_timeline_range_to_selected(context)

        self.initial_mouse_x = event.mouse_x

        if context.screen.is_animation_playing:
            context.scene.frame_current = context.scene.frame_start

        context.window.cursor_set('SCROLL_X')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


class OBJECT_OT_randomize_handle_extrusion(bpy.types.Operator):
    bl_idname = "object.randomize_handle_extrusion"
    bl_label = "Randomize Handle Extrusion"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Mousewheel for seed. Randomize handle extrusion"

    _timer = None
    initial_mouse_x = None
    initial_handle_vectors = {}
    initial_handle_types = {}
    _current_strength = 0.0
    _current_seed = 0
    _initial_frame_start = 0
    _initial_frame_end = 0

    @classmethod
    def poll(cls, context):
        return (context.active_object and
                context.active_object.animation_data and
                context.active_object.animation_data.action and
                context.selected_visible_fcurves and
                len([kf for fc in context.selected_visible_fcurves for kf in fc.keyframe_points if kf.select_control_point]) > 0)

    def _apply_randomized_extrusion(self, context, strength):
        random.seed(self._current_seed)
        
        # Dictionary, um Zufallswerte pro Knochen zu speichern
        bone_random_factors = {}

        for (data_path, keyframe_index, array_index), initial_vectors in self.initial_handle_vectors.items():
            fcurve = None
            for fc in context.active_object.animation_data.action.fcurves:
                if fc.data_path == data_path and fc.array_index == array_index:
                    fcurve = fc
                    break

            if not fcurve or keyframe_index >= len(fcurve.keyframe_points):
                continue
            
            keyframe = fcurve.keyframe_points[keyframe_index]
            
            # Neue Logik: Zufallsfaktor pro Knochen
            if context.scene.use_bone_randomization:
                # Extrahiere Knochennamen aus dem data_path
                # Zum Beispiel 'pose.bones["BoneName"].location' -> "BoneName"
                try:
                    bone_name = data_path.split('"')[1]
                except IndexError:
                    bone_name = None # Fallback für nicht-Knochen-Pfade
                
                if bone_name not in bone_random_factors:
                    # Berechne den Zufallsfaktor nur einmal pro Knochen
                    bone_random_factors[bone_name] = random.uniform(-strength, strength)
                
                random_factor = bone_random_factors.get(bone_name, 0.0)
            else:
                # Ursprüngliche Logik: Zufallsfaktor pro Kanal
                random_factor = random.uniform(-strength, strength)

            # Linkes Handle
            vec_left_initial = initial_vectors['left']
            length_left_initial = math.sqrt(vec_left_initial[0]**2 + vec_left_initial[1]**2)
            if length_left_initial > 0:
                new_length_left = length_left_initial * (1.0 + random_factor)
                new_x_left = keyframe.co[0] + vec_left_initial[0] / length_left_initial * new_length_left
                new_y_left = keyframe.co[1] + vec_left_initial[1] / length_left_initial * new_length_left
                keyframe.handle_left[0] = new_x_left
                keyframe.handle_left[1] = new_y_left

            # Rechtes Handle
            vec_right_initial = initial_vectors['right']
            length_right_initial = math.sqrt(vec_right_initial[0]**2 + vec_right_initial[1]**2)
            if length_right_initial > 0:
                new_length_right = length_right_initial * (1.0 + random_factor)
                new_x_right = keyframe.co[0] + vec_right_initial[0] / length_right_initial * new_length_right
                new_y_right = keyframe.co[1] + vec_right_initial[1] / length_right_initial * new_length_right
                keyframe.handle_right[0] = new_x_right
                keyframe.handle_right[1] = new_y_right
        
        for area in context.screen.areas:
            if area.type in {'GRAPH_EDITOR', 'VIEW_3D'}:
                area.tag_redraw()

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            
            if event.mouse_x < 5 or event.mouse_x > context.window.width - 5:
                if event.mouse_x < 5:
                    new_x = context.window.width - 10
                else:
                    new_x = 10
                self.initial_mouse_x += (new_x - event.mouse_x)
                context.window.cursor_warp(new_x, event.mouse_y)
            
            base_divisor = 1000.0 if event.alt else 200.0
            delta_x = event.mouse_x - self.initial_mouse_x
            
            delta_x = max(0.0, delta_x)
            
            power_exponent = 2.0
            abs_delta_x = abs(delta_x)
            strength = (abs_delta_x / base_divisor) ** power_exponent
            if delta_x < 0:
                strength *= -1.0
            
            self._current_strength = strength
            self._apply_randomized_extrusion(context, self._current_strength)
            #self.report({'INFO'}, f"Strength: {self._current_strength:.4f}, Seed: {self._current_seed}")
            return {'RUNNING_MODAL'}
            
        elif event.type == 'WHEELUPMOUSE':
            self._current_seed += 1
            self._apply_randomized_extrusion(context, self._current_strength)
            self.report({'INFO'}, f"Seed: {self._current_seed}")
            return {'RUNNING_MODAL'}
        
        elif event.type == 'WHEELDOWNMOUSE':
            self._current_seed -= 1
            self._apply_randomized_extrusion(context, self._current_strength)
            self.report({'INFO'}, f"Seed: {self._current_seed}")
            return {'RUNNING_MODAL'}

        elif event.type == 'LEFTMOUSE':
            # Iteriere über alle initial gespeicherten Keyframes
            for (data_path, keyframe_index, array_index), initial_vectors in self.initial_handle_vectors.items():
                fcurve = None
                for fc in context.active_object.animation_data.action.fcurves:
                    if fc.data_path == data_path and fc.array_index == array_index:
                        fcurve = fc
                        break
                
                # Wenn der Keyframe noch existiert, setze die Handle-Typen
                if fcurve and keyframe_index < len(fcurve.keyframe_points):
                    keyframe = fcurve.keyframe_points[keyframe_index]
                    keyframe.handle_left_type = 'ALIGNED'
                    keyframe.handle_right_type = 'ALIGNED'

            context.scene.frame_start = self._initial_frame_start
            context.scene.frame_end = self._initial_frame_end

            context.window.cursor_set('DEFAULT')
            return {'FINISHED'}
        
        elif event.type == 'RIGHTMOUSE' or event.type == 'ESC':
            for (data_path, keyframe_index, array_index), initial_vectors in self.initial_handle_vectors.items():
                fcurve = None
                for fc in context.active_object.animation_data.action.fcurves:
                    if fc.data_path == data_path and fc.array_index == array_index:
                        fcurve = fc
                        break
                
                if not fcurve or keyframe_index >= len(fcurve.keyframe_points):
                    continue
                
                keyframe = fcurve.keyframe_points[keyframe_index]
                initial_types = self.initial_handle_types[(data_path, keyframe_index, array_index)]
                
                keyframe.handle_left[0] = keyframe.co[0] + initial_vectors['left'][0]
                keyframe.handle_left[1] = keyframe.co[1] + initial_vectors['left'][1]
                keyframe.handle_right[0] = keyframe.co[0] + initial_vectors['right'][0]
                keyframe.handle_right[1] = keyframe.co[1] + initial_vectors['right'][1]
                
                keyframe.handle_left_type = initial_types['left']
                keyframe.handle_right_type = initial_types['right']
            
            context.scene.frame_start = self._initial_frame_start
            context.scene.frame_end = self._initial_frame_end
            
            context.window.cursor_set('DEFAULT')
            if self._timer:
                context.window_manager.event_timer_remove(self._timer)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}
    
    def invoke(self, context, event):
        if not context.selected_visible_fcurves or not [kf for fc in context.selected_visible_fcurves for kf in fc.keyframe_points if kf.select_control_point]:
            self.report({'WARNING'}, "Keine Keyframes in den aktiven, sichtbaren Kurven ausgewählt.")
            return {'CANCELLED'}
        
        self._initial_frame_start = context.scene.frame_start
        self._initial_frame_end = context.scene.frame_end
        
        if not context.scene.keep_framerange and context.screen.is_animation_playing:
            set_timeline_range_to_selected(context)
        
        if context.screen.is_animation_playing:
            context.scene.frame_current = context.scene.frame_start
        
        self.initial_mouse_x = event.mouse_x
        self.initial_handle_vectors.clear()
        self.initial_handle_types.clear()
        self._current_strength = 0.0
        self._current_seed = 0

        selected_keyframes_found = False
        for fcurve in context.selected_visible_fcurves:
            for keyframe_index, keyframe in enumerate(fcurve.keyframe_points):
                if keyframe.select_control_point:
                    selected_keyframes_found = True
                    key = (fcurve.data_path, keyframe_index, fcurve.array_index)
                    
                    self.initial_handle_types[key] = {
                        'left': keyframe.handle_left_type,
                        'right': keyframe.handle_right_type
                    }
                    self.initial_handle_vectors[key] = {
                        'left': (keyframe.handle_left[0] - keyframe.co[0], keyframe.handle_left[1] - keyframe.co[1]),
                        'right': (keyframe.handle_right[0] - keyframe.co[0], keyframe.handle_right[1] - keyframe.co[1]),
                    }

        if not selected_keyframes_found:
            self.report({'WARNING'}, "Keine Keyframes in den aktiven, sichtbaren Kurven ausgewählt.")
            return {'CANCELLED'}
        
        context.window.cursor_set('SCROLL_X')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


class OBJECT_OT_move_keys_to_cursor(bpy.types.Operator):
    bl_idname = "object.move_keys_to_cursor"
    bl_label = "Move Keys to Cursor"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Sets selected keyframes to the timeline cursor frame, preserving their handles"

    @classmethod
    def poll(cls, context):
        return (context.active_object and
                context.active_object.animation_data and
                context.active_object.animation_data.action and
                context.selected_visible_fcurves and
                len([kf for fc in context.selected_visible_fcurves for kf in fc.keyframe_points if kf.select_control_point]) > 0)

    def execute(self, context):
        
        selected_keyframes = []
        for fcurve in context.selected_visible_fcurves:
            for kf in fcurve.keyframe_points:
                if kf.select_control_point:
                    selected_keyframes.append(kf)

        if not selected_keyframes:
            self.report({'WARNING'}, "Keine Keyframes ausgewählt.")
            return {'CANCELLED'}
        
        cursor_frame = context.scene.frame_current

        for kf in selected_keyframes:
            # Speichere die relativen Handle-Vektoren
            handle_left_vector_x = kf.handle_left[0] - kf.co[0]
            handle_left_vector_y = kf.handle_left[1] - kf.co[1]
            
            handle_right_vector_x = kf.handle_right[0] - kf.co[0]
            handle_right_vector_y = kf.handle_right[1] - kf.co[1]
            
            # Setze den Keyframe-Punkt auf den Cursor-Frame
            kf.co[0] = cursor_frame
            
            # Wende die relativen Vektoren auf die neuen Keyframe-Koordinaten an
            kf.handle_left[0] = kf.co[0] + handle_left_vector_x
            kf.handle_left[1] = kf.co[1] + handle_left_vector_y
            
            kf.handle_right[0] = kf.co[0] + handle_right_vector_x
            kf.handle_right[1] = kf.co[1] + handle_right_vector_y
        
        # Stelle sicher, dass der Graph-Editor und 3D-View aktualisiert werden
        for area in context.screen.areas:
            if area.type in {'GRAPH_EDITOR', 'VIEW_3D'}:
                area.tag_redraw()
        
        return {'FINISHED'}



        

        
        


class GRAPH_PT_sub_options1(bpy.types.Panel):
    bl_label = "Advanced"
    bl_idname = "GRAPH_PT_sub_options_advanced1"  # Eindeutige ID
    bl_parent_id = "GRAPH_PT_handle_manipulator"
    bl_space_type = 'GRAPH_EDITOR'
    bl_region_type = 'UI'

    def draw(self, context):
        layout = self.layout
        scene = context.scene 
        button_height_scale = 1.4
        factor = 1/1.5
        sep2 = button_height_scale/factor
        sep1 = factor
        col = layout.column(align=True)
        col.scale_y = button_height_scale
        
        #basics
        
        row = col.row(align=True)
        row.operator(OBJECT_OT_manipulate_handles.bl_idname, text="Left/Right",icon='HANDLE_ALIGNED') 
        
        row = col.row(align=True)
        row.operator("graph.move_keyframes_x",icon='TRACKING_FORWARDS_SINGLE')
        
        row = col.row(align=True)
        row.operator("object.extrude_handles_between_frames", text="Extrude/Slide I",icon='AREA_SWAP')
        
        
        
        
        
        
        
        col.label(text="Randomize")
        row = col.row(align=True)
        row.operator("object.randomize_handle_extrusion", text="Extrusion",icon='HANDLE_ALIGNED')
        row.operator("object.randomize_handle_rotation", text="Rotation",icon='GESTURE_ROTATE')
        
        row = col.row(align=True)
        row.operator("object.random_x_pos", text="X-Value",icon='TRACKING_FORWARDS_SINGLE')   
        row.operator("OBJECT_OT_randomize_keys", text="Y-Value",icon='EMPTY_SINGLE_ARROW')
        
        #col.separator(factor= sep1)
        row = col.row(align=True)
        row.prop(context.scene, "use_bone_randomization", toggle=True, text="On bones",icon='BONE_DATA')


class GRAPH_PT_sub_options2(bpy.types.Panel):
    bl_label = "Options"
    bl_idname = "GRAPH_PT_sub_options_advanced2"  # Eindeutige ID
    bl_parent_id = "GRAPH_PT_handle_manipulator"
    bl_space_type = 'GRAPH_EDITOR'
    bl_region_type = 'UI'

    def draw(self, context):
        layout = self.layout
        scene = context.scene 
        button_height_scale = 1.4
        factor = 1/1.5
        sep2 = button_height_scale/factor
        sep1 = factor
        col = layout.column(align=True)
        col.scale_y = button_height_scale
        
        #options
        #col.label(text="Options")
        if context.active_object and context.active_object.type == 'ARMATURE':
            row = col.row(align=True)
            # Verwende den Operator anstelle der Property
            row.operator(OBJECT_OT_toggle_bones_isolation.bl_idname, text="Isolate Bones", icon='POINTCLOUD_POINT')
        else:
            col.label(text="Isolate Bones (Select Armature)")
        col.operator("object.move_keys_to_cursor", text="Set to cursor",icon='TRIA_UP')
        col.operator("graph.decimate_unselected", text="Decimate",icon='MOD_DECIM')
        
        
        col.separator(factor=sep1)
        filter_row = col.row(align=True)
        filter_row.scale_x = 0.8
        filter_row.scale_y = button_height_scale/1.5
        filter_row.prop(scene, "filter_loc", toggle=True, text="Loc",icon='CON_LOCLIKE')
        filter_row.prop(scene, "filter_rot", toggle=True, text="Rot",icon='ORIENTATION_GIMBAL')
        filter_row.prop(scene, "filter_scale", toggle=True, text="Scale",icon='ORIENTATION_LOCAL')

        filter_row = col.row(align=True)
        filter_row.scale_x = 0.8
        filter_row.scale_y = button_height_scale/1.5
        filter_row.prop(scene, "filter_x", toggle=True, text="X",icon='NODE_SOCKET_MATERIAL')
        filter_row.prop(scene, "filter_y", toggle=True, text="Y",icon='NODE_SOCKET_SHADER')
        filter_row.prop(scene, "filter_z", toggle=True, text="Z",icon='NODE_SOCKET_STRING')
        
        col.separator(factor=sep1)
        row = col.row(align=True)
        row.prop(context.scene, "keep_framerange", toggle=True, text="Normal Range",icon='TIME')

        row = col.row(align=True)
        row.prop(scene, "additional_preframes", text="Preframes")
        row.prop(scene, "additional_postframes", text="Postframes")
        
        
        
        
'''class GRAPH_PT_sub_options3(bpy.types.Panel):
    bl_label = "Randomization"
    bl_idname = "GRAPH_PT_sub_options_advanced3"  # Eindeutige ID
    bl_parent_id = "GRAPH_PT_handle_manipulator"
    bl_space_type = 'GRAPH_EDITOR'
    bl_region_type = 'UI'

    def draw(self, context):
        layout = self.layout
        scene = context.scene 
        button_height_scale = 1.4
        factor = 1/1.5
        sep2 = button_height_scale/factor
        sep1 = factor
        col = layout.column(align=True)
        col.scale_y = button_height_scale
        
        
        
class GRAPH_PT_sub_options4(bpy.types.Panel):
    bl_label = "Operations"
    bl_idname = "GRAPH_PT_sub_options_advanced4"  # Eindeutige ID
    bl_parent_id = "GRAPH_PT_handle_manipulator"
    bl_space_type = 'GRAPH_EDITOR'
    bl_region_type = 'UI'

    def draw(self, context):
        layout = self.layout
        scene = context.scene 
        button_height_scale = 1.4
        factor = 1/1.5
        sep2 = button_height_scale/factor
        sep1 = factor
        col = layout.column(align=True)
        col.scale_y = button_height_scale
        
        #options
        
        
        
        
        
        
        
class GRAPH_PT_sub_options5(bpy.types.Panel):
    bl_label = "Old"
    bl_idname = "GRAPH_PT_sub_options_advanced5"  # Eindeutige ID
    bl_parent_id = "GRAPH_PT_handle_manipulator"
    bl_space_type = 'GRAPH_EDITOR'
    bl_region_type = 'UI'

    def draw(self, context):
        layout = self.layout
        scene = context.scene 
        button_height_scale = 1.4
        factor = 1/1.5
        sep2 = button_height_scale/factor
        sep1 = factor
        col = layout.column(align=True)
        col.scale_y = button_height_scale
        
        #options
        #col.label(text="Options")
        
        
        row = col.row(align=True)
        row.operator("object.manipulate_right_handles", text="asd")'''
        
        
        

class GRAPH_PT_handle_manipulator(bpy.types.Panel):
    bl_label = "Handle Manipulator"
    bl_idname = "GRAPH_PT_handle_manipulator"
    bl_space_type = 'GRAPH_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Tools"

    def draw(self, context):
        layout = self.layout
        scene = context.scene 
        button_height_scale = 1.4
        factor = 1/1.5
        sep2 = button_height_scale/factor
        sep1 = factor
        col = layout.column(align=True)
        col.scale_y = button_height_scale
        
        #basics
        row = col.row(align=True)
        row.operator(OBJECT_OT_scale_handles.bl_idname, text="Scale Handles",icon='ORIENTATION_VIEW')
        #col.separator(factor=sep1)
        
        
        row = col.row(align=True)
        row.operator("OBJECT_OT_rotate_keys", text="Rotate",icon='GESTURE_ROTATE') 
        row.operator("OBJECT_OT_flatten_keys", text="Flatten",icon='REMOVE') 
        
        col.separator(factor=sep1)
        row = col.row(align=True)
        row.operator("object.extrude_slide_handles_between_frames", text="Extrude/Slide X/Y",icon='AREA_SWAP')
        
        #col.separator(factor=sep1)
        row = col.row(align=True)
        row.operator("graph.scale_keyframes_x",icon='CENTER_ONLY')
        
        
        
        
        
        
        


addon_keymaps = []

        
def register():
    bpy.utils.register_class(OBJECT_OT_randomize_keys)
    bpy.utils.register_class(OBJECT_OT_manipulate_handles)
    bpy.utils.register_class(OBJECT_OT_scale_handles)
    bpy.utils.register_class(OBJECT_OT_manipulate_right_handles)
    bpy.utils.register_class(OBJECT_OT_rotate_keys)
    bpy.utils.register_class(OBJECT_OT_extrude_slide_handles_between_frames)
    bpy.utils.register_class(OBJECT_OT_extrude_handles_between_frames)
    bpy.utils.register_class(GRAPH_OT_decimate_unselected)
    bpy.utils.register_class(GRAPH_PT_handle_manipulator)
    bpy.utils.register_class(BONES_OT_toggle_unselected_bones)
    bpy.utils.register_class(OBJECT_OT_randomize_handle_rotation)
    bpy.utils.register_class(OBJECT_OT_randomize_handle_extrusion)
    bpy.utils.register_class(GRAPH_OT_scale_keyframes_x)
    bpy.utils.register_class(GRAPH_OT_move_keyframes_x)
    bpy.utils.register_class(GRAPH_OT_select_next_keys)
    bpy.utils.register_class(GRAPH_OT_select_previous_keys)
    bpy.utils.register_class(GRAPH_OT_add_next_keys)
    bpy.utils.register_class(GRAPH_OT_subtract_keys)
    bpy.utils.register_class(OBJECT_OT_random_x_pos)
    bpy.utils.register_class(OBJECT_OT_move_keys_to_cursor)
    bpy.utils.register_class(OBJECT_OT_flatten_keys)
    bpy.utils.register_class(OBJECT_OT_slide_handles)
    bpy.utils.register_class(OBJECT_OT_toggle_bones_isolation)
    bpy.utils.register_class(GRAPH_PT_sub_options2)
    bpy.utils.register_class(GRAPH_PT_sub_options1)
    #bpy.utils.register_class(GRAPH_PT_sub_options3)
    #bpy.utils.register_class(GRAPH_PT_sub_options4)
    #bpy.utils.register_class(GRAPH_PT_sub_options5)
    
    
    



    
    bpy.types.Scene.filter_loc = bpy.props.BoolProperty(name="Location Filter", default=False, update=filter_fcurves)
    bpy.types.Scene.filter_rot = bpy.props.BoolProperty(name="Rotation Filter", default=False, update=filter_fcurves)
    bpy.types.Scene.filter_scale = bpy.props.BoolProperty(name="Scale Filter", default=False, update=filter_fcurves)
    bpy.types.Scene.filter_x = bpy.props.BoolProperty(name="X Axis Filter", default=False, update=filter_fcurves)
    bpy.types.Scene.filter_y = bpy.props.BoolProperty(name="Y Axis Filter", default=False, update=filter_fcurves)
    bpy.types.Scene.filter_z = bpy.props.BoolProperty(name="Z Axis Filter", default=False, update=filter_fcurves)
    
    
    bpy.types.Scene.vorschau = bpy.props.IntProperty(
        name="Vorschau",
        default=15,
        min=0,
        max=100,
        step=1,
        description="Frames before first selection"
    )
    
    bpy.types.Scene.nachschau = bpy.props.IntProperty(
        name="Nachschau",
        default=15,
        min=0,
        max=100,
        step=10,
        description="Frames after last selection"
    )
    
    
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc:
        # Erstelle eine globale Keymap für das Fenster
        km = kc.keymaps.new(name='Window', space_type='EMPTY')
        
        # Hotkey für den nächsten Keyframe (Numpad 3)
        kmi_next = km.keymap_items.new(
            GRAPH_OT_select_next_keys.bl_idname, 
            type='NUMPAD_3', 
            value='PRESS'
        )
        
        # Hotkey für den vorherigen Keyframe (Numpad 1)
        kmi_prev = km.keymap_items.new(
            GRAPH_OT_select_previous_keys.bl_idname, 
            type='NUMPAD_1', 
            value='PRESS'
        )
        kmi_plus = km.keymap_items.new(
            GRAPH_OT_add_next_keys.bl_idname, 
            type='NUMPAD_5', 
            value='PRESS'
        )
        
        # Hotkey für den vorherigen Keyframe (Numpad 1)
        kmi_minus = km.keymap_items.new(
            GRAPH_OT_subtract_keys.bl_idname, 
            type='NUMPAD_2', 
            value='PRESS'
        )
        kmi_play_pause = km.keymap_items.new(
            'screen.animation_play',  # Der Operator für Play/Pause
            type='NUMPAD_4',  # Die Taste
            value='PRESS'
        )
        
        
        
        
        # Speichere die Keymap-Instanz
        addon_keymaps.append(km)



def unregister():
    bpy.utils.unregister_class(OBJECT_OT_randomize_keys)
    bpy.utils.unregister_class(OBJECT_OT_manipulate_handles)
    bpy.utils.unregister_class(OBJECT_OT_scale_handles)
    bpy.utils.unregister_class(OBJECT_OT_manipulate_right_handles)
    bpy.utils.unregister_class(OBJECT_OT_rotate_keys)
    bpy.utils.unregister_class(OBJECT_OT_extrude_slide_handles_between_frames)
    bpy.utils.unregister_class(OBJECT_OT_extrude_handles_between_frames)
    bpy.utils.unregister_class(GRAPH_PT_handle_manipulator)
    bpy.utils.unregister_class(BONES_OT_toggle_unselected_bones)
    bpy.utils.unregister_class(GRAPH_OT_decimate_unselected)
    bpy.utils.unregister_class(OBJECT_OT_randomize_handle_rotation)
    bpy.utils.unregister_class(OBJECT_OT_randomize_handle_extrusion)
    bpy.utils.unregister_class(GRAPH_OT_scale_keyframes_x)
    bpy.utils.unregister_class(GRAPH_OT_move_keyframes_x)
    bpy.utils.unregister_class(GRAPH_OT_select_next_keys)
    bpy.utils.unregister_class(GRAPH_OT_select_previous_keys)
    bpy.utils.unregister_class(GRAPH_OT_add_next_keys)
    bpy.utils.unregister_class(GRAPH_OT_subtract_keys)
    bpy.utils.unregister_class(OBJECT_OT_random_x_pos)
    bpy.utils.unregister_class(OBJECT_OT_move_keys_to_cursor)
    bpy.utils.unregister_class(OBJECT_OT_flatten_keys)
    bpy.utils.unregister_class(OBJECT_OT_slide_handles)
    bpy.utils.unregister_class(OBJECT_OT_toggle_bones_isolation)
    bpy.utils.unregister_class(GRAPH_PT_sub_options1)
    bpy.utils.unregister_class(GRAPH_PT_sub_options2)
    #bpy.utils.unregister_class(GRAPH_PT_sub_options3)
    #bpy.utils.unregister_class(GRAPH_PT_sub_options4)
    #bpy.utils.unregister_class(GRAPH_PT_sub_options5)


    del bpy.types.Scene.vorschau
    del bpy.types.Scene.nachschau
    

    del bpy.types.Scene.filter_loc
    del bpy.types.Scene.filter_rot
    del bpy.types.Scene.filter_scale
    del bpy.types.Scene.filter_x
    del bpy.types.Scene.filter_y
    del bpy.types.Scene.filter_z
    
    for km in addon_keymaps:
        bpy.context.window_manager.keyconfigs.addon.keymaps.remove(km)
    
    # Leere die Liste der Keymaps
    addon_keymaps.clear()

if __name__ == "__main__":
    register()
    
    
    #extrude: verändert wert und timing
    #in x: verändert timing, wert bleibt gleich
    #in y: verändert wert, timing bleibt gleich
