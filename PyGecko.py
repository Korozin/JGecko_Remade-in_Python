import os
import time
import math
import tkinter
import pygame
import socket, struct
import PySimpleGUI as sg
from sys import byteorder
from tkinter import filedialog
from binascii import hexlify, unhexlify
from mutagen.mp3 import MP3 as mp3

# PyGecko v2 | Release 2021/11/2
# CopyRight (c) Pixel&Syoch

#------- Start User Interface Setting -------#
#起動音ファイル（startup.mp3）がない場合は起動画面自体が再生されません
screeny=23 # 画面にはみ出る場合はここを変更(17など)
buttonx=12 # buttontype1
buttonxm=17 # buttontype2
buttonxs=28 # buttontype3
#------- End User Interface Setting -------#


#------- Start TCPGecko Module -------#
class switch(object):
    def __init__(self, value):
        self.value = value
        self.fall = False
    def __iter__(self):
        yield self.match
        raise StopIteration
    def match(self, *args):
        if self.fall or not args:
            return True
        elif self.value in args:
            self.fall = True
            return True
        else:
            return False
def hexstr(data, length): #Pad hex to value for prettyprint
    return hex(data).lstrip("0x").rstrip("L").zfill(length).upper()
def hexstr0(data): #Uppercase hex to string
    return "0x" + hex(data).lstrip("0x").rstrip("L").upper()
def binr(byte): #Get bits as a string
    return bin(byte).lstrip("0b").zfill(8)
def uint8(data, pos):
    return struct.unpack(">B", data[pos:pos + 1])[0]
def uint16(data, pos):
    return struct.unpack(">H", data[pos:pos + 2])[0]
def uint24(data, pos):
    return struct.unpack(">I", "\00" + data[pos:pos + 3])[0] #HAX
def uint32(data, pos):
    return struct.unpack(">I", data[pos:pos + 4])[0]
def getstr(data, pos): #Keep incrementing till you hit a stop
    string = ""
    while data[pos] != 0:
        if pos != len(data):
            string += chr(data[pos])
            pos += 1
        else: break
    return string
def enum(**enums):
    return type('Enum', (), enums)
