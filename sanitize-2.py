#!/usr/bin/python3

import time
import telnetlib
import subprocess
import os
import sys

workdir="/etc/sanitize"
FTP_SVR="10.147.20.159"

# Declares the Switch class along with its respective methods
# to access and performing reboot operations based on its respective model.

class Switch:
    def __init__(self, switch_name, switch_address, user = "venko", pwd = "V3nk0-raisecom"):
        self.switch_name = switch_name
        self.switch_address = switch_address
        self.USER = user
        self.PASSWD = pwd
        self.switch_address = switch_address
        self.telnet_commands = None
        """ Define the connections as variables so we can deal with them later """
        self.t = None
        self.model = self.model_selection()

    def sanitize_device(self):
        """ Defines telnet section as t and send the respective command of a given dictionary """
        self.swap_files()
        self.t = telnetlib.Telnet(self.switch_address) # Define t as the telnet section
        print(f"Connected to switch {self.switch_name}!!")
        time.sleep(2)
        REBOOTED=None
        while not REBOOTED:
            for command in self.telnet_commands.keys():
                if command in {"ame: ", "ord: ", "gin:", "ord:"}:
                    print("Sending the credentials...")
                else:
                    pass
                time.sleep(0.7)
                self.t.read_until(command.encode('ascii'))
                response = self.telnet_commands.get(command)
                if response in {"yes", "y"}:
                    self.t.write(response.encode('ascii') + b'\n')
                    print("Reboot command sent.")
                    REBOOTED=True
                    break
                if command == "#":
                    self.sanitize_rax()
                    print("Rebooting in 3 seconds. Ctrl+C to cancel")
                    time.sleep(3)
                self.t.write(response.encode('ascii') + b'\n')

    def send_command(self, cmds):
        """ Defines telnet section as t and send the respective command of a given dictionary """
        self.t = telnetlib.Telnet(self.switch_address) # Define t as the telnet section
        print(f"Connected to switch {self.switch_name}!!")
        time.sleep(2)
        SENT=None
        while not SENT:
            for command in self.telnet_commands.keys():
                if command in {"ame: ", "ord: ", "gin:", "ord:"}:
                    print("Sending the credentials...")
                else:
                    pass
                time.sleep(0.7)
                self.t.read_until(command.encode('ascii'))
                response = self.telnet_commands.get(command)
                #print(f"Resp: {response}")
                if command == "#":
                    for cmd in cmds:
                        self.t.write(cmd[0].encode('ascii') + b'\n')
                        time.sleep(0.7)
                        if len(cmd[1]):
                            response=self.t.read_until(cmd[1].encode('ascii'))
                        #response = self.telnet_commands.get(command)
                        #print(f"Response: {response}")
                        for r in response.split(b"\n"):
                            print(r.decode('ascii'))
                    SENT=True
                    break
                self.t.write(response.encode('ascii') + b'\n')

    def model_selection(self):
        ISCOM = { "RING-S1", "RING-S3", "ISCOM-S4" }
        RAX711 = { "RING-S2", "RAX-MPLS1", "RAX-MPLS2", "RAX-MPLS3" }
        OCNOS = {"OcNOS"}
        if self.switch_name in ISCOM:
            self.NEED_TO_SWAP = True
            self.telnet_commands = {
                "ame: ": self.USER,
                "ord: ": self.PASSWD,
                "#": "reboot",
                "y/n):":  "y"
            }
            return "_ISCOM_"
        elif self.switch_name in RAX711:
            self.NEED_TO_SWAP = False
            self.telnet_commands = {
                "gin:": "raisecom",
                "ord:": "raisecom",
                "#": "reboot",
                "firm:":  "yes"
            }
            return "_RAX711_"
        elif self.switch_name in OCNOS:
            self.NEED_TO_SWAP = False
            self.telnet_commands = {
                "gin:": "venko",
                "ord:": "V3nk0-2023!",
                "OS>" : "ena",
                "NOS#": "copy scp startup-config vrf management",
                "IP:" : "10.30.0.220",
                "ame:": "venko",
                "word:": "v3nk0",
                "path:": "/etc/sanitize/config_files/OcNOS",
                "NOS#": "reload",
                "(y/n):": "n",
                "(y/n):": "y"
            }
        else:
            print("This is not a valid Switch\n\nQuitting for {}!".format(self.switch_name))
            self.__del__

    def sanitize_rax(self):
        # Execute one more line of command, needed for factory reboot in RAX711 models
        if self.model == "_RAX711_":
            print("Oh! A RAX model.. In this case, we need to send another command.")
            self.t.write(b"boot next-startup system1\n")
            self.t.write(b"write\n")
        else:
            pass
    
    def close_session(self):
        """Closes the telnet connection if it is open."""
        if self.t:
            self.t.close()
            print("Telnet connection closed.")

    def swap_files(self):
        if self.NEED_TO_SWAP:
            # Swaps the startcfg file inside the switch
            swap_files_script=f"{workdir}/swap_files.sh"
            subprocess.Popen(["bash", swap_files_script, self.switch_name],\
                preexec_fn=set_user(), cwd=workdir)
            print("Factory default restored swapping files.")
        else:
            print("This switch doesn't need file swapping. Skipping process...")
            pass


    def __del__(self):
        print(f"Finished factory reset in {self.switch_name}.\n")


