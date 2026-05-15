import logging
import time

logger = logging.getLogger(__name__)


def retry(fn, retries=3, delay=2, label=""):
    """线性退避重试，最后一次失败时 re-raise。"""
    for attempt in range(retries):
        try:
            return fn()
        except Exception as e:
            if attempt == retries - 1:
                raise
            wait = delay * (attempt + 1)
            logger.warning("%s 第 %d 次失败 (%s)，%ds 后重试…", label, attempt + 1, e, wait)
            time.sleep(wait)
