import subprocess
import requests
import tarfile
from pathlib import Path
import io

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

