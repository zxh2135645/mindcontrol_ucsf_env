#!/usr/bin/env python
__author__ = 'akeshavan'

import numpy as np
from dipy.tracking import utils
from scipy.ndimage import label
import sys
from copy import deepcopy
from nipype.utils.filemanip import save_json, fname_presuffix
import pandas as pd
from glob import glob
import os
import nibabel as nib
import sys
sys.path.append(os.path.split(__file__)[0])

def report_stats(report):
    num_success = len([r for r in report["FP"] if r["caught"]])
    print("Number of False Positives Removed", num_success, "/", len(report["FP"]))
    stats = {"FP_removed": num_success}
    #print("Ratio Threshold was", report["ratio_threshold"])
    #stats["ratio_threshold"] = report["ratio_threshold"]
    num_success = len([r for r in report["FN"] if r["caught"]])
    stats["FN_caught"] = num_success
    print("Number of False Negatives Detected", num_success, "/", len(report["FN"]))
    error_size = [r["CM_err"] for r in report["FN"] if r["caught"]]
    if len(error_size):
        print("Average CM Error:", np.sqrt(np.mean(error_size)))
        print("Min CM Error", np.sqrt(np.min(error_size)))
        print("Max CM Error", np.sqrt(np.max(error_size)))
        stats["FN_Average_Error"] = np.sqrt(np.mean(error_size))
        stats["FN_Min_Error"] = np.sqrt(np.min(error_size))
        stats["FN_Max_Error"] = np.sqrt(np.max(error_size))
    return stats

def detect_FP(df, data, aff, report):
    fp = df[df.annotation=="FP"][["x", "y", "z"]].values
    to_indices = np.round(np.asarray(list(utils.move_streamlines(fp.tolist(), np.linalg.inv(aff))))).astype(int)

    for j,idx in enumerate(to_indices):
        entry = {}
        val = data[idx[0],idx[1], idx[2]]
        entry["world"] = fp.tolist()[j]
        entry["ijk"] = idx.tolist()
        entry["caught"] = False
        if val:
            entry["caught"] = True
            entry["size"] = float(np.sum(data==val))
            data[data==val] = 0

        else:
            searchR = 1

            for i in range(3):
                new_idx = deepcopy(idx)
                new_idx[i] += searchR
                #print("trying", new_idx)
                val = data[new_idx[0],new_idx[1], new_idx[2]]
                if val != 0:
                    break
                new_idx = deepcopy(idx)
                new_idx[i] -= searchR
                val = data[new_idx[0],new_idx[1], new_idx[2]]
                if val != 0:
                    break
            if val == 0:
                #print("ERROR, no lesion here!!!", idx) #TODO: draw a 2 vox box around this coordinate and look for val
                pass
            else:
                #print("FOUND VALS AROUND POINT", new_idx)
                entry["ijk"] = new_idx.tolist()
                entry["caught"] = True
                entry["size"] = float(np.sum(data==val))
                data[data==val] = 0
        report["FP"].append(entry)
    return report, data

def find_FN(ratio, indices, fn, dist_radius=5):
    entries = []
    false_neg_mask = np.zeros(ratio.shape)
    for idx, ijk in enumerate(indices):
        entry = {}
        entry["world"] = fn.tolist()[idx]
        entry["ijk"] = ijk.tolist()
        entry["caught"] = False
        i,j,k = ijk
        r = dist_radius
        sq = ratio[i-r:i+r, j-r:j+r, k-r:k+r]
        m, s, val = np.mean(sq), np.std(sq), ratio[i,j,k]

        #the thresholded ratio image is 0 here. User has clicked CSF.
        if not val:
            entry["errType"] = "click not in mask"

        else:
            stddev_steps = np.linspace(0.5,(val-m)/s, 20)
            thrs = [m+t*s for t in stddev_steps]
            entry["errType"] = "no peaks near click"
            for threshold in thrs:
                label_img, nlabels = label(ratio >= threshold)
                label_idx = label_img[i,j,k]
                mask = label_img==label_idx
                indices = np.nonzero(mask)
                cm = np.asarray([np.mean(z) for z in indices])
                cmErr = np.linalg.norm(cm - np.asarray(ijk))
                count = np.sum(mask)

                #Center of mass should be close to clicked point and the blob shouldn't be too big
                if count < 1000 and cmErr < 3:
                    entry["caught"] = True
                    entry["size"] = float(count)
                    entry["CM"] = cm.tolist()
                    entry["CM_err"] = float(cmErr)
                    entry["local_threshold"] = threshold
                    entry["errType"] = ""
                    false_neg_mask[indices] = 1

                    break
        entries.append(entry)
    return entries, false_neg_mask

