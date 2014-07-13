#!/bin/bash

rm -rf dist
touch qt.conf
cp ../mftp.py .
cp ../mftp_res.py .
cp ../ui_utils.py .
cp ../res/app_icon.icns ./
/usr/bin/python build_app.py py2app
rm -rf build
rm -rf mftp.dmg
hdiutil create mftp.dmg -srcfolder dist/mftp.app