import urllib.request
import zipfile
import os
import shutil
import sys

def install_ffmpeg():
    print("[+] Downloading FFmpeg for Windows...")
    url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    zip_path = "ffmpeg.zip"
    
    urllib.request.urlretrieve(url, zip_path)
    
    print("[+] Extracting...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall("ffmpeg_temp")
        
    print("[+] Installing to virtual environment...")
    # Find the extracted ffmpeg.exe
    ffmpeg_exe = None
    for root, dirs, files in os.walk("ffmpeg_temp"):
        if "ffmpeg.exe" in files:
            ffmpeg_exe = os.path.join(root, "ffmpeg.exe")
            break
            
    if ffmpeg_exe:
        venv_scripts = os.path.join(os.path.dirname(sys.executable))
        target_path = os.path.join(venv_scripts, "ffmpeg.exe")
        shutil.copy2(ffmpeg_exe, target_path)
        print(f"[+] Successfully installed ffmpeg to {target_path}")
    else:
        print("[!] Could not find ffmpeg.exe in the downloaded archive.")
        
    # Cleanup
    print("[+] Cleaning up...")
    os.remove(zip_path)
    shutil.rmtree("ffmpeg_temp")
    print("[+] Done.")

if __name__ == "__main__":
    install_ffmpeg()
