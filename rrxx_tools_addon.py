bl_info = {
    "name": "RRXX Tools",
    "author": "loverslab member (Thanks to mariokart64n for original Max script)",
    "version": (1, 0, 2),
    "blender": (2, 79, 0),
    "location": "View3D > Tool Shelf > Misc Tab",
    "description": "",
    "warning": "",
    "wiki_url": "",
    "category": "Import-Export",
}
import bpy
import math, re, os
from struct import pack, unpack
from mathutils import Vector, Matrix, Euler

####### const
START_OFS = 8

####### YobjData
class YobjData:
    def __init__(self, f):
        self.inFile = f
        f.seek(0)
        assert f.read(4) == b"JBOY"
        self.pof0Ofs = unpack(">I", f.read(4))[0] + START_OFS
        assert unpack(">I", f.read(4))[0] == 0
        assert (unpack(">I", f.read(4))[0] + START_OFS) == self.pof0Ofs
        assert unpack(">I", f.read(4))[0] == 0
        assert unpack(">I", f.read(4))[0] == 0
        self.meshCount = unpack(">I", f.read(4))[0]
        self.meshOfs = unpack(">I", f.read(4))[0] + START_OFS
        self.boneCount = unpack(">I", f.read(4))[0]
        self.texCount = unpack(">I", f.read(4))[0]
        self.boneOfs = unpack(">I", f.read(4))[0] + START_OFS
        self.texNameOfs = unpack(">I", f.read(4))[0] + START_OFS
        self.objGroupNameOfs = unpack(">I", f.read(4))[0] + START_OFS
        self.objGroupCount = unpack(">I", f.read(4))[0]
        assert unpack(">I", f.read(4))[0] == 0
        assert unpack(">I", f.read(4))[0] == 0

        self.texNames = []
        f.seek(self.texNameOfs)
        for i in range(self.texCount):
            self.texNames.append( unpack("16s", f.read(16))[0].decode("sjis").strip("\0") )

        self.objGroupNames = []
        f.seek(self.objGroupNameOfs)
        for i in range(self.objGroupCount):
            self.objGroupNames.append( unpack("16s", f.read(16))[0].decode("sjis").strip("\0") )
            assert unpack(">I", f.read(4))[0] == 1
            assert unpack(">I", f.read(4))[0] == 0
            _texCountInOb = unpack(">I", f.read(4))[0]
            assert unpack(">I", f.read(4))[0] == 0

        self.bones = []
        for i in range(self.boneCount):
            f.seek(self.boneOfs + 80 * i)
            self.bones.append(BoneData(f, i))
        self.boneNames = [ self.bones[i].name for i in range(self.boneCount) ]

        self.objs = []
        for i in range(self.meshCount):
            f.seek(self.meshOfs + 180 * i)
            self.objs.append(ObjData(f, i, self.objGroupNames, self.boneNames))

    def importModel(self, modelName):
        ## create armature
        bpy.ops.object.armature_add(location=(0, 0, 0))
        armature = bpy.context.object
        armature.show_x_ray = True
        armature.data.draw_type = "STICK"
        armature.name = modelName
        armature.rotation_euler[0] = math.radians(-90)
        armature.scale = Vector((0.1, ) * 3)
        armature.location = Vector((0, 0, 1.115))

        bpy.ops.object.mode_set(mode="EDIT")
        for i, bone in enumerate(self.bones):
            if i > 0:
                bpy.ops.armature.bone_primitive_add()
            eBone = bpy.context.object.data.edit_bones[-1]
            eBone.name = bone.name
            if "prop_childCount" not in eBone:
                eBone["prop_childCount"] = 0
            eBone.head = Vector((0, 0, 0))
            eBone.tail = Vector((1, 0, 0))
            eBone.length = 0.5
            eBone.transform( Euler(bone.rot[0:3]).to_matrix().to_4x4(), roll=False )
            eBone.transform( Matrix.Translation(bone.pos[0:3]), roll=False )

            if bone.parentId >= 0:
                eBone.parent = bpy.context.object.data.edit_bones[ self.bones[bone.parentId].name ]
                eBone.parent["prop_id"] = bone.parentId
                eBone.parent["prop_childCount"] += 1
            for pBone in eBone.parent_recursive:
                parentBone = self.bones[pBone["prop_id"]]
                eBone.transform(
                    Matrix.Translation(parentBone.pos[0:3]) *
                    Euler(parentBone.rot[0:3]).to_matrix().to_4x4()
                    , roll=False
                )

        for eBone in reversed(bpy.context.object.data.edit_bones):   # fix orient
            for pBone in eBone.parent_recursive:
                if pBone["prop_childCount"] == 1 or \
                    pBone.name + "_d" == eBone.name or \
                    pBone.name + "_x" == eBone.name:
                        pBone.tail = eBone.head.copy()

        bpy.ops.object.mode_set(mode="OBJECT")

        ## create meshes
        for obj in self.objs:
            mesh = bpy.data.meshes.new(obj.name)
            mesh.from_pydata(obj.verts, [], obj.faces)
            mesh.update()
            mesh.use_auto_smooth = True
            mesh.normals_split_custom_set_from_vertices(obj.normals)
            ob = bpy.data.objects.new(obj.name, mesh)
            bpy.context.scene.objects.link(ob)
            bpy.context.scene.objects.active = ob
            ob.location = Vector((0, 0, 0))
            ob.parent = armature
            ob.hide = (obj.vertCount == 0)

            bpy.ops.mesh.uv_texture_add()
            uvMap = mesh.uv_layers[0]
            for fIdx, poly in enumerate(mesh.polygons):
                for vNum, loopIdx in enumerate(poly.loop_indices):
                    vIdx = poly.vertices[vNum]
                    uvMap.data[loopIdx].uv = obj.uvs[vIdx]

            for boneId in obj.boneIds:
                ob.vertex_groups.new(self.bones[boneId].name)
            for i in range(obj.vertCount):
                for boneId, weight in obj.weights[i]:
                    ob.vertex_groups[self.bones[boneId].name].add([i], weight, "REPLACE")

            bpy.ops.mesh.vertex_color_add()
            colMap = mesh.vertex_colors[0]
            for fIdx, poly in enumerate(mesh.polygons):
                for vNum, loopIdx in enumerate(poly.loop_indices):
                    vIdx = poly.vertices[vNum]
                    colMap.data[loopIdx].color = obj.colors[vIdx][0:3]

            # remember obj id
            ob["prop_id"] = obj.id
            # modifier
            bpy.ops.object.modifier_add(type="ARMATURE")
            ob.modifiers[-1].object = armature


    def modifyModel(self, outFilepath):
        selectedObjects = getSelectedObjects()
        if len(selectedObjects) == 0:
            return

        self.inFile.seek(0)
        data = bytearray(self.inFile.read())
        for ob in selectedObjects:
            if "prop_id" not in ob:
                continue
            mesh = ob.data
            obj = self.objs[ob["prop_id"]]

            # prepare normal
            normalMap = {}  # vIdx => normal
            mesh.calc_normals_split()
            for fIdx, poly in enumerate(mesh.polygons):
                for vNum, loopIdx in enumerate(poly.loop_indices):
                    vIdx = poly.vertices[vNum]
                    if vIdx not in normalMap:
                        normalMap[vIdx] = Vector((0, 0, 0))
                    normalMap[vIdx] -= mesh.loops[loopIdx].normal
            for normal in normalMap.values():
                normal.normalize()
            # prepare color
            outColMap = {}  # vIdx => color
            colMap = mesh.vertex_colors[0]
            for fIdx, poly in enumerate(mesh.polygons):
                for vNum, loopIdx in enumerate(poly.loop_indices):
                    vIdx = poly.vertices[vNum]
                    outColMap[vIdx] = colMap.data[loopIdx].color

            # set vert, normal, color
            ofs = obj.vertOfs2
            for i in range(obj.vertCount):
                if ob.hide == False:
                    data[ofs : ofs + 12] = pack(">3f", *ob.data.vertices[i].co.to_tuple())
                else:
                    data[ofs : ofs + 12] = pack(">3f", 0, 0, 0)
                ofs += 12
                normal = normalMap[i]
                data[ofs : ofs + 12] = pack(">3f", *normal.to_tuple())
                ofs += 12
                data[ofs : ofs + 4] = pack("4B",
                    round(outColMap[i][0] * 255), round(outColMap[i][1] * 255),
                    round(outColMap[i][2] * 255), round(outColMap[i][2] * 255)
                )
                ofs += 4

            # prepare UV
            outUvMap = {}  # vIdx => UV
            uvMap = mesh.uv_layers[0]
            for fIdx, poly in enumerate(mesh.polygons):
                for vNum, loopIdx in enumerate(poly.loop_indices):
                    vIdx = poly.vertices[vNum]
                    outUvMap[vIdx] = uvMap.data[loopIdx].uv
            # set UV
            ofs = obj.uvOfs
            for i in range(obj.vertCount):
                data[ofs : ofs + 8] = pack(">2f", outUvMap[i][0], 1.0 - outUvMap[i][1])
                ofs += 8

            # set weight
            ofs = obj.weightOfs
            vgroups = [ ob.vertex_groups[name] for name in obj.boneNames if name in ob.vertex_groups ]
            for i, vert in enumerate(mesh.vertices):
                curVgroups = []  # vertex groups having bone weight
                if ob.hide == False:
                    for vg in vgroups:
                        try:
                            if vg.weight(i) > 0.0001:
                                curVgroups.append(vg)
                        except:
                            pass  # skip null weight
                for j in range(obj.boneLimit):
                    if j < len(curVgroups):
                        vg = curVgroups[j]
                        data[ofs : ofs + 4] = pack("<I", obj.boneNames.index(vg.name))
                        ofs += 4
                        data[ofs : ofs + 4] = pack(">f", vg.weight(i))
                        ofs += 4
                    else:
                        data[ofs : ofs + 4] = pack("<I", 255)
                        ofs += 4
                        data[ofs : ofs + 4] = pack(">f", 0.0)
                        ofs += 4

        with open(outFilepath, "wb") as outFile:
            outFile.write(data)

