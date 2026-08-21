import os
import math
import numpy as np
import trimesh
from trimesh.creation import cylinder, box

output_dir = r"c:\Users\wlals\OneDrive\문서\Vico - Ai drawing\stl_parts"
os.makedirs(output_dir, exist_ok=True)

# Helper function to create hollow cylinder or hole cutouts
def create_cylinder_hole(radius, height, transform=None):
    c = cylinder(radius=radius, height=height, sections=32)
    if transform is not None:
        c.apply_transform(transform)
    return c

# 1. NEMA 17 Stepper Motor Mount
def generate_motor_mount():
    # NEMA 17 faceplate: 42x42mm, thickness 6mm, center boss hole 23mm, bolt holes 31mm spacing M3 (radius 1.7mm)
    mount_base = box(extents=[42, 42, 6])
    
    # Center boss hole (23mm diameter, 11.5mm radius) + shaft clearance
    center_hole = cylinder(radius=11.5, height=10, sections=32)
    
    # 4 M3 bolt holes (31mm spacing -> offset +-15.5)
    holes = [center_hole]
    for dx in [-15.5, 15.5]:
        for dy in [-15.5, 15.5]:
            h = cylinder(radius=1.7, height=10, sections=16)
            h.apply_translation([dx, dy, 0])
            holes.append(h)
            
    # Base attachment ears/flange (bottom plate for fixing to acrylic)
    flange = box(extents=[60, 20, 6])
    flange.apply_translation([0, -21, -3]) # attached at bottom edge
    
    # Flange M4 mounting holes
    for dx in [-22, 22]:
        h = cylinder(radius=2.2, height=10, sections=16)
        h.apply_translation([dx, -21, -3])
        holes.append(h)

    # Combine & subtract
    mesh = mount_base.union(flange)
    for h in holes:
        mesh = mesh.difference(h)
        
    mesh.export(os.path.join(output_dir, "1_nema17_motor_mount.stl"))
    print("Generated 1_nema17_motor_mount.stl")

# 2. Y-Axis Rod Support / End Block (for 8mm smooth rod)
def generate_rod_support():
    # Block 30x20x25mm, 8.2mm hole at Z=15mm height
    block = box(extents=[30, 20, 25])
    block.apply_translation([0, 0, 12.5])
    
    # 8.2mm rod hole along Y axis (X-rotation 90 deg)
    rod_hole = cylinder(radius=4.1, height=40, sections=32)
    rod_hole.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2, [1, 0, 0]))
    rod_hole.apply_translation([0, 0, 15])
    
    # Base M4 mounting holes (2 holes)
    h1 = cylinder(radius=2.2, height=30, sections=16)
    h1.apply_translation([-10, 0, 12.5])
    h2 = cylinder(radius=2.2, height=30, sections=16)
    h2.apply_translation([10, 0, 12.5])
    
    mesh = block.difference(rod_hole).difference(h1).difference(h2)
    mesh.export(os.path.join(output_dir, "2_y_axis_rod_support.stl"))
    print("Generated 2_y_axis_rod_support.stl")

# 3. Y-Axis Gantry Slider (Holds LM8UU bearings for Y-axis + X-axis rods)
def generate_y_gantry_slider():
    # Block 40x45x30mm
    block = box(extents=[40, 45, 30])
    block.apply_translation([0, 0, 15])
    
    # LM8UU bearing hole (OD 15.2mm -> radius 7.6mm) along Y-axis
    lm8uu_hole = cylinder(radius=7.6, height=50, sections=32)
    lm8uu_hole.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2, [1, 0, 0]))
    lm8uu_hole.apply_translation([0, 0, 10])
    
    # Two X-axis rod holes (8.2mm diameter, 4.1mm radius) along X-axis at Z=22mm, spaced 18mm in Y
    x_rod1 = cylinder(radius=4.1, height=50, sections=32)
    x_rod1.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2, [0, 1, 0]))
    x_rod1.apply_translation([0, -9, 22])
    
    x_rod2 = cylinder(radius=4.1, height=50, sections=32)
    x_rod2.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2, [0, 1, 0]))
    x_rod2.apply_translation([0, 9, 22])
    
    # Belt clamp slot (6.5mm wide slot for GT2 belt)
    belt_slot = box(extents=[10, 7, 10])
    belt_slot.apply_translation([15, 0, 10])
    
    mesh = block.difference(lm8uu_hole).difference(x_rod1).difference(x_rod2).difference(belt_slot)
    mesh.export(os.path.join(output_dir, "3_y_gantry_slider.stl"))
    print("Generated 3_y_gantry_slider.stl")