def main(argv):
    print(argv)
    switch_dict = {
        "RINGS1" : { "name": "RING-S1", "addr" : "10.30.0.200", "user": "venko", "pwd": "V3nk0-raisecom" },
        "RINGS2" : { "name": "RING-S2", "addr" : "10.30.0.201", "user": "master", "pwd": "America.1" },
        "RINGS3" : { "name": "RING-S3", "addr" : "10.30.0.202", "user": "venko", "pwd": "V3nk0-raisecom" },
        "ISCOM-S4" : { "name": "ISCOM-S4", "addr" : "10.30.0.248", "user": "venko", "pwd": "V3nk0-raisecom" },
        "RAX-MPLS1" : { "name": "RAX-MPLS1", "addr" : "10.30.0.203", "user": "venko", "pwd": "V3nk0-raisecom" },
        "RAX-MPLS2" : { "name": "RAX-MPLS2", "addr" : "10.30.0.204", "user": "raisecom", "pwd": "raisecom" },
        "RAX-MPLS3" : { "name": "RAX-MPLS3", "addr" : "10.30.0.206", "user": "raisecom", "pwd": "raisecom" },
        #"OcNOS" : { "name": "OcNOS", "addr" : "10.30.0.206", "user": "venko", "pwd": "V3nk0-raisecom" }
    }

    for switch in switch_dict.keys():
        switch_info = switch_dict.get(switch)
        if len(argv) > 1:
            file_name = argv[2] + "-"
            if switch != "RINGS2" and (switch.find("RAX-MPLS") < 0) and "down" in argv[1]:
                continue
            s = Switch(switch_info["name"], switch_info["addr"], switch_info["user"], switch_info["pwd"])
            upload_cmds = [ 
                ("write backup-config", "#"),
                ("upload backup-config ftp " + FTP_SVR + " venko V3nk0 " + file_name + switch_info["name"] + ".cfg", "#")
            ]
            download_cmds = [ 
                ("download backup-config ftp " + FTP_SVR + " venko V3nk0 "  + file_name + switch_info["name"] + ".cfg", "place it"),
                ("yes", "#"),
                ("copy backup-config startup-config", "#")
            ]
            if switch != "RINGS2" and switch.find("RAX-MPLS") < 0:
                upload_cmds = [
                    ("ftp put " + FTP_SVR + " venko V3nk0 " + file_name + switch_info["name"] + ".cfg running-config", "#")
                ]
                download_cmds = [
                    ("ftp get " + FTP_SVR +" venko V3nk0 "  + file_name + switch_info["name"] + ".cfg localfile backup.cfg", "#")
                ]
            print(f"Starting loop for {switch_info["name"]}")

            if "up" in argv[1]:
                cmds = upload_cmds
            elif "down" in argv[1]:
                cmds = download_cmds
            else:
                print("Wrong command")
                sys.exit(1)
            s.send_command(cmds)
            del s
            continue
        if switch != "RINGS2":
            # TODO TEST/VERIFY PROCESS FOR REBOOTING RINGS2
            s = Switch(switch_info["name"], switch_info["addr"])
            print(f"Starting loop for {switch_info["name"]}")
        else:
            s = Switch(switch_info[0], switch_info[1])
        # Send a reboot command to the device 
        s.sanitize_device()
        del s
    if not len(argv) > 1:
        miniusers_setup()

def set_user():
    def result():
        ###Define venko in a subprocess everytime that is called
        os.setgid(1000)
        os.setuid(1000)
    return result

def miniusers_setup():
    print("Now we will start setting up the mini-users.")
    ## TODO VERIFY IF THERE ARE MINI-USERS ACTIVE AND CHOSE ACCORDINGLY
    #mini_user_list="/home/venko/mini-user/mini-user list"
    #result = subprocess.run(mini_user_list, shell=True, capture_output=True, text=True)
    #print(result)
    print("Stopping all mini-users...")
    subprocess.run(["bash",f"{workdir}/muser_stop.sh"])
    time.sleep(1)
    print("Starting all mini-users...")
    subprocess.run(["bash",f"{workdir}/muser_start.sh"])

if __name__=="__main__":
    main(sys.argv)


