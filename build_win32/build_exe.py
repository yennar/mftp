from distutils.core import setup
import py2exe
import sys
 
#this allows to run it with a simple double click.
sys.argv.append('py2exe')


py2exe_options = {
        "dll_excludes": ["MSVCP90.dll","w9xpopen.exe"],
        "compressed": 1,
        "optimize": 2,
        "ascii": 0,
        "includes": ["sip"],
        "bundle_files": 1,
        }
 
setup(
      name = 'mftp',
      version = '1.0',
      console = [{
            'script' : 'mftp.py'
             }
           ],     
      zipfile = None,
      options = {'py2exe': py2exe_options}
      )
      