#!/usr/bin/python

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtNetwork import *
from ui_utils import *

import mftp_res
import sys
import platform
import base64
import getpass
import argparse
import stat
import os

class MFtpCore(QObject):
    
    ftp_stat_str = ['Unconnected','HostLookup','Connecting','Connected','LoggedIn','Closing']
    core_stat_str = ['WaitingForConnected',
                     'WaitingForLoggedIn',
                     'WaitingForListFileDownLoadDone',
                     'WaitingForListFileUploadDone',
                     'WaitingForFileGetsDone',
                     'WaitingForFilePutsDone',
                     'WaitingForOp',
                     'WaitingForConnection']
    
    Unconnected = 0
    HostLookup = 1
    Connecting = 2
    Connected = 3
    LoggedIn = 4
    Closing = 5
    
    
    WaitingForConnected = 0
    WaitingForLoggedIn = 1
    WaitingForListFileDownLoadDone = 2
    WaitingForListFileUploadDone = 3
    WaitingForFileGetsDone = 4
    WaitingForFilePutsDone = 5
    WaitingForOp = 6
    WaitingForConnection = 7
    
    log = pyqtSignal(str)
    status = pyqtSignal(str)
    listupdate = pyqtSignal(dict)
    ready = pyqtSignal()
    busy = pyqtSignal()
    failed = pyqtSignal()
    
    ListFile = '.mftp_list_file'
    TimeOutThreadHold = 86400000
    
    def __init__(self):
        super(MFtpCore, self).__init__()
        self.ftp = QFtp()
        self.core_state = self.WaitingForConnection
        self.filelist = ''
        self.filelist_temp = ''
        self.wFileHandle = None
        
        self.ftp.commandFinished.connect(self.onCommandFinished)
        self.ftp.commandStarted.connect(self.onCommandStarted)
        self.ftp.done.connect(self.onDone)
        self.ftp.stateChanged.connect(self.onStateChanged)
        self.ftp.readyRead.connect(self.onReadyRead)
        
    def doAbortAll(self):
        self.ftp.abort()

    def doConnect(self,Host,Port,UserName,Password):
        if self.core_state != self.WaitingForConnection:
            return
        self.doAbortAll()       
        self.ftp.connectToHost(Host,Port)
        self.UserName = UserName
        self.Password = Password
        self.core_state = self.WaitingForConnected
        
    def doUpload(self,FileName):
        
        if self.core_state != self.WaitingForOp:
            return -1
        
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
            f.close()
            self.mainFSM ('uploadFile',{
                    'data' : data,
                    'serverFileName' : serverFileName,
                    'timestamp' : QDateTime.currentDateTime().toTime_t()
                },True)

        else:
            self.log.emit("[~] Cannot open %s for read" % FileName)

    def doDownload(self,serverFileName,localFileName):
        if self.core_state != self.WaitingForOp:
            return -1        
        
        self.mainFSM ('downloadFile',{
                'localFileName' : localFileName,
                'serverFileName' : serverFileName
            },False)

    def doRefreshList(self):
        if self.core_state != self.WaitingForOp:
            return -1
                    
        self.mainFSM ('refreshList',0,False)
            
    def onCommandFinished(self,i,e):
        if not e:
            s = 'OK' 
        else:
            s = 'Failed : ' + self.ftp.errorString()
            try:
                self.log.emit("[%d] Command Finished %s" % (i,str(s)))
            except:
                self.log.emit("[%d] Command Failed" % i)
            self.failed.emit()      
        self.mainFSM('commandFinished',i,e)
        
    def onCommandStarted(self,i):
        #self.log.emit("[%d] Command %d Started" % (i,self.ftp.currentCommand()))
        self.mainFSM('commandStarted',i,False)

    def onReadyRead (self):
        #self.log.emit("[~] onReadyRead")
        self.mainFSM('readyRead',self.ftp.bytesAvailable(),False)

    def onDone(self,e):
        #self.log.emit("[~] Done")
        self.mainFSM('done',0,e)
        
    def onStateChanged(self,i):
        self.status.emit(self.ftp_stat_str[i])
        self.mainFSM('stateChanged',i,False)
                        
    def mainFSM(self,t,i,e):
        #print self.core_stat_str[self.core_state],t,i,e
        
        if self.core_state == self.WaitingForConnected:
            if t == 'commandFinished' and not e:
                self.ftp.login(self.UserName,self.Password)
                self.core_state = self.WaitingForLoggedIn
        
        elif self.core_state == self.WaitingForLoggedIn:
            if t == 'commandFinished' and not e:
                self.ftp.get(self.ListFile)
                self.log.emit("[~] Get file list")
                self.core_state = self.WaitingForListFileDownLoadDone
            if t == 'commandFinished' and e:
                self.log.emit("[~] Login failed, check your user name and password")
                self.ftp.close()
                self.core_state = self.WaitingForConnection
                
        elif self.core_state == self.WaitingForListFileDownLoadDone:
                                  
            if t == 'readyRead':
                self.log.emit("[~] Get file list %d bytes" % i)
                self.filelist_temp += self.ftp.readAll()
                self.core_state = self.WaitingForListFileDownLoadDone

            if t == 'commandFinished':
                if not e:
                    self.filelist = self.filelist_temp
                    self.filelist_temp = ''
                    self.processList()
                    
                self.core_state = self.WaitingForOp
                self.log.emit("[~] Ready")
                                
        elif self.core_state == self.WaitingForOp:
            if t == 'uploadFile':
                self.ftp.put(i['data'],i['serverFileName'])
                self.tempI = i
                self.core_state = self.WaitingForFilePutsDone 
            if t == 'downloadFile':
                if i['localFileName'] == '*':
                    i['localFileName'] = self.latest_filename
                    i['serverFileName'] = self.latest_filename
                f = QFile(i['localFileName'])
                if f.open(QIODevice.WriteOnly):
                    self.log.emit("[~] Start download %s to %s" % (i['serverFileName'],i['localFileName']))
                    self.wFileHandle = f
                    self.ftp.get(i['serverFileName'])          
                    self.core_state = self.WaitingForFileGetsDone
                else:
                    self.log.emit("[~] Cannot open %s for write" % self.tempI['localFileName'])               
            if t == 'refreshList':
                self.ftp.get(self.ListFile)
                self.log.emit("[~] Get file list")
                self.core_state = self.WaitingForListFileDownLoadDone
                               
        elif self.core_state == self.WaitingForFilePutsDone:
            if t == 'commandFinished' and not e:
                self.filelist += "\n%s\t%d\n" % (self.tempI['serverFileName'],self.tempI['timestamp'])
                try:
                    self.ftp.put(self.filelist,self.ListFile)
                except:
                    self.ftp.put(self.filelist.toLocal8Bit(),self.ListFile)
                    
                self.core_state = self.WaitingForListFileUploadDone
                
        elif self.core_state == self.WaitingForListFileUploadDone:
            if t == 'commandFinished' and not e:          
                self.ftp.get(self.ListFile,None)
                self.log.emit("[~] Get file list")
                self.core_state = self.WaitingForListFileDownLoadDone   
               
        elif self.core_state == self.WaitingForFileGetsDone:
            if t == 'readyRead':
                self.log.emit("[~] Get %d bytes" % i)
                data = self.ftp.readAll()
                self.wFileHandle.write(data)
                
            if t == 'commandFinished':
                self.wFileHandle.close()
                self.log.emit("[~] Download OK")
                self.core_state = self.WaitingForOp
                self.log.emit("[~] Ready")               
        
        if self.core_state == self.WaitingForOp:
            self.ready.emit()
        else:
            self.busy.emit()
            
    def processList(self):
        
        listfile_info = {}
        t = 0
        filelist_new = ''
        for line in self.filelist.split("\n"):
            item = line.split("\t")
            if len(item) !=2:
                continue
            filename = item[0]
            filetimestamp = int(item[1].replace("\r","").replace("\n",""))
            if filetimestamp + self.TimeOutThreadHold > QDateTime.currentDateTime().toTime_t():
                listfile_info[str(filename)] = filetimestamp
                filelist_new += line + "\n"
                if filetimestamp > t:
                    t = filetimestamp
                    self.latest_filename = str(filename)
            else:
                self.log.emit("[~] Out of date %s" % filename)
        self.listupdate.emit(listfile_info)
        self.filelist = filelist_new                      