# 4. X-Axis Pen Carriage Main Body (Holds 2x LM8UU bearings for X rods)
def generate_x_pen_carriage():
    # Block 50x45x28mm
    block = box(extents=[50, 45, 28])
    block.apply_translation([0, 0, 14])
    
    # Two LM8UU bearing holes along X-axis at Z=14mm, Y spacing 18mm
    lm8uu_1 = cylinder(radius=7.6, height=60, sections=32)
    lm8uu_1.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2, [0, 1, 0]))
    lm8uu_1.apply_translation([0, -9, 14])
    
    lm8uu_2 = cylinder(radius=7.6, height=60, sections=32)
    lm8uu_2.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2, [0, 1, 0]))
    lm8uu_2.apply_translation([0, 9, 14])
    
    # SG90 Servo mounting pocket (23x12.5mm, 15mm deep) on front face
    servo_pocket = box(extents=[23.5, 13, 20])
    servo_pocket.apply_translation([0, 17, 14])
    
    # M3 mounting holes for front Pen Lifter slide guide
    m3_1 = cylinder(radius=1.6, height=40, sections=16)
    m3_1.apply_translation([-18, 17, 14])
    m3_2 = cylinder(radius=1.6, height=40, sections=16)
    m3_2.apply_translation([18, 17, 14])
    
    # GT2 Belt clamp groove on back
    belt_groove = box(extents=[40, 4, 8])
    belt_groove.apply_translation([0, -20, 14])
    
    mesh = block.difference(lm8uu_1).difference(lm8uu_2).difference(servo_pocket).difference(m3_1).difference(m3_2).difference(belt_groove)
    mesh.export(os.path.join(output_dir, "4_x_pen_carriage.stl"))
    print("Generated 4_x_pen_carriage.stl")

# 5. Pen Lifter & Pen Holder
def generate_pen_holder():
    # Vertical sliding plate with pen clamp cylinder (Pen diameter 12mm -> radius 6.1mm)
    holder_body = box(extents=[30, 25, 55])
    holder_body.apply_translation([0, 0, 27.5])
    
    # Pen Hole (Vertical 12.2mm diameter cylinder cut)
    pen_hole = cylinder(radius=6.1, height=70, sections=32)
    pen_hole.apply_translation([0, 3, 27.5])
    
    # Pen tightening Thumb screw M3 hole from front
    screw_hole = cylinder(radius=1.6, height=30, sections=16)
    screw_hole.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2, [1, 0, 0]))
    screw_hole.apply_translation([0, 10, 35])
    
    # Servo push arm contact ledge at Z=10mm
    ledge = box(extents=[15, 10, 5])
    ledge.apply_translation([0, -10, 10])
    
    mesh = holder_body.union(ledge).difference(pen_hole).difference(screw_hole)
    mesh.export(os.path.join(output_dir, "5_pen_holder.stl"))
    print("Generated 5_pen_holder.stl")

# 6. Limit Switch Mount
def generate_limit_switch_mount():
    # Compact mount for Micro switch (M2/M2.5 hole spacing 9.5mm)
    base = box(extents=[25, 15, 4])
    base.apply_translation([0, 0, 2])
    
    wall = box(extents=[25, 4, 15])
    wall.apply_translation([0, 5.5, 7.5])
    
    # 2x Switch mounting holes M2.5 (1.3mm radius)
    h1 = cylinder(radius=1.3, height=10, sections=16)
    h1.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2, [1, 0, 0]))
    h1.apply_translation([-4.75, 5.5, 8])
    
    h2 = cylinder(radius=1.3, height=10, sections=16)
    h2.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2, [1, 0, 0]))
    h2.apply_translation([4.75, 5.5, 8])
    
    # Rod clamp / frame mounting hole M3
    h_frame = cylinder(radius=1.7, height=10, sections=16)
    h_frame.apply_translation([0, -3, 2])
    
    mesh = base.union(wall).difference(h1).difference(h2).difference(h_frame)
    mesh.export(os.path.join(output_dir, "6_limit_switch_mount.stl"))
    print("Generated 6_limit_switch_mount.stl")

if __name__ == "__main__":
    generate_motor_mount()
    generate_rod_support()
    generate_y_gantry_slider()
    generate_x_pen_carriage()
    generate_pen_holder()
    generate_limit_switch_mount()
