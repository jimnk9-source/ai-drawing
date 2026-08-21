import os
import math
import struct

output_dir = r"c:\Users\wlals\OneDrive\문서\Vico - Ai drawing\stl_parts"
os.makedirs(output_dir, exist_ok=True)

def write_stl(filename, triangles):
    """
    triangles: list of (normal, (v1, v2, v3))
    """
    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'wb') as f:
        # 80 bytes header
        header = b'Vico AI Drawing Plotter 3D STL Part'.ljust(80, b'\x00')
        f.write(header)
        # number of triangles
        f.write(struct.pack('<I', len(triangles)))
        for normal, (v1, v2, v3) in triangles:
            # 3 floats normal, 9 floats vertices, 2 bytes attribute
            f.write(struct.pack('<ffffffffffffH', 
                                normal[0], normal[1], normal[2],
                                v1[0], v1[1], v1[2],
                                v2[0], v2[1], v2[2],
                                v3[0], v3[1], v3[2],
                                0))
    print(f"Generated: {filename} ({len(triangles)} triangles)")

def calc_normal(v1, v2, v3):
    ax, ay, az = v2[0]-v1[0], v2[1]-v1[1], v2[2]-v1[2]
    bx, by, bz = v3[0]-v1[0], v3[1]-v1[1], v3[2]-v1[2]
    nx = ay*bz - az*by
    ny = az*bx - ax*bz
    nz = ax*by - ay*bx
    length = math.sqrt(nx*nx + ny*ny + nz*nz)
    if length > 0:
        return (nx/length, ny/length, nz/length)
    return (0, 0, 0)

def add_box(triangles, x0, x1, y0, y1, z0, z1):
    vertices = [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), # Bottom 0,1,2,3
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)  # Top 4,5,6,7
    ]
    faces = [
        # Bottom (-Z)
        (0, 2, 1), (0, 3, 2),
        # Top (+Z)
        (4, 5, 6), (4, 6, 7),
        # Front (-Y)
        (0, 1, 5), (0, 5, 4),
        # Back (+Y)
        (2, 3, 7), (2, 7, 6),
        # Left (-X)
        (0, 4, 7), (0, 7, 3),
        # Right (+X)
        (1, 2, 6), (1, 6, 5)
    ]
    for i1, i2, i3 in faces:
        v1, v2, v3 = vertices[i1], vertices[i2], vertices[i3]
        n = calc_normal(v1, v2, v3)
        triangles.append((n, (v1, v2, v3)))

def add_cylinder(triangles, cx, cy, z0, z1, radius, segments=24):
    top_verts = []
    bot_verts = []
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        bot_verts.append((x, y, z0))
        top_verts.append((x, y, z1))
    
    bot_center = (cx, cy, z0)
    top_center = (cx, cy, z1)
    
    for i in range(segments):
        next_i = (i + 1) % segments
        # Bottom face (-Z)
        v1, v2, v3 = bot_center, bot_verts[next_i], bot_verts[i]
        triangles.append((calc_normal(v1, v2, v3), (v1, v2, v3)))
        # Top face (+Z)
        v1, v2, v3 = top_center, top_verts[i], top_verts[next_i]
        triangles.append((calc_normal(v1, v2, v3), (v1, v2, v3)))
        # Side Quad (2 triangles)
        v1, v2, v3 = bot_verts[i], bot_verts[next_i], top_verts[next_i]
        triangles.append((calc_normal(v1, v2, v3), (v1, v2, v3)))
        v1, v2, v3 = bot_verts[i], top_verts[next_i], top_verts[i]
        triangles.append((calc_normal(v1, v2, v3), (v1, v2, v3)))

# 1. NEMA 17 Motor Mount STL
def gen_1_nema17_mount():
    tris = []
    # Main Plate 42x42x6mm
    add_box(tris, -21, 21, -21, 21, 0, 6)
    # Bottom Flange 60x20x6mm
    add_box(tris, -30, 30, -35, -15, 0, 6)
    # Center Boss ring & Motor Support pillars
    add_cylinder(tris, 0, 0, 6, 8, 14, 24)
    write_stl("1_nema17_motor_mount.stl", tris)

# 2. Y-Axis Rod Support STL
def gen_2_y_rod_support():
    tris = []
    # Main Block 30x20x25mm
    add_box(tris, -15, 15, -10, 10, 0, 25)
    # Rod Clamp Top Ridge
    add_box(tris, -15, 15, -5, 5, 25, 28)
    write_stl("2_y_axis_rod_support.stl", tris)

# 3. Y-Axis Gantry Slider STL
def gen_3_y_gantry_slider():
    tris = []
    # Main Gantry Body 40x45x30mm
    add_box(tris, -20, 20, -22.5, 22.5, 0, 30)
    # X-rod holding extension
    add_box(tris, -20, 20, -22.5, 22.5, 30, 34)
    write_stl("3_y_gantry_slider.stl", tris)

# 4. X-Axis Pen Carriage Main Body STL
def gen_4_x_pen_carriage():
    tris = []
    # Main Carriage Block 50x45x28mm
    add_box(tris, -25, 25, -22.5, 22.5, 0, 28)
    # Servo mount extension bracket
    add_box(tris, -15, 15, 22.5, 32.5, 5, 25)
    write_stl("4_x_pen_carriage.stl", tris)

# 5. Pen Holder & Lifter Bracket STL
def gen_5_pen_holder():
    tris = []
    # Slider Plate 30x6x55mm
    add_box(tris, -15, 15, -3, 3, 0, 55)
    # Pen Clamp Sleeve (Outer cylinder)
    add_cylinder(tris, 0, 10, 10, 45, 10, 24)
    # Servo Arm Pusher Ledge
    add_box(tris, -8, 8, -10, -3, 8, 14)
    write_stl("5_pen_holder.stl", tris)

# 6. Limit Switch Mount STL
def gen_6_limit_switch_mount():
    tris = []
    # Base Mount 25x15x4mm
    add_box(tris, -12.5, 12.5, -7.5, 7.5, 0, 4)
    # Switch Backing Vertical Wall 25x4x15mm
    add_box(tris, -12.5, 12.5, 3.5, 7.5, 4, 19)
    write_stl("6_limit_switch_mount.stl", tris)

if __name__ == "__main__":
    gen_1_nema17_mount()
    gen_2_y_rod_support()
    gen_3_y_gantry_slider()
    gen_4_x_pen_carriage()
    gen_5_pen_holder()
    gen_6_limit_switch_mount()
