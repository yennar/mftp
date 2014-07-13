#!/bin/bash

rm -rf mftp.zip
cp ../mftp.py __main__.py
cp ../mftp_res.py .
cp ../ui_utils.py .
zip mftp.zip __main__.py mftp_res.py ui_utils.py
cat hashbang.txt mftp.zip > mftp
chmod +x mftp