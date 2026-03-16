import os
import urllib.request
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("download_models")

MODELS = {
    "kokoro-v0_19.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx",
    "voices.bin": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.bin"
}

def download():
    for filename, url in MODELS.items():
        if os.path.exists(filename):
            logger.info(f"Model {filename} already exists. Skipping.")
            continue
        
        logger.info(f"Downloading {filename} from {url}...")
        try:
            urllib.request.urlretrieve(url, filename)
            logger.info(f"Successfully downloaded {filename}")
        except Exception as e:
            logger.error(f"Failed to download {filename}: {e}")
            raise

if __name__ == "__main__":
    download()
