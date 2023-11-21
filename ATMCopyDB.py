#NCR ATMs Copy electronic calendar


import os
import paramiko
from datetime import datetime, timedelta
import json
import time
import subprocess
import re
import sqlite3
import uuid


PlayBookHost = "xxxxx"
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

def sftp_remote_files(host, username, password, remote_path, local_path, file_name, cursor, conn):
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
            unique_id = str(uuid.uuid4())

            # Υπολογισμός της ώρας έναρξης και ολοκλήρωσης για το επόμενο αντίγραφο
            next_start_time = datetime.now()
            next_end_time = next_start_time + timedelta(minutes=5)

            # Εισαγωγή δεδομένων στη βάση δεδομένων
            cursor.execute('''
                INSERT INTO copyres (id, time, host, filename, nextcopy)
                VALUES (?, ?, ?, ?, ?)
            ''', (unique_id, timestamp, host, os.path.basename(latest_file), next_end_time.strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()

            # Εκτέλεση του Ansible playbook
            playbook_command = f"ansible-playbook -l {PlayBookHost} -i /root/ansible/inventory /root/tasks/ATM_TASKS/copy.kivsrv-atm-live.yml"
            result = subprocess.run(playbook_command, shell=True, capture_output=True)

            # Ανάκτηση των προτύπων ok=1 και changed=1 με χρήση re
            matches = re.findall(r'(\w+)=1', result.stdout.decode())
            play_status = ','.join(matches) if matches else "N/A"

            # Καταγραφή του status στη βάση δεδομένων
            cursor.execute('''
                UPDATE copyres
                SET playstatus = ?
                WHERE id = ?
            ''', (play_status, unique_id))
            conn.commit()

        except IOError as e:
            print(f"Failed to copy {latest_file}: {e}")

    sftp.close()
    ssh.close()

    if latest_file:
        subject = "ΑΤΜ Files Transfer Summary"
        message = f"Total files copied: 1\n\nCopied files:\n{os.path.basename(latest_file)} -> {local_file} at {timestamp}\n"
        message += f"\nDate and time of sender: {datetime.now()}"
    return latest_file

with open('remote_hosts5M.json') as json_file:
    remote_hosts = json.load(json_file)

# Σύνδεση με τη βάση δεδομένων SQLite
conn = sqlite3.connect('copy_results.db')
cursor = conn.cursor()

# Δημιουργία του πίνακα αν δεν υπάρχει ήδη
cursor.execute('''
    CREATE TABLE IF NOT EXISTS copyres (
        id TEXT PRIMARY KEY,
        time TEXT,
        host TEXT,
        filename TEXT,
        nextcopy TEXT,
        playstatus TEXT
    )
''')
conn.commit()

while True:
    for host_info in remote_hosts:
        latest_file = sftp_remote_files(host_info["host"], host_info["username"], host_info["password"],
                                        host_info["remote_path"], host_info["local_path"], host_info["file_name"], cursor, conn)

    # Υπολογισμός ώρας έναρξης και ολοκλήρωσης για το επόμενο αντίγραφο
    next_start_time = datetime.now() + timedelta(minutes=5)
    next_end_time = next_start_time + timedelta(minutes=5)
    print(f"\nNext copy will start at: {next_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nExpected completion time: {next_end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Waiting for 5 minutes before the next iteration...")
    time.sleep(300)


conn.close()
