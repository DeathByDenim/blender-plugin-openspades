bl_info = {
    "name": "OpenSpades map making",
    "author": "Jarno van der Kolk",
    "blender": (3, 0, 0),
    "version": (1, 0, 0),
    "category": "Import-Export",
    "description": "Export to OpenSpades vxl maps",
    "location": "File > Import-Export"
}
import bpy
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, FloatProperty, EnumProperty
import bmesh
import math
from mathutils import Matrix, Vector
import numpy as np
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())


def menu_func(self, context):
    self.layout.operator(OpenSpadesExportToVXL.bl_idname, text="OpenSpades VXL (.vxl)")

def register():
    bpy.utils.register_class(OpenSpadesExportToVXL)
    bpy.types.TOPBAR_MT_file_export.append(menu_func)

def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func)
    bpy.utils.unregister_class(OpenSpadesExportToVXL)

def voxelize(context):
    # Based on https://www.youtube.com/watch?v=l9wSDtqThmQ
    source = context.active_object.data
    bpy.ops.object.duplicate()

    target = context.active_object.data
    


class OpenSpadesExportToVXL(bpy.types.Operator, ExportHelper):
    """Selection to VXL"""
    bl_idname = "export_scene.vxl"
    bl_label = "Export OpenSpades VXL"
    bl_options = {"PRESET"}

    VXL_WIDTH = 512
    VXL_LENGTH = 512
    VXL_HEIGHT = 64
    COLOUR_RED = 2
    COLOUR_GREEN = 1
    COLOUR_BLUE = 0
    COLOUR_ALPHA = 3

    filename_ext = ".vxl"
    filter_glob : StringProperty(default='*'+filename_ext, options={"HIDDEN"})

    # https://github.com/droghio/Blender-Voxel-Export
    def execute(self, context):
        if not self.filepath:
            raise Exception("Filepath is not set")

        self.save(context)

        return {"FINISHED"}

    # def column_match(self, face, x, y, zmax, obj):
    #     """Check if this face is at (x,y) and below zmax"""
    #     centre = obj.matrix_world @ face.calc_center_median()
    #     if math.fabs(centre[0] - x) >= 0.0001:
    #         return False
    #     if math.fabs(centre[1] - y) >= 0.0001:
    #         return False
    #     # if centre[2] > zmax:
    #     #     return False
    #     return True

    def column_match(self, face, x, y):
        """Check if this face is at (x,y)"""
        if face[0] != x:
            return False
        if face[1] != y:
            return False
        return True

    def is_surface(self, x, y, z):
        return True

    def save(self, context):
        # Get the mesh for the currently selected object
        obj = context.active_object
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        print(f"bm.faces: {len(bm.faces)}")

        # Find the faces pointing up and down
        upfaces = [f for f in bm.faces if f.normal @ Vector([0,0,1]) > 0.999]
        downfaces = [f for f in bm.faces if f.normal @ Vector([0,0,-1]) > 0.999]
        print(f"upfaces:   {len(upfaces)}")
        print(f"downfaces: {len(downfaces)}")
        
        if len(upfaces) == 0 or len(downfaces) == 0:
            raise Exception("Faces are not aligned. Did you forget to apply Remesh?")

        # After remesh, every face should be square and the same size, so the
        # resolution can be grabbed from any edge
        edges = [e for e in upfaces[0].edges]
        resolution = edges[0].calc_length()
        print(f"resolution: {resolution}")
        if math.fabs(edges[1].calc_length() - resolution) > 0.001:
            raise Exception("Faces are not square. Did you forget to apply Remesh?")
        

        # Get the bounding box in world coordinates
        world_bound_box0 = obj.matrix_world @ Vector(obj.bound_box[0])
        world_bound_box6 = obj.matrix_world @ Vector(obj.bound_box[6])
        bbox_x_min = min([world_bound_box0[0], world_bound_box6[0]])
        bbox_x_max = max([world_bound_box0[0], world_bound_box6[0]])
        bbox_y_min = min([world_bound_box0[1], world_bound_box6[1]])
        bbox_y_max = max([world_bound_box0[1], world_bound_box6[1]])
        bbox_z_min = min([world_bound_box0[2], world_bound_box6[2]])
        bbox_z_max = max([world_bound_box0[2], world_bound_box6[2]])

        # Selected object is assumed to be the centre of the map. It's also assumed
        # that the bottom of the object is the ground
        xmin = obj.location[0] - self.VXL_WIDTH * resolution / 2.
        ymin = obj.location[1] - self.VXL_LENGTH * resolution / 2.
        zmin = bbox_z_min
        zmax = zmin + resolution * self.VXL_HEIGHT
        print(f"xmin: {xmin}")
        print(f"ymin: {ymin}")
        print(f"zmin: {zmin}")
        print(f"zmax: {zmax}")

        print("Dimensions: ")
        print(round((bbox_x_max - bbox_x_min) / resolution))
        print(round((bbox_y_max - bbox_y_min) / resolution))

        # Convert to VXL coordinates
        conversionnmatrix = Matrix.Scale(1/resolution, 4) @ Matrix.Translation([0, 0, -bbox_z_min]) @ obj.matrix_world

        upfaces = [conversionnmatrix @ f.calc_center_median() for f in upfaces]
        downfaces = [conversionnmatrix @ f.calc_center_median() for f in downfaces]
        
        minx = upfaces[0][0]
        miny = upfaces[0][1]
        maxx = upfaces[0][0]
        maxy = upfaces[0][1]
        for u in upfaces:
            minx = min(minx, u[0])
            miny = min(miny, u[1])
            maxx = max(maxx, u[0])
            maxy = max(maxy, u[1])
        print(f"minx : {minx}")
        print(f"maxx : {maxx}")
        print(f"miny : {miny}")
        print(f"maxy : {maxy}")

        upfaces = [Matrix.Translation([-(maxx + minx) / 2 + self.VXL_WIDTH / 2, -(maxy + miny) / 2 + self.VXL_LENGTH / 2, 0]) @ f for f in upfaces]
        downfaces = [Matrix.Translation([-(maxx + minx) / 2 + self.VXL_WIDTH / 2, -(maxy + miny) / 2 + self.VXL_LENGTH / 2, 0]) @ f for f in downfaces]

        # Correct for off by 0.5 due to odd and even dimensions and such and round to integer values
        offbyhalfx = round(2 * upfaces[0][0]) % 2
        offbyhalfy = round(2 * upfaces[0][0]) % 2
        upfaces = [Matrix.Translation([offbyhalfx * 0.5, offbyhalfy * 0.5, 0]) @ f for f in upfaces]
        upfaces = [[round(f[0]), round(f[1]), round(f[2])] for f in upfaces]
        downfaces = [Matrix.Translation([offbyhalfx * 0.5, offbyhalfy * 0.5, 0]) @ f for f in downfaces]
        downfaces = [[round(f[0]), round(f[1]), round(f[2])] for f in downfaces]

        # Recalculate the min and max after all these shifts
        minx = upfaces[0][0]
        miny = upfaces[0][1]
        maxx = upfaces[0][0]
        maxy = upfaces[0][1]
        for u in upfaces:
            minx = min(minx, u[0])
            miny = min(miny, u[1])
            maxx = max(maxx, u[0])
            maxy = max(maxy, u[1])
        print(f"minx : {minx}")
        print(f"maxx : {maxx}")
        print(f"miny : {miny}")
        print(f"maxy : {maxy}")

        with open(self.filepath, 'wb') as outfile:
            context.window_manager.progress_begin(0, 100)
            # for iy in range(self.VXL_LENGTH//2, self.VXL_LENGTH//2+1):
            #     context.window_manager.progress_update(iy / self.VXL_LENGTH)
            #     for ix in range(self.VXL_WIDTH//2, self.VXL_WIDTH//2+1):
            for iy in range(self.VXL_LENGTH):
                context.window_manager.progress_update(iy / self.VXL_LENGTH)
                for ix in range(self.VXL_WIDTH):

                    # Skip the stuff outside of the bounding box
                    if ix < minx or ix > maxx or iy < miny or iy > maxy:
                        np.array(0, dtype=np.int8).tofile(outfile)
                        np.array(self.VXL_HEIGHT-1, dtype=np.int8).tofile(outfile)
                        np.array(self.VXL_HEIGHT-1, dtype=np.int8).tofile(outfile)
                        np.array(0, dtype=np.int8).tofile(outfile)
                        np.array([255,0,255,255], dtype=np.int8).tofile(outfile)
                        continue


                    # Find the faces that are in this particular column at (ix, iy)
                    localupfaces = [f for f in upfaces if self.column_match(f, ix, iy)]
                    localupfaces.sort(key=lambda f: f[2], reverse=True)
                    localdownfaces = [f for f in downfaces if self.column_match(f, ix, iy)]
                    localdownfaces.sort(key=lambda f: f[2], reverse=True)
                    if len(localupfaces) > 0:
                        print(f"len(localupfaces) :{len(localupfaces)}")
                    if len(localdownfaces) > 0:
                        print(f"len(localdownfaces) :{len(localdownfaces)}")

                    if len(localupfaces) == 0 or len(localupfaces) != len(localdownfaces):
                        np.array(0, dtype=np.int8).tofile(outfile)
                        np.array(self.VXL_HEIGHT-1, dtype=np.int8).tofile(outfile)
                        np.array(self.VXL_HEIGHT-1, dtype=np.int8).tofile(outfile)
                        np.array(0, dtype=np.int8).tofile(outfile)
                        np.array([255,0,0,255], dtype=np.int8).tofile(outfile)
                        continue
                    
                    doprint = True
                    if len(localdownfaces) <= 1:
                        doprint = False

                    if doprint:
                        print(f"(ix, iy) = ({ix}, {iy})")

                    air_start = 0
                    while len(localupfaces) > 0:
                        localupface = localupfaces.pop(0)
                        
                        # upface is the top of a voxel. In VXL coordinates, 0 is
                        # top, but in Blender, 0 is bottom.
                        iz = self.VXL_HEIGHT - localupface[2]

                        top_colors_start = iz
                        if doprint:
                            print(f"top_colors_start {top_colors_start}")

                        iz = self.VXL_HEIGHT
                        while len(localdownfaces) > 0:
                            if doprint:
                                print("Checking down face")
                            localdownface = localdownfaces.pop(0)
                            zdown = localdownface[2]
                            # if zdown > z or zdown < zmin:
                            #     print(f"zdown: {zdown}")
                            #     print(f"z: {z}")
                            #     raise Exception("Reject")
                            #     if doprint:
                            #         print("Rejected")
                            #     continue
                            # z = zdown
                            iz = self.VXL_HEIGHT - zdown
                            break

                        top_colors_end = iz
                        if doprint:
                            print(f"top_colors_end {top_colors_end}")
                        top_colors_len = top_colors_end - top_colors_start
                        if doprint:
                            print(f"top_colors_len {top_colors_len}")
                        
                        bottom_colors_start = iz
                        bottom_colors_end = iz

                        top_colors_len = top_colors_end - top_colors_start
                        bottom_colors_len = bottom_colors_end - bottom_colors_start

                        colors = top_colors_len + bottom_colors_len

                        if iz == self.VXL_HEIGHT:
                            np.array(0, dtype=np.int8).tofile(outfile)
                        else:
                            np.array(colors + 1, dtype=np.int8).tofile(outfile)
                        np.array(top_colors_start, dtype=np.int8).tofile(outfile)
                        np.array(top_colors_end - 1, dtype=np.int8).tofile(outfile)
                        np.array(air_start, dtype=np.int8).tofile(outfile)
                        np.array([0,255,0,255] * top_colors_len, dtype=np.int8).tofile(outfile)

                        air_start = iz
                    if iz != self.VXL_HEIGHT:
                        np.array(0, dtype=np.int8).tofile(outfile)
                        np.array(self.VXL_HEIGHT-1, dtype=np.int8).tofile(outfile)
                        np.array(self.VXL_HEIGHT-1, dtype=np.int8).tofile(outfile)
                        np.array(air_start, dtype=np.int8).tofile(outfile)
                        np.array([0,255,255,255], dtype=np.int8).tofile(outfile)
                        
                    if doprint:
                        print()

            context.window_manager.progress_end()



# This allows you to run the script directly from blenders text editor
# to test the addon without having to install it.
if __name__ == "__main__":
    register()
