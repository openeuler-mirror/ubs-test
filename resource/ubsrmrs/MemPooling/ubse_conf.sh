#!/bin/sh
RACK_CONF="/etc/ubse/ubse.conf"

# 更新或添加 group
if grep -Eq '^#?group=' "$RACK_CONF"; then
    sed -i "/^\[ubse\.memory\]/,/^\[/{s/^#\?group=.*/group=$1/}" "$RACK_CONF"
else
    sed -i "/^\[ubse\.memory\]/a group=$1" "$RACK_CONF"
fi

# 更新或添加 provider
if grep -Eq '^#?provider=' "$RACK_CONF"; then
    sed -i "/^\[ubse\.memory\]/,/^\[/{s/^#\?provider=.*/provider=$2/}" "$RACK_CONF"
else
    sed -i "/^\[ubse\.memory\]/a provider=$2" "$RACK_CONF"
fi