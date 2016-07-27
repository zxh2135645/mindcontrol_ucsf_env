# UCSF Mindcontrol bin/ README

These are helper functions to take UCSF pipeline outputs and put them in mindcontrol.

##config.json

This configuration file tells the other scripts which ports to use for each environment (production, development) and where to save database backups.

## mcdb.py

mcdb.py is a wrapper for the meteor and mongo database functions. Examples


### Start the server

```

mcdb.py -e development -start

mcdb.py -e production -start

```

### Stop the server

```

mcdb.py -e development -start

mcdb.py -e production -start

```

### Backup the database

```

mcdb.py -e development -backup

mcdb.py -e production -backup

```

### Restore the database

```
mcdb.py -e developent -restore <path/to/backup/>/meteor

mcdb.py -e production -restore <path/to/backup/>/meteor

```

## mcup.py

mcup.py is used to update the database (production or development) with entries. The script assumes the directory structure and outputs of UCSF's pipelines (called PBR). To use, run:

```

mcup.py -e development -s mse1 mse2 mse3

```

or

```

mcup.py -e development -s list_of_mses.txt

```

where the list_of_mses.txt file is formatted like:

```
mse1
mse2
mse3
```

## mc_roi.py

mc_roi.py converts the papaya coordinates saved in the database to a nifti-gz volume, and then adds that volume as a loadable image in mindcontrol. To use, run

```
mc_roi.py -e development -s mse# 
mc_roi.py -e development -s mse_list.txt 
mc_roi.py -e development -s mse# --entry_type freesurfer antsCT
```

