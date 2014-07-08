#!/usr/bin/python

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtNetwork import *

import sys

class MFtpCore(QObject):
    
    ftp_stat_str = ['Unconnected','HostLookup','Connecting','Connected','LoggedIn','Closing']
    core_stat_str = ['WaitingForLoggedIn','WaitingForListFile','WaitingForFileGetsDone','WaitingForFilePutsDone','WaitingForOp']
    
    Unconnected = 0
    HostLookup = 1
    Connecting = 2
    Connected = 3
    LoggedIn = 4
    Closing = 5
    
    WaitingForLoggedIn = 0
    WaitingForListFile = 1
    WaitingForFileGetsDone = 2
    WaitingForFilePutsDone = 3
    WaitingForOp = 4
    
    log = pyqtSignal(['QString'])
    status = pyqtSignal(['QString'])
    
    ListFile = '.mftp_list_file'
    
    def __init__(self):
        super(MFtpCore, self).__init__()
        self.ftp = QFtp()
        self.core_state = self.WaitingForLoggedIn
        self.listfile = QBuffer()
        self.listfile.open(QBuffer.ReadWrite)
    
        self.ftp.commandFinished.connect(self.onCommandFinished)
        self.ftp.commandStarted.connect(self.onCommandStarted)
        self.ftp.done.connect(self.onDone)
        self.ftp.stateChanged.connect(self.onStateChanged)
        
    def doAbortAll(self):
        self.ftp.abort()

    def doInvoke(self,Host,Port,UserName,Password):
        self.doAbortAll()
        self.ftp.connectToHost(Host,Port)
        self.ftp.login(UserName,Password)
        self.core_state = self.WaitingForLoggedIn
        
    def doUpload(self,FileName):
        fi = QFileInfo(FileName)
        if not fi.exists():
            self.log.emit("[~] File %s not exists" % FileName)
            return
        serverFileName = fi.fileName()
        self.log.emit("[~] Server file name %s" % serverFileName)    
        
        if fi.isSymLink():
            FileName = fi.symLinkTarget()
        self.log.emit("[~] Local file name %s" % FileName)
        f = QFile(FileName)
        if f.open(QIODevice.ReadOnly):
            self.log.emit("[~] Uploading")
            data = f.readAll()
            self.ftp.put(data,serverFileName)
            self.listfile.write("%s\t%d\n" % (serverFileName,fi.lastModified().toMSecsSinceEpoch()))
            self.listfile.seek(0)
            self.ftp.put(self.listfile,self.ListFile)
        else:
            self.log.emit("[~] Cannot open %s for read" % FileName)
    
    def onCommandFinished(self,i,e):
        if not e:
            s = 'OK' 
        else:
            s = 'Failed : ' + self.ftp.errorString()
        self.log.emit("[%d] Command %d Finished %s" % (i,self.ftp.currentCommand(),s))
        self.mainFSM('commandFinished',i,e)
        
    def onCommandStarted(self,i):
        self.log.emit("[%d] Command %d Started" % (i,self.ftp.currentCommand()))
        self.mainFSM('commandStarted',i,True)

    def onDone(self,e):
        self.log.emit("[~] Done")
        self.mainFSM('done',0,e)
        
    def onStateChanged(self,i):
        self.status.emit(self.ftp_stat_str[i])
        self.mainFSM('stateChanged',i,True)
                        
    def mainFSM(self,t,i,e):
        if self.core_state == self.WaitingForLoggedIn:
            if t == 'stateChanged' and i == self.LoggedIn:
                self.listfile.seek(0)
                self.ftp.get(self.ListFile,self.listfile)
                self.core_state = self.WaitingForListFile
                
        elif self.core_state == self.WaitingForListFile:
            if t == 'done':
                self.core_state = self.WaitingForOp
                
                
                
class MFtpUI(QDialog):
    def __init__(self):
        super(MFtpUI, self).__init__()
        
        self.mftpCore = MFtpCore()
        self.mftpCore.log.connect(self.onLog)
        self.mftpCore.status.connect(self.onStatus)
        
        self.btnConnect = QPushButton("Connect")
        self.btnConnect.clicked.connect(self.onConnect)

        self.btnUpload = QPushButton("Upload")
        self.btnUpload.clicked.connect(self.onUpload)
                
        self.txtLog = QTextEdit()
        self.txtStatus = QLineEdit()
             
        l = QVBoxLayout()
        
        l0 = QHBoxLayout()
        l0.addWidget(self.btnConnect)
        l0.addWidget(self.btnUpload)
        l0.addStretch()
        
        l.addLayout(l0)
        l.addWidget(self.txtLog)
        l.addWidget(self.txtStatus)
        
        self.setLayout(l)
        
    def onConnect(self):
        self.mftpCore.doInvoke("10.0.0.10",21,"zhoury","marvell@92")
        
    def onLog(self,s):
        self.txtLog.append(s)
        
    def onStatus(self,s):
        self.txtStatus.setText(s)
        
    def onUpload(self):
        fileName = QFileDialog.getOpenFileName(self,"Open File",".","All Files (*.*)");
        if fileName:
            self.mftpCore.doUpload(fileName)
            
                
if __name__ == '__main__':

    app = QApplication(sys.argv)
    w = MFtpUI()
    w.show()
    sys.exit(app.exec_())        
        
                          