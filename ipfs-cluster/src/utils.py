import subprocess
import requestes

def fetch_and_extract_sources(tarfile_url):
    """
    Fetch and Install sources from internet
    """
    try:
        response = requests.get(tarfile_url, allow_redirects=True, stream=True)
        dst = Path('/opt/ipfs-cluster/')
        with tarfile.open(fileobj=io.BytesIO(response.content), mode='r:bz2') as tfile:
            tfile.extractall(path=dst)
    except subprocess.CalledProcessError as e:
        print(e)
        sys.exit(-1)
