bl_info = {
    "name": "RRXX Tools",
    "author": "loverslab member (Thanks to mariokart64n for original Max script)",
    "version": (1, 0, 3),
    "blender": (3, 5, 0),
    "location": "View3D > Tool Shelf > Misc Tab",
    "description": "",
    "warning": "",
    "wiki_url": "",
    "category": "Import-Export",
}
import bpy
import math, re, os
from struct import pack, unpack
from mathutils import Vector, Matrix, Euler, Quaternion

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

    def importModel(self, modelName, logger):
        # create armature
        bpy.ops.object.armature_add(location=(0, 0, 0))
        armature = bpy.context.object
        armature.show_in_front = True
        armature.data.display_type = "STICK"
        armature.name = modelName
        armature.rotation_euler[0] = math.radians(-90)
        armature.scale = Vector((0.1, ) * 3)
        armature.location = Vector((0, 0, 1.115))

       # TODO: re-enable armature import once it works properly
       #bpy.ops.object.mode_set(mode="EDIT")
       #for i, bone in enumerate(self.bones):
       #    if i > 0:
       #        bpy.ops.armature.bone_primitive_add()
       #    eBone = armature.data.edit_bones[-1]
       #    eBone.name = bone.name
       #    if "prop_childCount" not in eBone:
       #        eBone["prop_childCount"] = 0
       #    eBone.head = bpy.context.object.data.edit_bones[-2].tail if i > 0 else Vector((0, 0, 0))
       #    eBone.tail = Vector((0, 0, 0.5))
       #    eBone.length = 0.5
       #    eBone.matrix = Euler(bone.rot[0:3]).to_matrix().to_4x4() @ Matrix.Translation(bone.pos[0:3])
       #   
       #    if bone.parentId >= 0:
       #        eBone.parent = armature.data.edit_bones[ self.bones[bone.parentId].name ]
       #        eBone.parent["prop_id"] = bone.parentId
       #        eBone.parent["prop_childCount"] += 1
       #    for pBone in eBone.parent_recursive:
       #        parentBone = self.bones[pBone["prop_id"]]
       #        eBone.matrix = Euler(bone.rot[0:3]).to_matrix().to_4x4() @ Matrix.Translation(bone.pos[0:3])


       #for eBone in reversed(armature.data.edit_bones):   # fix orient
       #    for pBone in eBone.parent_recursive:
       #        if pBone["prop_childCount"] == 1 or \
       #            pBone.name + "_d" == eBone.name or \
       #            pBone.name + "_x" == eBone.name:
       #                pBone.tail = eBone.head.copy()
       #
       #bpy.ops.object.mode_set(mode="OBJECT")

        ## create meshes
        for obj in self.objs:
            mesh = bpy.data.meshes.new(obj.name)
            mesh.from_pydata(obj.verts, [], obj.faces)
            mesh.update()
            mesh.use_auto_smooth = True
            mesh.normals_split_custom_set_from_vertices(obj.normals)
            ob = bpy.data.objects.new(obj.name, mesh)
            bpy.context.scene.collection.objects.link(ob)
            bpy.context.view_layer.objects.active = ob
            ob.location = Vector((0, 0, 0))
            ob.parent = armature
            ob.hide_set(obj.vertCount == 0)

            bpy.ops.mesh.uv_texture_add()
            uvMap = mesh.uv_layers[0]
            for fIdx, poly in enumerate(mesh.polygons):
                for vNum, loopIdx in enumerate(poly.loop_indices):
                    vIdx = poly.vertices[vNum]
                    uvMap.data[loopIdx].uv = obj.uvs[vIdx]

            for boneId in obj.boneIds:
                ob.vertex_groups.new(name=self.bones[boneId].name)
            for i in range(obj.vertCount):
                for boneId, weight in obj.weights[i]:
                    ob.vertex_groups[self.bones[boneId].name].add([i], weight, "REPLACE")

            #bpy.ops.mesh.vertex_color_add()
            #colMap = mesh.vertex_colors[0]
            mesh.vertex_colors.new()
            colMap = mesh.vertex_colors.active
            for fIdx, poly in enumerate(mesh.polygons):
                for vNum, loopIdx in enumerate(poly.loop_indices):
                    vIdx = poly.vertices[vNum]
                    colMap.data[loopIdx].color = obj.colors[vIdx][0:4]
            
            # remember obj id
            ob["prop_id"] = obj.id
            # modifier
            bpy.ops.object.modifier_add(type="ARMATURE")
            ob.modifiers[-1].object = armature


    def modifyModel(self, outFilepath, logger):
        selected = set(getSelectedObjects())
        selectedObjects = [ob for ob in bpy.context.scene.objects if ob in selected or ob.parent in selected]
        if len(selectedObjects) == 0:
            return

        self.inFile.seek(0)
        data = bytearray(self.inFile.read())
        for ob in selectedObjects:
            logger({"INFO"}, "processing " + ob.name)
            if "prop_id" not in ob:
                logger({"INFO"}, "skipping " + ob.name)
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
                if ob.hide_get() == False:
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
                if ob.hide_get() == False:
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
    filepath : bpy.props.StringProperty(subtype="FILE_PATH")
    filename : bpy.props.StringProperty(subtype="FILE_NAME")

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
            yobj.importModel(self.filename, self.report)
            bpy.ops.object.select_all(action="DESELECT")
            self.report({'INFO'}, "finished")
        return {'FINISHED'}

####### RRXXOpsExport
class RRXXOpsExport(bpy.types.Operator):
    bl_idname = "export.rrxx"
    bl_label = "Export RRXX Model"
    filepath : bpy.props.StringProperty(subtype="FILE_PATH")
    filename : bpy.props.StringProperty(subtype="FILE_NAME")

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
            yobj.modifyModel(outFilepath, self.report)
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
            ob.select_set(True)
        return {'FINISHED'}

####### RRXXPanel
class RRXXPanel(bpy.types.Panel):
    bl_label = "RRXX Tools"
    bl_idname = "VIEW3D_PT_rrxx"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"

    def draw(self, context):
        l = self.layout.box()
        l.row().label(text="1. Import *.yobj or *.ymxen file.")
        l.row().operator("import.rrxx")
        l.row().label(text="2. Edit vertex position/UV/normal/weight/color.")
        l.row().label(text="3. Select Armature and child objects.")
        l.row().operator("object.rrxx_select_children")
        l.row().label(text="4. Export.")
        l.row().label(text="Select original file and you will get new file in MOD dir.")
        l.row().operator("export.rrxx")


####### getSelectedObjects
def getSelectedObjects():
    return [ob for ob in bpy.context.scene.objects if ob.select_get() == True]

######################## register

register_classes = (
    RRXXPanel,
    RRXXOpsImport,
    RRXXOpsExport,
    RRXXOpsSelectChildren
)

def register():
    for cls in register_classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in register_classes:
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