class MFtpAuth:
    
    @staticmethod 
    def resetAuth():
        settings = QSettings("OSoftWare", "MFTP")
        settings.clear()
        settings.sync()    
    
    @staticmethod 
    def saveAuth(r):
        siteNameConf = base64.b64encode(str(r['Site']))
        settings = QSettings("OSoftWare", "MFTP")
        settings.beginGroup(siteNameConf)
        userNameConf = base64.b64encode(str(r['UserName']))
        passWordConf = base64.b64encode(str(r['Password']))
        settings.setValue(userNameConf,passWordConf)
        settings.sync()
        if os.path.exists(settings.fileName()):
            os.chmod(settings.fileName(),stat.S_IRUSR | stat.S_IWUSR)
    
    @staticmethod         
    def getAuth(siteName,userName,isGUI = False,parent = None,NeedPropmt = False):
        
        if platform.system() == 'Windows':
            isGUI = True
        
        if not siteName is None:
            siteNameConf = base64.b64encode(str(siteName))
        else:
            siteNameConf = None
        
        if not userName is None:
            userNameConf = base64.b64encode(str(userName))
        else:
            userNameConf = None

        settings = QSettings("OSoftWare", "MFTP")
        groups = settings.childGroups()
        if siteNameConf is None and len(groups) == 1:
            siteNameConf = groups[0]
            try:
                siteName = base64.b64decode(str(siteNameConf))
            except:
                NeedPropmt = True
        else:
            NeedPropmt = True
                    
        if siteNameConf is None:
            NeedPropmt = True
        else:
            settings.beginGroup(siteNameConf)
            if userNameConf is None:
                usernames = settings.childKeys()
                if len(usernames) == 1:
                    userNameConf = usernames[0]
                    userName = base64.b64decode(str(userNameConf))
                    
            if userNameConf is None:
                NeedPropmt = True
            else:
                if settings.contains(userNameConf):
                    passWordConf = settings.value(userNameConf).toString()
                    passWord = base64.b64decode(str(passWordConf))
                else:
                    NeedPropmt = True
                
        if NeedPropmt:
            if isGUI:
                 r = QXInputDialog.getMulti(
                    parent,"Account Settings",
                    "Enter Authority",
                    ["Site","UserName","Password*"],
                    {'Site' : siteName,'UserName':userName}
                 )
                 
                 return r
            else:
                if siteName is None:
                    siteName = raw_input("Site Name :")
                    if not siteName:
                        return None
                else:
                    siteNameP = raw_input("Site Name [%s]:" % siteName)
                    if siteNameP:
                        siteName = siteNameP
                
                if userName is None:
                    userName = raw_input("Username [%s]:" % getpass.getuser())
                    if not userName:
                        return None
                else:
                    userNameP = raw_input("Username[%s]:" % userName)
                    if userNameP:
                        userName = userNameP
                        
                passWord = getpass.getpass("Password: ")
                if not passWord:
                    return None
        
        return {'Site' : siteName,'UserName':userName,'Password':passWord}            
                                  
                
            
                               
