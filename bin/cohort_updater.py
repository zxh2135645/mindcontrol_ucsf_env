#!/usr/bin/env python
import numpy as np
import pbr
import os
from nipype.utils.filemanip import load_json
from pbr.workflows.nifti_conversion.utils import description_renamer
heuristic = load_json(os.path.join(os.path.split(pbr.__file__)[0], "heuristic.json"))["filetype_mapper"]
import pandas as pd
from subprocess import Popen, PIPE
import pandas as pd
import argparse
from os.path import join

get_numerical_msid = lambda x: str(int(x[-4:]))

def get_diff(x):
    get_year = lambda x: int(x[:4])
    x["year"] = x.date.map(get_year)
    return x.year.max() - x.year.min()
    
def get_cohort(counts, min_number_tp, min_time_difference):
    cohort = counts.loc[counts.times[counts.times>=min_time_difference].index][counts.mse>=min_number_tp]
    return cohort

def get_cohort_counts(counts, min_number_tp, min_time_difference):
    cohort = counts.loc[counts.times[counts.times>=min_time_difference].index][counts.mse>=min_number_tp]
    return {"exams": cohort.sum().mse, "subjects": cohort.count().mse, 
            "min_num_tp": min_number_tp, "min_time_diff": min_time_difference}

def get_exams(df_final, msids):
    out_idx = np.in1d(df_final.msid.values, msids)
    return df_final[out_idx]

def reduce_df(df_final, to_drop):
    df_final1 = df_final.dropna()
    df_dropped = df_final1[np.in1d(df_final1.nii.values, to_drop) == False]
    print(df_final.shape, "reduced to",df_final1.shape, "reduced to", df_dropped.shape)
    return df_dropped

def get_all_mse(msid):
    cmd = ["ms_get_patient_imaging_exams", "--patient_id", get_numerical_msid(msid), "--dcm_dates"]
    proc = Popen(cmd, stdout=PIPE)
    lines = [l.decode("utf-8").split() for l in proc.stdout.readlines()[5:]]
    tmp = pd.DataFrame(lines, columns=["mse", "date"])
    tmp["mse"] = "mse"+tmp.mse
    tmp["msid"] = msid
    return tmp
    
def filter_files(descrip,nii_type, heuristic):
    output = []
    for i, desc in enumerate(descrip):
        if desc in list(heuristic.keys()):
            if heuristic[desc] == nii_type:
                 output.append(desc)
    return output
    
def get_modality(mse, nii_type="T1"):
    output = pd.DataFrame()
    num = mse.split("mse")[-1]
    cmd = ["ms_dcm_exam_info", "-t", num]
    proc = Popen(cmd, stdout=PIPE)
    lines = [description_renamer(" ".join(l.decode("utf-8").split()[1:-1])) for l in proc.stdout.readlines()[8:]]
    if nii_type:
        files = filter_files(lines, nii_type, heuristic)
        output["nii"] = files
    else:
        output["nii"] = lines
    output["mse"] = mse
    return output

def get_summary_counts(df):
    counts = df.groupby("msid").apply(lambda x: x.count()[["mse"]])
    counts["times"] = df.groupby("msid").apply(get_diff)
    return counts
    
def get_all_mses_and_dates(msids, modality="T1", to_ignore = [], do_modality_reduction=True):
    df_final = pd.DataFrame()
    for m in msids:
        mse = get_all_mse(m)
        tmp = pd.DataFrame()
        for ms in mse.mse:
            desc = get_modality(ms, modality)
            tmp = tmp.append(desc, ignore_index=True)
        foo = pd.merge(mse, tmp, left_on=["mse"], right_on=["mse"], how="outer")
        df_final = df_final.append(foo, ignore_index=True)
        print("msid", m, "complete")
    if do_modality_reduction:
        df = reduce_df(df_final, to_ignore)
    else:
        df = df_final
    return df
  
    
def get_pbr_list(cohort, filename):
    mse = list(set(cohort.mse))
    pd.DataFrame(mse).to_csv(filename, index=None, header=None)
    return filename


def get_collection(port=3001):
    from pymongo import MongoClient
    client = MongoClient("localhost", port)
    db =  client.meteor
    collection = db.subjects
    return collection, client

def update_demographics(cohort_df, study_tag, meteor_port):
    """This will just add dates and a study tag"""
    coll, _ = get_collection(meteor_port + 1)
    for i, row in cohort_df.iterrows():
        mse = row.mse
        finder = {"subject_id": mse, "entry_type": "demographic"}
        res = coll.find_one(finder)
        if res is None:
            finder["Study Tag"] = []
            coll.insert_one(finder)
            res = coll.find_one(finder)
        if not "Study Tag" in res.keys():
            res["Study Tag"] = []
        if not isinstance(res["Study Tag"], list):
            res["Study Tag"] = [res["Study Tag"]]
        if not study_tag in res["Study Tag"]:
            res["Study Tag"].append(study_tag)
        output = {"metrics":{"DCM_StudyDate": int(row.date)},
                  "Study Tag": res["Study Tag"],
                  "msid": row.msid}
        coll.update_one(finder, {"$set": output})
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-e', '--env', dest="env")
    parser.add_argument("-c",  nargs="+", dest="cohort_names")
    config = load_json(os.path.join(os.path.split(__file__)[0], "config.json"))
    #print(config)
    #parser.add_argument('-p',"--meteor_port", dest='meteor_port')
    #parser.add_argument("-s", "--static_port", dest="static_port")
    args = parser.parse_args()
    do_cohorts = args.cohort_names
    base_dir = os.path.split(__file__)[0]
    if args.env in ["development", "production"]:
        auto_cohort = load_json(os.path.join(os.path.split(__file__)[0], "auto_cohorts.json"))
        for cohort in auto_cohort:
            if do_cohorts is not None:
                if not cohort["name"] in do_cohorts:
                    print("skipping", cohort["name"])
                    continue
            msids = np.genfromtxt(cohort["msid_path"],dtype=str).tolist()
            df = get_all_mses_and_dates(msids, cohort["modality"], cohort["to_ignore"], cohort["modality_reduction"])

            if cohort["reduction"] == "long":
                counts = get_summary_counts(df)
                cohort_subjects = get_cohort(counts, cohort["num_timepoints"], cohort['num_years']).index.values
                cohort_df = get_exams(df, cohort_subjects)
                cohort_df.to_csv(join(base_dir,"../watchlists/demographics/{}.csv".format(cohort["name"])))
                get_pbr_list(cohort_df, join(base_dir, "../watchlists/mse/{}.txt".format(cohort["name"])))
                update_demographics(cohort_df, cohort["name"], config[args.env]["meteor_port"])
            else:
                df.to_csv(join(base_dir, "../watchlists/demographics/{}.csv".format(cohort["name"])))
                get_pbr_list(df, join(base_dir, "../watchlists/mse/{}.txt".format(cohort["name"])))
                update_demographics(df, cohort["name"], config[args.env]["meteor_port"])

    else:
        raise Exception("Choose the database you want to append to w/ -e production or -e development")
