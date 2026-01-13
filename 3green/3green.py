import colorsys
import matplotlib.pyplot as plt

hue = (3 + 1) / 12        # 3 → 120°
rgb = colorsys.hsv_to_rgb(hue, 1, 1)

plt.imshow([[rgb]])
plt.title("3 === GREEN")
plt.axis("off")
plt.show()