class MFtpUI(QDialog):
    def __init__(self):
        super(MFtpUI, self).__init__()
        
        self.mftpCore = MFtpCore()
        self.mftpCore.log.connect(self.onLog)
        self.mftpCore.status.connect(self.onStatus)
        self.mftpCore.listupdate.connect(self.onListUpdate)
        
        self.btnConnect = QPushButton("Connect")
        self.btnConnect.clicked.connect(self.onConnect)

        self.btnUpload = QPushButton("Upload")
        self.btnUpload.clicked.connect(self.onUpload)
        self.btnDownload = QPushButton("Download")
        self.btnDownload.clicked.connect(self.onDownload)
        self.btnRefresh = QPushButton("Refresh")
        self.btnRefresh.clicked.connect(self.onRefresh)                        
        self.lstFiles = QListWidget(self)
        self.txtLog = QTextEdit()
        self.txtStatus = QLineEdit()
             
        l = QVBoxLayout()
        
        l0 = QHBoxLayout()
        l0.addWidget(self.btnConnect)
        l0.addWidget(self.btnUpload)
        l0.addWidget(self.btnDownload)
        l0.addWidget(self.btnRefresh)
        l0.addStretch()
        
        l.addLayout(l0)
        l.addWidget(self.lstFiles)
        l.addWidget(self.txtLog)
        l.addWidget(self.txtStatus)
        
        self.setLayout(l)
        
    def onConnect(self):
        self.mftpCore.doConnect("iftp.marvell.com",21,"zhoury","marvell@92")
        
    def onLog(self,s):
        self.txtLog.append(s)
        
    def onStatus(self,s):
        self.txtStatus.setText(s)
        
    def onUpload(self):
        fileName = QFileDialog.getOpenFileName(self,"Open File",".","All Files (*.*)")
        if fileName:
            self.mftpCore.doUpload(fileName)
            
    def onDownload(self):
        item = self.lstFiles.currentItem()
        if item:
            serverFileName = item.text()
        else:
            self.onLog("Please Select Item")
            return
            
        localFileName = QFileDialog.getSaveFileName(self,"Save File",serverFileName,"All Files (*.*)")
        if localFileName:
            self.mftpCore.doDownload(serverFileName,localFileName)            
        else:
            self.onLog("Please Select localFileName")
    def onRefresh (self):
        self.mftpCore.doRefreshList()
        
    def onListUpdate(self,d):
        self.lstFiles.clear()
        for i in d.keys():
            self.lstFiles.addItem(i)       

