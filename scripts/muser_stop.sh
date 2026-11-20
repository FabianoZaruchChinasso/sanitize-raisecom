#!/bin/bash

PATH=$PATH:/home/venko/mini-user
set -x

# Stop all mini-users sections
function StopMiniUsers {
    for i in $(seq 1 6); do
        mini-user stop $i 
        echo -e "Mini-user $i stopped."
        done
    mini-user list
}

# Cleans-up the ovs-bridges
function TeardownOvs {
    for bridge in $(sudo ovs-vsctl list-br); do
        echo "Removing bridge: $bridge"
        sudo ovs-vsctl del-br "$bridge"
    done
}

StopMiniUsers
TeardownOvs
exit 0

