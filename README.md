Vibecoded with google gemini. I have no idea how to write python code

v1.1

changes:
- added icons
- quick selection navigation with NumPad_1, 2, 3 and 5: Toggle through them. 5 is adding to selection on the right. 2 is deleting selection from the right
- slide operator: Like extend on individual origins without changing direction 
- flatten operator: Reverse to rotate (useful when you have extreme random rotations and you dont wanna give up the motion)
- scale: How often do you want to scale relative to the first selected key in blender but cant make the timeline cursor stop while playing the animation?
- move keyframe in x: Not very useful but why not
- Random Operators: Extrusion, rotation, x-value, y-valus. Self explanatory
- On bones option: untoggled: randomizes every selected keyframe. toggled: randomization refers to the whole bone as one (Useful for quick timing randomization between different bones for example with x-value randomization)

- isolate bones option: basically toggles SHIFT + H and ALT + H in 3d viewport (useful when you have a dopesheet window with all keyed bones somewhere, select them and quickly hide all bones which have no keyframe)
- keep framerange: untoggle for selection dependant framerange. When animation is NOT playing the numpad selections change the cursor position. When animation is playing every operator sets the timelines around the selection. Buffer frames can be customized with preframe and postframe. When only one key selection per curve, the timeline reference extends to neighbouring keyframes. Toggle "Keep Framerange" to disable the whole option (useful in small looping animations)
- move to cursor operator: Move selected keys to timeline cursor. Useful for reversing the random x-value operation
- decimate keyframes operator: Useful for quickly decimating baked animations. select the curve extremes to preserve the shape and click this button (Nothing fancy, just a quick decimate by error operation)

- rotation strength is now also dependant on next keyframe
- there are still some bugs with the cursor jump to selection
