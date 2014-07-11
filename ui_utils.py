#!/usr/bin/python

from PyQt4.QtCore import *
from PyQt4.QtGui import *

class QXInputDialog(QInputDialog):
    
    @staticmethod 
    def getMulti(parent,title,label,items,defaultVal = None,flags=0):
        dlg = QDialog(parent)
        dlg.setWindowTitle(title)
        if flags !=0:
            dlg.setWindowFlags(flags)
        
        mainL = QVBoxLayout()
        mainL.addWidget(QLabel(label))
        
        formL = QFormLayout()
        edits = {}
        for item in items:
            edit = QLineEdit()
            
            if item[-1] == '*':
                item = item[0:len(item) - 1]
                edit.setEchoMode(QLineEdit.Password)
            
            edits[item] = edit    
            formL.addRow(item,edit)
                
            
            try:
                edit.setText(defaultVal[item])
            except:
                pass
            
        mainL.addLayout(formL)
        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(dlg.accept)
        buttonBox.rejected.connect(dlg.reject)
        mainL.addWidget(buttonBox)
        dlg.setLayout(mainL)
        r = dlg.exec_()
        if r == QDialog.Accepted:
            result = {}
            for item in items:
                if item[-1] == '*':
                    item = item[0:len(item) - 1]
                result[item] = str(edits[item].text())
            return result
        else:
            return None          

if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    x = QXInputDialog.getMulti(None,"multi","Enter Survey",["Name","Gender","Opt*"])
    print x 
                