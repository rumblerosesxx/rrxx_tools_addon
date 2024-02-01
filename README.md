# rrxx_tools_addon
Blender import/export of Rumble Roses XX model files


Originally written by anonymous loverslab member, based on maxscript from mariokart64n.

NSFW link: https://www.loverslab.com/topic/54420-rumble-roses-xx-nude-mod-xbox360/page/3/

With this addon, you can import Rumble Roses XX model (meshes and bones) and export it back (vertex position/UV/normal/weight/color).


![Menu](https://github.com/rumblerosesxx/rrxx_tools_addon/blob/3820adef217425b0c6de9203da956228b01a8bdc/menu.png)

 

FAQ:

- How can I hide some vertices?

Well, there are two ways to hide them.

(1) In object mode, hide unnecessary objects by hitting H key. Then export model.

(2) In edit mode, select unnecessary vertices and scale very small like 0.1.
    Move them into middle of body, then remove their weight from all groups.
    Give them weight 1.0 for a center bone (eg. koshi, mune). Then export model.

 

- When I edit mesh, it starts to look blocky. Why?

Good question. Because every vertex has custom normals, you need to fix normals after editing shape.

You can use Data Transfer modifier, to copy correct custom normals from another mesh.

Caution: When cloning mesh for normal reference, remove Custom Property (prop_id) from the new cloned object. It's used by export function.

 

- Does it import textures?

No. You should manually assign textures if you need.

 

Credit:

Original 3ds Max script - thanks mariokart64n!

https://www.youtube.com/playlist?list=PLgeoiwC2u6R6SaRFDAZCI9J_QUoptVmcK

 

Changelog:

 - v1.0.3: Port to blender 3.5

 - v1.0.2: Fix Shift-JIS name issue
   
 - v1.0.1: Fixed error when exporting

 - v1.0.0: Initial release