####### ObjData
class ObjData:
    def __init__(self, f, id, names, boneNames):
        self.id = id
        self.unks = []
        self.headerOfs = f.tell()
        self.vertCount = unpack(">I", f.read(4))[0]
        self.drawCount = unpack(">I", f.read(4))[0]
        _boneCount = unpack(">I", f.read(4))[0]
        self.boneIds = [ val - 1 for val in unpack(">%dI" % _boneCount, f.read(4 * _boneCount)) ]
        self.boneNames = [ boneNames[bId] for bId in self.boneIds ]
        f.seek((20 - len(self.boneIds)) * 4, 1)
        self.boneLimit = unpack(">I", f.read(4))[0]
        self.objGroupId = unpack(">I", f.read(4))[0]
        self.name = "%s_%02d" % (names[self.objGroupId], self.id)
        assert unpack(">I", f.read(4))[0] == 1
        self.vertOfs = unpack(">I", f.read(4))[0] + START_OFS
        self.weightOfs = unpack(">I", f.read(4))[0] + START_OFS
        self.uvOfs = unpack(">I", f.read(4))[0] + START_OFS
        assert unpack(">I", f.read(4))[0] == 1
        self.yName = unpack("16s", f.read(16))[0].decode("sjis").strip("\0")  # yBumpMap, etc.
        self.unks += unpack(">I", f.read(4))
        self.unks += unpack(">I", f.read(4))
        self.texCount = unpack(">I", f.read(4))[0]
        self.texOfs = unpack(">I", f.read(4))[0] + START_OFS
        self.drawOfs = unpack(">I", f.read(4))[0] + START_OFS
        self.vertCountCopy = unpack(">I", f.read(4))[0]
        assert unpack(">I", f.read(4))[0] == 0
        self.pos = unpack("<3f", f.read(12))
        self.posRadius = unpack("<f", f.read(4))[0]
        ## header END

        self.verts = []
        self.normals = []
        self.colors = []
        f.seek(self.vertOfs)
        self.vertOfs2 = unpack(">I", f.read(4))[0] + START_OFS
        f.seek(self.vertOfs2)
        for i in range(self.vertCount):
            self.verts.append(unpack(">3f", f.read(12)))
            x, y, z = unpack(">3f", f.read(12))
            self.normals.append((-x, -y, -z))
            self.colors.append([ v / 255 for v in unpack("4B", f.read(4)) ])  ## RGBB

        self.uvs = []
        f.seek(self.uvOfs)
        for i in range(self.vertCount):
            self.uvs.append((unpack(">f", f.read(4))[0], 1.0 - unpack(">f", f.read(4))[0]))

        self.weights = []
        f.seek(self.weightOfs)
        for i in range(self.vertCount):
            self.weights.append([])
            for j in range(self.boneLimit):
                boneIdx = unpack("<I", f.read(4))[0]
                weight = unpack(">f", f.read(4))[0]
                if boneIdx != 255:
                    self.weights[i].append( (self.boneIds[boneIdx], weight) )

        self.faces = []
        f.seek(self.drawOfs)
        if self.vertCount > 0:
            for i in range(self.drawCount):
                f.seek(self.drawOfs + (12 * i))
                assert unpack(">I", f.read(4))[0] == 6
                faceIndiceCount = unpack(">I", f.read(4))[0]
                faceOfs = unpack(">I", f.read(4))[0] + START_OFS
                f.seek(faceOfs)
                faceDirection = 1
                fIdx1 = unpack(">H", f.read(2))[0]
                fIdx2 = unpack(">H", f.read(2))[0]
                for j in range(2, faceIndiceCount):
                    fIdx3 = unpack(">H", f.read(2))[0]
                    faceDirection *= -1
                    if (fIdx3 != fIdx1) and (fIdx3 != fIdx2):
                        if faceDirection > 0:
                            self.faces.append((fIdx1, fIdx2, fIdx3))
                        else:
                            self.faces.append((fIdx1, fIdx3, fIdx2))
                    fIdx1 = fIdx2
                    fIdx2 = fIdx3

