import logging
import sys

logger = logging.getLogger("security_platform")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)

# Convention: never pass passwords, tokens, or OTPs into these calls.
