
# coding: utf-8

# # Mindboggle Outputs to Mindcontrol

# gist_to: https://gist.github.com/156e9d479d1f72e7656463843af8fd6d

# In[71]:

#%pylab inline
from nipype.utils.filemanip import load_json, save_json
from glob import glob 
import os
from os.path import join, split, exists
from pbr.config import config as cc
import pandas as pd
from copy import deepcopy
import argparse


# ## Functions

# In[3]:

def get_status_file(pipeline, mse, outdir):
    folder = join(outdir, mse, pipeline, "status.json")
    if not exists(folder):
        #print("file not found", mse)
        return None
    status = load_json(folder)

    return status


# In[4]:

def get_name_from_mindboggle_output(fname):
    return fname.split("/")[-3]


# In[5]:

def get_t1(name,mse, outdir):
    nii_file = join(outdir, mse, "nii",name+".nii.gz")
    if exists(nii_file):
        return nii_file
    else:
        raise Exception("ERROR: file not found", mse)


# In[6]:

def relative_path(x, mse):
    foo = x.split("/"+mse+"/")[-1]
    return join(mse, foo)


# In[38]:

def create_mindboggle_entry(mse, outdir):
    status = get_status_file("mindboggle", mse, outdir)
    if status is not None:
        entries = []
        init = {"subject_id": mse}
        fs = status["hybrid_segmentation_fs"]
        ants = status["hybrid_segmentation_ants"]
        name = [get_name_from_mindboggle_output(f) for f in fs]
        for i, n in enumerate(name):
            entry = deepcopy(init)
            entry["name"] = n
            entry["check_masks"] = [relative_path(get_t1(n, mse, outdir), mse),
                                    relative_path(ants[i], mse),
                                    relative_path(fs[i], mse)]
            entry["metrics"] = status["metrics"][i]
            entry["entry_type"] = "mindboggle"
            entries.append(entry)
        return entries


# In[9]:

def create_alignment_entry(mse, outdir):
    status = get_status_file("alignment", mse, outdir)
    if status is not None:
        if "t1_files" in list(status.keys()):
            paths = [relative_path(s, mse) for s in status["t1_files"]]             + [relative_path(s, mse) for s in status["t2_files"]]             + [relative_path(s, mse) for s in status["flair_files"]]             + [relative_path(s, mse) for s in status["gad_files"]] 
            entry = {}
            entry["subject_id"] = mse
            entry["check_masks"] = paths
            entry["name"] = paths[0].split("/")[-1].split(".nii.gz")[0]
            entry["entry_type"] = "align"
            return entry


# In[63]:

def create_nifti_entry(mse, outdir):
    #TODO: add metrics for nifti via pulse sequense params
    status = get_status_file("nii", mse, outdir)
    if status is not None:
        entries = [{"check_masks": [relative_path(x, mse)],
                    "name": os.path.split(x)[-1].split(".nii.gz")[0],
                    "entry_type":"nifti",
                    "subject_id": mse} for x in status["nifti_files"]]
        return entries


# In[36]:

def create_antsCT_entry(mse, outdir):
    status = get_status_file("antsCT", mse, outdir)
    if status is not None:
        t1_names = [q.split("/")[-2] for q in status["BrainSegmentation"]]
        t1_files = [os.path.join(q.split("antsCT")[0],"nii", t1_names[i]+".nii.gz")
                    for i,q in enumerate(status["BrainSegmentation"])]
        if "metrics" in list(status.keys()):
            entries = [{"check_masks": [relative_path(t1_files[i], mse),
                                   relative_path(q, mse)],
                   "name": t1_names[i],
                    'entry_type': "antsCT",
                        "subject_id": mse,
                   "metrics": status["metrics"][i]} for i, q in enumerate(status["BrainSegmentation"])]
            return entries


# In[30]:

def create_freesurfer_entry(mse, outdir):
    status = get_status_file("masks", mse, outdir)
    if status is not None:
        t1_names = [q.split("/")[-2] for q in status["aparc"]]
        t1_files = [q for i,q in enumerate(status["orig"])]
        if "metrics" in list(status.keys()):
            entries = [{"check_masks": [relative_path(t1_files[i], mse),
                                        relative_path(q, mse)],
                       "name": t1_names[i],
                       'entry_type': "freesurfer",
                        "subject_id": mse,
                       "metrics": status["metrics"][i]} for i, q in enumerate(status["aparc"])]
            return entries


# In[10]:

def get_mindboggle_info(mse, outdir, all_entries):
    status = get_status_file("mindboggle", mse, outdir)
    if status is not None:
        entries = create_mindboggle_entry(status, mse, outdir) #is a list
        all_entries += entries


# In[43]:

def get_collection(port=3001):
    from pymongo import MongoClient
    client = MongoClient("localhost", port)
    db =  client.meteor
    collection = db.subjects
    return collection, client


# In[47]:

def update_db(meteor_port, entry):
    coll, _ = get_collection(meteor_port + 1)
    finder = {"subject_id": entry["subject_id"], 
              "entry_type": entry["entry_type"]}
    if "name" in entry.keys():
        finder["name"] = entry["name"]
        
    if coll.find_one(finder):    
        coll.update_one(finder, {"$set": entry})
    else:
        coll.insert_one(entry)


# In[68]:

def get_all_entries(mse, outdir):
    """
    Note: This doesn't update demographics, only PBR outputs
    """
    folders = [split(q)[1] for q in glob(join(outdir, mse, "*"))]
    print(folders)
    entries = []
    status_complete = []
    for fol in folders:
        if fol in pbr_folder_mapper.keys():
            func= pbr_folder_mapper[fol]
            to_add = func(mse, outdir)
            if to_add:
                entries += to_add
                status_complete.append(fol)
                
    entries.append({"subject_id": mse, "entry_type": 'demographic', "status": status_complete})
    return entries
    


# In[57]:

def update_db_entries(meteor_port, entries):
    return [update_db(meteor_port, entry) for entry in entries]


# #### TODO: Talk to MSPacman for demographic info (dates)

# In[8]:

def create_demographic_entry(mse, msid, demographics, study_tag):
    entry = {}
    entry["subject_id"] = mse
    entry["msid"] = msid
    entry["entry_type"] = "demographic"
    entry["Study Tag"] = study_tag
    entry["metrics"] = {}
    entry['metrics']["DCM_StudyDate"] = int(demographics[demographics.mse==mse].date.values[0])
    return entry



outdir = cc["output_directory"]
pbr_folder_mapper = {
          "nii": create_nifti_entry, 
          "masks": create_freesurfer_entry, 
          "antsCT": create_antsCT_entry,
          "mindboggle": create_mindboggle_entry,
          "alignment": create_alignment_entry}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-e', '--env', dest="env")
    parser.add_argument("-s",  nargs="+", dest="subjects")
    config = load_json(os.path.join(os.path.split(__file__)[0], "config.json"))
    #print(config)
    #parser.add_argument('-p',"--meteor_port", dest='meteor_port')
    #parser.add_argument("-s", "--static_port", dest="static_port")
    args = parser.parse_args()
    if args.env in ["development", "production"]:
        env = args.env
        if len(args.subjects) > 0:
            if args.subjects[0].endswith(".txt"):
                import numpy as np
                subjects = np.genfromtxt(args.subjects[0], dtype=str)
            else:
                subjects = args.subjects
        for mse in subjects:
            meteor_port = config[env]["meteor_port"]
            entries = get_all_entries(mse, outdir)
            update_db_entries(meteor_port, entries)
    else:
        raise Exception("Choose the database you want to append to w/ -e production or -e development")

