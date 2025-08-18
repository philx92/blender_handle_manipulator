import bpy
import math
import random

bl_info = {
    "name": "Handle Manipulator",
    "author": "Gemini",
    "version": (1, 0),
    "blender": (4, 0, 0),
    "location": "Graph Editor > Sidebar",
    "description": "Manipulate selected keyframe handles.",
    "category": "Animation",
}

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



import bpy
import math

class OBJECT_OT_rotate_keys(bpy.types.Operator):
    bl_idname = "object.rotate_keys"
    bl_label = "Rotate Keyframes"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Rotation direction dependant on next keyframe (for correct anticipation/overshoot of multiple keyframes). Mousewheel for sensitivity"

    _initial_keyframe_data = {}
    
    initial_mouse_x = None
    _strength_multiplier = 0.5
    
    # Empfindlichkeit in Grad pro Pixel
    _degrees_per_pixel = 0.5

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
            
            # NEU: Logik zur Bestimmung der Rotationsrichtung
            direction = 1.0
            
            # Überprüfe, ob es einen nächsten Keyframe gibt
            if keyframe_index + 1 < len(fcurve.keyframe_points):
                next_keyframe = fcurve.keyframe_points[keyframe_index + 1]
                
                # Wenn der Y-Wert des nächsten Keyframes gleich ist, keine Rotation
                if next_keyframe.co[1] == keyframe.co[1]:
                    continue
                
                if next_keyframe.co[1] < keyframe.co[1]:
                    direction = -1.0 # Kehre die Richtung um, wenn der nächste Y-Wert niedriger ist
            
            # Wenn es keinen nächsten gibt, nutze den vorherigen Keyframe
            elif keyframe_index > 0:
                previous_keyframe = fcurve.keyframe_points[keyframe_index - 1]

                # Wenn der Y-Wert des vorherigen Keyframes gleich ist, keine Rotation
                if previous_keyframe.co[1] == keyframe.co[1]:
                    continue
                
                if previous_keyframe.co[1] > keyframe.co[1]:
                    direction = -1.0 # Kehre die Richtung um, wenn der vorherige Y-Wert höher ist

            # Die Rotation wird jetzt mit der ermittelten Richtung multipliziert
            rotation_angle_radians = math.radians(rotation_angle_degrees * direction)
            
            cos_angle = math.cos(rotation_angle_radians)
            sin_angle = math.sin(rotation_angle_radians)
            
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
            delta_x = event.mouse_x - self.initial_mouse_x
            
            # Korrigierte Berechnung der Drehstärke
            rotation_strength_degrees = delta_x * self._degrees_per_pixel * 0.0001
            
            self._apply_rotation(context, rotation_strength_degrees)
            # Ausgabe auf Grad ändern
            self.report({'INFO'}, f"Rotation Sensitivity: {self._degrees_per_pixel:.2f} ")
            return {'RUNNING_MODAL'}
            
        elif event.type == 'WHEELUPMOUSE':
            self._degrees_per_pixel *= 1.5
            
            delta_x = event.mouse_x - self.initial_mouse_x
            rotation_strength_degrees = delta_x * self._degrees_per_pixel
            self._apply_rotation(context, rotation_strength_degrees)
            return {'RUNNING_MODAL'}
        
        elif event.type == 'WHEELDOWNMOUSE':
            self._degrees_per_pixel /= 1.5
            self._degrees_per_pixel = max(0.01, self._degrees_per_pixel)
            
            delta_x = event.mouse_x - self.initial_mouse_x
            rotation_strength_degrees = delta_x * self._degrees_per_pixel
            self._apply_rotation(context, rotation_strength_degrees)
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
            
            context.window.cursor_set('DEFAULT')
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}
    
    def invoke(self, context, event):
        if not context.selected_visible_fcurves or not [kf for fc in context.selected_visible_fcurves for kf in fc.keyframe_points if kf.select_control_point]:
            self.report({'WARNING'}, "Keine Keyframes in den aktiven, sichtbaren Kurven ausgew\u00e4hlt.")
            return {'CANCELLED'}
        
        self._initial_keyframe_data.clear()
        self.initial_mouse_x = event.mouse_x

        for fcurve in context.selected_visible_fcurves:
            for keyframe_index, keyframe in enumerate(fcurve.keyframe_points):
                if keyframe.select_control_point:
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



