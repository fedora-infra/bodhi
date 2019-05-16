#!/bin/sh
echo $@ >> /tmp/pungi-calls.log
BASEDIR=/srv/composes/final
dir=`mktemp -d ${BASEDIR}/compose-XXXXXX`
# Fake compose metadata
mkdir -p ${dir}/compose/metadata/
touch ${dir}/compose/metadata/composeinfo.json
echo "Compose dir: ${dir}"
