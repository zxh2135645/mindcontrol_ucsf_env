#!/usr/bin/env python
__author__ = 'akeshavan'
import argparse
from os.path import join, split, exists, relpath, abspath
from pbr.config import config as cc
import os
from nipype.utils.filemanip import load_json, fname_presuffix

def get_collection(port=3001):
    from pymongo import MongoClient
    client = MongoClient("localhost", port)
    db =  client.meteor
    collection = db.subjects
    return collection, client

def run_dura_edit(entry_finder, in_file, meteor_port):
    import nibabel as nib
    import numpy as np
    from scipy.ndimage import label
    import pandas as pd
    print("meteor port is", meteor_port)
    coll, cli = get_collection(meteor_port+1)
    entry = coll.find_one(entry_finder)
    if entry is not None:

        brain_mask = join(cc["output_directory"], entry["check_masks"][1])
        imgb = nib.load(brain_mask)
        datab, affb = imgb.get_data(), imgb.get_affine()

        maskimg = nib.load(in_file)
        mdata = maskimg.get_data()
        null_coords = np.nonzero(datab[mdata==1])
        print("removing", null_coords[0].shape[0], "voxels in the first pass, out of",
              mdata.sum())
        print("now removing floating chunks")

        ndatab = datab.copy()
        ndatab[mdata==1] = 0
        labelimg, nlabels = label(ndatab)
        sizes = np.bincount(labelimg.ravel())[1:]
        ndatab[labelimg!=1] = 0
        print("removing", len(sizes)-1, "chunks")
        print("original brain size is", datab.sum(), "final brain size is", ndatab.sum())
        print("removed", 100-(float(ndatab.sum())/datab.sum())*100, "%s")
        final_brain_mask = fname_presuffix(in_file, suffix="_edited")
        nib.Nifti1Image(ndatab, affb).to_filename(final_brain_mask)
        print("wrote brain mask", final_brain_mask)

        datab[ndatab==1] = 0
        coords = np.nonzero(datab)
        df = pd.DataFrame(data=np.asarray(list(coords)).T, columns=["x", "y", "z"])
        coords_fname = abspath(in_file).replace(".nii.gz", ".csv")
        df.to_csv(coords_fname)
        print("wrote removed coordinates as", coords_fname)

    else:
        raise Exception("can't find a valid entry in the db")


def get_info_from_path(in_file):
    rpath = relpath(in_file, cc["output_directory"])
    try:
        subid, mc_folder, seq_name, wf_name, roi_folder, nifti_name = rpath.split("/")
    except:
        print("path does not point to a valid mindcontrol output")

    if mc_folder != "mindcontrol":
        raise Exception("This is not a mindcontrol folder")
    if roi_folder != "rois":
        raise Exception("this is not a mindcontrol folder")

    entry_finder = {"subject_id": subid, "entry_type": wf_name, "name": seq_name}
    print("entry finder is", entry_finder)
    return entry_finder


edit_type_dict = {"dura": run_dura_edit}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--in_file', dest="in_file")
    parser.add_argument("-z", "--edit_type", dest="edit_type")
    parser.add_argument('-e', '--env', dest="env")
    config = load_json(os.path.join(os.path.split(__file__)[0], "config.json"))

    args = parser.parse_args()

    if args.env in ["development", "production"]:
        env = args.env
        meteor_port = config[env]["meteor_port"]
        if args.edit_type in edit_type_dict.keys():
            entry_finder = get_info_from_path(args.in_file)
            edit_type_dict[args.edit_type](entry_finder, args.in_file, meteor_port)
        else:
            raise Exception("edit type must be in", " ".join(edit_type_dict.keys()))

