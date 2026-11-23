"""Download the Cookie Cats A/B test data (90,189 players) into data/.

The data comes from Tactile Entertainment's Cookie Cats experiment, first
published in DataCamp's "Mobile Games A/B Testing" project. This script takes
it from a public GitHub mirror. Run from the repository root.
"""

import hashlib
import urllib.request
from pathlib import Path

URL = "https://raw.githubusercontent.com/robguilarr/ab_testing_cookie_cats/main/datasets/cookie_cats.csv"
MD5 = "99b48ea3d4a552fa6b27aac60a8cfddf"
OUT = Path("data/cookie_cats.csv")

OUT.parent.mkdir(exist_ok=True)
data = urllib.request.urlopen(URL).read()
assert hashlib.md5(data).hexdigest() == MD5, "file differs from the version analysed"
OUT.write_bytes(data)
print("saved", OUT, len(data), "bytes")
