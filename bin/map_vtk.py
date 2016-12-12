#!/usr/bin/env python
__author__ = 'akeshavan'
import argparse
from march_cubes import read_vtk, write_vtk
from pbr.config import config as cc
from os.path import join, exists, split, abspath
from nipype.utils.filemanip import load_json
bd = cc["output_directory"]

def get_msid(input_nii):
    fname = split(input_nii)[1]
    return fname.split("-")[0]

def get_t1(mse):
    status = join(bd, mse, "nii", "status.json")
    assert(exists(status))
    info = load_json(status)
    return info["t1_files"]

def get_name(t1):
    return split(t1)[1].split(".nii.gz")[0]


def map_vtk(vtk_file, transforms, output_vtk, inversions = None):
    """
    inputs:
        vtk_file: string of file that exists
        transforms: list of files that exist from ANTS to use
        output_vtk: string

    outputs:
        output_vtk
    """

    import pandas as pd
    import numpy as np

    verts, faces = read_vtk(vtk_file)
    in_csv = vtk_file.replace(".vtk", "_map.csv")
    out_csv = output_vtk + ".csv"
    df = pd.DataFrame(verts, columns=["x","y","z"])
    df.y = df.y*-1
    df.x = df.x*-1
    df["t"] = 0
    df.to_csv(in_csv, index=None)
    #cmd = ["antsApplyTransformsToPoints", "-d", "3", "-i", in_csv,
    #        "-o", out_csv]
    #for q in transforms:
    #    cmd += ["-t", q]
    #check_call(cmd)
    from nipype.interfaces.ants import ApplyTransformsToPoints
    node= ApplyTransformsToPoints(dimension=3)
    node.inputs.input_file = in_csv
    if inversions:
        node.inputs.invert_transform_flags = inversions
    #node.inputs.output_file = out_csv
    node.inputs.transforms = transforms
    print(node.cmdline)
    res = node.run()
    out = pd.read_csv(res.outputs.output_file)
    out.y = -1 * out.y #LPS to LAS
    out.x = -1 * out.x
    write_vtk(out[["x","y","z"]].values, faces[:,1:], output_vtk)
    return output_vtk

def obj_to_csv(obj_file):
    from nipype.utils.filemanip import load_json, save_json, fname_presuffix
    import os
    import pandas as pd

    out_coords = fname_presuffix(obj_file, newpath = os.path.abspath("."), suffix="_coords", use_ext=False)+".csv"
    print("out coords", out_coords)
    foo = load_json(obj_file)
    data = foo["vertices"]
    df = pd.DataFrame(data,columns=["x","y","z"])
    df["t"] = 1
    df["y"] = df["y"]*-1
    df["x"] = df["x"]*-1
    df.to_csv(out_coords, index=None, header = None)
    return out_coords

def csv_to_obj(obj_file, csv_file):
    from nipype.utils.filemanip import load_json, save_json, fname_presuffix
    import os
    import pandas as pd

    out_obj = fname_presuffix(csv_file, newpath = os.path.abspath("."), suffix="_xfm", use_ext=False)+".json"
    foo = load_json(obj_file)
    df = pd.read_csv(csv_file)
    df["y"] = -1*df.y
    df["x"] = -1*df.x
    #print(df.shape)#.values[:,:,:,0].tolist()
    foo["vertices"] = df.values[:,:2].tolist()
    save_json(out_obj, foo)
    return out_obj


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--in_file", dest="in_file")
    parser.add_argument("-o", "--out_file", dest="out_file")
    parser.add_argument("-e", "--base_exam", dest="base_exam")
    parser.add_argument("-b", "--base_t1", dest="base_t1")
    parser.add_argument("-t", "--target_exam", dest="target_exam")
    parser.add_argument("-d", "--nonlinear", dest="use_nonlinear", default=False)

    args = parser.parse_args()
    print(args)
    assert(args.base_exam != None)
    t1_files = get_t1(args.base_exam)
    if len(t1_files)>1 and (args.base_t1 == None):
        raise Exception("need to specify base t1 since we found >1 t1 file")

    if args.base_t1:
        main_t1 = [t for t in t1_files if args.base_t1 in t][0]
    else:
        main_t1 = t1_files[0]

    print("located a base t1", main_t1)
    msid = get_msid(main_t1)
    print("msid is", msid)
    msid_status = join(bd, msid, "align", "status.json")
    assert(exists(msid_status))
    msid_status = load_json(msid_status)
    base_mse = msid_status["mse_order"][0]

    if args.target_exam == None:
        args.target_exam = base_mse

    target_t1 = get_t1(args.target_exam)[0]
    target_msid = get_msid(target_t1)
    assert(target_msid == msid)

    #find baseline mse from align_long workflow
    if base_mse == args.target_exam:
        print("mapping to baseline")
        affines = msid_status["affines"]
        aff = [a for a in affines if get_name(main_t1) in a]
        assert(len(aff)==1)
        print("found affine", aff[0])
        assert(args.in_file is not None)
        if args.out_file == None:
            from nipype.utils.filemanip import fname_presuffix
            args.out_file = fname_presuffix(args.in_file, newpath=abspath("."), suffix="_"+base_mse)
        if args.out_file.endswith(".vtk"):
            print("mapping vtk")
            map_vtk(args.in_file, aff, args.out_file,[False])
        elif args.out_file.endswith(".json"):
            print("mapping json")
            coords = obj_to_csv(args.in_file)
            from nipype.interfaces.ants import ApplyTransformsToPoints
            foo = ApplyTransformsToPoints(dimension=3)
            foo.inputs.input_file = coords
            foo.inputs.transforms = aff
            foo.inputs.invert_transform_flags = [False]
            print("running xfm", foo.cmdline)
            res = foo.run()
            out_csv = res.outputs.output_file
            csv_to_obj(args.in_file, out_csv)
        elif args.out_file.endswith(".nii.gz"):
            raise NotImplementedError

    else:
        raise NotImplementedError("AK hasn't implemented this yet.")
