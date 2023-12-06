import os
import shutil
import paramiko
from datetime import datetime, timedelta
import json
import time
import subprocess
import sys
from art import text2art

def load_ascii_art(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return None
    except Exception as e:
        print(f"Error loading ASCII art from '{file_path}': {e}")
        return None

if len(sys.argv) < 6:
    print("Usage: python3 AtmCopy.py inventoryfile playbook.yml inventoryhost sftphosts.json 5 [--offansible] [--decodep6]")
    sys.exit(1)

AnsibleInventory = sys.argv[1]
PlayBookRUN = sys.argv[2]
GroupHostRUN = sys.argv[3]
remote_host_json = sys.argv[4]
sleep_minutes = int(sys.argv[5])
off_ansible = "--offansible" in sys.argv
decode_p6 = "--decodep6" in sys.argv
ascii_art_file_path = "ascii_art.txt"
decode_arc_pass = "XAXAXAXA"
ascii_art = load_ascii_art(ascii_art_file_path)

def get_most_recent_file(sftp, remote_path, file_name):
    files = sftp.listdir(remote_path)
    latest_file = None
    latest_mtime = 0

    for filename in files:
        remote_file = os.path.join(remote_path, filename)
        file_stat = sftp.stat(remote_file)
        if file_stat.st_mtime > latest_mtime and filename == file_name:
            latest_file = remote_file
            latest_mtime = file_stat.st_mtime

    return latest_file

def sftp_remote_files(host, username, password, remote_path, local_path, file_name):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(hostname=host, username=username, password=password)
    except paramiko.AuthenticationException:
        print(f"Authentication failed for host {host}")
        return None
    except Exception as e:
        print(f"Failed to connect to host {host}: {e}")
        return None

    local_path = local_path.replace('\\', '/')
    os.makedirs(local_path, exist_ok=True)

    sftp = ssh.open_sftp()
    latest_file = get_most_recent_file(sftp, remote_path, file_name)

    if not latest_file:
        print(f"File '{file_name}' not found in source directory on host {host}")
        return None

    local_file = os.path.join(local_path, file_name)
    win_local_file = local_file.replace('//', '/')
    win_local_file_txt = win_local_file.replace('.arc', '.txt')
    win_local_dir = os.path.dirname(win_local_file)
    win_local_dir_decode = os.path.join(win_local_dir, '')

    try:
        sftp.get(latest_file, local_file)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"Successfully copied {latest_file} to {local_file} at {timestamp}")

        if not off_ansible:
            playbook_command = f"ansible-playbook -l {GroupHostRUN} -i {AnsibleInventory} {PlayBookRUN}"
            subprocess.run(playbook_command, shell=True)

        if decode_p6:
            decode_command = f"wine Arc.exe e -p{decode_arc_pass} {win_local_file} -o+  -y"
            subprocess.run(decode_command, shell=True)
            print(f"Decoding from  {win_local_file} to {win_local_dir_decode}")
            time.sleep(3)
            shutil.move("p6info.txt",win_local_dir_decode)
            #os.remove(local_file)

            #print(f"Decoded {local_file} using Arc.exe and deleted {file_name}")

    except IOError as e:
       print(f"Failed to copy {latest_file}: {e}")

    sftp.close()
    ssh.close()

    return latest_file

with open(remote_host_json) as json_file:
    remote_hosts = json.load(json_file)

while True:
    for host_info in remote_hosts:
        latest_file = sftp_remote_files(host_info["host"], host_info["username"], host_info["password"],
                                        host_info["remote_path"], host_info["local_path"], host_info["file_name"])
        if latest_file is None:
            if ascii_art:
                print(ascii_art)
            else:
                print("Host Unavailable")
            continue

    next_start_time = datetime.now() + timedelta(minutes=sleep_minutes)
    next_end_time = next_start_time + timedelta(minutes=sleep_minutes)
    print(f"\nNext copy will start at: {next_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nExpected completion time: {next_end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Waiting for {sleep_minutes} minutes before the next iteration...")
    time.sleep(sleep_minutes * 60)
