import urllib.request

url = "https://data.netlab.360.com/feeds/dga/dga.txt"
try:
    urllib.request.urlretrieve(url, "dga.txt")
except Exception as e:
    print(f"Failed to download: {e}")
