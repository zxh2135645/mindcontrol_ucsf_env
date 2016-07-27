import argparse
from nipype.utils.filemanip import load_json
import os
from subprocess import check_call

def start_servers(env = "development", meteor_port=3000, static_port=3002):
    import subprocess
    from pbr.db_utils import check_for_servers
    import pbr
    import os
    
    server_cmd = ["meteor", "--port", str(meteor_port)]
    static_cmd = ["start_static_server", str(static_port)]
    #TODO: What is this dir @ production??
    meteor_dir = os.path.join(os.path.split(os.path.realpath(__file__))[0].replace("bin", env),"mindcontrol")
    print("The meteor dir is", meteor_dir)
    print("meteor port, static port", meteor_port, static_port)
    pid1, pid2, pid3 = zcheck_for_servers(meteor_port, static_port)
    cwd = os.getcwd()
    
    if not pid1 and not pid3:
        os.chdir(meteor_dir)
        pid1 = subprocess.Popen(server_cmd)
    if not pid2:
        pid2 = subprocess.Popen(static_cmd, stdout = subprocess.PIPE)

    os.chdir(cwd)
    return pid1, pid2, pid3


def zcheck_for_servers(meteor_port, static_port):
    import psutil
    print("checking in", meteor_port, static_port)
    db_port = meteor_port + 1

    pid1, pid2, pid3 = None, None, None

    connections = psutil.net_connections()

    for c in connections:
        host, port = c.laddr
        if port==meteor_port and (host == "127.0.0.1" or host == "0.0.0.0"):
            pid1 = c.pid
        if port==static_port and (host == "127.0.0.1" or host == "0.0.0.0"):
            pid2 = c.pid
        if port==db_port and (host == "127.0.0.1" or host == "0.0.0.0"):
            pid3 = c.pid

    return pid1, pid2, pid3

def kill_servers(meteor_port, static_port):
    import psutil
    
    pid1,pid2,pid3 = zcheck_for_servers(meteor_port, static_port)
    
    if pid1:
        p = psutil.Process(pid1)
        p.terminate()
        print("terminated", pid1, "for meteor")

    if pid2:
        p = psutil.Process(pid2)
        p.terminate()
        print("terminated", pid2, "for static server")
    if pid3:
        p = psutil.Process(pid3)
        p.terminate()
        print("terminated", pid3, "for mongo")

    return

def backup_function(backup_dir, port):
    import time
    dt = time.strftime("%Y%B%d-%H%M%S")

    cmd = ["mongodump", "-h", "127.0.0.1", "--port",
           str(port), "-d", "meteor", "-o",
           os.path.join(backup_dir, dt)]

    print(" ".join(cmd))
    check_call(cmd)

def restore_function(restore_dir, port):
    cmd = ["mongorestore", "-h", "127.0.0.1", "--drop", "--port", str(port), "-d", "meteor", restore_dir]
    print(" ".join(cmd))
    check_call(cmd)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-e', '--env', dest="env")
    parser.add_argument("-start", action="store_true")
    parser.add_argument("-stop", action="store_true")
    parser.add_argument("-backup", action="store_true")
    parser.add_argument("-restore", dest="restore_dir")
    config = load_json(os.path.join(os.path.split(__file__)[0], "config.json"))
    #print(config)
    #parser.add_argument('-p',"--meteor_port", dest='meteor_port')
    #parser.add_argument("-s", "--static_port", dest="static_port")
    args = parser.parse_args()
    #print(args)
    if args.env in ["development", "production"]:
        env = args.env
        if args.start:
            start_servers(args.env, config[env]["meteor_port"], config[env]["static_port"])
        elif args.stop:
            kill_servers(config[env]["meteor_port"], config[env]["static_port"])
        elif args.backup:
            backup_function(config[env]["backup_dir"],config[env]["meteor_port"]+1) 
        if args.restore_dir and not args.stop:
            restore_function(args.restore_dir, config[env]["meteor_port"]+1)   

    else:
       raise Exception("ENV must be 'development' or 'production'")





