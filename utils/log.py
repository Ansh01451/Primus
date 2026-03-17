# Configure module-level logger
import logging


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s %(filename)s:%(lineno)d')
handler.setFormatter(formatter)
logger.addHandler(handler)