class OBJECT_OT_randomize_keys(bpy.types.Operator):
    bl_idname = "object.randomize_keys"
    bl_label = "Randomize Keyframes"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Randomize keyframe Y-Values. Mousewheel for seed"

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
        
        for (data_path, keyframe_index, array_index), initial_data in self.initial_keyframe_data.items():
            fcurve = None
            for fc in context.active_object.animation_data.action.fcurves:
                if fc.data_path == data_path and fc.array_index == array_index:
                    fcurve = fc
                    break

            if not fcurve or keyframe_index >= len(fcurve.keyframe_points):
                continue
            
            keyframe = fcurve.keyframe_points[keyframe_index]
            random_offset_y = random.uniform(-strength, strength)
            keyframe.co[1] = initial_data['co_y'] + random_offset_y

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
            power_exponent = 2.0
            abs_delta_x = abs(delta_x)
            strength = (abs_delta_x / base_divisor) ** power_exponent
            if delta_x < 0:
                strength *= -1.0
            
            self._current_strength = strength
            self._apply_randomization(context, self._current_strength)
            self.report({'INFO'}, f"Strength: {self._current_strength:.4f}, Seed: {self._current_seed}")
            return {'RUNNING_MODAL'}
            
        elif event.type == 'WHEELUPMOUSE':
            self._current_seed += 1
            self._apply_randomization(context, self._current_strength)
            
            return {'RUNNING_MODAL'}
        
        elif event.type == 'WHEELDOWNMOUSE':
            self._current_seed -= 1
            self._apply_randomization(context, self._current_strength)
            
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

        self.initial_mouse_x = event.mouse_x
        self.initial_keyframe_data.clear()
        
        self._current_strength = 0.0
        self._current_seed = 0

        selected_keyframes_found = False
        for fcurve in context.selected_visible_fcurves:
            for keyframe_index, keyframe in enumerate(fcurve.keyframe_points):
                if keyframe.select_control_point:
                    selected_keyframes_found = True
                    key = (fcurve.data_path, keyframe_index, fcurve.array_index)
                    
                    self.initial_keyframe_data[key] = {
                        'co_x': keyframe.co[0], 
                        'co_y': keyframe.co[1],
                        'handle_left_type': keyframe.handle_left_type,
                        'handle_right_type': keyframe.handle_right_type,
                        'handle_left_vec': (keyframe.handle_left[0] - keyframe.co[0], keyframe.handle_left[1] - keyframe.co[1]),
                        'handle_right_vec': (keyframe.handle_right[0] - keyframe.co[0], keyframe.handle_right[1] - keyframe.co[1])
                    }

        if not selected_keyframes_found:
            self.report({'WARNING'}, "Keine Keyframes in den aktiven, sichtbaren Kurven ausgewählt.")
            return {'CANCELLED'}
        
        context.window.cursor_set('SCROLL_X')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

