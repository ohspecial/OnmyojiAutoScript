import argparse
import multiprocessing
import pickle

from module.logger import logger
from module.server.setting import State

process: multiprocessing.Process = None
from module.ocr.models import OcrModel

class ModelProxy:
    client = None
    online = True

    @classmethod
    def init(cls, address=State.deploy_config.OcrClientAddress):
        import zerorpc

        logger.info(f"Connecting to OCR server {address}")
        cls.client = zerorpc.Client(timeout=10)
        cls.client.connect(f"tcp://{address}")
        try:
            cls.client.hello()

            logger.info("Successfully connected to OCR server")
        except:
            cls.online = False
            logger.warning("Ocr server not running")

    @classmethod
    def close(cls):
        if cls.client is not None:
            logger.info('Disconnect to OCR server')
            cls.client.close()
            logger.info('Successfully disconnected to OCR server')
            cls.client = None

    def __init__(self, lang) -> None:
        self.lang = lang

    def ocr(self, img_fp):
        """
        Args:
            img_fp (np.ndarray):

        Returns:

        """
        if self.online:
            img_str = img_fp.dumps()
            try:
                return self.client("ocr", img_str)
            except Exception as e:
                logger.warning(f"Ocr server disconnected: {e}")

                self.online = False
        from module.ocr.models import OCR_MODEL
        return OCR_MODEL.__getattribute__(self.lang).ocr(img_fp)
    def detect_and_ocr(self, img_fp, drop_score=None):
        if self.online:
            img_str = img_fp.dumps()
            try:
                return self.client("detect_and_ocr", img_str, drop_score)
            except Exception as e:
                logger.warning(f"Ocr server disconnected: {e}")
                self.online = False
        from module.ocr.models import OCR_MODEL
        return OCR_MODEL.__getattribute__(self.lang).detect_and_ocr(img_fp, drop_score)
    def ocr_lines(self, img_fp):
        if self.online:
            img_str = img_fp.dumps()
            try:
                return self.client("ocr_lines", img_str)
            except:
                self.online = False
        from module.ocr.models import OCR_MODEL
        return OCR_MODEL.__getattribute__(self.lang).ocr_lines(img_fp)
    def ocr_single_line(self, img_fp):
        if self.online:
            img_str = img_fp.dumps()
            try:
                return self.client("ocr_single_line", img_str)
            except Exception as e:
                logger.warning(f"Ocr server disconnected: {e}")
                self.online = False
        from module.ocr.models import OCR_MODEL
        return OCR_MODEL.__getattribute__(self.lang).ocr_single_line(img_fp)

class ModelProxyFactory:
    def __getattribute__(self, __name='ch'):
        if ModelProxy.client is None:
            ModelProxy.init(address=State.deploy_config.OcrClientAddress)
        return ModelProxy

    def close(self):
        ModelProxy.close()

def start_ocr_server(port=22268):
    import zerorpc
    import zmq

    class OCRServer(OcrModel):
        def hello(self):
            return "hello"
        def ocr(self, img_fp):
            img_fp = pickle.loads(img_fp)
            cnocr = self.__getattribute__('ch')
            return cnocr.ocr(img_fp)
        def detect_and_ocr(self, img_fp, drop_score=None):
            img_fp = pickle.loads(img_fp)
            cnocr = self.__getattribute__('ch')
            return cnocr.detect_and_ocr(img_fp, drop_score)
        def ocr_lines(self, img_fp):
            img_fp = pickle.loads(img_fp)
            cnocr = self.__getattribute__('ch')
            return cnocr.ocr_lines(img_fp)
        def ocr_single_line(self, img_fp):
            img_fp = pickle.loads(img_fp)
            cnocr = self.__getattribute__('ch')
            return cnocr.ocr_single_line(img_fp)


    server = zerorpc.Server(OCRServer())
    try:
        server.bind(f"tcp://*:{port}")
    except zmq.error.ZMQError:
        logger.error(f"Ocr server cannot bind on port {port}")
        return
    logger.info(f"[OcrServer] Listening on port {port}")
    server.run()

def alive() -> bool:
    global process
    if process is not None:
        return process.is_alive()
    else:
        return False

def start_ocr_server_process(port=22268):
    global process
    if not alive():
        process = multiprocessing.Process(target=start_ocr_server, args=(port,))
        process.start()

if __name__ == "__main__":
    # Run server
    parser = argparse.ArgumentParser(description="OAS OCR service")
    parser.add_argument(
        "--port",
        type=int,
        help="Port to listen. Default to OcrServerPort in deploy setting",
    )
    args, _ = parser.parse_known_args()
    port = args.port or State.deploy_config.OcrServerPort
    start_ocr_server(port=port)