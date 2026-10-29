"""STEP 4 - test SAM 3.1 alone.
Usage:  python test_sam.py path/to/screenshot.png "button"
Prints how many matches SAM 3.1 found and where (as fractions of the image)."""
import mimetypes
import sys

from app.sam_refine import segment_concept

if len(sys.argv) < 3:
    print('Usage: python test_sam.py image.png "button"')
    sys.exit(1)

path, concept = sys.argv[1], sys.argv[2]
mime = mimetypes.guess_type(path)[0] or "image/png"
boxes = segment_concept(open(path, "rb").read(), mime, concept)
print(f"SAM 3.1 found {len(boxes)} match(es) for '{concept}'")
for i, b in enumerate(boxes, start=1):
    print(i, [round(v, 3) for v in b["box"]])