class TCPGecko:
    def __init__(self, *args):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        print("Connecting to " + str(args[0]) + ":7331")
        self.s.connect((str(args[0]), 7331)) #IP, 1337 reversed, Cafiine uses 7332+
        print("Connected!")
    def readmem(self, address, length): #Number of bytes
        if length == 0: raise BaseException("Reading memory requires a length (# of bytes)")
        if not self.validrange(address, length): raise BaseException("Address range not valid")
        if not self.validaccess(address, length, "read"): raise BaseException("Cannot read from address")
        ret = b""
        if length > 0x400:
            print("Length is greater than 0x400 bytes, need to read in chunks")
            print("Start address:   " + hexstr0(address))
            for i in range(int(length / 0x400)): #Number of blocks, ignores extra
                self.s.send(b"\x04") #cmd_readmem
                request = struct.pack(">II", address, address + 0x400)
                self.s.send(request)
                status = self.s.recv(1)
                if   status == b"\xbd": ret += self.s.recv(0x400)
                elif status == b"\xb0": ret += b"\x00" * 0x400
                else: raise BaseException("Something went terribly wrong")
                address += 0x400;length -= 0x400
                print("Current address: " + hexstr0(address))
            if length != 0: #Now read the last little bit
                self.s.send(b"\x04")
                request = struct.pack(">II", address, address + length)
                self.s.send(request)
                status = self.s.recv(1)
                if   status == b"\xbd": ret += self.s.recv(length)
                elif status == b"\xb0": ret += b"\x00" * length
                else: raise BaseException("Something went terribly wrong")
            print("Finished!")
        else:
            self.s.send(b"\x04")
            request = struct.pack(">II", address, address + length)
            self.s.send(request)
            status = self.s.recv(1)
            if   status == b"\xbd": ret += self.s.recv(length)
            elif status == b"\xb0": ret += b"\x00" * length
            else: raise BaseException("Something went terribly wrong")
        return ret
    def readkern(self, address): #Only takes 4 bytes, may need to run multiple times
        if not self.validrange(address, 4): raise BaseException("Address range not valid")
        if not self.validaccess(address, 4, "write"): raise BaseException("Cannot write to address")
        self.s.send(b"\x0C") #cmd_readkern
        request = struct.pack(">I", int(address))
        self.s.send(request)
        value  = struct.unpack(">I", self.s.recv(4))[0]
        return value
    def writekern(self, address, value): #Only takes 4 bytes, may need to run multiple times
        if not self.validrange(address, 4): raise BaseException("Address range not valid")
        if not self.validaccess(address, 4, "write"): raise BaseException("Cannot write to address")
        self.s.send(b"\x0B") #cmd_readkern
        print(value)
        request = struct.pack(">II", int(address), int(value))
        self.s.send(request)
        return
    def pokemem(self, address, value): #Only takes 4 bytes, may need to run multiple times
        if not self.validrange(address, 4): raise BaseException("Address range not valid")
        if not self.validaccess(address, 4, "write"): raise BaseException("Cannot write to address")
        self.s.send(b"\x03") #cmd_pokemem
        request = struct.pack(">II", int(address), int(value))
        self.s.send(request) #Done, move on
        return
    def search32(self, address, value, size):
        self.s.send(b"\x72") #cmd_search32
        request = struct.pack(">III", address, value, size)
        self.s.send(request)
        reply = self.s.recv(4)
        return struct.unpack(">I", reply)[0]
    def getversion(self):
        self.s.send(b"\x9A") #cmd_os_version
        reply = self.s.recv(4)
        return struct.unpack(">I", reply)[0]
    def writestr(self, address, string):
        if not self.validrange(address, len(string)): raise BaseException("Address range not valid")
        if not self.validaccess(address, len(string), "write"): raise BaseException("Cannot write to address")
        if type(string) != bytes: string = bytes(string, "UTF-8") #Sanitize
        if len(string) % 4: string += bytes((4 - (len(string) % 4)) * b"\x00")
        pos = 0
        for x in range(int(len(string) / 4)):
            self.pokemem(address, struct.unpack(">I", string[pos:pos + 4])[0])
            address += 4;pos += 4
        return
    def memalign(self, size, align):
        symbol = self.get_symbol("coreinit.rpl", "MEMAllocFromDefaultHeapEx", True, 1)
        symbol = struct.unpack(">I", symbol.address)[0]
        address = self.readmem(symbol, 4)
        ret = self.call(address, size, align)
        return ret
    def freemem(self, address):
        symbol = self.get_symbol("coreinit.rpl", "MEMFreeToDefaultHeap", True, 1)
        symbol = struct.unpack(">I", symbol.address)[0]
        addr = self.readmem(symbol, 4)
        self.call(addr, address) #void, no return
    def memalloc(self, size, align, noprint=False):
        return self.function("coreinit.rpl", "OSAllocFromSystem", noprint, 0, size, align)
    def freealloc(self, address):
        return self.function("coreinit.rpl", "OSFreeToSystem", True, 0, address)
    def createpath(self, path):
        if not hasattr(self, "pPath"): self.pPath = self.memalloc(len(path), 0x20, True) #It'll auto-pad
        size = len(path) + (32 - (len(path) % 32))
        self.function("coreinit.rpl", "memset", True, 0, self.pPath, 0x00, size)
        self.writestr(self.pPath, path)
    def createstr(self, string):
        address = self.memalloc(len(string), 0x20, True) #It'll auto-pad
        size = len(string) + (32 - (len(string) % 32))
        self.function("coreinit.rpl", "memset", True, 0, address, 0x00, size)
        self.writestr(address, string)
        print("String address: " + hexstr0(address))
        return address
    def FSInitClient(self):
        self.pClient = self.memalign(0x1700, 0x20)
        self.function("coreinit.rpl", "FSAddClient", True, 0, self.pClient)
    def FSInitCmdBlock(self):
        self.pCmd = self.memalign(0xA80, 0x20)
        self.function("coreinit.rpl", "FSInitCmdBlock", True, 0, self.pCmd)
    def FSOpenDir(self, path="/"):
        print("Initializing...")
        self.function("coreinit.rpl",  "FSInit", True)
        if not hasattr(self, "pClient"): self.FSInitClient()
        if not hasattr(self, "pCmd"):    self.FSInitCmdBlock()
        print("Getting memory ready...")
        self.createpath(path)
        self.pDh   = self.memalloc(4, 4, True)
        print("Calling function...")
        ret = self.function("coreinit.rpl", "FSOpenDir", False, 0, self.pClient, self.pCmd, self.pPath, self.pDh, 0xFFFFFFFF)
        self.pDh = int(hexlify(self.readmem(self.pDh, 4)), 16)
        print("Return value: " + hexstr0(ret))
    def SAVEOpenDir(self, path="/", slot=255):
        print("Initializing...")
        self.function("coreinit.rpl",  "FSInit", True, 0)
        self.function("nn_save.rpl", "SAVEInit", True, 0, slot)
        print("Getting memory ready...")
        if not hasattr(self, "pClient"): self.FSInitClient()
        if not hasattr(self, "pCmd"):    self.FSInitCmdBlock()
        self.createpath(path)
        self.pDh   = self.memalloc(4, 4, True)
        print("Calling function...")
        ret = self.function("nn_save.rpl", "SAVEOpenDir", False, 0, self.pClient, self.pCmd, slot, self.pPath, self.pDh, 0xFFFFFFFF)
        self.pDh = int(hexlify(self.readmem(self.pDh, 4)), 16)
        print("Return value: " + hexstr0(ret))
    def FSReadDir(self):
        global printe
        if not hasattr(self, "pBuffer"): self.pBuffer = self.memalign(0x164, 0x20)
        print("pBuffer address: " + hexstr0(self.pBuffer))
        ret = self.function("coreinit.rpl", "FSReadDir", True, 0, self.pClient, self.pCmd, self.pDh, self.pBuffer, 0xFFFFFFFF)
        self.entry = self.readmem(self.pBuffer, 0x164)
        printe = getstr(self.entry, 100) + " "
        self.FileSystem().printflags(uint32(self.entry, 0), self.entry)
        self.FileSystem().printperms(uint32(self.entry, 4))
        print(printe)
        return self.entry, ret
    def SAVEOpenFile(self, path="/", mode="r", slot=255):
        print("Initializing...")
        self.function("coreinit.rpl",  "FSInit", True)
        self.function("nn_save.rpl", "SAVEInit", slot, True)
        print("Getting memory ready...")
        if not hasattr(self, "pClient"): self.FSInitClient()
        if not hasattr(self, "pCmd"):    self.FSInitCmdBlock()
        self.createpath(path)
        self.pMode = self.createstr(mode)
        self.pFh   = self.memalign(4, 4)
        print("Calling function...")
        print("This function may have errors")
    def FSReadFile(self):
        if not hasattr(self, "pBuffer"): self.pBuffer = self.memalign(0x200, 0x20)
        print("pBuffer address: " + hexstr0(self.pBuffer))
        ret = self.function("coreinit.rpl", "FSReadFile", False, 0, self.pClient, self.pCmd, self.pBuffer, 1, 0x200, self.pFh, 0, 0xFFFFFFFF)
        print(ret)
        return tcp.readmem(self.pBuffer, 0x200)
    def get_symbol(self, rplname, symname, noprint=False, data=0):
        self.s.send(b"\x71") #cmd_getsymbol
        request = struct.pack(">II", 8, 8 + len(rplname) + 1) #Pointers
        request += rplname.encode("UTF-8") + b"\x00"
        request += symname.encode("UTF-8") + b"\x00"
        size = struct.pack(">B", len(request))
        data = struct.pack(">B", data)
        self.s.send(size) #Read this many bytes
        self.s.send(request) #Get this symbol
        self.s.send(data) #Is it data?
        address = self.s.recv(4)
        return ExportedSymbol(address, self, rplname, symname, noprint)
    def call(self, address, *args):
        arguments = list(args)
        if len(arguments)>8 and len(arguments)<=16:
            while len(arguments) != 16:
                arguments.append(0)
            self.s.send(b"\x80")
            address = struct.unpack(">I", address)[0]
            request = struct.pack(">I16I", address, *arguments)
            self.s.send(request)
            reply = self.s.recv(8)
            return struct.unpack(">I", reply[:4])[0]
        elif len(arguments) <= 8:
            while len(arguments) != 8:
                arguments.append(0)
            self.s.send(b"\x70")
            address = struct.unpack(">I", address)[0]
            request = struct.pack(">I8I", address, *arguments)
            self.s.send(request)
            reply = self.s.recv(8)
            return struct.unpack(">I", reply[:4])[0]
        else: raise BaseException("Too many arguments!")
    def function(self, rplname, symname, noprint=False, data=0, *args):
        symbol = self.get_symbol(rplname, symname, noprint, data)
        ret = self.call(symbol.address, *args)
        return ret
    def validrange(self, address, length):
        if   0x01000000 <= address and address + length <= 0x01800000: return True
        elif 0x0E000000 <= address and address + length <= 0x10000000: return True #Depends on game
        elif 0x10000000 <= address and address + length <= 0x50000000: return True #Doesn't quite go to 5
        elif 0xE0000000 <= address and address + length <= 0xE4000000: return True
        elif 0xE8000000 <= address and address + length <= 0xEA000000: return True
        elif 0xF4000000 <= address and address + length <= 0xF6000000: return True
        elif 0xF6000000 <= address and address + length <= 0xF6800000: return True
        elif 0xF8000000 <= address and address + length <= 0xFB000000: return True
        elif 0xFB000000 <= address and address + length <= 0xFB800000: return True
        elif 0xFFFE0000 <= address and address + length <= 0xFFFFFFFF: return True
        else: return False
    def validaccess(self, address, length, access):
        if   0x01000000 <= address and address + length <= 0x01800000:
            if access.lower() == "read":  return True
            if access.lower() == "write": return False
        elif 0x0E000000 <= address and address + length <= 0x10000000: #Depends on game, may be EG 0x0E3
            if access.lower() == "read":  return True
            if access.lower() == "write": return False
        elif 0x10000000 <= address and address + length <= 0x50000000:
            if access.lower() == "read":  return True
            if access.lower() == "write": return True
        elif 0xE0000000 <= address and address + length <= 0xE4000000:
            if access.lower() == "read":  return True
            if access.lower() == "write": return False
        elif 0xE8000000 <= address and address + length <= 0xEA000000:
            if access.lower() == "read":  return True
            if access.lower() == "write": return False
        elif 0xF4000000 <= address and address + length <= 0xF6000000:
            if access.lower() == "read":  return True
            if access.lower() == "write": return False
        elif 0xF6000000 <= address and address + length <= 0xF6800000:
            if access.lower() == "read":  return True
            if access.lower() == "write": return False
        elif 0xF8000000 <= address and address + length <= 0xFB000000:
            if access.lower() == "read":  return True
            if access.lower() == "write": return False
        elif 0xFB000000 <= address and address + length <= 0xFB800000:
            if access.lower() == "read":  return True
            if access.lower() == "write": return False
        elif 0xFFFE0000 <= address and address + length <= 0xFFFFFFFF:
            if access.lower() == "read":  return True
            if access.lower() == "write": return True
        else: return False
    class FileSystem:
        Flags = enum(
            IS_DIRECTORY    = 0x80000000,
            IS_QUOTA        = 0x40000000,
            SPRT_QUOTA_SIZE = 0x20000000,
            SPRT_ENT_ID     = 0x10000000,
            SPRT_CTIME      = 0x08000000,
            SPRT_MTIME      = 0x04000000,
            SPRT_ATTRIBUTES = 0x02000000,
            SPRT_ALLOC_SIZE = 0x01000000,
            IS_RAW_FILE     = 0x00800000,
            SPRT_DIR_SIZE   = 0x00100000,
            UNSUPPORTED_CHR = 0x00080000)
        Permissions = enum(
            OWNER_READ  = 0x00004000,
            OWNER_WRITE = 0x00002000,
            OTHER_READ  = 0x00000400,
            OTHER_WRITE = 0x00000200)
        def printflags(self, flags, data):
            global printe
            if flags & self.Flags.IS_DIRECTORY:    printe += " Directory"
            if flags & self.Flags.IS_QUOTA:        printe += " Quota"
            if flags & self.Flags.SPRT_QUOTA_SIZE: printe += " .quota_size: " + hexstr0(uint32(data, 24))
            if flags & self.Flags.SPRT_ENT_ID:     printe += " .ent_id: " + hexstr0(uint32(data, 32))
            if flags & self.Flags.SPRT_CTIME:      printe += " .ctime: " + hexstr0(uint32(data, 36))
            if flags & self.Flags.SPRT_MTIME:      printe += " .mtime: " + hexstr0(uint32(data, 44))
            if flags & self.Flags.SPRT_ATTRIBUTES: pass
            if flags & self.Flags.SPRT_ALLOC_SIZE: printe += " .alloc_size: " + hexstr0(uint32(data, 20))
            if flags & self.Flags.IS_RAW_FILE:     printe += " Raw (Unencrypted) file"
            if flags & self.Flags.SPRT_DIR_SIZE:   printe += " .dir_size: " + hexstr0(uint64(data, 24))
            if flags & self.Flags.UNSUPPORTED_CHR: printe += " !! UNSUPPORTED CHARACTER IN NAME"
        def printperms(self, perms):
            global printe
            if perms & self.Permissions.OWNER_READ:  printe += " OWNER_READ"
            if perms & self.Permissions.OWNER_WRITE: printe += " OWNER_WRITE"
            if perms & self.Permissions.OTHER_READ:  printe += " OTHER_READ"
            if perms & self.Permissions.OTHER_WRITE: printe += " OTHER_WRITE"  