####### BoneData
class BoneData:
    def __init__(self, f, id):
        self.id = id
        self.name = unpack("16s", f.read(16))[0].decode("sjis").strip("\0")
        self.pos = unpack(">4f", f.read(16))
        assert self.pos[3] == 0.0
        self.rot = unpack(">4f", f.read(16))
        assert self.rot[3] == 0.0
        self.parentId = unpack(">i", f.read(4))[0]
        assert unpack(">I", f.read(4))[0] == 0
        assert unpack(">I", f.read(4))[0] == 0
        assert unpack(">I", f.read(4))[0] == 0
        self.endPos = unpack("<4f", f.read(16))

####### RRXXOpsImport
class RRXXOpsImport(bpy.types.Operator):
    bl_idname = "import.rrxx"
    bl_label = "Import RRXX Model"
    filepath = bpy.props.StringProperty(subtype="FILE_PATH")
    filename = bpy.props.StringProperty(subtype="FILE_NAME")

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT"

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        self.report({'INFO'}, "loading " + self.filepath)
        with open(self.filepath, "rb") as f:
            yobj = YobjData(f)
            yobj.importModel(self.filename)
            bpy.ops.object.select_all(action="DESELECT")
            self.report({'INFO'}, "finished")
        return {'FINISHED'}

####### RRXXOpsExport
class RRXXOpsExport(bpy.types.Operator):
    bl_idname = "export.rrxx"
    bl_label = "Export RRXX Model"
    filepath = bpy.props.StringProperty(subtype="FILE_PATH")
    filename = bpy.props.StringProperty(subtype="FILE_NAME")

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and len(getSelectedObjects()) > 0

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        with open(self.filepath, "rb") as f:
            yobj = YobjData(f)
            outDir = os.path.dirname(self.filepath) + "/MOD/"
            os.makedirs(outDir, exist_ok=True)
            outFilepath = outDir + self.filename
            self.report({'INFO'}, "saving to " + outFilepath)
            yobj.modifyModel(outFilepath)
            self.report({'INFO'}, "finished")
        return {'FINISHED'}