class MFTextEdit(QTextEdit):
    def __init__(self,parent=None):
        super(MFTextEdit, self).__init__(parent)
        self.setReadOnly(True)
            
    def sizeHint(self):          
        return QSize(400, 120);
                
class MFtpGUI(QMainWindow):
    
    def __init__(self,auth):
        super(MFtpGUI, self).__init__()                    
    
        self.auth = auth
        ### Toolbar
        self.tbrMain = self.addToolBar("Main")

        self.btnAccount = QAction(QIcon(":account.png"),"Account",self.tbrMain)
        self.btnAccount.triggered.connect(self.onAccount)        
        self.btnConnect = QAction(QIcon(":connect.png"),"Connect",self.tbrMain)
        self.btnConnect.triggered.connect(self.onConnect)
        self.btnUpload = QAction (QIcon(":upload.png"),"Upload",self.tbrMain)
        self.btnUpload.triggered.connect(self.onUpload)
        self.btnDownload = QAction(QIcon(":download.png"),"Download",self.tbrMain)
        self.btnDownload.triggered.connect(self.onDownload)
        self.btnRefresh = QAction (QIcon(":refresh.png"),"Refresh",self.tbrMain)
        self.btnRefresh.triggered.connect(self.onRefresh)
               
        self.tbrMain.addAction(self.btnAccount)       
        self.tbrMain.addAction(self.btnConnect)
        self.tbrMain.addSeparator()
        self.tbrMain.addAction(self.btnUpload)
        self.tbrMain.addAction(self.btnDownload)
        self.tbrMain.addAction(self.btnRefresh)
        
        ### Main
        self.lstFiles = QListWidget(self)
        self.setCentralWidget(self.lstFiles)
 
        ### logging
        dockLog = QDockWidget("Log", self)
        dockLog.setAllowedAreas(Qt.BottomDockWidgetArea)
        self.txtLog = MFTextEdit(dockLog)
        dockLog.setWidget(self.txtLog)
        self.addDockWidget(Qt.BottomDockWidgetArea, dockLog)       
         
        ### status
        
        self.statusBar().showMessage("Ready")
        
        ### Window
        self.setWindowTitle("MFTP")
        self.resize(720,576)
        
        ### Core        
        self.mftpCore = MFtpCore()
        self.mftpCore.log.connect(self.onLog)
        self.mftpCore.status.connect(self.onStatus)
        self.mftpCore.listupdate.connect(self.onListUpdate)
        
    def onAccount(self):
        auth = self.auth
        auth = MFtpAuth.getAuth(auth['Site'],self.auth['UserName'],True,self,True)
        if auth is None:
            return
        else:
            MFtpAuth.resetAuth()
            MFtpAuth.saveAuth(auth)
            self.auth = auth        
            
    def onConnect(self):
        
        self.mftpCore.doConnect(self.auth['Site'],21,self.auth['UserName'],self.auth['Password'])
        
    def onLog(self,s):
        self.txtLog.append(s)
        
    def onStatus(self,s):
        self.statusBar().showMessage(s)
        
    def onUpload(self):
        fileName = QFileDialog.getOpenFileName(self,"Open File",".","All Files (*.*)")
        if fileName:
            self.mftpCore.doUpload(fileName)
            
    def onDownload(self):
        item = self.lstFiles.currentItem()
        if item:
            serverFileName = item.text()
        else:
            self.onLog("Please Select Item")
            return
            
        localFileName = QFileDialog.getSaveFileName(self,"Save File",serverFileName,"All Files (*.*)")
        if localFileName:
            self.mftpCore.doDownload(serverFileName,localFileName)            
        else:
            self.onLog("Please Select localFileName")
    def onRefresh (self):
        self.mftpCore.doRefreshList()
        
    def onListUpdate(self,d):
        self.lstFiles.clear()
        for i in d.keys():
            self.lstFiles.addItem(i) 

