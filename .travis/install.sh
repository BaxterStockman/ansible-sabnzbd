#!/usr/bin/env bash

: "${BOOTSTRAP_URL:=https://github.com/BaxterStockman/ansible-bootstrap.git}"
: "${BOOTSTRAP_VERSION:=master}"
: "${BOOTSTRAP_ROLE_NAME:=bootstrap}"

if [[ -z "$ANSIBLE_HOME" ]]; then
    ANSIBLE_HOME=~/.ansible
fi

tmpdir=$(mktemp -d)

ansible-galaxy install -p "$tmpdir" \
    "${BOOTSTRAP_URL},${BOOTSTRAP_VERSION},${BOOTSTRAP_ROLE_NAME}"

mkdir -p "${ANSIBLE_HOME}/plugins"
for plugin_type in action_plugins callback_plugins; do
    cp -a "${tmpdir}/${BOOTSTRAP_ROLE_NAME}/${plugin_type}" "${ANSIBLE_HOME}/plugins"
done

cp -a "${tmpdir}/${BOOTSTRAP_ROLE_NAME}/library" "$ANSIBLE_HOME"
