__author__ = 'akeshavan'
import pandas as pd
import nibabel as nib
from pbr.config import config as cc
from os.path import join, exists, split
import nipype.pipeline.engine as pe
from nipype.interfaces.slicer import SimpleRegionGrowingSegmentation
import nipype.interfaces.utility as niu
import nipype.interfaces.fsl as fsl
import nipype.interfaces.ants as ants
import nipype.interfaces.io as nio
import itertools

def getSRGS(inputv, seeds, multiplier=1.0,
            nbhd = 1, iterations=5, timestep = 0.0625,
            smoothingiterations=5):
    import os
    from subprocess import check_call
    from nipype.utils.filemanip import fname_presuffix
    outputv = fname_presuffix(inputv, newpath=os.path.abspath("."), suffix="_{}_{}_{}_{}_{}".format(multiplier,
                                                                                                   nbhd, iterations,
                                                                                                   timestep,
                                                                                                    smoothingiterations))
    cmd = ["SimpleRegionGrowingSegmentation", inputv,
           outputv, "--multiplier", str(multiplier),
          "--neighborhood", str(nbhd),
          "--iterations", str(iterations),
          "--timestep", str(timestep),
          "--smoothingIterations", str(smoothingiterations)]
    cmd += ["--seed", "{},{},{}".format(*seeds)]
    check_call(cmd)
    return outputv


def combine_stats(out_stats, parameters):
    import pandas as pd
    import os
    #df1 = pd.read_csv(parameters)
    df2 = pd.DataFrame(out_stats)
    print(df2)
    df = pd.merge(parameters,df2, left_index=True, right_index=True)
    #df["filenames"] = out_files
    outfile = os.path.abspath("stats.csv")
    df.to_csv(outfile)
    return outfile


def get_workflow(parameters,name=0):
    wf = pe.Workflow(name="%04d"%name+"regionGrowing")
    wf.base_dir = "/scratch/henry_temp/keshavan/region_growing_test"
    n = pe.Node(niu.Function(input_names=["inputv", "seeds", "multiplier",
                "nbhd", "iterations", "timestep",
                "smoothingiterations"], output_names=["outfile"],
                            function=getSRGS),
               name="srgs")
    inputspec = pe.Node(niu.IdentityInterface(fields=["seeds", "in_file"]), name="inputspec")
    n.iterables = [(q, parameters[q].tolist()) for q in ["multiplier",
                "nbhd", "iterations", "timestep",
                "smoothingiterations"]]
    n.synchronize = True
    wf.connect(inputspec, "seeds", n, "seeds")
    wf.connect(inputspec, "in_file", n, "inputv")

    dt = pe.Node(fsl.ChangeDataType(output_datatype="short"), name="changedt")
    wf.connect(n,"outfile", dt, "in_file")

    stats = pe.Node(fsl.ImageStats(op_string="-c -w"), name="stats")
    wf.connect(dt, "out_file", stats, "in_file")

    avg = pe.JoinNode(ants.AverageImages(dimension=3, normalize=False),
                      name="average",
                     joinsource="srgs",
                     joinfield=["images"])
    wf.connect(dt, "out_file", avg, "images")

    st = pe.JoinNode(niu.Function(input_names=["out_stats", "parameters"],
                              output_names=["outfile"],
                              function=combine_stats),
                 name="combiner",
                     joinsource="srgs",
                     joinfield=["out_stats"])
    #wf.connect(dt, "out_file", st, "out_files")
    wf.connect(stats, "out_stat", st, "out_stats")
    st.inputs.parameters = parameters

    outputspec = pe.Node(niu.IdentityInterface(fields=["avg_image", "stats"]), name="outputspec")
    wf.connect(avg, "output_average_image", outputspec, "avg_image")
    wf.connect(st,"outfile", outputspec, "stats")
    return wf, inputspec, outputspec


df = pd.read_csv("/data/henry7/PBR/subjects/mse2441/mindcontrol/ms1244-mse2441-002-AX_T1_3D_IRSPGR/align/rois/ms1244-mse2441-002-AX_T1_3D_IRSPGR-veovibes.csv",
                index_col=0)

coords = [[row.x, row.y, row.z] for i, row in df.iterrows()]
input_file = "/data/henry7/PBR/subjects/mse2441/alignment/ms1244-mse2441-002-AX_T1_3D_IRSPGR.nii.gz"
output_file = "/data/henry7/PBR/subjects/mse2441/lesion_grow/ms1244-mse2441-002-AX_T1_3D_IRSPGR.nii.gz"


import numpy as np
multipliers =np.linspace(1,1.5,5)
iterators = [5]
nbhds = [1]
timestep = [0.0625]
smoothings = [5]

data = [q for q in itertools.product(multipliers, iterators, nbhds, timestep, smoothings)]
parameters = pd.DataFrame(data, columns = ["multiplier", "iterations", "nbhd", "timestep", "smoothingiterations"])
parameters.head()

#mwf = pe.Workflow(name="region_growing_meta")
#mwf.base_dir = "/scratch/henry_temp/keshavan/region_growing_test"
#merger = pe.Node(niu.Merge(len(coords)), name="merger")

#for i,c in enumerate(coords):
wf, inp, out = get_workflow(parameters)
inp.inputs.in_file = input_file
inp.iterables = ("seeds", coords)
#inp.inputs.seeds = c
#mwf.add_nodes([wf])
#mwf.connect(out, "avg_image", merger, "in%d"%i)



wf.run()
