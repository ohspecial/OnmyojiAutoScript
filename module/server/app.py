# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import argparse
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from module.logger import logger
from module.ocr.rpc import stop_ocr_server_process, start_ocr_server_process

from module.server.home_router import home_app
from module.server.script_router import script_app
from module.server.setting import State


def cleanup_and_exit():
    """清理资源并退出"""
    logger.info("正在停止OCR server...")
    stop_ocr_server_process()
    logger.info("OCR server已停止")

app = FastAPI(
    title='OAS',
    description='OAS web service',
    version='0.0.0',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(home_app)
app.include_router(script_app)


# ocrServer
if State.deploy_config.UseOcrServer:
    port = State.deploy_config.OcrServerPort
    start_ocr_server_process(port=port)

@app.on_event("startup")
async def startup_event():
    logger.info('OAS web service startup done')
    # ocrServer
    if State.deploy_config.UseOcrServer:
        port = State.deploy_config.OcrServerPort
        start_ocr_server_process(port=port)
    pass

@app.on_event("shutdown")
async def shutdown_event():
    logger.info('OAS web service shutdown done')
    cleanup_and_exit()

















def fastapi_app():
    parser = argparse.ArgumentParser(description="OAS web service")
    parser.add_argument(
        "-k", "--key", type=str, help="Password of OAS. No password by default"
    )
    parser.add_argument(
        "--cdn",
        action="store_true",
        help="Use jsdelivr cdn for pywebio static files (css, js). Self host cdn by default.",
    )
    parser.add_argument(
        "--run",
        nargs="+",
        type=str,
        help="Run OAS by config names on startup",
    )
    args, _ = parser.parse_known_args()


    return app