class MFtpCUI(QEventLoop):
    
    def __init__(self,auth,action,filename):
        super(MFtpCUI, self).__init__()                  
        self.auth = auth
        self.action = action
        self.filename = filename
        
        self.mftpCore = MFtpCore()
        self.mftpCore.log.connect(self.onLog)
        self.mftpCore.status.connect(self.onStatus)
        self.mftpCore.ready.connect(self.onReady)
        self.mftpCore.failed.connect(self.onFailed)
        
        self.mftpCore.doConnect(self.auth['Site'],21,self.auth['UserName'],self.auth['Password'])
        
    def onLog(self,s):
        print s
        
    def onStatus(self,s):
        print "[Status] %s" % s
            
    def onReady(self):
        if self.action == '':
            self.exit()
        if self.action == 'get':
            self.mftpCore.doDownload(self.filename,self.filename)
            self.action = ''
        if self.action == 'put':
            self.mftpCore.doUpload(self.filename)
            self.action = ''
    def onFailed(self):
        self.exit()        
        
              
                        
if __name__ == '__main__':

    app = QApplication(sys.argv)
    argparser = argparse.ArgumentParser(prog='mftp',description='MFTP - A micro ftp client',prefix_chars='-+')
    
    argparser.add_argument('--user','-u',metavar = 'UserName',type=str,nargs=1,help="ftp user name")
    argparser.add_argument('--site','-s',metavar = 'SiteName',type=str,nargs=1,help="ftp site name")
    argparser.add_argument('-get',metavar = 'GetFileName',type=str,nargs='?',const='*',help="download a file, only -get without GetFileName stands for the latest file")
    argparser.add_argument('-put',metavar = 'PutFileName',type=str,nargs=1,help="upload a file")
    argparser.add_argument('--auth','-a',nargs='?',const='y',help="retype authority information")
    args = argparser.parse_args()
    
    
    isGUI = False

    if not args.user is None:
        isGUI = False
        #print "2",isGUI

    if not args.get and not args.put:
        isGUI = True
        #print "1",isGUI
            
    if args.get and args.put:
        print "[ERROR] get and put conflit, specify one at a time"
        exit()
    
    authPrompt = False
    if (not args.user is None) or args.auth:
        authPrompt = True
        
    if not args.auth is None:
        if args.auth == "reset":
            MFtpAuth.resetAuth()     
    
    auth = MFtpAuth.getAuth(args.site,args.user,isGUI,None,authPrompt)
    if auth is None:
        exit()
    elif args.user is None:
        MFtpAuth.saveAuth(auth)
    
    #print "3",isGUI
    
    if isGUI:
        w = MFtpGUI(auth)
        w.show()
        sys.exit(app.exec_())
    else:

        if args.get is None:
            action = 'put'
            filename = args.put
            filename = filename[0]
        else:
            action = 'get'
            filename = args.get            
         
            
        w = MFtpCUI(auth,action,filename)
        w.exec_()      
        
                          