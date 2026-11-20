#!/bin/bash
set -x
PATH=$PATH:/home/venko/mini-user

interface_list=("enp4s0f1" "enp2s0f1" "enp4s0f3" "enp2s0f0" "enp3s0f0" "enp3s0f1")
_WORKDIR=/etc/sanitize/workdir

function StartMiniUsers {
    for i in $(seq 1 6); do
        interface=${interface_list[i-1]}
        mini-user start $i \
        -i $interface \
        -d $_WORKDIR
        echo -e "Mini-user $i created at $interface"
        done
}

StartMiniUsers
exit 0