def hexstr0(data):
    return "0x" + hex(data).lstrip("0x").rstrip("L").zfill(8).upper()
class ExportedSymbol(object):
    def __init__(self, address, rpc=None, rplname=None, symname=None, noprint=False):
        self.address = address
        self.rpc     = rpc
        self.rplname = rplname
        self.symname = symname
        if not noprint:
            print(symname + " address: " + hexstr0(struct.unpack(">I", address)[0]))
    def __call__(self, *args):
        return self.rpc.call(self.address, *args)
#------- End TCPGecko Module -------#


#------- Start PyGecko -------#
sg.theme('DarkBlue17')
startup=0
if(os.path.isfile('startup.mp3'))==True:
        startup=1
if(startup==1):
        layout = [[sg.Text('PyGecko',font=('',40))]]
        start = sg.Window('PyGecko', layout).Finalize()
        filename = 'startup.mp3'
        mp3_length = mp3(filename).info.length
        time.sleep(0.5)

codes =  [
                   [sg.Listbox((),font=('',6),size=(48,screeny),key='list',enable_events=True,disabled=True,background_color='#383C4A',text_color='#ffffff'),sg.Multiline(font=('',7),size=(20,screeny-2),key='codebox',disabled=True,background_color='#404552',text_color='#ffffff'),sg.Multiline(font=('',7),size=(48,screeny-2),key='commentbox',disabled=True,background_color='#404552',text_color='#e4ecff')],
                   [sg.Button('AddCode',key='addbutton',size=(buttonx,1),disabled=True),sg.Button('EditCode',key='editbutton',size=(buttonx,1),disabled=True),sg.Button('SaveCodeList',key='save',size=(buttonxm,1),disabled=True),sg.Button('ExportGCTU',key='exgctubutton',size=(buttonxs,1),disabled=True)],
                   [sg.Button('SendCodes',key='sendbutton',size=(buttonxs,1),disabled=True),sg.Button('LoadCodeList',key='load',size=(buttonxm,1)),sg.Button('ImportGCTU',key='imgctubutton',size=(buttonxs,1),disabled=True)],
                   [sg.Input('192.168.',size=(16,1),key='ipi',background_color='#404552',text_color='#e4ecff'),sg.Button('Connect',key='connect'),sg.Checkbox('AutoSaveCodeList',key='autosavelist',enable_events=True),sg.Checkbox('DisableCodes',key='disable')],
]
                   
