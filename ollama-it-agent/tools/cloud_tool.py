import subprocess

def cloud_disk_check(vm_ip, username, key_path):
    cmd = f"ssh -i {key_path} {username}@{vm_ip} df -h"

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    return result.stdout