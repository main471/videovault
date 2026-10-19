"""Génère l'icône VideoVault : un coffre-fort avec un symbole play."""
from PIL import Image, ImageDraw

SIZE = 256
img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# --- Corps du coffre-fort (tuile arrondie, gris ardoise) ---
m = 26
radius = 44
body = [m, m, SIZE - m, SIZE - m]
d.rounded_rectangle(body, radius=radius, fill=(46, 53, 62, 255))
# Liseré extérieur.
d.rounded_rectangle(body, radius=radius, outline=(74, 84, 96, 255), width=3)

# Porte intérieure (encadré en retrait).
inset = 20
door = [m + inset, m + inset, SIZE - m - inset, SIZE - m - inset]
d.rounded_rectangle(door, radius=26, outline=(92, 103, 116, 255), width=4)

cx, cy = SIZE // 2, SIZE // 2

# --- Molette de coffre-fort autour du play ---
# Anneau de la molette.
r_out = 58
d.ellipse([cx - r_out, cy - r_out, cx + r_out, cy + r_out],
          outline=(150, 160, 172, 255), width=7)

# Ergots de la molette (petits traits radiaux, repères de combinaison).
import math
r_in, r_tick = 58, 72
for ang in range(0, 360, 30):
    a = math.radians(ang)
    x1 = cx + r_in * math.cos(a)
    y1 = cy + r_in * math.sin(a)
    x2 = cx + r_tick * math.cos(a)
    y2 = cy + r_tick * math.sin(a)
    d.line([x1, y1, x2, y2], fill=(120, 131, 144, 255), width=5)

# --- Symbole play au centre (triangle blanc cassé) ---
s = 30
triangle = [(cx - s + 6, cy - s), (cx - s + 6, cy + s), (cx + s + 4, cy)]
d.polygon(triangle, fill=(235, 237, 240, 255))

# --- Poignée du coffre (à droite) ---
hx = SIZE - m - inset - 2
d.line([hx, cy - 16, hx, cy + 16], fill=(150, 160, 172, 255), width=8)

img.save("docs/icon.png")
img.save("docs/icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
print("Icône coffre-fort + play générée : docs/icon.png, docs/icon.ico")