####### RRXXOpsSelectChildren
class RRXXOpsSelectChildren(bpy.types.Operator):
    bl_idname = "object.rrxx_select_children"
    bl_label = "Select Children"

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and len(getSelectedObjects()) == 1

    def execute(self, context):
        for ob in context.object.children:
            ob.select = True
        return {'FINISHED'}

####### RRXXPanel
class RRXXPanel(bpy.types.Panel):
    bl_label = "RRXX Tools"
    bl_idname = "VIEW3D_PT_rrxx"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"

    def draw(self, context):
        l = self.layout
        l.row().label("1. Import *.yobj or *.ymxen file.")
        l.row().operator("import.rrxx", icon="FILESEL")
        l.row().label("2. Edit vertex position/UV/normal/weight/color.")
        l.row().label("3. Select Armature and child objects.")
        l.row().operator("object.rrxx_select_children", icon="RESTRICT_SELECT_OFF")
        l.row().label("4. Export.")
        l.row().label("Select original file and you will get new file in MOD dir.")
        l.row().operator("export.rrxx", icon="SAVE_PREFS")
        l.row().label("5. Don't earn money with mod. Respect game author. Thanks!")

####### getSelectedObjects
def getSelectedObjects():
    return [ob for ob in bpy.context.scene.objects if ob.select == True]

######################## register
def register():
    bpy.utils.register_module(__name__)

def unregister():
    bpy.utils.unregister_module(__name__)

if __name__ == "__main__":
    register()
