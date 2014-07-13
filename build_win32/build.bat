@echo off
copy ..\mftp.py .\
copy ..\mftp.qrc .\
copy ..\ui_utils.py .\
mkdir res
copy ..\res\* .\res\
pyrcc4 mftp.qrc > mftp_res.py
python build_exe.py
upx dist\mftp.exe
del /s /q build
rd /s /q build

