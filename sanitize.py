#!/usr/bin/python3

import time
import telnetlib
import subprocess
import os

workdir="/etc/sanitize"

# Declares the Switch class along with its respective methods
# to access and performing reboot operations based on its respective model.

class Switch:
    def __init__(self, switch_name, switch_address):
        self.switch_name = switch_name
        self.switch_address = switch_address
        self.USER = "venko"
        self.PASSWD = "V3nk0-raisecom"
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

    def model_selection(self):
        ISCOM = {"RING-S1", "RING-S3"}
        RAX711 = {"RING-S2"}
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


def main():
    switch_dict = { 
        "RINGS1" : [ "RING-S1", "10.30.0.200"],
        "RINGS2" : [ "RING-S2", "10.30.0.201"],
        "RINGS3" : [ "RING-S3", "10.30.0.202"],
        "OcNOS"  : [ "OcNOS", "10.30.0.206"]
    }

    for switch in switch_dict.keys():
        switch_info = switch_dict.get(switch)
        if switch != "RINGS2":
            # TODO TEST/VERIFY PROCESS FOR REBOOTING RINGS2
            s = Switch(switch_info[0], switch_info[1])
            print(f"Starting loop for {switch_info[0]}")
        else:
            s = Switch(switch_info[0], switch_info[1])
        # Send a reboot command to the device 
        s.sanitize_device()
        del s
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
    main()


