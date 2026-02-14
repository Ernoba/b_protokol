# bproto/utils.py
import socket
import platform
import subprocess

class SystemUtils:
    @staticmethod
    def get_free_tcp_port():
        tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp.bind(('', 0))
        _, port = tcp.getsockname()
        tcp.close()
        return port

    @staticmethod
    def copy_to_clipboard(text):
        try:
            system = platform.system()
            if system == "Windows":
                cmd = "clip"
            elif system == "Darwin":
                cmd = "pbcopy"
            else:
                cmd = "xclip -selection clipboard"
            
            # Encoding fix
            subprocess.run(cmd.split(), input=text.encode('utf-8'), check=True)
            return True
        except: 
            return False