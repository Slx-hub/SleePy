import subprocess

if __name__=='__main__':
    print("Hello World!")
    try: 
        subprocess.run(["aplay", f"./sounds/startup.wav"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e: 
        print("Sound error: %s", e)