#!/usr/bin/env python
__author__ = 'akeshavan'
import pandas as pd
import nibabel as nib
import numpy as np
from dipy.tracking import utils
import os
from scipy.ndimage import label
import sys
from glob import glob
from copy import deepcopy

def correct_lesions(in_csv, lesion_file, ratio_file, ants_seg):
    df = pd.read_csv(in_csv)

    img = nib.load(lesion_file)
    data, aff = img.get_data(), img.get_affine()

    fp = df[df.annotation=="FP"][["x", "y", "z"]].values
    to_indices = np.round(np.asarray(list(utils.move_streamlines(fp.tolist(), np.linalg.inv(aff))))).astype(int)

    for idx in to_indices:
        val = data[idx[0],idx[1], idx[2]]
        if val:
            data[data==val] = 0
        else:
            searchR = 1

            for i in range(3):
                new_idx = deepcopy(idx)
                new_idx[i] += searchR
                print("trying", new_idx)
                val = data[new_idx[0],new_idx[1], new_idx[2]]
                if val != 0:
                    break
                new_idx = deepcopy(idx)
                new_idx[i] -= searchR
                val = data[new_idx[0],new_idx[1], new_idx[2]]
                if val != 0:
                    break
            if val == 0:
                print("ERROR, no lesion here!!!", idx) #TODO: draw a 1 vox box around this coordinate and look for val
            else:
                print("FOUND VALS AROUND POINT", new_idx)
                data[data==val] = 0

    out_path = os.path.join(os.path.split(os.path.split(in_csv)[0])[0], "lst_edits")
    if not os.path.exists(out_path):
        os.makedirs(out_path)
    out_file = os.path.join(out_path, "no_FP_"+lesion_file.split("/")[-1])
    nib.Nifti1Image(data,aff).to_filename(out_file)
    print(out_file, "written")

    ratio_img = nib.load(ratio_file)
    ratio, raffine = ratio_img.get_data(), ratio_img.affine

    rvals = ratio[data > 0]
    new_thr = np.mean(rvals) - np.std(rvals)
    print("new_threshold is", new_thr)

    def get_indices(coords, aff):
        return np.round(np.asarray(list(utils.move_streamlines(coords.tolist(),
                        np.linalg.inv(aff))))).astype(int)


    def chopper(in_file, ratio_file):
        import tempfile
        from subprocess import check_call
        out_file = tempfile.mktemp(suffix=".nii.gz")
        cmd = "mri_convert -i {} -o {} --like {}".format(in_file, out_file, ratio_file)
        check_call(cmd.split(" "))
        return out_file

    ants_chopped = chopper(ants_seg, ratio_file) #gets shit to alignment space
    ants_img = nib.load(ants_chopped)
    ants_data = ants_img.get_data()
    wm_mask = ants_data == 3

    ratio[wm_mask ==0] = 0
    wm_only = ratio > new_thr
    label_img, nlabels = label(wm_only)
    nib.Nifti1Image(label_img, aff).to_filename("label_img.nii.gz")
    fn = df[df.annotation=="FN"][["x", "y", "z"]].values
    to_indices = np.round(np.asarray(list(utils.move_streamlines(fn.tolist(), np.linalg.inv(aff))))).astype(int)

    maxval = data.max()
    for i, idx in enumerate(to_indices):
        val = label_img[idx[0], idx[1], idx[2]]
        if val > 1:
            vol_idx = np.nonzero(label_img == val)
            print(vol_idx[0].shape)
            data[vol_idx] = maxval + i
        else:
            print("missed", idx, "because val is", val)

    out_file = os.path.join(out_path, "no_FP_filled_FN_"+lesion_file.split("/")[-1])
    nib.Nifti1Image(data,aff).to_filename(out_file)
    print(out_file, "written")
    return out_file

if __name__ == "__main__":

    if len(sys.argv) < 1:
        raise Exception("USAGE: edit_lst.py /path/to/csv/file/from/mc_roi")

    in_csv = sys.argv[1]

    name = "-".join(in_csv.split("/")[-1].split("-")[:-1])
    mse = name.split("-")[1]

    lesion_file = "/data/henry7/PBR/subjects/{}/lst/lpa/" \
              "ples_lpa_m{}_index.nii.gz".format(mse, name)
    assert(os.path.exists(lesion_file))

    ratio_file = glob("/data/henry7/PBR/subjects/{}/ratio//" \
             "{}-{}-*-{}*.nii.gz".format(mse, name.split("-")[0],
                                     name.split("-")[1], name.split("-")[-1]))
    assert(len(ratio_file) == 1)
    ratio_file = ratio_file[0]

    ants_seg = glob("/data/henry7/PBR/subjects/{}/antsCT/" \
           "*/BrainSegmentation.nii.gz".format(mse))
    assert(len(ants_seg))
    ants_seg = ants_seg[-1]

    correct_lesions(in_csv, lesion_file, ratio_file, ants_seg)