def correct_lesions(in_csv, lesion_file, ratio_file, ants_seg, dist_radius=5):

    # Initialize report, load csv data and lesion seg data
    report = dict(FP=[], FN=[], base_csv=in_csv,
                  ratio_file=ratio_file, dist_radius=dist_radius)
    df = pd.read_csv(in_csv)
    img = nib.load(lesion_file)
    data, aff = img.get_data(), img.affine
    report["orig_lesion_volume"] = fslstats(lesion_file)
    report["orig_num_lesions"] = num_lesions(data)
    # detect false positives and return if none are detected
    # probably a coordinate system error, or clicks are bad
    report, data = detect_FP(df, data, aff, report)
    num_success = len([r for r in report["FP"] if r["caught"]])
    # coordinate system error ??
    if len(report["FP"]) and not num_success:
        return None, None, None

    # Write the lesion file w/ the false positives removed.
    out_path = os.path.join(os.path.split(os.path.split(in_csv)[0])[0], "lst_edits")
    if not os.path.exists(out_path):
        os.makedirs(out_path)
    out_file = os.path.join(out_path, "no_FP_"+lesion_file.split("/")[-1])
    nib.Nifti1Image(data,aff).to_filename(out_file)

    # Load the ratio image
    ratio_img = nib.load(ratio_file)
    ratio, raffine = ratio_img.get_data(), ratio_img.affine

    # Get the tissue segmentation in the same space as the ratio file
    # Mask to exclude CSF
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
    wm_mask = ants_data >= 2 #exclude CSF
    ratio[wm_mask ==0] = 0

    # Prepare false negatives and find them
    fn = df[df.annotation=="FN"][["x", "y", "z"]].values
    to_indices = np.round(np.asarray(list(utils.move_streamlines(fn.tolist(), np.linalg.inv(aff))))).astype(int)
    entries, fn_image = find_FN(ratio, to_indices, fn, dist_radius)
    print(ratio.shape, data.shape)
    report["FN"] += entries
    data = data + fn_image #add the found false neggies to data

    # Score the false negatives, reject if less than 40% are found
    report_file = fname_presuffix(in_csv, prefix="report_dr{}_".format(dist_radius),
                                  newpath=out_path,
                                  use_ext=False,
                                  suffix="_{}.json".format(os.path.split(ratio_file)[-1])) #long name for prov.
    stats = report_stats(report)
    num_success = len([r for r in report["FN"] if r["caught"]])
    total = len(report["FN"])
    if float(total) > 0:
        print("success score", num_success/float(total) )
        if num_success/float(total) < 0.4:
            print("notgood enough")
            return None, None, None

    # Write the final image, save the report
    out_file = os.path.join(out_path, "no_FP_filled_FN_dr{}_".format(dist_radius)+ratio_file.split("/")[-1])
    nib.Nifti1Image(data, aff).to_filename(out_file)

    report["final_lesion_vol"] = fslstats(out_file)
    report["final_lesion_count"] = num_lesions(data)
    save_json(report_file, report)
    print("\n\n\n","OUTPUT:", out_file,"\n\n\n")
    return out_file, report, stats

def num_lesions(data):
    img, nlabels = label(data>0)
    counts = np.bincount(img.ravel())
    return len(counts[counts > 3])

def fslstats(input_file):
    from subprocess import Popen, PIPE
    res = Popen(["fslstats", input_file,
            "-V"], stdout=PIPE)
    res.wait()
    return float(res.stdout.readlines()[0].split()[-1].decode("utf-8"))

def prep(in_csv, type_of_img="ratio"):
    parts = in_csv.split("/")[-1].split("-")
    if len(parts[4]) == 3:
        name = "-".join(parts[:5])
    else:
        name = "-".join(parts[:4])
    #print("name is", name)
    mse = name.split("-")[1]

    lesion_file = "/data/henry7/PBR/subjects/{}/lst/lpa/" \
              "ples_lpa_m{}_index.nii.gz".format(mse, name)
    assert os.path.exists(lesion_file), "lesion file does not exist {}".format(lesion_file)

    from mc_paint import create_paint_volume
    lesion_file_painted = create_paint_volume(5051,
                                              {"subject_id":mse, "entry_type": "lst", "name": name},
                                              os.path.join(os.path.split(in_csv)[0],
                                              "{}_painted.nii.gz".format(name)))

    ratio_file = glob("/data/henry7/PBR/subjects/{}/{}//" \
             "{}-{}-*-{}*.nii.gz".format(mse, type_of_img, name.split("-")[0],
                                     name.split("-")[1], name.split("-")[-1]))
    assert(len(ratio_file) == 1)
    ratio_file = ratio_file[0]

    ants_seg = glob("/data/henry7/PBR/subjects/{}/antsCT/" \
           "*/BrainSegmentation.nii.gz".format(mse))
    assert(len(ants_seg))
    ants_seg = ants_seg[-1]
    return in_csv, lesion_file_painted, ratio_file, ants_seg

def run_edits(mse, type_of_img = "ratio", dist_radius = 5):
    from mc_roi import get_all_seeds
    coord_system1 = "/data/henry7/PBR/subjects/{}/mindcontrol/*/lst/rois/*-{}.csv"
    coord_system2 = "/data/henry7/PBR/subjects/{}/mindcontrol/*/lst/rois/*-{}_origAff.csv"

    f1 = get_all_seeds(mse, 5050, ["lst"])
    for i,K in enumerate(f1):

        try:
            #f1 = [glob(K.format(mse,author)) for author in authors]

            print("\n\n",mse, "coord system {}".format(K), type_of_img, dist_radius)
            args1 = prep(K, type_of_img)
            reportfile, report1, stats1 = correct_lesions(*args1, dist_radius=dist_radius)
            if reportfile is not None:
                stats1["coord_system"] = i
                stats1["exam_id"] = mse
                return stats1, report1

        except IndexError:
            return


if __name__ == "__main__":

    if len(sys.argv) < 1:
        raise Exception("USAGE: edit_lst.py <list of mse>")

    mse = sys.argv[1:]
    file_types = ["alignment"]
    dist_radii = [2]
    for m in mse:
        try:
            [run_edits(m,type_of_img=f, dist_radius=dr) for f in file_types for dr in dist_radii]
        except Exception as e:
            print("\n\n\n\n", "SOMETHING WENT WRONG WITH", m,e, "\n\n\n\n")
