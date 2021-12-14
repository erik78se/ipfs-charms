import subprocess

def getIpfsVersion():
    resp = subprocess.check_output(['ipfs','--version']).decode()
    return resp.rstrip().rpartition(' ')[-1] # Get the version
