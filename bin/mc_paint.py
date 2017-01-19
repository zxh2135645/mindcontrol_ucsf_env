__author__ = 'akeshavan'
import nibabel as nib
from os.path import join, exists, split
from dipy.tracking import utils
import numpy as np
from pbr.config import config as cc

def get_collection(port=3001):
    from pymongo import MongoClient
    client = MongoClient("localhost", port)
    db =  client.meteor
    collection = db.subjects
    return collection, client

def get_segmentation_mask(db, query):
    cursor = db.find(query)
    results = []
    for item in cursor:
        results.append(item)
    #print(len(results))
    assert(len(results) == 1)
    subject = results[0]

    return nib.load(join(cc["output_directory"],subject["check_masks"][1]))

def get_papaya_aff(img):
    vs = img.header.get_zooms()
    aff = img.affine
    ort = nib.orientations.io_orientation(aff)
    papaya_aff = np.zeros((4, 4))
    for i, line in enumerate(ort):
        papaya_aff[line[0],i] = vs[i]*line[1]
    papaya_aff[:, 3] = aff[:, 3]
    return papaya_aff

def convert_to_indices(streamline, papaya_aff, aff, img):
    #print(streamline)
    topoints = lambda x : np.array([[m["x"], m["y"], m["z"]] for m in x["world_coor"]])
    points_orig = topoints(streamline)
    points_nifti_space = list(utils.move_streamlines([points_orig], aff, input_space=papaya_aff))[0]
    from dipy.tracking._utils import _to_voxel_coordinates, _mapping_to_voxel
    lin_T, offset = _mapping_to_voxel(aff, None)
    idx = _to_voxel_coordinates(points_orig, lin_T, offset)
    return points_nifti_space, idx


# the actual paint function (put helper functions above where I convert to the right space?)
def get_points_to_paint(drawing, papaya_affine, aff, img): #, outfilepath, name, authors, suffix=""):
    import pandas as pd
    df = pd.DataFrame()
    data = img.get_data()
    for d in drawing:
        pv = d["paintValue"]
        if len(d["world_coor"]):
            points_nii_space, trans_points = convert_to_indices(d, papaya_affine, aff, img)
            tmp = []
            for i,ni in enumerate(trans_points):
                to_append = {"x": ni[0], "y":ni[1], "z": ni[2], "val": pv}

                #validate affine. For some reason matrix_coor and world_coor don't always have the same size.
                # TODO: Why?
                if len(d["world_coor"]) == len(d["matrix_coor"]):
                    old_val_client = d["matrix_coor"][i]["old_val"]
                    true_val = data[ni[0], ni[1], ni[2]]
                    assert(old_val_client==true_val)

                tmp.append(to_append)
            df = df.append(pd.DataFrame(tmp), ignore_index=True)
    df.drop_duplicates(inplace=True)

    return df


def create_paint_volume(mongo_port, query, outpath):
    coll, cli = get_collection(mongo_port)
    mask_img = get_segmentation_mask(coll,query)
    paff = get_papaya_aff(mask_img)
    aff = mask_img.affine

    try:
        p1 = get_points_to_paint(coll.find_one(query)["painters"], paff, aff, mask_img)
    except AssertionError:
        p1 = get_points_to_paint(coll.find_one(query)["painters"], aff, aff, mask_img)

    data = mask_img.get_data()
    for idx, row in p1.iterrows():
        paint_value = row['val']
        x,y,z = row['x'], row['y'], row['z']
        data[x][y][z] = paint_value

    painted_image = nib.nifti1.Nifti1Image(data,aff,mask_img.header)
    painted_image.to_filename(outpath)
    return outpath