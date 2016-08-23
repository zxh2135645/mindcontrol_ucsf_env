#!/usr/bin/env python
__author__ = 'akeshavan'

from nipype.utils.filemanip import load_json, save_json
from glob import glob
import os
from os.path import join, split, exists
from pbr.config import config as cc
import pandas as pd
from copy import deepcopy
import argparse
def get_collection(port=3001):
    from pymongo import MongoClient
    client = MongoClient("localhost", port)
    db =  client.meteor
    collection = db.subjects
    return collection, client

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-e', '--env', dest="env")
    parser.add_argument("-s",  nargs="+", dest="subjects")
    config = load_json(os.path.join(os.path.split(__file__)[0], "config.json"))
    parser.add_argument("-i", "--include", dest="include", nargs="+")
    parser.add_argument("-x", "--exclude", dest="exclude", nargs="+")
    args = parser.parse_args()
    #print(args)
    if args.exclude == None:
        args.exclude = []
    if args.include == None:
        args.include = []
    if args.subjects == None:
        args.subjects = []
    if args.env in ["development", "production"]:
        env = args.env
        if len(args.subjects) > 0:
            if args.subjects[0].endswith(".txt"):
                import numpy as np
                subjects = np.genfromtxt(args.subjects[0], dtype=str)
            else:
                subjects = args.subjects
        meteor_port = config[env]["meteor_port"]
        query = {"entry_type":"demographic"}
        query["subject_id"] = {"$in": subjects.tolist()}
        query["status"] = {"$all": args.include, "$nin": args.exclude}
        coll, cli = get_collection(meteor_port+1)
        res = coll.find(query)
        for r in res:
            print(r["subject_id"])

    else:
        raise Exception("Choose the database you want to append to w/ -e production or -e development")