col1=[
    [sg.Input('10000000',size=(16,1),key='memoryad',background_color='#404552',text_color='#e4ecff'),sg.Button('Update',key='memoryupdate')],
    [sg.Listbox((),font=('',8),size=(20,screeny-2),key='memory',enable_events=True,background_color='#383C4A',text_color='#ffffff')]
]
col2=[
  [sg.Input('',key='memoryada',background_color='#404552',text_color='#e4ecff',size=(10,1))],
  [sg.Button('Apply',key='memoryapply')],
  [sg.Text("Can't read a Kernelarea")]
]
memoryviewer = [
    [(sg.Column(col1)),(sg.Column(col2))]
]

conversion= [
        [sg.Text('Decimal -> Hexadecimal')],
        [sg.Input('',size=(20,1),key='din',background_color='#404552',text_color='#ffffff')],
        [sg.Button('Convert',key='dhcon',size=(17,1))],
        [sg.Input('',size=(20,1),key='hout',background_color='#404552',text_color='#ffffff')],
        [sg.Text('\nHexadecimal -> Decimal')],
        [sg.Input('',size=(20,1),key='hin',background_color='#404552',text_color='#ffffff')],
        [sg.Button('Convert',key='hdcon',size=(17,1))],
        [sg.Input('',size=(20,1),key='dout',background_color='#404552',text_color='#ffffff')]
]

