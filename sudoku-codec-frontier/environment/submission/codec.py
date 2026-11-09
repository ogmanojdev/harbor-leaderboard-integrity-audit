"""Your codec. Replace the body of encode/decode and set BITS.

As shipped this is the article's 144-bit scheme, so it is already lossless and
already passes every gate -- it just does not meet the 108-bit target. Run
`python3 /app/reference/measure.py` to score it, then improve it.
"""
import sys
sys.path.insert(0, '/app/reference')
from article_codec import BITS, encode, decode  # noqa: F401
