import os
import paramiko
from datetime import datetime, timedelta
import json
import time
import subprocess
import sys

# Έλεγχος αν παρέχονται τα απαραίτητα ορίσματα
if len(sys.argv) < 5:
    print("Usage: python3 AtmCopy.py inventory atm-copy.yml windowsb1XX atmhosts.json 5")
    sys.exit(1)

# Λήψη των ορισμάτων από τη γραμμή εντολών
AnsibleInventory = sys.argv[1]
PlayBookRUN = sys.argv[2]
GroupHostRUN = sys.argv[3]
remote_host_json = sys.argv[4]
sleep_minutes = int(sys.argv[4])


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
    ssh.connect(hostname=host, username=username, password=password)

    local_path = local_path.replace('\\', '/')
    os.makedirs(local_path, exist_ok=True)

    sftp = ssh.open_sftp()
    latest_file = get_most_recent_file(sftp, remote_path, file_name)

    if latest_file:
        local_file = os.path.join(local_path, file_name)
        try:
            sftp.get(latest_file, local_file)
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"Successfully copied {latest_file} to {local_file} at {timestamp}")

            # Εκτέλεση του Ansible playbook
            playbook_command = f"ansible-playbook -l {GroupHostRUN} -i {AnsibleInventory} {PlayBookRUN}"
            subprocess.run(playbook_command, shell=True)

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

    # Υπολογισμός ώρας έναρξης και ολοκλήρωσης για το επόμενο αντίγραφο
    next_start_time = datetime.now() + timedelta(minutes=sleep_minutes)
    next_end_time = next_start_time + timedelta(minutes=sleep_minutes)
    print(f"\nNext copy will start at: {next_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nExpected completion time: {next_end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Waiting for {sleep_minutes} minutes before the next iteration...")
    time.sleep(sleep_minutes * 60)