layout = [[sg.TabGroup([[sg.Tab('Codes',codes),sg.Tab('Memory Viewer',memoryviewer),sg.Tab('Conversion',conversion)]],tab_background_color='#080823',title_color='#bfbfbf')]]
window = sg.Window('PyGecko', layout, size=(800,420),background_color='#0d0d35',button_color=('#e4ecff','')).Finalize()
window.Minimize()

if(os.path.isfile('setting.ini'))==True:
    		with open('setting.ini') as f:
    			tmp=f.read()
    			f.close
    		if('IPAddress: ' in tmp)==False:
    			os.remove('setting.ini')
    		if(os.path.isfile('setting.ini'))==True:
    			tmpa=tmp.index('IPAddress: ')
    			tmpb=tmp.index('\n')
    			tmpa=tmp[tmpa+11:tmpb]
    			window['ipi'].update(tmpa)
    			window['autosavelist'].update('AutoSaveList: True' in tmp)
if(startup==1):
        start.close()
savestart=0
two=''
tcp=''
entry=[]
titlestmp=[]
connect=0
restore=0
memoryaddress=''
disable=False
while True:
    event, values = window.read()
    if(event == sg.WIN_CLOSED):
        break
    if(event=='memory'):
    	if(values['memory']!=[]):
    		tmp=values['memory'][0]
    		memoryaddress=tmp[:8]
    		window['memoryada'].update(tmp[15:].upper())
    if(event=='memoryapply'):
    	if(memoryaddress!=''):
    		tcp.s.send(bytes.fromhex('03'))
    		tcp.s.send(bytes.fromhex(memoryaddress+values['memoryada']))
    		tmp=tmpa.index(values['memory'][0])
    		tmpa[tmp]=memoryaddress+'   |   '+values['memoryada']
    		window['memory'].update(tmpa)
    if(event=='memoryupdate'):
    	if(tcp==''):
    		sg.popup('Not connected')
    	else:
    		if(len(values['memoryad']))>=7:
    			tmpa=[]
    			for x in range(20):
    				tmp=format((int(values['memoryad'],16)+x*4),'X')
    				tmpa.append(tmp)
    				tmpb=tcp.readmem((int(values['memoryad'],16)+x*4),4)
    				tmpb=str(tmpb.hex())
    				tmpa[x]=tmpa[x]+'   |   '+tmpb
    			window['memory'].update(tmpa)
    		else:
    			sg.popup('no')
    if(event=='sendbutton'):
    	if(tcp==''):
    		sg.popup('Not connected')
    	else:
    		tmpc=''
    		tmpe=''
    		tmpf=''
    		for x in range(len(entry)):
    		   	tmp=entry[x]
    		   	tmp=''.join(tmp)
    		   	if('<code/>' in tmp)==False:
    		   				tmpa=tmp.index('<code>')
    		   				tmpb=tmp.index('</code>')
    		   				tmpd=tmp[tmpa+6:tmpb]
    		   				if('<enabled>false</enabled>' in tmp)==False:
    		   					if('<assembly_ram_write>false</assembly_ram_write>' in tmp)==False:
    		   						tmpc=tmpc+tmpd+'\n'
    		   					else:
    		   						tmpe=tmpe+tmpd+'\n'
    		   				else:
    		   					if('<assembly_ram_write>false</assembly_ram_write>' in tmp)==False:
    		   						tmpf=tmpf+tmpd+'\n'
    		with open('tmp.log','w') as f:
    		   	f.write(tmpc)
    		   	f.close
    		with open('tmp.log') as f:
    		   	tmpc=f.readlines()
    		   	f.close
    		if(os.path.isfile('tmp.log'))==True:
    		   os.remove('tmp.log')
    		tmpa=[]
    		for x in range(len(tmpc)):
    		   	tmp=tmpc[x]
    		   	tmp=tmp.replace('\n','')
    		   	tmp=tmp.replace(' ','')
    		   	if(values['disable'])==False:
    		   		if('#' in tmp)==False:
    		   			tmpa.append(tmp)
    		   	else:
    		   		if('#' in tmp)==True:
    		   			tmp=tmp.replace('#','')
    		   			tmpa.append(tmp)
    		for x in range(len(tmpa)):
    		   	tmp=tmpa[x]
    		   	tcp.s.send(bytes.fromhex('03'))
    		   	tcp.s.send(bytes.fromhex(tmp))
    		with open('tmp.log','w') as f:
    		   	f.write(tmpe)
    		   	f.close
    		with open('tmp.log') as f:
    		   	tmpe=f.readlines()
    		   	f.close
    		if(os.path.isfile('tmp.log'))==True:
    		   os.remove('tmp.log')
    		tmp=''.join(tmpe)
    		tmp=tmp.replace('\n','')
    		tmp=tmp.replace(' ','')
    		tcp.s.send(bytes.fromhex('03'))
    		tcp.s.send(bytes.fromhex('10014CFC00000000'))
    		if(values['disable'])==False:
    			for x in range(restore):
    				tcp.s.send(bytes.fromhex('03'))
    				tcp.s.send(bytes.fromhex('0'+format(0x1133000+x*4,'X')+'00000000'))
    			for x in range(math.floor(len(tmp)/8)):
    				tcp.s.send(bytes.fromhex('03'))
    				tcp.s.send(bytes.fromhex('0'+format(0x1133000+x*4,'X')+tmp[x*8:x*8+8]))
    			tcp.s.send(bytes.fromhex('03'))
    			restore=x
    			tcp.s.send(bytes.fromhex('10014CFC00000001'))
    if(event=='autosavelist'):
    	with open('setting.ini','w') as f:
    		f.write('IPAddress: '+values['ipi']+'\nAutoSaveList: '+str(values['autosavelist']))
    		f.close
    if(event=='exgctubutton'):
    	sg.popup('Please input the title id')
    	gctu = filedialog.asksaveasfilename(filetypes=[('','.gctu')])
    	if(gctu!=()):
    	   	if(gctu!=''):
    	   		tmpc=''
    	   		for x in range(len(entry)):
    	   			tmp=''.join(entry[x])
    	   			if('<assembly_ram_write>true</assembly_ram_write>' in tmp)==False:
    	   				if('<code/>' in tmp)==False:
    	   					if('<enabled>false</enabled>' in tmp)==False:
    	   						tmpa=tmp.index('<code>')
    	   						tmpb=tmp.index('</code>')
    	   						tmpc=tmpc+tmp[tmpa+6:tmpb]
    	   						tmpc=tmpc.replace(' ','')
    	   						tmpc=tmpc.replace('\n','')
    	   		tmpa=int(tmpc,16)
    	   		with open(gctu,'wb') as f:
    	   			f.write(tmpa.to_bytes(math.floor(len(tmpc)/2),'big'))
    	   			f.close()
    if(event=='imgctubutton'):
    	gctu = filedialog.askopenfilename(filetypes=[('','.gctu')])
    	if(gctu!=()):
    	   	if(gctu!=''):
    	   		with open(gctu,'rb') as f:
    	   			tmp=f.read()
    	   			f.close()
    	   		tmp=tmp.hex().upper()
    	   		tmpa=''
    	   		tmpb=0
    	   		for x in range(math.floor(len(tmp)/8)):
    	   			if(tmpb==0):
    	   				tmpc=' '
    	   			if(tmpb==1):
    	   				tmpc='\n'
    	   				tmpb=-1
    	   			tmpa=tmpa+tmp[x*8:x*8+8]+tmpc
    	   			tmpb=tmpb+1
    	   		tmpa=tmpa[:-1]
    	   		#titlestmp.append('✓ Imported gctu codes #'+format(titlecount,'X'))
    	   		titlestmp.append('✓ Imported gctu codes')
    	   		tmpb=[]
    	   		tmpb.append('    <entry name="Imported gctu codes">\n')
    	   		tmpb.append('        <code>'+tmpa+'</code>\n')
    	   		tmpb.append('        <authors/>\n')
    	   		tmpb.append('        <raw_assembly>false</raw_assembly>\n')
    	   		tmpb.append('        <assembly_ram_write>false</assembly_ram_write>\n')
    	   		tmpb.append('        <comment></comment>\n')
    	   		tmpb.append('        <enabled>true</enabled>\n')
    	   		tmpb.append('    </entry>\n')
    	   		entry.append(tmpb)
    	   		window['list'].update(titlestmp)
    	   		titlecount=titlecount+1
    if(event=='connect'):
    	with open('setting.ini','w') as f:
    		f.write('IPAddress: '+values['ipi']+'\nAutoSaveList: '+str(values['autosavelist']))
    		f.close
    	if(connect==1):
    		window['connect'].update('Connect')
    		tcp.s.close()
    		tcp=''
    		connect=0
    	else:
    		window['connect'].update('Disconnect')
    		tcp = TCPGecko(values['ipi'])
    		connect=1
    if(event=='addbutton'):
    	     addl = [
    	         [sg.Input(key='addtitle',size=(56),background_color='#404552',text_color='#ffffff')],
    	         [sg.Multiline(key='addcode',size=(22,10),background_color='#404552',text_color='#ffffff'),sg.Multiline(key='addcomment',size=(31,10),background_color='#404552',text_color='#ffffff')],
    	         [sg.Button('CopyCode',key='addcopy'),sg.Button('PasteCode',key='addpaste'),sg.Checkbox('AssemblyRAMWrite',key='addasm'),sg.Button('Cancel',key='addcancel'),sg.Button('OK',key='addok')]
    	     ]
    	     addwin = sg.Window('AddCode',addl,keep_on_top=True,modal=True,finalize=True)
    	     while True:
    	     	event, value = addwin.read()
    	     	if(event == sg.WIN_CLOSED):
    	     		break
    	     	if(event=='addcopy'):
    	     		tmp=value['addcode']
    	     		root=tkinter.Tk()
    	     		root.clipboard_append(tmp)
    	     		root.destroy()
    	     	if(event=='addpaste'):
    	     		root=tkinter.Tk()
    	     		tmp=root.clipboard_get()
    	     		root.destroy()
    	     		addwin['addcode'].update(tmp)
    	     	if(event=='addcancel'):
    	     		addwin.close()
    	     	if(event=='addok'):
    	     		tmp=value['addtitle']
    	     		tmpa=str(value['addasm']).lower()
    	     		#titlestmp.append('✓ '+tmp+ ' #'+format(titlecount,'X'))
    	     		titlestmp.append('✓ '+tmp)
    	     		tmpb=[]
    	     		tmpb.append('    <entry name="'+tmp+'">\n')
    	     		tmpb.append('        <code>'+value['addcode']+'</code>\n')
    	     		tmpb.append('        <authors/>\n')
    	     		tmpb.append('        <raw_assembly>false</raw_assembly>\n')
    	     		tmpb.append('        <assembly_ram_write>'+tmpa+'</assembly_ram_write>\n')
    	     		tmpb.append('        <comment>'+value['addcomment']+'</comment>\n')
    	     		tmpb.append('        <enabled>true</enabled>\n')
    	     		tmpb.append('    </entry>\n')
    	     		entry.append(tmpb)
    	     		window['list'].update(titlestmp)
    	     		titlecount=titlecount+1
    	     		addwin.close()
    	     addwin.close()
    if(event=='editbutton'):
    	     editl = [
    	         [sg.Input(key='edittitle',size=(67),background_color='#404552',text_color='#ffffff')],
    	         [sg.Multiline(key='editcode',size=(22,10),background_color='#404552',text_color='#ffffff'),sg.Multiline(key='editcomment',size=(40,10),background_color='#404552',text_color='#ffffff')],
    	         [sg.Button('CopyCode',key='editcopy'),sg.Button('PasteCode',key='editpaste'),sg.Button('Delete',key='deletecode'),sg.Checkbox('AssemblyRAMWrite',key='editasm'),sg.Button('Cancel',key='editcancel'),sg.Button('OK',key='editok')]
    	     ]
    	     editwin = sg.Window('EditCode',editl,keep_on_top=True,modal=True,finalize=True)
    	     tmpc=''.join(thisentry)
    	     tmp=tmpc.index('<entry name="')
    	     tmpa=tmpc.index('">')
    	     tmpb=tmpc[tmp+13:tmpa]
    	     editwin['edittitle'].update(tmpb)
    	     if('<code/>' in tmpc)==False:
    	     	tmp=tmpc.index('<code>')
    	     	tmpa=tmpc.index('</code>')
    	     	tmpb=tmpc[tmp+6:tmpa]
    	     	editwin['editcode'].update(tmpb)
    	     if('<comment/>' in tmpc)==False:
    	     	tmp=tmpc.index('<comment>')
    	     	tmpa=tmpc.index('</comment>')
    	     	tmpb=tmpc[tmp+9:tmpa]
    	     	editwin['editcomment'].update(tmpb)
    	     if('<assembly_ram_write>true</assembly_ram_write>' in tmpc)==True:
    	     	editwin['editasm'].update(True)
    	     while True:
    	     	event, value = editwin.read()
    	     	if(event == sg.WIN_CLOSED):
    	     		break
    	     	if(event=='editcopy'):
    	     		tmp=value['editcode']
    	     		root=tkinter.Tk()
    	     		root.clipboard_append(tmp)
    	     		root.destroy()
    	     	if(event=='editpaste'):
    	     		root=tkinter.Tk()
    	     		tmp=root.clipboard_get()
    	     		root.destroy()
    	     		editwin['editcode'].update(tmp)
    	     	if(event=='editcancel'):
    	     		editwin.close()
    	     	if(event=='editok'):
    	     		tmp=value['edittitle']
    	     		tmpa=str(value['editasm']).lower()
    	     		count=titlestmp.index(values['list'][0])
    	     		#titlestmp[count]=('✓ '+tmp+ ' #'+format(count,'X'))
    	     		titlestmp[count]=('✓ '+tmp)
    	     		tmpb=[]
    	     		tmpb.append('    <entry name="'+tmp+'">\n')
    	     		tmpb.append('        <code>'+value['editcode']+'</code>\n')
    	     		tmpb.append('        <authors/>\n')
    	     		tmpb.append('        <raw_assembly>false</raw_assembly>\n')
    	     		tmpb.append('        <assembly_ram_write>'+tmpa+'</assembly_ram_write>\n')
    	     		tmpb.append('        <comment>'+value['editcomment']+'</comment>\n')
    	     		tmpb.append('        <enabled>true</enabled>\n')
    	     		tmpb.append('    </entry>\n')
    	     		entry[count]=tmpb
    	     		window['list'].update(titlestmp)
    	     		editwin.close()
    	     	if(event=='deletecode'):
    	     		tmp=entry.index(thisentry)
    	     		del entry[tmp]
    	     		del titlestmp[tmp]
    	     		window['list'].update(titlestmp)
    	     		window['codebox'].update('')
    	     		window['commentbox'].update('')
    	     		editwin.close()
    if(event=='dhcon'):
    	din=window['din'].get()
    	if(din!=''):
    		if(din.isdigit())==True:
    			din=format(int(din),'X')
    			window['hout'].update(din)
    		else:
    			sg.popup('Invalid value')
    if(event=='hdcon'):
    	hin=window['hin'].get()
    	if(hin!=''):
    		hin=int(hin,16)
    		window['dout'].update(hin)
    if(event=='save'):
    	tmp=''
    	for x in range(len(entry)):
    		tmp=tmp+''.join(entry[x])
    	tmp='<?xml version="1.0" encoding="UTF-16"?>\n<codes>\n'+tmp+'</codes>\n'
    	save = filedialog.asksaveasfilename(filetypes=[('','.xml')])
    	if(save!=()):
    	 		if(save!=''):
    	 			with open(save,'w') as f:
    	 				f.write(tmp)
    	 				f.close
    if(event=='load'):
        load = filedialog.askopenfilename(filetypes=[('','.xml')])
        if(load!=()):
                if(load!=''):
                    savestart=1
                    window['editbutton'].update(disabled=True)
                    with open(load) as f:
                        tmp=f.readlines()
                        f.close()
                    titlestmp=[]
                    codes=[]
                    entry=[]
                    titlecount=0
                    i=0
                    for x in range(len(tmp)):
                    	tmpa=tmp[x]
                    	if('<entry name=' in tmpa)==True:
                    	    tmpb=tmpa.index('<entry name="')
                    	    tmpd=tmpa[tmpb:]
                    	    tmpc=tmpd.index('">')
                    	    #titlestmp.append(tmpa[tmpb+13:tmpc+4]+' #'+format(titlecount,'X'))
                    	    titlestmp.append(tmpa[tmpb+13:tmpc+4])
                    	    titlecount=titlecount+1
                    	    i=x
                    	if('</entry>' in tmpa)==True:
                    	    entry.append(tmp[i:x+1])
                    for x in range(len(titlestmp)):
                    	thisentry=entry[x]
                    	if('<enabled>true</enabled>' in (''.join(thisentry)))==True:
                    		titlestmp[x]='✓ '+titlestmp[x]
                    	else:
                    		titlestmp[x]='　'+titlestmp[x]
                    window['list'].update(titlestmp,disabled=False)
                    window['addbutton'].update(disabled=False)
                    window['exgctubutton'].update(disabled=False)
                    window['imgctubutton'].update(disabled=False)
                    window['sendbutton'].update(disabled=False)
                    window['save'].update(disabled=False)
    if(savestart==1):
    		if(values['autosavelist'])==True:
    			tmp=''
    			for x in range(len(entry)):
    				tmp=tmp+''.join(entry[x])
    			tmp='<?xml version="1.0" encoding="UTF-16"?>\n<codes>\n'+tmp+'</codes>\n'
    			with open(load,'w') as f:
    						f.write(tmp)
    						f.close
    if(event == 'list'):
        window['editbutton'].update(disabled=False)
        if(values['list']==two):
            count=titlestmp.index(two[0])
            tmp=''.join(thisentry)
            if(two[0][:2]=='✓ '):
            	titlestmp[count]='　'+titlestmp[count][2:]
            	tmp=tmp.replace('<enabled>true</enabled>','<enabled>false</enabled>')
            else:
            	titlestmp[count]='✓ '+titlestmp[count][1:]
            	tmp=tmp.replace('<enabled>false</enabled>','<enabled>true</enabled>')
            entry[count]=tmp
            window['list'].update(titlestmp)
        twi=values['list']
        if(values['list']!=two):
            thisentry=entry[titlestmp.index(twi[0])]
            thisentrytmp=''
            tmp=''.join(thisentry)
            tmpa=''
            if('<code/>' in tmp)==False:
            	tmpa=tmp.index('<code>')
            	tmpb=tmp.index('</code>')
            	tmpa=tmp[tmpa+6:tmpb]
            window['codebox'].update(tmpa)
            tmpa=''
            if('<comment/>' in tmp)==False:
            	tmpa=tmp.index('<comment>')
            	tmpb=tmp.index('</comment>')
            	tmpa=tmp[tmpa+9:tmpb]
            window['commentbox'].update(tmpa)
        two=values['list']
window.close()
#------- End PyGecko -------#
