import subprocess
import requests
import tarfile
from pathlib import Path
import io
import json
import logging

logger = logging.getLogger(__name__)

def fetch_and_extract_sources(tarfile_url, dstpath):
    """
    Fetch and Install sources from internet
    """
    try:
        response = requests.get(tarfile_url, allow_redirects=True, stream=True)
        dst = Path(dstpath)
        with tarfile.open(fileobj=io.BytesIO(response.content), mode='r:gz') as tfile:
            tfile.extractall(path=dst)
    except subprocess.CalledProcessError as e:
        print(e)
        sys.exit(-1)

def getIpfsClusterVersion():
    resp = subprocess.check_output(['/opt/ipfs/ipfs-cluster-service/ipfs-cluster-service','--version']).decode()
    return resp.rstrip().rpartition(' ')[-1] # Get the version

def write_service_json(ctx):
    """
    Writes the service.json file.
    """
    with open("/home/ubuntu/.ipfs-cluster/service.json", "r") as jsonFile:
        data = json.load(jsonFile)

    data['cluster']['secret'] = ctx['cluster_secret']
    
    with open("/home/ubuntu/.ipfs-cluster/service.json", "w") as jsonFile:
        json.dump(data, jsonFile, indent=4)


def get_cluster_secret():
    """
    Get the secret from the service.json file.
    """
    with open("/home/ubuntu/.ipfs-cluster/service.json", "r") as jsonFile:
        data = json.load(jsonFile)

    return data['cluster']['secret']

def get_identity_id():
    """
    Get the id from the identity.json file.
    """
    with open("/home/ubuntu/.ipfs-cluster/identity.json", "r") as jsonFile:
        data = json.load(jsonFile)

    return data['id']