class OBJECT_OT_manipulate_handles(bpy.types.Operator):
    bl_idname = "object.handle_manipulator"
    bl_label = "Manipulate Handles"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Extend both handles"
    
    _timer = None
    initial_mouse_x = None
    initial_handle_vectors = {}
    initial_handle_types = {}

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
            factor = max(delta_x / 200.0, -1.0)
            
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
                length_right_initial = math.sqrt(vec_right_initial[0]**2 + vec_right_initial[1]**2)
                
                if length_right_initial > 0:
                    new_length_right = length_right_initial * (1.0 + factor)
                    new_x_right = keyframe.co[0] + vec_right_initial[0] / length_right_initial * new_length_right
                    new_y_right = keyframe.co[1] + vec_right_initial[1] / length_right_initial * new_length_right
                    keyframe.handle_right[0] = new_x_right
                    keyframe.handle_right[1] = new_y_right

                vec_left_initial = initial_vectors['left']
                length_left_initial = math.sqrt(vec_left_initial[0]**2 + vec_left_initial[1]**2)

                if length_left_initial > 0:
                    new_length_left = length_left_initial * (1.0 + factor)
                    new_x_left = keyframe.co[0] + vec_left_initial[0] / length_left_initial * new_length_left
                    new_y_left = keyframe.co[1] + vec_left_initial[1] / length_left_initial * new_length_left
                    keyframe.handle_left[0] = new_x_left
                    keyframe.handle_left[1] = new_y_left
            
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

        self.initial_mouse_x = event.mouse_x
        self.initial_handle_vectors.clear()
        self.initial_handle_types.clear()

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
        self._timer = context.window_manager.event_timer_add(0.01, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

class OBJECT_OT_manipulate_right_handles(bpy.types.Operator):
    bl_idname = "object.manipulate_right_handles"
    bl_label = "Manipulate Right Handles"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Extend right handle"
    
    _timer = None
    initial_mouse_x = None
    initial_handle_vectors = {}
    initial_handle_types = {}

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
            factor = max(delta_x / 200.0, -1.0)
            
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
                length_right_initial = math.sqrt(vec_right_initial[0]**2 + vec_right_initial[1]**2)
                
                if length_right_initial > 0:
                    new_length_right = length_right_initial * (1.0 + factor)
                    new_x_right = keyframe.co[0] + vec_right_initial[0] / length_right_initial * new_length_right
                    new_y_right = keyframe.co[1] + vec_right_initial[1] / length_right_initial * new_length_right
                    keyframe.handle_right[0] = new_x_right
                    keyframe.handle_right[1] = new_y_right
            
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

        self.initial_mouse_x = event.mouse_x
        self.initial_handle_vectors.clear()
        self.initial_handle_types.clear()

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
        self._timer = context.window_manager.event_timer_add(0.01, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


class OBJECT_OT_manipulate_left_handles(bpy.types.Operator):
    bl_idname = "object.manipulate_left_handles"
    bl_label = "Manipulate Left Handles"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Extend left handle"
    
    _timer = None
    initial_mouse_x = None
    initial_handle_vectors = {}
    initial_handle_types = {}

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
            factor = max(delta_x / 200.0, -1.0)
            
            for (data_path, keyframe_index, array_index), initial_vectors in self.initial_handle_vectors.items():
                fcurve = None
                for fc in context.active_object.animation_data.action.fcurves:
                    if fc.data_path == data_path and fc.array_index == array_index:
                        fcurve = fc
                        break

                if not fcurve:
                    continue
                
                keyframe = fcurve.keyframe_points[keyframe_index]
                
                vec_left_initial = initial_vectors['left']
                length_left_initial = math.sqrt(vec_left_initial[0]**2 + vec_left_initial[1]**2)

                if length_left_initial > 0:
                    new_length_left = length_left_initial * (1.0 + factor)
                    new_x_left = keyframe.co[0] + vec_left_initial[0] / length_left_initial * new_length_left
                    new_y_left = keyframe.co[1] + vec_left_initial[1] / length_left_initial * new_length_left
                    keyframe.handle_left[0] = new_x_left
                    keyframe.handle_left[1] = new_y_left
            
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

        self.initial_mouse_x = event.mouse_x
        self.initial_handle_vectors.clear()
        self.initial_handle_types.clear()

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
        self._timer = context.window_manager.event_timer_add(0.01, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

import bpy
import math

 


# --- Operator: Extend/Shrink Between Batches ---
class OBJECT_OT_manipulate_handles_between_frames(bpy.types.Operator):
    bl_idname = "object.manipulate_handles_between_frames"
    bl_label = "Extend/Shrink Batches"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Slide handles between two keyframes"
    
    _timer = None
    initial_mouse_x = None
    initial_vectors_left_batch = {}
    initial_types_left_batch = {}
    initial_vectors_right_batch = {}
    initial_types_right_batch = {}
    initial_keyframe_coords_left_batch = {}
    initial_keyframe_coords_right_batch = {}

    @classmethod
    def poll(cls, context):
        if not (context.active_object and
                context.active_object.animation_data and
                context.active_object.animation_data.action and
                context.selected_visible_fcurves):
            return False
        
        selected_frames = []
        for fcurve in context.selected_visible_fcurves:
            for keyframe in fcurve.keyframe_points:
                if keyframe.select_control_point:
                    selected_frames.append(keyframe.co[0])
        
        return len(set(selected_frames)) >= 2 and len([kf for fc in context.selected_visible_fcurves for kf in fc.keyframe_points if kf.select_control_point]) > 0


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
            factor = min(max(delta_x / 200, -1.0), 1.0)
            
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
                
                if length_right_initial > 1e-6:
                    new_length_right = max(length_right_initial * (1.0 + factor), 0.0)
                    new_x_right = keyframe.co[0] + vec_right_initial[0] / length_right_initial * new_length_right
                    new_y_right = keyframe.co[1] + vec_right_initial[1] / length_right_initial * new_length_right
                    keyframe.handle_right[0] = new_x_right
                    keyframe.handle_right[1] = new_y_right
                else:
                    keyframe.handle_right[0] = keyframe.co[0]
                    keyframe.handle_right[1] = keyframe.co[1]
            
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

                if length_left_initial > 1e-6:
                    new_length_left = max(length_left_initial * (1.0 - factor), 0.0)
                    new_x_left = keyframe.co[0] + vec_left_initial[0] / length_left_initial * new_length_left
                    new_y_left = keyframe.co[1] + vec_left_initial[1] / length_left_initial * new_length_left
                    keyframe.handle_left[0] = new_x_left
                    keyframe.handle_left[1] = new_y_left
                else:
                    keyframe.handle_left[0] = keyframe.co[0]
                    keyframe.handle_left[1] = keyframe.co[1]

            for area in context.screen.areas:
                if area.type in {'GRAPH_EDITOR', 'VIEW_3D'}:
                    area.tag_redraw()
            
            return {'RUNNING_MODAL'}

        elif event.type == 'LEFTMOUSE':
            set_handles_aligned(context, self.initial_types_left_batch)
            set_handles_aligned(context, self.initial_types_right_batch)
            context.window.cursor_set('DEFAULT')
            if self._timer:
                context.window_manager.event_timer_remove(self._timer)
            return {'FINISHED'}
        
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            reset_handles(context, self.initial_vectors_left_batch, self.initial_types_left_batch, self.initial_keyframe_coords_left_batch)
            reset_handles(context, self.initial_vectors_right_batch, self.initial_types_right_batch, self.initial_keyframe_coords_right_batch)
            context.window.cursor_set('DEFAULT')
            if self._timer:
                context.window_manager.event_timer_remove(self._timer)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}
    
    def invoke(self, context, event):
        if context.active_object is None or context.active_object.animation_data is None:
            self.report({'WARNING'}, "Kein aktives Objekt oder keine Animationsdaten gefunden.")
            return {'CANCELLED'}

        if not context.selected_visible_fcurves:
            self.report({'WARNING'}, "Keine F-Kurven im Graph Editor sichtbar und ausgewählt.")
            return {'CANCELLED'}

        self.initial_mouse_x = event.mouse_x
        self.initial_vectors_left_batch.clear()
        self.initial_types_left_batch.clear()
        self.initial_vectors_right_batch.clear()
        self.initial_types_right_batch.clear()
        self.initial_keyframe_coords_left_batch.clear()
        self.initial_keyframe_coords_right_batch.clear()
        
        selected_frames = []
        for fcurve in context.selected_visible_fcurves:
            for keyframe in fcurve.keyframe_points:
                if keyframe.select_control_point:
                    selected_frames.append(keyframe.co[0])
                    
        if not selected_frames:
            self.report({'WARNING'}, "Keine Keyframes in den aktiven, sichtbaren Kurven ausgewählt.")
            return {'CANCELLED'}
        
        min_frame = min(selected_frames)
        max_frame = max(selected_frames)
        
        if min_frame == max_frame:
            self.report({'WARNING'}, "Wähle Keyframes auf mindestens zwei verschiedenen Frames aus.")
            return {'CANCELLED'}
        
        for fcurve in context.selected_visible_fcurves:
            for keyframe_index, keyframe in enumerate(fcurve.keyframe_points):
                if keyframe.select_control_point:
                    key = (fcurve.data_path, keyframe_index, fcurve.array_index)
                    
                    if keyframe.co[0] == min_frame:
                        self.initial_types_left_batch[key] = {
                            'left': keyframe.handle_left_type,
                            'right': keyframe.handle_right_type
                        }
                        self.initial_vectors_left_batch[key] = {
                            'left': (keyframe.handle_left[0] - keyframe.co[0], keyframe.handle_left[1] - keyframe.co[1]),
                            'right': (keyframe.handle_right[0] - keyframe.co[0], keyframe.handle_right[1] - keyframe.co[1]),
                        }
                        self.initial_keyframe_coords_left_batch[key] = {'co_x': keyframe.co[0], 'co_y': keyframe.co[1]}
                    elif keyframe.co[0] == max_frame:
                        self.initial_types_right_batch[key] = {
                            'left': keyframe.handle_left_type,
                            'right': keyframe.handle_right_type
                        }
                        self.initial_vectors_right_batch[key] = {
                            'left': (keyframe.handle_left[0] - keyframe.co[0], keyframe.handle_left[1] - keyframe.co[1]),
                            'right': (keyframe.handle_right[0] - keyframe.co[0], keyframe.handle_right[1] - keyframe.co[1]),
                        }
                        self.initial_keyframe_coords_right_batch[key] = {'co_x': keyframe.co[0], 'co_y': keyframe.co[1]}

        if not self.initial_vectors_left_batch or not self.initial_vectors_right_batch:
            self.report({'WARNING'}, "Stelle sicher, dass Keyframes auf dem ersten und letzten ausgewählten Frame vorhanden sind.")
            return {'CANCELLED'}

        context.window.cursor_set('SCROLL_X')
        self._timer = context.window_manager.event_timer_add(0.01, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


class OBJECT_OT_shrink_batches(bpy.types.Operator):
    bl_idname = "object.shrink_batches"
    bl_label = "Uniform Batch Scale"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Scale handles between two keyframes"
    
    _timer = None
    initial_mouse_x = None
    initial_vectors_left_batch = {}
    initial_types_left_batch = {}
    initial_vectors_right_batch = {}
    initial_types_right_batch = {}
    initial_keyframe_coords_left_batch = {}
    initial_keyframe_coords_right_batch = {}

    @classmethod
    def poll(cls, context):
        if not (context.active_object and
                context.active_object.animation_data and
                context.active_object.animation_data.action and
                context.selected_visible_fcurves):
            return False
        
        selected_frames = []
        for fcurve in context.selected_visible_fcurves:
            for keyframe in fcurve.keyframe_points:
                if keyframe.select_control_point:
                    selected_frames.append(keyframe.co[0])
        
        return len(set(selected_frames)) >= 2 and len([kf for fc in context.selected_visible_fcurves for kf in fc.keyframe_points if kf.select_control_point]) > 0

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
            
            factor = delta_x / 200.0

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
                
                if length_right_initial > 1e-6:
                    new_length_right = max(length_right_initial * (1.0 + factor), 0.0)
                    new_x_right = keyframe.co[0] + vec_right_initial[0] / length_right_initial * new_length_right
                    new_y_right = keyframe.co[1] + vec_right_initial[1] / length_right_initial * new_length_right
                    keyframe.handle_right[0] = new_x_right
                    keyframe.handle_right[1] = new_y_right
                else:
                    keyframe.handle_right[0] = keyframe.co[0]
                    keyframe.handle_right[1] = keyframe.co[1]
            
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

                if length_left_initial > 1e-6:
                    new_length_left = max(length_left_initial * (1.0 + factor), 0.0)
                    new_x_left = keyframe.co[0] + vec_left_initial[0] / length_left_initial * new_length_left
                    new_y_left = keyframe.co[1] + vec_left_initial[1] / length_left_initial * new_length_left
                    keyframe.handle_left[0] = new_x_left
                    keyframe.handle_left[1] = new_y_left
                else:
                    keyframe.handle_left[0] = keyframe.co[0]
                    keyframe.handle_left[1] = keyframe.co[1]

            for area in context.screen.areas:
                if area.type in {'GRAPH_EDITOR', 'VIEW_3D'}:
                    area.tag_redraw()
            
            return {'RUNNING_MODAL'}

        elif event.type == 'LEFTMOUSE':
            set_handles_aligned(context, self.initial_types_left_batch)
            set_handles_aligned(context, self.initial_types_right_batch)
            context.window.cursor_set('DEFAULT')
            if self._timer:
                context.window_manager.event_timer_remove(self._timer)
            return {'FINISHED'}
        
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            reset_handles(context, self.initial_vectors_left_batch, self.initial_types_left_batch, self.initial_keyframe_coords_left_batch)
            reset_handles(context, self.initial_vectors_right_batch, self.initial_types_right_batch, self.initial_keyframe_coords_right_batch)
            context.window.cursor_set('DEFAULT')
            if self._timer:
                context.window_manager.event_timer_remove(self._timer)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}
    
    def invoke(self, context, event):
        if context.active_object is None or context.active_object.animation_data is None:
            self.report({'WARNING'}, "Kein aktives Objekt oder keine Animationsdaten gefunden.")
            return {'CANCELLED'}

        if not context.selected_visible_fcurves:
            self.report({'WARNING'}, "Keine F-Kurven im Graph Editor sichtbar und ausgewählt.")
            return {'CANCELLED'}

        self.initial_mouse_x = event.mouse_x
        self.initial_vectors_left_batch.clear()
        self.initial_types_left_batch.clear()
        self.initial_vectors_right_batch.clear()
        self.initial_types_right_batch.clear()
        self.initial_keyframe_coords_left_batch.clear()
        self.initial_keyframe_coords_right_batch.clear()
        
        selected_frames = []
        for fcurve in context.selected_visible_fcurves:
            for keyframe in fcurve.keyframe_points:
                if keyframe.select_control_point:
                    selected_frames.append(keyframe.co[0])
                    
        if not selected_frames:
            self.report({'WARNING'}, "Keine Keyframes in den aktiven, sichtbaren Kurven ausgewählt.")
            return {'CANCELLED'}
        
        min_frame = min(selected_frames)
        max_frame = max(selected_frames)
        
        if min_frame == max_frame:
            self.report({'WARNING'}, "Wähle Keyframes auf mindestens zwei verschiedenen Frames aus.")
            return {'CANCELLED'}
        
        for fcurve in context.selected_visible_fcurves:
            for keyframe_index, keyframe in enumerate(fcurve.keyframe_points):
                if keyframe.select_control_point:
                    key = (fcurve.data_path, keyframe_index, fcurve.array_index)
                    
                    if keyframe.co[0] == min_frame:
                        self.initial_types_left_batch[key] = {
                            'left': keyframe.handle_left_type,
                            'right': keyframe.handle_right_type
                        }
                        self.initial_vectors_left_batch[key] = {
                            'left': (keyframe.handle_left[0] - keyframe.co[0], keyframe.handle_left[1] - keyframe.co[1]),
                            'right': (keyframe.handle_right[0] - keyframe.co[0], keyframe.handle_right[1] - keyframe.co[1]),
                        }
                        self.initial_keyframe_coords_left_batch[key] = {'co_x': keyframe.co[0], 'co_y': keyframe.co[1]}
                    elif keyframe.co[0] == max_frame:
                        self.initial_types_right_batch[key] = {
                            'left': keyframe.handle_left_type,
                            'right': keyframe.handle_right_type
                        }
                        self.initial_vectors_right_batch[key] = {
                            'left': (keyframe.handle_left[0] - keyframe.co[0], keyframe.handle_left[1] - keyframe.co[1]),
                            'right': (keyframe.handle_right[0] - keyframe.co[0], keyframe.handle_right[1] - keyframe.co[1]),
                        }
                        self.initial_keyframe_coords_right_batch[key] = {'co_x': keyframe.co[0], 'co_y': keyframe.co[1]}

        if not self.initial_vectors_left_batch or not self.initial_vectors_right_batch:
            self.report({'WARNING'}, "Stelle sicher, dass Keyframes auf dem ersten und letzten ausgewählten Frame vorhanden sind.")
            return {'CANCELLED'}

        context.window.cursor_set('SCROLL_X')
        self._timer = context.window_manager.event_timer_add(0.01, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


# --- UI Panel ---
class GRAPH_PT_handle_manipulator(bpy.types.Panel):
    bl_label = "Handle Manipulator"
    bl_idname = "GRAPH_PT_handle_manipulator"
    bl_space_type = 'GRAPH_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Tools"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.scale_y = 1.8
        col = layout.column(align=True)
        
        col.operator(OBJECT_OT_shrink_batches.bl_idname, text="Scale Batch")
        
        col.operator(OBJECT_OT_manipulate_handles_between_frames.bl_idname, text="Slide Batch")
                
        col.separator()
        
        col.operator(OBJECT_OT_rotate_keys.bl_idname, text="Rotate")
        
        col.separator()
        
        col.operator(OBJECT_OT_manipulate_handles.bl_idname, text="Both Handles")
        
        row = col.row(align=True)
        row.operator(OBJECT_OT_manipulate_left_handles.bl_idname, text="Left Handles")
        row.operator(OBJECT_OT_manipulate_right_handles.bl_idname, text="Right Handles")
        
        col.separator()
        
        col.operator(OBJECT_OT_randomize_keys.bl_idname, text="Randomize Y-Value")

        col.separator()
    
        
        # --- NEUER BEREICH FÜR DIE KLEINEREN BUTTONS ---
        filter_row = col.row(align=True)
        filter_row.scale_x = 0.8  # Skaliert die Breite der Buttons
        filter_row.scale_y = 0.6  # Skaliert die Höhe der Buttons
        filter_row.prop(scene, "filter_loc", toggle=True, text="Loc")
        filter_row.prop(scene, "filter_rot", toggle=True, text="Rot")
        filter_row.prop(scene, "filter_scale", toggle=True, text="Scale")

        filter_row = col.row(align=True)
        filter_row.scale_x = 0.8
        filter_row.scale_y = 0.6
        filter_row.prop(scene, "filter_x", toggle=True, text="X")
        filter_row.prop(scene, "filter_y", toggle=True, text="Y")
        filter_row.prop(scene, "filter_z", toggle=True, text="Z")
        # --- ENDE NEUER BEREICH ---
            

            
def register():
    bpy.utils.register_class(OBJECT_OT_randomize_keys)
    bpy.utils.register_class(OBJECT_OT_manipulate_handles)
    bpy.utils.register_class(OBJECT_OT_manipulate_left_handles)
    bpy.utils.register_class(OBJECT_OT_manipulate_right_handles)
    bpy.utils.register_class(OBJECT_OT_rotate_keys)
    bpy.utils.register_class(OBJECT_OT_manipulate_handles_between_frames)
    bpy.utils.register_class(OBJECT_OT_shrink_batches)
    bpy.utils.register_class(GRAPH_PT_handle_manipulator)
    
    bpy.types.Scene.filter_loc = bpy.props.BoolProperty(name="Location Filter", default=False, update=filter_fcurves)
    bpy.types.Scene.filter_rot = bpy.props.BoolProperty(name="Rotation Filter", default=False, update=filter_fcurves)
    bpy.types.Scene.filter_scale = bpy.props.BoolProperty(name="Scale Filter", default=False, update=filter_fcurves)
    bpy.types.Scene.filter_x = bpy.props.BoolProperty(name="X Axis Filter", default=False, update=filter_fcurves)
    bpy.types.Scene.filter_y = bpy.props.BoolProperty(name="Y Axis Filter", default=False, update=filter_fcurves)
    bpy.types.Scene.filter_z = bpy.props.BoolProperty(name="Z Axis Filter", default=False, update=filter_fcurves)



def unregister():
    bpy.utils.unregister_class(OBJECT_OT_randomize_keys)
    bpy.utils.unregister_class(OBJECT_OT_manipulate_handles)
    bpy.utils.unregister_class(OBJECT_OT_manipulate_left_handles)
    bpy.utils.unregister_class(OBJECT_OT_manipulate_right_handles)
    bpy.utils.unregister_class(OBJECT_OT_rotate_keys)
    bpy.utils.unregister_class(OBJECT_OT_manipulate_handles_between_frames)
    bpy.utils.unregister_class(OBJECT_OT_shrink_batches)
    bpy.utils.unregister_class(GRAPH_PT_handle_manipulator)
    


    del bpy.types.Scene.filter_loc
    del bpy.types.Scene.filter_rot
    del bpy.types.Scene.filter_scale
    del bpy.types.Scene.filter_x
    del bpy.types.Scene.filter_y
    del bpy.types.Scene.filter_z

if __name__ == "__main__":
    register()