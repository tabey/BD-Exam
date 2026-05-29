#!/bin/bash

mkdir -p data

log="download_errors.log"
> "$log"

xargs -P 8 -I {} bash -c '
  url="$1"
  filename=$(basename "$url")
  log="$2"
  
  if ! wget -q "$url" -O "$filename"; then
    echo "$(date +%Y-%m-%d\ %H:%M:%S) FAILED DOWNLOAD: $url" >> "$log"
    rm -f "$filename"
    exit 1
  fi
  
  if ! unzip -q "$filename" -d data/; then
    echo "$(date +%Y-%m-%d\ %H:%M:%S) FAILED EXTRACT: $filename" >> "$log"
    rm -f "$filename"
    exit 1
  fi
  
  rm "$filename"
' _ {} "$log" < urls.txt