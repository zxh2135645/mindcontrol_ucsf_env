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




